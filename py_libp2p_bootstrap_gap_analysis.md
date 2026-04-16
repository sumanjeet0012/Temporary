# py-libp2p Bootstrap Module — Gap Analysis vs go-libp2p

> **Repository audited:** `libp2p/py-libp2p` (cloned April 2026)  
> **Files analysed:** `libp2p/discovery/bootstrap/bootstrap.py`, `utils.py`, `__init__.py`,  
> `libp2p/filecoin/bootstrap.py`, `libp2p/discovery/events/peerDiscovery.py`,  
> `tests/core/discovery/bootstrap/`  
> **Compared against:** `go-libp2p` (p2p/net/swarm, p2p/discovery/backoff, keep-network fork),  
> `go-libp2p-kad-dht` bootstrap API, `js-libp2p` `@libp2p/bootstrap`

---

## Table of Contents

1. [Summary Scorecard](#1-summary-scorecard)  
2. [What py-libp2p Bootstrap Already Does Well](#2-what-py-libp2p-bootstrap-already-does-well)  
3. [Gap Analysis: Feature-by-Feature](#3-gap-analysis-feature-by-feature)  
   - 3.1 [Periodic Re-bootstrapping (Critical)](#31-periodic-re-bootstrapping-critical)  
   - 3.2 [Minimum Peer Threshold / Connection Watchdog (Critical)](#32-minimum-peer-threshold--connection-watchdog-critical)  
   - 3.3 [Exponential Backoff for Failed Connections (High)](#33-exponential-backoff-for-failed-connections-high)  
   - 3.4 [EventBus / Typed Async Events (High)](#34-eventbus--typed-async-events-high)  
   - 3.5 [Connection Manager + Peer Tagging (High)](#35-connection-manager--peer-tagging-high)  
   - 3.6 [DHT / Routing Table Refresh After Bootstrap (High)](#36-dht--routing-table-refresh-after-bootstrap-high)  
   - 3.7 [Standard Discovery Interface (Medium)](#37-standard-discovery-interface-medium)  
   - 3.8 [Default Bootstrap Peer List in Library (Medium)](#38-default-bootstrap-peer-list-in-library-medium)  
   - 3.9 [Peer Address TTL Strategy (Medium)](#39-peer-address-ttl-strategy-medium)  
   - 3.10 [Network Change Detection / Interface Polling (Medium)](#310-network-change-detection--interface-polling-medium)  
   - 3.11 [IP Diversity Filtering (Low)](#311-ip-diversity-filtering-low)  
   - 3.12 [QUIC / WebTransport Address Support (Low)](#312-quic--webtransport-address-support-low)  
   - 3.13 [Circuit Relay / AutoRelay Integration (Low)](#313-circuit-relay--autorelay-integration-low)  
   - 3.14 [Structured Lifecycle (Process/Closer Pattern) (Low)](#314-structured-lifecycle-processcloser-pattern-low)  
4. [Code-Level Issues Found](#4-code-level-issues-found)  
5. [Proposed Improvements with Implementation Sketches](#5-proposed-improvements-with-implementation-sketches)  
6. [Recommended Contribution Roadmap](#6-recommended-contribution-roadmap)

---

## 1. Summary Scorecard

| Feature | go-libp2p | py-libp2p | Gap |
|---|---|---|---|
| One-shot parallel connect at startup | ✅ | ✅ | — |
| DNS resolution with retry | ✅ | ✅ | — |
| Address validation | ✅ | ✅ | — |
| Dedup / self-peer filtering | ✅ | ✅ | — |
| Connection timeout | ✅ | ✅ | — |
| IPv6 support | ✅ | ⚠️ opt-in | Incomplete |
| **Periodic re-bootstrapping** | ✅ | ❌ | **Critical** |
| **Min-peer threshold watchdog** | ✅ | ❌ | **Critical** |
| **Exponential backoff on retry** | ✅ | ❌ | **High** |
| **Typed async EventBus** | ✅ | ❌ | **High** |
| **Connection manager peer tagging** | ✅ | ❌ | **High** |
| **DHT routing table refresh** | ✅ | ❌ | **High** |
| Standard `Discovery` interface | ✅ | ❌ | Medium |
| Default bootstrap peers (library-level) | ✅ | ❌ | Medium |
| Bootstrap peer address TTL strategy | ✅ | ⚠️ | Medium |
| Network change detection | ✅ | ❌ | Medium |
| IP diversity filtering | ✅ | ❌ | Low |
| QUIC address handling | ✅ | ❌ | Low |
| AutoRelay integration | ✅ | ❌ | Low |
| Process lifecycle (Closer/cancel scope) | ✅ | ⚠️ | Low |

---

## 2. What py-libp2p Bootstrap Already Does Well

Before diving into gaps, it is worth acknowledging the solid foundation already in place:

- **Parallel address processing** — Trio nursery is used correctly to run all bootstrap address tasks concurrently, matching go-libp2p's goroutine fan-out pattern.
- **DNS protocol detection** — `is_dns_addr()` correctly recognises `dns`, `dns4`, `dns6`, and `dnsaddr`, and delegates to a retry-aware resolver.
- **Graceful failure isolation** — individual address task failures are caught per-task and logged, preventing a single bad address from killing the nursery. This mirrors the resilience design of go's bootstrap.
- **Self-peer filtering** — avoids connecting to ourself, which is a correctness invariant that go-libp2p also enforces.
- **Test coverage** — DNS resolution failure, empty results, and address validation all have passing tests.

---

## 3. Gap Analysis: Feature-by-Feature

### 3.1 Periodic Re-bootstrapping (**Critical**)

**go-libp2p behaviour:**  
`BootstrapConfig` has a `Period` field (default `30s` in keep-network fork). A long-running goroutine wakes every `Period` and re-runs the bootstrap logic regardless of current connection count. This ensures the node re-integrates after a network partition or OS sleep/resume.

```go
// go-libp2p (keep-network fork)
var DefaultBootstrapConfig = BootstrapConfig{
    Period:            30 * time.Second,
    ConnectionTimeout: 10 * time.Second,
}
```

**py-libp2p current behaviour:**  
`start()` runs once and returns. There is no background task that periodically re-dials bootstrap peers. A node that loses all connections (e.g. laptop sleep, network blip) will stay disconnected forever.

**Impact:** A node bootstrapped once will silently partition itself from the network on any connection disruption with no self-healing.

---

### 3.2 Minimum Peer Threshold / Connection Watchdog (**Critical**)

**go-libp2p behaviour:**  
The bootstrapper continuously monitors active connection count. If it drops below `MinPeerThreshold` (e.g. 4), it immediately triggers a re-bootstrap pass. This is separate from the periodic timer and fires reactively on `ConnectednessChanged` events.

```go
// Conceptual go equivalent
if len(host.Network().Peers()) < cfg.MinPeerThreshold {
    go bootstrapOnce(ctx, host, bootstrapPeers)
}
```

**py-libp2p current behaviour:**  
`BootstrapDiscovery` has no concept of minimum peer count. `stop()` just clears `discovered_peers` — there is no active monitoring loop.

**Impact:** If bootstrap peers go offline after the initial pass, py-libp2p has no mechanism to compensate. The network view stagnates.

---

### 3.3 Exponential Backoff for Failed Connections (**High**)

**go-libp2p behaviour:**  
`BackoffDiscovery` / `BackoffConnector` in `p2p/discovery/backoff` wraps any discovery mechanism with configurable backoff strategies: `FullJitter`, `NoJitter`, etc. Failed bootstrap peers are not retried immediately — backoff prevents thundering-herd during network recovery.

```go
// go-libp2p backoff
bc, _ := backoff.NewBackoffConnector(host, 1024, 30*time.Second,
    backoff.NewExponentialDecorrelatedJitter(1*time.Second, 1*time.Minute, 3.0, nil))
```

**py-libp2p current behaviour:**  
`_connect_to_peer()` uses `trio.move_on_after(self.connection_timeout)` — a single attempt with a hard timeout. There is no retry mechanism. If a bootstrap peer is temporarily unreachable, that peer is simply abandoned for the lifetime of the process.

DNS resolution does have `dns_max_retries` with backoff, but TCP connection attempts have none.

**Impact:** Transient failures during startup (e.g. a bootstrap node briefly overloaded) permanently remove that peer from consideration.

---

### 3.4 EventBus / Typed Async Events (**High**)

**go-libp2p behaviour:**  
go-libp2p uses a structured, typed event bus (`event.Bus`). Bootstrap-relevant events are:
- `event.EvtPeerConnectednessChanged` — fired on connect/disconnect
- `event.EvtLocalReachabilityChanged` — enables DHT mode switching
- `event.EvtPeerIdentificationCompleted` — fired after Identify completes

Subscribers use typed channels:
```go
sub, _ := host.EventBus().Subscribe(new(event.EvtPeerConnectednessChanged))
for evt := range sub.Out() {
    // react to connection changes
}
```

**py-libp2p current behaviour:**  
`peerDiscovery.py` implements a bare callback list:
```python
class PeerDiscovery:
    _peer_discovered_handlers: list[Callable[[PeerInfo], None]]
```
There is only one event type (`peer_discovered`). There are no connection lifecycle events, no `EvtPeerConnectednessChanged` equivalent, and no mechanism for the bootstrap module to *subscribe* to network events to trigger reactive re-bootstrap.

**Impact:** The bootstrap module cannot react to disconnections. Adding reactive behaviour later requires redesigning the event system from scratch.

---

### 3.5 Connection Manager + Peer Tagging (**High**)

**go-libp2p / js-libp2p behaviour:**  
Bootstrap peers are tagged with a named tag (`bootstrap`), a numeric value (50), and a TTL. The connection manager uses tags to decide which connections to prune when the high-watermark is reached — bootstrap peers get protected status.

```javascript
// js-libp2p @libp2p/bootstrap
bootstrap({
  list: [...],
  tagName: 'bootstrap',
  tagValue: 50,
  tagTTL: 120_000   // 2 min; set Infinity for browser clients
})
```

**py-libp2p current behaviour:**  
There is no connection manager and no concept of peer tagging. Bootstrap peers are added to the peerstore with `PERMANENT_ADDR_TTL` for addresses, but nothing prevents an unrelated high-connection workload from closing these connections.

**Impact:** Under load, bootstrap peer connections can be evicted with no guarantee of re-establishment.

---

### 3.6 DHT / Routing Table Refresh After Bootstrap (**High**)

**go-libp2p behaviour:**  
After connecting to bootstrap peers, `dht.Bootstrap(ctx)` is called to populate the Kademlia routing table by querying for random peer IDs. This is a standard call pattern in all go-libp2p applications:

```go
dht, _ := dht.New(ctx, host)
// ... connect to bootstrap peers ...
dht.Bootstrap(ctx) // triggers random-walk queries to fill routing table
```

The DHT also has a `RefreshRoutingTable()` method, and `BootstrapConfig` defines `Queries` (how many random-walk queries per period) and `Timeout`.

**py-libp2p current behaviour:**  
`BootstrapDiscovery.start()` only dials peers. It has no callback, hook, or integration point for the Kademlia DHT to start its own routing table fill after connections are established. The `random_walk` module exists in `libp2p/discovery/random_walk/` but is completely disconnected from the bootstrap module.

**Impact:** Even after successful bootstrap, the DHT routing table is not populated, so `find_peer` / `find_providers` calls may fail silently.

---

### 3.7 Standard Discovery Interface (**Medium**)

**go-libp2p behaviour:**  
The `core/discovery` package defines:
```go
type Discoverer interface {
    FindPeers(ctx context.Context, ns string, opts ...Option) (<-chan peer.AddrInfo, error)
}
type Advertiser interface {
    Advertise(ctx context.Context, ns string, opts ...Option) (time.Duration, error)
}
```
All discovery implementations (mDNS, Rendezvous, bootstrap, DHT) satisfy these interfaces, enabling composability and testing via mocks.

**py-libp2p current behaviour:**  
`BootstrapDiscovery` exposes only `start()` and `stop()`. There is no abstract `IDiscovery` base class in `libp2p/abc.py`. mDNS, rendezvous, random-walk, and bootstrap all have incompatible APIs.

**Impact:** Difficult to swap or compose discovery mechanisms. Integration tests require knowledge of each concrete class rather than a shared interface.

---

### 3.8 Default Bootstrap Peer List in Library (**Medium**)

**go-libp2p behaviour:**  
`go-libp2p-kad-dht` exports:
```go
var DefaultBootstrapPeers []multiaddr.Multiaddr
func GetDefaultBootstrapPeerAddrInfos() []peer.AddrInfo
```
Users do not need to know any specific multiaddrs — calling `dht.New(ctx, host, dht.BootstrapPeers(dht.GetDefaultBootstrapPeerAddrInfos()...))` gives a correctly bootstrapped DHT.

**py-libp2p current behaviour:**  
Default bootstrap peers exist only in `examples/bootstrap/bootstrap.py` as a module-level constant `BOOTSTRAP_PEERS`. There is no `DEFAULT_BOOTSTRAP_PEERS` exported from `libp2p/discovery/bootstrap/__init__.py` or `libp2p/__init__.py`.

**Impact:** Every consumer must copy-paste the bootstrap peer list or depend on the examples directory. This is a poor library UX and inconsistent with go/js-libp2p.

---

### 3.9 Peer Address TTL Strategy (**Medium**)

**go-libp2p behaviour:**  
go-libp2p assigns different TTLs based on how an address was learned:
- `PermanentAddrTTL` for bootstrap / configured peers (addresses that should never expire)
- `ConnectedAddrTTL` for peers we're currently connected to
- `RecentlyConnectedAddrTTL` for peers we've recently disconnected from
- `OwnObservedAddrTTL` for self-observed addresses

**py-libp2p current behaviour:**  
`add_addr()` unconditionally uses `PERMANENT_ADDR_TTL` for all bootstrap peer addresses:
```python
self.peerstore.add_addrs(peer_info.peer_id, supported_addrs, PERMANENT_ADDR_TTL)
```
This is correct for the initial add, but there is no logic to downgrade to `RecentlyConnectedAddrTTL` after disconnection, nor to upgrade addresses based on successful connections.

**Impact:** Peerstore grows unboundedly with stale bootstrap addresses. No distinction between "bootstrap configured" vs. "recently seen".

---

### 3.10 Network Change Detection / Interface Polling (**Medium**)

**go-libp2p design intent:**  
go-libp2p issue #304 explicitly called for polling `host.Network().InterfaceAddresses()` for changes (e.g. IP address change after DHCP renewal, WiFi switch). When a network interface change is detected, a new bootstrap pass is triggered.

**py-libp2p current behaviour:**  
No interface polling. Bootstrap runs once at startup. NAT traversal changes, interface flap events, or IP address renewals are invisible to the bootstrap module.

**Impact:** Nodes behind a NAT or with dynamic IPs will not recover connectivity automatically after network interface events.

---

### 3.11 IP Diversity Filtering (**Low**)

**go-libp2p behaviour:**  
`go-libp2p-kad-dht` provides `NewRTPeerDiversityFilter(host, maxPerCpl, maxForTable)` which limits how many routing-table entries can share the same `/24` IPv4 prefix or `/48` IPv6 prefix. This resists Sybil-style routing table poisoning via bootstrap.

**py-libp2p current behaviour:**  
No IP diversity filtering in the bootstrap module or the routing table. All addresses from bootstrap peers are added regardless of IP prefix overlap.

**Impact:** A malicious bootstrap peer list could place many peers in the same IP range, degrading DHT lookup quality.

---

### 3.12 QUIC / WebTransport Address Support (**Low**)

**go-libp2p behaviour:**  
go-libp2p's swarm tries all available transports per peer. A bootstrap peer advertising both `/ip4/1.2.3.4/tcp/4001` and `/ip4/1.2.3.4/udp/4001/quic-v1` will be dialed over whichever succeeds first, with happy-eyeballs-style racing.

**py-libp2p current behaviour:**  
`_is_supported_addr()` explicitly filters to `P_TCP` only (plus optional `P_IP6`). QUIC multiaddrs are silently dropped:
```python
# Must have TCP protocol (by code)
has_tcp = any(p.code == P_TCP for p in protocols)
if not has_tcp:
    return False
```
The `filecoin/bootstrap.py` has a `filter_bootstrap_for_transport()` that accepts a `include_quic` flag, but the core `BootstrapDiscovery` class has no equivalent.

**Impact:** Once py-libp2p's QUIC transport matures, the bootstrap module will need an update to not discard valid QUIC-only bootstrap addresses.

---

### 3.13 Circuit Relay / AutoRelay Integration (**Low**)

**go-libp2p behaviour:**  
`libp2p.EnableAutoRelay()` hooks into the peer discovery pipeline. When a new peer is discovered (including via bootstrap), it is evaluated as a potential relay candidate. Bootstrap peers themselves are often relay-capable, so this synergy is intentional.

**py-libp2p current behaviour:**  
`peerDiscovery.emit_peer_discovered()` fires a callback, but no relay subsystem listens to it. Circuit relay v2 exists in py-libp2p but is not wired to the bootstrap-discovered peer feed.

**Impact:** py-libp2p nodes behind strict NATs cannot leverage bootstrap peers as relay candidates.

---

### 3.14 Structured Lifecycle (Process/Closer Pattern) (**Low**)

**go-libp2p behaviour:**  
`dht.BootstrapWithConfig()` returns a `goprocess.Process` which has a clean `Close()` method and a `Closed()` channel. The caller can `defer proc.Close()` and the bootstrap goroutine exits cleanly on context cancellation.

**py-libp2p current behaviour:**  
`stop()` clears `discovered_peers` but does not cancel any in-progress Trio tasks. If `start()` is called inside a nursery and the nursery is cancelled mid-run, cleanup is handled by Trio's cancellation machinery rather than a structured `stop()` hook. The `stop()` method is essentially a no-op beyond cache clearing.

**Impact:** Minor — Trio's structured concurrency handles most of this, but a proper `async with bootstrap:` context manager idiom would make lifecycle explicit and testable.

---

## 4. Code-Level Issues Found

Beyond the missing features, several specific code issues were noted during the audit:

### 4.1 `start()` validates addresses after logging them

```python
async def start(self) -> None:
    for i, addr in enumerate(self.bootstrap_addrs):
        logger.debug(f"{i + 1}. {addr}")          # ← logs before validation

    self.bootstrap_addrs = validate_bootstrap_addresses(self.bootstrap_addrs)  # ← validates after
```
Validation should run first; logging should reflect the validated set to avoid misleading debug output.

### 4.2 `stop()` is synchronous but the class is async-first

```python
def stop(self) -> None:
    self.discovered_peers.clear()
```
There is no `async def stop()` and no mechanism to signal background tasks to exit. If `start()` is ever made persistent (e.g. for periodic re-bootstrap), this `stop()` won't be able to cancel those tasks. It should be `async def stop(self)` returning a cancellable scope.

### 4.3 Connection check race condition

```python
# In add_addr():
if peer_info.peer_id not in self.swarm.connections:
    await self._connect_to_peer(peer_info.peer_id)

# Inside _connect_to_peer():
if peer_id in self.swarm.connections:
    return  # already connected
```
The double check (`add_addr` then `_connect_to_peer`) has a TOCTOU window in concurrent nursery tasks. Two tasks processing addresses for the same peer can both pass the first check before either connects. A `trio.Lock` per peer_id would eliminate this.

### 4.4 `PERMANENT_ADDR_TTL` is inappropriate for non-confirmed bootstrap peers

Addresses are added with `PERMANENT_ADDR_TTL` before a connection is even attempted. If connection fails, the stale addresses remain permanently in the peerstore. The correct pattern is:
1. Add with a short TTL (e.g. 10 minutes) initially.
2. Upgrade to `PERMANENT_ADDR_TTL` only after a successful connection.

### 4.5 No metric counters

The DNS resolution path has `DNSResolutionMetrics` — good. But bootstrap itself has no counters for:
- Total peers discovered
- Total peers successfully connected
- Total connection failures
- Connection latency histogram

go-libp2p exposes all of these via Prometheus. py-libp2p has a monitoring demo but bootstrap doesn't hook into it.

---

## 5. Proposed Improvements with Implementation Sketches

### 5.1 Add `BootstrapConfig` and periodic re-bootstrap

```python
# libp2p/discovery/bootstrap/config.py  (NEW FILE)
from dataclasses import dataclass, field

@dataclass
class BootstrapConfig:
    bootstrap_addrs: list[str]
    min_peer_threshold: int = 4          # trigger re-bootstrap below this
    period: float = 30.0                 # seconds between periodic checks
    connection_timeout: float = 10.0
    allow_ipv6: bool = False
    dns_resolution_timeout: float = 10.0
    dns_max_retries: int = 3
```

```python
# In BootstrapDiscovery:
async def run(self) -> None:
    """Long-running background task: initial bootstrap + periodic refresh."""
    await self.start()          # initial one-shot pass (existing logic)

    async with trio.open_nursery() as nursery:
        nursery.start_soon(self._periodic_check_loop)
        nursery.start_soon(self._event_listener_loop)   # future: event bus

async def _periodic_check_loop(self) -> None:
    while True:
        await trio.sleep(self.period)
        connected = len(self.swarm.connections)
        if connected < self.min_peer_threshold:
            logger.info(
                f"Below threshold ({connected} < {self.min_peer_threshold}), "
                "re-bootstrapping..."
            )
            await self.start()
```

### 5.2 Exponential backoff per peer

```python
# libp2p/discovery/bootstrap/backoff.py  (NEW FILE)
import math, trio

class ExponentialBackoff:
    def __init__(self, base: float = 1.0, cap: float = 60.0, factor: float = 2.0):
        self.base = base
        self.cap = cap
        self.factor = factor
        self._attempts: dict[str, int] = {}

    def record_failure(self, peer_id: str) -> None:
        self._attempts[peer_id] = self._attempts.get(peer_id, 0) + 1

    def record_success(self, peer_id: str) -> None:
        self._attempts.pop(peer_id, None)

    def delay(self, peer_id: str) -> float:
        n = self._attempts.get(peer_id, 0)
        return min(self.base * (self.factor ** n), self.cap)
```

```python
# In _connect_to_peer():
delay = self._backoff.delay(str(peer_id))
if delay > 0:
    logger.debug(f"Backoff {delay:.1f}s before retrying {peer_id}")
    await trio.sleep(delay)

try:
    await self.swarm.dial_peer(peer_id)
    self._backoff.record_success(str(peer_id))
except (SwarmDialAllFailedError, SwarmException):
    self._backoff.record_failure(str(peer_id))
    raise
```

### 5.3 Export `DEFAULT_BOOTSTRAP_PEERS` from the library

```python
# libp2p/discovery/bootstrap/peers.py  (NEW FILE)
"""
Well-known public bootstrap peers for the libp2p network.
Mirrors go-libp2p-kad-dht's DefaultBootstrapPeers.
"""

DEFAULT_BOOTSTRAP_PEERS: list[str] = [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwgVma9sHHFKR2MF4KALd7PAnrAqFBsYcxhpGT",
    "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
    "/ip4/104.236.179.241/tcp/4001/p2p/QmSoLPppuBtQSGwKDZT2M73ULpjvfd3aZ6ha4oFGL1KrGM",
    "/ip4/128.199.219.111/tcp/4001/p2p/QmSoLV4Bbm51jM9C4gDYZQ9Cy3U6aXMJDAbzgu2fzaDs64",
    "/ip4/104.236.76.40/tcp/4001/p2p/QmSoLV4Bbm51jM9C4gDYZQ9Cy3U6aXMJDAbzgu2fzaDs64",
    "/ip4/178.62.158.247/tcp/4001/p2p/QmSoLer265NRgSp2LA3dPaeykiS1J6DifTC88f5uVQKNAd",
]
```

```python
# libp2p/discovery/bootstrap/__init__.py  (UPDATED)
from .bootstrap import BootstrapDiscovery
from .config import BootstrapConfig
from .peers import DEFAULT_BOOTSTRAP_PEERS

__all__ = ["BootstrapDiscovery", "BootstrapConfig", "DEFAULT_BOOTSTRAP_PEERS"]
```

### 5.4 Add `IDiscovery` abstract base class

```python
# libp2p/abc.py  (ADD to existing file)
from abc import ABC, abstractmethod
from typing import AsyncIterator

class IDiscovery(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...   # make async

    @abstractmethod
    def register_peer_discovered_handler(
        self, handler: Callable[[PeerInfo], None]
    ) -> None: ...
```

```python
# BootstrapDiscovery now inherits IDiscovery
class BootstrapDiscovery(IDiscovery):
    ...
    async def stop(self) -> None:       # was sync, now async
        self._cancel_scope.cancel()
        self.discovered_peers.clear()
```

### 5.5 Add two-phase TTL for peerstore entries

```python
# In add_addr() — before connection attempt
self.peerstore.add_addrs(
    peer_info.peer_id,
    supported_addrs,
    ttl=600,   # 10 min provisional TTL
)

# In _connect_to_peer() — on success
if peer_id in self.swarm.connections:
    # Upgrade to permanent TTL after confirmed connection
    self.peerstore.add_addrs(
        peer_id,
        self.peerstore.addrs(peer_id),
        PERMANENT_ADDR_TTL,
    )
```

### 5.6 Fix the TOCTOU race with a per-peer lock

```python
# In BootstrapDiscovery.__init__():
self._connecting: set[str] = set()
self._connect_lock = trio.Lock()

# In add_addr():
peer_id_str = str(peer_info.peer_id)
async with self._connect_lock:
    if peer_id_str in self._connecting:
        return
    self._connecting.add(peer_id_str)
try:
    await self._connect_to_peer(peer_info.peer_id)
finally:
    self._connecting.discard(peer_id_str)
```

### 5.7 DHT integration hook

Add an optional callback so the caller can trigger DHT refresh after bootstrap:

```python
class BootstrapDiscovery(IDiscovery):
    def __init__(
        self,
        swarm: INetworkService,
        bootstrap_addrs: list[str],
        *,
        on_bootstrap_complete: Callable[[], Awaitable[None]] | None = None,
        ...
    ):
        self.on_bootstrap_complete = on_bootstrap_complete

    async def start(self) -> None:
        # ... existing logic ...
        if self.on_bootstrap_complete and len(self.swarm.connections) > 0:
            await self.on_bootstrap_complete()
```

Usage at the caller site:
```python
kademlia_dht = KademliaServer(...)

bootstrap = BootstrapDiscovery(
    swarm=swarm,
    bootstrap_addrs=DEFAULT_BOOTSTRAP_PEERS,
    on_bootstrap_complete=kademlia_dht.bootstrap_routing_table,
)
```

---

## 6. Recommended Contribution Roadmap

The gaps are organised into three phases, each independently PR-able.

### Phase 1 — Correctness and Stability (Immediate)

| PR | Title | Files Changed |
|---|---|---|
| #A | Fix TOCTOU race in parallel connect | `bootstrap.py` |
| #B | Fix `stop()` → `async def stop()`, add cancel scope | `bootstrap.py` |
| #C | Move address validation before logging in `start()` | `bootstrap.py` |
| #D | Two-phase peerstore TTL (provisional → permanent) | `bootstrap.py` |
| #E | Export `DEFAULT_BOOTSTRAP_PEERS` from library | new `peers.py`, `__init__.py` |

### Phase 2 — Feature Parity (Short-term)

| PR | Title | Files Changed |
|---|---|---|
| #F | Add `BootstrapConfig` dataclass | new `config.py`, `bootstrap.py` |
| #G | Add `ExponentialBackoff` and wire into `_connect_to_peer` | new `backoff.py`, `bootstrap.py` |
| #H | Add `min_peer_threshold` watchdog + `period` re-bootstrap loop | `bootstrap.py` |
| #I | Add `IDiscovery` ABC to `libp2p/abc.py` | `abc.py`, `bootstrap.py` |
| #J | DHT integration hook (`on_bootstrap_complete` callback) | `bootstrap.py`, docs |

### Phase 3 — Advanced (Medium-term)

| PR | Title | Files Changed |
|---|---|---|
| #K | QUIC address support via `include_quic` flag | `bootstrap.py`, `utils.py` |
| #L | Typed event system (`EvtPeerConnectednessChanged`) | new `events/` module |
| #M | IP prefix diversity filter | new `diversity.py`, `bootstrap.py` |
| #N | Prometheus metrics for bootstrap (peers discovered, latency) | `bootstrap.py`, monitoring docs |

---

*Analysis performed by code inspection of `libp2p/py-libp2p` (April 2026) and comparison with `go-libp2p`, `go-libp2p-kad-dht`, and `js-libp2p/packages/peer-discovery-bootstrap`.*
