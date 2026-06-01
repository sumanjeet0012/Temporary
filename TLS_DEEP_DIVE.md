# TLS in py-libp2p — A Complete Walkthrough

---

## Part 1: What Is TLS and Why Do We Need It?

### The Problem Without TLS

Imagine two computers talking over the internet. Without any protection, every router, ISP, or attacker sitting on the network path between them can:

1. **Read everything** — your messages, passwords, file contents.
2. **Modify everything** — change data in transit without either party knowing.
3. **Impersonate** either party — claim to be Alice while talking to Bob, and vice versa.

This is called a **man-in-the-middle (MITM) attack**, and raw TCP connections are completely vulnerable to it.

### What TLS Solves

**TLS (Transport Layer Security)** is a cryptographic protocol that wraps a raw byte stream and guarantees:

| Property | What It Means |
|---|---|
| **Confidentiality** | All data is encrypted. Eavesdroppers see only ciphertext. |
| **Integrity** | Any tampering with data is detected and the connection is dropped. |
| **Authentication** | Each side proves who they are using a cryptographic certificate. |

TLS does not invent new algorithms — it's a protocol framework that orchestrates well-known building blocks (key exchange, symmetric encryption, message authentication) into a reliable secure channel.

### TLS Versions

| Version | Status | Notes |
|---|---|---|
| TLS 1.0 / 1.1 | ❌ Deprecated | Broken by POODLE, BEAST attacks |
| TLS 1.2 | ⚠️ OK | Still in wide use but has weaknesses |
| **TLS 1.3** | ✅ Current | Removes old cipher suites, faster handshake, forward secrecy by default |

**py-libp2p enforces TLS 1.3 only:**
```python
# libp2p/security/tls/transport.py:129
ctx.minimum_version = ssl.TLSVersion.TLSv1_3
```

---

## Part 2: Core TLS Concepts

### 2.1 The TLS Handshake (TLS 1.3)

Before any application data flows, the two sides execute a handshake to agree on cryptographic parameters and exchange certificates:

```
Client                                       Server
  |                                              |
  |------ ClientHello (key share, ciphers) ----->|
  |<----- ServerHello (key share choice) --------|
  |<----- {EncryptedExtensions}  ----------------|
  |<----- {Certificate}          ----------------|  <- Server proves identity
  |<----- {CertificateVerify}    ----------------|
  |<----- {Finished}             ----------------|
  |                                              |
  |------ {Certificate}          -------------->|  <- Client proves identity (mutual TLS)
  |------ {CertificateVerify}    -------------->|
  |------ {Finished}             -------------->|
  |                                              |
  |====== Application Data (encrypted) =========|
```

After the handshake, both sides have a shared symmetric key derived from the Diffie-Hellman key exchange. All further data is encrypted with this key.

### 2.2 Certificates and the Libp2p Extension

A certificate in standard TLS is issued by a Certificate Authority (CA) and binds a domain name to a public key.

**libp2p doesn't use CAs.** Instead, each peer generates its own self-signed certificate with a custom X.509 extension. This extension cryptographically binds the TLS certificate to the peer's **libp2p identity** (its Ed25519 or RSA keypair).

The binding works like this:

```
libp2p private key  --signs-->  (prefix + TLS cert public key)  --stored in-->  X.509 extension
```

So when a peer presents its TLS certificate, the verifier can:
1. Read the libp2p extension from the cert.
2. Extract the libp2p public key.
3. Verify the signature over the TLS cert's public key.
4. Derive the Peer ID from the libp2p public key (`ID.from_pubkey()`).
5. Confirm this matches the expected Peer ID.

This is defined in the [libp2p TLS spec](https://github.com/libp2p/specs/blob/master/tls/tls.md).

### 2.3 ALPN Protocol Negotiation

**ALPN (Application-Layer Protocol Negotiation)** allows the two sides to agree on an application-level protocol during the TLS handshake, before any application data is sent.

In libp2p, ALPN is used to advertise preferred stream multiplexers (like yamux, mplex) so that muxer negotiation can happen "for free" inside the handshake without an extra round trip.

```python
# libp2p/security/tls/transport.py:248
alpn_list = list(self._preferred_muxers) + [ALPN_PROTOCOL]
ctx.set_alpn_protocols(alpn_list)
```

If no muxer is matched, it falls back to `"libp2p"` which signals: "use multistream-select for muxer negotiation after the handshake."

### 2.4 Mutual TLS (mTLS) vs One-Way TLS

| Mode | Who shows a certificate? |
|---|---|
| One-way TLS | Only the server. Client remains anonymous. |
| Mutual TLS (mTLS) | Both client and server. Full bilateral authentication. |

**libp2p TLS requires mutual authentication** — both peers must prove their identity. However, Python's `ssl` module has a fundamental limitation: a server cannot request a client certificate without having a CA certificate to verify it against. This is Bug #01, explained in Part 4.

---

## Part 3: How TLS Works in py-libp2p (Step by Step)

The TLS implementation is spread across several files. Here's the complete journey from raw TCP socket to encrypted application stream.

---

### Step 1: Raw TCP Connection is Established

A raw TCP socket is created by the transport layer. This is a **plaintext byte stream** — completely unprotected.

**Files:** `libp2p/transport/tcp/tcp.py`, `libp2p/network/connection/raw_connection.py`

When you call `ipfs swarm connect` or `host.connect(peer_info)`, the Swarm dials the peer and gets back a `RawConnection` object. At this point, no security has been applied.

```python
# libp2p/network/swarm.py:648
raw_conn = await self.transport.dial(addr)
```

The raw connection carries no identity information and provides no confidentiality or integrity guarantees. It is simply bytes flowing over a TCP socket.

---

### Step 2: Security Upgrade — Multistream-Select Picks TLS

Before any libp2p protocol can be used, the connection must be secured. The `TransportUpgrader` is responsible for this.

**File:** `libp2p/transport/upgrader.py`

```python
# libp2p/transport/upgrader.py:50-72
async def upgrade_security(
    self, raw_conn: IRawConnection, is_initiator: bool, peer_id: ID | None = None
) -> ISecureConn:
    if is_initiator:
        # Outbound: we dialed, provide expected peer_id for verification
        secure_conn = await self.security_multistream.secure_outbound(raw_conn, peer_id)
        # Validate the peer ID we got matches what we expected
        authenticated_peer_id = secure_conn.get_remote_peer()
        if authenticated_peer_id != peer_id:
            await secure_conn.close()
            raise SecurityUpgradeFailure(...)
        return secure_conn
    # Inbound: peer dialed us, discover their peer_id
    return await self.security_multistream.secure_inbound(raw_conn)
```

`SecurityMultistream` runs a `multistream-select` negotiation over the raw connection to agree on a security protocol. If both sides advertise `/tls/1.0.0`, that transport is chosen.

**File:** `libp2p/security/security_multistream.py`

```python
# libp2p/security/security_multistream.py:83-107
async def secure_inbound(self, conn: IRawConnection) -> ISecureConn:
    # Run multistream-select, pick TLS transport
    transport = await self.select_transport(conn, False)
    return await transport.secure_inbound(conn)

async def secure_outbound(self, conn: IRawConnection, peer_id: ID) -> ISecureConn:
    transport = await self.select_transport(conn, True)
    return await transport.secure_outbound(conn, peer_id)
```

---

### Step 3: TLS Certificate is Generated (Once, at Startup)

When `TLSTransport` is constructed, it immediately generates a self-signed TLS certificate that embeds the local peer's libp2p identity in a custom X.509 extension.

**File:** `libp2p/security/tls/certificate.py`

```python
# libp2p/security/tls/certificate.py:246-271
def generate_certificate(private_key, cert_template):
    # 1. Generate an ephemeral ECDSA P-256 key for TLS-layer signing
    tls_private_key = ec.generate_private_key(ec.SECP256R1())

    # 2. Sign (magic_prefix + TLS_pubkey_DER) with the libp2p host key
    spki_der = tls_private_key.public_key().public_bytes(DER, SubjectPublicKeyInfo)
    signature = private_key.sign(LIBP2P_CERT_PREFIX + spki_der)
    #           ^ LIBP2P_CERT_PREFIX = b"libp2p-tls-handshake:"

    # 3. Embed libp2p public key + signature in a custom OID extension
    builder = add_libp2p_extension(builder, private_key.get_public_key(), signature)
    #         ^ OID = 1.3.6.1.4.1.53594.1.1 (same across all implementations)

    # 4. Self-sign the cert with the ephemeral TLS key
    certificate = builder.sign(private_key=tls_private_key, algorithm=hashes.SHA256())
```

The result: a certificate where the TLS layer sees an ECDSA cert, but any libp2p-aware verifier can extract the embedded libp2p identity by reading the custom extension.

This certificate is cached in `TLSTransport._cert_pem` for reuse across all connections.

---

### Step 4: SSL Context is Configured

For each new connection, a fresh `ssl.SSLContext` is created with the cached certificate loaded into it.

**File:** `libp2p/security/tls/transport.py` — `create_ssl_context()`

```python
# libp2p/security/tls/transport.py:84-274
def create_ssl_context(self, server_side: bool = False) -> ssl.SSLContext:
    ctx = ssl.SSLContext(
        ssl.PROTOCOL_TLS_SERVER if server_side else ssl.PROTOCOL_TLS_CLIENT
    )
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3  # Enforce TLS 1.3 only

    # We do our own post-handshake certificate verification
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # Python limitation — see Bug #01

    # Load our self-signed identity certificate
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)

    # Advertise preferred muxers via ALPN + "libp2p" fallback
    alpn_list = list(self._preferred_muxers) + [ALPN_PROTOCOL]
    ctx.set_alpn_protocols(alpn_list)
```

> **Note on `CERT_NONE`:** The libp2p spec calls for custom post-handshake verification of the embedded extension rather than standard CA chains. Setting `CERT_NONE` disables Python's built-in verification so that our own logic can run. This is intentional but introduces the security gap in Bug #01.

---

### Step 5: TLS Handshake Over MemoryBIO

Because libp2p uses its own async I/O layer (Trio), Python's `ssl` module cannot be used in the normal blocking fashion. Instead, the TLS state machine is driven manually using `ssl.MemoryBIO` — a software buffer that decouples the TLS engine from the actual network socket.

**File:** `libp2p/security/tls/io.py` — `TLSStreamReadWriter.handshake()`

```python
# libp2p/security/tls/io.py:91-203
async def handshake(self, enable_autotls: bool = False) -> None:
    in_bio = ssl.MemoryBIO()   # network bytes IN  → SSL engine
    out_bio = ssl.MemoryBIO()  # SSL engine bytes → network OUT
    ssl_obj = self.ssl_context.wrap_bio(in_bio, out_bio, server_side=...)

    while True:
        try:
            ssl_obj.do_handshake()   # Advance the TLS state machine
            break                    # Done when no exception raised

        except ssl.SSLWantReadError:
            # TLS needs more data from the network
            pending = out_bio.read()
            if pending:
                await self.raw_connection.write(pending)   # flush TLS output first
            incoming = await self.raw_connection.read(4096)
            in_bio.write(incoming)  # feed new network data to TLS engine

        except ssl.SSLWantWriteError:
            # TLS has output to send
            data = out_bio.read()
            await self.raw_connection.write(data)

    # After handshake: extract peer cert and ALPN result
    cert_bin = ssl_obj.getpeercert(binary_form=True)
    if cert_bin:
        self._peer_certificate = x509.load_der_x509_certificate(cert_bin)

    raw_protocol = ssl_obj.selected_alpn_protocol()
    self._negotiated_protocol = None if raw_protocol == "libp2p" else raw_protocol
```

After this completes, all subsequent `write()` / `read()` calls on this object go through transparent TLS encryption.

---

### Step 6: Post-Handshake Identity Verification

Now that the TLS layer is established and we have the peer's certificate, we verify the libp2p identity embedded in it.

**File:** `libp2p/security/tls/transport.py` — `secure_outbound()` (for connections we initiated)

```python
# libp2p/security/tls/transport.py:432-447
peer_cert = tls_reader_writer.get_peer_certificate()
if not peer_cert:
    raise ValueError("missing peer certificate")  # Hard failure for outbound

# Walk the libp2p extension in the cert
remote_public_key = self._extract_public_key_from_cert(peer_cert)
remote_peer_id = ID.from_pubkey(remote_public_key)

# Compare against who we thought we were connecting to
if remote_peer_id != peer_id:
    raise ValueError(f"Peer ID mismatch: expected {peer_id} got {remote_peer_id}")
```

The verification in `verify_certificate_chain()`:

```python
# libp2p/security/tls/certificate.py:274-359
def verify_certificate_chain(cert_chain):
    # Step 1: Check validity window (not_before / not_after)
    if not_before > now or not_after < now:
        raise ValueError("certificate expired or not yet valid")

    # Step 2: Find the custom OID extension (1.3.6.1.4.1.53594.1.1)
    for ext in cert.extensions:
        if ext.oid == LIBP2P_EXTENSION_OID:
            ext_value = ext.value.value
            break

    # Step 3: Verify TLS cert's self-signature (it's self-signed)
    pub = cert.public_key()
    pub.verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(hash_alg))

    # Step 4: Verify the extension's signature (libp2p key over TLS key)
    signed = decode_signed_key(ext_value)
    host_pub = deserialize_public_key(signed.public_key_bytes)
    message = LIBP2P_CERT_PREFIX + cert.public_key().public_bytes(DER, SPKI)
    if not host_pub.verify(message, signed.signature):
        raise ValueError("signature invalid")

    return host_pub  # Return the authenticated libp2p public key
```

---

### Step 7: SecureSession Created — Encrypted Channel Ready

**File:** `libp2p/security/secure_session.py`

A `SecureSession` wraps the `TLSReadWriter` and records the authenticated identities of both sides. All higher-level code reads and writes through this object.

```python
# libp2p/security/tls/transport.py:364-372
session = SecureSession(
    local_peer=self.local_peer,          # Our Peer ID
    local_private_key=self.libp2p_privkey,
    remote_peer=remote_peer_id,          # Authenticated remote Peer ID
    remote_permanent_pubkey=remote_public_key,
    is_initiator=False,
    conn=tls_reader_writer,              # Encrypted I/O object
)
return session
```

`SecureSession.write(data)` → `TLSReadWriter.write_msg(data)` → TLS encryption → raw TCP bytes  
`SecureSession.read(n)` → `TLSReadWriter.read_msg()` → TLS decryption → plaintext bytes

---

### Step 8: Muxer Upgrade — Multiple Streams Over One Connection

Once the connection is secured, `TransportUpgrader.upgrade_connection()` negotiates a stream multiplexer (yamux or mplex) over the `SecureSession`. This allows many independent logical streams (Bitswap, Identify, Ping, etc.) to share a single encrypted connection.

```
Raw TCP
  └──[TLS upgrade]──> SecureSession
                         └──[muxer upgrade]──> MuxedConn
                                                  ├── stream 1 (Bitswap)
                                                  ├── stream 2 (Identify)
                                                  └── stream 3 (Ping)
```

---

## Part 4: Bug Analysis

---

### Bug #01 — TLS Inbound Fail-Open (Authentication Bypass)

**Report:** `bugs/01-tls-inbound-fail-open/report.md`

#### What Happens

A remote client can complete the libp2p TLS handshake **without presenting a certificate** and without proving any libp2p identity. The server still creates a valid `SecureSession` for this connection, assigning a freshly generated synthetic Peer ID to the unauthenticated client.

#### Evidence (from `result.json`)

```json
{
  "client_results": [
    { "peer_cert_sent": false, "tls_handshake_completed": true },
    { "peer_cert_sent": false, "tls_handshake_completed": true }
  ],
  "server_observation": {
    "accepted_session_count": 2,
    "all_sessions_used_placeholder_identity": true,
    "distinct_placeholder_peer_ids": 2
  }
}
```

Two clients, zero certificates presented, both accepted — each with a different synthetic Peer ID.

#### Root Cause — Three-Layer Failure

**Layer 1 — SSL context never requests a client certificate:**
```python
# libp2p/security/tls/transport.py:138
ctx.verify_mode = ssl.CERT_NONE
# CERT_NONE = don't request, don't verify. The client is never even asked.
```

**Layer 2 — A missing certificate triggers a warning, not a failure:**
```python
# libp2p/security/tls/transport.py:306-327
peer_cert = tls_reader_writer.get_peer_certificate()
if not peer_cert:
    logger.warning("TLS inbound: no peer cert (Python ssl limitation)")
    # Generate a random identity for this stranger
    placeholder_keypair = libp2p.generate_new_ed25519_identity()
    remote_peer_id = ID.from_pubkey(placeholder_keypair.public_key)
    # ^ This peer ID did NOT come from the wire. It's invented.
```

**Layer 3 — A full authenticated-looking session is returned:**
```python
# libp2p/security/tls/transport.py:346-355
session = SecureSession(
    remote_peer=remote_peer_id,  # <- synthetic, unauthenticated
    ...
)
return session  # All downstream code believes this peer is authenticated
```

#### Impact

- Any peer can connect without proving a libp2p identity.
- Allowlists, logging, policy enforcement, and accounting based on Peer ID are useless.
- The same attacker connecting twice gets two different Peer IDs — impossible to block or track.
- The libp2p TLS spec's core guarantee (mutual peer authentication) is broken.

#### Recommended Fix

**Fix 1 — Use `CERT_OPTIONAL` so the client is actually asked for a certificate:**
```python
# libp2p/security/tls/transport.py - create_ssl_context()
# Change:
ctx.verify_mode = ssl.CERT_NONE
# To:
ctx.verify_mode = ssl.CERT_OPTIONAL  # Requests cert; doesn't reject if absent (CA-less)
```
With `CERT_OPTIONAL` and no CA configured, Python will *ask* for a certificate and make it available via `getpeercert()` if the client sends one. This is the minimal change to unblock the verification path for standards-compliant clients (Go, Rust).

**Fix 2 — Treat a missing certificate as a hard failure, not a warning:**
```python
# libp2p/security/tls/transport.py - secure_inbound()
peer_cert = tls_reader_writer.get_peer_certificate()
if not peer_cert:
    # Hard failure: the libp2p TLS spec requires mutual authentication
    raise HandshakeFailure(
        "Inbound TLS connection presented no client certificate. "
        "Mutual authentication is required by the libp2p TLS spec."
    )
```

The AutoTLS bootstrap path (which legitimately has no peer cert during broker registration) must be handled in a completely separate, clearly-guarded code path — not by degrading security for all inbound connections.

---

### Bug #08 — Circuit Relay v2 Target Reservation Bypass

**Report:** `bugs/08-relay-target-reservation-bypass/report.md`

#### Background — How Circuit Relay v2 Works

Circuit Relay allows a **source** peer to reach a **destination** peer through a relay node, even when the destination is behind NAT. The Circuit Relay v2 spec requires the **destination** to hold an active reservation on the relay before a CONNECT is accepted. This is an explicit opt-in: the destination says "I'm reachable via this relay." Without this requirement, the relay becomes an open vector for sending unsolicited traffic to any connected peer.

#### What Happens (The Bug)

A source peer **with** a reservation can successfully open a relayed application stream to a destination peer that **never made any reservation** on the relay.

#### Evidence (from `result.json`)

```json
{
  "dest_reserved_before": false,
  "dest_reserved_after": false,
  "source_reserved_after": true,
  "relay_connect_observation": {
    "target_had_reservation_at_connect": false,
    "source_had_reservation_at_connect": true
  },
  "destination_received_message": "relay-app-message"
}
```

The destination had no reservation, yet received the full application message.

#### Root Cause — Admission Check Uses the Wrong Peer ID

The `_handle_connect` method is given:
- `peer_id` = the **destination** (who we want to reach via the relay)
- `source_addr` = the **source** (who sent the CONNECT request)

The bug is that `can_accept_connection` is called with `source_addr` instead of `peer_id`:

```python
# libp2p/relay/circuit_v2/protocol.py:667-702
async def _handle_connect(self, stream: INetStream, msg: HopMessage) -> None:
    peer_id = ID(msg.peer)                   # <- DESTINATION
    source_addr = stream.muxed_conn.peer_id  # <- SOURCE

    # BUG: checks SOURCE reservation instead of DESTINATION reservation
    if not self.resource_manager.can_accept_connection(peer_id=source_addr):
        ...
        return
    # If the source has a reservation, this passes — even if destination never reserved!
```

The `can_accept_connection()` method itself is correct — it looks up reservations by peer ID:

```python
# libp2p/relay/circuit_v2/resources.py:449-465
def can_accept_connection(self, peer_id: ID) -> bool:
    reservation = self._reservations.get(peer_id)
    return reservation is not None and reservation.can_accept_connection()
```

The problem is simply that it's being handed the source's ID instead of the destination's ID.

#### Impact

- A destination that never opted in can be reached through the relay.
- The relay's explicit opt-in model for the target side is meaningless.
- The relay spends bandwidth and connection slots routing unsolicited traffic to non-reserved peers.
- Any firewall policy assuming "only reserved peers are reachable" is violated.

#### Recommended Fix

Check the **destination's** reservation for the "is this destination reachable?" admission check. Source-side resource accounting should be a separate, independent check:

```python
# libp2p/relay/circuit_v2/protocol.py - _handle_connect()
async def _handle_connect(self, stream: INetStream, msg: HopMessage) -> None:
    peer_id = ID(msg.peer)                   # <- DESTINATION
    source_addr = stream.muxed_conn.peer_id  # <- SOURCE

    # FIX: Require the DESTINATION to have an active reservation
    if not self.resource_manager.can_accept_connection(peer_id=peer_id):  # peer_id, not source_addr
        relay_envelope_bytes, _ = env_to_send_in_RPC(self.host)
        relay_envelope = unmarshal_envelope(relay_envelope_bytes)
        await self._send_status(
            stream,
            StatusCode.NO_RESERVATION,  # or PERMISSION_DENIED
            "Destination peer has no active reservation on this relay",
            relay_envelope,
        )
        await stream.reset()
        return

    # Separately check source-side connection limits (if needed)
    source_reservation = self.resource_manager._reservations.get(source_addr)
    if source_reservation and not source_reservation.can_accept_connection():
        ...  # source connection limit exceeded
```

This separates the two concerns clearly:
1. **Target admission** — does the destination allow relay traffic? (`peer_id`)
2. **Source accounting** — has the source hit its connection limit? (`source_addr`)

---

## Summary Table

| Step | File | What Happens |
|---|---|---|
| 1 | `transport/tcp/tcp.py` | Raw TCP connection established |
| 2 | `security/security_multistream.py` | multistream-select picks `/tls/1.0.0` |
| 3 | `security/tls/certificate.py` | Self-signed cert with libp2p extension generated |
| 4 | `security/tls/transport.py` | `ssl.SSLContext` configured (TLS 1.3, ALPN) |
| 5 | `security/tls/io.py` | TLS handshake driven over MemoryBIO |
| 6 | `security/tls/transport.py` | Peer cert extracted, libp2p extension verified |
| 7 | `security/secure_session.py` | `SecureSession` created with authenticated Peer IDs |
| 8 | `transport/upgrader.py` | Muxer negotiated (yamux/mplex) |
| Bug #01 | `security/tls/transport.py:306-355` | Inbound: missing cert → placeholder Peer ID → bypass |
| Bug #08 | `relay/circuit_v2/protocol.py:692` | `can_accept_connection(source_addr)` should be `can_accept_connection(peer_id)` |
