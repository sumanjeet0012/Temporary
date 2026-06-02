# Circuit Relay v2 in py-libp2p — A Complete Walkthrough

______________________________________________________________________

## Part 1: What Is a Relay and Why Do We Need It?

### The Problem Without Relay

Modern devices rarely have public IP addresses. Most are hidden behind NAT (Network Address Translation) routers, corporate firewalls, or operating under ISP-level CGNAT. When two such peers try to connect directly:

```
Peer A (NAT)          Peer B (NAT)
  |                       |
[Router A]            [Router B]
  |                       |
  |---  Internet  --------|
```

- **Peer A cannot reach Peer B** directly because Peer B has no publicly routable address.
- **Peer B cannot reach Peer A** for the same reason.
- A direct TCP dial simply fails — the SYN packet arrives at the remote NAT box but is silently dropped.

This is called the **NAT traversal problem**, and it affects a huge fraction of real-world devices (home computers, mobile phones, IoT nodes, nodes inside cloud VPCs, etc.).

### What a Relay Solves

A **relay node** is a peer with a stable, publicly reachable address. It sits on the open internet and acts as a **forwarding proxy** between two NAT-ed peers:

```
Peer A (NAT)          Relay (Public IP)         Peer B (NAT)
  |                        |                        |
  |--- connect to relay -->|<--- connect to relay --|
  |                        |                        |
  |<== relayed circuit =============================>|
```

Both peers maintain outbound connections to the relay. The relay stitches them together into a single logical circuit. Data flows: A → Relay → B and B → Relay → A, transparently.

### Why Circuit Relay v2 Specifically?

libp2p went through two relay protocol generations:

| Version           | Status        | Key Weakness                                                                 |
| ----------------- | ------------- | ---------------------------------------------------------------------------- |
| Circuit Relay v1  | ❌ Deprecated | Unlimited resource use; no reservation system; easy to abuse                 |
| **Circuit Relay v2** | ✅ Current | Explicit **reservation** system; resource limits per peer; hop/stop split    |

**Circuit Relay v2** (defined in [the libp2p spec](https://github.com/libp2p/specs/blob/master/relay/circuit-v2.md)) solves v1's resource-abuse problem by requiring the **destination** peer to hold an active **reservation** on the relay before any source can connect through it.

______________________________________________________________________

## Part 2: Core Concepts

### 2.1 Roles — HOP, STOP, CLIENT

Every peer in a circuit can play one or more of three roles. py-libp2p models these as bit-flags:

```python
# libp2p/relay/circuit_v2/config.py:80-91
class RelayRole(Flag):
    HOP    = auto()   # Act as a relay for others
    STOP   = auto()   # Accept relayed connections as the destination
    CLIENT = auto()   # Dial through existing relays as the source
```

| Role       | Who plays it?         | What it does                                                                |
| ---------- | --------------------- | --------------------------------------------------------------------------- |
| **HOP**    | The relay node        | Accepts RESERVE and CONNECT requests; stitches circuits together            |
| **STOP**   | The destination peer  | Receives a STOP CONNECT from the relay; accepts the incoming circuit        |
| **CLIENT** | The source/dialing peer | Makes reservations and dials destinations through the relay               |

A real-world relay node typically has `HOP | STOP | CLIENT` enabled. A destination peer uses `STOP | CLIENT`.

### 2.2 Reservations — The Explicit Opt-In

Before a destination can be reached through a relay, it must hold an active **reservation** on that relay. The reservation is:

- **Explicit**: the destination peer sends a `RESERVE` message to the relay and receives a signed voucher in return.
- **Time-bounded**: reservations expire (default TTL: 1 hour).
- **Capacity-limited**: the relay enforces `max_reservations` globally.
- **A gatekeeping mechanism**: the relay will only forward CONNECT requests to destinations that have reserved.

```
Destination ──RESERVE──▶ Relay
Relay ─────voucher────▶ Destination    ← signed proof of reservation
```

Without a reservation, the relay's `can_accept_connection()` returns `False` for the destination, and the CONNECT is rejected.

### 2.3 The Circuit Multiaddr

A relay connection is addressed using a special multiaddr format that encodes the full path:

```
/ip4/1.2.3.4/tcp/4001/p2p/QmRelay/p2p-circuit/p2p/QmDestination
 \_____relay transport________/ \_____/ \__destination peer ID__/
                                 marker
```

Components:
- **Relay transport** (`/ip4/.../tcp/.../p2p/QmRelay`) — how to reach the relay itself.
- **`/p2p-circuit`** — the marker that says "this is a relayed address".
- **Destination peer ID** (`/p2p/QmDestination`) — the final target.

py-libp2p parses this with `parse_circuit_ma()`:

```python
# libp2p/relay/circuit_v2/transport.py:472-517
def parse_circuit_ma(self, ma: multiaddr.Multiaddr) -> tuple[multiaddr.Multiaddr, ID]:
    # Must contain /p2p-circuit
    if not any(p.code == P_P2P_CIRCUIT for p in protocols):
        raise ValueError(f"Missing /p2p-circuit in Multiaddr: {ma}")

    # Rightmost /p2p = destination
    dest_id_str = ma.get_peer_id()
    target_peer_id = ID.from_base58(dest_id_str)

    # Strip /p2p/<dest> then /p2p-circuit → what's left is the relay MA
    without_dest = ma.decapsulate_code(P_P2P)
    relay_ma = without_dest.decapsulate_code(P_P2P_CIRCUIT)
    return relay_ma, target_peer_id
```

### 2.4 Resource Limits

The relay enforces configurable limits via `RelayLimits`:

```python
# libp2p/relay/circuit_v2/resources.py:46-52
@dataclass
class RelayLimits:
    duration: int           # Max circuit lifetime in seconds (default: 3600)
    data: int               # Max bytes per circuit (default: 1 GB)
    max_circuit_conns: int  # Max concurrent circuits per reservation (default: 8)
    max_reservations: int   # Max total active reservations (default: 4)
```

These limits are embedded in the `RESERVE` response so the client knows what it's allocated.

### 2.5 Protocol IDs

```python
# libp2p/relay/circuit_v2/protocol.py:79-80
PROTOCOL_ID      = TProtocol("/libp2p/circuit/relay/2.0.0")        # HOP streams
STOP_PROTOCOL_ID = TProtocol("/libp2p/circuit/relay/2.0.0/stop")   # STOP streams
```

- **`/libp2p/circuit/relay/2.0.0`** — used between the source/destination and the relay (RESERVE and CONNECT requests).
- **`/libp2p/circuit/relay/2.0.0/stop`** — used by the relay to notify the destination that a circuit is arriving.

______________________________________________________________________

## Part 3: How Circuit Relay v2 Works in py-libp2p (Step by Step)

The relay flow involves two independent phases: **reservation setup** (done in advance by the destination) and **connection establishment** (done on-demand by the source). Here is the complete journey.

______________________________________________________________________

### Step 1: All Three Peers Start Up

Three hosts are created — **relay**, **source**, and **destination** — and each registers the appropriate protocol handlers.

**Files:** `libp2p/relay/circuit_v2/protocol.py`, `libp2p/relay/circuit_v2/transport.py`

```python
# relay node: handles both HOP and STOP protocols
relay_protocol = CircuitV2Protocol(relay_host, limits=make_limits(), allow_hop=True)
relay_host.set_stream_handler(PROTOCOL_ID,      relay_protocol._handle_hop_stream)
relay_host.set_stream_handler(STOP_PROTOCOL_ID, relay_protocol._handle_stop_stream)

# destination node: handles STOP protocol only
destination_protocol = CircuitV2Protocol(destination_host, allow_hop=False)
destination_host.set_stream_handler(STOP_PROTOCOL_ID, destination_protocol._handle_stop_stream)

# source node: purely a CLIENT
source_transport = CircuitV2Transport(source_host, source_protocol,
    RelayConfig(roles=RelayRole.STOP | RelayRole.CLIENT, limits=make_limits()))
```

At this point all three peers are listening but no circuits exist.

______________________________________________________________________

### Step 2: Destination Connects to the Relay

The destination peer dials the relay over a normal TCP connection and sends a **RESERVE** message on the HOP protocol stream:

```
Destination ──(TCP connect)──▶ Relay
Destination ──RESERVE msg───▶ Relay._handle_hop_stream()
                                └──▶ _handle_reserve()
```

**File:** `libp2p/relay/circuit_v2/protocol.py` — `_handle_reserve()`

```python
# libp2p/relay/circuit_v2/protocol.py:547-665
async def _handle_reserve(self, stream: INetStream, msg: HopMessage) -> None:
    peer_id = ID(msg.peer)

    # Check capacity
    if not self.resource_manager.can_accept_reservation(peer_id):
        # Send RESOURCE_LIMIT_EXCEEDED and return
        ...

    # Create the reservation entry
    self.resource_manager.reserve(peer_id)

    # Build signed voucher
    reservation_obj = self.resource_manager._reservations.get(peer_id)
    pb_reservation = reservation_obj.to_proto()   # includes signature + expiry

    # Send back STATUS=OK with the reservation object and limits
    response = HopMessage(
        type=HopMessage.STATUS,
        status=create_status(code=StatusCode.OK, ...),
        reservation=pb_reservation,
        limit=Limit(duration=self.limits.duration, data=self.limits.data),
    )
    await stream.write(response.SerializeToString())
```

After this step, the relay's `_reservations` dict contains an entry for the destination's peer ID.

______________________________________________________________________

### Step 3: Relay Issues a Signed Reservation Voucher

The `Reservation` object stores a cryptographic voucher:

**File:** `libp2p/relay/circuit_v2/resources.py` — `Reservation._generate_voucher()` and `to_proto()`

```python
# resources.py:101-126 — Generate a unique voucher token
def _generate_voucher(self) -> bytes:
    random_bytes = os.urandom(16)       # 128 bits of entropy
    timestamp    = str(int(self.created_at * 1_000_000)).encode()
    peer_bytes   = self.peer_id.to_bytes()

    h = hashlib.sha256()
    h.update(random_bytes)
    h.update(timestamp)
    h.update(peer_bytes)
    return h.digest()

# resources.py:177-226 — Sign the voucher with the relay's private key
def to_proto(self) -> PbReservation:
    data_to_sign = RELAY_VOUCHER_DOMAIN_SEP + self.voucher + expiration_bytes
    #              ^ "libp2p-relay-voucher:" prefix
    signature = private_key.sign(data_to_sign)

    return PbReservation(
        expire    = int(self.expires_at),
        voucher   = self.voucher,
        signature = signature,
    )
```

The voucher and signature allow the source peer to attach **proof** of the destination's reservation in its CONNECT request, and the relay to verify it has not been forged.

______________________________________________________________________

### Step 4: Source Dials — `CircuitV2Transport.dial()`

The source peer calls `source_transport.dial(circuit_ma)` with the circuit multiaddr:

**File:** `libp2p/relay/circuit_v2/transport.py` — `dial()` and `dial_peer_info()`

```python
# transport.py:203-255
async def dial(self, maddr: multiaddr.Multiaddr) -> INetConn:
    # 1. Parse /relay_addr/p2p-circuit/p2p/dest
    relay_maddr, dest_peer_id = self.parse_circuit_ma(maddr)

    # 2. Build PeerInfo objects
    relay_peer_info = PeerInfo(relay_peer_id, [relay_maddr])
    dest_info       = PeerInfo(dest_peer_id, [maddr])

    # 3. Do the actual relay dial
    raw_conn = await self.dial_peer_info(dest_info=dest_info, relay_info=relay_peer_info)

    # 4. Upgrade to a full libp2p connection (TLS + muxer)
    return await self.host.upgrade_outbound_connection(raw_conn, dest_info.peer_id)
```

Inside `dial_peer_info()`:

```python
# transport.py:361-401
await self.host.connect(relay_info)          # ① TCP connect to relay
relay_stream = await self.host.new_stream(relay_peer_id, [PROTOCOL_ID])

# ② Optionally make our own reservation on the relay
if self.config.enable_client:
    await self._make_reservation(relay_stream, relay_peer_id)

# ③ Build the HOP CONNECT message
connect_msg = HopMessage(
    type        = HopMessage.CONNECT,
    peer        = dest_info.peer_id.to_bytes(),  # Who we want to reach
    senderRecord= envelope_bytes,                # Our signed peer record
)
# Attach reservation proof if we have one
if reservation_proof and reservation_proof.expire > int(time.time()):
    connect_msg.reservation.CopyFrom(reservation_proof)

await relay_stream.write(connect_msg.SerializeToString())
```

______________________________________________________________________

### Step 5: Relay Receives the CONNECT — `_handle_connect()`

The relay's HOP stream handler dispatches incoming CONNECT requests to `_handle_connect()`:

**File:** `libp2p/relay/circuit_v2/protocol.py` — `_handle_connect()`

```python
# protocol.py:667-702
async def _handle_connect(self, stream: INetStream, msg: HopMessage) -> None:
    peer_id     = ID(msg.peer)                    # ← DESTINATION peer
    source_addr = stream.muxed_conn.peer_id       # ← SOURCE peer

    # Verify reservation proof if supplied
    if msg.HasField("reservation"):
        if not self.resource_manager.verify_reservation(source_addr, msg.reservation):
            await self._send_status(stream, StatusCode.PERMISSION_DENIED, ...)
            await stream.reset()
            return

    # Check resource limits
    if not self.resource_manager.can_accept_connection(peer_id=source_addr):  # ← BUG HERE
        await self._send_status(stream, StatusCode.RESOURCE_LIMIT_EXCEEDED, ...)
        await stream.reset()
        return
    ...
```

> ⚠️ **Note:** Bug #08 lives in this function. See Part 4.

______________________________________________________________________

### Step 6: Relay Opens a STOP Stream to the Destination

After the admission check passes, the relay opens a new stream to the destination and sends a `STOP CONNECT` message:

**File:** `libp2p/relay/circuit_v2/protocol.py` — `_handle_connect()` (continued)

```python
# protocol.py:710-732
# Open stream to the destination on the STOP protocol
dst_stream = await self.host.new_stream(peer_id, [STOP_PROTOCOL_ID])

# Relay sends: "source peer X wants to connect"
stop_msg = StopMessage(
    type         = StopMessage.CONNECT,
    peer         = source_addr.to_bytes(),   # Source peer's ID
    senderRecord = relay_envelope_bytes,     # Relay's signed envelope
)
await dst_stream.write(stop_msg.SerializeToString())

# Wait for destination's STATUS response
resp_bytes = await dst_stream.read(1024)
```

```
Relay ──STOP CONNECT──▶ Destination._handle_stop_stream()
Destination ──STATUS OK──▶ Relay
```

______________________________________________________________________

### Step 7: Destination Handles the STOP Stream — `_handle_stop_stream()`

**File:** `libp2p/relay/circuit_v2/protocol.py` — `_handle_stop_stream()`

```python
# protocol.py:430-503
async def _handle_stop_stream(self, stream: INetStream) -> None:
    msg_bytes = await stream.read(1024)
    stop_msg  = StopMessage()
    stop_msg.ParseFromString(msg_bytes)

    if stop_msg.type != StopMessage.CONNECT:
        await self._send_stop_status(stream, StatusCode.MALFORMED_MESSAGE, ...)
        return

    # Send OK to relay
    src_peer_id     = ID(stop_msg.peer)
    src_peer_record = self.host.get_peerstore().get_peer_record(src_peer_id)
    await self._send_stop_status(stream, StatusCode.OK, "Connection established",
                                 src_peer_record)

    # Upgrade this STOP stream into a full libp2p connection
    await self.handle_incoming_connection(stream, stop_msg.peer)
```

`handle_incoming_connection()` wraps the STOP stream in a `RawConnection` and calls `host.upgrade_inbound_connection()`, which runs TLS and muxer negotiation over the relay channel.

______________________________________________________________________

### Step 8: Relay Stitches the Two Streams Together

Back in `_handle_connect()`, after the destination confirms OK:

```python
# protocol.py:770-800
# Send STATUS=OK to the source peer
await self._send_status(stream, StatusCode.OK, "Connection established", ...)

# Relay data bidirectionally between source stream and destination stream
async with trio.open_nursery() as nursery:
    nursery.start_soon(self._relay_data, stream,     dst_stream, source_addr)
    nursery.start_soon(self._relay_data, dst_stream, stream,     peer_id)
```

`_relay_data()` reads bytes from one stream and writes them to the other in a tight loop. The relay is now a transparent byte-forwarding pipe.

______________________________________________________________________

### Step 9: Application Data Flows Over the Circuit

From the source and destination's perspective, the relay is invisible. They have a `RawConnection` (backed by the relay streams) which gets upgraded like any other connection:

```
Source                   Relay                  Destination
  |                        |                        |
  |<====TCP to relay======>|<====TCP to relay======>|
  |                        |                        |
  | RawConnection (relayed)|                        | RawConnection (relayed)
  |  └── TLS upgrade       |    relay_data() loop   |  └── TLS upgrade
  |      └── muxer         |   ←bytes→ ←bytes→      |      └── muxer
  |          └── streams   |                        |          └── streams
```

The full connection stack (including TLS mutual authentication and stream muxing) runs over the relayed byte channel, exactly as it would over a direct TCP connection.

______________________________________________________________________

### Full Message Sequence Diagram

```
Source               Relay                  Destination
  |                    |                        |
  |                    |<──RESERVE─────────────|   Step 2: dest opts in
  |                    |──voucher+OK──────────▶|   Step 3: signed proof
  |                    |                        |
  |──connect to relay──▶|                       |   Step 4: source dials
  |──RESERVE (opt)────▶|                        |   Step 4: source reserves
  |──HOP CONNECT ──────▶|                       |   Step 4: CONNECT request
  |  (dest=QmDest)      |                        |
  |                     |──STOP CONNECT────────▶|   Step 6: relay notifies dest
  |                     |                  OK──▶|   Step 7: dest accepts
  |                     |◀──STATUS OK─────────  |
  |◀──STATUS OK─────────|                        |   Step 8: relay confirms source
  |                     |                        |
  |<══════ Application Data (relayed) ═══════════|   Step 9: data flows
```

______________________________________________________________________

### Summary Table

| Step | File                                       | What Happens                                                      |
| ---- | ------------------------------------------ | ----------------------------------------------------------------- |
| 1    | `relay/circuit_v2/protocol.py`             | All peers start, protocol handlers registered                     |
| 2    | `relay/circuit_v2/protocol.py:547`         | Destination sends RESERVE → relay creates reservation             |
| 3    | `relay/circuit_v2/resources.py:101`        | Relay generates signed voucher, sends back to destination         |
| 4    | `relay/circuit_v2/transport.py:203`        | Source calls `dial()`, parses circuit multiaddr, opens HOP stream |
| 5    | `relay/circuit_v2/protocol.py:667`         | Relay receives CONNECT, runs admission check (Bug #08 lives here) |
| 6    | `relay/circuit_v2/protocol.py:710`         | Relay opens STOP stream to destination                            |
| 7    | `relay/circuit_v2/protocol.py:430`         | Destination handles STOP, sends OK, upgrades to full connection   |
| 8    | `relay/circuit_v2/protocol.py:798`         | Relay starts bidirectional `_relay_data()` loop                   |
| 9    | `relay/circuit_v2/transport.py:252`        | Source upgrades raw circuit conn (TLS + muxer); app data flows    |

______________________________________________________________________

## Part 4: Bug Analysis

______________________________________________________________________

### Bug #08 — Circuit Relay v2 Target Reservation Bypass

**Report:** `08-relay-target-reservation-bypass/report.md`
**PoC:** `08-relay-target-reservation-bypass/attachments/poc.py`
**Result:** `08-relay-target-reservation-bypass/attachments/result.json`

#### Background — What the Spec Requires

Circuit Relay v2 is built on an **explicit opt-in model for the destination**. The destination must hold an active reservation before the relay will accept any CONNECT targeting it. This is by design:

- Without this check, the relay becomes a conduit for sending unsolicited traffic to **any** peer connected to it, regardless of their intent.
- The reservation model says: *"I, the destination, consent to be reachable via this relay."* No reservation = no consent = no traffic.

#### What Happens (The Bug)

A source peer **with** a reservation can successfully open a relayed application stream to a destination peer that **never made any reservation** on the relay. The destination receives the full application message.

#### Evidence (from `result.json`)

```json
{
  "dest_reserved_before": false,
  "dest_reserved_after":  false,
  "source_reserved_after": true,
  "relay_connect_observation": {
    "handler_invoked": true,
    "target_had_reservation_at_connect": false,
    "source_had_reservation_at_connect": true
  },
  "destination_received_message": "relay-app-message"
}
```

The destination never held a reservation (`dest_reserved_before = false`, `dest_reserved_after = false`), yet `destination_received_message = "relay-app-message"` confirms it received traffic through the relay.

#### Root Cause — Wrong Peer ID in the Admission Check

The `_handle_connect` function receives two distinct identities:

- `peer_id` — the **destination** (extracted from `msg.peer`, i.e., who the source wants to reach)
- `source_addr` — the **source** (the peer that opened this HOP stream)

The admission check is supposed to ask: *"Does the DESTINATION have a reservation?"* Instead, it asks: *"Does the SOURCE have a reservation?"*

```python
# libp2p/relay/circuit_v2/protocol.py:667-702
async def _handle_connect(self, stream: INetStream, msg: HopMessage) -> None:
    peer_id     = ID(msg.peer)                   # ← DESTINATION
    source_addr = stream.muxed_conn.peer_id      # ← SOURCE

    # BUG: The admission check uses source_addr instead of peer_id
    if not self.resource_manager.can_accept_connection(peer_id=source_addr):
        #                                                  ^^^^^^^^^^
        #                                  Should be peer_id (DESTINATION), not source_addr
        await self._send_status(stream, StatusCode.RESOURCE_LIMIT_EXCEEDED, ...)
        await stream.reset()
        return
    # If the SOURCE has a reservation, this passes —
    # even if the DESTINATION never reserved!
```

The `can_accept_connection()` method itself is correct. It looks up the given `peer_id` in the reservations dict and returns `False` if no reservation is found:

```python
# libp2p/relay/circuit_v2/resources.py:449-465
def can_accept_connection(self, peer_id: ID) -> bool:
    reservation = self._reservations.get(peer_id)
    return reservation is not None and reservation.can_accept_connection()
```

The logic is right. The argument is wrong. Passing `source_addr` evaluates the *source's* reservation slot count, not the *destination's* existence in the registry.

#### Why the Existing Reservation Proof Check Does Not Save It

There is a `verify_reservation` check earlier in `_handle_connect()`:

```python
if msg.HasField("reservation"):
    if not self.resource_manager.verify_reservation(source_addr, msg.reservation):
        ...
        return
```

This only runs when the source *attaches a reservation proof* to the CONNECT message. The PoC does exactly that — it makes the source reserve, gets a valid proof, and attaches it. So this check passes because the source's proof is valid. The destination's reservation is never verified.

#### Three-Layer Failure

**Layer 1 — Wrong variable in the admission check:**

```python
# protocol.py:692 (the bug)
if not self.resource_manager.can_accept_connection(peer_id=source_addr):
#                                                          ^^^^^^^^^^^
#                                         source_addr goes here, peer_id should
```

**Layer 2 — No separate check for the destination:**

There is no line in `_handle_connect()` that asks `can_accept_connection(peer_id=peer_id)`. The destination's reservation is never consulted.

**Layer 3 — The relay happily forwards all traffic:**

Because the admission gate uses the wrong peer ID and passes, the relay opens a STOP stream to the destination, which accepts it (because the destination's STOP handler does not independently check relay-side reservations), and the circuit is fully established.

#### Impact

- A destination that never opted in can be reached through the relay.
- The relay's explicit opt-in model for the target side is meaningless.
- A source peer can spend relay resources to deliver unsolicited traffic to a non-reserved target.
- Any policy or firewall assumption that says *"only reserved peers are reachable via this relay"* is violated.
- The issue still requires the destination to be connected to the relay, but it removes the separate target-side reservation requirement that is the entire point of Circuit Relay v2's admission model.

#### Proof of Concept Walk-through

The PoC (`poc.py`) demonstrates this in five steps:

1. **Setup:** Three hosts are created — relay, source, destination.
2. **Destination connects to relay** (no RESERVE is sent — only a plain TCP connection).
3. **Source dials destination** through the relay using `CircuitV2Transport.dial()`. The source *does* make a reservation during `dial_peer_info()`.
4. **The relay's `_handle_connect()` is called.** The PoC patches it with a tracing wrapper that records which peer had a reservation at the moment of the check.
5. **Results are written to `result.json`:** destination received the app message, target had no reservation.

```python
# poc.py:80-100 — Tracing wrapper that observes the bug live
async def tracing_handle_connect(stream, msg) -> None:
    target_peer_id = ID(msg.peer)
    source_peer_id = stream.muxed_conn.peer_id
    relay_connect_observation.update({
        "target_had_reservation_at_connect":
            relay_protocol.resource_manager.has_reservation(target_peer_id),
        "source_had_reservation_at_connect":
            relay_protocol.resource_manager.has_reservation(source_peer_id),
    })
    await original_handle_connect(stream, msg)  # Bug still executes
```

The output confirms: `target_had_reservation_at_connect = false`, yet the connection succeeds.

#### Recommended Fix

The fix requires separating two distinct concerns:

1. **Target admission** — does the destination allow relay traffic? (check `peer_id`)
2. **Source accounting** — has the source hit its connection limit? (check `source_addr`)

```python
# libp2p/relay/circuit_v2/protocol.py — _handle_connect() FIXED

async def _handle_connect(self, stream: INetStream, msg: HopMessage) -> None:
    peer_id     = ID(msg.peer)                   # ← DESTINATION
    source_addr = stream.muxed_conn.peer_id      # ← SOURCE

    # FIX: Check that the DESTINATION has an active reservation
    if not self.resource_manager.can_accept_connection(peer_id=peer_id):
        #                                                      ^^^^^^^^
        #                                   peer_id (DESTINATION), not source_addr
        relay_envelope_bytes, _ = env_to_send_in_RPC(self.host)
        relay_envelope = unmarshal_envelope(relay_envelope_bytes)
        await self._send_status(
            stream,
            StatusCode.NO_RESERVATION,          # Correct status code
            "Destination peer has no active reservation on this relay",
            relay_envelope,
        )
        await stream.reset()
        return

    # Separately check source-side connection limits (optional but correct)
    source_reservation = self.resource_manager._reservations.get(source_addr)
    if source_reservation and not source_reservation.can_accept_connection():
        ...  # source has exceeded its own circuit connection limit
```

This change separates what was previously conflated:

| Check               | Peer ID to use | Purpose                                    |
| ------------------- | -------------- | ------------------------------------------ |
| Target admission    | `peer_id`      | Is destination registered and reachable?   |
| Source limit check  | `source_addr`  | Has source exhausted its connection slots? |

______________________________________________________________________

## Summary

Circuit Relay v2 in py-libp2p provides a robust NAT traversal mechanism with an explicit opt-in reservation model. The reservation system is designed to give destination peers full control over their reachability through a relay. Bug #08 breaks this model by checking the *source's* reservation instead of the *destination's* reservation in the CONNECT admission gate — a one-word variable substitution (`source_addr` → `peer_id`) that collapses the entire security boundary of the protocol's target-side opt-in model.
