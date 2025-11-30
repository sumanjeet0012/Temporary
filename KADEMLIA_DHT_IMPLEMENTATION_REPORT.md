# py-libp2p Kademlia DHT Implementation Report

## Overview

This report analyzes the current state of the Kademlia DHT implementation in py-libp2p by comparing it against the official [libp2p Kademlia DHT specification](https://github.com/libp2p/specs/blob/master/kad-dht/README.md).

**Report Date:** November 30, 2025  
**Repository:** [libp2p/py-libp2p](https://github.com/libp2p/py-libp2p)  
**Branch:** fix/pubsub-protocol-negotiation-crash-910

---

## Executive Summary

| Category | Implemented | Partially Implemented | Missing |
|----------|-------------|----------------------|---------|
| **Core Parameters** | 4 | 1 | 0 |
| **DHT Operations** | 4 | 2 | 0 |
| **RPC Messages** | 5 | 1 | 0 |
| **Routing Table** | 4 | 1 | 1 |
| **Protocol Features** | 4 | 3 | 3 |
| **Total** | **21** | **8** | **4** |

---

## 1. Core Parameters & Definitions

### ✅ Fully Implemented

| Parameter | Spec Value | py-libp2p Value | Status | Notes |
|-----------|-----------|-----------------|--------|-------|
| **Replication parameter (`k`)** | 20 | 20 (`BUCKET_SIZE = 20`) | ✅ Implemented | Correctly set in `common.py` |
| **Alpha concurrency (`α`)** | 10 | 3 (`ALPHA = 3`) | ⚠️ Partial | Different from spec recommendation of 10 |
| **Distance function** | XOR(sha256(key1), sha256(key2)) | XOR(sha256(key1), sha256(key2)) | ✅ Implemented | Correctly uses SHA-256 hashing |
| **Keyspace length** | 256 bits | 256 bits (`MAXIMUM_BUCKETS = 256`) | ✅ Implemented | Properly configured |
| **Query Timeout** | 10 seconds | 10 seconds (`QUERY_TIMEOUT = 10`) | ✅ Implemented | Matches spec |

### ⚠️ Partial Implementation Notes

- **Alpha Concurrency**: The spec recommends `α = 10`, but py-libp2p uses `α = 3`. This may result in slower lookups but lower network overhead.

---

## 2. DHT Operations

### 2.1 Peer Routing (FIND_NODE)

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Iterative lookup algorithm | ✅ Implemented | `PeerRouting.find_closest_peers_network()` |
| Return k closest peers | ✅ Implemented | Correctly returns up to 20 peers |
| Alpha-limited concurrency | ✅ Implemented | Queries in batches of ALPHA (3) |
| Convergence detection | ✅ Implemented | Stops when no new closer peers found |
| Max lookup rounds | ✅ Implemented | `MAX_PEER_LOOKUP_ROUNDS = 20` |

**Status: ✅ Fully Implemented**

### 2.2 Value Storage (`PUT_VALUE`)

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Store at k closest peers | ✅ Implemented | `KadDHT.put_value()` |
| Local storage | ✅ Implemented | `ValueStore.put()` |
| Record validation before storage | ✅ Implemented | Uses `NamespacedValidator` |
| Value expiration/TTL | ✅ Implemented | `DEFAULT_TTL = 24 hours` |

**Status: ✅ Fully Implemented**

### 2.3 Value Retrieval (`GET_VALUE`)

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Local lookup first | ✅ Implemented | Checks `ValueStore` before network |
| Network lookup | ✅ Implemented | Queries closest peers |
| Quorum support | ❌ Missing | No quorum parameter `Q` implementation |
| Entry validation | ✅ Implemented | `NamespacedValidator.validate()` |
| Entry correction (PUT to outdated peers) | ❌ Missing | Does not update peers with outdated values |
| Conflict resolution via `Select()` | ✅ Implemented | `Validator.select()` interface exists |

**Status: ⚠️ Partially Implemented** - Missing quorum support and entry correction

### 2.4 Content Provider Advertisement (`ADD_PROVIDER`)

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Find k closest peers | ✅ Implemented | Uses `find_closest_peers_network()` |
| Send ADD_PROVIDER to closest peers | ✅ Implemented | `ProviderStore.provide()` |
| Validate provider matches sender | ✅ Implemented | Checks `provider_id != peer_id` |
| Provider record storage | ✅ Implemented | `ProviderStore.add_provider()` |
| Republish interval (22 hours) | ✅ Implemented | `PROVIDER_RECORD_REPUBLISH_INTERVAL = 22 * 60 * 60` |
| Expiration interval (48 hours) | ✅ Implemented | `PROVIDER_RECORD_EXPIRATION_INTERVAL = 48 * 60 * 60` |
| Address TTL (30 minutes) | ✅ Implemented | `PROVIDER_ADDRESS_TTL = 30 * 60` |

**Status: ✅ Fully Implemented**

### 2.5 Content Provider Discovery (`GET_PROVIDERS`)

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Local provider lookup | ✅ Implemented | Checks local `ProviderStore` first |
| Network provider query | ✅ Implemented | `ProviderStore.find_providers()` |
| Include closer peers in response | ✅ Implemented | Returns `closerPeers` when no providers found |
| Parallel queries with ALPHA limit | ✅ Implemented | Queries in batches |

**Status: ✅ Fully Implemented**

### 2.6 Bootstrap Process

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Run on startup | ✅ Implemented | `KadDHT.run()` starts refresh |
| Periodic refresh | ✅ Implemented | `ROUTING_TABLE_REFRESH_INTERVAL = 60` (1 min for testing) |
| Random key lookups per k-bucket | ⚠️ Partial | `RTRefreshManager` exists but only for non-empty buckets |
| Self-lookup for close peer awareness | ✅ Implemented | `refresh_routing_table()` looks up own ID |
| Query timeout | ✅ Implemented | Uses `QUERY_TIMEOUT` |

**Status: ⚠️ Partially Implemented** - Spec recommends 10-minute refresh; implementation uses 1 minute

---

## 3. RPC Messages (Protobuf)

### 3.1 Message Format

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Length-prefixed messages (varint) | ✅ Implemented | Uses `varint.encode()/decode()` |
| Protobuf serialization | ✅ Implemented | `kademlia_pb2.py` generated from `.proto` |
| Stream-based RPC | ✅ Implemented | Opens streams for each RPC |

### 3.2 Message Types

| Message Type | Status | Notes |
|--------------|--------|-------|
| `FIND_NODE (4)` | ✅ Implemented | Fully functional |
| `GET_VALUE (1)` | ✅ Implemented | Fully functional |
| `PUT_VALUE (0)` | ✅ Implemented | Fully functional |
| `GET_PROVIDERS (3)` | ✅ Implemented | Fully functional |
| `ADD_PROVIDER (2)` | ✅ Implemented | Fully functional |
| `PING (5)` | ⚠️ Partial | Implemented for liveness checks, spec says deprecated |

### 3.3 Protobuf Schema Comparison

**Spec Fields:**
```protobuf
message Record {
    bytes key = 1;
    bytes value = 2;
    string timeReceived = 5;
}

message Message {
    MessageType type = 1;
    bytes key = 2;
    Record record = 3;
    repeated Peer closerPeers = 8;
    repeated Peer providerPeers = 9;
    int32 clusterLevelRaw = 10; // NOT USED
}
```

**py-libp2p Implementation:** ✅ Matches spec with additions for signed peer records

| Field | Spec | py-libp2p | Status |
|-------|------|-----------|--------|
| `Record.key` | ✅ | ✅ | Match |
| `Record.value` | ✅ | ✅ | Match |
| `Record.timeReceived` | ✅ | ✅ | Match |
| `Message.type` | ✅ | ✅ | Match |
| `Message.key` | ✅ | ✅ | Match |
| `Message.record` | ✅ | ✅ | Match |
| `Message.closerPeers` | ✅ | ✅ | Match |
| `Message.providerPeers` | ✅ | ✅ | Match |
| `Message.clusterLevelRaw` | ✅ | ✅ | Match (unused) |
| `Peer.signedRecord` | ❌ | ✅ | Extension (good) |
| `Message.senderRecord` | ❌ | ✅ | Extension (good) |

**Status: ✅ Fully Compatible** - Includes spec-compliant extensions for signed peer records

---

## 4. Routing Table

### 4.1 K-Bucket Implementation

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| K-bucket structure | ✅ Implemented | `KBucket` class with ordered peers |
| Least-recently-seen ordering | ✅ Implemented | Uses `OrderedDict` with timestamps |
| Bucket capacity = k (20) | ✅ Implemented | `bucket_size = BUCKET_SIZE` |
| Ping oldest peer on full bucket | ✅ Implemented | `_ping_peer()` called before eviction |
| Replace unresponsive peers | ✅ Implemented | Evicts if ping fails |
| Bucket splitting | ✅ Implemented | `KBucket.split()` and `_split_bucket()` |

### 4.2 Routing Table Management

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Find k closest peers locally | ✅ Implemented | `find_local_closest_peers()` |
| Add/remove peers | ✅ Implemented | `add_peer()`, `remove_peer()` |
| Peer info storage | ✅ Implemented | Stores `PeerInfo` with addresses |
| Stale peer detection | ✅ Implemented | `get_stale_peers()` with threshold |
| Periodic peer refresh | ✅ Implemented | `_periodic_peer_refresh()` |
| Maximum buckets (256) | ✅ Implemented | `MAXIMUM_BUCKETS = 256` |
| XOR-based bucket finding | ❌ Missing | Uses range-based approach instead |

**Status: ⚠️ Partially Implemented** - Uses simplified range-based bucket selection

---

## 5. Client and Server Mode

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| DHTMode enum (CLIENT/SERVER) | ✅ Implemented | `DHTMode.CLIENT`, `DHTMode.SERVER` |
| Server mode: handle incoming streams | ✅ Implemented | `handle_stream()` only processes if SERVER |
| Client mode: reject incoming streams | ✅ Implemented | Returns early if CLIENT mode |
| Mode switching | ✅ Implemented | `switch_mode()` method |
| Advertise protocol via Identify | ⚠️ Partial | Protocol registered but Identify integration unclear |
| Only add server-mode peers to routing table | ❌ Missing | No mode detection for remote peers |

**Status: ⚠️ Partially Implemented** - Missing remote peer mode detection

---

## 6. Entry Validation

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| `Validator` interface | ✅ Implemented | `Validator` base class |
| `Validator.validate()` method | ✅ Implemented | Abstract method defined |
| `Validator.select()` method | ✅ Implemented | Abstract method for conflict resolution |
| `NamespacedValidator` | ✅ Implemented | Routes to validators by namespace |
| Public Key (`pk`) validator | ✅ Implemented | `PublicKeyValidator` class |
| IPNS validator | ❌ Missing | TODO comment in code |
| Validate on GET_VALUE | ✅ Implemented | Validates retrieved values |
| Validate on PUT_VALUE (before store) | ✅ Implemented | `put_value()` calls `validate()` |

**Status: ⚠️ Partially Implemented** - Missing IPNS validator

---

## 7. Protocol Identification

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Protocol ID: `/ipfs/kad/1.0.0` | ✅ Implemented | `PROTOCOL_ID = TProtocol("/ipfs/kad/1.0.0")` |
| Protocol prefix: `/ipfs` | ✅ Implemented | `PROTOCOL_PREFIX = TProtocol("/ipfs")` |
| Stream handler registration | ✅ Implemented | `host.set_stream_handler(PROTOCOL_ID, ...)` |

---

## 8. Signed Peer Records

| Feature | Status | Implementation Details |
|---------|--------|------------------------|
| Support for signed peer records | ✅ Implemented | `senderRecord` and `signedRecord` fields |
| Consume and verify envelopes | ✅ Implemented | `maybe_consume_signed_record()` |
| Store in peerstore | ✅ Implemented | `consume_peer_record()` with TTL |
| Include in RPC responses | ✅ Implemented | `env_to_send_in_RPC()` helper |

**Status: ✅ Fully Implemented**

---

## 9. Missing Features Summary

### 🔴 Critical Missing Features

1. **Quorum Support for Value Retrieval**
   - Spec requires configurable quorum `Q` for value consistency
   - Current implementation returns first found value
   - Impact: May return stale values in network partitions

2. **Entry Correction**
   - Spec requires updating peers with outdated values during GET_VALUE
   - Current implementation does not propagate better values
   - Impact: Network convergence to best value is slower

3. **Remote Peer Mode Detection**
   - Should only add server-mode peers to routing table
   - Current implementation adds all peers regardless of mode
   - Impact: Routing table may contain unreachable client-mode peers

4. **IPNS Validator**
   - Required for IPFS compatibility
   - Currently marked as TODO
   - Impact: Cannot validate IPNS records

### 🟡 Minor Missing/Different Features

1. **Alpha Parameter Value**
   - Spec: `α = 10`, Implementation: `α = 3`
   - Lower concurrency, slower lookups

2. **Routing Table Refresh Interval**
   - Spec: 10 minutes, Implementation: 1 minute (for testing)
   - Should be configurable or match spec for production

3. **XOR-Trie Based Routing**
   - Spec suggests XOR-tries as alternative
   - Implementation uses k-bucket with range splitting
   - Functional but different approach

---

## 10. Implementation Quality

### Strengths

1. **Clean Code Structure**: Well-organized modules (`kad_dht.py`, `routing_table.py`, `peer_routing.py`, `value_store.py`, `provider_store.py`)
2. **Async/Await**: Proper use of `trio` for concurrency
3. **Signed Peer Records**: Goes beyond basic spec with security features
4. **Comprehensive Logging**: Detailed debug logging throughout
5. **Validator Framework**: Extensible validation system

### Areas for Improvement

1. **Test Coverage**: Should verify all spec compliance points
2. **Documentation**: Add spec reference comments in code
3. **Configuration**: Make parameters like `ALPHA` configurable
4. **Error Handling**: More granular error types for different failure modes

---

## 11. Recommendations

### High Priority

1. **Implement Quorum Support**
   ```python
   async def get_value(self, key: bytes, quorum: int = 1) -> bytes | None:
       # Collect quorum responses before returning
   ```

2. **Add Entry Correction**
   ```python
   # After finding best value, PUT to peers with outdated values
   for peer in outdated_peers:
       await self.value_store._store_at_peer(peer, key, best_value)
   ```

3. **Implement IPNS Validator**
   ```python
   class IPNSValidator(Validator):
       def validate(self, key: str, value: bytes) -> None:
           # Validate IPNS record signature and expiry
       
       def select(self, key: str, values: list[bytes]) -> int:
           # Select by sequence number
   ```

### Medium Priority

4. **Remote Peer Mode Detection**
   - Check if remote peer advertises `/ipfs/kad/1.0.0` via Identify
   - Only add to routing table if server mode

5. **Configurable Parameters**
   ```python
   class KadDHTConfig:
       alpha: int = 10  # Match spec default
       refresh_interval: int = 600  # 10 minutes
       query_timeout: int = 10
   ```

### Low Priority

6. **Consider XOR-Trie Implementation**
   - For very large networks, XOR-tries may be more efficient
   - Current k-bucket approach is sufficient for most use cases

---

## 12. Compatibility Matrix

| libp2p Implementation | Expected Compatibility |
|-----------------------|------------------------|
| go-libp2p | ✅ High - Wire protocol compatible |
| rust-libp2p | ✅ High - Wire protocol compatible |
| js-libp2p | ✅ High - Wire protocol compatible |
| IPFS Kubo | ⚠️ Medium - Missing IPNS validation |

---

## Conclusion

The py-libp2p Kademlia DHT implementation covers approximately **75-80% of the specification**. The core DHT operations (peer routing, value storage/retrieval, provider management) are functional and wire-compatible with other libp2p implementations.

**Key gaps to address:**
1. Quorum support for value retrieval
2. Entry correction mechanism  
3. IPNS validator
4. Remote peer mode detection

These gaps primarily affect advanced use cases and IPFS-specific functionality. For basic DHT operations and peer discovery, the current implementation is production-ready.

---

*Report generated by analyzing py-libp2p source code against libp2p/specs/kad-dht specification*
