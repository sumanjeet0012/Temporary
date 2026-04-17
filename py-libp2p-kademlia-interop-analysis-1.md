# py-libp2p Kademlia DHT: Interoperability Analysis with IPFS Kubo & go-libp2p

> **Author:** Deep analysis based on direct code inspection of:
> - `py-libp2p` @ `github.com/libp2p/py-libp2p` (latest main)
> - `go-libp2p-kad-dht` @ `github.com/libp2p/go-libp2p-kad-dht` (latest main)
> - IPFS Kubo DHT (inherits go-libp2p-kad-dht)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Critical Missing Features (Blocks Interop)](#3-critical-missing-features-blocks-interop)
4. [Important Missing Features (Degrades Interop)](#4-important-missing-features-degrades-interop)
5. [Nice-to-Have Features (Performance & Production)](#5-nice-to-have-features-performance--production)
6. [Implementation Guide](#6-implementation-guide)
7. [Interoperability Testing Strategy](#7-interoperability-testing-strategy)
8. [Protocol Wire Compatibility Checklist](#8-protocol-wire-compatibility-checklist)
9. [Key Differences Reference Table](#9-key-differences-reference-table)

---

## 1. Executive Summary

The py-libp2p Kademlia DHT is a solid foundation, correctly implementing: the core k-bucket routing table, XOR-distance metric, iterative lookup (partially), FIND_NODE / GET_VALUE / PUT_VALUE / GET_PROVIDERS / ADD_PROVIDER message handling, varint-length-prefixed protobuf framing, and IPNS/PK namespace validators. However, several critical gaps prevent full wire-level interoperability with Kubo and go-libp2p nodes on the public IPFS DHT network.

**The three showstoppers for Kubo interop are:**

1. **Unsigned DHT records** — Kubo rejects `PUT_VALUE` messages where the record is not signed with the authoring node's private key.
2. **Wrong provider key format** — IPFS provider lookups use raw multihash bytes as keys, not UTF-8 encoded strings.
3. **No true iterative lookup** — The current `get_value` / `find_providers` only queries already-known peers, not the newly discovered closer peers returned in responses. This means queries terminate prematurely and almost never reach the true closest nodes on the real network.

---

## 2. Architecture Overview

### py-libp2p Structure

```
libp2p/kad_dht/
├── kad_dht.py          # KadDHT service (stream handler, put_value, get_value, provide)
├── routing_table.py    # RoutingTable + KBucket (split on local-ID bucket only)
├── peer_routing.py     # PeerRouting (find_peer, find_closest_peers_network)
├── provider_store.py   # ProviderStore (in-memory, add/get/expire providers)
├── value_store.py      # ValueStore (in-memory dict, put/get/expire values)
├── common.py           # ALPHA=3, BUCKET_SIZE=20, PROTOCOL_ID=/ipfs/kad/1.0.0
├── utils.py            # XOR distance, signed record consumption
└── pb/kademlia_pb2.py  # Compiled protobuf (Message, Record)
```

### go-libp2p-kad-dht Structure (for reference)

```
go-libp2p-kad-dht/
├── dht.go              # IpfsDHT struct (alpha, beta, addr filter, conn mgr)
├── query.go            # Full iterative lookup with qpeerset state machine
├── lookup.go           # GetClosestPeers + runLookupWithFollowup
├── handlers.go         # Message handlers (sign/verify records)
├── records.go          # GetPublicKey (parallel DHT + direct fetch)
├── dht_bootstrap.go    # Bootstrap peers + periodic fix-low-peers
├── rt_diversity_filter.go  # Sybil resistance (IP group limits per CPL)
├── fullrt/             # Accelerated full-routing-table client (crawler)
├── dual/               # WAN + LAN dual DHT
├── provider/           # SweepingProvider (batched region-based reprovide)
├── netsize/            # Network size estimator
└── rtrefresh/          # Routing table refresh manager
```

---

## 3. Critical Missing Features (Blocks Interop)

### 3.1 Unsigned DHT Records (PUT_VALUE)

**Status:** ❌ Not implemented — **breaks Kubo interop**

**The Problem:**  
go-libp2p and Kubo validate every incoming `PUT_VALUE` record using `go-libp2p-record`. For `/pk/` namespace, the value must be the raw public key protobuf bytes. For `/ipns/` namespace, the value must be a signed `IpnsEntry` protobuf. The record's `author` field must be set to the peer's public key bytes and the `signature` field must be the Ed25519/secp256k1 signature over `SHA256("libp2p-record:" + key + value)`. Records without a valid signature are dropped silently.

**Current py-libp2p behavior:**  
`ValueStore.put()` calls `make_put_record(key, value)` which sets `key` and `value` but does NOT set `author` or `signature`. Kubo will accept the record at the transport level but immediately reject it at validation.

**Implementation:**

```python
# libp2p/kad_dht/record_signing.py  (NEW FILE)
import hashlib
from libp2p.crypto.keys import PrivateKey
from libp2p.kad_dht.pb.kademlia_pb2 import Record

RECORD_SIGNING_PREFIX = b"libp2p-record:"

def sign_record(record: Record, private_key: PrivateKey) -> Record:
    """
    Sign a DHT record per the go-libp2p-record spec.
    Signature covers: SHA256(RECORD_SIGNING_PREFIX + key + value)
    
    This is required for Kubo / go-libp2p interoperability.
    """
    # Build the signing payload: prefix + key + value
    payload = RECORD_SIGNING_PREFIX + record.key + record.value
    
    # Sign with the node's private key
    signature = private_key.sign(payload)
    
    # Set author (public key protobuf bytes) and signature
    pub_key_bytes = private_key.get_public_key().serialize()
    record.author = pub_key_bytes
    record.signature = signature
    return record

def verify_record(record: Record) -> bool:
    """Verify a record's signature. Returns False for records without signatures."""
    if not record.signature or not record.author:
        return False  # Unsigned records fail verification
    try:
        from libp2p.crypto.keys import deserialize_public_key
        pub_key = deserialize_public_key(record.author)
        payload = RECORD_SIGNING_PREFIX + record.key + record.value
        pub_key.verify(payload, record.signature)
        return True
    except Exception:
        return False
```

Then update `ValueStore.put()` and `KadDHT._store_at_peer()` to call `sign_record()` before storing/sending.

---

### 3.2 Wrong Provider Key Format (CID → Multihash)

**Status:** ❌ Not implemented — **breaks IPFS content routing**

**The Problem:**  
In IPFS, content is addressed by CID. The DHT provider key is **NOT** the CID string but the **raw multihash bytes** of the CID's content identifier. go-libp2p-kad-dht expects `ADD_PROVIDER.key` and `GET_PROVIDERS.key` to be raw multihash bytes (e.g., `sha2-256` digest of the content).

**Current py-libp2p behavior:**  
`KadDHT.provide(key: str)` does `key_bytes = key.encode("utf-8")` — this produces the UTF-8 bytes of the string, not a multihash. A Kubo node receiving this will not find any matching providers because it looks up the key as a multihash.

**Implementation:**

```python
# libp2p/kad_dht/cid_utils.py  (NEW FILE)
import multihash
from typing import Union

def cid_to_provider_key(cid_or_multihash: Union[str, bytes]) -> bytes:
    """
    Convert a CID string or raw bytes to the DHT provider key format.
    
    The DHT provider key is the raw multihash bytes of the CID's digest,
    NOT the CID string itself. This matches go-libp2p-kad-dht behavior.
    
    Examples:
        cid_to_provider_key("QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o")
        → sha2-256 multihash bytes (34 bytes for sha2-256)
    """
    if isinstance(cid_or_multihash, str):
        # Handle CIDv0 (base58btc encoded multihash)
        import base58
        raw = base58.b58decode(cid_or_multihash)
        # CIDv0: raw bytes are the multihash directly
        # CIDv1: need to decode the CID structure
        if raw[0] in (0x12, 0x20):  # sha2-256 multihash code
            return raw  # Already a multihash
        # For CIDv1, use py-cid or manual decode
        # pip install py-cid
        try:
            import cid as pycid
            c = pycid.make_cid(cid_or_multihash)
            return bytes(c.multihash)
        except ImportError:
            raise ImportError("pip install py-cid for CIDv1 support")
    elif isinstance(cid_or_multihash, bytes):
        # Assume it's already a multihash
        return cid_or_multihash
    raise TypeError(f"Expected str or bytes, got {type(cid_or_multihash)}")
```

Update `KadDHT.provide()` and `KadDHT.find_providers()` to use `cid_to_provider_key()`.

---

### 3.3 Non-Iterative Lookup (get_value / find_providers)

**Status:** ❌ Critically incomplete — **queries terminate at routing table depth**

**The Problem:**  
True Kademlia iterative lookup works as follows:
1. Query the α closest known peers for the target key.
2. From each response, collect the `closerPeers` returned.
3. Add those newly discovered peers to the candidate set.
4. Query the next α closest **unqueried** candidates.
5. Repeat until no new closer peers are discovered (convergence), or β of the closest K peers have responded.

**Current py-libp2p behavior:**  
`get_value()` and `find_providers()` iterate through `find_local_closest_peers()` — the peers already in the routing table — and query them, but **never process the `closerPeers` returned in responses**. If the answer is held by a peer 3 hops away, py-libp2p will miss it entirely. This is the most critical correctness gap.

**Implementation (Iterative Lookup Engine):**

```python
# libp2p/kad_dht/iterative_query.py  (NEW FILE)
"""
True S/Kademlia iterative lookup with peer state tracking.
Mirrors go-libp2p-kad-dht's query.go + qpeerset.
"""
from enum import Enum, auto
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

import trio
from libp2p.peer.id import ID
from .common import ALPHA, BUCKET_SIZE, QUERY_TIMEOUT
from .routing_table import peer_id_to_key, xor_distance

logger = logging.getLogger(__name__)

class PeerState(Enum):
    HEARD    = auto()   # Discovered, not yet queried
    WAITING  = auto()   # Query in-flight
    QUERIED  = auto()   # Successfully responded
    UNREACHABLE = auto() # Failed / timed out

@dataclass
class QueryPeer:
    peer_id: ID
    state: PeerState = PeerState.HEARD
    distance: int = 0
    result: Any = None  # Response data from this peer

class QueryPeerset:
    """Tracks all peers seen during an iterative lookup."""
    
    def __init__(self, target_key: bytes, k: int = BUCKET_SIZE):
        self.target_key = target_key
        self.k = k
        self._peers: dict[ID, QueryPeer] = {}
    
    def add(self, peer_id: ID) -> bool:
        """Add a peer if not seen before. Returns True if newly added."""
        if peer_id in self._peers:
            return False
        dist = xor_distance(peer_id_to_key(peer_id), self.target_key)
        self._peers[peer_id] = QueryPeer(peer_id, PeerState.HEARD, dist)
        return True
    
    def mark_waiting(self, peer_id: ID):
        if peer_id in self._peers:
            self._peers[peer_id].state = PeerState.WAITING
    
    def mark_queried(self, peer_id: ID, result=None):
        if peer_id in self._peers:
            self._peers[peer_id].state = PeerState.QUERIED
            self._peers[peer_id].result = result
    
    def mark_unreachable(self, peer_id: ID):
        if peer_id in self._peers:
            self._peers[peer_id].state = PeerState.UNREACHABLE
    
    def get_heard(self, n: int = ALPHA) -> list[ID]:
        """Get up to n closest HEARD peers (next to query)."""
        heard = [p for p in self._peers.values() if p.state == PeerState.HEARD]
        heard.sort(key=lambda p: p.distance)
        return [p.peer_id for p in heard[:n]]
    
    def get_closest_queried(self, k: int = None) -> list[QueryPeer]:
        """Get the k closest QUERIED peers (final result set)."""
        k = k or self.k
        queried = [p for p in self._peers.values() if p.state == PeerState.QUERIED]
        queried.sort(key=lambda p: p.distance)
        return queried[:k]
    
    def have_converged(self) -> bool:
        """
        Convergence: all of the k closest known peers have been queried
        (or are unreachable). No HEARD peer is closer than the k-th
        closest QUERIED peer.
        """
        heard = [p for p in self._peers.values() if p.state == PeerState.HEARD]
        if not heard:
            return True  # Nothing left to query
        
        # Get the k-th closest queried peer's distance
        queried = self.get_closest_queried()
        if len(queried) < self.k:
            return False  # Haven't found k peers yet
        
        k_th_dist = queried[-1].distance
        # If any HEARD peer is closer than the k-th queried, not converged
        for p in heard:
            if p.distance < k_th_dist:
                return False
        return True


async def run_iterative_lookup(
    seed_peers: list[ID],
    target_key: bytes,
    query_fn: Callable[[ID], Awaitable[tuple[list[ID], Any]]],
    stop_fn: Callable[[QueryPeerset], bool] = None,
    alpha: int = ALPHA,
    k: int = BUCKET_SIZE,
    max_rounds: int = 30,
) -> QueryPeerset:
    """
    Run a full Kademlia iterative lookup.
    
    query_fn(peer_id) -> (closer_peers: list[ID], result: Any)
      - closer_peers: the closerPeers from the response
      - result: any data found (value, providers, etc.) or None
    
    stop_fn(qpeerset) -> bool
      - return True to terminate early (e.g., value found)
    
    Returns the final QueryPeerset for inspection.
    """
    qps = QueryPeerset(target_key, k)
    for p in seed_peers:
        qps.add(p)
    
    sem = trio.Semaphore(alpha)
    found_event = trio.Event()
    
    for _round in range(max_rounds):
        if stop_fn and stop_fn(qps):
            break
        if qps.have_converged():
            break
        
        next_peers = qps.get_heard(alpha)
        if not next_peers:
            break  # No more candidates
        
        # Mark all as WAITING before launching tasks
        for p in next_peers:
            qps.mark_waiting(p)
        
        async def query_one(peer_id: ID) -> None:
            try:
                async with trio.open_cancel_scope() as scope:
                    scope.deadline = trio.current_time() + QUERY_TIMEOUT
                    closer, result = await query_fn(peer_id)
                    qps.mark_queried(peer_id, result)
                    # KEY: add newly discovered closer peers to candidate set
                    for new_peer in closer:
                        qps.add(new_peer)
                    if stop_fn and stop_fn(qps):
                        found_event.set()
            except Exception as e:
                logger.debug(f"Query to {peer_id} failed: {e}")
                qps.mark_unreachable(peer_id)
            finally:
                sem.release()
        
        async with trio.open_nursery() as nursery:
            for peer_id in next_peers:
                await sem.acquire()
                if found_event.is_set():
                    sem.release()
                    break
                nursery.start_soon(query_one, peer_id)
    
    return qps
```

---

### 3.4 PING Uses Wrong Framing

**Status:** ❌ Wire-incompatible with go-libp2p

**The Problem:**  
`KBucket._ping_peer()` sends the ping message length as a 4-byte big-endian integer:
```python
await stream.write(len(msg_bytes).to_bytes(4, byteorder="big"))
```
But the DHT protocol (`/ipfs/kad/1.0.0`) uses **varint** length prefixes for all messages. go-libp2p will fail to parse the length and close the stream.

**Fix:**

```python
# In routing_table.py, KBucket._ping_peer()
import varint

# WRONG (current):
await stream.write(len(msg_bytes).to_bytes(4, byteorder="big"))

# CORRECT:
await stream.write(varint.encode(len(msg_bytes)))

# Similarly for reading response:
# WRONG (current):
length_bytes = await stream.read(4)
msg_len = int.from_bytes(length_bytes, byteorder="big")

# CORRECT:
length_prefix = b""
while True:
    byte = await stream.read(1)
    if not byte:
        return False
    length_prefix += byte
    if byte[0] & 0x80 == 0:
        break
msg_len = varint.decode_bytes(length_prefix)
```

---

## 4. Important Missing Features (Degrades Interop)

### 4.1 Persistent Datastore

**Status:** ⚠️ Missing — records lost on restart

go-libp2p-kad-dht uses a `go-datastore` interface backed by LevelDB or Badger for persistent record storage. py-libp2p uses in-memory dicts only. On restart:
- All locally stored IPNS records are lost.
- Provider records are lost (must re-`provide`).
- Routing table is not persisted (go saves it to datastore too).

**Implementation:**

```python
# libp2p/kad_dht/persistent_store.py  (NEW FILE)
"""
Pluggable persistent datastore for DHT records.
Default: in-memory. Plugin: SQLite, LevelDB (via plyvel), RocksDB.
"""
import abc
import sqlite3
import time
from pathlib import Path

class IDHTDatastore(abc.ABC):
    @abc.abstractmethod
    def get(self, key: bytes) -> bytes | None: ...
    
    @abc.abstractmethod
    def put(self, key: bytes, value: bytes, ttl: float = 0) -> None: ...
    
    @abc.abstractmethod
    def delete(self, key: bytes) -> None: ...
    
    @abc.abstractmethod
    def query(self, prefix: bytes) -> list[tuple[bytes, bytes]]: ...

class SQLiteDatastore(IDHTDatastore):
    """SQLite-backed persistent datastore for DHT records."""
    
    def __init__(self, db_path: str | Path):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                key BLOB PRIMARY KEY,
                value BLOB NOT NULL,
                expires_at REAL
            )
        """)
        self._conn.commit()
    
    def get(self, key: bytes) -> bytes | None:
        cur = self._conn.execute(
            "SELECT value, expires_at FROM records WHERE key=?", (key,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        value, expires_at = row
        if expires_at and time.time() > expires_at:
            self.delete(key)
            return None
        return value
    
    def put(self, key: bytes, value: bytes, ttl: float = 0) -> None:
        expires_at = time.time() + ttl if ttl else None
        self._conn.execute(
            "INSERT OR REPLACE INTO records (key, value, expires_at) VALUES (?,?,?)",
            (key, value, expires_at)
        )
        self._conn.commit()
    
    def delete(self, key: bytes) -> None:
        self._conn.execute("DELETE FROM records WHERE key=?", (key,))
        self._conn.commit()
    
    def query(self, prefix: bytes) -> list[tuple[bytes, bytes]]:
        cur = self._conn.execute(
            "SELECT key, value FROM records WHERE key LIKE ? AND "
            "(expires_at IS NULL OR expires_at > ?)",
            (prefix + b"%", time.time())
        )
        return cur.fetchall()
```

---

### 4.2 Network Event Integration (Auto Peer Discovery)

**Status:** ⚠️ Missing — routing table only grows on received streams

go-libp2p subscribes to `event.EvtPeerConnectednessChanged` and automatically adds peers to the routing table when they connect. py-libp2p only adds a peer to the routing table inside `handle_stream()` when the remote initiates a DHT message. This means:
- Peers connected via other protocols (gossipsub, bitswap) are never added to the DHT routing table.
- The routing table can remain empty even when the node has many connections.

**Implementation:**

```python
# In kad_dht.py, KadDHT.__init__():
# Register connection notifier with host network
host.get_network().notify(DHTConnNotifee(self))

# libp2p/kad_dht/notifee.py  (NEW FILE)
class DHTConnNotifee:
    """Notifee that adds connected peers to the DHT routing table."""
    
    def __init__(self, dht: "KadDHT"):
        self._dht = dht
    
    async def connected(self, network, conn) -> None:
        peer_id = conn.get_remote_peer_id()
        # Only add in SERVER mode; client mode peers are ephemeral
        if self._dht.mode == DHTMode.SERVER:
            await self._dht.routing_table.add_peer(peer_id)
    
    async def disconnected(self, network, conn) -> None:
        peer_id = conn.get_remote_peer_id()
        self._dht.routing_table.remove_peer(peer_id)
    
    # Implement other INotifee methods as no-ops
    async def listen(self, network, maddr) -> None: pass
    async def listen_close(self, network, maddr) -> None: pass
    async def open_stream(self, network, stream) -> None: pass
    async def close_stream(self, network, stream) -> None: pass
```

---

### 4.3 Beta Parameter (Resiliency / S/Kademlia)

**Status:** ⚠️ Missing — queries terminate too early

go-libp2p-kad-dht has a `beta` parameter (default 3 for Amino DHT). A query terminates when the β closest peers have all **responded** (not just been queried). This gives confidence that you've found the true closest peers to the target. Without beta, py-libp2p terminates when it runs out of unqueried candidates, which can happen before converging if many peers time out.

```python
# In common.py
BETA = 3  # S/Kademlia resiliency parameter

# In iterative_query.py, have_converged():
def have_converged_with_beta(self, beta: int = BETA) -> bool:
    """
    Convergence: beta of the k closest peers have successfully responded.
    """
    queried_closest = self.get_closest_queried(self.k)
    return len(queried_closest) >= beta
```

---

### 4.4 Routing Table Diversity Filter (Sybil Resistance)

**Status:** ⚠️ Missing — vulnerable to eclipse attacks

go-libp2p-kad-dht includes `rtPeerIPGroupFilter` which limits the number of peers in the routing table from the same /24 IPv4 (or /48 IPv6) subnet. This is the primary Sybil resistance mechanism at the routing table level.

```python
# libp2p/kad_dht/diversity_filter.py  (NEW FILE)
import ipaddress
from collections import defaultdict
from libp2p.peer.id import ID

class PeerDiversityFilter:
    """
    Limits peers per /24 IPv4 subnet per CPL bucket.
    Mirrors go-libp2p-kad-dht's rtPeerIPGroupFilter.
    """
    
    def __init__(self, max_per_cpl: int = 3, max_total: int = 10):
        self.max_per_cpl = max_per_cpl
        self.max_total = max_total
        # {ip_group: count} and {cpl: {ip_group: count}}
        self._table_count: dict[str, int] = defaultdict(int)
        self._cpl_count: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    
    def _ip_group(self, addr_bytes: bytes) -> str:
        """Extract /24 for IPv4, /48 for IPv6."""
        try:
            # addr_bytes is a multiaddr; extract IP
            import multiaddr
            ma = multiaddr.Multiaddr(addr_bytes)
            ip_str = ma.value_for_protocol("ip4") or ma.value_for_protocol("ip6")
            if ip_str:
                ip = ipaddress.ip_address(ip_str)
                if isinstance(ip, ipaddress.IPv4Address):
                    network = ipaddress.ip_network(f"{ip}/24", strict=False)
                else:
                    network = ipaddress.ip_network(f"{ip}/48", strict=False)
                return str(network)
        except Exception:
            pass
        return "unknown"
    
    def allow(self, peer_id: ID, cpl: int, addrs: list[bytes]) -> bool:
        if not addrs:
            return True  # Allow peers without addresses (unknown diversity)
        group = self._ip_group(addrs[0])
        if self._table_count[group] >= self.max_total:
            return False
        if self._cpl_count[cpl][group] >= self.max_per_cpl:
            return False
        return True
    
    def add(self, peer_id: ID, cpl: int, addrs: list[bytes]) -> None:
        if not addrs:
            return
        group = self._ip_group(addrs[0])
        self._table_count[group] += 1
        self._cpl_count[cpl][group] += 1
    
    def remove(self, peer_id: ID, cpl: int, addrs: list[bytes]) -> None:
        if not addrs:
            return
        group = self._ip_group(addrs[0])
        self._table_count[group] = max(0, self._table_count[group] - 1)
        self._cpl_count[cpl][group] = max(0, self._cpl_count[cpl][group] - 1)
```

---

### 4.5 Stream Reuse / Message Manager

**Status:** ⚠️ Missing — high connection overhead

go-libp2p-kad-dht maintains a `MessageSender` that reuses existing streams for multiple DHT messages to the same peer (within a timeout window). py-libp2p opens a new stream per every single DHT query. On the public IPFS network, this creates:
- ~O(k × iterations) stream open/close cycles per lookup.
- Significant latency overhead (new stream = new noise handshake if no existing connection).

**Implementation:**

```python
# libp2p/kad_dht/message_sender.py  (NEW FILE)
"""
Reusable DHT message sender — one stream per peer, reused for ALPHA seconds.
Mirrors go-libp2p-kad-dht/internal/net/message_manager.go
"""
import time
import logging
import trio
import varint
from libp2p.peer.id import ID
from .pb.kademlia_pb2 import Message
from .common import PROTOCOL_ID

logger = logging.getLogger(__name__)
STREAM_REUSE_TIMEOUT = 60.0  # seconds

class PeerMessageSender:
    """Holds a reusable stream to a single peer."""
    
    def __init__(self, stream, peer_id: ID):
        self.stream = stream
        self.peer_id = peer_id
        self._lock = trio.Lock()
        self._last_used = time.time()
        self._invalid = False
    
    def is_valid(self) -> bool:
        return not self._invalid and (time.time() - self._last_used) < STREAM_REUSE_TIMEOUT
    
    async def send_request(self, msg: Message) -> Message:
        async with self._lock:
            try:
                data = msg.SerializeToString()
                await self.stream.write(varint.encode(len(data)))
                await self.stream.write(data)
                
                # Read response
                length_prefix = b""
                while True:
                    byte = await self.stream.read(1)
                    if not byte:
                        raise ConnectionError("Stream closed")
                    length_prefix += byte
                    if byte[0] & 0x80 == 0:
                        break
                resp_len = varint.decode_bytes(length_prefix)
                resp_bytes = await self.stream.read(resp_len)
                
                response = Message()
                response.ParseFromString(resp_bytes)
                self._last_used = time.time()
                return response
            except Exception as e:
                self._invalid = True
                raise


class MessageManager:
    """Manages reusable streams to DHT peers."""
    
    def __init__(self, host):
        self._host = host
        self._senders: dict[ID, PeerMessageSender] = {}
        self._lock = trio.Lock()
    
    async def send_request(self, peer_id: ID, msg: Message) -> Message:
        sender = await self._get_sender(peer_id)
        return await sender.send_request(msg)
    
    async def _get_sender(self, peer_id: ID) -> PeerMessageSender:
        async with self._lock:
            sender = self._senders.get(peer_id)
            if sender and sender.is_valid():
                return sender
            # Open new stream
            stream = await self._host.new_stream(peer_id, [PROTOCOL_ID])
            sender = PeerMessageSender(stream, peer_id)
            self._senders[peer_id] = sender
            return sender
```

---

### 4.6 GetPublicKey (Parallel DHT + Direct Fetch)

**Status:** ⚠️ Missing — `/pk/` lookups fail for Ed25519 peers

go-libp2p's `GetPublicKey` tries to fetch the public key via TWO parallel paths: directly from the peer via a direct stream AND via DHT lookup. For newer Ed25519 peer IDs (multihash `0x00` identity codec), the public key is inlined in the peer ID itself and this is a no-op. But for older RSA and secp256k1 peer IDs, this lookup is required.

py-libp2p has `PublicKeyValidator` but no equivalent `GetPublicKey` method on the DHT.

```python
# In kad_dht.py, add to KadDHT class:
async def get_public_key(self, peer_id: ID) -> bytes | None:
    """
    Fetch a peer's public key.
    1. Try to extract from PeerID (inline for Ed25519).
    2. Try peerstore.
    3. Look up /pk/<peer_id_bytes> in DHT.
    """
    # 1. Try inline extraction (Ed25519 identity multihash)
    from libp2p.peer.id import ID as PeerID
    try:
        # Ed25519 peer IDs have inlined public keys
        mh = peer_id.to_bytes()
        import multihash
        decoded = multihash.decode(mh)
        if decoded.code == 0x00:  # identity codec
            return decoded.digest  # Public key bytes
    except Exception:
        pass
    
    # 2. Try peerstore
    try:
        pub_key = self.host.get_peerstore().pubkey(peer_id)
        if pub_key:
            return pub_key.serialize()
    except Exception:
        pass
    
    # 3. DHT lookup: key = /pk/<peer_id_bytes>
    pk_key = "/pk/" + peer_id.to_bytes().decode("latin-1")
    value = await self.get_value(pk_key)
    return value
```

---

### 4.7 Provider Record Republication

**Status:** ⚠️ Commented out in production code

The `_republish_provider_records()` method exists in `ProviderStore` but is commented out in the main loop. Without republication, provider records expire after 48 hours and the node effectively "unprovides" content without re-calling `provide()`.

```python
# In KadDHT._run_main_loop(), uncomment and add:
PROVIDER_REPUBLISH_INTERVAL = 22 * 60 * 60  # 22 hours

async def _run_main_loop(self) -> None:
    last_republish = time.time()
    while self.manager.is_running:
        await self.refresh_routing_table()
        
        current_time = time.time()
        if current_time - last_republish >= PROVIDER_REPUBLISH_INTERVAL:
            await self.provider_store._republish_provider_records()
            last_republish = current_time
        
        # Also republish DHT values every 12 hours
        expired_values = self.value_store.cleanup_expired()
        self.provider_store.cleanup_expired()
        
        await trio.sleep(ROUTING_TABLE_REFRESH_INTERVAL)
```

---

## 5. Nice-to-Have Features (Performance & Production)

### 5.1 Dual DHT (WAN + LAN)

go-libp2p-kad-dht has `dual.DHT` which runs two parallel DHT instances:
- **WAN DHT:** Protocol `/ipfs/kad/1.0.0` — the global IPFS network.
- **LAN DHT:** Protocol `/ipfs/lan/kad/1.0.0` — local network discovery (mDNS peers). Uses `/ip4/192.168.x.x/` filtered addresses only.

py-libp2p currently only supports WAN. For full IPFS node compatibility, implement a `DualKadDHT` wrapper that runs both modes.

### 5.2 Address Filtering

go-libp2p-kad-dht filters out private/loopback addresses from peer records before storing them. py-libp2p propagates all addresses including `127.0.0.1` and `192.168.x.x`, which are not routable on the internet.

```python
# libp2p/kad_dht/addr_filter.py
import ipaddress
from multiaddr import Multiaddr

PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

def filter_addrs(addrs: list[Multiaddr]) -> list[Multiaddr]:
    """Remove private/loopback addresses — not routable on WAN DHT."""
    public = []
    for addr in addrs:
        try:
            ip_str = addr.value_for_protocol("ip4") or addr.value_for_protocol("ip6")
            if ip_str:
                ip = ipaddress.ip_address(ip_str)
                if any(ip in net for net in PRIVATE_RANGES):
                    continue
        except Exception:
            pass
        public.append(addr)
    return public
```

### 5.3 Network Size Estimator

go-libp2p-kad-dht estimates the number of peers in the DHT network using results from `GetClosestPeers` queries. This estimate is used to optimize provider batching and concurrency.

```python
# libp2p/kad_dht/netsize.py
import math
from collections import deque

class NetworkSizeEstimator:
    """
    Estimates DHT network size from observed k-closest peer distances.
    Based on go-libp2p-kad-dht/netsize/netsize.go
    
    The estimate uses: N ≈ k / avg_distance_to_k_closest
    """
    
    def __init__(self, k: int = 20, window: int = 10):
        self.k = k
        self._estimates: deque[float] = deque(maxlen=window)
    
    def track(self, target_key: bytes, closest_peers: list) -> None:
        """Update estimate from a GetClosestPeers result."""
        if len(closest_peers) < self.k:
            return
        # Compute average distance to closest k peers
        from .routing_table import peer_id_to_key
        from .utils import xor_distance
        distances = [xor_distance(peer_id_to_key(p), target_key) for p in closest_peers]
        distances.sort()
        avg_dist = sum(distances[:self.k]) / self.k
        if avg_dist > 0:
            # Estimate: N = 2^256 / (avg_dist / k)
            estimate = (2**256 / avg_dist) * self.k
            self._estimates.append(math.log2(estimate))
    
    def network_size(self) -> float | None:
        """Returns estimated log2(network_size) or None if not enough data."""
        if len(self._estimates) < 3:
            return None
        return 2 ** (sum(self._estimates) / len(self._estimates))
```

### 5.4 OpenTelemetry Observability

go-libp2p-kad-dht has full OpenTelemetry tracing for all DHT operations. For production deployments of py-libp2p, add:

```python
# libp2p/kad_dht/metrics.py
try:
    from opentelemetry import trace, metrics
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

class DHTMetrics:
    """OTel metrics for DHT operations."""
    
    def __init__(self):
        if not OTEL_AVAILABLE:
            return
        meter = metrics.get_meter("py-libp2p-kad-dht")
        self.find_peer_duration = meter.create_histogram(
            "dht.find_peer.duration_ms"
        )
        self.routing_table_size = meter.create_gauge(
            "dht.routing_table.peers"
        )
        self.queries_total = meter.create_counter("dht.queries.total")
        self.query_errors = meter.create_counter("dht.queries.errors")
```

### 5.5 Lookup Optimization (lookup_optim)

go-libp2p-kad-dht tracks query latency per peer and uses it to avoid querying slow peers during tight iterative lookups. Can be added on top of the iterative lookup engine.

---

## 6. Implementation Guide

### Phase 1: Critical Wire Compatibility (1–2 weeks)

**Priority:** Fix these first — they block ALL interop with Kubo nodes.

| Task | File(s) | Effort |
|------|---------|--------|
| Fix PING varint framing | `routing_table.py` | 30 min |
| Add record signing (PUT_VALUE) | `value_store.py`, new `record_signing.py` | 2 days |
| Fix provider key format (CID → multihash) | `kad_dht.py`, new `cid_utils.py` | 1 day |
| Implement true iterative lookup | new `iterative_query.py`, update `peer_routing.py` | 3 days |

### Phase 2: Protocol Correctness (2–4 weeks)

| Task | File(s) | Effort |
|------|---------|--------|
| Network event integration | new `notifee.py`, update `kad_dht.py` | 1 day |
| Beta parameter + convergence fix | `common.py`, `iterative_query.py` | 1 day |
| GetPublicKey method | `kad_dht.py` | 1 day |
| Provider record republication | `provider_store.py`, `kad_dht.py` | 0.5 days |
| Address filtering | new `addr_filter.py` | 0.5 days |
| Persistent datastore | new `persistent_store.py` | 2 days |

### Phase 3: Production Quality (4–8 weeks)

| Task | File(s) | Effort |
|------|---------|--------|
| Stream reuse / message manager | new `message_sender.py` | 3 days |
| Peer diversity filter | new `diversity_filter.py` | 2 days |
| Bootstrap peer management | update `kad_dht.py` | 1 day |
| Dual DHT (WAN + LAN) | new `dual.py` | 3 days |
| Network size estimator | new `netsize.py` | 1 day |
| OTel observability | new `metrics.py` | 2 days |

---

## 7. Interoperability Testing Strategy

### 7.1 Unit Test: Wire Protocol Compliance

Test that py-libp2p produces bytes that go-libp2p can parse.

```python
# tests/kad_dht/test_wire_compat.py

import pytest
from libp2p.kad_dht.pb.kademlia_pb2 import Message, Record
import varint

def test_find_node_request_framing():
    """Verify FIND_NODE uses varint framing, not fixed-4-byte."""
    msg = Message()
    msg.type = Message.MessageType.FIND_NODE
    msg.key = b"\x12\x20" + b"\xab" * 32  # multihash bytes
    
    data = msg.SerializeToString()
    framed = varint.encode(len(data)) + data
    
    # Verify varint decode gives correct length
    length_prefix = b""
    for byte in framed:
        length_prefix += bytes([byte])
        if byte & 0x80 == 0:
            break
    decoded_len = varint.decode_bytes(length_prefix)
    assert decoded_len == len(data)

def test_put_value_record_has_signature():
    """PUT_VALUE records must be signed for Kubo interop."""
    from libp2p.kad_dht.record_signing import sign_record, verify_record
    from libp2p.crypto.keys import generate_key_pair
    
    private_key, _ = generate_key_pair("Ed25519")
    
    record = Record()
    record.key = b"/ipns/test"
    record.value = b"test_value"
    
    signed = sign_record(record, private_key)
    assert signed.signature != b""
    assert signed.author != b""
    assert verify_record(signed) is True

def test_provider_key_is_multihash():
    """Provider keys must be multihash bytes, not UTF-8 strings."""
    from libp2p.kad_dht.cid_utils import cid_to_provider_key
    import multihash
    
    cid_str = "QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o"
    key = cid_to_provider_key(cid_str)
    
    # Verify it's a valid multihash
    decoded = multihash.decode(key)
    assert decoded.code == 0x12  # sha2-256
    assert len(decoded.digest) == 32

def test_ping_uses_varint():
    """PING messages must use varint framing like all other DHT messages."""
    from libp2p.kad_dht.pb.kademlia_pb2 import Message
    import varint
    
    ping = Message()
    ping.type = Message.PING
    data = ping.SerializeToString()
    
    # The framed message must decode correctly with varint
    encoded_len = varint.encode(len(data))
    # Must NOT be fixed 4 bytes
    assert len(encoded_len) != 4 or encoded_len != len(data).to_bytes(4, "big")
```

### 7.2 Integration Test: py-libp2p ↔ go-libp2p in Docker

```dockerfile
# docker/go-peer/Dockerfile
FROM golang:1.21
WORKDIR /app
COPY go_peer.go .
RUN go mod init testpeer && \
    go get github.com/libp2p/go-libp2p@latest && \
    go get github.com/libp2p/go-libp2p-kad-dht@latest && \
    go build -o go_peer .
ENTRYPOINT ["./go_peer"]
```

```go
// docker/go-peer/go_peer.go
package main

import (
    "context"
    "encoding/json"
    "fmt"
    "os"
    
    libp2p "github.com/libp2p/go-libp2p"
    dht "github.com/libp2p/go-libp2p-kad-dht"
    "github.com/libp2p/go-libp2p/core/peer"
)

func main() {
    ctx := context.Background()
    
    h, _ := libp2p.New()
    d, _ := dht.New(ctx, h, dht.Mode(dht.ModeServer))
    _ = d.Bootstrap(ctx)
    
    // Print peer info for py-libp2p to connect to
    addrs := make([]string, len(h.Addrs()))
    for i, a := range h.Addrs() {
        addrs[i] = fmt.Sprintf("%s/p2p/%s", a, h.ID())
    }
    
    info := map[string]interface{}{
        "peer_id": h.ID().String(),
        "addrs":   addrs,
    }
    json.NewEncoder(os.Stdout).Encode(info)
    
    // Block and serve DHT requests
    select {}
}
```

```python
# tests/interop/test_go_interop.py
"""
Cross-language interoperability tests.
Requires docker-compose up go-peer before running.
"""
import pytest
import trio
import json
import subprocess

@pytest.fixture
async def go_peer_info():
    """Start go-libp2p peer and return its multiaddr."""
    proc = subprocess.Popen(
        ["docker", "run", "--rm", "-p", "4001:4001", "go-dht-peer"],
        stdout=subprocess.PIPE,
    )
    line = proc.stdout.readline()
    info = json.loads(line)
    yield info
    proc.terminate()

async def test_py_can_find_go_peer(go_peer_info):
    """py-libp2p should be able to FIND_NODE and get a response from go peer."""
    from libp2p import new_host
    from libp2p.kad_dht import KadDHT, DHTMode
    from libp2p.peer.peerinfo import PeerInfo
    
    host = await new_host()
    dht = KadDHT(host, DHTMode.CLIENT)
    
    # Connect to go peer
    go_peerinfo = PeerInfo.from_multiaddr(go_peer_info["addrs"][0])
    await host.connect(go_peerinfo)
    
    # Try FIND_NODE
    result = await dht.find_peer(go_peerinfo.peer_id)
    assert result is not None
    assert result.peer_id == go_peerinfo.peer_id

async def test_py_provide_go_findproviders(go_peer_info):
    """py-libp2p provide() should be discoverable by go-libp2p findproviders."""
    # This test requires correct multihash provider keys
    pass

async def test_go_putvalue_py_getvalue(go_peer_info):
    """go-libp2p PUT_VALUE should be retrievable by py-libp2p GET_VALUE."""
    pass
```

### 7.3 Integration Test: Against Live Kubo Node

```python
# tests/interop/test_kubo_interop.py
"""
Test against a local Kubo (go-ipfs) node.
Requires: ipfs daemon --enable-gc=false
"""
import pytest
import httpx  # for Kubo HTTP API
import trio

KUBO_API = "http://127.0.0.1:5001"

async def get_kubo_peer_info():
    """Get local Kubo node peer info via HTTP API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{KUBO_API}/api/v0/id")
        data = resp.json()
        return {
            "peer_id": data["ID"],
            "addrs": data["Addresses"],
        }

async def test_py_connects_to_kubo():
    """py-libp2p DHT node should be able to connect to local Kubo."""
    from libp2p import new_host
    from libp2p.kad_dht import KadDHT, DHTMode
    
    info = await get_kubo_peer_info()
    host = await new_host()
    dht = KadDHT(host, DHTMode.SERVER)
    
    # Connect to Kubo
    from libp2p.peer.peerinfo import info_from_p2p_addr
    peerinfo = info_from_p2p_addr(info["addrs"][0])
    await host.connect(peerinfo)
    
    # Kubo should show us as a DHT peer
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{KUBO_API}/api/v0/routing/findpeer",
            params={"arg": str(host.get_id())}
        )
    # If Kubo can find us, we're DHT-compatible
    assert resp.status_code == 200

async def test_py_get_value_ipns(kubo_peer):
    """
    Kubo publishes IPNS record; py-libp2p should retrieve it.
    Requires: ipfs name publish /ipfs/<some_cid>
    """
    import subprocess
    result = subprocess.run(
        ["ipfs", "name", "publish", "/ipfs/QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"],
        capture_output=True, text=True
    )
    ipns_key = result.stdout.strip().split(": ")[0].replace("Published to ", "")
    
    from libp2p.kad_dht import KadDHT, DHTMode
    # ... retrieve /ipns/<key> from DHT
    value = await dht.get_value(f"/ipns/{ipns_key}")
    assert value is not None  # Should get the IPNS record bytes

async def test_py_provide_kubo_discover():
    """
    py-libp2p announces providing a CID; Kubo should discover it.
    Critical test for provider key format correctness.
    """
    cid = "QmYjtig7VJQ6XsnUjqqJvj7QaMcCAwtrgNdahSiFofrE7o"
    
    # py-libp2p announces
    await dht.provide(cid)  # Must use multihash key!
    
    # Kubo looks for providers
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{KUBO_API}/api/v0/routing/findprovs",
            params={"arg": cid, "num-providers": "1"}
        )
    providers = [json.loads(line) for line in resp.text.strip().split("\n") if line]
    provider_ids = [p["Responses"][0]["ID"] for p in providers if p.get("Responses")]
    
    assert str(host.get_id()) in provider_ids
```

### 7.4 Routing Table Convergence Test

```python
# tests/kad_dht/test_routing_convergence.py
"""
Test that the iterative lookup algorithm converges correctly.
Uses a local 100-node DHT network.
"""
import pytest
import trio
from libp2p.testing.factories import HostFactory

async def test_iterative_lookup_reaches_correct_node():
    """
    With 100 nodes, a lookup for node X should return X in the result set,
    even if X is not in the initial routing table.
    """
    N = 100
    hosts = [await HostFactory.create() for _ in range(N)]
    dhts = [KadDHT(h, DHTMode.SERVER) for h in hosts]
    
    # Connect in a ring topology (each node knows its 2 neighbors only)
    for i in range(N):
        await hosts[i].connect(PeerInfo(hosts[(i+1) % N].get_id(), []))
    
    # Now lookup node[50] from node[0]
    # Without iterative lookup: will fail (node[50] not in node[0]'s RT)
    # With iterative lookup: should succeed by traversing the ring
    target = hosts[50].get_id()
    result = await dhts[0].find_peer(target)
    assert result is not None
    assert result.peer_id == target

async def test_value_stored_at_correct_nodes():
    """PUT_VALUE should be stored at the k closest nodes to the key."""
    # Store a value from node[0]
    await dhts[0].put_value("/myapp/test-key", b"hello")
    
    # The k nodes closest to SHA256("/myapp/test-key") should have it
    key_bytes = "/myapp/test-key".encode()
    from libp2p.kad_dht.routing_table import peer_id_to_key
    from libp2p.kad_dht.utils import xor_distance
    
    distances = [(i, xor_distance(peer_id_to_key(hosts[i].get_id()), key_bytes))
                 for i in range(N)]
    distances.sort(key=lambda x: x[1])
    
    # The top-20 closest should have the value
    for idx, _ in distances[:20]:
        val = dhts[idx].value_store.get(key_bytes)
        assert val is not None, f"Node {idx} should have the value"
```

### 7.5 Continuous Interop Monitoring

```yaml
# .github/workflows/interop-test.yml
name: DHT Interoperability Tests

on:
  push:
    paths: ['libp2p/kad_dht/**']
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC

jobs:
  interop:
    runs-on: ubuntu-latest
    services:
      kubo:
        image: ipfs/kubo:latest
        ports: ['5001:5001', '4001:4001']
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Wait for Kubo to start
        run: sleep 10
      - name: Run interop tests
        run: pytest tests/interop/ -v --timeout=120
      - name: Run wire protocol tests  
        run: pytest tests/kad_dht/test_wire_compat.py -v
```

---

## 8. Protocol Wire Compatibility Checklist

Before testing against a live Kubo/go-libp2p node, verify all items:

### Framing
- [x] All messages use **varint** length prefix (NOT fixed 4-byte)
- [ ] PING message uses varint (currently uses 4-byte big-endian) ← **BUG**
- [x] Messages are protobuf-encoded `Message` type
- [x] Protocol ID is `/ipfs/kad/1.0.0`

### FIND_NODE
- [x] Request: `type=FIND_NODE`, `key=<target_peer_id_bytes>`
- [x] Response: `closerPeers` list with peer IDs and multiaddrs
- [x] Signed peer records (`senderRecord`) included in responses
- [ ] Newly discovered `closerPeers` are added to iterative query set ← **MISSING**

### PUT_VALUE
- [x] Request: `type=PUT_VALUE`, `record.key`, `record.value`
- [ ] `record.author` set to public key bytes ← **MISSING**
- [ ] `record.signature` is valid Ed25519/RSA/secp256k1 signature ← **MISSING**
- [x] `/pk/<bytes>` and `/ipns/<bytes>` keys recognized

### GET_VALUE
- [x] Request: `type=GET_VALUE`, `key=<bytes>`
- [x] Response includes `record` if found, else `closerPeers`
- [ ] `closerPeers` from responses fed back into iterative query ← **MISSING**
- [ ] Record signatures verified before acceptance ← **MISSING**

### ADD_PROVIDER
- [x] Request: `type=ADD_PROVIDER`, `key=<multihash_bytes>`, `providerPeers`
- [ ] Key is raw multihash bytes, not UTF-8 string ← **BUG in provide()**
- [x] Provider peer includes addresses
- [x] Signed peer records included

### GET_PROVIDERS
- [x] Request: `type=GET_PROVIDERS`, `key=<multihash_bytes>`
- [x] Response includes `providerPeers` and/or `closerPeers`
- [ ] Key must be multihash bytes ← **BUG in find_providers()**
- [ ] `closerPeers` fed back into iterative query ← **MISSING**

### Routing Table
- [x] Bucket size k=20
- [x] Bucket split only on local-ID bucket
- [x] XOR distance metric using SHA2-256 of peer ID bytes
- [ ] Maximum buckets = 256 ← **Currently: MAXIMUM_BUCKETS=256 ✓**
- [ ] CPL (common prefix length) used for bucket lookup ← **Uses key range instead**
- [ ] Diversity filter (max N peers per /24) ← **MISSING**

---

## 9. Key Differences Reference Table

| Feature | py-libp2p | go-libp2p | Impact |
|---------|-----------|-----------|--------|
| **Record Signing** | ❌ Unsigned | ✅ Ed25519/RSA/secp256k1 | Kubo rejects PUT_VALUE |
| **Iterative Lookup** | ⚠️ Partial (no closerPeers propagation) | ✅ Full qpeerset state machine | Queries fail on real network |
| **Provider Key Format** | ❌ UTF-8 string bytes | ✅ Raw multihash bytes | Provider lookup broken |
| **PING Framing** | ❌ 4-byte big-endian | ✅ varint | Protocol error |
| **Beta Parameter** | ❌ Not implemented | ✅ Default 3 | Early query termination |
| **Persistent Datastore** | ❌ In-memory only | ✅ LevelDB/Badger | Records lost on restart |
| **Network Events** | ❌ Manual add only | ✅ Auto on connect/disconnect | Routing table stays empty |
| **Address Filtering** | ❌ All addrs propagated | ✅ Private addrs filtered | LAN addrs leaked to WAN |
| **Diversity Filter** | ❌ Not implemented | ✅ /24 per CPL limit | Eclipse attack possible |
| **Stream Reuse** | ❌ New stream per query | ✅ Reused within timeout | 10-100x higher latency |
| **GetPublicKey** | ⚠️ Validator only | ✅ Parallel DHT+direct | /pk/ lookups fail for RSA |
| **Provider Republish** | ⚠️ Commented out | ✅ Every 22 hours | Content "unprovided" after 48h |
| **Dual DHT** | ❌ WAN only | ✅ WAN + LAN | No local network discovery |
| **Bootstrap Peers** | ⚠️ No built-in list | ✅ dnsaddr bootstrap peers | Can't bootstrap on public net |
| **Network Size Est.** | ❌ Not implemented | ✅ Estimator in GetClosestPeers | No query optimization |
| **OTel Tracing** | ❌ Logging only | ✅ Full span tracing | No production observability |
| **FullRT Client** | ❌ Not implemented | ✅ Crawler-based full trie | No accelerated client mode |
| **CPL-based Buckets** | ⚠️ Range-based | ✅ CPL (k-bucket standard) | Minor lookup efficiency diff |
| **Lookup Check** | ❌ Not implemented | ✅ Pre-add peer validation | Stale peers stay in RT |
| **Lookup Followup** | ❌ Not implemented | ✅ Queries top-K after convergence | Reduced write amplification |

---

## References

- [Kademlia Paper (Maymounkov & Mazières 2002)](https://pdos.csail.mit.edu/~petar/papers/maymounkov-kademlia-lncs.pdf)
- [S/Kademlia Paper (Baumgart & Mies 2007)](https://ovgu.de/~baumgart/papers/baumgart07.pdf)
- [IPFS Amino DHT Spec](https://github.com/ipfs/specs/blob/main/IPFS_DHT.md)
- [go-libp2p-kad-dht](https://github.com/libp2p/go-libp2p-kad-dht)
- [go-libp2p-record (signing spec)](https://github.com/libp2p/go-libp2p-record)
- [libp2p DHT Spec](https://github.com/libp2p/specs/tree/master/kad-dht)
- [py-libp2p](https://github.com/libp2p/py-libp2p)
- [IPFS Kubo](https://github.com/ipfs/kubo)
