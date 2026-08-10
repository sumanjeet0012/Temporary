# Notifee in py-libp2p — A Complete Guide

> **Audience:** py-libp2p maintainers and contributors.
> **Scope:** What a notifee is, how it is wired into the network stack, how each built-in notifee uses it, and how to write your own.
> **Source of truth:** the `py-libp2p` checkout at `/Users/sumanjeet/code/py-libp2p` (this guide references exact file:line locations).

---

## 1. What is a Notifee?

A **notifee** is py-libp2p's observer/callback mechanism for **network lifecycle events**.
It is the Python equivalent of the `network.Notifiee` interface in go-libp2p
(which itself is a play on "notify": the *notifiee* is the object that **receives**
notifications, while the network is the *notifier* that emits them).

It lets a component (the pubsub subsystem, the connection manager's tag store, the
identify protocol, or your own code) be **notified asynchronously** whenever one of
these things happens on the local node's `Swarm`:

| Event | Trigger |
|-------|---------|
| `connected` | A new connection to a remote peer is established |
| `disconnected` | An existing connection to a remote peer is closed |
| `opened_stream` | A new stream is opened over a connection |
| `closed_stream` | A stream is closed |
| `listen` | The node starts listening on a new multiaddress |
| `listen_close` | The node stops listening on a multiaddress |

The name *notifee* follows go-libp2p naming. In js-libp2p the same concept is
called **"events"** (`libp2p.addEventListener('peer:connect', ...)`), and in the
abstract libp2p spec it is part of the *network eventing* model.

---

## 2. The `INotifee` interface

Defined in `libp2p/abc.py:1890`. It is an abstract base class with **six abstract
async methods** — every notifee must implement all of them (or inherit a no-op
implementation).

```python
class INotifee(ABC):
    @abstractmethod
    async def opened_stream(self, network: "INetwork", stream: INetStream) -> None: ...

    @abstractmethod
    async def closed_stream(self, network: "INetwork", stream: INetStream) -> None: ...

    @abstractmethod
    async def connected(self, network: "INetwork", conn: INetConn) -> None: ...

    @abstractmethod
    async def disconnected(self, network: "INetwork", conn: INetConn) -> None: ...

    @abstractmethod
    async def listen(self, network: "INetwork", multiaddr: Multiaddr) -> None: ...

    @abstractmethod
    async def listen_close(self, network: "INetwork", multiaddr: Multiaddr) -> None: ...
```

Every callback receives:

- `network: INetwork` — the swarm/network instance that emitted the event (so a
  notifee can reach back into the network, e.g. `network.connections`).
- A subject object describing *what* happened:
  - `INetConn` for `connected` / `disconnected` — the connection that opened/closed.
  - `INetStream` for `opened_stream` / `closed_stream` — the stream that opened/closed.
  - `Multiaddr` for `listen` / `listen_close` — the address that was bound/unbound.

### Why are they all abstract?

There is no "default no-op" base class — each concrete notifee is expected to
implement all six methods explicitly. In practice the built-in ones implement
the methods they care about and make the rest trivial no-ops
(e.g. `async def opened_stream(...): return None` or `await trio.lowlevel.checkpoint()`).

---

## 3. Registration: how a notifee gets attached

The `Swarm` owns a list of notifees and exposes a single registration method.

**Interface declaration** — `libp2p/abc.py:1675`:
```python
def register_notifee(self, notifee: "INotifee") -> None: ...
```

**Implementation** — `libp2p/network/swarm.py:2130`:
```python
def register_notifee(self, notifee: INotifee) -> None:
    self.notifees.append(notifee)
```

The list is initialized in `Swarm.__init__` (`swarm.py:217`):
```python
self.notifees: list[INotifee] = []
```

> Note: there is currently **no `unregister_notifee`**. Registration is
> append-only for the lifetime of the swarm. (Relevant to PeerDrop: we had to
> reach into a private `_peer_discovered_handlers` list elsewhere for the same
> class of problem — an unregister API would be a clean public addition.)

### The registration points in the codebase

| Where | What registers | Why |
|-------|---------------|-----|
| `libp2p/network/swarm.py:273` | `TagStoreNotifee(self.tag_store)` | Keeps the connection-manager tag store in sync with real connections |
| `libp2p/host/basic_host.py:325` | `_IdentifyNotifee(self)` | Triggers automatic Identify on connect / listen |
| `libp2p/pubsub/pubsub.py:398` | `PubsubNotifee(peer_send, dead_peer_send)` | Feeds pubsub with new/dead peer IDs |

Registration is always done from the *component's* constructor — the swarm itself
does not know about pubsub, identify, or the tag store; it just stores opaque
`INotifee` objects.

---

## 4. Dispatch: how events reach every notifee

When a lifecycle event happens, the `Swarm` calls a **`notify_*`** method that
**fan-outs to every registered notifee concurrently** using a Trio nursery.

`libp2p/network/swarm.py:2137–2192`:

```python
async def notify_opened_stream(self, stream: INetStream) -> None:
    async with trio.open_nursery() as nursery:
        for notifee in self.notifees:
            nursery.start_soon(notifee.opened_stream, self, stream)

async def notify_connected(self, conn: INetConn) -> None:
    async with trio.open_nursery() as nursery:
        for notifee in self.notifees:
            nursery.start_soon(notifee.connected, self, conn)

async def notify_disconnected(self, conn: INetConn) -> None:
    async with trio.open_nursery() as nursery:
        for notifee in self.notifees:
            nursery.start_soon(notifee.disconnected, self, conn)

async def notify_listen(self, multiaddr: Multiaddr) -> None:
    async with trio.open_nursery() as nursery:
        for notifee in self.notifees:
            nursery.start_soon(notifee.listen, self, multiaddr)

async def notify_closed_stream(self, stream: INetStream) -> None:
    ...
    async with trio.open_nursery() as nursery:
        for notifee in self.notifees:
            nursery.start_soon(notifee.closed_stream, self, stream)

async def notify_listen_close(self, multiaddr: Multiaddr) -> None:
    async with trio.open_nursery() as nursery:
        for notifee in self.notifees:
            nursery.start_soon(notifee.listen_close, self, multiaddr)

# Generic notifier used by NetStream._notify_closed
async def notify_all(self, notifier: Callable[[INotifee], Awaitable[None]]) -> None:
    async with trio.open_nursery() as nursery:
        for notifee in self.notifees:
            nursery.start_soon(notifier, notifee)
```

Key properties of the dispatch model:

1. **Concurrent fan-out** — each notifee callback runs as its own task in a
   nursery; a slow notifee does not block the others.
2. **The nursery waits for all** — `async with trio.open_nursery()` blocks until
   every spawned callback completes. Event emission is therefore *synchronous
   from the caller's perspective*: when `notify_connected()` returns, all
   notifees have finished handling the event.
3. **Ordering** — notifees are invoked in registration order (list order), but
   run concurrently so completion order is not guaranteed.
4. **Failure isolation is the notifee's job** — if one notifee's callback raises,
   the nursery propagates the exception and the event emitter may fail. This is
   why the built-in notifees are defensive (e.g. `PubsubNotifee` swallows
   `trio.BrokenResourceError`, `_IdentifyNotifee` wraps pushes in try/except).

---

## 5. Where the events are emitted (trigger points)

The `notify_*` calls are woven into the connection / stream / listener lifecycle:

### 5.1 `connected` — `libp2p/network/swarm.py:2017`

After a new `SwarmConn` is created, registered in `self.connections[peer_id]`,
trimmed, and the connection pruner has run:

```python
# Call notifiers since event occurred
await self.notify_connected(swarm_conn)
```

**Important subtlety (swarm.py:1998–2003):** if a connection for the peer
already exists, the swarm *reuses* it and returns early:

```python
logger.debug(f"Connection already exists for peer {peer_id}")
await swarm_conn.close()
return existing_conn  # no notify_connected is fired
```

This "dedupe on existing connection" behavior is a deliberate design choice
(one pubsub stream per peer), but it has a consequence for the pubsub
registration race — see §8.

### 5.2 `disconnected` — `libp2p/network/connection/swarm_connection.py:212`

When a connection is closed (in `SwarmConnection.close()`), after streams are
reset and a short settling delay:

```python
# Notify all listeners about the disconnection
await self._notify_disconnected()          # line 212
...
async def _notify_disconnected(self) -> None:
    await self.swarm.notify_disconnected(self)
```

### 5.3 `opened_stream` — `libp2p/network/connection/swarm_connection.py:286`

Every new stream (inbound and outbound) is wrapped in a `NetStream` and
announced:

```python
async def _add_stream(self, muxed_stream: IMuxedStream) -> NetStream:
    net_stream = NetStream(muxed_stream, self, self._metric_send_channel)
    if self.event_started.is_set():
        await net_stream.set_state(StreamState.OPEN)
    self.streams.add(net_stream)
    await self.swarm.notify_opened_stream(net_stream)
    return net_stream
```

### 5.4 `closed_stream` — `swarm_connection.py:276, 357` and `net_stream.py:364`

Called when a stream is closed or reset, from both the inbound handler path and
`NetStream`'s own close logic (`NetStream._notify_closed` → `notify_all`).

Note that `notify_closed_stream` in `swarm.py:2157` also performs one-time
**resource manager cleanup** (releasing stream permits and rcmgr resources),
guarded by a `_resource_released` flag on the stream so it runs exactly once.

### 5.5 `listen` — `libp2p/network/swarm.py:1488`

After a listener successfully binds a multiaddress:

```python
await listener.listen(maddr)
await self.notify_listen(maddr)
```

### 5.6 `listen_close` — `libp2p/network/swarm.py:1832`

During swarm shutdown, after each listener is closed:

```python
await listener.close()
await self.notify_listen_close(multiaddr)
```

---

## 6. The built-in notifees

### 6.1 `PubsubNotifee` — the most important one

`libp2p/pubsub/pubsub_notifee.py:21`

This is the notifee that makes GossipSub/pubsub work at all. It **bridges
network connection events into pubsub's internal peer queues**:

```python
class PubsubNotifee(INotifee):
    def __init__(self, initiator_peers_queue, dead_peers_queue):
        self.initiator_peers_queue = initiator_peers_queue   # new peers
        self.dead_peers_queue = dead_peers_queue             # dead peers

    async def connected(self, network, conn):
        await self.initiator_peers_queue.send(conn.muxed_conn.peer_id)

    async def disconnected(self, network, conn):
        await self.dead_peers_queue.send(conn.muxed_conn.peer_id)
```

The other four methods (`opened_stream`, `closed_stream`, `listen`,
`listen_close`) are no-ops that just yield (`await trio.lowlevel.checkpoint()`).

**Why queues instead of calling pubsub directly?** The notifee callbacks run
inside the swarm's nursery. Pubsub's peer handling (`_handle_new_peer`) does
I/O — it *opens a stream* to the peer — which must not block connection setup.
The trio memory channels decouple the two:
the notifee only does a cheap `send`, and pubsub's long-running consumer tasks
do the expensive work.

The channels are created in `Pubsub.__init__` (`libp2p/pubsub/pubsub.py:391`):

```python
peer_send, peer_receive = trio.open_memory_channel[ID](0)
dead_peer_send, dead_peer_receive = trio.open_memory_channel[ID](0)
self.peer_receive_channel = peer_receive
self.dead_peer_receive_channel = dead_peer_receive
# Register a notifee
self.host.get_network().register_notifee(
    PubsubNotifee(peer_send, dead_peer_send)
)
```

**Consumer side** — `libp2p/pubsub/pubsub.py:934`:

```python
async def handle_peer_queue(self) -> None:
    async with self.peer_receive_channel:
        async for peer_id in self.peer_receive_channel:
            # Add Peer - wrap in exception handler to prevent service crash
            self.manager.run_task(self._handle_new_peer_safe, peer_id)
```

`_handle_new_peer_safe` (pubsub.py:880) wraps `_handle_new_peer` in try/except
so a protocol-negotiation failure can never crash the pubsub service. On success,
`_handle_new_peer` opens a stream to the peer on a pubsub protocol and registers
it in `self.peers`.

**Dead-peer side** — `pubsub.py:946`:

```python
async def handle_dead_peer_queue(self) -> None:
    async with self.dead_peer_receive_channel:
        async for peer_id in self.dead_peer_receive_channel:
            ...
            self._handle_dead_peer(peer_id)
```

`_handle_dead_peer` (pubsub.py:898) cleans up: forgets subscriptions, removes the
peer from `self.peers`, closes its outbound queue, and calls `router.remove_peer`.

**Summary of the full data flow:**

```
new TCP/yamux connection
        │
        ▼
Swarm.new_connection ──► notify_connected(conn)            [swarm.py:2017]
        │                        │
        │                        ▼
        │              PubsubNotifee.connected              [pubsub_notifee.py:33]
        │                        │
        │                        ▼  (cheap, non-blocking)
        │              initiator_peers_queue.send(peer_id)
        │                        │
        ▼                        ▼
Pubsub.handle_peer_queue  ──►  _handle_new_peer_safe(peer_id)   [pubsub.py:934, 880]
                                       │
                                       ▼  (expensive: opens stream, negotiates protocol)
                              _handle_new_peer(peer_id)          [pubsub.py:~762]
                                       │
                                       ▼
                              peer registered in self.peers
                              router.add_peer / subscriptions exchanged
```

### 6.2 `_IdentifyNotifee` — automatic Identify

`libp2p/host/basic_host.py:138`

Triggers the Identify protocol automatically, mirroring go-libp2p's
`Connected → IdentifyWait` behavior:

- `connected()` → calls `host._on_notifee_connected(conn)` → fires outbound
  Identify to the new peer.
- `disconnected()` → `host._on_notifee_disconnected(conn)`.
- `listen()` → schedules a debounced `_push_identify_to_all_peers()` after the
  batch of bindings completes (so multiple addresses bound in rapid succession
  produce a single IdentifyPush).

Note it holds a **weakref** to the host (`weakref.ref(host)`) so the notifee
never keeps the host alive, and guards every callback against a dead reference.

### 6.3 `TagStoreNotifee` — connection-manager bookkeeping

`libp2p/network/tag_store.py:493`

Keeps the connection manager's `TagStore` in sync with reality — the Python
equivalent of go-libp2p's `cmNotifee` that drives `BasicConnMgr`'s peerInfo map:

- `connected()` → `store.record_connection(peer_id, id(conn))`
- `disconnected()` → `store.remove_connection(peer_id, id(conn))`

Registered by the swarm itself at `swarm.py:273` in
`_init_connection_management()`. The other four callbacks are no-ops.

---

## 7. Writing your own notifee

Subclass `INotifee`, implement all six methods, and register it on the network.

```python
import trio
from multiaddr import Multiaddr
from libp2p.abc import INotifee, INetConn, INetwork, INetStream


class ConnectionCounterNotifee(INotifee):
    """Counts live connections and logs stream activity."""

    def __init__(self) -> None:
        self.connected_count = 0

    async def connected(self, network: INetwork, conn: INetConn) -> None:
        self.connected_count += 1
        print(f"[notifee] connected to {conn.muxed_conn.peer_id}")

    async def disconnected(self, network: INetwork, conn: INetConn) -> None:
        self.connected_count -= 1
        print(f"[notifee] disconnected from {conn.muxed_conn.peer_id}")

    async def opened_stream(self, network: INetwork, stream: INetStream) -> None:
        print(f"[notifee] stream opened with {stream.muxed_conn.peer_id}")

    async def closed_stream(self, network: INetwork, stream: INetStream) -> None:
        print(f"[notifee] stream closed with {stream.muxed_conn.peer_id}")

    async def listen(self, network: INetwork, multiaddr: Multiaddr) -> None:
        print(f"[notifee] listening on {multiaddr}")

    async def listen_close(self, network: INetwork, multiaddr: Multiaddr) -> None:
        print(f"[notifee] stopped listening on {multiaddr}")


# Register on the swarm
network = host.get_network()          # INetwork
network.register_notifee(ConnectionCounterNotifee())
```

### Best practices

1. **Keep callbacks fast.** The notify methods run on the event path. If you need
   to do real work (I/O, protocol negotiation), push the event onto a memory
   channel and process it in your own background task — exactly how
   `PubsubNotifee` works.
2. **Never raise.** An exception in a notifee callback propagates through the
   emitter's nursery and can break connection setup/teardown. Wrap risky work in
   `try/except` (see `_IdentifyNotifee`).
3. **Yield.** In no-op callbacks, `await trio.lowlevel.checkpoint()` keeps Trio
   scheduling honest.
4. **Deduplicate by design.** Events fire per *connection* and per *stream*.
   Multiple connections to the same peer mean multiple `connected` callbacks for
   that peer — decide how to dedupe (pubsub handles this by checking
   `peer_id in self.peers` in `_handle_new_peer`).

---

## 8. Known caveat: the one-shot peer-registration race (maintainer note)

This is a real, observed limitation worth knowing about (it was the root cause of
a messaging bug in a downstream project, PeerDrop):

1. `PubsubNotifee.connected` fires **once per new connection** and enqueues the
   peer ID.
2. `_handle_new_peer` tries `host.new_stream(peer_id, self.protocols)` **exactly
   once**; on `SwarmException` it logs `"fail to add new peer"` and returns —
   **there is no retry**.
3. If the connection is established (e.g. by mDNS auto-discovery) *before* the
   muxer handshake completes, the stream open can race and fail — the peer is
   never registered.
4. A later explicit `connect_peer()` call to the same peer finds the existing
   connection and returns early (`swarm.py:2000`, "Connection already exists"),
   so **no second `connected` notifee fires** and pubsub never gets another
   chance to register the peer.
5. If the racing connection then closes, `disconnected` → `_handle_dead_peer`
   removes the peer state entirely.

**Impact:** pubsub silently never learns about a reachable peer; published
messages to it are dropped forever.

**Possible upstream improvements:**
- Add retry/backoff in `_handle_new_peer` when `new_stream` fails (re-enqueue on
  `peer_receive_channel` after a short delay, bounded attempts).
- Only enqueue the peer in `PubsubNotifee.connected` once the connection is
  stream-ready (e.g. after `event_started` / muxer handshake).
- Add a public `ensure_peer_stream(peer_id)` (or `register_peer`) API so
  applications can (re)register a peer on demand instead of reaching into the
  private `_handle_new_peer_safe`.
- Consider an `unregister_notifee` API to match the append-only
  `register_notifee`.

---

## 9. Tests

The notifee system is covered by:

- `tests/core/pubsub/test_pubsub_notifee_integration.py` — verifies that
  connecting enqueues and adds the peer, disconnecting enqueues and removes it,
  `BrokenResourceError` is swallowed, duplicate connections don't duplicate peer
  state, and blacklisted peers are not added.
- `tests/core/network/test_notifee_performance.py` — performance characteristics
  of the fan-out dispatch.

---

## 10. Cheat sheet

| Concept | Location |
|---------|----------|
| `INotifee` abstract interface (6 callbacks) | `libp2p/abc.py:1890` |
| `register_notifee` (interface) | `libp2p/abc.py:1675` |
| `register_notifee` + `notify_*` fan-out (implementation) | `libp2p/network/swarm.py:2130–2192` |
| Notifee list initialization | `libp2p/network/swarm.py:217` |
| `connected` emission | `libp2p/network/swarm.py:2017` |
| `disconnected` emission | `libp2p/network/connection/swarm_connection.py:212, 289` |
| `opened_stream` emission | `libp2p/network/connection/swarm_connection.py:286` |
| `closed_stream` emission | `swarm_connection.py:276, 357` / `net_stream.py:364` |
| `listen` / `listen_close` emission | `swarm.py:1488` / `swarm.py:1832` |
| `PubsubNotifee` | `libp2p/pubsub/pubsub_notifee.py:21` |
| Pubsub notifee registration + channels | `libp2p/pubsub/pubsub.py:391–398` |
| `handle_peer_queue` / `handle_dead_peer_queue` | `libp2p/pubsub/pubsub.py:934, 946` |
| `_handle_new_peer_safe` / `_handle_dead_peer` | `libp2p/pubsub/pubsub.py:880, 898` |
| `_IdentifyNotifee` | `libp2p/host/basic_host.py:138` |
| Identify notifee registration | `libp2p/host/basic_host.py:325` |
| `TagStoreNotifee` | `libp2p/network/tag_store.py:493` |
| TagStore notifee registration | `libp2p/network/swarm.py:273` |
