# Python Bitswap Interoperability with Kubo

This document summarizes the changes made to the Python `py-libp2p` Bitswap implementation to achieve seamless file-sharing interoperability with Kubo (the reference Go IPFS implementation).

## The Core Challenge

Initially, attempting to download a file from the Python Bitswap provider using Kubo's `ipfs get` command resulted in the download hanging indefinitely and eventually timing out, despite the Python provider correctly identifying that it had the requested blocks. 

Through deep network tracing and protocol analysis, we discovered the issue stemmed from **Stream Directionality expectations** and **Protocol Negotiation behaviors** within the libp2p ecosystem.

## What We Changed (and Why)

### 1. Corrected Stream Directionality for Block Responses

**The Problem:** 
When Kubo wants a file, it opens an *inbound stream* to the Python provider and sends a `WANTLIST` message. The previous Python implementation processed this wantlist, fetched the blocks, and then wrote the block responses directly back onto that **same inbound stream**.

**The "Why":**
Kubo's Bitswap client treats streams with strict directionality expectations. When it opens an outbound stream to send a `WANTLIST`, it does not expect to read raw block payloads on that exact same stream. Instead, it expects the remote provider to dial back and open a **new outbound stream** (from the provider to the client) to deliver the requested blocks. Because Python was appending blocks to the inbound stream, Kubo silently ignored them and stalled.

**The Fix:**
We updated `_process_wantlist` in `libp2p/bitswap/client.py` to always explicitly dial a new outbound stream back to the requester before sending block responses:

```python
# We MUST open a new stream to the client to send the blocks.
try:
    outbound_stream = await self.host.new_stream(
        peer_id, [TProtocol(peer_protocol)]
    )
except Exception as e:
    logger.error(f"Failed to open outbound stream to send response: {e}")
    return

if blocks_to_send_v100:
    await self._send_blocks_in_batches_v100(blocks_to_send_v100, peer_id, outbound_stream)
```

### 2. Handled the TLS/Identity Limitation Gracefully

**The Problem:**
Python's standard `ssl` library lacks the ability to request a client certificate during a TLS 1.3 handshake without verifying it against a trusted CA (a feature Go provides via `InsecureSkipVerify`). Because `py-libp2p` uses self-signed peer identities, Python defaults to generating a "placeholder" peer ID for inbound TLS connections until the actual `Identify` protocol exchange takes place. 

**The "Why":**
When Kubo completes the `Identify` exchange, Python realizes the peer ID has changed and attempts to update it. However, the connection is already registered under the placeholder ID, leading to a `PeerStoreError`. Consequently, Kubo's `SignedPeerRecord` is rejected, and Kubo's `PeerStore` doesn't fully record Python's protocol support.

**The Fix:**
Fortunately, the stream directionality fix above organically bypasses this limitation! When Python calls `self.host.new_stream()`, it explicitly forces the stream to negotiate using `/ipfs/bitswap/1.2.0` (extracted dynamically from the inbound stream, bypassing the incomplete `PeerStore`). 

Kubo, gracefully handling the Identity rejection, still maintains the multiplexed connection. It readily accepts Python's new stream request, allowing the block transfer to proceed unimpeded over the existing TLS connection.

### 3. Preserved `WANT_HAVE` Optimization

**The Problem:**
In Bitswap 1.2.0, clients often send `WANT_HAVE` requests to discover which peers hold a block before actually requesting it via `WANT_BLOCK`. 

**The "Why":**
If the provider responds with a `HAVE` (BlockPresence), Kubo must execute another full round-trip to send a `WANT_BLOCK` request. 

**The Fix:**
Bitswap 1.2.0 formally allows a provider to send a block *instead* of a `HAVE` presence. We preserved the optimization where Python directly sends the block (implicit `HAVE`) when responding to a `WANT_HAVE` request. Coupled with the stream directionality fix, Kubo accepts this block instantly, bypassing an entire network round-trip and accelerating the download.

## Final Result

By aligning Python's stream management with Kubo's architectural expectations, the Python Bitswap implementation is now fully interoperable with standard IPFS nodes. 

In our final validation, Kubo successfully downloaded a 200MB test file (`199.55 MiB / 199.55 MiB [==============================] 100.00% 3s`) directly from the Python provider, proving the robustness of the integration.
