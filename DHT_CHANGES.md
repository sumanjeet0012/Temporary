# Kademlia DHT & Bootstrap Module — Bug Fixes Summary

**Branch:** `fix/dht-provide-improvements`
**Commits:** `d4189ed8`, `877d8e68`, `acc0ce26`, `1618af72`, `40ec6b64`

---

## Table of Contents

1. [Kademlia DHT Fixes](#kademlia-dht-fixes)
   - [Bug 1: ADD_PROVIDER Handler `break` Instead of `continue`](#bug-1-add_provider-handler-break-instead-of-continue)
   - [Bug 2: PUT_VALUE Key Validation Checks Wrong Key](#bug-2-put_value-key-validation-checks-wrong-key)
   - [Bug 3: `find_providers` Swallows `trio.Cancelled`](#bug-3-find_providers-swallows-triocancelled)
   - [Bug 4: Routing Table Logs Misleading "Successfully Refreshed"](#bug-4-routing-table-logs-misleading-successfully-refreshed)
   - [Bug 5: `maybe_consume_signed_record` Crashes on None peer_id](#bug-5-maybe_consume_signed_record-crashes-on-none-peer_id)
   - [Bug 6: `get_value` Uses Local Routing Table Instead of Network Lookup](#bug-6-get_value-uses-local-routing-table-instead-of-network-lookup)
   - [Bug 7: `find_peer` Doesn't Re-check Peerstore After Network Lookup](#bug-7-find_peer-doesnt-re-check-peerstore-after-network-lookup)
   - [Bug 8: Missing Max Varint Byte Limit in Response Reading (DoS)](#bug-8-missing-max-varint-byte-limit-in-response-reading-dos)
   - [Bug 9: ADD_PROVIDER Handler Sends Response (Fire-and-Forget Violation)](#bug-9-add_provider-handler-sends-response-fire-and-forget-violation)
   - [Bug 10: ADD_PROVIDER Key Length Check Missing `> 80` Bound](#bug-10-add_provider-key-length-check-missing--80-bound)
   - [Bug 11: `_query_peer_for_closest` Has No Timeout](#bug-11-_query_peer_for_closest-has-no-timeout)
   - [Bug 12: `_query_peer_for_closest` Can Query Self](#bug-12-_query_peer_for_closest-can-query-self)
   - [Bug 13: PUT_VALUE Doesn't Verify Record Key Matches Message Key](#bug-13-put_value-doesnt-verify-record-key-matches-message-key)
   - [Bug 14: `get_value`/`put_value` Propagation Re-signs Records](#bug-14-get_valueput_value-propagation-re-signs-records)
   - [Bug 15: `handle_stream` Returns on Error Instead of Breaking Loop](#bug-15-handle_stream-returns-on-error-instead-of-breaking-loop)
   - [Bug 16: CID Key Encoding for `provide`/`find_providers` API](#bug-16-cid-key-encoding-for-providefind_providers-api)
   - [Bug 17: Routing Table Concurrency Safety](#bug-17-routing-table-concurrency-safety)
   - [Bug 18: Routing Table Bucket Split Doesn't Start Periodic Refresh](#bug-18-routing-table-bucket-split-doesnt-start-periodic-refresh)
   - [Bug 19: Provider Store Republishes Every Record Every Cycle](#bug-19-provider-store-republishes-every-record-every-cycle)
   - [Bug 20: Provider Store `_add_provider` Doesn't Validate Input](#bug-20-provider-store-_add_provider-doesnt-validate-input)
   - [Bug 21: FIND_NODE Response Missing Empty Peer ID Check](#bug-21-find_node-response-missing-empty-peer-id-check)
2. [Bootstrap Module Fixes](#bootstrap-module-fixes)
   - [Bug B1: `allow_ipv6` Parameter Is Accepted But Never Used](#bug-b1-allow_ipv6-parameter-is-accepted-but-never-used)
   - [Bug B2: Uses `ID.from_base58` Instead of `ID.from_string`](#bug-b2-uses-idfrom_base58-instead-of-idfrom_string)
   - [Bug B3: No Verification That DNS-Resolved Addresses Match Expected Peer ID](#bug-b3-no-verification-that-dns-resolved-addresses-match-expected-peer-id)
3. [Files Changed](#files-changed)

---

## Kademlia DHT Fixes

### Bug 1: ADD_PROVIDER Handler `break` Instead of `continue`

**File:** `libp2p/kad_dht/kad_dht.py` (commit `acc0ce26`)

**Issue:** The ADD_PROVIDER handler used `break` when encountering an invalid signed record, which exits the entire message handling loop and closes the stream. This prevents processing any subsequent messages on the same connection.

**Root Cause:** Copy-paste error from the outer handler structure. The `break` was meant to skip the invalid provider but instead broke out of the `handle_stream` method entirely.

**Fix:** Changed `break` → `continue` so the handler skips only the invalid provider and continues processing remaining providers in the message.

```python
# Before
await stream.close()
return

# After
continue
```

---

### Bug 2: PUT_VALUE Key Validation Checks Wrong Key

**File:** `libp2p/kad_dht/kad_dht.py` (commit `acc0ce26`)

**Issue:** The PUT_VALUE handler compared `message.key` against `message.record.key`, but per the libp2p spec, the record's key must match the message key. The code was checking `message.key != message.key` (comparing the same field).

**Fix:** Added explicit validation: `if message.key != key:` where `key = message.record.key`, which checks that the message-level key matches the record-level key.

---

### Bug 3: `find_providers` Swallows `trio.Cancelled`

**File:** `libp2p/kad_dht/provider_store.py` (commit `acc0ce26`)

**Issue:** The `find_providers` method caught `trio.Cancelled` and logged it, preventing proper cancellation propagation. This caused `ExceptionGroup` errors in trio nurseries when tasks were cancelled due to timeouts.

**Fix:** Re-raise `trio.Cancelled` after logging, allowing proper cancellation propagation through the trio task tree.

```python
# Before
except trio.Cancelled:
    logger.debug(f"Query for providers from {peer_id} timed out")

# After
except trio.Cancelled:
    logger.debug(f"Query for providers from {peer_id} cancelled")
    raise
```

---

### Bug 4: Routing Table Logs Misleading "Successfully Refreshed"

**File:** `libp2p/kad_dht/routing_table.py` (commit `acc0ce26`)

**Issue:** The `_periodic_peer_refresh` method logged "Successfully refreshed peer" even when the peer was removed because it was unresponsive. The log appeared after the remove/replace logic, making debugging confusing.

**Fix:** Removed the misleading log line. The existing logs for "Removed unresponsive peer" and "Old peer is still alive" are sufficient.

---

### Bug 5: `maybe_consume_signed_record` Crashes on None peer_id

**File:** `libp2p/kad_dht/utils.py` (commit `acc0ce26`)

**Issue:** When `peer_id=None` (e.g., for provider records where the sender isn't verified), the function tried `isinstance(peer_id, ID)` which returned `False`, causing valid records to be rejected. Then accessing `record.peer_id` would fail.

**Fix:** Changed the check to `if peer_id is not None and record.peer_id != peer_id:` — only validates peer ID match when a peer ID is actually provided.

```python
# Before
if not (isinstance(peer_id, ID) and record.peer_id == peer_id):
    return False

# After
if peer_id is not None and record.peer_id != peer_id:
    return False
```

---

### Bug 6: `get_value` Uses Local Routing Table Instead of Network Lookup

**File:** `libp2p/kad_dht/kad_dht.py` (commit `1618af72`)

**Issue:** The `get_value` method used `self.routing_table.find_local_closest_peers(key_bytes)` to find peers to query. This only searches the local routing table, which may not have the closest peers in the network. The `put_value` method also had this issue.

**Fix:** Changed both `get_value` and `put_value` to use `await self.peer_routing.find_closest_peers_network(key_bytes)` which performs an iterative FIND_NODE query across the network, matching go-libp2p's behavior.

```python
# Before
closest_peers = [
    peer for peer in self.routing_table.find_local_closest_peers(key_bytes)
    if peer != self.local_peer_id
]

# After
closest_peers = [
    peer for peer in await self.peer_routing.find_closest_peers_network(key_bytes)
    if peer != self.local_peer_id
]
```

---

### Bug 7: `find_peer` Doesn't Re-check Peerstore After Network Lookup

**File:** `libp2p/kad_dht/peer_routing.py` (commit `40ec6b64`)

**Issue:** During a network lookup (`find_closest_peers_network`), the target peer's signed record may be discovered and added to the peerstore via `maybe_consume_signed_record`, even if the target wasn't in the top 20 closest peers. But `find_peer` only checked the `closest_peers` list after the lookup, not the peerstore.

**Fix:** Added a peerstore re-check after the network lookup completes. If the target peer has addresses in the peerstore, return it directly.

```python
# Added after the network lookup loop
try:
    addrs = self.host.get_peerstore().addrs(peer_id)
    if addrs:
        logger.debug(f"Found peer {peer_id} in peerstore after network lookup")
        return PeerInfo(peer_id, addrs)
except Exception:
    pass
```

---

### Bug 8: Missing Max Varint Byte Limit in Response Reading (DoS)

**Files:** `peer_routing.py`, `value_store.py`, `provider_store.py` (commit `40ec6b64`)

**Issue:** Four methods that read varint-prefixed response lengths had unbounded read loops. A malicious peer could send endless continuation bytes (`0x80+`) in the varint prefix, causing the read loop to consume memory and CPU indefinitely.

**Affected methods:**
- `_query_peer_for_closest` in `peer_routing.py`
- `_store_at_peer` in `value_store.py`
- `_get_from_peer` in `value_store.py`
- `_get_providers_from_peer` in `provider_store.py`

**Fix:** Added `max_varint_bytes = 10` (the maximum bytes for a uint64 varint) to all four methods. If the varint exceeds this limit, the response is discarded.

```python
max_varint_bytes = 10
while True:
    b = await stream.read(1)
    if not b:
        return []
    length_bytes += b
    if b[0] & 0x80 == 0:
        break
    if len(length_bytes) >= max_varint_bytes:
        logger.warning("Varint length exceeds maximum bytes, ignoring response")
        return []
```

---

### Bug 9: ADD_PROVIDER Handler Sends Response (Fire-and-Forget Violation)

**File:** `libp2p/kad_dht/kad_dht.py` (commit `d4189ed8`)

**Issue:** The ADD_PROVIDER handler sent an acknowledgement response back to the sender. Per the IPFS DHT spec, ADD_PROVIDER is **fire-and-forget** — the receiver stores the provider record but does NOT send a response. go-libp2p returns `nil, nil` from `handleAddProvider`.

**Fix:** Removed the response sending code. The handler now just processes the providers and logs completion.

---

### Bug 10: ADD_PROVIDER Key Length Check Missing `> 80` Bound

**File:** `libp2p/kad_dht/kad_dht.py` (commit `40ec6b64`)

**Issue:** An earlier commit (1618af72) removed the `len(key) > 80` check from the ADD_PROVIDER handler, thinking it was unnecessary. However, go-libp2p's `handleAddProvider` AND `handleGetProviders` BOTH check `len(key) > 80`. Only `handleGetValue` uses `len(key) == 0` alone.

**Fix:** Restored the original check: `if len(key) > 80 or len(key) == 0:`.

---

### Bug 11: `_query_peer_for_closest` Has No Timeout

**File:** `libp2p/kad_dht/peer_routing.py` (commit `1618af72`)

**Issue:** The `_query_peer_for_closest` method had no timeout. If a peer accepted a connection but never responded (e.g., due to network issues or slow processing), the query would hang indefinitely, blocking the entire iterative lookup.

**Fix:** Wrapped the entire query body in `trio.move_on_after(QUERY_TIMEOUT)` (10 seconds). If the timeout fires, the method returns an empty list.

---

### Bug 12: `_query_peer_for_closest` Can Query Self

**File:** `libp2p/kad_dht/peer_routing.py` (commit `d4189ed8`)

**Issue:** The iterative lookup in `find_closest_peers_network` didn't exclude the local peer from the list of peers to query. This could result in the node trying to open a stream to itself.

**Fix:** Added `p != local_id` filter when building `peers_to_query`:

```python
local_id = self.host.get_id()
peers_to_query = [
    p for p in closest_peers if p not in queried_peers and p != local_id
][:ALPHA]
```

---

### Bug 13: PUT_VALUE Doesn't Verify Record Key Matches Message Key

**File:** `libp2p/kad_dht/kad_dht.py` (commit `acc0ce26`)

**Issue:** The PUT_VALUE handler didn't validate that `message.key` matches `message.record.key`. Per the spec, these should be identical. A mismatched key could corrupt the DHT store.

**Fix:** Added explicit validation:

```python
if message.key != key:
    logger.warning("PUT_VALUE record key does not match message key")
    break
```

---

### Bug 14: `get_value`/`put_value` Propagation Re-signs Records

**File:** `libp2p/kad_dht/value_store.py`, `libp2p/kad_dht/kad_dht.py` (commit `d4189ed8`)

**Issue:** When propagating records to peers during `get_value` or storing the best record locally, the code called `value_store.put()` which creates a new signed record with the local peer's key. This overwrites the original author's signature, making the record invalid.

**Fix:**
1. Added `put_record()` method to `ValueStore` that stores a signed Record directly without re-signing.
2. Added `record` parameter to `_store_at_peer()` to send the original signed record.
3. Changed `get_value` to use `put_record(key_bytes, best_rec)` and `_store_at_peer(..., record=best_rec)`.

---

### Bug 15: `handle_stream` Returns on Error Instead of Breaking Loop

**File:** `libp2p/kad_dht/kad_dht.py` (commit `d4189ed8`)

**Issue:** Multiple error paths in `handle_stream` used `return` which exits the entire method. Since `handle_stream` can handle multiple messages on a single stream, `return` closes the stream prematurely.

**Fix:** Changed `return` → `break` in all error paths within the message handling loop. This breaks out of the loop but still reaches the `finally` block for proper cleanup.

---

### Bug 16: CID Key Encoding for `provide`/`find_providers` API

**File:** `libp2p/kad_dht/kad_dht.py` (commit `d4189ed8`)

**Issue:** The `provide()` and `find_providers()` convenience methods used `key.encode("utf-8")` to convert the key string to bytes. However, per the IPFS DHT spec, provider keys should be the **multihash** portion of a CID, not the UTF-8 encoding of the CID string.

**Fix:** Added CID parsing: try to parse the key as a CID and extract its multihash. Fall back to hex decoding, then UTF-8 encoding.

```python
from libp2p.bitswap.cid import parse_cid

try:
    cid_obj = parse_cid(key)
    key_bytes = cid_obj.multihash
except (ValueError, TypeError):
    try:
        key_bytes = bytes.fromhex(key)
    except ValueError:
        key_bytes = key.encode("utf-8")
```

---

### Bug 17: Routing Table Concurrency Safety

**File:** `libp2p/kad_dht/routing_table.py` (commit `d4189ed8`)

**Issue:** The `KBucket.add_peer` method could race with itself when multiple coroutines tried to add peers simultaneously. Between the ping check and the actual insert, another coroutine could modify the bucket, causing lost updates or duplicate entries.

**Fix:**
1. Added `trio.Lock` to `KBucket` to serialize `add_peer` calls.
2. Added re-checks after the async ping: if the bucket state changed during the ping (e.g., the target peer was already added, or the bucket became full), handle it gracefully.

---

### Bug 18: Routing Table Bucket Split Doesn't Start Periodic Refresh

**File:** `libp2p/kad_dht/routing_table.py` (commit `d4189ed8`)

**Issue:** When a bucket was split, the new buckets didn't start their periodic peer refresh timers. This meant stale peers in the new buckets would never be evicted.

**Fix:** Added `_rt_refresh_nursery` to `RoutingTable` and `start_periodic_refresh()` method. After splitting, the new buckets' refresh tasks are started in the nursery.

---

### Bug 19: Provider Store Republishes Every Record Every Cycle

**File:** `libp2p/kad_dht/provider_store.py` (commit `d4189ed8`)

**Issue:** The `_republish_provider_records` method republished ALL provider records on every cycle (every 12 hours). Per spec, records should only be republished every 22 hours.

**Fix:** Added `_last_republish` dict to track when each key was last republished. Only keys whose last republish is older than `PROVIDER_RECORD_REPUBLISH_INTERVAL` (22 hours) are republished.

---

### Bug 20: Provider Store `_add_provider` Doesn't Validate Input

**File:** `libp2p/kad_dht/provider_store.py` (commit `d4189ed8`)

**Issue:** The `_add_provider` method didn't validate that the `provider` parameter was non-None or had a valid `peer_id`. Passing `None` would cause an `AttributeError`.

**Fix:** Added input validation at the start of the method:

```python
if not provider or not provider.peer_id:
    logger.debug("Skipping add_provider with invalid PeerInfo")
    return
```

---

### Bug 21: FIND_NODE Response Missing Empty Peer ID Check

**File:** `libp2p/kad_dht/peer_routing.py` (commit `d4189ed8`)

**Issue:** When processing FIND_NODE responses, the code didn't check for empty peer IDs. A peer could send a response with an empty `id` field in `closerPeers`, causing `ID(b"")` to be created and added to results.

**Fix:** Added `if not peer_data.id:` check before creating the `ID`:

```python
if not peer_data.id:
    logger.debug("Skipping peer with empty ID in FIND_NODE")
    continue
```

---

## Bootstrap Module Fixes

### Bug B1: `allow_ipv6` Parameter Is Accepted But Never Used

**File:** `libp2p/discovery/bootstrap/bootstrap.py` (commit `877d8e68`)

**Issue:** The `BootstrapDiscovery` constructor accepts an `allow_ipv6` parameter, but the `_is_supported_addr` method only checks for transport protocol support (tcp, quic, etc.) — it never checks whether the address is IPv4 or IPv6. IPv6 addresses are always accepted regardless of the flag.

**Test:** `tests/core/discovery/bootstrap/test_bug_allow_ipv6.py`

**Status:** Confirmed via test. Not yet fixed (low priority — bootstrap is not the primary discovery mechanism).

---

### Bug B2: Uses `ID.from_base58` Instead of `ID.from_string`

**File:** `libp2p/discovery/bootstrap/bootstrap.py` (commit `877d8e68`)

**Issue:** The bootstrap peer ID parsing uses `ID.from_base58()` which only does base58 decoding without multihash validation. The standard `ID.from_string()` (used in `info_from_p2p_addr`) validates both multibase and base58, rejecting invalid peer IDs.

**Test:** `tests/core/discovery/bootstrap/test_bug_peer_id_parsing.py`

**Status:** Confirmed via test. Not yet fixed.

---

### Bug B3: No Verification That DNS-Resolved Addresses Match Expected Peer ID

**File:** `libp2p/discovery/bootstrap/bootstrap.py` (commit `877d8e68`)

**Issue:** When resolving `dnsaddr` TXT records, the code doesn't verify that the resolved addresses contain the expected peer ID. A malicious DNS response could return addresses with a different peer ID, and they'd be added to the peerstore under the original peer ID. go-libp2p's `ResolveDNSAddr` performs this verification.

**Test:** `tests/core/discovery/bootstrap/test_bug_dns_peer_id.py`

**Status:** Confirmed via test. Not yet fixed.

---

## Files Changed

| File | Changes |
|------|---------|
| `libp2p/kad_dht/kad_dht.py` | ADD_PROVIDER fire-and-forget, PUT_VALUE key validation, CID key encoding, network lookup for get/put_value, handle_stream break-vs-return, record propagation |
| `libp2p/kad_dht/peer_routing.py` | find_peer peerstore re-check, query timeout, self-query exclusion, max varint limit, empty peer ID check |
| `libp2p/kad_dht/provider_store.py` | ADD_PROVIDER fire-and-forget, Cancelled re-raise, max varint limit, republish interval, input validation |
| `libp2p/kad_dht/routing_table.py` | Concurrency lock, bucket split refresh, misleading log removal |
| `libp2p/kad_dht/value_store.py` | put_record method, record parameter for _store_at_peer, max varint limits |
| `libp2p/kad_dht/utils.py` | maybe_consume_signed_record None peer_id handling |
| `tests/core/kad_dht/test_kad_dht.py` | Updated provide/find_providers test to use CID string |
| `tests/core/kad_dht/test_bug_find_peer_peerstore.py` | New: confirms find_peer peerstore re-check bug |
| `tests/core/kad_dht/test_bug_max_varint.py` | New: confirms missing max varint check |
| `tests/core/discovery/bootstrap/test_bug_allow_ipv6.py` | New: confirms allow_ipv6 unused |
| `tests/core/discovery/bootstrap/test_bug_dns_peer_id.py` | New: confirms DNS peer ID mismatch |
| `tests/core/discovery/bootstrap/test_bug_peer_id_parsing.py` | New: confirms from_base58 vs from_string |
