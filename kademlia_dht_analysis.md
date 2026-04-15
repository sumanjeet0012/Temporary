# Kademlia DHT: py-libp2p vs go-libp2p — Deep Analysis & Gap Report

> **Scope:** This document provides an exhaustive, side-by-side analysis of the Kademlia DHT
> implementations in `py-libp2p` (Python) and `go-libp2p-kad-dht` (Go). Every architectural
> layer is compared, and all gaps in py-libp2p are catalogued with prioritised recommendations
> for contributors.
>
> **Baseline versions:** py-libp2p ≥ 0.3.0 (post-PR #579, after KadDHT landed); go-libp2p-kad-dht master (Apr 2026)

---

## Table of Contents

1. [Implementation Overview](#1-implementation-overview)
2. [Architecture Comparison](#2-architecture-comparison)
3. [Feature Matrix](#3-feature-matrix)
4. [Layer-by-Layer Deep Dive](#4-layer-by-layer-deep-dive)
   - 4.1 [Routing Table & K-Buckets](#41-routing-table--k-buckets)
   - 4.2 [Core DHT Operations (RPC Wire Protocol)](#42-core-dht-operations-rpc-wire-protocol)
   - 4.3 [Iterative Lookup Algorithm](#43-iterative-lookup-algorithm)
   - 4.4 [Value Store & Provider Records](#44-value-store--provider-records)
   - 4.5 [Record Validation & Selection](#45-record-validation--selection)
   - 4.6 [Bootstrap & Routing Table Refresh](#46-bootstrap--routing-table-refresh)
   - 4.7 [Client / Server Modes](#47-client--server-modes)
   - 4.8 [Peer Diversity & Routing Table Security](#48-peer-diversity--routing-table-security)
   - 4.9 [Observability: Metrics & Tracing](#49-observability-metrics--tracing)
   - 4.10 [Concurrency Model](#410-concurrency-model)
   - 4.11 [Network Utilities](#411-network-utilities)
5. [Missing Features — Prioritised](#5-missing-features--prioritised)
   - 5.1 [P0 — Critical / Spec Compliance](#51-p0--critical--spec-compliance)
   - 5.2 [P1 — High / Production Readiness](#52-p1--high--production-readiness)
   - 5.3 [P2 — Medium / Robustness & Security](#53-p2--medium--robustness--security)
   - 5.4 [P3 — Low / Nice-to-Have & Advanced](#54-p3--low--nice-to-have--advanced)
6. [Contribution Roadmap](#6-contribution-roadmap)
7. [References](#7-references)

---

## 1. Implementation Overview

| Attribute | py-libp2p | go-libp2p-kad-dht |
|---|---|---|
| **Language** | Python 3.10+ | Go 1.21+ |
| **Concurrency runtime** | Trio (structured concurrency) | goroutines + context |
| **Protocol ID** | `/ipfs/kad/1.0.0` | `/ipfs/kad/1.0.0` (+ legacy `/kad/1.0.0`) |
| **Wire format** | Protobuf (`dht.proto`) | Protobuf (`dht.proto`) |
| **Keyspace** | SHA-256 (256-bit XOR) | SHA-256 (256-bit XOR) |
| **Replication factor k** | 20 (configurable) | 20 (configurable) |
| **Alpha (concurrency)** | 3 | 10 (configurable) |
| **Repo** | `libp2p/py-libp2p` → `libp2p/kad_dht/` | `libp2p/go-libp2p-kad-dht` |
| **Spec compliance** | Partial | Near-complete + extensions |
| **IPFS / Amino DHT compat** | Partial | Full |
| **S/Kademlia extensions** | ❌ Not implemented | ✅ Disjoint paths |
| **Coral/BitTorrent extensions** | ❌ | ✅ Provider records |
| **Production maturity** | Early / experimental | Battle-tested (IPFS mainnet) |

---

## 2. Architecture Comparison

### py-libp2p Directory Structure

```
libp2p/kad_dht/
├── __init__.py
├── kad_dht.py          # KadDHT service, DHTMode, bootstrap, put/get/provide logic
├── routing_table.py    # KBucket, RoutingTable
├── value_store.py      # ValueStore (in-memory, TTL-based)
├── lookup.py           # Iterative lookup coroutine
├── utils.py            # xor_distance, sort_peer_ids_by_distance, shared_prefix_len
└── pb/                 # Compiled protobuf (dht_pb2.py)
```

### go-libp2p-kad-dht Directory Structure

```
go-libp2p-kad-dht/
├── dht.go              # IpfsDHT struct, New(), mode management, identify integration
├── dht_bootstrap.go    # Bootstrap logic, routing table refresh triggers
├── routing.go          # PutValue, GetValue, Provide, FindProvidersAsync
├── lookup.go           # runLookup(), makeAsyncFindOrStop()
├── query.go            # queryManager, queryPeerState machine
├── records/
│   ├── provider_manager.go   # ProviderManager with go-datastore persistence
│   └── selection.go          # Best-record selection
├── pb/
│   └── dht.pb.go             # Wire messages
├── rtrefresh/
│   └── rt_refresh_manager.go # Periodic routing table refresh with math-based timing
├── netsize/
│   └── netsize.go            # Network size estimation
├── internal/
│   ├── config/               # Full Option-builder config system
│   └── metrics/              # Prometheus metrics
├── peerdiversity/
│   └── (via go-libp2p-kbucket) # IP-diversity filter
└── tracing.go                # OpenTelemetry span tracing
```

The Go implementation is a full subsystem with **~12 specialized files + sub-packages** versus py-libp2p's **~6 core files**. This structural gap maps directly to the missing feature set described below.

---

## 3. Feature Matrix

The table uses the following symbols:

- ✅ **Implemented & functional**
- ⚠️ **Partially implemented / differs from spec**
- ❌ **Not implemented**
- 🔬 **Experimental / untested interop**

| Feature | py-libp2p | go-libp2p | Notes |
|---|:---:|:---:|---|
| **FIND_NODE RPC** | ✅ | ✅ | |
| **PUT_VALUE RPC** | ✅ | ✅ | |
| **GET_VALUE RPC** | ✅ | ✅ | |
| **ADD_PROVIDER RPC** | ✅ | ✅ | |
| **GET_PROVIDERS RPC** | ✅ | ✅ | |
| **PING RPC** | ❌ | ✅ | Used for bucket liveness checks |
| **k-bucket split on overflow** | ✅ | ✅ | py-libp2p PR #846 |
| **XOR distance metric** | ✅ | ✅ | |
| **SHA-256 key hashing** | ✅ | ✅ | |
| **Iterative lookup (α-concurrent)** | ⚠️ | ✅ | py alpha=3, Go alpha=10 |
| **Lookup termination (k-closest converge)** | ⚠️ | ✅ | Subtle correctness differences |
| **Disjoint paths (S/Kademlia)** | ❌ | ✅ | `d` parallel disjoint paths |
| **Lookup event streaming** | ❌ | ✅ | `LookupEvent` pub/sub |
| **Query state machine** | ⚠️ | ✅ | Go has explicit peer states |
| **Routing Table Refresh Manager** | ❌ | ✅ | Math-based adaptive refresh |
| **Periodic random-walk refresh** | ⚠️ | ✅ | py-libp2p basic bootstrap only |
| **Identify-triggered RT updates** | ❌ | ✅ | Event-driven from identify |
| **Connection manager RT scoring** | ❌ | ✅ | CPL-based kbucket tag scoring |
| **Peer diversity filter (IP-group)** | ❌ | ✅ | Anti-eclipse hardening |
| **`minRTRefreshThreshold` logic** | ❌ | ✅ | Avoids polluting small tables |
| **Network size estimator** | ❌ | ✅ | `netsize` package |
| **AUTO mode (detect reachability)** | ❌ | ✅ | Auto CLIENT↔SERVER switching |
| **CLIENT mode** | ✅ | ✅ | |
| **SERVER mode** | ✅ | ✅ | |
| **Custom namespace validators** | ✅ | ✅ | |
| **Best-record selector** | ❌ | ✅ | Selector per namespace |
| **Quorum-based GET** | ❌ | ✅ | Wait for `quorum` responses |
| **Provider record persistence** | ❌ | ✅ | go-datastore backed |
| **Provider record GC / expiry** | ⚠️ | ✅ | py: in-memory TTL only |
| **Provider re-announcement** | ❌ | ✅ | Republish every 12h |
| **Value record republish** | ❌ | ✅ | Republish every 24h |
| **Public key record (`/pk/` ns)** | ❌ | ✅ | `GetPublicKey()` |
| **IPNS record (`/ipns/` ns)** | ❌ | ✅ | IPNS validator built-in |
| **`GetClosestPeers()` public API** | ❌ | ✅ | Returns k-closest chan |
| **Default IPFS bootstrap peers** | ❌ | ✅ | Hardcoded Amino DHT list |
| **Public/private routing filter** | ❌ | ✅ | LAN vs WAN filter fns |
| **OpenTelemetry tracing** | ❌ | ✅ | Per-operation spans |
| **Prometheus metrics** | ❌ | ✅ | RT size, query latencies, etc. |
| **Structured logging** | ⚠️ | ✅ | py uses stdlib logging |
| **Option builder (functional config)** | ⚠️ | ✅ | py: constructor kwargs |
| **Interop with go-libp2p nodes** | 🔬 | ✅ | Basic ops work; advanced don't |
| **Interop with IPFS mainnet** | 🔬 | ✅ | |
| **Test coverage (unit)** | ⚠️ | ✅ | Basic tests exist |
| **Test coverage (interop)** | ❌ | ✅ | Cross-impl interop tests |

---

## 4. Layer-by-Layer Deep Dive

### 4.1 Routing Table & K-Buckets

#### py-libp2p

The `RoutingTable` class holds a list of `KBucket` objects. Each `KBucket` stores `PeerInfo` objects (peer_id + multiaddrs) with a last-seen timestamp. Buckets split when they overflow the `k=20` limit and the local node's ID falls in the overflowing bucket's range. Core methods:

```
RoutingTable.add_peer()
RoutingTable.remove_peer()
RoutingTable.find_local_closest_peers()   # O(k * num_buckets) XOR sort
RoutingTable.get_stale_peers()
RoutingTable.cleanup_routing_table()
KBucket.split()
```

**What works well:** Standard lazy-split Kademlia structure, SHA-256 bucket IDs, XOR comparisons, basic stale peer cleanup.

**What's missing / diverges:**

| Gap | go-libp2p approach |
|---|---|
| No pending-slot for full buckets | Go holds a `replacement cache` per bucket and installs replacements when a live peer fails a PING |
| No CPL-based connection manager scoring | Go sets a `kbucket` tag on every peer's conn manager entry; score = `baseConnMgrScore + CPL` so highly-useful peers are protected |
| No `PeerKadID` typed identifier | Go unifies `peer.ID` + `kb.ID` to avoid repeated re-hashing |
| No routing table filter hooks | Go exposes `RouteTableFilterFunc` and `QueryFilterFunc` for LAN/WAN separation and custom admission policies |
| `find_local_closest_peers` not alpha-sorted across buckets efficiently | Go uses `go-libp2p-kbucket`'s `NearestPeers(key, count)` with a sorted-set structure |
| No diversity constraint on RT population | Covered in §4.8 |

---

### 4.2 Core DHT Operations (RPC Wire Protocol)

Both implementations use the same Protobuf `Message` type with `MessageType` enum:

```protobuf
enum MessageType {
  PUT_VALUE     = 0;
  GET_VALUE     = 1;
  ADD_PROVIDER  = 2;
  GET_PROVIDERS = 3;
  FIND_NODE     = 4;
  PING          = 5;
}
```

#### py-libp2p

All five meaningful types (0–4) are handled. Each is opened as a new libp2p stream over `/ipfs/kad/1.0.0`.

**Missing: `PING` (type 5)**

Go uses PING actively during routing table maintenance: before evicting a bucket peer to make room for a new one, it PINGs the oldest peer. If the PING succeeds the new peer is rejected; if it fails the old peer is evicted. Without PING, py-libp2p's bucket eviction is purely timer-based (stale timestamp), which is less accurate and can cause premature or late evictions.

```python
# py-libp2p: missing ping implementation
# Needed in kad_dht.py:
async def ping(self, peer_id: ID) -> bool:
    stream = await self.host.new_stream(peer_id, [KAD_PROTOCOL_ID])
    msg = dht_pb2.Message(type=dht_pb2.Message.PING)
    await write_pbmsg(stream, msg)
    response = await read_pbmsg(stream)
    return response.type == dht_pb2.Message.PING
```

---

### 4.3 Iterative Lookup Algorithm

The spec-compliant lookup keeps two sets: `Pq` (already queried) and `Pn` (candidates sorted by XOR distance ascending). α peers are queried concurrently. Terminates when the k-closest known peers have all been queried.

#### py-libp2p

Implements the iterative lookup in `lookup.py`. The core logic is correct but has these gaps:

**1. Concurrency (α) is fixed at 3, not configurable.** Go exposes this as `dht.opt.concurrency` (default 10 for Amino DHT).

**2. No explicit query-peer state machine.** Go's `query.go` maintains per-peer states:

```
Unreached → Waiting → Queried
                    ↘ Unreachable
```

This allows proper backfill (when an in-flight query returns the response, newly-discovered peers are inserted into Pn before the termination check). Without explicit states, py-libp2p can terminate early or fail to discover close peers.

**3. No disjoint path parallelism (S/Kademlia §4.4).**

**4. No `LookupEvent` emission** — go-libp2p streams granular lookup events (request sent, response received, peer added to result set, termination reason) to an optional channel. This enables debugging tools and monitoring dashboards.

**5. Lookup termination reason not tracked.** Go distinguishes:
- `LookupStopped` — user stopFn cancelled
- `LookupCancelled` — context cancelled
- `LookupStarvation` — no more unqueried peers
- `LookupCompleted` — k-closest all queried

---

### 4.4 Value Store & Provider Records

#### py-libp2p `ValueStore`

In-memory dictionary with TTL expiry. API: `put`, `get`, `has`, `remove`, `cleanup_expired`, `size`, `get_keys`. Cleaned up by a background Trio task.

**Limitations:**

| Issue | Impact |
|---|---|
| **No persistence across restarts** | Node loses all stored records on shutdown |
| **No republishing** | Records silently expire without re-announcement; network gradually loses data |
| **Provider records stored in same ValueStore** | Semantically different from value records; go-libp2p has a dedicated `ProviderManager` |
| **No cap on stored records** | Unbounded memory growth |
| **No provider expiry (12 h per spec)** | Spec requires providers to be GC'd after 12 hours unless re-announced |

#### go-libp2p `ProviderManager`

A dedicated struct backed by `go-datastore` (typically BadgerDB or LevelDB). Features:

- Provider records expire after `ProvideValidity` (12 hours, spec-mandated)
- A background goroutine runs `GC()` periodically
- Persistent across restarts
- Cap on providers per CID
- Separate from generic key-value records

**Value record republishing** (go-libp2p only):

```go
// Every 24h, re-PUT all locally-originated value records to the k-closest peers
func (dht *IpfsDHT) republishKeys(ctx context.Context) {
    for key, value := range dht.localRecords {
        dht.PutValue(ctx, key, value)
    }
}
```

The original Kademlia paper (§2.3) mandates this; py-libp2p omits it entirely.

---

### 4.5 Record Validation & Selection

#### py-libp2p

Custom validators are supported via `libp2p.records.validator.Validator`. The `KadDHT` accepts a `validators` dict mapping namespace → `Validator`. This matches the go-libp2p model for validation.

**What's missing: Record Selection (Selector)**

When `GET_VALUE` returns multiple records from different peers, go-libp2p runs a **selector** function per namespace to pick the best record:

```go
type SelectFunc func(key string, values [][]byte) (int, error)
// e.g., for /ipns/: picks the record with the highest sequence number
```

py-libp2p always returns the first valid record. This is incorrect for IPNS (which should return the highest-seq record) and any namespace where records can be legitimately updated.

**Built-in namespaces in go-libp2p:**

| Namespace | Validator | Selector |
|---|---|---|
| `/pk/` | Checks pubkey matches peer ID hash | First valid |
| `/ipns/` | Checks IPNS record signature | Highest sequence number |

py-libp2p has neither `/pk/` nor `/ipns/` built-in.

---

### 4.6 Bootstrap & Routing Table Refresh

#### py-libp2p

Bootstrap connects to a list of provided multiaddresses and performs a `FIND_NODE` for the local peer ID to populate the routing table. A simple periodic refresh re-bootstraps on a fixed interval.

**What's missing:**

**1. Math-based adaptive refresh interval** (`rtrefresh.RtRefreshManager`)

Go computes a `maxLastSuccessfulOutboundThreshold` using:

```go
l1 := math.Log(float64(1) - math.Pow(float64(1)/float64(cfg.BucketSize), float64(cfg.BucketSize)))
l2 := math.Log(float64(1) - (float64(cfg.Concurrency) / float64(cfg.BucketSize)))
maxLastSuccessfulOutboundThreshold = time.Duration(l1 / l2 * float64(cfg.RoutingTable.RefreshInterval))
```

Buckets that haven't been queried within this threshold are refreshed with a random lookup in their keyspace range. py-libp2p uses a simple fixed timer, meaning quiet buckets may go stale.

**2. Identify-triggered routing table updates**

When a peer's identify response arrives (or updates), go-libp2p immediately evaluates it as a routing table candidate. This is the primary way the RT populates efficiently on a live network. py-libp2p populates the RT only during explicit DHT operations.

```go
// go-libp2p dht.go
dht.host.Network().Notify(&network.NotifyBundle{
    ConnectedF: func(net network.Network, conn network.Conn) {
        // evaluate conn for RT inclusion based on identify
    },
})
```

**3. `minRTRefreshThreshold`**

Before adding a peer to the routing table, go-libp2p checks: "if the RT already has `> minRTRefreshThreshold` peers, only add this peer if we actually got a response from them (not just a new connection)." This prevents routing table pollution in a large network.

**4. Default IPFS bootstrap peers**

go-libp2p ships `DefaultBootstrapPeers` (the Amino DHT bootstrap nodes). py-libp2p requires the caller to supply all bootstrap addresses.

---

### 4.7 Client / Server Modes

Both implementations support `CLIENT` and `SERVER` modes per the spec:

- **SERVER**: advertises `/ipfs/kad/1.0.0` via identify, handles incoming streams, populates other nodes' routing tables
- **CLIENT**: queries the DHT without advertising, not added to others' routing tables

#### py-libp2p gap: No AUTO mode

go-libp2p implements a third mode: **`ModeAuto`**. The DHT monitors whether the local node has public (routable) addresses via the libp2p autonat subsystem. If reachable → switches to SERVER; if behind NAT → stays CLIENT. This is critical for correct IPFS network behavior.

```go
// go-libp2p dht.go
case ModeAuto:
    dht.host.Network().Notify(&network.NotifyBundle{
        // subscribe to reachability events from autonat
    })
```

py-libp2p requires the caller to explicitly choose a mode. An incorrect choice (e.g., CLIENT behind NAT choosing SERVER) degrades the network for everyone.

---

### 4.8 Peer Diversity & Routing Table Security

This is one of the most significant security gaps in py-libp2p's DHT.

#### go-libp2p Peer Diversity Filter

go-libp2p-kbucket (the routing table library) supports a `PeerIPGroupFilter` that limits how many peers from the same IP subnet can occupy each k-bucket:

```go
func NewRTPeerDiversityFilter(h host.Host, maxPerCpl, maxForTable int) *rtPeerIPGroupFilter
```

- `maxPerCpl`: max peers from same /24 subnet per bucket
- `maxForTable`: max peers from same /24 across the whole table

**Why this matters:** Without IP diversity constraints, an attacker can:
1. Generate many peer IDs near a target key (Sybil attack)
2. Fill the victim's relevant k-bucket with attacker-controlled nodes
3. Censor or eclipse all queries for that key region

py-libp2p has **no IP diversity filter**. The routing table accepts any peer regardless of IP grouping.

#### Public vs Private Routing Table Filters

go-libp2p also ships two admission filters:

```go
func PublicQueryFilter(_ *IpfsDHT, ai peer.AddrInfo) bool
    // true if peer appears publicly reachable

func PrivateRoutingTableFilter(dht *IpfsDHT, conns []network.Conn) bool
    // true if peer is on a private/LAN network
```

This allows running a LAN-only DHT (`/ipfs/lan/kad/1.0.0`) and a public DHT simultaneously, with cleanly separated routing tables. py-libp2p has no equivalent.

---

### 4.9 Observability: Metrics & Tracing

#### go-libp2p

Full observability stack:

**OpenTelemetry Tracing**: Every top-level DHT operation (`PutValue`, `GetValue`, `Provide`, `FindProvidersAsync`, `FindPeer`) creates a named span. Internal operations like `sendRequest` create child spans. Span attributes include peer ID, key, operation result.

```go
func (dht *IpfsDHT) PutValue(ctx context.Context, key string, value []byte, ...) (err error) {
    ctx, end := tracer.PutValue(dhtName, ctx, key, value, opts...)
    defer func() { end(err) }()
    // ...
}
```

**Prometheus Metrics** (via `internal/metrics`):

- Routing table size over time
- Query latency histograms per operation type
- Number of peers queried per lookup
- Provider store size
- Bootstrap success/failure counts
- RT refresh timing

**Query event bus**: Lookup state changes are emitted as `LookupEvent` structs on a context-attached channel, enabling real-time inspection.

#### py-libp2p

Uses Python stdlib `logging` with no structured fields. No metrics, no tracing spans.

---

### 4.10 Concurrency Model

Both implementations use structured concurrency, but the models differ significantly.

| Aspect | py-libp2p (Trio) | go-libp2p (goroutines) |
|---|---|---|
| **Task spawning** | `nursery.start_soon()` | `go func()` + context |
| **Cancellation** | Trio cancel scope | `context.WithCancel` |
| **Query concurrency** | `trio.open_nursery()` with α tasks | `queryManager` with goroutine pool |
| **RT refresh** | Simple periodic task | `RtRefreshManager` with math-derived schedule |
| **Provider GC** | Single cleanup task | ProviderManager GC goroutine |

**Key py-libp2p concern:** The iterative lookup fires α concurrent stream operations inside a nursery. If any sub-task raises an unhandled exception, Trio cancels the whole nursery, potentially dropping valid responses mid-lookup. The Go implementation isolates per-peer query failures explicitly via error returns, never aborting sibling queries.

---

### 4.11 Network Utilities

#### Network Size Estimator (`netsize` package) — go-libp2p only

go-libp2p maintains a running estimate of the DHT network size based on observed bucket fill levels:

```go
// netsize.go
func (e *Estimator) NetworkSize() (int32, error)
```

This is used to:
- Auto-tune k (rare) and advertise replication
- Compute expected lookup depth (log₂(N))
- Detect network partitions

py-libp2p has no equivalent.

#### `GetClosestPeers()` — go-libp2p only

```go
func (dht *IpfsDHT) GetClosestPeers(ctx context.Context, key string) (<-chan peer.ID, error)
```

Streams the k-closest peers to a raw string key. Used by IPFS for advanced content routing. py-libp2p exposes no equivalent public API.

#### `GetPublicKey()` — go-libp2p only

```go
func (dht *IpfsDHT) GetPublicKey(ctx context.Context, p peer.ID) (ci.PubKey, error)
```

Retrieves a peer's public key from the DHT (stored under `/pk/<multihash>`). Essential for verifying IPNS records and authenticating peer identities. py-libp2p has no `/pk/` namespace support.

---

## 5. Missing Features — Prioritised

Priority legend:

| Badge | Label | Meaning |
|---|---|---|
| 🔴 **P0** | Critical | Spec non-compliance or breaks interop with go/IPFS |
| 🟠 **P1** | High | Required for production / real-network use |
| 🟡 **P2** | Medium | Robustness and security hardening |
| 🟢 **P3** | Low | Advanced features, optimisations, DX |

---

### 5.1 P0 — Critical / Spec Compliance

These gaps mean py-libp2p cannot interoperate correctly with go-libp2p nodes on the live IPFS network or violates the canonical libp2p Kademlia spec.

---

#### 🔴 P0-1 — PING RPC Message Handler

**Spec ref:** `dht.proto` MessageType 5; used in bucket eviction policy

**Problem:** Without PING, when a k-bucket is full and a new peer is encountered, py-libp2p cannot verify whether the oldest bucket peer is still alive. The spec requires: evict only if the oldest peer does not respond to a PING. py-libp2p evicts based on a staleness timestamp, which is inaccurate.

**Impact:** Routing table churn, premature eviction of live peers, acceptance of less-useful peers.

**Fix outline:**
```python
# kad_dht.py
async def _ping_peer(self, peer_id: ID) -> bool:
    try:
        stream = await self.host.new_stream(peer_id, [KAD_PROTOCOL_ID])
        async with stream:
            msg = dht_pb2.Message(type=dht_pb2.Message.PING)
            await write_pbmsg(stream, msg)
            resp = await read_pbmsg_with_timeout(stream, timeout=10)
            return resp.type == dht_pb2.Message.PING
    except Exception:
        return False

# routing_table.py: KBucket.add_peer() — call _ping_peer on oldest when full
```

---

#### 🔴 P0-2 — Record Selector Functions

**Spec ref:** libp2p kad-dht spec §Record Selection; critical for `/ipns/`

**Problem:** GET_VALUE may return multiple conflicting records from different peers. Without a selector, py-libp2p cannot determine which record is authoritative. For IPNS this means potentially serving an old (lower sequence number) version of a name record.

**Fix outline:**
```python
# records/selector.py
SelectorFunc = Callable[[str, list[bytes]], int]  # returns index of best record

DEFAULT_SELECTORS: dict[str, SelectorFunc] = {
    "pk": lambda key, vals: 0,   # public keys are unique, first valid wins
    "ipns": select_ipns_record,  # pick highest SeqNo
}

# kad_dht.py: in get_value(), after collecting responses:
best_idx = self.selectors[namespace](key, records)
return records[best_idx]
```

---

#### 🔴 P0-3 — Identify-Triggered Routing Table Population

**Spec ref:** go-libp2p-kad-dht design doc; de-facto standard behavior

**Problem:** On a live network, peers are discovered primarily through the libp2p `identify` protocol, not through explicit DHT operations. Without subscribing to identify events, py-libp2p's routing table remains nearly empty until a manual `bootstrap()` call — it will not self-heal as the network changes.

**Fix outline:**
```python
# kad_dht.py
def _setup_identify_listeners(self):
    # Listen to identify protocol events from the host's event bus
    # When a peer's identify response arrives:
    # - Check if peer advertises /ipfs/kad/1.0.0
    # - If yes, try to add to routing table
    self.host.get_network().register_notifee(
        on_connected=self._handle_new_connection
    )

async def _handle_new_connection(self, peer_id: ID):
    # Only add if peer is a DHT server (advertises kad protocol)
    # Respects minRTRefreshThreshold
    ...
```

---

#### 🔴 P0-4 — Provider Record Republishing

**Spec ref:** Original Kademlia paper §2.3; libp2p spec §Provider Records

**Problem:** Provider records are distributed to the k-closest peers and expire after 24 hours (spec-mandated). If the providing node does not re-announce every ~12 hours, records silently disappear. py-libp2p never republishes.

**Fix outline:**
```python
# kad_dht.py: background task
async def _provider_republish_loop(self):
    while True:
        await trio.sleep(PROVIDER_REPUBLISH_INTERVAL)  # 12h
        for cid in self.local_provider_keys:
            await self.provide(cid, broadcast=True)
```

---

### 5.2 P1 — High / Production Readiness

These features are not strictly required for basic spec compliance but are necessary for any real-network deployment.

---

#### 🟠 P1-1 — Routing Table Refresh Manager

**Problem:** py-libp2p refreshes the routing table on a simple fixed interval. This does not account for:
- Buckets that have not been queried recently (per-bucket staleness)
- The mathematical relationship between refresh interval, concurrency, and bucket size

**Fix:** Implement `RTRefreshManager` that tracks `last_successful_outbound_query_at` per bucket and triggers targeted random lookups for stale buckets.

---

#### 🟠 P1-2 — Quorum-Based GET_VALUE

**Problem:** py-libp2p's `get_value` returns the first valid response. go-libp2p waits until `quorum` (default: 1 for key-value, higher for routing records) peers return a consistent value before returning.

**Impact:** Single-peer responses can return stale data. Quorum adds fault tolerance.

**Fix outline:**
```python
async def get_value(self, key: str, quorum: int = 1) -> bytes | None:
    results: list[bytes] = []
    async for record in self._iterative_get(key):
        if record is not None:
            results.append(record)
        if len(results) >= quorum:
            break
    return self.selectors[namespace](key, results) if results else None
```

---

#### 🟠 P1-3 — Datastore-Backed Provider Records

**Problem:** All provider records are lost on restart. For any node intended to serve as a persistent provider (e.g., an IPFS gateway, a GooseSwarm task provider), in-memory storage is insufficient.

**Fix:** Integrate `anyio`-compatible key-value store (e.g., `sqlite3` or `rocksdict`) as a backend for `ValueStore` and a dedicated `ProviderManager`.

---

#### 🟠 P1-4 — AUTO Mode (Reachability-Adaptive CLIENT/SERVER)

**Problem:** Callers must manually set `DHTMode.CLIENT` or `DHTMode.SERVER`. A node behind NAT that incorrectly sets SERVER mode will advertise itself as reachable, causing lookup failures for other nodes trying to contact it.

**Fix:** Subscribe to libp2p's autonat/reachability events. Automatically promote to SERVER when external connectivity is confirmed and demote to CLIENT when behind NAT.

---

#### 🟠 P1-5 — Value Record Republishing

**Problem:** Like provider records, application key-value records also expire and must be republished by the original writer (Kademlia §2.3). py-libp2p does not implement this.

**Fix:** Track locally-originated records and republish every 24h (per spec).

---

#### 🟠 P1-6 — `GetClosestPeers()` Public API

**Problem:** There is no way for callers to retrieve the k-closest peers to an arbitrary key without performing a full `find_node` and manually extracting results. go-libp2p exposes this as a first-class streaming API used widely by IPFS subsystems.

**Fix:**
```python
async def get_closest_peers(
    self, key: str
) -> AsyncIterator[ID]:
    """Stream the k-closest peers to key, in ascending XOR order."""
    ...
```

---

### 5.3 P2 — Medium / Robustness & Security

---

#### 🟡 P2-1 — Peer Diversity Filter (Anti-Eclipse Hardening)

**Problem:** Without IP-group diversity constraints on the routing table, py-libp2p is vulnerable to Eclipse and Sybil attacks where an adversary fills a k-bucket with nodes they control, censoring queries for a key range.

**Fix:** Implement a configurable `max_per_subnet` limit (per-bucket and global) for the `RoutingTable`. Track peer IP prefixes (/24) and enforce limits in `add_peer()`.

**Reference:** `go-libp2p-kbucket/peerdiversity` package.

---

#### 🟡 P2-2 — S/Kademlia Disjoint Lookup Paths

**Problem:** Standard Kademlia iterative lookup is susceptible to routing attacks: a malicious peer in the lookup path can return false results. S/Kademlia's disjoint paths query `d` independent paths to the target, requiring an attacker to control nodes on all paths simultaneously.

**Fix:** Run `d` (default: `bucket_size / 2 = 10`) concurrent lookups with disjoint peer sets and merge results.

---

#### 🟡 P2-3 — Bucket Replacement Cache (Pending Slots)

**Problem:** When a k-bucket is full and a new peer is discovered, the new peer should wait in a replacement cache until a current bucket peer fails a PING (P0-1). Without this cache, valid peers are silently dropped.

**Fix:** Add `pending: list[PeerInfo]` to each `KBucket`. After a failed PING, install the pending peer.

---

#### 🟡 P2-4 — Connection Manager RT Scoring

**Problem:** If the libp2p connection manager prunes connections due to resource pressure, it should protect peers that are important to the DHT routing table (especially those in low-CPL buckets, which are rare and hard to replace). py-libp2p does not tag DHT peers with the connection manager.

**Fix:** After adding a peer to the routing table, set a connection manager tag:
```python
score = BASE_SCORE + cpl_with_local_peer
self.host.get_conn_manager().tag_peer(peer_id, "kbucket", score)
```

---

#### 🟡 P2-5 — minRTRefreshThreshold for RT Admission

**Problem:** On a large network, a new connection alone is insufficient to qualify a peer for the routing table. go-libp2p only adds peers who have either responded to a DHT query or sent one. This prevents routing table pollution.

**Fix:** Track `has_responded` per peer and enforce the threshold in `add_peer()`.

---

### 5.4 P3 — Low / Nice-to-Have & Advanced

---

#### 🟢 P3-1 — OpenTelemetry Tracing

Instrument all public DHT operations (`put_value`, `get_value`, `provide`, `find_providers`, `find_peer`) with OpenTelemetry spans. Use `opentelemetry-api` + `opentelemetry-sdk`. Critical for production debugging and performance profiling.

---

#### 🟢 P3-2 — Prometheus / OpenMetrics Metrics

Expose routing table size, lookup latency histograms, query success/failure rates, provider store size as Prometheus metrics via `prometheus-client`. Essential for monitoring py-libp2p nodes in production.

---

#### 🟢 P3-3 — Network Size Estimator

Estimate the DHT network size from observed k-bucket fill levels. Useful for adaptive configuration and detecting network partitions.

---

#### 🟢 P3-4 — `/pk/` Namespace Support (`GetPublicKey`)

Store and retrieve public keys under `/pk/<peer-id-multihash>`. Required for full IPNS compatibility and for verifying peer identities from the DHT. Implement `GetPublicKey(peer_id)` using the DHT.

---

#### 🟢 P3-5 — `/ipns/` Namespace Support

Add built-in validator and selector for IPNS records (IPNS record protobuf, signature verification against public key, sequence number selection). Currently py-libp2p would need a caller-supplied validator and has no selector.

---

#### 🟢 P3-6 — LookupEvent Streaming

Emit granular `LookupEvent` objects (request sent, response received, peer state change, termination reason) to an optional `trio.MemoryReceiveChannel`. Essential for building DHT debugging tools and performance dashboards.

---

#### 🟢 P3-7 — Functional Options Configuration

Replace constructor keyword-argument configuration with a composable `Option` builder pattern (matching go-libp2p's style). This makes the API more extensible without breaking existing call sites as new options are added.

---

#### 🟢 P3-8 — Cross-Implementation Interop Tests

Add a test suite that spins up a real go-libp2p node (via subprocess or Docker) and verifies:
- py → go: PUT_VALUE, GET_VALUE, ADD_PROVIDER, GET_PROVIDERS, FIND_NODE
- go → py: same set in reverse
- py node appears in go node's routing table and vice versa

This is the most reliable way to catch spec deviations early.

---

#### 🟢 P3-9 — Default IPFS Bootstrap Peers

Ship a `DEFAULT_BOOTSTRAP_PEERS` constant (Amino DHT bootstrap nodes) analogous to go-libp2p's `GetDefaultBootstrapPeerAddrInfos()`. Allows py-libp2p nodes to join the public IPFS network with zero configuration.

---

## 6. Contribution Roadmap

The following phased plan takes py-libp2p's Kademlia DHT from its current experimental state toward full spec compliance and production readiness.

### Phase 1 — Spec Compliance (P0 items, ~4–6 weeks)

1. **PING handler** (P0-1) — ~3 days
2. **Record selector functions** (P0-2) — ~2 days
3. **Identify-triggered RT population** (P0-3) — ~1 week
4. **Provider record republishing** (P0-4) — ~2 days
5. **Value record republishing** (P1-5) — ~2 days (do alongside P0-4)

### Phase 2 — Production Readiness (P1 items, ~4–8 weeks)

6. **Routing table refresh manager** (P1-1) — ~1 week
7. **Quorum-based GET** (P1-2) — ~3 days
8. **Datastore-backed provider records** (P1-3) — ~1 week
9. **AUTO mode** (P1-4) — ~1 week
10. **`GetClosestPeers()` API** (P1-6) — ~2 days
11. **Default bootstrap peers** (P3-9) — ~1 day

### Phase 3 — Security Hardening (P2 items, ~3–4 weeks)

12. **Peer diversity filter** (P2-1) — ~1 week
13. **S/Kademlia disjoint paths** (P2-2) — ~2 weeks
14. **Bucket replacement cache** (P2-3) — ~3 days
15. **Connection manager scoring** (P2-4) — ~2 days
16. **`minRTRefreshThreshold`** (P2-5) — ~2 days

### Phase 4 — Observability & Advanced (P3 items, ~2–4 weeks)

17. **OTel tracing** (P3-1) — ~1 week
18. **Prometheus metrics** (P3-2) — ~1 week
19. **Interop test suite** (P3-8) — ~1 week
20. **`/pk/` + `/ipns/` namespaces** (P3-4, P3-5) — ~1 week

---

## 7. References

| Resource | URL |
|---|---|
| libp2p Kademlia DHT Specification | https://github.com/libp2p/specs/tree/master/kad-dht |
| go-libp2p-kad-dht source | https://github.com/libp2p/go-libp2p-kad-dht |
| go-libp2p-kbucket source | https://github.com/libp2p/go-libp2p-kbucket |
| py-libp2p source | https://github.com/libp2p/py-libp2p |
| py-libp2p KadDHT PR #579 | https://github.com/libp2p/py-libp2p/pull/579 |
| py-libp2p Issue #540 (feature request) | https://github.com/libp2p/py-libp2p/issues/540 |
| Kademlia whitepaper (Maymounkov & Mazières 2002) | https://pdos.csail.mit.edu/~petar/papers/maymounkov-kademlia-lncs.pdf |
| S/Kademlia (Baumgart & Meinert 2007) | https://ieeexplore.ieee.org/document/4447808 |
| go-libp2p-kad-dht Go pkg docs | https://pkg.go.dev/github.com/libp2p/go-libp2p-kad-dht |
| py-libp2p readthedocs (kad_dht module) | https://py-libp2p.readthedocs.io/en/latest/ |

---

*Document prepared: April 2026. Based on py-libp2p ≥ 0.3.0 and go-libp2p-kad-dht master (last commit Apr 13, 2026).*
