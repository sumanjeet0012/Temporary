# Yamux in py-libp2p — A Complete Deep Dive

> This document traces the full lifecycle of Yamux in py-libp2p: from what it is,
> why it exists, how it boots up, how protocol negotiation works, how frames flow,
> and what bug broke cross-language interop with go-libp2p / Kubo.

---

## Table of Contents

1. [What is Yamux and Why Do We Need It?](#1-what-is-yamux-and-why-do-we-need-it)
2. [Where Yamux Lives in py-libp2p](#2-where-yamux-lives-in-py-libp2p)
3. [Step 1 — Host Creation: Wiring Yamux In](#step-1--host-creation-wiring-yamux-in)
4. [Step 2 — TCP Connection & Security Upgrade](#step-2--tcp-connection--security-upgrade)
5. [Step 3 — Muxer Protocol Negotiation (multistream-select)](#step-3--muxer-protocol-negotiation-multistream-select)
6. [Step 4 — Yamux Object Instantiation](#step-4--yamux-object-instantiation)
7. [Step 5 — Yamux Start & the handle_incoming Loop](#step-5--yamux-start--the-handle_incoming-loop)
8. [Step 6 — Opening a Stream (SYN / ACK Handshake)](#step-6--opening-a-stream-syn--ack-handshake)
9. [Step 7 — Sending Data (Window-Based Flow Control)](#step-7--sending-data-window-based-flow-control)
10. [Step 8 — Receiving Data in handle_incoming](#step-8--receiving-data-in-handle_incoming)
11. [Step 9 — Closing a Stream (FIN / Half-Close)](#step-9--closing-a-stream-fin--half-close)
12. [Step 10 — Resetting a Stream (RST)](#step-10--resetting-a-stream-rst)
13. [Step 11 — Ping / Pong & RTT Measurement](#step-11--ping--pong--rtt-measurement)
14. [Step 12 — Connection Teardown (GO_AWAY)](#step-12--connection-teardown-go_away)
15. [The Bug: SYN+RST Frame Mishandling](#the-bug-synrst-frame-mishandling)
16. [The Fix](#the-fix)
17. [Quick Reference: Frame Types & Flags](#quick-reference-frame-types--flags)

---

## 1. What is Yamux and Why Do We Need It?

### The Problem: One TCP Connection, Many Logical Channels

A raw TCP connection is a single byte-stream between two peers. If two programs
want to talk about multiple things at the same time (e.g. one stream for block
exchange, another for DHT queries, another for identify), they would normally
need multiple TCP connections — which is expensive (separate TLS handshakes,
OS resources, NAT traversal per connection).

**Stream multiplexing** solves this: it lets you run many independent logical
streams over a single physical connection.

### What is Yamux?

**Yamux** (Yet Another MUltipleXer) is a stream-multiplexing protocol originally
written by HashiCorp. It is:

- **Binary framed** — every logical message is wrapped in a 12-byte header.
- **Full-duplex** — both sides can open streams independently.
- **Flow-controlled** — each stream has its own credit window (like TCP within TCP).
- **Lightweight** — no per-stream connection setup beyond a single SYN frame.

The libp2p ecosystem chose Yamux as the **preferred** muxer because it
interoperates cleanly with go-libp2p, rust-libp2p, and Kubo (go-IPFS).

### The Alternative: Mplex

py-libp2p also ships with **Mplex** (`/mplex/6.7.0`), an older and simpler
multiplexer. It lacks flow control and is being phased out across the ecosystem.
Yamux (`/yamux/1.0.0`) is the default.

---

## 2. Where Yamux Lives in py-libp2p

```
libp2p/
├── __init__.py                          ← new_host(), muxer wiring
├── stream_muxer/
│   ├── muxer_multistream.py             ← MuxerMultistream (negotiation + factory)
│   └── yamux/
│       ├── __init__.py
│       └── yamux.py                     ← YamuxStream + Yamux (the full implementation)
└── protocol_muxer/
    ├── multiselect.py                   ← server-side protocol negotiation
    └── multiselect_client.py            ← client-side protocol negotiation
```

The two main classes in `yamux.py`:

| Class | Role |
|---|---|
| `YamuxStream` | A single logical stream (read / write / close / reset) |
| `Yamux` | The muxed connection; manages all streams, runs the frame loop |

---

## Step 1 — Host Creation: Wiring Yamux In

**File:** `libp2p/__init__.py` → `new_host()` / `new_swarm()`

When you call:

```python
from libp2p import new_host
host = new_host(key_pair=key_pair, muxer_preference="YAMUX")
```

Internally, `new_swarm()` builds a **muxer options dict** that maps protocol
string → muxer class:

```python
{
    TProtocol("/yamux/1.0.0"): Yamux,   # primary
    TProtocol("/mplex/6.7.0"): Mplex,   # fallback
}
```

This dict is handed to a `TransportUpgrader`, which in turn creates a
`MuxerMultistream` instance. `MuxerMultistream` holds the ordered list of
muxers that this peer is willing to speak.

**Key point:** At this stage no Yamux object exists yet. We only registered
*which* muxer classes are available. The actual `Yamux` instance is created
per-connection, after the muxer is negotiated.

---

## Step 2 — TCP Connection & Security Upgrade

**File:** `libp2p/transport/tcp/tcp.py` + `TransportUpgrader`

When a TCP connection is established (either dialing out or accepting in), the
raw socket is immediately **upgraded** through two layers:

```
Raw TCP socket
    │
    ▼
[Security Negotiation]   ← multistream-select picks Noise or TLS
    │
    ▼
Encrypted / Authenticated connection  (ISecureConn)
    │
    ▼
[Muxer Negotiation]      ← multistream-select picks /yamux/1.0.0
    │
    ▼
Yamux muxed connection   (IMuxedConn)
```

The security layer (Noise / TLS) runs its own multistream-select handshake first.
Only after the connection is encrypted does the muxer negotiation happen.

---

## Step 3 — Muxer Protocol Negotiation (multistream-select)

**File:** `libp2p/stream_muxer/muxer_multistream.py` → `MuxerMultistream.new_conn()`

**multistream-select** is libp2p's meta-protocol for agreeing on sub-protocols.
Every negotiation follows this pattern over the encrypted connection:

```
Initiator (dialer)          Responder (listener)
─────────────────           ────────────────────
→ /multistream/1.0.0\n
                            ← /multistream/1.0.0\n
→ /yamux/1.0.0\n
                            ← /yamux/1.0.0\n      (agreement!)
```

If the responder doesn't support the requested protocol, it replies `na\n` and
the initiator tries the next one in its list (e.g. `/mplex/6.7.0`).

The Python code path:

```python
# muxer_multistream.py
protocol, transport_class = await self._selector.select(
    conn, conn.is_initiator, self.negotiate_timeout
)
# protocol == "/yamux/1.0.0"
# transport_class == Yamux
```

- **Initiator** uses `MultiselectClient.select_one_of()` to propose protocols.
- **Responder** uses `Multiselect.negotiate()` to listen and confirm.

After agreement, `new_conn()` instantiates `Yamux(conn, peer_id, ...)` and
returns it.

---

## Step 4 — Yamux Object Instantiation

**File:** `yamux.py` → `Yamux.__init__()`

```python
Yamux(secured_conn, peer_id, is_initiator=True/False, on_close=...)
```

Key internal state initialized here:

| Attribute | Purpose |
|---|---|
| `next_stream_id` | `1` for initiator (odd IDs), `2` for responder (even IDs) |
| `streams` | `dict[stream_id → YamuxStream]` |
| `stream_buffers` | `dict[stream_id → bytearray]` — inbound data per stream |
| `stream_events` | `dict[stream_id → trio.Event]` — signals new data/state change |
| `new_stream_send_channel` | Channel to deliver newly-opened remote streams |
| `_write_lock` | Serializes all frame writes (only one writer at a time) |
| `event_shutting_down` | Set when the connection is being torn down |
| `_rtt` | Smoothed round-trip time (updated by ping/pong) |

**Stream ID assignment (per Yamux spec):**
- Initiator uses **odd** IDs: 1, 3, 5, …
- Responder uses **even** IDs: 2, 4, 6, …
- This prevents ID collisions when both sides open streams simultaneously.

---

## Step 5 — Yamux Start & the handle_incoming Loop

**File:** `yamux.py` → `Yamux.start()`

```python
await yamux_conn.start()
```

`start()` opens a **trio nursery** and launches two background tasks:

```
trio nursery
├── _handle_incoming_with_ready_signal()   ← the main frame-reading loop
└── _measure_rtt_loop()                    ← periodic ping/pong for RTT
```

`nursery.start()` is used (not `start_soon`) so that `handle_incoming` is
**guaranteed to be running** before `start()` returns. This prevents a race
where a stream could be opened before the loop is ready to process ACKs.

Once started, `event_started` is set and `_established = True`.

### The handle_incoming Loop

This is the **heart of Yamux**. It runs forever, reading one 12-byte header at
a time from the encrypted connection, then dispatching based on frame type:

```
while not shutting_down:
    header = await read_exactly(conn, 12 bytes)
    version, type, flags, stream_id, length = unpack(header)

    if SYN:       → new stream or window update on new stream
    elif ACK:     → stream accepted / data on existing stream
    elif DATA:    → data for existing stream
    elif WINDOW_UPDATE: → flow control credit for existing stream
    elif PING:    → respond with PONG (or record RTT)
    elif GO_AWAY: → peer is closing connection
```

---

## Step 6 — Opening a Stream (SYN / ACK Handshake)

### Initiator side: `open_stream()`

```python
stream = await yamux.open_stream()
```

1. Allocates a new `YamuxStream` with the next odd/even stream ID.
2. Registers it in `streams`, `stream_buffers`, `stream_events`.
3. Sends a **SYN frame**:

```
┌─────────┬──────┬───────┬───────────┬────────┐
│ version │ type │ flags │ stream_id │ length │
│  0x00   │ 0x01 │ SYN   │    1      │   0    │
│         │ WIN  │ 0x01  │           │        │
└─────────┴──────┴───────┴───────────┴────────┘
```

Type `0x01` = `TYPE_WINDOW_UPDATE` with `FLAG_SYN` = open a new stream.

### Responder side: `handle_incoming()` on SYN

When the responder's `handle_incoming` loop sees a frame with `FLAG_SYN` and the
stream ID is **not yet known**:

1. Creates a new `YamuxStream(stream_id, self, is_initiator=False)`.
2. Registers it in `streams`, `stream_buffers`, `stream_events`.
3. Sends back an **ACK frame**:

```
┌─────────┬──────┬───────┬───────────┬────────┐
│ version │ type │ flags │ stream_id │ length │
│  0x00   │ 0x01 │ ACK   │    1      │   0    │
│         │ WIN  │ 0x02  │           │        │
└─────────┴──────┴───────┴───────────┴────────┘
```

4. Sends the new stream into `new_stream_send_channel`.

### Accepting a stream: `accept_stream()`

On the responder's application side:

```python
stream = await yamux.accept_stream()
```

This simply awaits the next item from `new_stream_receive_channel` — the channel
that `handle_incoming` fills whenever a SYN is processed.

**Full SYN/ACK flow:**

```
Initiator                          Responder
─────────                          ─────────
open_stream()
  → WINDOW_UPDATE SYN stream=1
                                   handle_incoming sees SYN
                                   creates YamuxStream(1)
                                   ← WINDOW_UPDATE ACK stream=1
                                   accept_stream() returns stream 1
stream is now open both sides
```

---

## Step 7 — Sending Data (Window-Based Flow Control)

**File:** `yamux.py` → `YamuxStream.write()`

Each stream has a **send window** (default 256 KB). The sender may only transmit
as many bytes as the current window allows.

```python
await stream.write(data)
```

Loop until all bytes sent:
1. Check `send_window > 0`.
2. Slice up to `min(send_window, MAX_MESSAGE_SIZE - HEADER_SIZE, remaining)` bytes.
3. Build a `DATA` frame (type `0x00`) and write it.
4. Decrement `send_window` by bytes sent.
5. If window hits zero, wait (polling with 5-second timeout) for a
   `WINDOW_UPDATE` from the receiver.

**Max frame payload:** 64 KB (matches go-yamux default).

---

## Step 8 — Receiving Data in handle_incoming

When a `TYPE_DATA` frame arrives for an **existing** stream:

1. Read `length` bytes from the connection.
2. `stream_buffers[stream_id].extend(data)` — append to the stream's buffer.
3. Decrement `recv_window` by the number of bytes received.
4. Set `stream_events[stream_id]` — wakes up any `read()` waiter.

### Auto-tuning the Receive Window

`YamuxStream.read()` calls `_auto_tune_and_send_window_update()` after consuming
data. This ports go-yamux's two-pass `GrowTo` logic:

1. **Pass 1:** Restore window to `target_recv_window`.
2. **Auto-tune:** If data arrived within `4 × RTT` of the last epoch, double
   `target_recv_window` (up to 16 MB max).
3. **Pass 2:** If target grew, send the extra delta too.
4. Send a single `WINDOW_UPDATE` frame with the total delta to the peer.

This adaptive window allows throughput to scale up for fast peers while staying
conservative for slow ones — matching go-yamux behavior exactly.

---

## Step 9 — Closing a Stream (FIN / Half-Close)

**File:** `yamux.py` → `YamuxStream.close()`

Yamux supports **half-close** (like TCP FIN). Closing a stream only stops
*sending*; the remote side can still send data until it also closes.

```python
await stream.close()
```

1. Sends a `WINDOW_UPDATE` frame with `FLAG_FIN`:

```
┌─────────┬──────┬───────┬───────────┬────────┐
│ version │ type │ flags │ stream_id │ length │
│  0x00   │ 0x01 │ FIN   │    1      │   0    │
│         │ WIN  │ 0x04  │           │        │
└─────────┴──────┴───────┴───────────┴────────┘
```

2. Sets `send_closed = True`.
3. If `recv_closed` is also `True` → sets `closed = True` (fully closed).

On the receiver's `handle_incoming`, a frame with `FLAG_FIN` sets
`stream.recv_closed = True` and wakes the reader. If the reader is waiting,
it drains remaining buffer data and then raises `MuxedStreamEOF`.

---

## Step 10 — Resetting a Stream (RST)

**File:** `yamux.py` → `YamuxStream.reset()`

RST is an **abrupt** close — no more data, both directions immediately.

```python
await stream.reset()
```

Sends a `WINDOW_UPDATE` frame with `FLAG_RST`:

```
┌─────────┬──────┬───────┬───────────┬────────┐
│ version │ type │ flags │ stream_id │ length │
│  0x00   │ 0x01 │ RST   │    1      │   0    │
│         │ WIN  │ 0x08  │           │        │
└─────────┴──────┴───────┴───────────┴────────┘
```

Sets `closed = send_closed = recv_closed = reset_received = True`.

On the receiver's `handle_incoming`, `FLAG_RST` sets `stream.closed = True` and
`stream.reset_received = True`. Any pending `read()` raises `MuxedStreamReset`.

---

## Step 11 — Ping / Pong & RTT Measurement

**File:** `yamux.py` → `Yamux._measure_rtt_loop()`

Every 30 seconds (after an initial 0.5 s delay), the connection sends a `PING`
frame with `FLAG_SYN`:

```
┌─────────┬──────┬───────┬───────────┬──────────┐
│ version │ type │ flags │ stream_id │  value   │
│  0x00   │ 0x02 │ SYN   │    0      │  nonce   │
│         │ PING │ 0x01  │           │          │
└─────────┴──────┴───────┴───────────┴──────────┘
```

The remote side immediately echoes it back with `FLAG_ACK`. The sender measures
the elapsed time and updates `_rtt` using exponential smoothing:

```python
new_rtt = now - ping_sent_time
_rtt = (_rtt + new_rtt) / 2
```

This RTT value drives the auto-tune window logic in `_auto_tune_and_send_window_update`.

---

## Step 12 — Connection Teardown (GO_AWAY)

**File:** `yamux.py` → `Yamux.close()`

To cleanly shut down, the connection sends a `GO_AWAY` frame:

```
┌─────────┬──────┬───────┬───────────┬────────────┐
│ version │ type │ flags │ stream_id │ error_code │
│  0x00   │ 0x03 │   0   │    0      │    0x0     │
│         │ GWAY │       │           │  (normal)  │
└─────────┴──────┴───────┴───────────┴────────────┘
```

Error codes:
- `0x0` — Normal termination
- `0x1` — Protocol error
- `0x2` — Internal error

After sending `GO_AWAY`:
1. `event_shutting_down` is set.
2. `new_stream_send_channel` is closed (unblocks any pending `accept_stream()`).
3. All streams are marked closed and their events are set (wakes all readers).
4. The underlying `secured_conn` is closed.
5. `event_closed` is set.
6. The `on_close` callback is invoked.

---

## The Bug: SYN+RST Frame Mishandling

### Background

The Yamux spec allows **flag combinations** on a single frame. In particular, a
frame can carry **both `FLAG_SYN` and `FLAG_RST`** simultaneously. This means:

> "I am opening a new stream, but I am immediately resetting it."

This is a valid edge case that go-libp2p (and Kubo) can send during certain
protocol negotiation failures or when a stream is rejected before it is fully
established.

### What Was Added in the "Latest" Version

The latest `py-libp2p` (merged into the official repo) added handling for
`FLAG_FIN` and `FLAG_RST` arriving together with `FLAG_SYN`. The FIN handling
was correct. The RST handling had a subtle but critical bug.

Here is the relevant code path in `handle_incoming()`, inside the `FLAG_SYN`
branch, for a **new** (not yet seen) stream ID:

```python
# 1. Create the stream object
stream = YamuxStream(stream_id, self, False)
self.streams[stream_id] = stream
self.stream_buffers[stream_id] = bytearray()
self.stream_events[stream_id] = trio.Event()

# 2. Handle optional data / window update ...

# 3. Handle FIN flag (correct)
if flags & FLAG_FIN:
    stream.recv_closed = True
    if stream.send_closed:
        stream.closed = True
    self.stream_events[stream_id].set()

# 4. Handle RST flag (BUGGY)
if flags & FLAG_RST:
    stream.closed = True
    stream.reset_received = True
    self.stream_events[stream_id].set()

# 5. ← BUG: This runs UNCONDITIONALLY, even when RST was set
ack_header = struct.pack(...)   # ACK frame
new_stream_notify = stream      # put stream in accept queue
```

**The bug:** Steps 4 and 5 are independent `if` blocks. When `FLAG_RST` is set,
step 4 correctly marks the stream as dead. But step 5 runs regardless — it
**still builds an ACK** and **still enqueues the dead stream** into
`new_stream_send_channel`.

### Consequences

1. **False ACK to the remote peer:** The Python peer sends `WINDOW_UPDATE ACK`
   back to go-libp2p, telling it "I accepted your stream." But go-libp2p already
   reset that stream — receiving an unexpected ACK for a dead stream confuses its
   state machine.

2. **Zombie stream in accept queue:** `accept_stream()` returns a stream that is
   already `closed = True` and `reset_received = True`. Any attempt to read from
   or write to it immediately raises an exception, causing the protocol handler to
   fail.

3. **Interop breaks:** go-libp2p / Kubo use `SYN+RST` in specific protocol
   negotiation flows. Every time this happens, the Python peer responds
   incorrectly, leading to connection-level confusion and ultimately failed data
   transfers.

### Why the Working Version Didn't Have This Bug

The **working** version (in `editable_dependency/working/py-libp2p`) simply did
not have the `FLAG_FIN` / `FLAG_RST` handling inside the SYN block at all.
When a `SYN+RST` frame arrived, the RST flag was silently ignored and only the
ACK path ran — which happened to work because go-libp2p rarely sent `SYN+RST`
in the tested scenarios.

The correct fix is not to remove the RST handling (that would be a regression)
but to make the ACK conditional on RST **not** being set.

---

## The Fix

**File:** `libp2p/stream_muxer/yamux/yamux.py`

Change the RST block from two independent `if` statements into a proper
`if / else`:

```python
# BEFORE (buggy)
if flags & FLAG_RST:
    stream.closed = True
    stream.reset_received = True
    self.stream_events[stream_id].set()

# Always runs — even after RST!
ack_header = struct.pack(YAMUX_HEADER_FORMAT, 0, TYPE_WINDOW_UPDATE, FLAG_ACK, stream_id, 0)
new_stream_notify = stream
```

```python
# AFTER (fixed)
if flags & FLAG_RST:
    stream.closed = True
    stream.reset_received = True
    self.stream_events[stream_id].set()
else:
    # Only ACK and enqueue the stream if it was NOT reset
    ack_header = struct.pack(YAMUX_HEADER_FORMAT, 0, TYPE_WINDOW_UPDATE, FLAG_ACK, stream_id, 0)
    new_stream_notify = stream
```

**Why this is correct:**

- When `SYN+RST` arrives, the stream is dead on arrival. We register it (so any
  stray frames for that ID are handled gracefully), mark it closed, and silently
  discard it — no ACK, no enqueue.
- When `SYN` alone (or `SYN+FIN`) arrives, the normal ACK path runs and the
  stream is delivered to `accept_stream()`.
- This mirrors the pattern already used for `syn_payload_err`: when the SYN
  payload can't be read, the stream is created and closed without ACKing.

### Verification

After applying the fix, all four interop tests pass:

```
Test 1: Go adds file → Python fetches     PASS
Test 2: Python adds file → Go fetches     PASS
Test 3: Go adds large file → Python fetches  PASS
Test 4: Python adds large file → Go fetches  PASS

All tests passed!
```

---

## Quick Reference: Frame Types & Flags

### Frame Header (12 bytes, big-endian)

```
 0       1       2       3       4       5       6       7
┌───────┬───────┬───────────────┬───────────────────────────────┐
│  ver  │ type  │     flags     │           stream_id           │
├───────┴───────┴───────────────┼───────────────────────────────┤
│                            length                             │
└───────────────────────────────────────────────────────────────┘
```

### Frame Types

| Value | Name | Purpose |
|---|---|---|
| `0x0` | `DATA` | Carry payload bytes for a stream |
| `0x1` | `WINDOW_UPDATE` | Adjust flow-control window (also used for SYN/FIN/RST signals) |
| `0x2` | `PING` | Measure RTT |
| `0x3` | `GO_AWAY` | Graceful connection shutdown |

### Flags (bitmask)

| Bit | Value | Name | Meaning |
|---|---|---|---|
| 0 | `0x1` | `SYN` | Start a new stream (or ping request) |
| 1 | `0x2` | `ACK` | Acknowledge a SYN (or ping response) |
| 2 | `0x4` | `FIN` | Half-close: no more data from sender |
| 3 | `0x8` | `RST` | Abrupt close: stream is dead immediately |

### Valid Flag Combinations

| Combination | Meaning |
|---|---|
| `SYN` | Open new stream |
| `ACK` | Confirm new stream |
| `FIN` | Half-close stream |
| `RST` | Reset stream |
| `SYN+FIN` | Open stream that is immediately half-closed |
| `SYN+RST` | Open stream that is immediately fully reset (edge case, triggers the bug) |
| `DATA+FIN` | Last data frame before half-close |

### Stream ID Assignment

| Role | IDs |
|---|---|
| Initiator (dialer) | 1, 3, 5, 7, … (odd) |
| Responder (listener) | 2, 4, 6, 8, … (even) |

### Default Limits

| Constant | Value | Purpose |
|---|---|---|
| `DEFAULT_WINDOW_SIZE` | 256 KB | Initial flow-control window per stream |
| `MAX_WINDOW_SIZE` | 16 MB | Maximum auto-tuned window size |
| `MAX_MESSAGE_SIZE` | 64 KB | Maximum payload per DATA frame |
| `HEADER_SIZE` | 12 bytes | Fixed Yamux frame header size |
| `RTT_MEASURE_INTERVAL` | 30 s | How often ping/pong runs |
| `stream_backlog_limit` | 256 | Max pending unaccepted streams |
