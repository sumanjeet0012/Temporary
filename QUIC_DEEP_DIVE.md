# QUIC Transport in py-libp2p — A Complete Walkthrough

______________________________________________________________________

## Part 1: What Is QUIC and Why Does libp2p Use It?

### The Problem With TCP for Modern Networking

TCP has been the backbone of internet transport for decades, but it carries several limitations that matter for peer-to-peer networking:

```
TCP Limitations
  ├── Head-of-line blocking — one lost packet stalls all streams on a connection
  ├── 3-way handshake latency — high round-trip cost to establish a connection
  ├── Separate TLS negotiation — another 1–2 round trips on top of TCP
  ├── No connection migration — IP address changes break the connection
  └── Middlebox ossification — TCP headers are not encrypted; firewalls inspect them
```

In a libp2p network, peers frequently exchange many small protocol streams on the same connection (identify, DHT, pubsub, ping, etc.). TCP's head-of-line blocking means a single dropped packet can cause all those protocol streams to stall simultaneously.

### What QUIC Solves

QUIC (Quick UDP Internet Connections, RFC 9000) runs over UDP and delivers a fundamentally different model:

```
QUIC Benefits
  ├── Integrated TLS 1.3 — authentication + encryption in the first handshake
  ├── Independent streams — a lost packet only blocks the affected stream
  ├── 0-RTT or 1-RTT connection — ~1 fewer round trip than TCP+TLS
  ├── Connection migration — connections survive IP changes (e.g., NAT rebinding)
  └── Encrypted headers — middleboxes cannot see or modify connection metadata
```

For a peer-to-peer protocol like libp2p, these properties are significant:

| Feature                   | TCP + TLS               | QUIC                              |
| ------------------------- | ----------------------- | --------------------------------- |
| Handshake round trips     | 3 (TCP) + 2 (TLS)      | 1 (0-RTT possible)                |
| Stream multiplexing       | Requires muxer (yamux)  | **Native in protocol**            |
| Head-of-line blocking     | ❌ Yes (all streams)     | ✅ No (per-stream only)            |
| Connection migration      | ❌ Breaks on IP change   | ✅ Survives NAT rebind             |
| Metadata privacy          | ❌ Headers visible       | ✅ Encrypted headers               |

### QUIC as Both Transport and Muxer in py-libp2p

QUIC is unique because it collapses the transport and stream-multiplexing layers into one. In py-libp2p the `QUICConnection` class implements **both** `IRawConnection` and `IMuxedConn`, unlike TCP which needs a separate yamux or mplex muxer:

```python
# libp2p/transport/quic/connection.py:47-64
class QUICConnection(IRawConnection, IMuxedConn):
    """
    QUIC connection implementing both raw connection and muxed connection interfaces.
    QUIC natively provides stream multiplexing, so this connection acts as both
    a raw connection (for transport layer) and muxed connection (for upper layers).
    """
```

### The QUIC Multiaddr Format

QUIC uses the `/quic-v1` (RFC 9000) and `/quic` (draft-29) multiaddr components over UDP:

```
/ip4/1.2.3.4/udp/4001/quic-v1/p2p/QmPeer
 \___________/ \______/ \_____/ \_________/
  IP address    UDP       QUIC    Peer ID
                port     version
```

- `/quic-v1` — RFC 9000, the standardized version (preferred).
- `/quic` — IETF draft-29, retained for interoperability with older nodes.

______________________________________________________________________

## Part 2: Core Concepts

### 2.1 Module Structure

The QUIC implementation lives entirely under `libp2p/transport/quic/` and is composed of the following files:

| File                         | Responsibility                                                        |
| ---------------------------- | --------------------------------------------------------------------- |
| `transport.py`               | Entry point — `QUICTransport` class, dial, and listener creation     |
| `config.py`                  | All configuration knobs (`QUICTransportConfig`)                       |
| `listener.py`                | `QUICListener` — receives UDP datagrams and promotes connections      |
| `connection.py`              | `QUICConnection` — stream muxer + raw connection combined             |
| `stream.py`                  | `QUICStream` — individual bidirectional QUIC streams                  |
| `security.py`                | TLS certificate generation and peer identity verification             |
| `connection_id_registry.py`  | Registry mapping QUIC Connection IDs → `QUICConnection` objects       |
| `exceptions.py`              | QUIC-specific exception hierarchy                                     |
| `utils.py`                   | Helper functions (multiaddr parsing, version detection, etc.)         |

### 2.2 Configuration — `QUICTransportConfig`

`QUICTransportConfig` (a dataclass) governs everything from TLS verification to stream limits. Key defaults:

```python
# libp2p/transport/quic/config.py:60-79
@dataclass
class QUICTransportConfig(ConnectionConfig):
    idle_timeout: float = 30.0          # Close idle connections after 30 s
    max_datagram_size: int = 1200       # MTU-safe UDP payload (avoids IP fragmentation)
    enable_draft29: bool = True         # Also support QUIC draft-29 for compatibility
    enable_v1: bool = True              # RFC 9000 QUIC v1 (preferred)
    verify_mode: ssl.VerifyMode = ssl.CERT_NONE   # ← Bug lives here (see Part 4)
    alpn_protocols: list[str] = ["libp2p"]
    max_concurrent_streams: int = 100
    connection_timeout: float = 10.0

    PROTOCOL_QUIC_V1:     TProtocol = TProtocol("quic-v1")  # RFC 9000
    PROTOCOL_QUIC_DRAFT29: TProtocol = TProtocol("quic")    # draft-29
```

The config also carries per-stream timeouts, flow control windows, buffer sizes, and negotiation semaphore limits — all exposed as class-level constants like `STREAM_OPEN_TIMEOUT`, `STREAM_FLOW_CONTROL_WINDOW`, etc.

### 2.3 Security — libp2p TLS over QUIC

libp2p mandates **mutual TLS 1.3** for all QUIC connections. Peer identity is not carried in the QUIC headers; instead it is embedded in a custom X.509 extension:

```
OID: 1.3.6.1.4.1.53594.1.1   ← LIBP2P_TLS_EXTENSION_OID
Contents:
  SEQUENCE {
    publicKey  OCTET STRING   ← libp2p public key (protobuf-serialized)
    signature  OCTET STRING   ← Sign("libp2p-tls-handshake:" || cert_pubkey)
  }
```

The ephemeral certificate is generated by `CertificateGenerator.generate_certificate()`. An ephemeral ECDSA P-256 key signs the certificate, and the libp2p identity key signs the extension. This means:

1. The TLS certificate proves possession of the ephemeral key.
2. The extension signature proves the ephemeral key belongs to the libp2p identity.
3. Together, they bind the TLS session to the libp2p peer ID without using the identity key directly for TLS.

```python
# libp2p/transport/quic/security.py:669-751 — CertificateGenerator.generate_certificate()
cert_private_key = LibP2PKeyConverter.libp2p_to_tls_private_key(libp2p_key)
                 # ↑ Generates an ephemeral ECDSA P-256 key

extension_data = extension_handler.create_signed_key_extension(
    libp2p_private_key=libp2p_key,
    cert_public_key=cert_public_key_bytes,  # DER of ephemeral cert public key
)
# extension_data = ASN.1 DER { pubkey || Sign(b"libp2p-tls-handshake:" || pubkey_bytes) }
```

Verification on the receiver side (`PeerAuthenticator.verify_peer_certificate()`) checks:

1. Certificate validity period (not expired, not yet valid).
2. Presence of the libp2p extension OID.
3. The extension signature verifies under the extracted libp2p public key.
4. The derived peer ID matches the expected peer ID (for outbound dials).

### 2.4 Connection ID Registry

QUIC uses **Connection IDs (CIDs)** — opaque identifiers carried in packet headers — to demultiplex packets from multiple peers arriving on the same UDP socket. The `QUICConnectionIDRegistry` in `connection_id_registry.py` maintains a two-level map:

```
CID → (QUICConnection | pending QuicConnection | None)
         ↑ established     ↑ handshaking         ↑ unknown
```

During the handshake phase, the mapping points to the raw `aioquic.QuicConnection` (pending). After promotion it points to the full `QUICConnection` wrapper. This is critical because QUIC peers can rotate CIDs mid-connection (e.g., after connection migration).

### 2.5 Protocol Versions

```python
# libp2p/transport/quic/config.py:222-223
PROTOCOL_QUIC_V1:     TProtocol = TProtocol("quic-v1")  # RFC 9000
PROTOCOL_QUIC_DRAFT29: TProtocol = TProtocol("quic")    # draft-29
```

Both versions share the same code path internally; they differ only in the aioquic `supported_versions` field. The transport stores separate server/client configs per version keyed as `"quic-v1_server"`, `"quic-v1_client"`, etc.

### 2.6 Stream IDs

QUIC stream IDs follow RFC 9000 encoding rules:

```
Stream ID bit 0:  0 = client-initiated, 1 = server-initiated
Stream ID bit 1:  0 = bidirectional, 1 = unidirectional

Examples:
  0, 4, 8, …   → Client bidirectional  (libp2p uses these)
  1, 5, 9, …   → Server bidirectional
  2, 6, 10, …  → Client unidirectional
  3, 7, 11, …  → Server unidirectional
```

```python
# libp2p/transport/quic/connection.py:251-266
def _calculate_initial_stream_id(self) -> int:
    if self._is_initiator:
        return 0   # Client-initiated bidirectional
    else:
        return 1   # Server-initiated bidirectional
```

______________________________________________________________________

## Part 3: How QUIC Works in py-libp2p (Step by Step)

The lifecycle of a QUIC connection involves three independent phases: **transport initialization**, **dialing (outbound)** or **listening (inbound)**, and **stream-level communication**. Here is the complete journey for both sides.

______________________________________________________________________

### Step 1: Transport Initialization — `QUICTransport.__init__()`

When a libp2p host is configured with QUIC, a `QUICTransport` is created with the host's private key.

**File:** `libp2p/transport/quic/transport.py`

```python
# transport.py:76-118
class QUICTransport(ITransport):
    def __init__(self, private_key: PrivateKey, config: QUICTransportConfig | None = None):
        self._private_key = private_key
        self._peer_id = ID.from_pubkey(private_key.get_public_key())
        self._config = config or QUICTransportConfig()

        # Security manager: generates TLS certs, verifies peer certs
        self._security_manager = create_quic_security_transport(
            self._private_key, self._peer_id, enable_autotls=False
        )

        # Builds QuicConfiguration objects for each version + direction
        self._quic_configs: dict[TProtocol, QuicConfiguration] = {}
        self._setup_quic_configurations()
```

`_setup_quic_configurations()` creates **four** `QuicConfiguration` objects:
- `quic-v1_server`, `quic-v1_client`
- `quic_server`, `quic_client` (draft-29)

Each config has the libp2p TLS certificate, private key, ALPN `["libp2p"]`, and the version's wire-format identifier. The `verify_mode` is set via `_apply_tls_configuration()`.

```python
# transport.py:208-229 — _apply_tls_configuration()
def _apply_tls_configuration(self, config: QuicConfiguration, tls_config: QUICTLSSecurityConfig):
    config.certificate    = tls_config.certificate
    config.private_key    = tls_config.private_key
    config.alpn_protocols = tls_config.alpn_protocols
    config.verify_mode    = ssl.CERT_NONE       # ← BUG: should require peer cert
```

> ⚠️ **Note:** The `ssl.CERT_NONE` assignment here is one of the root causes of the inbound fail-open bug. See Part 4.

______________________________________________________________________

### Step 2: Outbound — Dialing a Peer

When the host wants to connect to a remote QUIC peer, it calls `QUICTransport.dial(maddr)`.

**File:** `libp2p/transport/quic/transport.py` — `dial()`

```python
# transport.py:231-323
async def dial(self, maddr: multiaddr.Multiaddr) -> QUICConnection:
    # 1. Parse and validate the QUIC multiaddr
    host, port = quic_multiaddr_to_endpoint(maddr)
    remote_peer_id = ID.from_string(maddr.get_peer_id())  # Must be present

    # 2. Select the right QuicConfiguration for the version
    config_key = TProtocol(f"{quic_version}_client")
    config = self._quic_configs[config_key]
    config.is_client = True

    # 3. Create aioquic's sans-IO QUIC connection
    native_quic_connection = NativeQUICConnection(configuration=config)

    # 4. Wrap it in the py-libp2p QUICConnection
    connection = QUICConnection(
        quic_connection=native_quic_connection,
        remote_addr=(host, port),
        remote_peer_id=remote_peer_id,   # ← Known for outbound dials
        local_peer_id=self._peer_id,
        is_initiator=True,
        maddr=maddr,
        transport=self,
        security_manager=self._security_manager,
    )

    # 5. Start background tasks and await handshake completion
    await connection.connect(self._background_nursery)
    return connection
```

Inside `connection.connect()`:

```python
# connection.py:398-453
async def connect(self, nursery: trio.Nursery) -> None:
    await self.start()                           # Binds socket, sends Initial packet
    await self._start_background_tasks()         # Event loop, maintenance tasks
    await self._connected_event.wait()           # Wait for HandshakeCompleted event

    # Verify peer identity AFTER handshake
    peer_id = await self._verify_peer_identity_with_security()
    if peer_id:
        self.peer_id = peer_id
    self._established = True
```

______________________________________________________________________

### Step 3: The TLS Handshake (Client Side)

After the Initial packet is sent, the connection's `_client_packet_receiver` loop reads responses and feeds them into aioquic's sans-IO core. The handshake progresses through:

```
Client                         Server
  |                              |
  |──── Initial (ClientHello) ──▶|   aioquic sends, trio writes to UDP socket
  |                              |
  |◀─── Initial + Handshake ────|   ServerHello, EncryptedExtensions, Certificate,
  |     (ServerHello, cert…)     |   CertificateVerify, Finished
  |                              |
  |──── Handshake (Finished) ───▶|   Client finishes
  |                              |
  |   HandshakeCompleted event   |   aioquic fires event internally
```

When aioquic fires `HandshakeCompleted`, the `_event_processing_loop` catches it, sets `_connected_event`, and unblocks the `connect()` waiter:

```python
# connection.py:579-630 — _verify_peer_identity_with_security()
async def _verify_peer_identity_with_security(self) -> ID | None:
    await self._extract_peer_certificate()       # Reads from aioquic TLS context

    if not self._peer_certificate:
        return None                              # ← Silently succeeds if no cert!

    verified_peer_id = self._security_manager.verify_peer_identity(
        self._peer_certificate,
        self._remote_peer_id,
    )
    self._peer_verified = True
    return verified_peer_id
```

______________________________________________________________________

### Step 4: Inbound — Listening for Connections

On the server side, `QUICTransport.create_listener(handler_fn)` creates a `QUICListener`:

**File:** `libp2p/transport/quic/transport.py` — `create_listener()`

```python
# transport.py:363-397
def create_listener(self, handler_function: TQUICConnHandlerFn) -> QUICListener:
    server_configs = {
        version: config
        for version, config in self._quic_configs.items()
        if version.endswith("_server")
    }
    listener = QUICListener(
        transport=self,
        handler_function=handler_function,
        quic_configs=server_configs,
        config=self._config,
        security_manager=self._security_manager,
    )
    self._listeners.append(listener)
    return listener
```

After the listener calls `await listener.listen(maddr)`, it binds a UDP socket and starts the `_handle_incoming_packets` loop.

______________________________________________________________________

### Step 5: Packet Reception and Routing

Every UDP datagram from the network arrives in the `_handle_incoming_packets` loop and is dispatched to `_process_packet`:

**File:** `libp2p/transport/quic/listener.py`

```python
# listener.py:1320-1342
async def _handle_incoming_packets(self) -> None:
    while self._listening and self._socket:
        data, addr = await self._socket.recvfrom(65536)
        if self._nursery:
            self._nursery.start_soon(self._process_packet, data, addr)
```

`_process_packet` examines the QUIC packet header to determine whether it is:

- **Long header** (Initial, Handshake, Retry) → a new connection or ongoing handshake
- **Short header** (1-RTT) → an established connection

For a new long-header packet, `_handle_new_connection()` creates an aioquic `QuicConnection` (in server mode) and registers it as a *pending* connection in the CID registry.

______________________________________________________________________

### Step 6: Handshake Progression — Pending Connection

While a connection is in the *pending* state (handshaking), every incoming packet is processed by `_handle_pending_connection()`, which feeds data to aioquic and calls `_process_quic_events()`.

Key events handled during the pending phase:

| Event                  | Action                                                         |
| ---------------------- | -------------------------------------------------------------- |
| `HandshakeCompleted`   | Triggers `_promote_pending_connection()`                       |
| `ProtocolNegotiated`   | Also triggers promotion if `_handshake_complete` is true      |
| `StreamDataReceived`   | Triggers promotion if handshake complete, otherwise warns     |
| `ConnectionTerminated` | Removes the pending entry                                      |

______________________________________________________________________

### Step 7: Connection Promotion — `_promote_pending_connection()`

This is the most critical step on the inbound path. After the handshake completes, the pending entry is *promoted* to a full `QUICConnection`:

**File:** `libp2p/transport/quic/listener.py` — `_promote_pending_connection()`

```python
# listener.py:978-1118
async def _promote_pending_connection(self, quic_conn, addr, destination_connection_id):
    async with per_cid_lock:
        # 1. Create the QUICConnection wrapper
        connection = QUICConnection(
            quic_connection=quic_conn,
            remote_addr=addr,
            remote_peer_id=None,                # ← No peer ID yet!
            local_peer_id=self._transport._peer_id,
            is_initiator=False,
            ...
        )

        # 2. Register in the CID registry
        await self._registry.promote_pending(pending_cid, connection)

        # 3. Start the connection's background tasks
        await connection.connect(self._nursery)

        # 4. Attempt peer identity verification
        if self._security_manager:
            try:
                peer_id = await connection._verify_peer_identity_with_security()
                if peer_id:
                    connection.peer_id = peer_id
            except Exception as e:
                logger.error(f"Security verification failed: {e}")
                await connection.close()
                return                           # Rejects connection on hard failure

        # 5. Invoke user callback — even if peer_id is still None!
        if quic_key not in self._handler_invoked_quic_ids:
            self._handler_invoked_quic_ids.add(quic_key)
            await self._handler(connection)     # ← Called regardless of cert presence
```

> ⚠️ **Note:** Step 4 silently continues when there is no peer certificate. Step 5 then calls the user handler with an unauthenticated connection. This is the core of Bug #02. See Part 4.

______________________________________________________________________

### Step 8: Stream Lifecycle

Once a connection is established, application code opens and accepts streams:

```python
# Open an outbound stream
stream = await connection.open_stream()

# Accept an inbound stream
stream = await connection.accept_stream(timeout=30.0)
```

Each `QUICStream` maps to an aioquic stream ID. The `_event_processing_loop` watches for `StreamDataReceived` and `StreamReset` events and routes them to the correct `QUICStream` object. Stream data is buffered in the stream object and delivered via `stream.read()`.

Stream IDs are allocated monotonically and follow the QUIC spec parity rules (client always picks even IDs for bidirectional streams).

______________________________________________________________________

### Full Inbound Connection Sequence Diagram

```
Client (remote)                  py-libp2p QUICListener            Application Handler
      |                                   |                                |
      |──── Initial (ClientHello) ───────▶|                                |
      |                                   │ Create pending QuicConnection  |
      |◀─── Initial + Handshake ─────────|                                |
      |     (ServerHello, cert, Finished) |                                |
      |                                   |                                |
      |──── Handshake (Finished) ────────▶|                                |
      |                                   │ HandshakeCompleted event       |
      |                                   │ _promote_pending_connection()  |
      |                                   │   • Create QUICConnection      |
      |                                   │   • Register in CID registry   |
      |                                   │   • connect() → background     |
      |                                   │     tasks started              |
      |                                   │   • _verify_peer_identity()    |
      |                                   │     (may silently skip!)       |
      |                                   │   • invoke handler ────────────▶|
      |──── 1-RTT data ─────────────────▶|   route to QUICConnection      |
      |                                   │   StreamDataReceived event     |
      |                                   │   → QUICStream receive buffer  |
      |                                   │   → stream.read() unblocks ────▶|
```

______________________________________________________________________

### Summary Table

| Step | File                                           | What Happens                                                       |
| ---- | ---------------------------------------------- | ------------------------------------------------------------------ |
| 1    | `transport/quic/transport.py:76`               | `QUICTransport.__init__()` — TLS certs generated, configs built    |
| 2    | `transport/quic/transport.py:231`              | `dial()` — parse multiaddr, create `QUICConnection`, start tasks   |
| 3    | `transport/quic/connection.py:398`             | `connect()` — send Initial packet, await `HandshakeCompleted`      |
| 3b   | `transport/quic/security.py:754`               | `PeerAuthenticator` verifies peer cert + libp2p extension          |
| 4    | `transport/quic/transport.py:363`              | `create_listener()` — build `QUICListener` with server configs     |
| 5    | `transport/quic/listener.py:1320`              | `_handle_incoming_packets()` — read UDP, dispatch to handler       |
| 6    | `transport/quic/listener.py:718`               | `_handle_pending_connection()` — feed aioquic, process events      |
| 7    | `transport/quic/listener.py:978`               | `_promote_pending_connection()` — create connection, call handler  |
| 8    | `transport/quic/connection.py:470`             | `_event_processing_loop()` — route stream data to `QUICStream`s    |

______________________________________________________________________

## Part 4: Bug Analysis

______________________________________________________________________

### Bug #02 — QUIC Inbound Callback Exposure Before Peer Identity Verification

**Report:** `02-quic-inbound-fail-open/report.md`
**PoC:** `02-quic-inbound-fail-open/attachments/poc.py`
**Result:** `02-quic-inbound-fail-open/attachments/result.json`

#### Background — What the Spec Requires

The libp2p QUIC transport is built on the libp2p TLS specification ([libp2p/specs/tls](https://github.com/libp2p/specs/blob/master/tls/tls.md)). The spec is unambiguous:

> *"Nodes MUST present the libp2p Public Key Extension [...] the receiving peer MUST verify the extension and MUST abort the connection if the extension is missing or invalid."*

For QUIC in particular, peer identity is not optional or advisory — it **is** the authentication model. Without a verified peer certificate, the listener has no idea who it is talking to. The application callback must never be invoked for an unauthenticated peer.

#### What Happens (The Bug)

A raw aioquic client can complete the QUIC/TLS handshake **without presenting a peer certificate**. The listener:

1. Creates the `QUICConnection` wrapper.
2. Attempts `_verify_peer_identity_with_security()`.
3. Finds no peer certificate — and **silently returns `None`** instead of aborting.
4. Invokes the application callback with the unauthenticated connection.
5. Accepts and delivers inbound stream data from that unauthenticated connection.

#### Evidence (from `result.json`)

```json
{
  "client_result": {
    "tls_handshake_complete": true,
    "alpn": "libp2p",
    "peer_cert_sent": false,
    "stream_payload_sent": "unauth-quic-stream-data"
  },
  "server_observation": {
    "callback_invoked": true,
    "has_peer_certificate": false,
    "is_established": false,
    "peer_id": "16Uiu2HAmG6gznUPxUzqmERBTz5LQhmmNHbh9QuT3zDBE4godZ9s5",
    "peer_verified": false,
    "remote_peer_id": null,
    "inbound_stream_received": "unauth-quic-stream-data"
  }
}
```

Key observations:
- `peer_cert_sent = false` — the client sent no certificate.
- `callback_invoked = true` — the server still called the user handler.
- `has_peer_certificate = false` — no certificate was available.
- `peer_verified = false` — peer was **not** verified.
- `remote_peer_id = null` — no identity was established.
- `peer_id` **equals** `server_peer_id` — the connection fell back to the **local** peer ID.
- `inbound_stream_received = "unauth-quic-stream-data"` — stream data reached the app.

#### Root Cause — Six Interconnected Defects

##### Defect 1 — `ssl.CERT_NONE` in the Default Config

**File:** `libp2p/transport/quic/config.py:77-79`

```python
@dataclass
class QUICTransportConfig(ConnectionConfig):
    verify_mode: ssl.VerifyMode = ssl.CERT_NONE  # ← Disables certificate requirement
```

`ssl.CERT_NONE` means the TLS layer does not require the peer to present a certificate. This is the correct default for HTTPS clients that don't do mutual TLS, but it is **incorrect** for libp2p QUIC, which mandates mutual authentication.

##### Defect 2 — `ssl.CERT_NONE` Hardcoded in `_apply_tls_configuration()`

**File:** `libp2p/transport/quic/transport.py:208-224`

```python
def _apply_tls_configuration(self, config: QuicConfiguration, tls_config):
    config.certificate         = tls_config.certificate
    config.private_key         = tls_config.private_key
    config.certificate_chain   = tls_config.certificate_chain
    config.alpn_protocols      = tls_config.alpn_protocols
    config.verify_mode         = ssl.CERT_NONE   # ← Overrides even a correct config
```

Even if a caller passed a `QUICTransportConfig` with `verify_mode=ssl.CERT_REQUIRED`, this line silently overrides it with `ssl.CERT_NONE`. The config field is never honoured.

##### Defect 3 — Inbound Connection Created With `remote_peer_id=None`

**File:** `libp2p/transport/quic/listener.py:1014-1018`

```python
connection = QUICConnection(
    quic_connection=quic_conn,
    remote_addr=addr,
    remote_peer_id=None,    # ← Identity is intentionally deferred
    local_peer_id=self._transport._peer_id,
    is_initiator=False,
    ...
)
```

This is not inherently wrong — the identity must be derived from the certificate. But it becomes dangerous when combined with the next defect.

##### Defect 4 — `peer_id` Falls Back to Local Peer ID When Remote Is None

**File:** `libp2p/transport/quic/connection.py:105`

```python
self.peer_id = remote_peer_id or local_peer_id
#              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# When remote_peer_id is None, peer_id = local_peer_id!
```

So `connection.peer_id` returns the **server's own peer ID** for an unauthenticated inbound connection. Application code reading `connection.peer_id` would see the server's identity, not the client's — a misleading and potentially dangerous confusion.

##### Defect 5 — Verification Silently Passes When No Certificate Exists

**File:** `libp2p/transport/quic/connection.py:591-597`

```python
async def _verify_peer_identity_with_security(self) -> ID | None:
    await self._extract_peer_certificate()

    if not self._peer_certificate:
        logger.debug("No peer certificate available for verification")
        return None           # ← Silent return, not an error!
```

The caller in `_promote_pending_connection()` treats `None` as "verification not needed":

```python
# listener.py:1064-1079
peer_id = await connection._verify_peer_identity_with_security()
if peer_id:
    connection.peer_id = peer_id
# ... execution continues to the user callback
```

The `if peer_id:` guard silently skips the peer ID update and falls through to the handler invocation. There is no check for `peer_id is None` as an error condition.

##### Defect 6 — User Callback Is Invoked Before Verification Succeeds

**File:** `libp2p/transport/quic/listener.py:1064-1092`

```python
# listener.py:1064-1092
if self._security_manager:
    try:
        peer_id = await connection._verify_peer_identity_with_security()
        if peer_id:
            connection.peer_id = peer_id
        logger.info("Security verification successful ...")
    except Exception as e:
        logger.error(f"Security verification failed: {e}")
        await connection.close()
        return                   # Only hard exceptions abort!

# ... The callback is always reached unless an exception was raised
if quic_key not in self._handler_invoked_quic_ids:
    self._handler_invoked_quic_ids.add(quic_key)
    await self._handler(connection)   # ← Called with unverified peer!
```

The guard only returns early when `_verify_peer_identity_with_security()` raises an exception. When no certificate is present, the function returns `None` (Defect 5) and no exception is raised — so the `return` is never hit.

#### The Three-Layer Failure Summary

```
Layer 1 — TLS layer allows no certificate  (ssl.CERT_NONE in config + apply_tls_configuration)
           └── aioquic doesn't require client cert → handshake completes with no peer cert

Layer 2 — Verification layer silently passes  (_verify_peer_identity_with_security returns None)
           └── No exception raised → promote_pending_connection continues execution

Layer 3 — Handler layer invokes callback unconditionally
           └── User callback receives an unauthenticated QUICConnection
               └── peer_id = local_peer_id (misleading fallback)
               └── inbound streams are accepted and readable
```

#### Proof of Concept Walk-through

The PoC (`poc.py`) demonstrates this in four steps:

1. **Setup:** A real `QUICTransport` listener is started on a random UDP port using a genuine py-libp2p key pair.

2. **Raw client dials:** An `aioquic` client connects with `verify_mode=ssl.CERT_NONE` and **no certificate configured** — it deliberately skips the peer cert.

3. **Stream data sent:** The raw client opens a QUIC stream and writes `"unauth-quic-stream-data"`.

4. **Results recorded:** The `on_connection` callback (the user handler) reads the connection state and the stream data, writing everything to `result.json`.

```python
# poc.py:52-79 — The user callback that observes the bug
async def on_connection(connection) -> None:
    peer_cert = await connection.get_peer_certificate()
    accepted_details.update({
        "callback_invoked":     True,
        "peer_id":              str(connection.peer_id),
        "remote_peer_id":       str(connection.remote_peer_id()) or None,
        "peer_verified":        bool(connection.is_peer_verified),
        "has_peer_certificate": peer_cert is not None,
    })
    stream = await connection.accept_stream(timeout=5.0)
    payload = await stream.read(4096)
    accepted_details["inbound_stream_received"] = payload.decode()
```

The output confirms the bug: the callback fires, stream data is readable, and the peer is neither identified nor verified.

#### Impact

- An unauthenticated remote peer reaches the application callback.
- The unauthenticated peer can deliver inbound stream data to that callback path.
- Connection slots, callback work, and per-peer state are consumed before authentication succeeds.
- Application code cannot safely assume an inbound QUIC callback represents an authenticated libp2p peer.
- `connection.peer_id` returns the **server's own peer ID** — a misleading identity aliasing bug.
- Any application logic that branches on peer identity (ACLs, routing, rate-limiting) operates on a garbage value.
- The libp2p security trust boundary — "all connections are mutually authenticated" — is completely violated on the inbound path.

#### Recommended Fix

Four targeted changes close all six defects:

**Fix 1 — Change the default `verify_mode` in config:**

```python
# config.py:77-79
verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED   # Require peer certificate
```

**Fix 2 — Honour `verify_mode` in `_apply_tls_configuration()`, do not hardcode it:**

```python
# transport.py:208-224 — FIXED
def _apply_tls_configuration(self, config: QuicConfiguration, tls_config):
    config.certificate         = tls_config.certificate
    config.private_key         = tls_config.private_key
    config.certificate_chain   = tls_config.certificate_chain
    config.alpn_protocols      = tls_config.alpn_protocols
    # Do NOT override verify_mode here — let the caller's config take effect
    # config.verify_mode = ssl.CERT_NONE  ← REMOVE THIS LINE
```

**Fix 3 — Treat missing peer certificate as a fatal error in `_verify_peer_identity_with_security()`:**

```python
# connection.py:579-630 — FIXED
async def _verify_peer_identity_with_security(self) -> ID | None:
    await self._extract_peer_certificate()

    if not self._peer_certificate:
        raise QUICPeerVerificationError(
            "No peer certificate: unauthenticated connection rejected"
        )
    # ... rest of verification unchanged
```

**Fix 4 — Block the user callback when peer identity is not verified:**

```python
# listener.py:1064-1092 — FIXED
if self._security_manager:
    try:
        peer_id = await connection._verify_peer_identity_with_security()
        if not peer_id:
            # Treat None as a fatal verification failure
            logger.error("Peer identity could not be established; closing connection")
            await connection.close()
            return
        connection.peer_id = peer_id
    except Exception as e:
        logger.error(f"Security verification failed: {e}")
        await connection.close()
        return

# Only reached if peer_id was successfully verified
await self._handler(connection)
```

These four changes together enforce:

| Enforcement Point       | Mechanism                                             |
| ----------------------- | ----------------------------------------------------- |
| TLS layer               | `ssl.CERT_REQUIRED` forces aioquic to request cert   |
| Verification layer      | `None` cert raises `QUICPeerVerificationError`        |
| Handler invocation gate | `None` return triggers connection close + return      |
| Identity consistency    | `peer_id` is only set from verified certificate       |

______________________________________________________________________

## Summary

QUIC in py-libp2p is a high-performance transport that collapses TCP, TLS, and stream multiplexing into a single protocol. It uses libp2p's TLS 1.3 certificate extension mechanism to bind ephemeral TLS sessions to libp2p peer identities — making all connections mutually authenticated by design.

Bug #02 breaks this guarantee entirely on the inbound path: six interconnected defects allow a raw QUIC client with no certificate to complete the TLS handshake, reach the application handler, and deliver stream data — all while `connection.peer_id` returns the server's own identity. The fix requires four targeted changes that together enforce the libp2p spec's mandatory mutual authentication at every layer: TLS, verification, and handler invocation.
