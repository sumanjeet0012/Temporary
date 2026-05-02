# Integration Plan: Porting py-ipfs-lite Features into py-libp2p

> All code excerpts in this document are taken **directly from your local files** at
> `/Users/sumanjeet/code/bitswap/py-libp2p/libp2p/bitswap/`.

---

## Table of Contents

1. [UnixFSFile instead of MerkleDag](#1-unixfsfile-instead-of-merkledag)
2. [Balanced DAG Layout](#2-balanced-dag-layout)
3. [io.IOBase Input Support](#3-ioiobase-input-support)
4. [BlockService — Transparent Local→Network Fallback](#4-blockservice--transparent-localnetwork-fallback)
5. [FilesystemBlockStore — Persistent Storage](#5-filesystemblockstore--persistent-storage)
6. [Canonical DAG-PB Encoding](#6-canonical-dag-pb-encoding)
7. [Wantlist / Message Dataclasses](#7-wantlist--message-dataclasses)
8. [Summary of All Changes](#8-summary-of-all-changes)

---

## 1. UnixFSFile instead of MerkleDag

### Current State in your local `dag.py`

In `add_file()`, every leaf chunk is stored as a **`CODEC_RAW` block**:

```python
# libp2p/bitswap/dag.py  (your local file, ~line 220)
for i, chunk_data in enumerate(chunk_file(file_path, chunk_size)):
    chunk_cid = compute_cid_v1(chunk_data, codec=CODEC_RAW)   # ← RAW codec
    await self.bitswap.add_block(chunk_cid, chunk_data)
    chunks_data.append((chunk_cid, len(chunk_data)))
```

Same pattern in `add_bytes()`:

```python
# libp2p/bitswap/dag.py  (your local file, ~line 380)
for i, chunk_data in enumerate(chunks):
    chunk_cid = compute_cid_v1(chunk_data, codec=CODEC_RAW)   # ← RAW codec
    await self.bitswap.add_block(chunk_cid, chunk_data)
    chunks_data.append((chunk_cid, len(chunk_data)))
```

And for small files (single block):

```python
# libp2p/bitswap/dag.py  (your local file, ~line 168)
if file_size <= chunk_size:
    cid = compute_cid_v1(data, codec=CODEC_RAW)   # ← RAW codec
    await self.bitswap.add_block(cid, data)
```

**Problem:** Kubo (`ipfs add`) wraps every leaf chunk in `UnixFS Data(type=File)` + `dag-pb`.
Using `CODEC_RAW` produces completely different CIDs — a file added by py-libp2p
**cannot be fetched by any Kubo node**, and vice versa.

### What to change

**File:** `libp2p/bitswap/dag_pb.py` — add a `create_leaf_node()` helper:

```python
# Add to dag_pb.py after create_file_node()

def create_leaf_node(data: bytes) -> bytes:
    """
    Create a DAG-PB leaf node for a single file chunk.

    Wraps raw bytes in UnixFS Data(type=File, data=chunk) + PBNode,
    matching Kubo's default behaviour (RawLeaves=false).
    This ensures leaf CIDs are identical to those produced by `ipfs add`.

    Args:
        data: Raw chunk bytes

    Returns:
        Encoded DAG-PB bytes (to be stored as a dag-pb block)
    """
    unixfs_data = UnixFSData(type="file", data=data, filesize=len(data))
    return encode_dag_pb([], unixfs_data)   # no links — data is inline
```

**File:** `libp2p/bitswap/dag.py` — update all three places that use `CODEC_RAW` for leaves:

```python
# BEFORE — add_file() chunk loop
chunk_cid = compute_cid_v1(chunk_data, codec=CODEC_RAW)
await self.bitswap.add_block(chunk_cid, chunk_data)
chunks_data.append((chunk_cid, len(chunk_data)))

# AFTER — add_file() chunk loop
from .dag_pb import create_leaf_node
leaf_block = create_leaf_node(chunk_data)
chunk_cid = compute_cid_v1(leaf_block, codec=CODEC_DAG_PB)
await self.bitswap.add_block(chunk_cid, leaf_block)
chunks_data.append((chunk_cid, len(chunk_data)))   # size = original data size, not block size
```

Apply the same change in `add_bytes()` and for the single-block small-file path.

Also update `fetch_file()` — the leaf extraction logic at ~line 630:

```python
# BEFORE — fetch_file() leaf reassembly
if is_file_node(leaf_raw):
    _, leaf_unixfs = decode_dag_pb(leaf_raw)
    chunk = leaf_unixfs.data if leaf_unixfs and leaf_unixfs.data else b""
else:
    chunk = leaf_raw   # raw block fallback
```

This already handles `dag-pb` leaves correctly — **no change needed here**.
The `is_file_node` / `decode_dag_pb` path already extracts `.data` from UnixFS.

### Benefit

| Before | After |
|--------|-------|
| Leaves use `CODEC_RAW` → wrong CIDs | Leaves use `dag-pb` + UnixFS → **CIDs match Kubo exactly** |
| py-libp2p files not fetchable by Kubo | Any Kubo node can fetch files added by py-libp2p |
| py-libp2p cannot fetch Kubo-added files | py-libp2p fetches any file from the IPFS network |

---

## 2. Balanced DAG Layout

### Current State in your local `dag_pb.py`

`create_file_node()` builds a **flat 1-level structure** — the root links directly to every chunk:

```python
# libp2p/bitswap/dag_pb.py  (your local file, ~line 200)
def create_file_node(chunks: Sequence[tuple[CIDInput, int]]) -> bytes:
    links = []
    total_size = 0
    blocksizes = []

    for i, (cid, size) in enumerate(chunks):
        links.append(Link(cid=cid, name=f"chunk{i}", size=size))   # ALL chunks as direct links
        blocksizes.append(size)
        total_size += size

    unixfs_data = UnixFSData(type="file", filesize=total_size, blocksizes=blocksizes)
    return encode_dag_pb(links, unixfs_data)
```

**Problem:** Kubo's maximum is **174 links per node**. With the current 63 KB chunk size
(`DEFAULT_CHUNK_SIZE = 63 * 1024` in `chunker.py`), a 100 MB file produces ~1,626 chunks.
`create_file_node()` puts all 1,626 as direct links on the root — this:
- Produces a root block that is **megabytes in size** (exceeds `MAX_BLOCK_SIZE`)
- Creates a **different CID** than Kubo for the same file
- Gets **rejected by other IPFS nodes**

### What to change

**File:** `libp2p/bitswap/dag_pb.py` — add `balanced_layout()`:

```python
# Add to dag_pb.py

MAX_LINKS_PER_NODE = 174   # Matches Go's balanced.Layout default


def balanced_layout(
    leaves: list[tuple[bytes, bytes, int]],
    max_links: int = MAX_LINKS_PER_NODE,
) -> tuple[bytes, bytes]:
    """
    Build a balanced Merkle DAG from leaf blocks.

    Groups leaves into batches of max_links (174), creates internal nodes
    for each batch, then repeats until a single root remains.
    Matches Go's balanced.Layout exactly.

    Args:
        leaves: List of (cid_bytes, block_bytes, file_data_size) tuples.
                cid_bytes: CID of the leaf block (as bytes)
                block_bytes: The actual encoded block bytes
                file_data_size: Size of raw file data in this leaf (not block size)
        max_links: Max links per internal node (default 174, matches Kubo)

    Returns:
        (root_cid_bytes, root_block_bytes)
    """
    if not leaves:
        raise ValueError("Cannot build balanced layout from empty leaf list")

    if len(leaves) == 1:
        return leaves[0][0], leaves[0][1]

    # level entries: (cid_bytes, block_bytes, file_data_size, cumulative_block_size)
    # cumulative_block_size = len(block) + sum(children's cumulative sizes)
    level: list[tuple[bytes, bytes, int, int]] = [
        (cid, blk, fsize, len(blk)) for cid, blk, fsize in leaves
    ]

    while len(level) > 1:
        next_level: list[tuple[bytes, bytes, int, int]] = []
        for i in range(0, len(level), max_links):
            batch = level[i : i + max_links]
            if len(batch) == 1:
                next_level.append(batch[0])
                continue

            # Build internal node linking to this batch
            internal_links = []
            blocksizes = []
            total_filesize = 0
            total_cum = 0

            for cid_b, _, fsize, cum in batch:
                internal_links.append(Link(cid=cid_b, name="", size=cum))
                blocksizes.append(fsize)
                total_filesize += fsize
                total_cum += cum

            unixfs_data = UnixFSData(
                type="file", filesize=total_filesize, blocksizes=blocksizes
            )
            internal_block = encode_dag_pb(internal_links, unixfs_data)
            internal_cid = compute_cid_v1(internal_block, codec=CODEC_DAG_PB)
            cum_size = len(internal_block) + total_cum
            next_level.append((internal_cid, internal_block, total_filesize, cum_size))

        level = next_level

    return level[0][0], level[0][1]
```

> **Note:** `compute_cid_v1` and `CODEC_DAG_PB` are already imported in `dag_pb.py`
> via `from .cid import CIDInput, cid_to_bytes` — add `compute_cid_v1, CODEC_DAG_PB`
> to that import.

**File:** `libp2p/bitswap/dag.py` — replace `create_file_node()` call with `balanced_layout()`:

```python
# BEFORE — dag.py add_file() and add_bytes()
root_data = create_file_node(chunks_data)
root_cid = compute_cid_v1(root_data, codec=CODEC_DAG_PB)
await self.bitswap.add_block(root_cid, root_data)

# AFTER
from .dag_pb import balanced_layout
# Build leaf tuples: (cid_bytes, block_bytes, file_data_size)
# We need the block bytes — store them during chunk loop:
leaves = [(cid, leaf_block, data_size) for cid, leaf_block, data_size in leaf_triples]
root_cid, root_data = balanced_layout(leaves)
await self.bitswap.add_block(root_cid, root_data)
```

This requires a small refactor of the chunk loop to also retain the `leaf_block` bytes,
not just `(cid, size)`. Change `chunks_data` from `list[tuple[bytes, int]]`
to `list[tuple[bytes, bytes, int]]` (cid, block_bytes, data_size).

### Benefit

| Before | After |
|--------|-------|
| Root links to ALL chunks directly (flat) | Balanced tree, max 174 links/node |
| Root block can be MBs for large files | Root block always small (≤ 174 links) |
| Files > 174 chunks produce wrong CIDs | **CIDs match Kubo for files of any size** |
| Large root blocks rejected by IPFS nodes | All nodes within block size limits |

---

## 3. io.IOBase Input Support

### Current State in your local `dag.py`

`add_file()` only accepts a **file path string**:

```python
# libp2p/bitswap/dag.py  (your local file, ~line 114)
async def add_file(
    self,
    file_path: str,          # ← only accepts string path
    chunk_size: int | None = None,
    progress_callback: ...,
    wrap_with_directory: bool = True,
) -> bytes:
    file_size = get_file_size(file_path)   # os.path.getsize
    for chunk_data in chunk_file(file_path, chunk_size):   # opens file internally
```

`add_bytes()` accepts in-memory `bytes` but loads everything into RAM:

```python
# dag.py add_bytes() — full data in memory
async def add_bytes(self, data: bytes, ...) -> bytes:
    file_size = len(data)
    chunks = chunk_bytes(data, chunk_size)   # entire data already in memory
```

Your local `chunker.py` has `chunk_file()` (file path) and `chunk_bytes()` (bytes),
but **no `chunk_stream()` for `io.IOBase`**.

### What to change

**File:** `libp2p/bitswap/chunker.py` — add `chunk_stream()`:

```python
# Add to chunker.py
import io
from collections.abc import Iterator

def chunk_stream(
    stream: io.IOBase, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> Iterator[bytes]:
    """
    Stream chunks from any io.IOBase object.

    Memory efficient — reads one chunk at a time without loading the
    entire content into memory. Works with file handles, BytesIO,
    GzipFile, network streams, or any readable io.IOBase.

    Args:
        stream: Any readable io.IOBase (open(), BytesIO, GzipFile, etc.)
        chunk_size: Size of each chunk in bytes

    Yields:
        Chunks of up to chunk_size bytes

    Example:
        >>> import io
        >>> data = b"hello world " * 100000
        >>> for chunk in chunk_stream(io.BytesIO(data)):
        ...     print(f"chunk: {len(chunk)} bytes")
    """
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        yield chunk
```

**File:** `libp2p/bitswap/dag.py` — add `add_stream()` method to `MerkleDag`:

```python
# Add to MerkleDag class in dag.py
async def add_stream(
    self,
    stream: "io.IOBase",
    chunk_size: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> bytes:
    """
    Add data from any io.IOBase stream to the DAG.

    More flexible than add_file() (accepts any stream, not just file paths)
    and more memory efficient than add_bytes() (reads one chunk at a time).

    Args:
        stream: Any readable io.IOBase — open() handles, BytesIO,
                GzipFile, network streams, etc.
        chunk_size: Optional chunk size (auto-selected if None)
        progress_callback: Optional callback(current, total, status)

    Returns:
        Root CID bytes

    Example:
        >>> import io, gzip
        >>> # From BytesIO
        >>> root_cid = await dag.add_stream(io.BytesIO(b"hello world"))

        >>> # From a file handle
        >>> with open("movie.mp4", "rb") as f:
        ...     root_cid = await dag.add_stream(f)

        >>> # From a gzip stream (decompress on-the-fly)
        >>> with gzip.open("archive.gz", "rb") as f:
        ...     root_cid = await dag.add_stream(f)
    """
    import io as _io
    from .chunker import chunk_stream
    from .dag_pb import create_leaf_node, balanced_layout

    if chunk_size is None:
        chunk_size = DEFAULT_CHUNK_SIZE

    leaf_triples: list[tuple[bytes, bytes, int]] = []  # (cid, block_bytes, data_size)
    bytes_processed = 0

    for i, chunk_data in enumerate(chunk_stream(stream, chunk_size)):
        leaf_block = create_leaf_node(chunk_data)
        chunk_cid = compute_cid_v1(leaf_block, codec=CODEC_DAG_PB)
        await self.bitswap.add_block(chunk_cid, leaf_block)
        leaf_triples.append((chunk_cid, leaf_block, len(chunk_data)))
        bytes_processed += len(chunk_data)

        if progress_callback:
            await _call_progress_callback(
                progress_callback, bytes_processed, bytes_processed,
                f"chunking ({i + 1} chunks)",
            )

    if not leaf_triples:
        # Empty stream — store empty leaf
        leaf_block = create_leaf_node(b"")
        cid = compute_cid_v1(leaf_block, codec=CODEC_DAG_PB)
        await self.bitswap.add_block(cid, leaf_block)
        return cid

    if len(leaf_triples) == 1:
        return leaf_triples[0][0]

    root_cid, root_data = balanced_layout(leaf_triples)
    await self.bitswap.add_block(root_cid, root_data)

    if progress_callback:
        await _call_progress_callback(
            progress_callback, bytes_processed, bytes_processed, "completed"
        )

    return root_cid
```

Also update `dag.py` imports at the top:

```python
# Add to dag.py imports
import io
from .chunker import (
    DEFAULT_CHUNK_SIZE,
    chunk_bytes,
    chunk_file,
    chunk_stream,       # ← add this
    estimate_chunk_count,
    get_file_size,
)
from .dag_pb import (
    create_file_node,
    create_leaf_node,   # ← add this
    balanced_layout,    # ← add this
    decode_dag_pb,
    is_directory_node,
    is_file_node,
)
```

### Benefit

| Before | After |
|--------|-------|
| `add_file()` — file path string only | `add_stream()` — **any `io.IOBase`** |
| `add_bytes()` — full data in RAM | `add_stream()` — one chunk at a time, **constant memory** |
| Cannot add a compressed/encrypted stream | Works with `GzipFile`, `BZ2File`, any wrapper |
| Cannot pipe network data into IPFS | Can stream data directly from network into DAG |

---

## 4. BlockService — Transparent Local→Network Fallback

### Current State in your local code

`MerkleDag` calls `self.bitswap.get_block()` / `self.bitswap.add_block()` directly.
`BitswapClient` checks its `block_store` internally, but there is no explicit service layer
that:
- **Auto-caches** blocks fetched from the network into the local store
- **Announces** newly stored blocks to peers who are waiting for them
- **Decouples** `MerkleDag` from the concrete `BitswapClient` type

Your `block_store.py` has `BlockStore` (ABC) and `MemoryBlockStore` — no service layer.
Your `__init__.py` exports `BitswapClient`, `BlockStore`, `MemoryBlockStore` — no `BlockService`.

### What to change

**File:** `libp2p/bitswap/block_service.py` *(new file)*

```python
# libp2p/bitswap/block_service.py  (new file)
"""
BlockService: transparent local→network fallback for block retrieval.

Bridges BlockStore and BitswapClient into a single unified interface:
- get_block: checks local store first, falls back to network, auto-caches result
- put_block: stores locally and announces to peers who have this CID in their wantlist
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .block_store import BlockStore
from .cid import CIDInput, cid_to_bytes

if TYPE_CHECKING:
    from libp2p.peer.id import ID as PeerID
    from .client import BitswapClient

logger = logging.getLogger(__name__)


class BlockService:
    """
    Combines local block storage with network exchange.

    On get_block:
        1. Check local BlockStore (fast, no network cost)
        2. If missing, fetch via BitswapClient (network)
        3. Auto-cache the fetched block locally for future requests

    On put_block:
        1. Store in local BlockStore
        2. Call BitswapClient.add_block() so it can respond to peers
           who have this CID in their wantlist

    Example:
        >>> store = FilesystemBlockStore("/var/lib/ipfs/blocks")
        >>> service = BlockService(store, bitswap)
        >>> dag = MerkleDag(bitswap, block_service=service)
    """

    def __init__(self, store: BlockStore, bitswap: "BitswapClient") -> None:
        self.store = store
        self.bitswap = bitswap

    async def get_block(
        self,
        cid: CIDInput,
        peer_id: "PeerID | None" = None,
        timeout: float = 30.0,
    ) -> bytes | None:
        """
        Get a block. Checks local store first, then fetches from network.
        Auto-caches any block fetched from the network.
        """
        cid_bytes = cid_to_bytes(cid)

        # 1. Local lookup — instant, no network
        data = await self.store.get_block(cid_bytes)
        if data is not None:
            logger.debug(f"BlockService: local hit {cid_bytes[:6].hex()}...")
            return data

        # 2. Network fetch via Bitswap
        logger.debug(f"BlockService: local miss, fetching from network")
        data = await self.bitswap.get_block(cid_bytes, peer_id, timeout)

        if data is not None:
            # Auto-cache locally — future requests for this block are free
            await self.store.put_block(cid_bytes, data)
            logger.debug(f"BlockService: cached fetched block locally")

        return data

    async def put_block(self, cid: CIDInput, data: bytes) -> None:
        """
        Store a block locally and notify peers who are waiting for it.
        """
        cid_bytes = cid_to_bytes(cid)
        await self.store.put_block(cid_bytes, data)
        # add_block() on BitswapClient stores the block AND notifies
        # any peers who have this CID in their pending wantlist
        await self.bitswap.add_block(cid_bytes, data)
        logger.debug(f"BlockService: stored and announced {cid_bytes[:6].hex()}...")
```

**File:** `libp2p/bitswap/__init__.py` — add export:

```python
from .block_service import BlockService

# Add to __all__:
"BlockService",
```

**File:** `libp2p/bitswap/dag.py` — optionally accept `BlockService`:

```python
# dag.py __init__ — updated
def __init__(
    self,
    bitswap: BitswapClient,
    block_store: BlockStore | None = None,
    block_service: "BlockService | None" = None,
) -> None:
    self.bitswap = bitswap
    self.block_store = block_store or bitswap.block_store
    self.block_service = block_service  # optional; used by add_stream if provided
```

### Benefit

| Before | After |
|--------|-------|
| No explicit caching layer | **Every fetched block is auto-cached** locally |
| `add_block` doesn't announce to waiting peers | `put_block` calls `bitswap.add_block()` — peers notified |
| `MerkleDag` hardwired to `BitswapClient` | Pluggable — inject any `BlockService` |
| Hard to unit-test `MerkleDag` | Mock `BlockService` in tests, no full Bitswap needed |

---

## 5. FilesystemBlockStore — Persistent Storage

### Current State in your local `block_store.py`

Only one implementation exists — `MemoryBlockStore`:

```python
# libp2p/bitswap/block_store.py  (your local file)
class MemoryBlockStore(BlockStore):
    def __init__(self) -> None:
        self._blocks: dict[CIDObject, bytes] = {}   # ← in-memory dict only

    async def get_block(self, cid: CIDInput) -> bytes | None:
        cid_obj = _normalize_cid(cid)
        return self._blocks.get(cid_obj)

    async def put_block(self, cid: CIDInput, data: bytes) -> None:
        cid_obj = _normalize_cid(cid)
        self._blocks[cid_obj] = data
```

**Problem:** When the process exits, all blocks are gone. For a long-running node or
any production use, this is unusable.

### What to change

**File:** `libp2p/bitswap/block_store.py` — add `FilesystemBlockStore` after `MemoryBlockStore`:

```python
# Add to block_store.py after MemoryBlockStore

import asyncio
from pathlib import Path


class FilesystemBlockStore(BlockStore):
    """
    Filesystem-based block store. Persists blocks to disk as files.

    Each block is stored as a file at:
        <base_path>/<first_2_chars_of_cid>/<rest_of_cid>

    This two-level directory structure (same as py-ipfs-lite and many IPFS
    implementations) avoids having too many files in a single directory.

    Args:
        base_path: Root directory for block storage. Created if it doesn't exist.

    Example:
        >>> store = FilesystemBlockStore("/var/lib/myapp/blocks")
        >>> bitswap = BitswapClient(host, store)
        # Blocks now survive process restarts!

        >>> # Combine with BlockService for auto-caching:
        >>> service = BlockService(store, bitswap)
    """

    def __init__(self, base_path: str | Path) -> None:
        self._path = Path(base_path)
        self._path.mkdir(parents=True, exist_ok=True)

    def _cid_to_path(self, cid: CIDInput) -> Path:
        """Convert a CID to a filesystem path using 2-char prefix directories."""
        cid_str = str(_normalize_cid(cid))
        return self._path / cid_str[:2] / cid_str[2:]

    async def get_block(self, cid: CIDInput) -> bytes | None:
        """Get a block by CID. Returns None if not found."""
        path = self._cid_to_path(cid)
        if not path.exists():
            return None
        return await asyncio.to_thread(path.read_bytes)

    async def put_block(self, cid: CIDInput, data: bytes) -> None:
        """Store a block to disk."""
        path = self._cid_to_path(cid)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def has_block(self, cid: CIDInput) -> bool:
        """Check if a block exists on disk."""
        return self._cid_to_path(cid).exists()

    async def delete_block(self, cid: CIDInput) -> None:
        """Delete a block from disk."""
        path = self._cid_to_path(cid)
        if path.exists():
            await asyncio.to_thread(path.unlink)

    def get_all_cids(self) -> list[bytes]:
        """Return all stored CIDs as bytes."""
        cids = []
        for subdir in self._path.iterdir():
            if subdir.is_dir():
                for entry in subdir.iterdir():
                    if entry.is_file():
                        cid_str = subdir.name + entry.name
                        try:
                            cid_obj = _normalize_cid(cid_str)
                            cids.append(cid_obj.buffer)
                        except Exception:
                            pass
        return cids

    def size(self) -> int:
        """Return the number of stored blocks."""
        return sum(1 for d in self._path.iterdir() if d.is_dir()
                   for f in d.iterdir() if f.is_file())
```

**File:** `libp2p/bitswap/__init__.py` — add export:

```python
from .block_store import BlockStore, MemoryBlockStore, FilesystemBlockStore

# Add to __all__:
"FilesystemBlockStore",
```

### Benefit

| Before | After |
|--------|-------|
| `MemoryBlockStore` only — all data lost on exit | **Blocks persist across process restarts** |
| Memory grows for every block fetched | Disk usage only — RAM stays flat |
| Cannot handle files larger than available RAM | Handles files of **any size** |
| Not suitable for production nodes | Production-ready persistent storage |
| Re-fetches same blocks every run | Previously fetched blocks served instantly from disk |

---

## 6. Canonical DAG-PB Encoding

### Current State in your local `dag_pb.py`

`encode_dag_pb()` uses protobuf's default `SerializeToString()`:

```python
# libp2p/bitswap/dag_pb.py  (your local file, ~line 88)
def encode_dag_pb(links: list[Link], unixfs_data: UnixFSData | None = None) -> bytes:
    pb_node = PBNode()

    # Add links
    for link in links:
        pb_link = pb_node.Links.add()
        pb_link.Hash = link.cid
        pb_link.Name = link.name
        pb_link.Tsize = link.size

    # Add UnixFS data
    if unixfs_data:
        pb_unixfs = PBUnixFSData()
        pb_unixfs.Type = UnixFSData.TYPE_MAP[unixfs_data.type]
        pb_unixfs.Data = unixfs_data.data
        pb_unixfs.filesize = unixfs_data.filesize
        ...
        pb_node.Data = pb_unixfs.SerializeToString()

    return pb_node.SerializeToString()   # ← standard protobuf serialization
```

**Problem:** Standard protobuf serializes fields in **field-number order**:
- `Data` is field 1 → serialized **first**
- `Links` is field 2 → serialized **second**

But the [DAG-PB spec](https://ipld.io/specs/codecs/dag-pb/spec/#serialization) requires
**Links before Data** for canonical encoding. Wrong order → different bytes → **different CID**
than Kubo for the same logical content.

### What to change

**File:** `libp2p/bitswap/dag_pb.py` — add `_encode_varint()` and replace `encode_dag_pb()`:

```python
# Add before encode_dag_pb() in dag_pb.py

def _encode_varint(value: int) -> bytes:
    """Encode an unsigned integer as a protobuf varint."""
    buf = []
    while value > 0x7F:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.append(value & 0x7F)
    return bytes(buf)
```

Replace the body of `encode_dag_pb()`:

```python
# BEFORE — encode_dag_pb() uses pb_node.SerializeToString()
def encode_dag_pb(links: list[Link], unixfs_data: UnixFSData | None = None) -> bytes:
    pb_node = PBNode()
    for link in links:
        pb_link = pb_node.Links.add()
        pb_link.Hash = link.cid
        pb_link.Name = link.name
        pb_link.Tsize = link.size
    if unixfs_data:
        ...
        pb_node.Data = pb_unixfs.SerializeToString()
    return pb_node.SerializeToString()   # ← wrong field order

# AFTER — manually serialize with Links (field 2) before Data (field 1)
def encode_dag_pb(links: list[Link], unixfs_data: UnixFSData | None = None) -> bytes:
    """
    Encode links and UnixFS data as DAG-PB with canonical ordering.

    DAG-PB canonical format requires Links (field 2) BEFORE Data (field 1).
    Standard protobuf emits Data first (field 1 < field 2), producing
    different bytes and a different CID than Kubo.

    This function manually constructs the wire format to enforce correct ordering.
    """
    result = b""

    # 1. Serialize Links first — field 2, wire type 2 (length-delimited) = tag 0x12
    from .pb.dag_pb_pb2 import PBLink
    for link in links:
        pb_link = PBLink()
        pb_link.Hash = link.cid
        pb_link.Name = link.name
        pb_link.Tsize = link.size
        link_bytes = pb_link.SerializeToString()
        result += b"\x12" + _encode_varint(len(link_bytes)) + link_bytes

    # 2. Serialize Data after Links — field 1, wire type 2 = tag 0x0a
    if unixfs_data is not None:
        pb_unixfs = PBUnixFSData()
        pb_unixfs.Type = UnixFSData.TYPE_MAP[unixfs_data.type]  # type: ignore[assignment]
        pb_unixfs.Data = unixfs_data.data
        pb_unixfs.filesize = unixfs_data.filesize
        for bs in unixfs_data.blocksizes:
            pb_unixfs.blocksizes.append(bs)
        if unixfs_data.hash_type:
            pb_unixfs.hashType = unixfs_data.hash_type
        if unixfs_data.fanout:
            pb_unixfs.fanout = unixfs_data.fanout
        data_bytes = pb_unixfs.SerializeToString()
        result += b"\x0a" + _encode_varint(len(data_bytes)) + data_bytes

    return result
```

> `decode_dag_pb()` uses `PBNode.ParseFromString()` which is order-independent —
> **no change needed** there.

### Benefit

| Before | After |
|--------|-------|
| `Data` field serialized before `Links` | `Links` serialized before `Data` — **DAG-PB canonical order** |
| Root CID differs from Kubo for same content | Root CID **byte-identical to Kubo** |
| CID verification against Kubo nodes fails | Full CID compatibility with entire IPFS network |
| Combined with fix #1: still wrong root CID | Combined with fix #1: **complete Kubo compatibility** |

---

## 7. Wantlist / Message Dataclasses

### Current State in your local `messages.py`

Everything uses raw protobuf objects and magic integers:

```python
# libp2p/bitswap/messages.py  (your local file)
def create_wantlist_entry(
    block_cid: CIDInput,
    priority: int = 1,
    cancel: bool = False,
    want_type: int = 0,          # ← what does 0 mean? Block? Have?
    send_dont_have: bool = False,
) -> Message.Wantlist.Entry:
    entry = Message.Wantlist.Entry()
    entry.block = cid_to_bytes(block_cid)
    entry.priority = priority
    entry.cancel = cancel
    entry.wantType = want_type   # ← raw int, no type safety
    entry.sendDontHave = send_dont_have
    return entry
```

There is no `WantType` enum, no `BlockPresence` type, no `BitswapMessage` dataclass.
Code that builds or inspects messages must know raw protobuf field names and int values.

### What to change

**File:** `libp2p/bitswap/wantlist.py` *(new file)*

```python
# libp2p/bitswap/wantlist.py  (new file)
"""
Typed dataclass wrappers for Bitswap wantlist entries and messages.

Provides a clean, self-documenting Python API over the raw protobuf
Message format from messages.py / pb/bitswap_pb2.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .cid import CIDInput, cid_to_bytes


class WantType(Enum):
    """Type of want request (Bitswap 1.2.0 field)."""
    Block = 0   # Request the full block bytes
    Have = 1    # Only ask: "do you have this block?" (cheaper)


class BlockPresenceType(Enum):
    """Type of block presence response (Bitswap 1.2.0)."""
    Have = 0       # Peer has the block and can send it
    DontHave = 1   # Peer does not have the block


@dataclass
class WantlistEntry:
    """A single entry in a Bitswap wantlist."""
    cid: bytes                              # CID as raw bytes
    priority: int = 1                       # Higher = more urgent
    cancel: bool = False                    # True to cancel a previous want
    want_type: WantType = WantType.Block    # Block or Have
    send_dont_have: bool = False            # Request explicit DontHave responses

    @classmethod
    def from_cid(
        cls,
        cid: CIDInput,
        priority: int = 1,
        cancel: bool = False,
        want_type: WantType = WantType.Block,
        send_dont_have: bool = False,
    ) -> WantlistEntry:
        """Create a WantlistEntry from any CIDInput form."""
        return cls(
            cid=cid_to_bytes(cid),
            priority=priority,
            cancel=cancel,
            want_type=want_type,
            send_dont_have=send_dont_have,
        )


@dataclass
class Wantlist:
    """A collection of wantlist entries."""
    entries: List[WantlistEntry] = field(default_factory=list)
    full: bool = False   # True = complete wantlist replacement, False = delta update

    def add(
        self,
        cid: CIDInput,
        priority: int = 1,
        want_type: WantType = WantType.Block,
        send_dont_have: bool = False,
    ) -> None:
        """Add a want entry."""
        self.entries.append(WantlistEntry.from_cid(
            cid, priority=priority, want_type=want_type,
            send_dont_have=send_dont_have,
        ))

    def cancel(self, cid: CIDInput) -> None:
        """Add a cancel entry for a previously wanted CID."""
        self.entries.append(WantlistEntry.from_cid(cid, cancel=True))

    def contains(self, cid: CIDInput) -> bool:
        """Check if a CID is in the wantlist."""
        cid_bytes = cid_to_bytes(cid)
        return any(e.cid == cid_bytes for e in self.entries)

    def __len__(self) -> int:
        return len(self.entries)


@dataclass
class BlockPresence:
    """A HAVE or DONT_HAVE response for a specific CID."""
    cid: bytes
    type: BlockPresenceType

    @classmethod
    def have(cls, cid: CIDInput) -> BlockPresence:
        return cls(cid=cid_to_bytes(cid), type=BlockPresenceType.Have)

    @classmethod
    def dont_have(cls, cid: CIDInput) -> BlockPresence:
        return cls(cid=cid_to_bytes(cid), type=BlockPresenceType.DontHave)


@dataclass
class BitswapMessage:
    """
    High-level typed representation of a Bitswap protocol message.

    Wraps the raw protobuf Message with typed fields and helper methods.
    Convert to/from protobuf using to_proto() / from_proto().
    """
    wantlist: Optional[Wantlist] = None
    blocks: List[tuple[bytes, bytes]] = field(default_factory=list)   # (cid, data)
    block_presences: List[BlockPresence] = field(default_factory=list)
    pending_bytes: int = 0

    # --- Convenience properties ---

    @property
    def is_want(self) -> bool:
        """True if this message contains want entries."""
        return self.wantlist is not None and len(self.wantlist) > 0

    @property
    def has_blocks(self) -> bool:
        """True if this message contains block data."""
        return bool(self.blocks)

    @property
    def has_presences(self) -> bool:
        """True if this message contains HAVE/DONT_HAVE responses."""
        return bool(self.block_presences)

    # --- Builder methods ---

    def add_want(self, cid: CIDInput, **kwargs) -> None:
        """Add a want entry to this message."""
        if self.wantlist is None:
            self.wantlist = Wantlist()
        self.wantlist.add(cid, **kwargs)

    def add_block(self, cid: CIDInput, data: bytes) -> None:
        """Add a block payload to this message."""
        self.blocks.append((cid_to_bytes(cid), data))

    def add_have(self, cid: CIDInput) -> None:
        """Add a HAVE presence response."""
        self.block_presences.append(BlockPresence.have(cid))

    def add_dont_have(self, cid: CIDInput) -> None:
        """Add a DONT_HAVE presence response."""
        self.block_presences.append(BlockPresence.dont_have(cid))
```

**File:** `libp2p/bitswap/messages.py` — update `create_wantlist_entry()` to accept `WantType`:

```python
# messages.py — updated create_wantlist_entry() signature
from .wantlist import WantType   # add this import

def create_wantlist_entry(
    block_cid: CIDInput,
    priority: int = 1,
    cancel: bool = False,
    want_type: WantType | int = WantType.Block,   # now accepts enum OR int
    send_dont_have: bool = False,
) -> Message.Wantlist.Entry:
    entry = Message.Wantlist.Entry()
    entry.block = cid_to_bytes(block_cid)
    entry.priority = priority
    entry.cancel = cancel
    # Accept both WantType enum and raw int for backward compatibility
    entry.wantType = want_type.value if isinstance(want_type, WantType) else want_type  # type: ignore[assignment]
    entry.sendDontHave = send_dont_have
    return entry
```

**File:** `libp2p/bitswap/__init__.py` — add exports:

```python
from .wantlist import (
    WantType,
    WantlistEntry,
    Wantlist,
    BlockPresence,
    BlockPresenceType,
    BitswapMessage,
)

# Add to __all__:
"WantType", "WantlistEntry", "Wantlist",
"BlockPresence", "BlockPresenceType", "BitswapMessage",
```

### Benefit

| Before | After |
|--------|-------|
| `want_type=0` — what does 0 mean? | `want_type=WantType.Block` — **self-documenting** |
| Raw protobuf objects everywhere | Typed dataclasses with IDE autocomplete |
| No `BlockPresence` type | `BlockPresence.have(cid)` / `BlockPresence.dont_have(cid)` |
| No message introspection helpers | `msg.is_want`, `msg.has_blocks`, `msg.has_presences` |
| Silent bugs from wrong int values | Type errors caught at development time |
| Backward-incompatible change risk | `WantType | int` keeps existing callers working |

---

## 8. Summary of All Changes

### Files to Modify

| File | What changes |
|------|-------------|
| `libp2p/bitswap/dag_pb.py` | Add `_encode_varint()`, `create_leaf_node()`, `balanced_layout()`. Fix `encode_dag_pb()` for canonical ordering (Links before Data). Add `compute_cid_v1, CODEC_DAG_PB` to imports. |
| `libp2p/bitswap/dag.py` | Update `add_file()` + `add_bytes()` to use `create_leaf_node()` + `balanced_layout()`. Add `add_stream()` method. Update imports. |
| `libp2p/bitswap/chunker.py` | Add `chunk_stream(stream: io.IOBase)` function. Add `import io`. |
| `libp2p/bitswap/block_store.py` | Add `FilesystemBlockStore` class. Add `import asyncio` and `from pathlib import Path`. |
| `libp2p/bitswap/messages.py` | Update `create_wantlist_entry()` to accept `WantType | int`. Add `from .wantlist import WantType`. |
| `libp2p/bitswap/__init__.py` | Export `BlockService`, `FilesystemBlockStore`, `WantType`, `WantlistEntry`, `Wantlist`, `BlockPresence`, `BlockPresenceType`, `BitswapMessage`. |

### Files to Create

| File | Purpose |
|------|---------|
| `libp2p/bitswap/block_service.py` | `BlockService` — transparent local→network fallback with auto-caching and peer announcement. |
| `libp2p/bitswap/wantlist.py` | `WantType`, `WantlistEntry`, `Wantlist`, `BlockPresence`, `BlockPresenceType`, `BitswapMessage` typed dataclasses. |

### Combined Benefits at a Glance

| Benefit | Enabled by |
|---------|-----------|
| ✅ Full Kubo CID compatibility for all files | #1 (UnixFS leaf encoding) + #6 (canonical ordering) |
| ✅ Files of any size work correctly | #2 (balanced DAG, 174 links/node) |
| ✅ Works with streams, BytesIO, GzipFile | #3 (io.IOBase + `add_stream()`) |
| ✅ Auto-caching of network-fetched blocks | #4 (BlockService) |
| ✅ Peer announcement on block store | #4 (BlockService `put_block`) |
| ✅ Persistent storage across restarts | #5 (FilesystemBlockStore) |
| ✅ Constant memory for any file size | #3 (stream chunking) + #5 (filesystem store) |
| ✅ Pluggable exchange backend | #4 (BlockService abstraction) |
| ✅ Self-documenting message construction | #7 (WantType enum + dataclasses) |
| ✅ Type-safe wantlist building | #7 (WantlistEntry, Wantlist dataclasses) |

### Recommended Order of Implementation

```
Step 1 → Fix #6 (canonical encoding in dag_pb.py)
         Small, isolated, no dependencies. Fixes the root cause of CID mismatch.

Step 2 → Fix #1 + #2 together (create_leaf_node + balanced_layout + update dag.py)
         These are tightly coupled — do both in one pass.

Step 3 → Fix #5 (FilesystemBlockStore in block_store.py)
         Self-contained, no dependencies on steps 1-2.

Step 4 → Fix #4 (create block_service.py)
         Depends on BlockStore ABC (already exists) and BitswapClient (already exists).

Step 5 → Fix #3 (chunk_stream in chunker.py + add_stream in dag.py)
         Depends on create_leaf_node and balanced_layout from step 2.

Step 6 → Fix #7 (create wantlist.py + update messages.py)
         Purely additive — no breaking changes, can be done any time.
```
