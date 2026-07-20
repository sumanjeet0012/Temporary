# py-ipfs-lite: Slow Connection Ramp-Up After Routing/Watermark Fixes

Repo: `IPFS-Meshkit/py-ipfs-lite`, commit `d5194eb` (deployed after the
routing-table and connection-manager watermark fixes)

## Symptom

`conn_mgr_low_water` raised to 400 (`conn_mgr_high_water` = 600). With only
~50 active connections — well below the low watermark — the node was
expected to ramp up quickly. Instead, only a handful of new connections were
made per 30-second `_connection_keeper_task` cycle.

## Root causes

Three separate issues in `_connection_keeper_task` (`py_ipfs_lite/peer.py`),
found by re-reading the actual deployed diff.

### 1. Opportunistic peerstore-dial branch is dead code while DHT is enabled

The branch that dials additional peers from the peerstore was added as:
```python
if total < low:
    ...
    if self.routing:
        ...
    elif total < self.config.conn_mgr_high_water:   # <-- paired with `if self.routing:`
        ...opportunistic peerstore dial...
```
The `elif` is nested one level too deep — it's the else-branch of `if
self.routing:`, not a sibling of the outer `if total < low:`. Since DHT
routing is enabled (`self.routing` is truthy), this branch **never
executes**, regardless of connection count. The peerstore-based dialing
intended to close the gap between low and high watermark is unreachable in
this deployment.

### 2. With #1 dead, only 6 hardcoded bootstrap peers get redialed per cycle

```python
bootstrap_addrs = default_bootstrap_peers()[:6]
for addr_str in bootstrap_addrs:
    ...
    await self.host.connect(info)
```
With the opportunistic branch unreachable, this — 6 bootstrap peers, once
per 30s cycle — is the *entire* active-dialing behavior while below low
water. It never draws on the peerstore (now much larger thanks to the
routing-table fix). This directly explains the "only a few new connections
per 30s" symptom: dialing is capped at +6/cycle, far short of the ~350
connections needed to reach 400.

### 3. Both dial loops are serial, not concurrent

```python
for addr_str in bootstrap_addrs:
    with trio.move_on_after(5):
        await self.host.connect(info)   # awaited one at a time
```
Same pattern in the (currently dead) opportunistic loop. Each dial has its
own 5s timeout, but attempts run one after another rather than in parallel.
If several of the 6 bootstrap/candidate peers are slow or unreachable —
routine on a real network — a single cycle can burn 20–30+ seconds on
timeouts alone, so even the full 6 bootstrap attempts may not reliably
complete within one 30s window.

## Fix

Restructure the two branches as independent `if` statements (not
`if`/`elif`) so opportunistic peerstore dialing runs whenever there's
headroom, whether or not the node is also below low water — and dial
concurrently via a trio nursery in both loops:

```python
if total < low:
    logger.info(...)
    bootstrap_addrs = default_bootstrap_peers()[:6]

    async def _dial_bootstrap(addr_str: str) -> None:
        try:
            info = info_from_p2p_addr(Multiaddr(addr_str))
            with trio.move_on_after(5):
                await self.host.connect(info)
        except Exception as dial_err:
            logger.debug(f"[ConnectionKeeper] Bootstrap dial failed: {dial_err}")

    async with trio.open_nursery() as n:
        for addr_str in bootstrap_addrs:
            n.start_soon(_dial_bootstrap, addr_str)

    if self.routing:
        raw_routing = ...
        if hasattr(raw_routing, "refresh_routing_table"):
            ...  # unchanged DHT refresh trigger

# Sibling `if`, not `elif` — must run whenever there's headroom, whether
# or not we're also below low water.
if total < self.config.conn_mgr_high_water:
    high = self.config.conn_mgr_high_water
    connected_ids = {c.muxed_conn.peer_id for c in raw_swarm.get_connections()}
    candidates = [
        p for p in self.host.get_peerstore().peers_with_addrs()
        if p not in connected_ids and p != self.host.get_id()
    ]
    random.shuffle(candidates)
    # More aggressive batch while critically below low water — 400/600
    # is a much bigger gap than the original 100/300 this was tuned for.
    batch = 50 if total < low else 20
    target = min(high - total, batch)

    async def _dial_candidate(peer_id) -> None:
        try:
            addrs = self.host.get_peerstore().addrs(peer_id)
            with trio.move_on_after(5):
                await self.host.connect(PeerInfo(peer_id, addrs))
        except Exception as dial_err:
            logger.debug(f"[ConnectionKeeper] Opportunistic dial failed: {dial_err}")

    async with trio.open_nursery() as n:
        for peer_id in candidates[:target]:
            n.start_soon(_dial_candidate, peer_id)
```

Key changes:
- Peerstore-dial block is now a sibling `if`, so it fires in every cycle
  with headroom — including cycles where the node is also below low water
  and redialing bootstrap peers.
- Both loops dial concurrently through a nursery instead of serially, so a
  batch's wall-clock cost is bounded by the 5s per-attempt timeout, not by
  `batch_size × 5s`.
- Batch size scales up (50 vs 20) while critically below low water, since
  400/600 is a much larger target than the original 100/300 configuration.

## Expected result

Going from 50 → 400 connections should take roughly 7–8 keeper cycles
(~4 minutes) at worst, instead of crawling at +6 connections per cycle
indefinitely.

## How to verify

1. Deploy the fix and restart the node with `low=400`, `high=600`.
2. Watch `[ConnectionKeeper]` log lines each cycle — connection count should
   climb noticeably every 30s instead of by single digits.
3. Track `/api/v0/swarm/peers` `NumPeers` over a few minutes — should
   approach 400 within under 5 minutes under normal network conditions.
4. Watch for renewed EMFILE or resource-manager degradation warnings during
   the faster ramp — if the larger batch size (50) reintroduces fd/rate
   pressure, scale it back down.
