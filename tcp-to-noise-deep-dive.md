# Deep Dive: From TCP Connection to Noise Handshake in py-libp2p

## Table of Contents
1. [Overview: The Complete Journey](#overview)
2. [Phase 1: TCP Connection Establishment](#tcp-connection)
3. [Phase 2: Protocol Negotiation (multistream-select)](#protocol-negotiation)
4. [Phase 3: The Security Upgrader](#security-upgrader)
5. [Phase 4: Noise Module Deep Dive](#noise-module)
6. [Phase 5: The Complete Noise Handshake](#noise-handshake)
7. [Phase 6: Post-Handshake Encrypted Communication](#post-handshake)
8. [Code Walkthrough with py-libp2p](#code-walkthrough)
9. [Wire Protocol Analysis](#wire-protocol)
10. [Real Example: Packet-by-Packet Breakdown](#real-example)

---

## 1. Overview: The Complete Journey {#overview}

When two py-libp2p nodes communicate, they go through several transformation layers. Let's visualize the entire process:

```
┌──────────────────────────────────────────────────────────────────┐
│                    APPLICATION WANTS TO CONNECT                  │
│                  host.new_stream(peer_id, protocols)             │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 1: TCP CONNECTION ESTABLISHMENT                            │
│                                                                  │
│  Initiator (Alice)              Network              Responder (Bob) │
│       |                                                    |     │
│       | ---- SYN (Connect to IP:Port) ----------------->  |     │
│       | <--- SYN-ACK (Acknowledge) ---------------------  |     │
│       | ---- ACK (Confirm) ---------------------------->  |     │
│       |                                                    |     │
│  Result: Raw TCP socket connection established              │
│          (Unreliable, unencrypted, no authentication)        │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 2: PROTOCOL NEGOTIATION (multistream-select)              │
│                                                                  │
│  Alice                         TCP Socket                    Bob   │
│    | ---- "/multistream/1.0.0\n" ----------------------->  |     │
│    | <--- "/multistream/1.0.0\n" -----------------------  |     │
│    | ---- "/noise\n" ---------------------------------->  |     │
│    | <--- "/noise\n" -----------------------------------  |     │
│    |                                                      |     │
│  Result: Both parties agree to use Noise protocol             │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 3: SECURITY UPGRADER INVOKED                              │
│                                                                  │
│  Network Layer calls:                                            │
│    upgrader.upgrade_outbound(raw_conn, peer_id)  [Alice]       │
│    upgrader.upgrade_inbound(raw_conn)            [Bob]          │
│                                                                  │
│  Upgrader delegates to:                                          │
│    noise_transport.secure_outbound(raw_conn, peer_id)          │
│    noise_transport.secure_inbound(raw_conn)                     │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 4: NOISE HANDSHAKE (3 Messages)                           │
│                                                                  │
│  Message 1: Alice → Bob                                          │
│    • Alice generates ephemeral keypair                          │
│    • Sends ephemeral public key                                 │
│    • Payload: empty or early data                               │
│                                                                  │
│  Message 2: Bob → Alice                                          │
│    • Bob generates ephemeral keypair                            │
│    • Performs DH: ee (ephemeral-ephemeral)                      │
│    • Sends: ephemeral key + static key (encrypted)              │
│    • Payload: NoiseHandshakePayload with identity               │
│                                                                  │
│  Message 3: Alice → Bob                                          │
│    • Alice performs DH: se (static-ephemeral)                   │
│    • Sends: static key (encrypted)                              │
│    • Payload: NoiseHandshakePayload with identity               │
│    • Both derive final encryption keys                          │
│                                                                  │
│  Result: Secure, encrypted, authenticated connection            │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 5: ENCRYPTED COMMUNICATION                                │
│                                                                  │
│  All subsequent data flows through:                              │
│    • Noise CipherState (ChaCha20-Poly1305)                      │
│    • Each message: [2-byte length][encrypted payload + 16-byte MAC] │
│    • Forward secrecy maintained                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Phase 1: TCP Connection Establishment {#tcp-connection}

### What Happens at the Network Level

Let's start with the TCP three-way handshake - the foundation of everything.

#### Step-by-Step TCP Handshake

```
Time   Initiator (Alice)                           Responder (Bob)
────   ─────────────────────────────────────────   ──────────────────
t=0    Alice wants to connect to Bob at           Bob is listening on
       127.0.0.1:9000                              0.0.0.0:9000

t=1    [Create TCP socket]
       socket = socket.socket(AF_INET, SOCK_STREAM)

t=2    [Send SYN packet]                    ────>  
       Flags: SYN
       Seq: 1000 (random initial seq number)
       
t=3                                          <────  [Receive SYN]
                                                    [Send SYN-ACK]
                                                    Flags: SYN, ACK
                                                    Seq: 5000 (Bob's seq)
                                                    Ack: 1001 (Alice's seq + 1)

t=4    [Receive SYN-ACK]
       [Send ACK]                            ────>
       Flags: ACK
       Seq: 1001
       Ack: 5001 (Bob's seq + 1)

t=5                                          <────  [Receive ACK]
                                                    
       ✅ Connection ESTABLISHED                    ✅ Connection ESTABLISHED
       
       Both parties can now send/receive bytes
```

### py-libp2p Code: TCP Transport Dial

Here's how py-libp2p implements the TCP connection:

```python
# File: libp2p/transport/tcp/tcp.py

class TCP(ITransport):
    """TCP transport for libp2p"""
    
    async def dial(self, maddr: Multiaddr) -> IRawConnection:
        """
        Dial (connect to) a peer at the given multiaddress.
        
        Args:
            maddr: Multiaddress like "/ip4/127.0.0.1/tcp/9000"
            
        Returns:
            A RawConnection wrapping the TCP socket
        """
        # Step 1: Parse the multiaddress
        # Extract IP address and port from the multiaddress format
        # "/ip4/127.0.0.1/tcp/9000" → ("127.0.0.1", 9000)
        addr_tuple = maddr_to_tuple(maddr)
        ip = addr_tuple[0]
        port = addr_tuple[1]
        
        # Step 2: Create TCP connection using trio (async I/O library)
        # This performs the TCP three-way handshake
        try:
            stream = await trio.open_tcp_stream(ip, port)
        except OSError as error:
            raise Exception(f"Failed to connect to {ip}:{port}") from error
        
        # Step 3: Wrap the raw TCP stream in a RawConnection object
        # RawConnection provides a consistent interface for all transports
        raw_conn = RawConnection(
            stream=stream,
            initiator=True,  # We initiated the connection
            maddr=maddr      # Store the multiaddress for reference
        )
        
        return raw_conn
```

### What is a RawConnection?

```python
# File: libp2p/network/connection/raw_connection.py

class RawConnection(IRawConnection):
    """
    A RawConnection is a simple wrapper around a network socket.
    It provides basic read/write operations but NO security or multiplexing.
    
    Think of it as a "pipe" where bytes go in one end and come out the other.
    """
    
    def __init__(self, stream, initiator: bool, maddr: Multiaddr):
        self.stream = stream          # The actual TCP socket (trio.Stream)
        self.initiator = initiator    # True if we dialed, False if we listened
        self.maddr = maddr            # The multiaddress we connected to/from
        self._closed = False
    
    async def write(self, data: bytes) -> None:
        """Send bytes over the connection"""
        if self._closed:
            raise Exception("Connection is closed")
        await self.stream.send_all(data)
    
    async def read(self, n: int = None) -> bytes:
        """Receive bytes from the connection"""
        if self._closed:
            raise Exception("Connection is closed")
        
        if n is None:
            # Read whatever is available
            return await self.stream.receive_some()
        else:
            # Read exactly n bytes
            data = bytearray()
            while len(data) < n:
                chunk = await self.stream.receive_some(n - len(data))
                if not chunk:
                    raise Exception("Connection closed by peer")
                data.extend(chunk)
            return bytes(data)
    
    async def close(self) -> None:
        """Close the connection"""
        self._closed = True
        await self.stream.aclose()
```

### TCP Listener (Server Side)

```python
# File: libp2p/transport/tcp/tcp.py

class TCPListener:
    """Listens for incoming TCP connections"""
    
    def __init__(self, handler_function, listen_maddr: Multiaddr):
        """
        Args:
            handler_function: Called when a new connection arrives
            listen_maddr: Address to listen on, e.g., "/ip4/0.0.0.0/tcp/8000"
        """
        self.handler_function = handler_function
        self.listen_maddr = listen_maddr
        self.server = None
    
    async def listen(self):
        """Start listening for connections"""
        # Parse the listen address
        addr_tuple = maddr_to_tuple(self.listen_maddr)
        ip = addr_tuple[0]
        port = addr_tuple[1]
        
        # Start TCP server
        # When a client connects, serve_client will be called
        async with trio.open_nursery() as nursery:
            listeners = await nursery.start(
                trio.serve_tcp, 
                self.serve_client,
                port,
                host=ip
            )
            self.server = listeners[0]
            
            # Keep running forever
            await trio.sleep_forever()
    
    async def serve_client(self, stream: trio.Stream):
        """Handle an incoming TCP connection"""
        # Wrap the TCP stream in a RawConnection
        raw_conn = RawConnection(
            stream=stream,
            initiator=False,  # We didn't initiate, they did
            maddr=self.listen_maddr
        )
        
        # Pass the connection to the handler
        # The handler will upgrade it with security & multiplexing
        await self.handler_function(raw_conn)
```

### Summary of Phase 1

At the end of Phase 1:
- ✅ TCP connection is established
- ✅ We have a `RawConnection` object
- ❌ No encryption yet (everything is plaintext)
- ❌ No authentication (we don't know who we're talking to)
- ❌ No multiplexing (only one conversation can happen)

**Next step:** Negotiate which security protocol to use.

---

## 3. Phase 2: Protocol Negotiation (multistream-select) {#protocol-negotiation}

Before applying security, both peers must agree on *which* security protocol to use. libp2p supports multiple security protocols (Noise, TLS, the old SECIO), so they need to negotiate.

### What is multistream-select?

multistream-select is a simple protocol negotiation mechanism:

```
Format of each message:
    [length_varint][protocol_string][newline]

Example:
    b'\x13/multistream/1.0.0\n'
    
Breaking it down:
    0x13 = 19 (length of the string including newline)
    "/multistream/1.0.0\n" = the protocol string
```

### The Negotiation Dance

```
Alice (Initiator)                              Bob (Responder)
       |                                              |
       | ---- "/multistream/1.0.0\n" ------------->  |
       |      (I want to negotiate protocols)         |
       |                                              |
       | <--- "/multistream/1.0.0\n" --------------  |
       |      (OK, I support negotiation)             |
       |                                              |
       | ---- "/noise\n" -------------------------->  |
       |      (I want to use Noise protocol)          |
       |                                              |
       | <--- "/noise\n" ---------------------------  |
       |      (OK, I also support Noise)              |
       |                                              |
     [Noise handshake begins]
```

### py-libp2p Code: multistream-select

```python
# File: libp2p/stream_muxer/multiselect.py

MULTISELECT_PROTOCOL_ID = "/multistream/1.0.0"
PROTOCOL_NOT_FOUND_MSG = "na"

class MultistreamNegotiator:
    """
    Implements the multistream-select protocol for negotiation.
    """
    
    async def select_protocol(
        self,
        protocols: Sequence[str],
        stream: ReadWriteCloser
    ) -> str:
        """
        Negotiate a protocol from a list of options.
        
        Args:
            protocols: List of protocols we want to use, in preference order
            stream: The connection to negotiate over
            
        Returns:
            The selected protocol string
        """
        # Step 1: Send our multistream-select header
        await self.send_message(stream, MULTISELECT_PROTOCOL_ID)
        
        # Step 2: Receive their multistream-select header
        response = await self.read_message(stream)
        if response != MULTISELECT_PROTOCOL_ID:
            raise Exception("Peer doesn't support multistream-select")
        
        # Step 3: Try each protocol in order of preference
        for protocol in protocols:
            # Send our proposal
            await self.send_message(stream, protocol)
            
            # Read their response
            response = await self.read_message(stream)
            
            if response == protocol:
                # They accepted!
                return protocol
            elif response == PROTOCOL_NOT_FOUND_MSG:
                # They don't support this protocol, try next one
                continue
            else:
                raise Exception(f"Unexpected response: {response}")
        
        # None of our protocols were accepted
        raise Exception("No mutually supported protocols")
    
    async def send_message(self, stream: ReadWriteCloser, msg: str) -> None:
        """Send a multistream-select message"""
        # Format: [varint length][message]\n
        msg_bytes = (msg + "\n").encode("utf-8")
        length_prefix = encode_varint(len(msg_bytes))
        await stream.write(length_prefix + msg_bytes)
    
    async def read_message(self, stream: ReadWriteCloser) -> str:
        """Receive a multistream-select message"""
        # Read the length prefix (varint)
        length = await read_varint(stream)
        
        # Read the message
        msg_bytes = await stream.read(length)
        
        # Remove trailing newline and decode
        msg = msg_bytes.rstrip(b"\n").decode("utf-8")
        return msg
```

### Varint Encoding

```python
def encode_varint(n: int) -> bytes:
    """
    Encode an integer as a variable-length integer.
    
    Small numbers use fewer bytes:
        0-127    : 1 byte
        128-16383: 2 bytes
        etc.
    """
    result = bytearray()
    while n > 0x7F:
        result.append((n & 0x7F) | 0x80)  # Set continuation bit
        n >>= 7
    result.append(n & 0x7F)  # Last byte, no continuation bit
    return bytes(result)

def decode_varint(data: bytes) -> Tuple[int, int]:
    """
    Decode a varint from bytes.
    Returns: (value, bytes_consumed)
    """
    result = 0
    shift = 0
    for i, byte in enumerate(data):
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):  # No continuation bit
            return result, i + 1
        shift += 7
    raise Exception("Incomplete varint")
```

### Wire Format Example

Let's see what actually goes over the wire:

```
Message: "/multistream/1.0.0\n"

Step 1: Encode the string
    "/multistream/1.0.0\n" → 19 bytes

Step 2: Encode length as varint
    19 → 0x13 (single byte, since 19 < 128)

Step 3: Combine
    Bytes on wire: 0x13 2f 6d 75 6c 74 69 73 74 72 65 61 6d 2f 31 2e 30 2e 30 0a
                   ^^^^  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                   length "/multistream/1.0.0\n"
```

---

## 4. Phase 3: The Security Upgrader {#security-upgrader}

After protocol negotiation, the `Upgrader` component takes the raw TCP connection and applies the negotiated security protocol.

### The Upgrader's Role

```python
# File: libp2p/network/connection/upgrader.py

class Upgrader:
    """
    Takes a raw connection and upgrades it with:
    1. Security (Noise, TLS, etc.)
    2. Multiplexing (Yamux, mplex)
    """
    
    def __init__(
        self,
        security_transports: Dict[str, ISecureTransport],
        muxer_transports: Dict[str, IMuxerTransport]
    ):
        """
        Args:
            security_transports: Map of protocol ID → security implementation
                Example: {"/noise": NoiseTransport(...)}
            muxer_transports: Map of protocol ID → muxer implementation
                Example: {"/yamux/1.0.0": YamuxTransport()}
        """
        self.security_transports = security_transports
        self.muxer_transports = muxer_transports
        self.multiselect = MultistreamNegotiator()
    
    async def upgrade_outbound(
        self,
        raw_conn: IRawConnection,
        peer_id: ID
    ) -> IMultiplexedConnection:
        """
        Upgrade an outbound connection (when we initiated).
        
        Flow:
            raw_conn → [security] → secure_conn → [muxing] → muxed_conn
        """
        # Step 1: Apply security
        secure_conn = await self._apply_security_outbound(raw_conn, peer_id)
        
        # Step 2: Apply multiplexing
        muxed_conn = await self._apply_muxer(secure_conn, peer_id)
        
        return muxed_conn
    
    async def _apply_security_outbound(
        self,
        raw_conn: IRawConnection,
        peer_id: ID
    ) -> ISecureConn:
        """Apply security protocol to outbound connection"""
        
        # Negotiate which security protocol to use
        security_protocols = list(self.security_transports.keys())
        selected_protocol = await self.multiselect.select_protocol(
            security_protocols,
            raw_conn
        )
        
        # Get the security transport for that protocol
        security_transport = self.security_transports[selected_protocol]
        
        # Perform the security handshake
        # THIS IS WHERE NOISE HANDSHAKE HAPPENS!
        secure_conn = await security_transport.secure_outbound(
            raw_conn,
            peer_id
        )
        
        return secure_conn
    
    async def upgrade_inbound(
        self,
        raw_conn: IRawConnection
    ) -> IMultiplexedConnection:
        """
        Upgrade an inbound connection (when they initiated).
        """
        # Step 1: Apply security
        secure_conn = await self._apply_security_inbound(raw_conn)
        
        # Step 2: Apply multiplexing  
        peer_id = secure_conn.get_remote_peer()
        muxed_conn = await self._apply_muxer(secure_conn, peer_id)
        
        return muxed_conn
    
    async def _apply_security_inbound(
        self,
        raw_conn: IRawConnection
    ) -> ISecureConn:
        """Apply security protocol to inbound connection"""
        
        # They will tell us which security protocol they want
        security_protocols = list(self.security_transports.keys())
        selected_protocol = await self.multiselect.select_protocol_from_list(
            security_protocols,
            raw_conn
        )
        
        # Get the security transport
        security_transport = self.security_transports[selected_protocol]
        
        # Perform the security handshake
        secure_conn = await security_transport.secure_inbound(raw_conn)
        
        return secure_conn
```

### Key Points

1. **Upgrader is the orchestrator** - it coordinates protocol negotiation and applies upgrades
2. **Security first, then multiplexing** - Always in this order
3. **Different methods for initiator vs responder** - `secure_outbound` vs `secure_inbound`
4. **The actual Noise handshake** happens inside `security_transport.secure_outbound/inbound`

---

## 5. Phase 4: Noise Module Deep Dive {#noise-module}

Now we're at the heart of the security layer. Let's understand the Noise module structure in py-libp2p.

### Noise Module Architecture

```
libp2p/security/noise/
├── transport.py          # Main Noise transport (secure_outbound/inbound)
├── io.py                 # Read/write Noise messages (handshake & transport)
├── handshake.py          # Noise handshake logic
├── patterns.py           # Noise XX pattern definition
├── pb/noise.proto        # Protobuf for NoiseHandshakePayload
└── exceptions.py         # Noise-specific exceptions
```

### The Noise Transport Class

```python
# File: libp2p/security/noise/transport.py

from noiseprotocol.connection import NoiseConnection  # External library
from libp2p.security.noise.io import NoiseHandshakeReadWriter

PROTOCOL_ID = "/noise"

class Transport(ISecureTransport):
    """
    Noise Protocol Framework security transport for libp2p.
    
    Implements the Noise_XX_25519_ChaChaPoly_SHA256 protocol.
    """
    
    def __init__(
        self,
        libp2p_keypair: KeyPair,
        noise_privkey: PrivateKey,
        early_data: bytes = None
    ):
        """
        Args:
            libp2p_keypair: The host's libp2p identity keypair
            noise_privkey: Private key for Noise protocol (usually same as libp2p)
            early_data: Optional data to send with first handshake message
        """
        self.libp2p_keypair = libp2p_keypair
        self.libp2p_privkey = libp2p_keypair.private_key
        self.noise_privkey = noise_privkey
        self.local_peer = ID.from_pubkey(libp2p_keypair.public_key)
        self.early_data = early_data or b""
    
    async def secure_outbound(
        self,
        conn: IRawConnection,
        peer_id: ID
    ) -> ISecureConn:
        """
        Secure an outbound connection (we are the initiator).
        
        This performs the complete Noise XX handshake.
        
        Args:
            conn: The raw TCP connection
            peer_id: Expected peer ID (for verification)
            
        Returns:
            A SecureConnection with encryption enabled
        """
        # Step 1: Initialize Noise handshake state as INITIATOR
        noise_state = self._create_noise_state(initiator=True)
        
        # Step 2: Create handshake message reader/writer
        handshake_rw = NoiseHandshakeReadWriter(conn, noise_state)
        
        # Step 3: Perform the XX handshake (3 messages)
        await self._perform_handshake_outbound(
            handshake_rw,
            peer_id
        )
        
        # Step 4: Handshake complete! Create secure connection
        secure_conn = self._create_secure_connection(
            conn,
            noise_state,
            peer_id
        )
        
        return secure_conn
    
    async def secure_inbound(
        self,
        conn: IRawConnection
    ) -> ISecureConn:
        """
        Secure an inbound connection (we are the responder).
        """
        # Step 1: Initialize Noise handshake state as RESPONDER
        noise_state = self._create_noise_state(initiator=False)
        
        # Step 2: Create handshake message reader/writer
        handshake_rw = NoiseHandshakeReadWriter(conn, noise_state)
        
        # Step 3: Perform the XX handshake (3 messages)
        remote_peer_id = await self._perform_handshake_inbound(
            handshake_rw
        )
        
        # Step 4: Handshake complete! Create secure connection
        secure_conn = self._create_secure_connection(
            conn,
            noise_state,
            remote_peer_id
        )
        
        return secure_conn
    
    def _create_noise_state(self, initiator: bool) -> NoiseConnection:
        """
        Create a Noise protocol state machine.
        
        Protocol: Noise_XX_25519_ChaChaPoly_SHA256
            - XX: Handshake pattern (mutual auth, full handshake)
            - 25519: Curve25519 for Diffie-Hellman
            - ChaChaPoly: ChaCha20-Poly1305 for encryption
            - SHA256: SHA-256 for hashing
        """
        from noiseprotocol.connection import NoiseConnection
        
        # Initialize Noise state with our protocol
        noise_state = NoiseConnection.from_name(
            b"Noise_XX_25519_ChaChaPoly_SHA256"
        )
        
        # Set our static key (long-term identity)
        noise_state.set_keypair_from_private_bytes(
            Keypair.STATIC,
            self.noise_privkey.to_bytes()
        )
        
        # Set prologue (authenticated but not encrypted metadata)
        noise_state.set_prologue(b"libp2p-noise-001")
        
        # Start handshake
        if initiator:
            noise_state.start_handshake()
        else:
            noise_state.start_handshake()
        
        return noise_state
```

### The NoiseHandshakePayload

During the handshake, peers exchange their libp2p identities:

```protobuf
// File: libp2p/security/noise/pb/noise.proto

message NoiseHandshakePayload {
    // The libp2p public key (NOT the Noise static key)
    bytes identity_key = 1;
    
    // Signature over the Noise static public key
    // Proves: "I control this libp2p identity AND this Noise key"
    bytes identity_sig = 2;
    
    // Optional application data (e.g., supported extensions)
    bytes data = 3;
}
```

**Why do we need this?**

The Noise protocol uses its own Curve25519 keys for the handshake. But libp2p nodes have their own identity keys (which might be RSA, Ed25519, secp256k1, etc.). We need to link the two:

```
Noise Static Key <--[signature]--> libp2p Identity Key

This signature proves:
"I am peer ID Qm... and I control both of these keys"
```

---

## 6. Phase 5: The Complete Noise Handshake {#noise-handshake}

Now for the main event: the actual Noise XX handshake with all its cryptographic glory.

### Noise XX Pattern Specification

```
Noise_XX_25519_ChaChaPoly_SHA256:
    -> e
    <- e, ee, s, es  
    -> s, se

Legend:
    ->           : Initiator sends message to responder
    <-           : Responder sends message to initiator
    e            : Generate ephemeral keypair, send public key
    s            : Send static public key (encrypted after first DH)
    ee           : Perform DH between ephemeral keys
    es           : Perform DH between initiator's ephemeral & responder's static
    se           : Perform DH between initiator's static & responder's ephemeral
```

### Message 1: Initiator → Responder

```python
async def _perform_handshake_outbound(
    self,
    handshake_rw: NoiseHandshakeReadWriter,
    expected_peer_id: ID
):
    """
    Perform the Noise XX handshake as the initiator.
    
    We send 3 messages, receive 2 messages.
    """
    
    # ═══════════════════════════════════════════════════════════
    # MESSAGE 1: Initiator → Responder
    # Pattern: -> e
    # ═══════════════════════════════════════════════════════════
    
    # Generate our ephemeral keypair
    # This is a temporary key just for this session
    # After handshake completes, it's thrown away (forward secrecy!)
    # The noise library handles this internally
    
    # Create payload for message 1
    # In XX pattern, first message typically has empty payload
    payload_1 = self.early_data  # Usually empty
    
    # Write message 1
    # Format: [2-byte length][noise_message][payload]
    # The noise_state.write_message() will:
    #   1. Generate ephemeral keypair if not exists
    #   2. Encrypt payload (but nothing to encrypt yet, no shared secret)
    #   3. Return: ephemeral_public_key || payload
    await handshake_rw.write_handshake_message(payload_1)
    
    print("[INITIATOR] Sent Message 1: ephemeral public key")
    
    # ═══════════════════════════════════════════════════════════
    # MESSAGE 2: Responder → Initiator
    # Pattern: <- e, ee, s, es
    # ═══════════════════════════════════════════════════════════
    
    # Read message 2 from responder
    payload_2 = await handshake_rw.read_handshake_message()
    
    # The noise_state.read_message() has done:
    #   1. Received responder's ephemeral public key (e)
    #   2. Performed DH between our ephemeral and their ephemeral (ee)
    #   3. Received responder's static public key, encrypted (s)
    #   4. Performed DH between our ephemeral and their static (es)
    #   5. Decrypted the payload using derived keys
    
    print("[INITIATOR] Received Message 2: e, ee, s, es")
    
    # Parse the payload - it contains responder's libp2p identity
    remote_handshake_payload = NoiseHandshakePayload()
    remote_handshake_payload.ParseFromString(payload_2)
    
    # Extract their libp2p public key
    remote_libp2p_pubkey = deserialize_public_key(
        remote_handshake_payload.identity_key
    )
    
    # Verify their signature
    # They signed: their_noise_static_key with their libp2p private key
    remote_noise_static_key = self.noise_state.get_remote_static()
    signature_valid = remote_libp2p_pubkey.verify(
        self._signature_payload(remote_noise_static_key),
        remote_handshake_payload.identity_sig
    )
    
    if not signature_valid:
        raise Exception("Invalid signature in handshake")
    
    # Get their peer ID
    remote_peer_id = ID.from_pubkey(remote_libp2p_pubkey)
    
    # Verify it matches expected peer ID
    if remote_peer_id != expected_peer_id:
        raise Exception(
            f"Peer ID mismatch: expected {expected_peer_id}, "
            f"got {remote_peer_id}"
        )
    
    print(f"[INITIATOR] Verified remote peer: {remote_peer_id}")
    
    # ═══════════════════════════════════════════════════════════
    # MESSAGE 3: Initiator → Responder
    # Pattern: -> s, se
    # ═══════════════════════════════════════════════════════════
    
    # Create our handshake payload with our identity
    our_handshake_payload = self._create_handshake_payload()
    payload_3 = our_handshake_payload.SerializeToString()
    
    # Write message 3
    # The noise_state.write_message() will:
    #   1. Send our static public key, encrypted
    #   2. Perform DH between our static and their ephemeral (se)
    #   3. Encrypt the payload
    #   4. Derive final transport keys (handshake complete!)
    await handshake_rw.write_handshake_message(payload_3)
    
    print("[INITIATOR] Sent Message 3: s, se")
    print("[INITIATOR] 🔒 Handshake complete! Secure channel established.")
    
    # Handshake is now complete!
    # The noise_state has transitioned from handshake mode to transport mode
    # We can now send/receive encrypted messages


def _create_handshake_payload(self) -> NoiseHandshakePayload:
    """
    Create the payload that proves our libp2p identity.
    """
    # Get our Noise static public key
    our_noise_static_pubkey = self.noise_state.get_static().public_bytes
    
    # Create signature over it with our libp2p private key
    signature = self.libp2p_privkey.sign(
        self._signature_payload(our_noise_static_pubkey)
    )
    
    # Create the payload
    payload = NoiseHandshakePayload()
    payload.identity_key = self.libp2p_keypair.public_key.serialize()
    payload.identity_sig = signature
    payload.data = b""  # Optional application data
    
    return payload


def _signature_payload(self, noise_static_pubkey: bytes) -> bytes:
    """
    Create the data to sign/verify.
    
    Format: "noise-libp2p-static-key:" || noise_static_pubkey
    """
    prefix = b"noise-libp2p-static-key:"
    return prefix + noise_static_pubkey
```

### Message Flow Visualization

Let's see the complete handshake with actual cryptographic operations:

```
═══════════════════════════════════════════════════════════════════════
TIME   INITIATOR (Alice)                    RESPONDER (Bob)
═══════════════════════════════════════════════════════════════════════

t=0    Generate ephemeral keypair           Waiting for message...
       e_priv_A, e_pub_A = genkey()
       
       State:
         e: (e_priv_A, e_pub_A)
         s: (s_priv_A, s_pub_A)  [not used yet]

───────────────────────────────────────────────────────────────────────
t=1    MESSAGE 1: -> e
       ─────────────────────────────────────────────────────>
       
       Sends: [length][e_pub_A][payload_empty]
       
       Wire bytes:
         0x00 0x20  = length (32 bytes)
         [32 bytes] = e_pub_A (Curve25519 public key)
         []         = empty payload

───────────────────────────────────────────────────────────────────────
t=2                                          Receive Message 1
                                             
                                             Store: remote_e = e_pub_A
                                             
                                             Generate ephemeral keypair
                                             e_priv_B, e_pub_B = genkey()
                                             
                                             Perform DH: ee
                                             shared_secret_1 = DH(e_priv_B, e_pub_A)
                                             
                                             Derive key: k1 = KDF(shared_secret_1)
                                             
                                             Now can encrypt with k1!

───────────────────────────────────────────────────────────────────────
t=3                                          MESSAGE 2: <- e, ee, s, es
       <─────────────────────────────────────────────────────
       
                                             Encrypts with k1:
                                               encrypted_s = encrypt(k1, s_pub_B)
                                               encrypted_payload = encrypt(k1, handshake_payload_B)
       
                                             Performs another DH: es
                                             shared_secret_2 = DH(s_priv_B, e_pub_A)
                                             
                                             Derive key: k2 = KDF(k1, shared_secret_2)
                                             
                                             Sends:
                                               [length]
                                               [e_pub_B]              (32 bytes)
                                               [encrypted_s_pub_B]    (48 bytes: 32 + 16 MAC)
                                               [encrypted_payload_B]  (variable + 16 MAC)

───────────────────────────────────────────────────────────────────────
t=4    Receive Message 2
       
       Store: remote_e = e_pub_B
       
       Perform DH: ee
       shared_secret_1 = DH(e_priv_A, e_pub_B)
       
       Derive key: k1 = KDF(shared_secret_1)
       
       Decrypt Bob's static key:
       s_pub_B = decrypt(k1, encrypted_s)
       
       Perform DH: es  
       shared_secret_2 = DH(e_priv_A, s_pub_B)
       
       Derive key: k2 = KDF(k1, shared_secret_2)
       
       Decrypt payload:
       handshake_payload_B = decrypt(k2, encrypted_payload_B)
       
       Verify Bob's identity:
       - Extract Bob's libp2p public key
       - Verify signature over s_pub_B
       - Check peer ID matches expected

───────────────────────────────────────────────────────────────────────
t=5    MESSAGE 3: -> s, se
       ─────────────────────────────────────────────────────>
       
       Perform DH: se
       shared_secret_3 = DH(s_priv_A, e_pub_B)
       
       Derive key: k3 = KDF(k2, shared_secret_3)
       
       Encrypt Alice's static key:
       encrypted_s = encrypt(k3, s_pub_A)
       
       Encrypt payload:
       handshake_payload_A = create_payload()
       encrypted_payload = encrypt(k3, handshake_payload_A)
       
       Sends:
         [length]
         [encrypted_s_pub_A]        (48 bytes)
         [encrypted_payload_A]      (variable + 16 MAC)

───────────────────────────────────────────────────────────────────────
t=6                                          Receive Message 3
                                             
                                             Perform DH: se
                                             shared_secret_3 = DH(e_priv_B, s_pub_A)
                                             
                                             Derive key: k3 = KDF(k2, shared_secret_3)
                                             
                                             Decrypt Alice's static key:
                                             s_pub_A = decrypt(k3, encrypted_s)
                                             
                                             Decrypt payload:
                                             handshake_payload_A = decrypt(k3, encrypted_payload_A)
                                             
                                             Verify Alice's identity:
                                             - Extract libp2p public key
                                             - Verify signature
                                             - Derive peer ID

───────────────────────────────────────────────────────────────────────
t=7    HANDSHAKE COMPLETE!                  HANDSHAKE COMPLETE!
       
       Derive transport keys:                Derive transport keys:
       k_send = KDF(k3, "send")             k_send = KDF(k3, "recv")  [opposite!]
       k_recv = KDF(k3, "recv")             k_recv = KDF(k3, "send")  [opposite!]
       
       Both parties now have:                Both parties now have:
       - Shared encryption keys              - Shared encryption keys
       - Verified peer identities            - Verified peer identities
       - Forward secrecy                     - Forward secrecy

═══════════════════════════════════════════════════════════════════════
```

### Key Derivation Details

The Key Derivation Function (KDF) uses HKDF-SHA256:

```python
def derive_keys(chaining_key: bytes, input_key_material: bytes) -> tuple:
    """
    Derive keys using HKDF (HMAC-based Key Derivation Function).
    
    Args:
        chaining_key: Previous key in the chain
        input_key_material: New secret (e.g., DH result)
    
    Returns:
        (new_chaining_key, cipher_key)
    """
    from cryptography.hazmat.primitives import hashes, hmac
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    
    # HMAC with chaining key
    h = hmac.HMAC(chaining_key, hashes.SHA256())
    h.update(input_key_material)
    temp_key = h.finalize()
    
    # Derive two keys from temp_key
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=64,  # 32 bytes each for two keys
        salt=temp_key,
        info=b""
    )
    keys = kdf.derive(b"\x01")
    
    new_chaining_key = keys[:32]
    cipher_key = keys[32:]
    
    return new_chaining_key, cipher_key
```

### The Handshake I/O Layer

```python
# File: libp2p/security/noise/io.py

class NoiseHandshakeReadWriter:
    """
    Handles reading and writing Noise handshake messages.
    
    Handshake messages are framed differently than transport messages:
    Format: [2-byte big-endian length][noise message]
    """
    
    def __init__(self, conn: IRawConnection, noise_state: NoiseConnection):
        self.conn = conn
        self.noise_state = noise_state
    
    async def write_handshake_message(self, payload: bytes) -> None:
        """
        Write a handshake message.
        
        Steps:
        1. Use noise_state to encrypt/frame the payload
        2. Prefix with 2-byte length
        3. Send over connection
        """
        # Let Noise library create the message
        # This includes: ephemeral/static keys + encrypted payload
        noise_message = self.noise_state.write_message(payload)
        
        # Frame it with length prefix
        length = len(noise_message)
        frame = length.to_bytes(2, 'big') + noise_message
        
        # Send
        await self.conn.write(frame)
    
    async def read_handshake_message(self) -> bytes:
        """
        Read a handshake message.
        
        Steps:
        1. Read 2-byte length
        2. Read that many bytes
        3. Use noise_state to decrypt/verify
        4. Return the payload
        """
        # Read length prefix
        length_bytes = await self.conn.read(2)
        length = int.from_bytes(length_bytes, 'big')
        
        # Read the message
        noise_message = await self.conn.read(length)
        
        # Let Noise library process it
        # This extracts keys, performs DH, decrypts payload
        try:
            payload = self.noise_state.read_message(noise_message)
        except Exception as e:
            raise NoiseHandshakeError(f"Failed to read message: {e}")
        
        return payload
```

---

## 7. Phase 6: Post-Handshake Encrypted Communication {#post-handshake}

After the handshake completes, we transition to "transport mode" where all data is encrypted.

### The Secure Connection

```python
# File: libp2p/security/noise/connection.py

class NoiseConnection(ISecureConn):
    """
    A secure connection after Noise handshake is complete.
    All read/write operations are encrypted.
    """
    
    def __init__(
        self,
        underlying_conn: IRawConnection,
        noise_state: NoiseConnection,
        remote_peer_id: ID,
        is_initiator: bool
    ):
        self.underlying_conn = underlying_conn
        self.noise_state = noise_state
        self.remote_peer_id = remote_peer_id
        self.is_initiator = is_initiator
        
        # Create transport reader/writer for post-handshake messages
        self.transport_rw = NoiseTransportReadWriter(
            underlying_conn,
            noise_state
        )
    
    async def read(self, n: int = None) -> bytes:
        """
        Read encrypted data from the connection.
        
        Each read decrypts one Noise transport message.
        """
        return await self.transport_rw.read_message()
    
    async def write(self, data: bytes) -> None:
        """
        Write data with encryption.
        
        The data is encrypted as a Noise transport message.
        """
        await self.transport_rw.write_message(data)
    
    def get_remote_peer(self) -> ID:
        """Get the verified peer ID of the remote peer"""
        return self.remote_peer_id
    
    def get_local_peer(self) -> ID:
        """Get our own peer ID"""
        return self.local_peer_id
    
    async def close(self) -> None:
        """Close the connection"""
        await self.underlying_conn.close()
```

### Transport Message Format

After handshake, messages have a different format:

```
Transport Message:
    [2-byte length][encrypted_payload][16-byte MAC]

Example:
    0x00 0x35  = 53 bytes follow
    [37 bytes] = encrypted data
    [16 bytes] = Poly1305 authentication tag
```

### The Transport I/O Layer

```python
# File: libp2p/security/noise/io.py

class NoiseTransportReadWriter:
    """
    Handles reading and writing encrypted transport messages.
    """
    
    MAX_PLAINTEXT_SIZE = 65519  # Noise limit
    
    def __init__(self, conn: IRawConnection, noise_state: NoiseConnection):
        self.conn = conn
        self.noise_state = noise_state
    
    async def write_message(self, data: bytes) -> None:
        """
        Write an encrypted transport message.
        
        Large messages are chunked to stay within Noise limits.
        """
        # Check size
        if len(data) > self.MAX_PLAINTEXT_SIZE:
            raise ValueError(f"Message too large: {len(data)} bytes")
        
        # Encrypt the data
        # Returns: ciphertext || 16-byte MAC
        encrypted = self.noise_state.encrypt(data)
        
        # Frame with length
        length = len(encrypted)
        frame = length.to_bytes(2, 'big') + encrypted
        
        # Send
        await self.conn.write(frame)
    
    async def read_message(self) -> bytes:
        """
        Read an encrypted transport message.
        """
        # Read length
        length_bytes = await self.conn.read(2)
        length = int.from_bytes(length_bytes, 'big')
        
        # Validate length
        if length > self.MAX_PLAINTEXT_SIZE + 16:  # +16 for MAC
            raise ValueError(f"Invalid message length: {length}")
        
        # Read encrypted message
        encrypted = await self.conn.read(length)
        
        # Decrypt
        try:
            plaintext = self.noise_state.decrypt(encrypted)
        except Exception as e:
            raise Exception(f"Decryption failed: {e}")
        
        return plaintext
```

### Cipher Details: ChaCha20-Poly1305

ChaCha20-Poly1305 is the AEAD (Authenticated Encryption with Associated Data) cipher:

```python
def encrypt_with_chacha20poly1305(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """
    Encrypt using ChaCha20-Poly1305.
    
    Args:
        key: 32-byte encryption key
        nonce: 12-byte nonce (incremented for each message)
        plaintext: Data to encrypt
    
    Returns:
        ciphertext || 16-byte authentication tag
    """
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    
    cipher = ChaCha20Poly1305(key)
    
    # Encrypt and authenticate
    # Returns: ciphertext || tag (combined)
    ciphertext_and_tag = cipher.encrypt(
        nonce,
        plaintext,
        associated_data=None  # No AD in Noise
    )
    
    return ciphertext_and_tag


def decrypt_with_chacha20poly1305(key: bytes, nonce: bytes, ciphertext_and_tag: bytes) -> bytes:
    """
    Decrypt and verify using ChaCha20-Poly1305.
    
    Raises:
        InvalidTag: If authentication fails (tampering detected)
    """
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    
    cipher = ChaCha20Poly1305(key)
    
    # Decrypt and verify
    plaintext = cipher.decrypt(
        nonce,
        ciphertext_and_tag,
        associated_data=None
    )
    
    return plaintext
```

### Nonce Management

Each message uses a unique nonce to prevent replay attacks:

```python
class CipherState:
    """
    Manages encryption state for one direction of communication.
    """
    
    def __init__(self, key: bytes):
        self.key = key
        self.nonce = 0  # Starts at 0, increments for each message
        self.cipher = ChaCha20Poly1305(key)
    
    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt a message"""
        # Convert nonce to 12 bytes (96 bits)
        nonce_bytes = self.nonce.to_bytes(12, 'little')
        
        # Encrypt
        ciphertext = self.cipher.encrypt(nonce_bytes, plaintext, None)
        
        # Increment nonce for next message
        self.nonce += 1
        
        # Check for nonce overflow (extremely unlikely)
        if self.nonce >= 2**64:
            raise Exception("Nonce exhausted, must rekey")
        
        return ciphertext
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt a message"""
        # Convert nonce to 12 bytes
        nonce_bytes = self.nonce.to_bytes(12, 'little')
        
        # Decrypt and verify
        plaintext = self.cipher.decrypt(nonce_bytes, ciphertext, None)
        
        # Increment nonce
        self.nonce += 1
        
        return plaintext
```

---

## 8. Code Walkthrough with py-libp2p {#code-walkthrough}

Let's trace through a complete example with actual code execution:

### Complete Example: Two Peers Connecting

```python
import trio
from libp2p import new_host
from libp2p.crypto.secp256k1 import create_new_key_pair

async def peer_alice():
    """Alice: The initiator"""
    
    # Step 1: Create host
    print("[Alice] Creating host...")
    key_pair_alice = create_new_key_pair()
    host_alice = new_host(key_pair=key_pair_alice)
    
    # Step 2: Start listening
    print("[Alice] Starting listener on port 9001...")
    await host_alice.get_network().listen("/ip4/127.0.0.1/tcp/9001")
    
    peer_id_alice = host_alice.get_id()
    print(f"[Alice] Peer ID: {peer_id_alice}")
    print(f"[Alice] Address: /ip4/127.0.0.1/tcp/9001/p2p/{peer_id_alice}")
    
    # Wait for Bob to start
    await trio.sleep(2)
    
    # Step 3: Dial Bob
    print("\n[Alice] Dialing Bob...")
    bob_addr = f"/ip4/127.0.0.1/tcp/9002/p2p/{peer_id_bob}"
    
    # This triggers:
    # 1. TCP dial
    # 2. Multistream negotiation
    # 3. Noise handshake
    # 4. Yamux negotiation
    # 5. Stream creation
    stream = await host_alice.new_stream(peer_id_bob, ["/echo/1.0.0"])
    
    print("[Alice] ✅ Connected! Secure stream established.")
    
    # Step 4: Send encrypted message
    message = b"Hello Bob, this is Alice!"
    print(f"[Alice] Sending: {message}")
    await stream.write(message)
    
    # Step 5: Receive encrypted response
    response = await stream.read()
    print(f"[Alice] Received: {response}")
    
    await stream.close()


async def peer_bob():
    """Bob: The responder"""
    
    # Step 1: Create host
    print("[Bob] Creating host...")
    key_pair_bob = create_new_key_pair()
    host_bob = new_host(key_pair=key_pair_bob)
    
    # Step 2: Register protocol handler
    async def echo_handler(stream):
        """Echo back whatever we receive"""
        print("[Bob] Received connection on /echo/1.0.0")
        
        # Read message
        data = await stream.read()
        print(f"[Bob] Received: {data}")
        
        # Echo it back
        print(f"[Bob] Echoing back: {data}")
        await stream.write(data)
        
        await stream.close()
    
    host_bob.set_stream_handler("/echo/1.0.0", echo_handler)
    
    # Step 3: Start listening
    print("[Bob] Starting listener on port 9002...")
    await host_bob.get_network().listen("/ip4/127.0.0.1/tcp/9002")
    
    global peer_id_bob
    peer_id_bob = host_bob.get_id()
    print(f"[Bob] Peer ID: {peer_id_bob}")
    print(f"[Bob] Address: /ip4/127.0.0.1/tcp/9002/p2p/{peer_id_bob}")
    print("[Bob] Waiting for connections...\n")
    
    # Wait forever
    await trio.sleep_forever()


# Run both peers concurrently
async def main():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(peer_bob)
        nursery.start_soon(peer_alice)

trio.run(main)
```

### Expected Output:

```
[Bob] Creating host...
[Bob] Starting listener on port 9002...
[Bob] Peer ID: QmBob1234...
[Bob] Address: /ip4/127.0.0.1/tcp/9002/p2p/QmBob1234...
[Bob] Waiting for connections...

[Alice] Creating host...
[Alice] Starting listener on port 9001...
[Alice] Peer ID: QmAlice567...
[Alice] Address: /ip4/127.0.0.1/tcp/9001/p2p/QmAlice567...

[Alice] Dialing Bob...
[Alice] TCP connecting to 127.0.0.1:9002...
[Alice] TCP connection established
[Alice] Negotiating /multistream/1.0.0...
[Alice] Negotiating /noise...
[Alice] Starting Noise handshake as initiator...
[Alice] Sent Message 1: ephemeral key
[Bob] Accepted TCP connection from 127.0.0.1:9001
[Bob] Negotiating /multistream/1.0.0...
[Bob] Negotiating /noise...
[Bob] Starting Noise handshake as responder...
[Bob] Received Message 1: ephemeral key
[Bob] Sent Message 2: e, ee, s, es
[Alice] Received Message 2: e, ee, s, es
[Alice] Verified remote peer: QmBob1234...
[Alice] Sent Message 3: s, se
[Bob] Received Message 3: s, se
[Bob] Verified remote peer: QmAlice567...
[Bob] 🔒 Handshake complete!
[Alice] 🔒 Handshake complete!
[Alice] Negotiating /yamux/1.0.0...
[Bob] Negotiating /yamux/1.0.0...
[Alice] Opening stream for /echo/1.0.0...
[Bob] Received connection on /echo/1.0.0
[Alice] ✅ Connected! Secure stream established.
[Alice] Sending: b'Hello Bob, this is Alice!'
[Bob] Received: b'Hello Bob, this is Alice!'
[Bob] Echoing back: b'Hello Bob, this is Alice!'
[Alice] Received: b'Hello Bob, this is Alice!'
```

---

## 9. Wire Protocol Analysis {#wire-protocol}

Let's examine what actually goes over the wire, byte by byte.

### Packet Capture Analysis

Using Wireshark or tcpdump, here's what we'd see:

```
═══════════════════════════════════════════════════════════════
PACKET 1-3: TCP Handshake
═══════════════════════════════════════════════════════════════
Alice → Bob: SYN
Bob → Alice: SYN-ACK  
Alice → Bob: ACK

═══════════════════════════════════════════════════════════════
PACKET 4: multistream-select Header (Alice)
═══════════════════════════════════════════════════════════════
Hex: 13 2f 6d 75 6c 74 69 73 74 72 65 61 6d 2f 31 2e 30 2e 30 0a

Decoded:
  0x13               = 19 (length as varint)
  2f 6d 75 ... 30    = "/multistream/1.0.0"
  0a                 = newline

═══════════════════════════════════════════════════════════════
PACKET 5: multistream-select Header (Bob)
═══════════════════════════════════════════════════════════════
Hex: 13 2f 6d 75 6c 74 69 73 74 72 65 61 6d 2f 31 2e 30 2e 30 0a

(Same as Alice's packet - confirming support)

═══════════════════════════════════════════════════════════════
PACKET 6: Noise Protocol Request (Alice)
═══════════════════════════════════════════════════════════════
Hex: 07 2f 6e 6f 69 73 65 0a

Decoded:
  0x07         = 7 (length)
  2f 6e ... 65 = "/noise"
  0a           = newline

═══════════════════════════════════════════════════════════════
PACKET 7: Noise Protocol Confirmation (Bob)
═══════════════════════════════════════════════════════════════
Hex: 07 2f 6e 6f 69 73 65 0a

(Bob confirms he supports Noise)

═══════════════════════════════════════════════════════════