# py-ipfs-lite: Routing Table Growth & Connection Manager Plateau

Repos involved: `sumanjeet0012/py-libp2p` (Kademlia DHT), `IPFS-Meshkit/py-ipfs-lite`
(connection maintenance)

## Symptoms

- Node connects to bootstrap peers, performs random walks / DHT lookups, and
  peers accumulate in the peerstore — but the routing table grows only very
  slowly, well behind the peerstore.
- Connection manager configured with `low_water=100`, `high_water=300`.
  Observed: connections plateau at ~100 and stay there indefinitely, even
  though the peerstore holds 3000+ known peers and there's 200 slots of
  unused headroom under `high_water`.

## Issue 1: Routing table not being populated from lookup results

### Root cause: `libp2p/kad_dht/peer_routing.py`

Two different code paths touch discovered peers, and only one of them
updates the routing table.

**`_query_peer_for_closest()`** — runs on every FIND_NODE query/response
during a lookup. When it parses the `closerPeers` in a response (the actual
output of the walk), it does this:

```python
new_peer_id = ID(peer_data.id)
if new_peer_id not in results:
    results.append(new_peer_id)
if peer_data.addrs:
    addrs = [Multiaddr(addr) for addr in peer_data.addrs]
    self.host.get_peerstore().add_addrs(new_peer_id, addrs, 3600)   # peerstore only
```
Every peer surfaced by a lookup round is written to the peerstore and
nowhere else.

**`refresh_routing_table()`** is the only place that calls
`routing_table.add_peer()` for newly-discovered peers — but only for the
**final converged `closest_peers`** result of a whole lookup (bounded to
`count`, typically ~20 peers):
```python
closest_peers = await self.find_closest_peers_network(local_id.to_bytes())
for peer_id in closest_peers:
    ...
    await self.routing_table.add_peer(peer_info)
```

Net effect: out of everything a walk discovers, only the last-mile top-K
survivors of a *full* lookup ever reach the routing table. Everything else
seen along the way — which is most of what accumulates in the peerstore —
is never evaluated for inclusion. The routing table grows by roughly K
peers per full refresh cycle instead of by every peer actually observed.

### Fix

Add the peer to the routing table at the same point it's added to the
peerstore, inside `_query_peer_for_closest`:

```python
if peer_data.addrs:
    addrs = [Multiaddr(addr) for addr in peer_data.addrs]
    self.host.get_peerstore().add_addrs(new_peer_id, addrs, 3600)
    try:
        await self.routing_table.add_peer(PeerInfo(new_peer_id, addrs))
    except Exception as e:
        logger.debug(
            f"Failed to add discovered peer {new_peer_id} to routing table: {e}"
        )
```
(`PeerInfo` is already imported in this file.)

Note: the routing table will still cap what it *keeps* per k-bucket — that's
correct Kademlia behavior, not a bug. The fix just makes sure every
discovered peer actually gets a chance to be evaluated for a bucket slot,
instead of only the final top-K of a completed lookup.

## Issue 2: Connections plateau at low_water, never grow toward high_water

### Root cause: `py_ipfs_lite/peer.py`, `_connection_keeper_task`

The task's own docstring states the actual behavior:
> "If active connections drop below low_watermark (100), re-dials bootstrap
> peers and triggers a DHT random walk to discover new peers."

The code matches:
```python
if total < low:
    # re-dial bootstrap peers + trigger DHT walk
    ...
```
There is no branch for `low <= total < high`. Once connections cross 100,
the loop logs the count and sleeps another 30s — nothing dials further, and
nothing draws on the 3000+ peers already sitting in the peerstore.
`high_water` is only used as the ceiling passed into
`raw_swarm.connection_config.max_connections`, which is what py-libp2p's own
pruner trims *down to* if the count is ever exceeded — it isn't something
anything actively climbs toward.

### Fix

Add an opportunistic-growth branch that dials from the peerstore whenever
there's headroom under `high`, independent of the emergency
bootstrap+DHT-walk path used when critically low:

```python
high = self.config.conn_mgr_high_water

if total < low:
    # existing emergency logic: bootstrap re-dial + DHT walk
    ...
elif total < high:
    # opportunistic growth: headroom exists and the peerstore has
    # candidates — use them instead of sitting idle
    connected_ids = {c.muxed_conn.peer_id for c in raw_swarm.get_connections()}
    candidates = [
        p for p in self.host.get_peerstore().peers_with_addrs()
        if p not in connected_ids and p != self.host.get_id()
    ]
    random.shuffle(candidates)
    target = min(high - total, 20)  # dial in modest batches, not all at once
    for peer_id in candidates[:target]:
        try:
            addrs = self.host.get_peerstore().addrs(peer_id)
            with trio.move_on_after(5):
                await self.host.connect(PeerInfo(peer_id, addrs))
        except Exception as dial_err:
            logger.debug(f"[ConnectionKeeper] Opportunistic dial failed: {dial_err}")
```

Batching matters here — `target = min(high - total, 20)` caps each cycle to
a modest number of new dials. Dialing all ~200 remaining slots at once every
30s would reproduce the EMFILE / rate-limiter pressure already fixed in the
resource manager work.

## Why these two compound each other

- Issue 1 keeps the routing table thin relative to the peerstore, so DHT
  queries have a smaller pool of "known good" peers to route through even
  though many more are sitting in the peerstore unused.
- Issue 2 means even the peers that *are* known (peerstore) never get
  dialed once the node crosses the low watermark, so connection diversity
  stays capped regardless of how many peers are discovered.

Fixing both together should let the node use its full configured range
(100–300 connections) and grow the routing table roughly in step with the
peerstore instead of trailing far behind it.

## How to verify

1. Apply both fixes and restart the node.
2. Track `routing_table` size vs `peerstore` size over time via
   `/api/v0/debug/routing_table` and `/api/v0/debug/peerstore` — the gap
   between them should shrink noticeably compared to before.
3. Track `/api/v0/swarm/peers` count — should climb from ~100 toward 300
   over a few `_connection_keeper_task` cycles (30s each) and hold there,
   instead of flatlining at the low watermark.
4. Watch for renewed EMFILE or degradation warnings during the ramp-up —
   if the batch size of 20 new dials per cycle is still too aggressive for
   the current fd/ulimit headroom, lower it further.
