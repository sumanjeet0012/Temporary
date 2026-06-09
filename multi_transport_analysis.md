# Multi-Transport Support in py-libp2p — Branch Analysis

**Branch:** `sumanjeet0012:py-libp2p:feat/multi_transport_support`  
**Base:** `libp2p/py-libp2p:main`  
**Author:** Sumanjeet Singh  
**Date of Analysis:** June 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [What Changed — File-by-File](#2-what-changed--file-by-file)
3. [New Files Introduced](#3-new-files-introduced)
4. [Modified Files](#4-modified-files)
5. [Architecture Diagram](#5-architecture-diagram)
6. [How It Works End-to-End](#6-how-it-works-end-to-end)
7. [Comparison with go-libp2p](#7-comparison-with-go-libp2p)
8. [Opinion — Is This the Right Approach?](#8-opinion--is-this-the-right-approach)
9. [Specific Issues and Gaps](#9-specific-issues-and-gaps)
10. [Recommendations](#10-recommendations)

---

## 1. Overview

Before this branch, py-libp2p's `Swarm` held a **single `ITransport` field**. A host could only be configured with one transport at a time — TCP **or** WebSocket **or** QUIC. There was no mechanism to listen on TCP and WebSocket simultaneously, and certainly no ability to share a port between them.

This branch restructures the transport layer around three goals:

- Allow the `Swarm` to hold **multiple registered transports** simultaneously (TCP + WebSocket + QUIC).
- Route dial/listen decisions via a new **`TransportManager`** using `can_dial()` / `can_listen()` per transport.
- Allow TCP and WebSocket to **share a single port** via a connection-level multiplexer (`SharedTCPDispatcher` in `cmux.py`) that peeks at the first bytes of each inbound connection to distinguish HTTP (WebSocket upgrade) from raw TCP.

---

## 2. What Changed — File-by-File

### New Files

| File | Purpose |
|------|---------|
| `libp2p/transport/manager.py` | `TransportManager` — ordered list of transports with `for_dialing()` / `for_listening()` routing |
| `libp2p/transport/cmux.py` | `SharedTCPDispatcher` — single TCP socket that multiplexes TCP and WebSocket by peeking at the first bytes |
| `libp2p/io/peekable_stream.py` | `PeekableStream` — trio stream wrapper that allows buffered peek-and-rewind, needed by `cmux.py` |

### Modified Files

| File | Change Summary |
|------|---------------|
| `libp2p/network/swarm.py` | Replaces `transport: ITransport` with `transport_manager: TransportManager`; new `transports=[]` constructor arg; all dial/listen routed through manager |
| `libp2p/transport/__init__.py` | Adds `TransportManager`, `create_transport()` factory, exports for new types |
| `libp2p/abc.py` | Adds `can_dial()`, `can_listen()`, `protocols()` as **abstract methods** on `ITransport` |
| `libp2p/transport/tcp/tcp.py` | Adds `can_dial()`, `can_listen()`, `protocols()` implementations; TCPListener now manages its own internal nursery |
| `libp2p/transport/websocket/transport.py` | Adds `can_dial()`, `can_listen()`, `protocols()` implementations |
| `libp2p/transport/quic/transport.py` | Adds `can_dial()`, `can_listen()`, `protocols()` implementations |
| `libp2p/transport/transport_registry.py` | Already existed in main; no structural change in this branch |

---

## 3. New Files Introduced

### 3.1 `libp2p/transport/manager.py` — `TransportManager`

This is the core of the feature. It maintains an ordered `list[ITransport]` and provides two routing methods.

```python
class TransportManager:
    def __init__(self) -> None:
        self._transports: list[ITransport] = []
        self._shared_tcp_listeners: dict[tuple[str, int], IListener] = {}

    def for_dialing(self, maddr: Multiaddr) -> ITransport | None: ...
    def for_listening(self, maddr: Multiaddr) -> ITransport | None: ...
    def listen_on(self, maddr: Multiaddr, conn_handler: THandler) -> IListener | None: ...
```

**Routing logic** (`for_dialing` / `for_listening`):

1. Build the set of protocol names from `maddr.protocols()`.
2. For each registered transport, do a fast pre-filter: `proto_names ∩ transport.protocols()`. If empty, skip.
3. Call `transport.can_dial(maddr)` (or `can_listen`) on survivors.
4. Return the first match.

**Port-sharing logic** (`listen_on`):

When a TCP-based address (either pure `/tcp` or `/tcp/ws`) is requested, `listen_on` creates or reuses a `SharedTCPDispatcher` keyed by `(host, port)`. The dispatcher is shared across TCP and WebSocket listeners on the same port.

### 3.2 `libp2p/transport/cmux.py` — `SharedTCPDispatcher`

```python
class SharedTCPDispatcher(IListener):
    tcp_handler: THandler | None
    ws_handler: Callable[[WebSocketRequest], Awaitable[None]] | None

    async def _handle_stream(self, stream: trio.SocketStream) -> None:
        peekable = PeekableStream(stream)
        data = await peekable.receive_some(8)   # peek 8 bytes
        peekable.buffer = bytearray(data) + peekable.buffer  # rewind

        is_http = data.startswith(b"GET ") or data.startswith(b"POST ") or ...

        if is_http and self.ws_handler:
            ws_request = await wrap_server_stream(self._nursery, peekable)
            await self.ws_handler(ws_request)
        elif not is_http and self.tcp_handler:
            tcp_stream = TrioTCPStream(peekable)
            await self.tcp_handler(tcp_stream)
        else:
            await stream.aclose()
```

The dispatcher opens one `trio.serve_tcp` socket and routes based on the first 8 bytes:
- `GET ` / `POST ` / `PUT ` → WebSocket upgrade path.
- Everything else → raw libp2p TCP path.

### 3.3 `libp2p/io/peekable_stream.py` — `PeekableStream`

A `trio.abc.Stream` wrapper with a `bytearray` buffer. When `receive_some()` is called, buffered bytes are returned first; once the buffer is empty it delegates to the underlying stream. This allows `cmux.py` to peek-and-rewind without consuming bytes that the actual handler needs.

---

## 4. Modified Files

### 4.1 `libp2p/abc.py` — Updated `ITransport` Interface

Three new abstract methods are added:

```python
class ITransport(ABC):
    @abstractmethod
    async def dial(self, maddr: Multiaddr) -> IRawConnection: ...

    @abstractmethod
    def create_listener(self, handler_function: THandler) -> IListener: ...

    @abstractmethod
    def can_dial(self, maddr: Multiaddr) -> bool: ...   # NEW

    @abstractmethod
    def can_listen(self, maddr: Multiaddr) -> bool: ...  # NEW

    @abstractmethod
    def protocols(self) -> list[str]: ...                # NEW
```

Each transport now self-declares which multiaddr protocol names it handles (`protocols()`) and whether it can specifically dial/listen on a given address.

### 4.2 `libp2p/network/swarm.py` — Multi-Transport Swarm

The biggest functional change. The old `transport: ITransport` field is replaced with `transport_manager: TransportManager`.

**Constructor change:**

```python
# Old (main branch)
def __init__(self, peer_id, peerstore, upgrader, transport: ITransport, ...):
    self.transport = transport

# New (this branch)
def __init__(self, peer_id, peerstore, upgrader,
             transports: list[ITransport] | ITransport | None = None, ...):
    self.transport_manager = TransportManager()
    if isinstance(transports, list):
        self.transport_manager.add_transports(transports)
    elif transports is not None:
        warnings.warn("Deprecated: use transports=[...]", DeprecationWarning)
        self.transport_manager.add_transport(transports)
```

Backward compatibility is maintained through a deprecation warning for old single-transport call sites.

**Listen change:**

```python
# Old: single transport listener
listener = self.transport.create_listener(conn_handler)

# New: routed through manager (handles CMUX)
listener = self.transport_manager.listen_on(maddr, conn_handler)
```

**Dial change:**

```python
# Old
raw_conn = await self.transport.dial(addr)

# New
transport = self.transport_manager.for_dialing(addr)
raw_conn = await transport.dial(addr)
```

### 4.3 Per-Transport: `can_dial()`, `can_listen()`, `protocols()`

Each transport now correctly self-declares its scope:

**TCP:**
```python
def can_dial(self, maddr: Multiaddr) -> bool:
    names = {p.name for p in maddr.protocols()}
    # TCP handles /tcp but NOT /ws, /wss, /quic, /quic-v1
    return "tcp" in names and not names.intersection({"ws", "wss", "quic", "quic-v1"})

def protocols(self) -> list[str]:
    return ["tcp"]
```

**WebSocket:**
```python
def can_dial(self, maddr: Multiaddr) -> bool:
    try:
        parse_websocket_multiaddr(maddr)
        return True
    except (ValueError, KeyError):
        return False

def protocols(self) -> list[str]:
    return ["ws", "wss"]
```

**QUIC:**
```python
def can_dial(self, maddr: Multiaddr) -> bool:
    return is_quic_multiaddr(maddr)

def protocols(self) -> list[str]:
    protos = ["quic-v1"]
    if self._config.enable_draft29:
        protos.append("quic")
    return protos
```

The TCP exclusion of `ws/wss` is important: since WebSocket runs over TCP, a naïve `"tcp" in names` check would match both `/tcp/4001` and `/tcp/8080/ws`. The explicit exclusion set ensures the manager routes them to the correct transport.

---

## 5. Architecture Diagram

```
Before (main branch):
┌──────────────┐
│   BasicHost  │
└──────┬───────┘
       │
┌──────▼───────┐          ONE transport only
│    Swarm     │─────────►  TCP  │  WebSocket  │  QUIC
│ transport:   │          (pick one at init time)
│ ITransport   │
└──────────────┘


After (this branch):
┌──────────────┐
│   BasicHost  │
└──────┬───────┘
       │
┌──────▼───────────────────────────────────────────────────┐
│                          Swarm                           │
│  transport_manager: TransportManager                     │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  _transports: [TCP(), WebsocketTransport(), QUIC()]  │ │
│  │                                                      │ │
│  │  for_dialing(maddr)  → routes by protocols()+can_dial │ │
│  │  for_listening(maddr) → routes by can_listen()       │ │
│  │  listen_on(maddr) → creates SharedTCPDispatcher      │ │
│  │                      for same-port TCP+WS            │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘

                     ┌──────────────────────┐
Port 4001 (TCP):     │  SharedTCPDispatcher │  ← cmux.py
                     │  ┌────────────┐       │
                     │  │ PeekStream │ peek  │
                     │  └─────┬──────┘       │
                     │        │              │
                     │   starts with         │
                     │  "GET "/"POST "?       │
                     │    yes     no          │
                     │     │       │          │
                     │  ws_handler tcp_handler│
                     └──────────────────────┘
```

---

## 6. How It Works End-to-End

### Registering Transports

```python
from libp2p.transport.tcp.tcp import TCP
from libp2p.transport.websocket.transport import WebsocketTransport
from libp2p.transport.quic.transport import QUICTransport

swarm = Swarm(
    peer_id=peer_id,
    peerstore=peerstore,
    upgrader=upgrader,
    transports=[
        TCP(),
        WebsocketTransport(upgrader),
        QUICTransport(private_key),
    ]
)
```

### Listening on Multiple Addresses

```python
await swarm.listen(
    Multiaddr("/ip4/0.0.0.0/tcp/4001"),           # → TCP transport
    Multiaddr("/ip4/0.0.0.0/tcp/4001/ws"),         # → SharedTCPDispatcher on port 4001
    Multiaddr("/ip4/0.0.0.0/udp/4001/quic-v1"),    # → QUIC transport
)
```

For port 4001, both TCP and WebSocket calls go through `listen_on`, which:
1. Detects `"tcp"` in protocols and looks up `(host, port)` in `_shared_tcp_listeners`.
2. Creates one `SharedTCPDispatcher` for the first call; reuses it for the second.
3. Assigns `dispatcher.tcp_handler` for the TCP address and `dispatcher.ws_handler` for the WebSocket address.

### Inbound Connection Routing

A new connection on port 4001 hits `SharedTCPDispatcher._handle_stream`:
1. `PeekableStream` reads 8 bytes without consuming them.
2. If bytes start with `GET ` → WebSocket upgrade via `trio_websocket.wrap_server_stream`.
3. Otherwise → raw TCP libp2p handshake via `TrioTCPStream`.

### Outbound Dial Routing

```python
# Swarm._dial_single_address
transport = self.transport_manager.for_dialing(addr)
raw_conn = await transport.dial(addr)
```

The manager's two-step filter (fast `protocols()` set intersection, then `can_dial()`) ensures the correct transport is selected for any multiaddr.

---

## 7. Comparison with go-libp2p

### 7.1 Transport Map vs Transport List

**go-libp2p:**
```go
// swarm.go
transports struct {
    sync.RWMutex
    m map[int]transport.Transport  // keyed by multiaddr protocol CODE (int)
}

// AddTransport registers one entry per protocol code
func (s *Swarm) AddTransport(t transport.Transport) error {
    for _, p := range t.Protocols() {
        s.transports.m[p] = t  // each protocol code maps to exactly one transport
    }
    return nil
}
```

go-libp2p uses a **protocol-code-keyed map**. Registration enforces that no two transports claim the same protocol code. `TransportForListening` selects by the last protocol code in the multiaddr, with proxy transports taking precedence.

**py-libp2p (this branch):**
```python
# manager.py
self._transports: list[ITransport] = []

def for_dialing(self, maddr: Multiaddr) -> ITransport | None:
    for transport in self._transports:
        if proto_names.intersection(set(transport.protocols())):
            if transport.can_dial(maddr):
                return transport  # first match wins
```

py-libp2p uses an **ordered list with first-match semantics**. This is simpler but means registration order matters and doesn't enforce uniqueness.

### 7.2 `TransportForListening` Logic

**go-libp2p:**
```go
func (s *Swarm) TransportForListening(a ma.Multiaddr) transport.Transport {
    selected := s.transports.m[protocols[len(protocols)-1].Code]  // last protocol wins
    for _, p := range protocols {
        transport, ok := s.transports.m[p.Code]
        if transport.Proxy() {
            selected = transport  // proxy transports have priority
        }
    }
    return selected
}
```

go-libp2p uses the **last protocol code** as the default selection, overridden by proxy transports. No `CanListen()` call is made — the protocol code lookup is the mechanism.

**py-libp2p (this branch):**
```python
def for_listening(self, maddr: Multiaddr) -> ITransport | None:
    for transport in self._transports:
        if proto_names.intersection(set(transport.protocols())):
            if transport.can_listen(maddr):
                return transport
```

Uses `can_listen()` + ordered iteration, which is more explicit. go-libp2p also has `CanDial()` on the transport interface, but listen routing is purely protocol-code-based. py-libp2p's approach is arguably cleaner for a Python implementation where explicit is better than implicit.

### 7.3 `OrderedListener` Interface

go-libp2p has an important interface this branch is missing:
```go
type OrderedListener interface {
    ListenOrder() int
}
```

go-libp2p's `Listen()` sorts all requested addresses by `ListenOrder()` before starting listeners. This is used so that, for example, QUIC is always started before WebRTC (WebRTC can reuse the QUIC UDP socket). This branch has no equivalent concept.

### 7.4 Port Sharing — The Critical Difference

**go-libp2p** does **not** do byte-peek cmux for TCP/WebSocket sharing. In go-libp2p, TCP and WebSocket are treated as **separate protocols with separate ports**. WebSocket runs over TCP, but go-libp2p registers them independently at different multiaddrs. Port sharing in go-libp2p only exists for QUIC/WebRTC via the `OrderedListener` pattern (reuse of UDP sockets).

**This branch** implements an HTTP-sniffing `SharedTCPDispatcher` that allows `/tcp/4001` and `/tcp/4001/ws` to literally share one socket. This is **not** the go-libp2p approach.

However, it is not unprecedented in the ecosystem. This is essentially what `go-cmux` (https://github.com/soheilhy/cmux) does in Go — application-layer multiplexing over a single TCP port. Some libp2p node operators do run this externally, but go-libp2p itself does not build it into the swarm.

### 7.5 Feature Comparison Table

| Feature | go-libp2p | py-libp2p (this branch) |
|---------|-----------|------------------------|
| Transport storage | `map[proto_code]Transport` | `list[ITransport]` (ordered) |
| Routing mechanism | Map lookup by protocol code | `can_dial()` / `can_listen()` + ordered iteration |
| Duplicate transport enforcement | ✅ Error on conflict | ❌ Silent override (first match wins) |
| `OrderedListener` (setup order) | ✅ Present | ❌ Missing |
| Port sharing TCP+WS | ❌ Separate ports | ✅ SharedTCPDispatcher (byte-peek) |
| `CanDial()` on transport | ✅ (also used by dial routing) | ✅ |
| Protocol self-declaration | ✅ `Protocols() []int` | ✅ `protocols() list[str]` |
| Proxy transport priority | ✅ `Proxy() bool` | ❌ Not implemented |
| `ListenClose` by multiaddr | ✅ | ❌ Not implemented in manager |
| Backward compat (single transport) | N/A | ✅ `DeprecationWarning` |

---

## 8. Opinion — Is This the Right Approach?

### 8.1 What's Done Well

**The `TransportManager` design is correct and closely mirrors go-libp2p.** Decoupling transport routing from the `Swarm` into a dedicated manager object is exactly the right separation of concerns. The `for_dialing()` / `for_listening()` API directly mirrors go-libp2p's `TransportForDialing()` / `TransportForListening()`.

**The `ITransport` interface extension is correct.** Adding `can_dial()`, `can_listen()`, and `protocols()` as abstract methods on `ITransport` is the right way to make transports self-describing. go-libp2p has the same contract.

**Backward compatibility handling is thoughtful.** The `DeprecationWarning` for single-transport call sites means existing tests and examples don't break immediately.

**`PeekableStream` is a clean primitive.** It correctly implements `trio.abc.Stream` and the buffer-rewind semantics are sound.

**The TCP exclusion logic in `TCP.can_dial()` is important and correct.** Without explicitly excluding `/ws` and `/wss`, TCP would incorrectly match WebSocket addresses (since WebSocket uses TCP underneath).

### 8.2 What Deviates from go-libp2p

**The `SharedTCPDispatcher` (cmux) is not how go-libp2p works** and should be treated carefully. go-libp2p intentionally keeps TCP and WebSocket on separate ports and separate sockets. The reason is that byte-sniffing creates a dependency between the two transports at the socket level — if the shared TCP server has a bug, it takes down both.

There are also correctness concerns with the cmux approach as currently implemented (detailed below).

**The transport storage as a `list` instead of a `map[code]Transport`** means there's no protection against registering two transports for the same protocol, which could silently produce non-deterministic behavior depending on registration order.

### 8.3 Overall Verdict

The core of this branch — `TransportManager`, the `ITransport` interface additions, and the `Swarm` refactoring — is **correct, well-designed, and should be merged in some form**. It unblocks the ability to have TCP + WebSocket + QUIC all active simultaneously, which is critical for py-libp2p to be a first-class libp2p implementation.

The `SharedTCPDispatcher` is **novel but risky**. It achieves the "single port" goal but diverges from go-libp2p semantics and has implementation correctness issues that need resolution before it can be merged.

---

## 9. Specific Issues and Gaps

### Issue 1: `SharedTCPDispatcher` — Incorrect Handler Assignment

In `TransportManager.listen_on`, when registering the WebSocket handler, an inner closure `ws_cmux_handler` is defined inline:

```python
async def ws_cmux_handler(ws_request: Any) -> None:
    ws = await ws_request.accept()
    from .websocket.connection import P2PWebSocketConnection
    is_secure = "wss" in protocols
    conn = P2PWebSocketConnection(
        ws,
        is_secure=is_secure,
        max_buffered_amount=32 * 1024 * 1024,
    )
    await conn_handler(conn)   # ← This calls swarm's _handle_inbound_connection
```

This bypasses `WebsocketListener` entirely — no connection tracking, no `_handshake_timeout`, no `_current_connections` limit, no `_total_connections` stats, no per-connection nursery teardown. Connections made via the cmux path are second-class compared to those through `WebsocketListener.listen()`.

### Issue 2: `SharedTCPDispatcher` — Nursery Race Condition

```python
async def _handle_stream(self, stream: trio.SocketStream) -> None:
    ...
    if is_http and self.ws_handler is not None:
        if self._nursery is None:   # ← race: nursery could be set to None after check
            return
        ws_request = await wrap_server_stream(self._nursery, peekable)
```

`self._nursery` can be set to `None` in `_run_server`'s `finally` block while `_handle_stream` is executing. The check-then-use of `self._nursery` is not atomic under trio's cooperative multitasking if an `await` occurs between the check and the use. `wrap_server_stream` itself can yield, at which point the nursery could cancel. This should use a trio `CancelScope` guard instead.

### Issue 3: `listen_on` Creates `SharedTCPDispatcher` Before Handler Assignment

```python
if key not in self._shared_tcp_listeners:
    dispatcher = SharedTCPDispatcher(host, port)
    self._shared_tcp_listeners[key] = dispatcher
...
if is_ws:
    dispatcher.ws_handler = ws_cmux_handler
else:
    dispatcher.tcp_handler = conn_handler
```

The dispatcher is stored in `_shared_tcp_listeners` before `dispatcher.tcp_handler` or `dispatcher.ws_handler` is set. If `listen()` is called on the dispatcher between storage and handler assignment (unlikely in practice since `listen()` is called by `Swarm.listen` afterward, but still a correctness hazard), a connection could arrive with `None` handlers and be silently dropped.

### Issue 4: `ITransport.can_listen` Is Not Truly Abstract

Looking at `libp2p/abc.py`, `can_listen` is decorated with `@abstractmethod` but the decorator is placed on the method without a body (`pass`-only). In Python, `@abstractmethod` with no body still technically requires subclass implementation, but the absence of docstring enforcement or a clear contract for "can_listen differs from can_dial" means future transport authors might not implement it distinctly. For relay transports (can dial but not listen), this distinction matters.

### Issue 5: No `OrderedListener` Equivalent

As noted, go-libp2p's `Listen()` sorts by `ListenOrder()` before starting listeners. This allows QUIC to be started before WebRTC so that WebRTC can reuse the QUIC UDP port. py-libp2p has no equivalent. While not immediately critical (py-libp2p doesn't have WebRTC yet), as the transport ecosystem grows this will become important.

### Issue 6: No Conflict Detection on `add_transport`

```python
def add_transport(self, transport: ITransport) -> None:
    self._transports.append(transport)
```

go-libp2p's `AddTransport` returns an error if a protocol is already registered. py-libp2p silently appends and relies on first-match semantics. If you accidentally register two TCP transports, the second is silently dead. This should at minimum log a warning.

### Issue 7: `TransportRegistry` vs `TransportManager` — Redundancy

Both `transport_registry.py` (existing in `main`) and `manager.py` (new in this branch) are present. The registry has its own `create_transport()` logic and also maintains a global singleton. The manager's `listen_on` does **not** use the registry at all — it uses `isinstance` checks and inline construction. The two abstractions overlap and the relationship between them is not defined. The registry should either be deleted or clearly scoped as "factory for constructing transport instances at startup" with the manager being "runtime routing".

### Issue 8: HTTP Sniffing Covers Only 3 Methods

```python
is_http = (
    data.startswith(b"GET ")
    or data.startswith(b"POST ")
    or data.startswith(b"PUT ")
)
```

A WebSocket upgrade is always a `GET` request (RFC 6455, section 4.1: "The client's opening handshake consists of... A Request-URI... An HTTP/1.1 upgrade request... The request MUST use the GET method"). So `POST` and `PUT` checks are unnecessary noise. More importantly, `DELETE`, `HEAD`, `OPTIONS`, `PATCH`, `CONNECT`, `TRACE` are all missing — a misbehaving or future HTTP client could bypass routing. Since only `GET` is needed for WebSocket, the check should be tightened to `data.startswith(b"GET ")`.

### Issue 9: No Tests

There are no test files for `cmux.py`, `manager.py`, or the multi-transport `Swarm` configuration in this branch. Given the complexity of the nursery lifecycle, the peek-and-rewind logic, and the port-sharing semantics, this is a significant gap.

---

## 10. Recommendations

### Immediate (must-fix before merge)

1. **Fix `SharedTCPDispatcher` to route through `WebsocketListener`**, not a bare inline handler. Either have `listen_on` create a real `WebsocketListener` and somehow thread it through the dispatcher, or restructure so `WebsocketTransport.create_listener()` returns a listener that already integrates with the dispatcher.

2. **Tighten the HTTP sniff to `b"GET "` only.** WebSocket upgrades are always GET requests. The current POST/PUT checks are unnecessary and the missing HTTP methods are a correctness gap.

3. **Add conflict detection to `add_transport`.** At minimum, check `transport.protocols()` against already-registered transports and warn. Ideally raise, matching go-libp2p behavior.

4. **Add tests.** At minimum: unit tests for `TransportManager.for_dialing` / `for_listening`, unit tests for `SharedTCPDispatcher` routing, and an integration test that starts a host listening on `/tcp/N` and `/tcp/N/ws` simultaneously and verifies both connection types work.

### Medium-term (follow-up PRs)

5. **Clarify `TransportRegistry` vs `TransportManager` roles.** Scope the registry as a construction-time factory and remove its overlap with the manager's routing. Remove the global singleton pattern.

6. **Implement `OrderedListener`** — even a simple `listen_order: int = 0` field on `ITransport` — to handle future transport setup ordering requirements.

7. **Implement `ListenClose` on `TransportManager`** — the manager currently has no way to stop a specific listener by multiaddr, which is needed for the full `INetworkService` contract.

### Design Question for Discussion

The `SharedTCPDispatcher` gives py-libp2p something go-libp2p deliberately does not have: same-port TCP/WebSocket multiplexing. This is useful for deployments behind load balancers that only expose a single port. However it adds complexity and a divergence from the reference implementation.

An alternative that stays closer to go-libp2p is to require TCP and WebSocket to use different ports (just as in go-libp2p), but expose a simple helper in the `host` layer that auto-assigns adjacent ports (e.g., `4001` for TCP, `4002` for WebSocket). This keeps the transport layer clean and matches go-libp2p semantics.

If same-port multiplexing is a hard requirement for py-libp2p (e.g., for browser/server compatibility), the cmux approach is reasonable but should be made opt-in rather than the default codepath in `listen_on`, and it should integrate properly with `WebsocketListener` rather than bypassing it.

---

## Summary

| Component | Status | Notes |
|-----------|--------|-------|
| `ITransport` interface additions | ✅ Correct | Matches go-libp2p contract |
| `TransportManager` routing | ✅ Correct | Minor: add conflict detection |
| `Swarm` refactoring | ✅ Correct | Backward compat preserved |
| `TCP.can_dial` exclusion logic | ✅ Correct | Critical for correct routing |
| `SharedTCPDispatcher` concept | ⚠️ Novel | Diverges from go-libp2p; useful but risky |
| `SharedTCPDispatcher` implementation | ❌ Bugs | Bypasses WebsocketListener, nursery race |
| `PeekableStream` | ✅ Clean | Sound implementation |
| `OrderedListener` | ❌ Missing | Needed for future transport ordering |
| Test coverage | ❌ None | Must be added before merge |
| `TransportRegistry` overlap | ⚠️ Unclear | Role vs `TransportManager` undefined |

The branch represents a substantial, well-directed effort. The core architecture is sound. The main items to resolve before merge are the `SharedTCPDispatcher` correctness issues and test coverage.
