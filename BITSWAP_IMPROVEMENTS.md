# py-libp2p Bitswap vs Kubo (go-bitswap): Gap Analysis & Improvement Roadmap

## Table of Contents
1. [Overview](#overview)
2. [Architecture Comparison](#architecture-comparison)
3. [Feature Gap Analysis](#feature-gap-analysis)
4. [Detailed Improvements by Category](#detailed-improvements-by-category)
   - [Session Management](#1-session-management-critical)
   - [Decision Engine](#2-decision-engine-critical)
   - [Provider Discovery](#3-provider-discovery-critical)
   - [Wantlist Management](#4-wantlist-management-high)
   - [Block Store](#5-block-store-high)
   - [Cancellation & Context](#6-cancellation--context-handling-high)
   - [Multi-Peer Fetching](#7-multi-peer-fetching-high)
   - [Chunker & DAG Builder](#8-chunker--dag-builder-medium)
   - [Metrics & Observability](#9-metrics--observability-medium)
   - [Message Handling](#10-message-handling-medium)
   - [Error Handling](#11-error-handling-medium)
   - [Memory Management](#12-memory-management-medium)
5. [Priority Summary Table](#priority-summary-table)
6. [Implementation Roadmap](#implementation-roadmap)

---

## Overview

This document compares py-libp2p's Bitswap implementation against Kubo's production
Bitswap (go-bitswap / boxo), identifies gaps, and proposes concrete improvements.

**py-libp2p Bitswap** is a Python implementation targeting compatibility with IPFS Kubo.
It successfully handles basic block exchange but lacks many of the optimizations that
make Kubo's Bitswap fast, resilient, and production-ready.

**Kubo Bitswap** (now in `ipfs/boxo`) is a battle-tested Go implementation used by
millions of IPFS nodes. It has years of performance tuning, multi-peer coordination,
and sophisticated scheduling built in.

---

## Architecture Comparison

### py-libp2p Bitswap (Current)

```
┌──────────────────────────────────────────────────┐
│                  Application                      │
│               (test_bitswap_ipfs.py)              │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│                  MerkleDag                        │
│  - fetch_file()  - add_file()                     │
│  - Recursive batch-fetch tree                     │
│  - Sequential leaf reassembly                     │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│              BitswapClient (single class)         │
│                                                   │
│  get_block()          get_blocks_batch()          │
│  want_block()         cancel_want()               │
│  _send_wantlist_to_peer()                         │
│  _broadcast_wantlist()                            │
│  _process_message()   _handle_stream()            │
│                                                   │
│  State:                                           │
│    _wantlist          _peer_wantlists             │
│    _pending_requests  _expected_blocks            │
│    _peer_protocols    _dont_have_responses        │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│              MemoryBlockStore                     │
│  (dict[CIDObject, bytes] — no eviction)           │
└──────────────────────┬───────────────────────────┘
                       │
                  libp2p Host
```

### Kubo Bitswap (go-bitswap / boxo)

```
┌──────────────────────────────────────────────────┐
│                  Application                      │
└────────────────┬─────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────┐
│          Bitswap Exchange (top-level API)         │
│  GetBlock()  GetBlocks()  NewSession()            │
│  HasBlock()  NotifyNewBlocks()  Close()           │
└────────────────┬─────────────────────────────────┘
                 │
     ┌───────────┴────────────┐
     │                        │
┌────▼──────────┐   ┌─────────▼──────────┐
│    Client     │   │      Server        │
│               │   │                   │
│ SessionManager│   │  DecisionEngine   │
│ WantManager   │   │  TaskWorkerPool   │
│ PeerManager   │   │  BlockPresence    │
│               │   │  Ledger (per peer)│
└────┬──────────┘   └─────────┬──────────┘
     │                        │
     └───────────┬────────────┘
                 │
┌────────────────▼─────────────────────────────────┐
│              Bitswap Network Layer                │
│  MessageSender  MessageReceiver                   │
│  ConnEventManager  ProviderQueryManager           │
└────────────────┬─────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────┐
│          Blockstore (GCBlockstore)                │
│  LRU Cache  Bloom Filter  Disk Persistence       │
└──────────────────────────────────────────────────┘
```

---

## Feature Gap Analysis

| Feature | py-libp2p | Kubo | Gap |
|---------|-----------|------|-----|
| **Basic block exchange** | ✅ | ✅ | None |
| **Protocol v1.0.0 / v1.1.0 / v1.2.0** | ✅ | ✅ | None |
| **Batch wantlist (multi-CID per message)** | ✅ | ✅ | None |
| **DontHave responses (v1.2.0)** | ✅ Partial | ✅ Full | Partial |
| **Cancel messages** | ✅ | ✅ | None |
| **Directory wrapper parsing** | ✅ | ✅ | None |
| **Session management** | ❌ | ✅ Full | **CRITICAL** |
| **Decision engine** | ❌ | ✅ Full | **CRITICAL** |
| **Provider search / DHT integration** | ❌ | ✅ Full | **CRITICAL** |
| **Multi-peer parallel fetching** | ❌ | ✅ Full | **HIGH** |
| **Peer scoring / selection** | ❌ | ✅ Full | **HIGH** |
| **Adaptive batch sizing** | ❌ | ✅ | **HIGH** |
| **Concurrent block fetching (async)** | ❌ | ✅ | **HIGH** |
| **Disk-backed block store** | ❌ | ✅ | **HIGH** |
| **Block store LRU eviction** | ❌ | ✅ | **HIGH** |
| **Bloom filter for local CID lookup** | ❌ | ✅ | **MEDIUM** |
| **Metrics / Prometheus** | ❌ | ✅ Full | **MEDIUM** |
| **Broadcast control** | ❌ | ✅ | **MEDIUM** |
| **WantHave vs WantBlock optimization** | ❌ | ✅ | **MEDIUM** |
| **HTTP retrieval fallback** | ❌ | ✅ | **MEDIUM** |
| **Streaming file reassembly** | ❌ | ✅ | **MEDIUM** |
| **HAMT directory sharding** | ❌ | ✅ | **MEDIUM** |
| **CIDv1 as default** | ❌ (CIDv0) | ✅ (CIDv1) | **LOW** |
| **Context-based cancellation** | ❌ | ✅ | **HIGH** |
| **Ledger per peer (fairness)** | ❌ | ✅ | **MEDIUM** |
| **Task priority queue** | ❌ | ✅ | **MEDIUM** |

---

## Detailed Improvements by Category

---

### 1. Session Management (CRITICAL)

#### Current State in py-libp2p

There is **no session concept**. Every `get_block()` or `get_blocks_batch()` call is
completely independent. The client has no memory of which peers previously served
which blocks.

```python
# Current: no session — each call is independent
block1 = await bitswap.get_block(cid1, peer_id=None)  # broadcasts to all
block2 = await bitswap.get_block(cid2, peer_id=None)  # broadcasts to all again
```

#### How Kubo Does It

Kubo's `SessionManager` groups related block requests into a **Session**. A session:
- Remembers which peers provided blocks in the past
- Preferentially requests from peers that have proven reliable
- Tracks latency per peer and routes future requests accordingly
- Implements **optimistic session peer discovery** — sends want-have to a small set,
  then expands if needed

```go
// Kubo: session groups related requests
session := exchange.NewSession(ctx)
blocks, _ := session.GetBlocks(ctx, []cid.Cid{cid1, cid2, cid3})
// Session automatically routes to the best peer based on history
```

#### Proposed Improvement

```python
class BitswapSession:
    """
    Groups related block requests for optimized multi-block fetching.
    Tracks which peers provided blocks and prefers them for future requests.
    """
    def __init__(self, client: BitswapClient):
        self._client = client
        self._peer_latencies: dict[PeerID, float] = {}   # peer -> avg latency ms
        self._peer_hit_count: dict[PeerID, int] = {}      # peer -> blocks served
        self._preferred_peers: list[PeerID] = []          # sorted by score
        self._session_id = uuid4()

    async def get_blocks(self, cids: list[CIDInput]) -> AsyncIterator[tuple[bytes, bytes]]:
        """Fetch blocks, routing to best peers based on session history."""
        # Sort peers by score (latency + hit rate)
        peers = self._rank_peers()
        # Send want-have to top peers first, fall back to broadcast
        ...

    def _rank_peers(self) -> list[PeerID]:
        """Score peers: higher hit count + lower latency = higher rank."""
        ...

    def record_response(self, peer_id: PeerID, cid: bytes, latency_ms: float):
        """Update peer stats after receiving a block."""
        ...
```

**Impact**: 30-50% reduction in redundant network requests for multi-block downloads.

---

### 2. Decision Engine (CRITICAL)

#### Current State in py-libp2p

The server side of Bitswap (responding to peers who want our blocks) is **extremely
simple**: when a peer sends a wantlist, the code checks if the block is in the store
and immediately sends it. There is no prioritization, rate limiting, or fairness.

```python
# Current: naive — send block immediately to anyone who asks
if has_block:
    data = await self.block_store.get_block(entry_cid)
    blocks_to_send.append(data)  # No priority, no rate limiting
```

#### How Kubo Does It

Kubo has a full **Decision Engine** with:
- **Per-peer ledger**: tracks bytes sent/received per peer (debt ratio)
- **Task priority queue**: orders outgoing blocks by peer debt ratio + request priority
- **Task worker pool**: configurable number of goroutines sending blocks concurrently
- **WantHave-replace optimization**: if a peer wants a block ≤ 1024 bytes, just send
  the block instead of a Have response (avoids an extra round-trip)
- **Max outstanding bytes per peer**: prevents one peer from consuming all bandwidth

```go
// Kubo Decision Engine pseudocode
func (e *Engine) taskWorker() {
    for task := range e.workQueue {
        peer := task.Target
        ledger := e.ledgerMap[peer]
        
        // Only send if debt ratio is acceptable
        if ledger.debtRatio() > maxDebtRatio {
            continue  // Skip greedy peers
        }
        
        // Send block with rate limiting
        e.sendBlock(peer, task.Entries)
    }
}
```

#### Proposed Improvement

```python
@dataclass
class PeerLedger:
    """Tracks fairness accounting per peer."""
    bytes_sent: int = 0
    bytes_received: int = 0

    def debt_ratio(self) -> float:
        if self.bytes_received == 0:
            return 1.0
        return self.bytes_sent / self.bytes_received

class DecisionEngine:
    """
    Prioritizes outgoing block responses based on peer fairness.
    Implements a task queue with per-peer debt tracking.
    """
    def __init__(self, block_store: BlockStore, max_outstanding_bytes: int = 8 * 1024 * 1024):
        self._ledgers: dict[PeerID, PeerLedger] = {}
        self._task_queue: list[tuple[float, PeerID, bytes]] = []  # (priority, peer, cid)
        self._max_outstanding = max_outstanding_bytes

    async def queue_block_for_peer(self, peer_id: PeerID, cid: bytes, priority: int):
        """Add a block send task, scored by peer debt ratio."""
        ledger = self._ledgers.setdefault(peer_id, PeerLedger())
        score = priority / (1 + ledger.debt_ratio())
        heapq.heappush(self._task_queue, (-score, peer_id, cid))

    async def process_tasks(self):
        """Worker loop: drain the task queue and send blocks."""
        while self._task_queue:
            _, peer_id, cid = heapq.heappop(self._task_queue)
            data = await self._block_store.get_block(parse_cid(cid))
            if data:
                await self._send_block(peer_id, cid, data)
                self._ledgers[peer_id].bytes_sent += len(data)
```

**Impact**: Prevents free-riding peers, improves fairness in multi-peer scenarios.

---

### 3. Provider Discovery (CRITICAL)

#### Current State in py-libp2p

There is **no provider discovery**. The caller must manually specify a `peer_id` or
rely on already-connected peers. If a block isn't available from connected peers,
the request simply times out.

```python
# Current: must know the peer in advance
data = await dag.fetch_file(cid, peer_id=known_peer)  # fails if peer_id is wrong
# or
data = await dag.fetch_file(cid)  # broadcasts to connected peers only
```

#### How Kubo Does It

Kubo uses a **ProviderQueryManager** that integrates with the DHT (Kademlia):
1. Sends `want-have` to connected peers first (fast path)
2. If no response within `ProviderSearchDelay` (default 1 second), queries DHT
3. DHT returns provider records — peers who have announced they have the content
4. Opens connections to those providers and requests blocks
5. Continues searching while downloading (parallel provider search + fetch)

```go
// Kubo: automatic provider discovery
block, err := exchange.GetBlock(ctx, cid)
// Internally: tries connected peers → DHT search → connect to providers
```

#### Proposed Improvement

```python
class ProviderQueryManager:
    """
    Discovers content providers via DHT when connected peers don't have a block.
    """
    def __init__(self, host: IHost, dht_routing: IRouting):
        self._host = host
        self._dht = dht_routing
        self._provider_search_delay = 1.0  # seconds before DHT search

    async def find_providers(self, cid: bytes, max_providers: int = 20) -> list[PeerID]:
        """Search DHT for peers who have this CID."""
        async for provider_info in self._dht.find_providers(cid, max_providers):
            yield provider_info.peer_id

    async def get_block_with_discovery(
        self,
        client: BitswapClient,
        cid: bytes,
        timeout: float = 30.0,
    ) -> bytes:
        """Fetch block, falling back to DHT discovery if needed."""
        # Try connected peers first
        try:
            with trio.fail_after(self._provider_search_delay):
                return await client.get_block(cid, timeout=self._provider_search_delay)
        except trio.TooSlowError:
            pass

        # Fall back to DHT discovery
        async for provider_id in self.find_providers(cid):
            await self._host.connect(provider_id)
            try:
                return await client.get_block(cid, peer_id=provider_id, timeout=timeout)
            except Exception:
                continue

        raise BlockNotFoundError(f"No providers found for {format_cid_for_display(cid)}")
```

**Impact**: Enables fetching content from the full IPFS network, not just pre-known peers.

---

### 4. Wantlist Management (HIGH)

#### Current State in py-libp2p

The wantlist is a flat `dict[CIDObject, dict]`. There is no per-peer wantlist
differentiation for outgoing requests. All CIDs are broadcast to all peers or
sent to a single specified peer. There is no **WantHave vs WantBlock** optimization.

```python
# Current: single global wantlist, no per-peer optimization
self._wantlist: dict[CIDObject, dict] = {}
# All CIDs sent as WantBlock — no WantHave pre-check
```

#### How Kubo Does It

Kubo's `WantManager` maintains:
- **Per-peer wantlists**: different peers may receive different subsets
- **WantHave first, WantBlock second**: sends `want-have` to discover which peer has
  the block, then sends `want-block` only to the peer that responds with `have`
- **Broadcast control**: configurable limit on how many peers receive wantlist broadcasts
- **Full vs incremental wantlists**: sends full wantlist on new peer connection,
  incremental updates thereafter

```
Kubo WantHave optimization:
  1. Send want-have(CID) to N peers
  2. Receive have(CID) from peer A
  3. Send want-block(CID) to peer A only
  4. Receive block from peer A
  → Avoids sending large blocks from multiple peers simultaneously
```

#### Proposed Improvement

```python
class WantManager:
    """
    Manages per-peer wantlists with WantHave/WantBlock optimization.
    """
    WANT_HAVE = 1    # Just check if peer has it
    WANT_BLOCK = 0   # Request the full block

    def __init__(self, client: BitswapClient):
        self._client = client
        self._pending_have: dict[bytes, set[PeerID]] = {}  # cid -> peers queried
        self._have_responses: dict[bytes, PeerID] = {}     # cid -> peer that has it

    async def get_block_optimized(self, cid: bytes, peers: list[PeerID]) -> bytes:
        """
        Two-phase fetch:
        1. Send want-have to multiple peers
        2. Send want-block only to peer that responds with 'have'
        """
        # Phase 1: want-have to top N peers
        top_peers = peers[:5]
        for peer in top_peers:
            await self._client.want_block(cid, want_type=self.WANT_HAVE,
                                           send_dont_have=True)
            await self._client._send_wantlist_to_peer(peer, [parse_cid(cid)])

        # Phase 2: wait for 'have' response, then want-block from that peer
        responding_peer = await self._wait_for_have(cid, timeout=2.0)
        if responding_peer:
            return await self._client.get_block(cid, peer_id=responding_peer)

        # Fallback: want-block broadcast
        return await self._client.get_block(cid)

    async def _wait_for_have(self, cid: bytes, timeout: float) -> PeerID | None:
        """Wait for a 'have' response from any peer."""
        ...
```

**Impact**: Reduces duplicate block transfers; critical for high-throughput scenarios.

---

### 5. Block Store (HIGH)

#### Current State in py-libp2p

Only `MemoryBlockStore` exists — a plain Python dict. It:
- Has **no size limit** (unbounded memory growth)
- Has **no eviction policy** (LRU, LFU, etc.)
- Has **no persistence** (lost on restart)
- Has **no bloom filter** for fast "do I have this?" checks

```python
class MemoryBlockStore(BlockStore):
    def __init__(self) -> None:
        self._blocks: dict[CIDObject, bytes] = {}  # grows forever
```

#### How Kubo Does It

Kubo uses a **GCBlockstore** with:
- **Disk persistence** (badger or flatfs backend)
- **LRU in-memory cache** (configurable size, default 256 MiB)
- **Bloom filter** for fast negative lookups (is this CID definitely not local?)
- **Garbage collection** to reclaim space for unpinned blocks
- **Pinning API** to prevent important blocks from being GC'd

#### Proposed Improvements

```python
class LRUBlockStore(BlockStore):
    """
    In-memory block store with LRU eviction.
    Prevents unbounded memory growth for long-running nodes.
    """
    def __init__(self, max_size_bytes: int = 256 * 1024 * 1024):  # 256 MiB
        self._cache: OrderedDict[CIDObject, bytes] = OrderedDict()
        self._current_size = 0
        self._max_size = max_size_bytes

    async def put_block(self, cid: CIDInput, data: bytes) -> None:
        cid_obj = parse_cid(cid)
        # Evict oldest entries if over limit
        while self._current_size + len(data) > self._max_size and self._cache:
            oldest_cid, oldest_data = self._cache.popitem(last=False)
            self._current_size -= len(oldest_data)
        self._cache[cid_obj] = data
        self._cache.move_to_end(cid_obj)
        self._current_size += len(data)

    async def get_block(self, cid: CIDInput) -> bytes | None:
        cid_obj = parse_cid(cid)
        if cid_obj in self._cache:
            self._cache.move_to_end(cid_obj)  # Mark as recently used
            return self._cache[cid_obj]
        return None


class DiskBlockStore(BlockStore):
    """
    Disk-backed block store for persistent storage across restarts.
    Uses content-addressed file layout: blocks/XX/YYYYYY (first 2 hex chars = dir).
    """
    def __init__(self, root_path: str):
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)

    def _block_path(self, cid_hex: str) -> Path:
        return self._root / cid_hex[:2] / cid_hex[2:]

    async def put_block(self, cid: CIDInput, data: bytes) -> None:
        cid_hex = parse_cid(cid).buffer.hex()
        path = self._block_path(cid_hex)
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)

    async def get_block(self, cid: CIDInput) -> bytes | None:
        cid_hex = parse_cid(cid).buffer.hex()
        path = self._block_path(cid_hex)
        return path.read_bytes() if path.exists() else None
```

**Impact**: Prevents OOM crashes for large downloads; enables persistent caching.

---

### 6. Cancellation & Context Handling (HIGH)

#### Current State in py-libp2p

There is **no proper cancellation**. Once a batch fetch starts, it runs to completion
or timeout. There is no way to cancel an in-progress download cleanly.

```python
# Current: no cancellation support
await dag.fetch_file(cid, timeout=120.0)
# If caller wants to cancel, they must cancel the entire nursery
```

#### How Kubo Does It

Kubo uses Go's `context.Context` for cancellation at every level:
- `GetBlock(ctx, cid)` — cancel individual block request
- `GetBlocks(ctx, cids)` — cancel entire batch
- Context propagates through all layers (session, network, store)
- Cancellation immediately stops all in-flight requests for that context

#### Proposed Improvement

```python
# Use trio's CancelScope for structured cancellation
async def fetch_file_cancellable(
    self,
    root_cid: CIDInput,
    cancel_scope: trio.CancelScope | None = None,
    timeout: float = 120.0,
) -> tuple[bytes, str | None]:
    """Fetch file with cancellation support via trio CancelScope."""
    scope = cancel_scope or trio.CancelScope()
    with scope:
        return await self._fetch_file_impl(root_cid, timeout=timeout)

# Usage
async with trio.open_nursery() as nursery:
    cancel_scope = trio.CancelScope()
    nursery.start_soon(dag.fetch_file_cancellable, cid, cancel_scope)

    # Cancel after 30 seconds or on user request
    await trio.sleep(30)
    cancel_scope.cancel()  # Cleanly cancels the download
```

**Impact**: Essential for production use — allows clean shutdown and user-driven cancellation.

---

### 7. Multi-Peer Fetching (HIGH)

#### Current State in py-libp2p

All blocks are fetched from a **single peer** (either specified or the first connected
peer). There is no parallelism across peers, and no fallback if a peer fails mid-download.

```python
# Current: single peer, sequential batches
block_map = await self.bitswap.get_blocks_batch(
    ordered_leaf_cids, peer_id=peer_id,  # single peer!
    batch_size=32
)
```

#### How Kubo Does It

Kubo's session manager:
- Discovers multiple providers via DHT
- Splits the wantlist across multiple peers simultaneously
- Tracks which peer is fastest (latency tracking)
- Automatically retries from a different peer if one fails
- Uses a "split-brain" strategy: sends want-have to many, want-block to the best

```
Kubo multi-peer download:
  Peer A  ←── want-block(CID_1, CID_2, CID_3)
  Peer B  ←── want-block(CID_4, CID_5, CID_6)
  Peer C  ←── want-block(CID_7, CID_8, CID_9)
  → All fetched in parallel, 3x throughput
```

#### Proposed Improvement

```python
async def get_blocks_multi_peer(
    self,
    cids: list[bytes],
    peers: list[PeerID],
    timeout: float = 60.0,
    batch_size: int = 32,
) -> dict[bytes, bytes]:
    """
    Fetch blocks from multiple peers in parallel.
    Splits CIDs across peers and races responses.
    """
    if not peers:
        return await self.get_blocks_batch(cids, timeout=timeout, batch_size=batch_size)

    results: dict[bytes, bytes] = {}
    # Distribute CIDs across available peers
    peer_assignments: dict[PeerID, list[bytes]] = {p: [] for p in peers}
    for i, cid in enumerate(cids):
        peer_assignments[peers[i % len(peers)]].append(cid)

    # Fetch from all peers concurrently
    async with trio.open_nursery() as nursery:
        for peer_id, peer_cids in peer_assignments.items():
            if peer_cids:
                nursery.start_soon(
                    self._fetch_from_peer_into,
                    peer_cids, peer_id, timeout, batch_size, results
                )

    return results

async def _fetch_from_peer_into(
    self,
    cids: list[bytes],
    peer_id: PeerID,
    timeout: float,
    batch_size: int,
    results: dict[bytes, bytes],
) -> None:
    """Fetch blocks from a specific peer and merge into shared results dict."""
    peer_results = await self.get_blocks_batch(
        cids, peer_id=peer_id, timeout=timeout, batch_size=batch_size
    )
    results.update(peer_results)
```

**Impact**: Near-linear throughput scaling with number of available peers.

---

### 8. Chunker & DAG Builder (MEDIUM)

#### Current State in py-libp2p

The chunker uses a **fixed chunk size of 63 KB** for all files. This is a hard limit
imposed by py-libp2p's stream size. Kubo uses 256 KB chunks by default.

```python
# Current: fixed 63 KB limit
DEFAULT_CHUNK_SIZE = 63 * 1024  # py-libp2p stream limit
```

The DAG builder creates a **flat tree** (root → all chunks directly). Kubo creates
a **balanced tree** (root → intermediate nodes → chunks) for files > ~174 chunks.

```
py-libp2p DAG (flat):           Kubo DAG (balanced):
Root                            Root
├─ Chunk 1                      ├─ Intermediate 1
├─ Chunk 2                      │  ├─ Chunk 1
├─ Chunk 3                      │  ├─ Chunk 2
└─ Chunk N (any size)           │  └─ ... (174 chunks)
                                ├─ Intermediate 2
                                │  └─ ...
                                └─ Intermediate N
```

#### Proposed Improvements

```python
# 1. Support larger chunk sizes (requires fixing stream size limit)
DEFAULT_CHUNK_SIZE = 256 * 1024  # 256 KB — Kubo default

# 2. Balanced tree builder for large files
MAX_LINKS_PER_NODE = 174  # Kubo's default

def build_balanced_dag(chunks: list[tuple[bytes, int]]) -> bytes:
    """
    Build a balanced Merkle DAG tree like Kubo does for large files.
    Creates intermediate nodes when chunk count exceeds MAX_LINKS_PER_NODE.
    """
    if len(chunks) <= MAX_LINKS_PER_NODE:
        # Small file: flat tree
        return create_file_node(chunks)

    # Large file: create intermediate nodes
    intermediate_nodes = []
    for i in range(0, len(chunks), MAX_LINKS_PER_NODE):
        batch = chunks[i:i + MAX_LINKS_PER_NODE]
        node_data = create_file_node(batch)
        node_cid = compute_cid_v1(node_data, codec=CODEC_DAG_PB)
        node_size = sum(size for _, size in batch)
        intermediate_nodes.append((node_cid, node_size))

    # Recurse if needed
    return build_balanced_dag(intermediate_nodes)

# 3. Rabin fingerprint chunker (content-defined chunking)
# Kubo's default is fixed-size, but supports Rabin for deduplication
class RabinChunker:
    """
    Content-defined chunking using Rabin fingerprints.
    Produces chunk boundaries based on content, enabling better deduplication
    across similar files (e.g., video files with small edits).
    """
    def __init__(self, min_size=256*1024, avg_size=1024*1024, max_size=4*1024*1024):
        self.min_size = min_size
        self.avg_size = avg_size
        self.max_size = max_size
    ...
```

**Impact**: Compatible DAG structure with Kubo; better deduplication for similar files.

---

### 9. Metrics & Observability (MEDIUM)

#### Current State in py-libp2p

There are **no metrics**. The only observability is through Python's `logging` module
with `[DAG]` and `[FETCH]` prefixed print statements added for debugging.

#### How Kubo Does It

Kubo exposes Prometheus metrics for:
- `bitswap_requests_total` — total block requests
- `bitswap_received_blocks_total` — blocks received from network
- `bitswap_sent_blocks_total` — blocks sent to peers
- `bitswap_dont_have_total` — DontHave responses received
- `bitswap_pending_requests` — current queue depth
- `bitswap_active_sessions` — open sessions
- `bitswap_peer_latency_ms` — per-peer latency histogram

#### Proposed Improvement

```python
from dataclasses import dataclass, field
from collections import defaultdict
import time

@dataclass
class BitswapMetrics:
    """Lightweight metrics collector for Bitswap operations."""
    blocks_requested: int = 0
    blocks_received: int = 0
    blocks_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    dont_have_received: int = 0
    timeouts: int = 0
    peer_latencies: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def record_block_received(self, peer_id: str, size: int, latency_ms: float):
        self.blocks_received += 1
        self.bytes_received += size
        self.peer_latencies[peer_id].append(latency_ms)

    def avg_latency(self, peer_id: str) -> float:
        lats = self.peer_latencies.get(peer_id, [])
        return sum(lats) / len(lats) if lats else 0.0

    def summary(self) -> dict:
        return {
            "blocks_requested": self.blocks_requested,
            "blocks_received": self.blocks_received,
            "bytes_received": self.bytes_received,
            "timeouts": self.timeouts,
            "dont_have": self.dont_have_received,
        }
```

**Impact**: Essential for debugging, performance tuning, and production monitoring.

---

### 10. Message Handling (MEDIUM)

#### Current State in py-libp2p

The `_process_blocks_v100()` method has **O(N²) complexity**: for each received
block, it iterates over all expected CIDs to find a match via `verify_cid()`.
For large batches (462 blocks), this means ~213,000 CID verifications.

```python
# Current: O(N * M) where N=received blocks, M=expected CIDs
for block_data in blocks:
    for cid in expected_cids:           # O(M) per block
        if verify_cid(cid, block_data): # expensive SHA-256 per check
            matched_cid = cid
            break
```

#### Proposed Improvement

```python
# Build a hash-to-CID index once, then O(1) lookup per block
async def _process_blocks_v100_optimized(self, blocks: list[bytes], peer_id: PeerID):
    """O(N) block processing using hash index instead of O(N²) linear scan."""

    # Build index: sha256(data) -> CID (built once per batch)
    expected_cids = self._expected_blocks.get(peer_id, set()).copy()
    hash_to_cid: dict[bytes, CIDObject] = {}
    for cid_obj in expected_cids:
        # Pre-compute expected hash from CID's multihash
        mh = cid_obj.multihash.digest  # Extract digest from multihash
        hash_to_cid[mh] = cid_obj

    for block_data in blocks:
        block_hash = hashlib.sha256(block_data).digest()
        matched_cid = hash_to_cid.get(block_hash)  # O(1) lookup
        if matched_cid:
            await self.block_store.put_block(matched_cid, block_data)
            self._pending_requests.get(matched_cid, _noop_event).set()
```

**Impact**: Reduces CPU usage by ~99% for large batch processing (O(N²) → O(N)).

---

### 11. Error Handling (MEDIUM)

#### Current State in py-libp2p

Errors are mostly swallowed or logged. There is no **retry logic**, no **partial
failure handling**, and no distinction between transient and permanent errors.

```python
# Current: single timeout, no retry
try:
    with trio.fail_after(timeout):
        await self._pending_requests[cid].wait()
except trio.TooSlowError:
    raise BitswapTimeoutError(...)  # No retry
```

#### Proposed Improvement

```python
async def get_block_with_retry(
    self,
    cid: CIDInput,
    peer_id: PeerID | None = None,
    timeout: float = 30.0,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
) -> bytes:
    """
    Fetch block with exponential backoff retry.
    Retries with a different peer on each attempt if available.
    """
    last_error = None
    peers = self._get_candidate_peers(peer_id)

    for attempt in range(max_retries):
        try_peer = peers[attempt % len(peers)] if peers else peer_id
        try:
            return await self.get_block(cid, peer_id=try_peer, timeout=timeout)
        except (BitswapTimeoutError, BlockNotFoundError) as e:
            last_error = e
            wait_time = backoff_factor ** attempt
            logger.warning(f"Attempt {attempt+1}/{max_retries} failed: {e}. "
                          f"Retrying in {wait_time:.1f}s...")
            await trio.sleep(wait_time)

    raise last_error or BlockNotFoundError(f"Block not found after {max_retries} retries")
```

**Impact**: Resilience against transient network failures; essential for production.

---

### 12. Memory Management (MEDIUM)

#### Current State in py-libp2p

When fetching large files, all blocks are accumulated in memory:

```python
# In dag.py: all blocks held in memory simultaneously
all_blocks_map: dict[bytes, bytes] = {}  # All 465 blocks (115 MB) in RAM
file_data = b""                          # Another 115 MB copy during reassembly
# Peak memory: ~230 MB for a 115 MB file!
```

#### Proposed Improvement

```python
async def fetch_file_streaming(
    self,
    root_cid: CIDInput,
    output_path: str,
    peer_id: PeerID | None = None,
    timeout: float = 120.0,
) -> int:
    """
    Fetch file and write directly to disk, avoiding full in-memory assembly.
    Memory usage: O(batch_size) instead of O(file_size).
    """
    # Step 1: Collect leaf CIDs (still needs intermediate nodes in memory)
    leaf_cids = await self._collect_leaf_cids(root_cid, peer_id, timeout)

    # Step 2: Stream blocks to disk in order
    bytes_written = 0
    with open(output_path, "wb") as f:
        # Fetch and write in batches — only batch_size blocks in RAM at once
        for batch_start in range(0, len(leaf_cids), 32):
            batch = leaf_cids[batch_start:batch_start + 32]
            batch_blocks = await self.bitswap.get_blocks_batch(
                batch, peer_id=peer_id, timeout=timeout, batch_size=32
            )
            for leaf_cid in batch:
                block_data = batch_blocks.get(leaf_cid, b"")
                chunk = self._extract_chunk_data(block_data)
                f.write(chunk)
                bytes_written += len(chunk)

    return bytes_written
```

**Impact**: Enables downloading files larger than available RAM; critical for large media files.

---

## Priority Summary Table

| # | Improvement | Priority | Effort | Impact |
|---|-------------|----------|--------|--------|
| 1 | **Session Management** | 🔴 Critical | High | Huge — 30-50% fewer requests |
| 2 | **Decision Engine** | 🔴 Critical | High | Huge — fairness + serving |
| 3 | **Provider Discovery (DHT)** | 🔴 Critical | High | Huge — enables open network |
| 4 | **Multi-Peer Parallel Fetching** | 🟠 High | Medium | Large — N× throughput |
| 5 | **Context/Cancellation** | 🟠 High | Medium | Large — production essential |
| 6 | **LRU Block Store** | 🟠 High | Low | Large — prevents OOM |
| 7 | **WantHave/WantBlock Optimization** | 🟠 High | Medium | Large — reduces bandwidth |
| 8 | **O(N) Block Matching (v1.0.0)** | 🟠 High | Low | Large — CPU reduction |
| 9 | **Streaming File Write** | 🟠 High | Low | Large — RAM reduction |
| 10 | **Retry with Backoff** | 🟡 Medium | Low | Medium — resilience |
| 11 | **Balanced DAG Builder** | 🟡 Medium | Medium | Medium — Kubo compatibility |
| 12 | **Metrics / Observability** | 🟡 Medium | Low | Medium — debugging |
| 13 | **Disk Block Store** | 🟡 Medium | Medium | Medium — persistence |
| 14 | **Broadcast Control** | 🟡 Medium | Medium | Medium — network load |
| 15 | **HAMT Directory Sharding** | 🟡 Medium | High | Medium — large dirs |
| 16 | **Rabin Chunker** | 🟢 Low | High | Low — deduplication |
| 17 | **HTTP Retrieval Fallback** | 🟢 Low | High | Low — compatibility |
| 18 | **CIDv1 as Default** | 🟢 Low | Low | Low — modernization |

---

## Implementation Roadmap

### Phase 1: Stability & Correctness (Weeks 1-2)

Focus on things that are broken or cause failures in current use:

1. **O(N) block matching** in `_process_blocks_v100()` — simple fix, big CPU win
2. **LRU eviction** in `MemoryBlockStore` — prevents OOM for long-running nodes
3. **Retry with backoff** in `get_block()` — resilience for transient failures
4. **Context/cancellation** — trio `CancelScope` propagation through all layers
5. **Streaming file write** in `dag.py` — reduce peak memory from 2× to 1×

### Phase 2: Performance (Weeks 3-6)

Improve throughput and efficiency:

6. **WantHave/WantBlock optimization** in `WantManager` — reduce duplicate transfers
7. **Multi-peer parallel fetching** — split wantlist across peers
8. **Adaptive batch sizing** — tune batch_size based on peer latency/throughput
9. **Session management** — track peer performance, prefer fast peers
10. **Metrics** — add `BitswapMetrics` class, expose via `/metrics` endpoint

### Phase 3: Production Features (Weeks 7-12)

Features needed for a fully functional IPFS node:

11. **Provider discovery** — integrate with DHT/Kademlia routing
12. **Decision engine** — per-peer ledger, task priority queue
13. **Disk block store** — persistent storage with content-addressed layout
14. **Balanced DAG builder** — match Kubo's tree structure for full compatibility
15. **Broadcast control** — limit wantlist broadcast to N peers

### Phase 4: Advanced (Future)

16. HAMT directory sharding for large directories
17. Rabin fingerprint chunker for content-defined chunking
18. HTTP retrieval fallback (Kubo's new feature)
19. CIDv1 as default for new content

---

## Quick Wins (Can Be Done Today)

The following improvements require minimal code changes but have significant impact:

### 1. Fix O(N²) Block Matching

**File**: `libp2p/bitswap/client.py`, method `_process_blocks_v100()`

Build a hash-to-CID index before the loop instead of calling `verify_cid()` for
every (block, CID) pair.

### 2. Add LRU Eviction to MemoryBlockStore

**File**: `libp2p/bitswap/block_store.py`

Add `max_size_bytes` parameter and evict oldest blocks when limit is exceeded.

### 3. Reduce Peak Memory in fetch_file

**File**: `libp2p/bitswap/dag.py`

Process leaf blocks in batches and write to disk incrementally instead of
accumulating all blocks and then all file data simultaneously.

### 4. Add Metrics Counters

**File**: `libp2p/bitswap/client.py`

Add a `BitswapMetrics` dataclass to `BitswapClient.__init__()` and increment
counters in `get_block()`, `_process_blocks_v100()`, etc.

### 5. Remove Debug Print Statements

**File**: `libp2p/bitswap/dag.py`

Replace `print(f"[FETCH] ...")` calls with proper `logger.info(...)` calls.

---

## Conclusion

py-libp2p's Bitswap is a **working foundation** that successfully exchanges blocks
with Kubo. The core protocol (wantlist, blocks, cancels, v1.0.0–v1.2.0) is correctly
implemented.

The **critical gaps** vs Kubo are architectural:
1. **No session management** — every request is stateless
2. **No decision engine** — serving blocks is naive and unfair
3. **No provider discovery** — can only talk to pre-known peers

The **high-priority gaps** are operational:
4. **No multi-peer parallelism** — single-peer bottleneck
5. **No cancellation** — can't stop in-progress downloads
6. **No memory management** — OOM risk for large files

Addressing Phase 1 and Phase 2 improvements would bring py-libp2p's Bitswap
significantly closer to production-grade quality, making it suitable for use in
real IPFS applications beyond simple file downloads.

---

**Document Version**: 1.0  
**Date**: April 14, 2026  
**Based on**: py-libp2p Bitswap (this repo) vs Kubo/boxo Bitswap (github.com/ipfs/boxo)
