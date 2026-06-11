# py-libp2p Multi-Transport Support

> Branch: `sumanjeet0012/py-libp2p@feat/multi_transport_support`

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Function-by-Function Flow](#2-function-by-function-flow)
   - [Step 1: `new_host()`](#step-1-new_host----libp2p__init__py)
   - [Step 2: `TransportUpgrader`](#step-2-transportupgrader__init__----libp2ptransportupgraderpy)
   - [Step 3: Transport Instantiation](#step-3-transport-instantiation)
   - [Step 4: Transport Registry](#step-4-transport-registration----libp2ptransport__init__py)
   - [Step 5: `Swarm.__init__()`](#step-5-swarm__init__----libp2pnetworkswarmpy)
   - [Step 6: `BasicHost.run()`](#step-6-basichostrun----libp2phostbasic_hostpy)
   - [Step 7: `Swarm.listen()`](#step-7-swarmlisten----the-core-of-multi-transport-listening)
   - [Step 8: `Swarm._handler()`](#step-8-swarm_handler----incoming-connection-handler)
   - [Step 9: `Swarm.dial()`](#step-9-swarmdial----outbound-connections-multi-transport-aware)
3. [Complete Call Graph](#3-complete-call-graph)
4. [Key Files Modified](#4-key-files-modified-in-your-branch)
5. [Backwards Compatibility Strategy](#5-backwards-compatibility-strategy)
   - [Modified `new_host()` Signature](#1-modify-new_host-signature)
   - [Internal Transport Assembly](#2-internal-transport-assembly-logic)
   - [Swarm Backwards Compat](#3-make-swarm-accept-both-single-and-multiple-transports)
   - [Auto-Generate Listen Addrs](#4-auto-generate-listen_addrs-from-enabled-transports)
   - [Smart Transport Matching](#5-smart-transport-matching-in-swarmlisten)
   - [Backwards Compatibility Checklist](#6-backwards-compatibility-checklist)
   - [Complete User-Facing Example](#7-complete-user-facing-example)
   - [Migration Path](#8-migration-path-for-existing-users)
   - [Additional Recommendations](#9-additional-recommendations)

---

## 1. High-Level Architecture

```
User Code
  │
  ▼
new_host(key_pair, ...)  ─────────────────────────  Entry Point (libp2p/__init__.py)
  │
  ├─► TransportUpgrader(security, muxers)            Security + Mux negotiation layer
  │
  ├─► Transport instantiation per protocol           TCP / WS / QUIC created here
  │     ├── TCP   → TCPTransport(upgrader)
  │     ├── WS    → WebsocketTransport(upgrader)
  │     └── QUIC  → QUICTransport(key_pair)
  │
  ├─► Swarm(peer_id, peerstore, upgrader, transports)  Network layer
  │
  └─► BasicHost(network=swarm)                       Host wrapper returned to user
```

---

## 2. Function-by-Function Flow

---

### Step 1: `new_host()` — `libp2p/__init__.py`

This is the **only entry point** users interact with.  
In the **current upstream** codebase it creates a single TCP transport.  
Your branch modifies this to build **multiple transports** simultaneously.

```python
def new_host(
    key_pair=None,
    ...
) -> BasicHost:
```

**What it does (current upstream):**

1. Generates or accepts a `KeyPair`
2. Derives `PeerID` from the public key
3. Creates a `PeerStore` and inserts the host's own keys
4. Builds a `TransportUpgrader` with configured security + muxer protocols
5. Creates a **single** `TCPTransport`
6. Constructs the `Swarm` (network layer) with that transport
7. Wraps the `Swarm` in a `BasicHost` and returns it

**What your branch changes:**

- Instead of creating a single TCP transport, it creates a **list of transports**
  (TCP + WebSocket + QUIC), consulting the `TransportRegistry`
- Passes all transports to a modified `Swarm` that can iterate over them during `listen()`

---

### Step 2: `TransportUpgrader.__init__()` — `libp2p/transport/upgrader.py`

```python
class TransportUpgrader:
    def __init__(
        self,
        secure_transports_by_protocol,
        muxer_transports_by_protocol,
        negotiate_timeout=5,
    ):
```

**What it does:**

- Stores mappings of protocol IDs → security transport instances (e.g., Noise, TLS)
- Stores mappings of protocol IDs → muxer classes (e.g., Yamux, Mplex)
- Used later by TCP & WS transports to **upgrade raw connections** into
  secure, multiplexed connections

> **Note:** QUIC does **not** use this upgrader because QUIC has built-in TLS 1.3
> and native stream multiplexing — it is entirely self-contained.

---

### Step 3: Transport Instantiation

#### 3a. `TCPTransport(upgrader)` — `libp2p/transport/tcp/tcp.py`

```python
class TCPTransport(ITransport):
    def __init__(self, upgrader):
        self._upgrader = upgrader
```

- Wraps raw TCP socket operations
- `create_listener(handler)` → returns a `TCPListener`
- `dial(maddr)` → opens a TCP connection and upgrades it through the upgrader
- Listens on a **TCP port** e.g. `/ip4/0.0.0.0/tcp/9000`

---

#### 3b. `WebsocketTransport(upgrader)` — `libp2p/transport/websocket/websocket.py`

```python
class WebsocketTransport(ITransport):
    def __init__(self, upgrader, tls_client_config=None, ...):
```

- Uses `trio-websocket` under the hood
- `create_listener(handler)` → returns a WS listener
- `dial(maddr)` → opens a WS connection and upgrades it through the upgrader
- Listens on a **TCP port** (same TCP port!) via HTTP Upgrade handshake  
  e.g. `/ip4/0.0.0.0/tcp/9000/ws`

---

#### 3c. `QUICTransport(key_pair)` — `libp2p/transport/quic/quic.py`

```python
class QUICTransport(ITransport):
    def __init__(self, key_pair):
```

- Uses `aioquic` or similar QUIC library
- Does **NOT** use the `TransportUpgrader` — QUIC has built-in TLS 1.3 and muxing
- `create_listener(handler)` → binds a **UDP socket**
- Listens on a **UDP port** e.g. `/ip4/0.0.0.0/udp/9000/quic-v1`

---

### Step 4: Transport Registration — `libp2p/transport/__init__.py`

The codebase has a `TransportRegistry` pattern:

```python
class TransportRegistry:
    def register(self, protocol: str, transport_class: type[ITransport]):
        """Map a multiaddr protocol string to a transport class."""

    def create_transport(self, protocol, upgrader=None, **kwargs):
        """Instantiate the right transport for the given protocol."""
```

And helper functions:

```python
register_transport(protocol, transport_class)    # e.g., register_transport("tcp", TCPTransport)
create_transport_for_multiaddr(maddr, upgrader)  # inspects maddr → picks correct transport
get_transport_registry()                         # global singleton
```

Your branch leverages this registry to loop over all registered transports and
instantiate them automatically when `new_host()` is called.

---

### Step 5: `Swarm.__init__()` — `libp2p/network/swarm.py`

```python
class Swarm(INetworkService):
    def __init__(self, peer_id, peerstore, upgrader, transport):
        self._peer_id    = peer_id
        self._peerstore  = peerstore
        self._upgrader   = upgrader
        self._transport  = transport       # upstream: single transport
        # your branch:
        # self._transports = [tcp, ws, quic, ...]
        self._listeners   = {}
        self._connections = {}
```

**What your branch changes:**

- `self._transport` (singular) → `self._transports: list[ITransport]`
- Stores multiple transport instances so `listen()` can iterate over all of them

---

### Step 6: `BasicHost.run()` — `libp2p/host/basic_host.py`

```python
class BasicHost:
    @asynccontextmanager
    async def run(self, listen_addrs):
        """Start the host and begin listening on the given multiaddrs."""
        await self._network.listen(*listen_addrs)
        # also starts identify, mDNS, bootstrap, etc.
        yield
        await self.close()
```

The user calls `async with host.run(listen_addrs=[...]):` which triggers `Swarm.listen()`.

---

### Step 7: `Swarm.listen()` — The Core of Multi-Transport Listening

This is **the key function** your branch modifies to enable simultaneous multi-transport
listening on the same port.

#### Upstream (single transport):

```python
async def listen(self, *multiaddrs):
    for maddr in multiaddrs:
        listener = self._transport.create_listener(self._handler)
        await listener.listen(maddr)
        self._listeners[maddr] = listener
```

#### Your branch (multi-transport):

```python
async def listen(self, *multiaddrs):
    for maddr in multiaddrs:
        # Find which transport can handle this multiaddr
        transport = self._match_transport(maddr)
        listener  = transport.create_listener(self._handler)
        await listener.listen(maddr)
        self._listeners[maddr] = listener
```

#### How same-port works across transports

| Transport | Example Multiaddr                      | Socket Type | Why Same Port Works                          |
|-----------|----------------------------------------|-------------|----------------------------------------------|
| TCP       | `/ip4/0.0.0.0/tcp/9000`               | TCP socket  | Raw TCP on port 9000                         |
| WebSocket | `/ip4/0.0.0.0/tcp/9000/ws`            | TCP socket  | HTTP Upgrade on same TCP port                |
| QUIC      | `/ip4/0.0.0.0/udp/9000/quic-v1`       | UDP socket  | Different L4 protocol — OS treats separately |

- **TCP and QUIC** can always share port `9000` because TCP uses a TCP socket
  while QUIC uses a UDP socket — the OS treats these as completely independent
- **WebSocket** sits on top of TCP. Two approaches:
  - **Approach A (Protocol Detection):** Single TCP socket sniffs the first bytes —
    if it sees an HTTP `Upgrade` header, route to the WS handler; otherwise treat
    as raw libp2p TCP (multistream-select). True same-socket sharing but more complex.
  - **Approach B (Separate Listeners):** WS listens on its own TCP port, or the
    multiaddr simply defines `/tcp/9000/ws` and `/tcp/9001` as distinct addresses.
    Your branch likely uses the multiaddr-differentiation approach.

---

### Step 8: `Swarm._handler()` — Incoming Connection Handler

When any listener accepts a new connection it calls this unified handler:

```python
async def _handler(self, raw_conn):
    """Called by any transport listener when a new connection arrives."""

    # 1. Upgrade security (Noise / TLS handshake)
    secured_conn = await self._upgrader.upgrade_security(raw_conn, is_initiator=False)

    # 2. Upgrade to multiplexed connection (Yamux / Mplex)
    muxed_conn = await self._upgrader.upgrade_muxer(secured_conn)

    # 3. Register connection in Swarm's connection map
    peer_id = secured_conn.get_remote_peer()
    self._connections[peer_id] = muxed_conn

    # 4. Start accepting streams on this muxed connection
    await self._accept_streams(muxed_conn)
```

> **For QUIC:** Steps 1 & 2 are skipped — QUIC already provides encryption and
> multiplexing natively. The QUIC transport returns connections that already
> implement the `IMuxedConn` interface directly.

---

### Step 9: `Swarm.dial()` — Outbound Connections (Multi-Transport Aware)

```python
async def dial(self, peer_id, multiaddrs):
    for maddr in multiaddrs:
        transport = self._match_transport(maddr)
        if transport:
            conn = await transport.dial(maddr)
            # ... upgrade and register
            return conn
    raise ConnectionFailure("No transport could dial any address")
```

`_match_transport()` inspects the multiaddr protocols to pick the right transport:

| Multiaddr Pattern          | Matched Transport       |
|---------------------------|-------------------------|
| `/tcp/...`                | `TCPTransport`          |
| `/tcp/.../ws`             | `WebsocketTransport`    |
| `/udp/.../quic-v1`        | `QUICTransport`         |

---

## 3. Complete Call Graph

```
User calls: new_host(key_pair=kp)
  │
  ├── KeyPair → PeerID derivation
  ├── PeerStore creation
  ├── TransportUpgrader(noise, yamux)
  ├── TCPTransport(upgrader)                   ─┐
  ├── WebsocketTransport(upgrader)              ├─ Multiple transports instantiated
  ├── QUICTransport(key_pair)                  ─┘
  ├── Swarm(peer_id, peerstore, upgrader, transports=[tcp, ws, quic])
  └── BasicHost(network=swarm)  ◄── returned to user


User calls: async with host.run(listen_addrs=[...]):
  │
  └── BasicHost.run(listen_addrs)
        │
        └── Swarm.listen(*listen_addrs)
              │
              ├── For "/ip4/0.0.0.0/tcp/9000"
              │     └── TCPTransport.create_listener(handler)
              │           └── TCPListener.listen(maddr)
              │                 └── trio.serve_tcp(port=9000)  ← TCP socket
              │
              ├── For "/ip4/0.0.0.0/tcp/9000/ws"
              │     └── WebsocketTransport.create_listener(handler)
              │           └── WSListener.listen(maddr)
              │                 └── serve_websocket(port=9000) ← TCP socket (HTTP Upgrade)
              │
              └── For "/ip4/0.0.0.0/udp/9000/quic-v1"
                    └── QUICTransport.create_listener(handler)
                          └── QUICListener.listen(maddr)
                                └── bind_udp_socket(port=9000) ← UDP socket


Incoming connection on ANY listener:
  │
  └── Swarm._handler(raw_conn)
        ├── upgrade_security(raw_conn)     [skipped for QUIC]
        ├── upgrade_muxer(secured_conn)    [skipped for QUIC]
        ├── register in self._connections
        └── _accept_streams loop begins
```

---

## 4. Key Files Modified in Your Branch

| File | Change Description |
|------|--------------------|
| `libp2p/__init__.py` | `new_host()` now creates multiple transports based on flags |
| `libp2p/network/swarm.py` | `Swarm` accepts `transports: list`; `listen()` iterates all |
| `libp2p/transport/__init__.py` | Uses `TransportRegistry` to auto-discover and instantiate transports |
| `libp2p/transport/tcp/tcp.py` | Unchanged — already implements `ITransport` |
| `libp2p/transport/websocket/` | Unchanged — already implements `ITransport` |
| `libp2p/transport/quic/` | New or modified QUIC transport implementation |
| `libp2p/host/basic_host.py` | `run()` passes multiple multiaddrs for different transports |

---

## 5. Backwards Compatibility Strategy

### Goal

Users should be able to write:

```python
# ── Old way (still works — TCP only, exactly as before) ──
host = new_host(key_pair=key_pair)

# ── New way (opt-in to extra transports via simple boolean flags) ──
host = new_host(
    key_pair=key_pair,
    enable_tcp=True,    # default: True  ← backwards compatible
    enable_ws=True,     # default: False ← opt-in
    enable_quic=True,   # default: False ← opt-in
)
```

Everything else — transport creation, listener setup, multiaddr generation —
happens **entirely under the hood**.

---

### 1. Modify `new_host()` Signature

```python
# libp2p/__init__.py

def new_host(
    key_pair: KeyPair = None,
    # ── Existing parameters (UNCHANGED) ──
    noise_key=None,
    muxer_opt=None,
    peerstore=None,
    disc_opt=None,
    # ── NEW: Transport enable flags ──
    enable_tcp: bool = True,       # ← default True = fully backwards compatible
    enable_ws: bool = False,
    enable_quic: bool = False,
    # ── NEW: Optional fine-grained config per transport ──
    transport_opts: dict = None,   # e.g. {"ws": {"tls_config": ctx}, "quic": {...}}
) -> BasicHost:
```

> **Key principle:** All new parameters default to values that reproduce the
> **exact same behaviour** as the current codebase.  
> `enable_tcp=True` + everything else `False` = identical to today.

---

### 2. Internal Transport Assembly Logic

Inside `new_host()`, add a transport assembly block **after** the upgrader is built:

```python
def new_host(...):
    # ... existing key_pair, peer_id, peerstore, upgrader setup (UNCHANGED) ...

    # ── NEW: Build transport list ──
    transports: list[ITransport] = []
    transport_opts = transport_opts or {}

    if enable_tcp:
        transports.append(
            TCPTransport(upgrader, **transport_opts.get("tcp", {}))
        )

    if enable_ws:
        transports.append(
            WebsocketTransport(upgrader, **transport_opts.get("ws", {}))
        )

    if enable_quic:
        transports.append(
            QUICTransport(key_pair, **transport_opts.get("quic", {}))
        )

    if not transports:
        raise ValueError("At least one transport must be enabled.")

    # ── Build Swarm with all transports ──
    swarm = Swarm(
        peer_id=peer_id,
        peerstore=peerstore,
        upgrader=upgrader,
        transports=transports,          # ← new: list instead of single
    )

    return BasicHost(network=swarm, ...)
```

---

### 3. Make `Swarm` Accept Both Single and Multiple Transports

For true backwards compatibility (in case anyone constructs `Swarm` directly):

```python
# libp2p/network/swarm.py

class Swarm(INetworkService):
    def __init__(
        self,
        peer_id,
        peerstore,
        upgrader,
        transport=None,       # ← OLD parameter (single transport) — kept for compat
        transports=None,      # ← NEW parameter (list of transports)
    ):
        # Normalise to a list internally
        if transports is not None:
            self._transports = list(transports)
        elif transport is not None:
            self._transports = [transport]      # wrap single transport in a list
        else:
            raise ValueError("Must provide either 'transport' or 'transports'.")

        self._peer_id     = peer_id
        self._peerstore   = peerstore
        self._upgrader    = upgrader
        self._listeners:  dict[Multiaddr, IListener] = {}
        self._connections = {}
```

---

### 4. Auto-Generate `listen_addrs` from Enabled Transports

Users shouldn't have to manually construct multiaddrs for each transport.
Add a small helper:

```python
# libp2p/utils/multiaddr_helpers.py

def generate_listen_addrs(
    port: int,
    host: str = "0.0.0.0",
    enable_tcp: bool = True,
    enable_ws: bool = False,
    enable_quic: bool = False,
) -> list[Multiaddr]:
    """Auto-generate multiaddrs for all enabled transports on the same port."""
    addrs = []
    if enable_tcp:
        addrs.append(Multiaddr(f"/ip4/{host}/tcp/{port}"))
    if enable_ws:
        addrs.append(Multiaddr(f"/ip4/{host}/tcp/{port}/ws"))
    if enable_quic:
        addrs.append(Multiaddr(f"/ip4/{host}/udp/{port}/quic-v1"))
    return addrs
```

Then in `BasicHost.run()`, auto-generate addrs when none are provided:

```python
# libp2p/host/basic_host.py

@asynccontextmanager
async def run(self, listen_addrs=None, port=0):
    if listen_addrs is None:
        # Auto-detect from which transports the Swarm was built with
        listen_addrs = self._generate_default_addrs(port)
    await self._network.listen(*listen_addrs)
    yield
    await self.close()
```

---

### 5. Smart Transport Matching in `Swarm.listen()`

Each transport must declare which multiaddr protocols it supports by implementing
a `can_handle()` method on the `ITransport` interface:

```python
# libp2p/transport/abc.py  (ITransport base class)

class ITransport(ABC):
    @abstractmethod
    def can_handle(self, maddr: Multiaddr) -> bool:
        """Return True if this transport can listen/dial the given multiaddr."""
        ...
```

Implement per transport:

```python
class TCPTransport(ITransport):
    def can_handle(self, maddr: Multiaddr) -> bool:
        protocols = [p.name for p in maddr.protocols()]
        return "tcp" in protocols and "ws" not in protocols and "wss" not in protocols

class WebsocketTransport(ITransport):
    def can_handle(self, maddr: Multiaddr) -> bool:
        protocols = [p.name for p in maddr.protocols()]
        return "ws" in protocols or "wss" in protocols

class QUICTransport(ITransport):
    def can_handle(self, maddr: Multiaddr) -> bool:
        protocols = [p.name for p in maddr.protocols()]
        return "quic" in protocols or "quic-v1" in protocols
```

`Swarm.listen()` uses `can_handle()` to dispatch:

```python
async def listen(self, *multiaddrs):
    for maddr in multiaddrs:
        for transport in self._transports:
            if transport.can_handle(maddr):
                listener = transport.create_listener(self._handle_connection)
                await listener.listen(maddr)
                self._listeners[maddr] = listener
                break
        else:
            raise TransportError(f"No registered transport can handle: {maddr}")
```

---

### 6. Backwards Compatibility Checklist

| Scenario | Expected Behaviour | Breaking? |
|----------|--------------------|:---------:|
| `new_host(key_pair=kp)` | TCP-only host — identical to today | ❌ No |
| `new_host(key_pair=kp, enable_ws=True)` | TCP + WS host | ❌ No |
| `new_host(key_pair=kp, enable_tcp=False, enable_quic=True)` | QUIC-only host | ❌ No |
| `Swarm(transport=tcp_transport)` | Single transport via old API | ❌ No |
| `Swarm(transports=[tcp, ws])` | Multi-transport via new API | ❌ No |
| `host.run(listen_addrs=[...])` | Explicit addrs — works as before | ❌ No |
| `host.run(port=9000)` | Auto-generates addrs for all enabled transports | ❌ No (new feature) |

---

### 7. Complete User-Facing Example

```python
import secrets
import trio
from libp2p import new_host
from libp2p.crypto.secp256k1 import create_new_key_pair

async def main():
    secret   = secrets.token_bytes(32)
    key_pair = create_new_key_pair(secret)

    # ── Old way: still works exactly as before ──────────────────────────────
    host = new_host(key_pair=key_pair)

    # ── New way: opt-in to additional transports ─────────────────────────────
    host = new_host(
        key_pair=key_pair,
        enable_tcp=True,
        enable_ws=True,
        enable_quic=True,
    )

    port = 9000

    async with host.run(port=port):
        print("Listening on:")
        for addr in host.get_addrs():
            print(f"  {addr}")
        # Output:
        #   /ip4/127.0.0.1/tcp/9000/p2p/QmXy...
        #   /ip4/127.0.0.1/tcp/9000/ws/p2p/QmXy...
        #   /ip4/127.0.0.1/udp/9000/quic-v1/p2p/QmXy...

        await trio.sleep_forever()

trio.run(main)
```

---

### 8. Migration Path for Existing Users

**Phase 1 — Your current PR:**  
Add `enable_tcp`, `enable_ws`, `enable_quic` with safe defaults.  
All existing code continues to work with **zero changes**.

**Phase 2 — Next minor version:**  
Add a `DeprecationWarning` when the old `transport=` kwarg is passed directly to `Swarm`:

```python
# libp2p/network/swarm.py

if transport is not None:
    import warnings
    warnings.warn(
        "Passing 'transport=' is deprecated. Use 'transports=[...]' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    self._transports = [transport]
```

**Phase 3 — Next major version:**  
Remove the `transport` (singular) parameter from `Swarm.__init__()` entirely.

---

### 9. Additional Recommendations

#### A. Use a `TransportConfig` dataclass instead of bare booleans

As more transports are added (WebTransport, WebRTC, etc.) bare booleans will not scale well.
Consider a typed config object:

```python
from dataclasses import dataclass, field

@dataclass
class TransportConfig:
    tcp:  bool | TCPConfig  = True
    ws:   bool | WSConfig   = False
    quic: bool | QUICConfig = False

# Usage:
host = new_host(
    key_pair=kp,
    transports=TransportConfig(tcp=True, ws=True, quic=False),
)
```

#### B. Document the port-sharing model

Make it explicit in docs and docstrings that:
- **TCP and WS** both bind a **TCP socket** on the same port number
- **QUIC** binds a **UDP socket** on the same port number
- The OS treats TCP:9000 and UDP:9000 as entirely separate — no conflicts

> This is the same model used by **go-libp2p** and **rust-libp2p**.

#### C. Add `host.get_transport_status()`

```python
def get_transport_status(self) -> dict[str, bool]:
    """Returns which transports are currently active and listening."""
    return {
        type(t).__name__: True
        for t in self._network._transports
    }
```

Useful for debugging and health-check endpoints.

#### D. Test Matrix

Ensure CI covers all combinations:

| TCP | WS  | QUIC | Test Case              |
|-----|-----|------|------------------------|
| ✅  | ❌  | ❌   | Regression (TCP only)  |
| ❌  | ✅  | ❌   | WS only                |
| ❌  | ❌  | ✅   | QUIC only              |
| ✅  | ✅  | ❌   | TCP + WS               |
| ✅  | ❌  | ✅   | TCP + QUIC             |
| ✅  | ✅  | ✅   | All three              |
| ✅  | ✅  | ✅   | Cross-transport dial   |
