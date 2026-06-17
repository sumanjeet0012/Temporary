# Generic DAG Service for Arbitrary IPLD Nodes

## 1. Purpose

This document describes the planned Generic DAG feature for `py-ipfs-lite` / `MerkleDag`.

Currently, the DAG implementation is mainly useful for file-like data:

```text
file / bytes
   ↓
UnixFS-style chunking or raw block storage
   ↓
CID
   ↓
Bitswap / blockstore
```

This is good for storing files, byte streams, artifacts, and large binary content. However, it is not enough for storing structured application data such as inference logs, manifests, metadata records, proofs, or linked IPLD objects.

The goal of this feature is to add methods that can store and retrieve arbitrary structured IPLD nodes.

Target usage:

```python
node = {
    "type": "inference_log",
    "model": "llama-3",
    "prompt": "What is 2 + 2?",
    "output": "4",
}

cid = await dag.add_node(node, codec=CODEC_DAG_JSON)
restored_node = await dag.get_node(cid)
await dag.remove_node(cid)
```

---

## 2. Core Concept

Everything eventually gets stored as bytes, but not all bytes represent the same kind of data.

For example, the same logical object:

```python
{
    "name": "Alice",
    "age": 30,
}
```

can be represented as:

```text
raw JSON bytes
DAG-JSON bytes
DAG-CBOR bytes
DAG-PB bytes
UnixFS file blocks
```

The CID must describe the actual encoding used for the block. If the CID says the block is `dag-cbor`, then the stored bytes must actually be DAG-CBOR bytes. If the CID says `dag-json`, then the stored bytes must actually be DAG-JSON bytes.

So the correct flow is:

```text
structured node
   ↓
encode using selected codec
   ↓
encoded bytes
   ↓
compute CID using same codec
   ↓
store block bytes
```

The wrong flow is:

```text
JSON bytes
   ↓
compute CID with codec=dag-cbor
   ↓
store bytes
```

That is wrong because the CID claims that the block is DAG-CBOR, but the bytes are actually JSON.

---

## 3. Why Not Use `add_bytes()`?

The existing `add_bytes()` method accepts already-created bytes:

```python
async def add_bytes(data: bytes, ...):
    ...
```

This means the method does not know how the bytes were created. They may be:

```text
raw binary
plain JSON
DAG-JSON
DAG-CBOR
DAG-PB
image bytes
random bytes
```

Therefore, `add_bytes()` should remain responsible for byte-stream or file-like storage.

The new method, `add_node()`, will accept structured data and will create the bytes itself using the selected codec.

Difference:

```text
add_bytes(data: bytes)
    bytes → CID → store

add_node(node, codec)
    structured node → encode with codec → bytes → CID → store
```

This separation prevents codec mismatch bugs.

---

## 4. What We Want to Add

We want to add generic IPLD node methods inside the existing `MerkleDag` class.

We are not creating a new class for now. The methods will be added directly into `MerkleDag`.

Required methods:

```python
async def add_node(self, node, codec=CODEC_DAG_JSON) -> bytes:
    ...

async def get_node(self, cid: bytes, peer_id=None):
    ...

async def remove_node(self, cid: bytes) -> None:
    ...
```

Supporting helper methods/functions:

```python
def encode_node(node, codec: int) -> bytes:
    ...

def decode_node(data: bytes, codec: int):
    ...

def get_codec_from_cid(cid: bytes) -> int:
    ...

async def add_encoded_block(self, data: bytes, codec: int) -> bytes:
    ...
```

---

## 5. Method Responsibilities

## 5.1 `add_node()`

### Purpose

Stores a structured IPLD node.

### Input

```python
node = {
    "type": "inference_log",
    "model": "llama-3",
    "output": "4",
}
```

### Flow

```text
node
   ↓
encode_node(node, codec)
   ↓
encoded bytes
   ↓
compute_cid_v1(encoded, codec=codec)
   ↓
bitswap.add_block(cid, encoded)
   ↓
return cid
```

### Example implementation shape

```python
async def add_node(self, node, codec=CODEC_DAG_JSON) -> bytes:
    encoded = encode_node(node, codec)
    cid = compute_cid_v1(encoded, codec=codec)
    await self.bitswap.add_block(cid, encoded)
    return cid
```

### Important rule

The codec used to encode the node must be the same codec used in the CID.

Correct:

```python
encoded = encode_node(node, CODEC_DAG_JSON)
cid = compute_cid_v1(encoded, codec=CODEC_DAG_JSON)
```

Incorrect:

```python
encoded = json.dumps(node).encode("utf-8")
cid = compute_cid_v1(encoded, codec=CODEC_DAG_CBOR)
```

---

## 5.2 `get_node()`

### Purpose

Fetches a CID and decodes the block back into a structured node.

### Flow

```text
cid
   ↓
read codec from CID
   ↓
get encoded block bytes from local blockstore or Bitswap
   ↓
decode_node(encoded, codec)
   ↓
return structured node
```

### Example implementation shape

```python
async def get_node(self, cid: bytes, peer_id=None):
    data = await self.bitswap.block_store.get_block(cid)

    if data is None and peer_id is not None:
        data = await self.bitswap.get_block(cid, peer_id)

    if data is None:
        raise BlockNotFoundError(cid)

    codec = get_codec_from_cid(cid)
    return decode_node(data, codec)
```

### Important rule

`get_node()` should not guess the encoding from the block bytes. It should read the codec from the CID.

---

## 5.3 `remove_node()`

### Purpose

Deletes a node from the local blockstore only.

This is not a network-wide delete.

### Flow

```text
cid
   ↓
local blockstore delete
```

### Example implementation shape

```python
async def remove_node(self, cid: bytes) -> None:
    await self.bitswap.block_store.delete_block(cid)
```

### Important rule

Removing locally does not remove the block from other peers.

---

## 6. Helper: `encode_node()`

The `encode_node()` helper converts structured data into bytes using the selected codec.

Example shape:

```python
def encode_node(node, codec: int) -> bytes:
    if codec == CODEC_DAG_JSON:
        return encode_dag_json(node)

    if codec == CODEC_DAG_CBOR:
        return encode_dag_cbor(node)

    raise UnsupportedCodecError(codec)
```

Initially, we can implement only `CODEC_DAG_JSON` if DAG-CBOR support is not ready.

Later, we can add:

```text
DAG-CBOR
DAG-PB
raw
custom codecs
```

---

## 7. Helper: `decode_node()`

The `decode_node()` helper converts encoded bytes back into structured data.

Example shape:

```python
def decode_node(data: bytes, codec: int):
    if codec == CODEC_DAG_JSON:
        return decode_dag_json(data)

    if codec == CODEC_DAG_CBOR:
        return decode_dag_cbor(data)

    if codec == CODEC_RAW:
        return data

    raise UnsupportedCodecError(codec)
```

---

## 8. Helper: `add_encoded_block()`

This optional helper stores already-encoded bytes using a given codec.

It is useful to avoid repeating CID computation and block storage code.

```python
async def add_encoded_block(self, data: bytes, codec: int) -> bytes:
    cid = compute_cid_v1(data, codec=codec)
    await self.bitswap.add_block(cid, data)
    return cid
```

Then `add_node()` can use it:

```python
async def add_node(self, node, codec=CODEC_DAG_JSON) -> bytes:
    encoded = encode_node(node, codec)
    return await self.add_encoded_block(encoded, codec)
```

Do not route this through the existing `add_bytes()` method if `add_bytes()` performs chunking, because chunking may create a UnixFS/DAG-PB file root.

---

## 9. How This Fits With Existing Methods

Existing methods remain useful:

```python
await dag.add_file(path)
await dag.get_file(cid, output_path)
await dag.add_bytes(data)
```

These are for file-like data or byte streams.

New methods are for structured IPLD nodes:

```python
await dag.add_node(node, codec=CODEC_DAG_JSON)
await dag.get_node(cid)
await dag.remove_node(cid)
```

Recommended separation inside `MerkleDag`:

```text
add_file() / get_file()
    file path APIs

add_bytes()
    byte-stream API, may use raw blocks and UnixFS-style chunking

add_node() / get_node() / remove_node()
    generic IPLD node APIs
```

---

## 10. Example: Storing an Inference Log

### Add prompt node

```python
prompt_cid = await dag.add_node(
    {
        "type": "prompt",
        "text": "What is 2 + 2?",
    },
    codec=CODEC_DAG_JSON,
)
```

### Add output node

```python
output_cid = await dag.add_node(
    {
        "type": "model_output",
        "text": "4",
    },
    codec=CODEC_DAG_JSON,
)
```

### Add inference log node

```python
log_cid = await dag.add_node(
    {
        "type": "inference_log",
        "model": "llama-3",
        "prompt": {"/": prompt_cid},
        "output": {"/": output_cid},
        "timestamp": "2026-06-17T16:33:00+05:30",
    },
    codec=CODEC_DAG_JSON,
)
```

### Retrieve log node

```python
log = await dag.get_node(log_cid)
```

Expected result:

```python
{
    "type": "inference_log",
    "model": "llama-3",
    "prompt": {"/": prompt_cid},
    "output": {"/": output_cid},
    "timestamp": "2026-06-17T16:33:00+05:30",
}
```

---

## 11. Why This Achieves Generic DAG Support

Before this feature, the DAG layer mainly handles:

```text
files / byte streams
   ↓
raw chunks or UnixFS-style file DAG
```

After this feature, the DAG layer will also handle:

```text
structured node
   ↓
codec-aware encoding
   ↓
CID-addressed block
```

This gives `py-ipfs-lite` the foundation to store:

```text
inference logs
metadata records
manifests
proofs
audit trails
linked DAG objects
application-specific IPLD nodes
```

---

## 12. Acceptance Criteria

This feature is complete when:

- `MerkleDag.add_node()` exists.
- `MerkleDag.get_node()` exists.
- `MerkleDag.remove_node()` exists.
- `add_node()` encodes structured data using the selected codec.
- `add_node()` computes the CID using the same codec used for encoding.
- `get_node()` reads the codec from the CID.
- `get_node()` decodes the bytes using that codec.
- `remove_node()` deletes only from the local blockstore.
- Existing `add_bytes()` and file methods continue to work.
- Generic DAG nodes do not pass through UnixFS chunking.
- Tests prove that a node can be added, retrieved, and removed.

---

## 13. Suggested Tests

### Test 1: Add and get DAG-JSON node

```python
node = {"name": "Alice", "age": 30}

cid = await dag.add_node(node, codec=CODEC_DAG_JSON)
restored = await dag.get_node(cid)

assert restored == node
```

### Test 2: Remove node

```python
cid = await dag.add_node({"hello": "world"}, codec=CODEC_DAG_JSON)
await dag.remove_node(cid)

assert not await dag.bitswap.block_store.has_block(cid)
```

### Test 3: Codec mismatch should fail

```python
bad_data = b'{"name":"Alice"}'
cid = compute_cid_v1(bad_data, codec=CODEC_DAG_CBOR)
await dag.bitswap.add_block(cid, bad_data)

with pytest.raises(Exception):
    await dag.get_node(cid)
```

### Test 4: Existing `add_bytes()` still works

```python
cid = await dag.add_bytes(b"hello world")
assert await dag.bitswap.block_store.has_block(cid)
```

---

## 14. Final Summary

We are adding generic IPLD node support to the existing `MerkleDag` class.

The new API will not replace file or byte APIs. It will sit beside them.

Final API shape:

```python
# Existing byte/file APIs
await dag.add_bytes(data)
await dag.add_file(path)
await dag.get_file(cid, output_path)

# New generic IPLD node APIs
cid = await dag.add_node(node, codec=CODEC_DAG_JSON)
node = await dag.get_node(cid)
await dag.remove_node(cid)
```

The key idea is:

```text
add_bytes() stores bytes.
add_node() creates codec-correct bytes from structured data, then stores them.
```

This allows `py-ipfs-lite` to support arbitrary IPLD DAGs while continuing to support UnixFS/file-style storage.
