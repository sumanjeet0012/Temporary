# Complete Guide to TCP in py-libp2p: From Basics to Implementation

## Table of Contents
1. [What is TCP and Why We Need It](#what-is-tcp)
2. [libp2p Architecture Overview](#libp2p-architecture)
3. [TCP Transport in py-libp2p](#tcp-transport)
4. [Complete Connection Workflow](#connection-workflow)
5. [Security Layer: Noise Handshake](#noise-handshake)
6. [Multiplexing Layer: Yamux](#yamux-multiplexer)
7. [Complete Code Example](#complete-example)
8. [Real-World Examples](#real-world-examples)

---

## 1. What is TCP and Why We Need It? {#what-is-tcp}

### What is TCP?

**TCP (Transmission Control Protocol)** is a fundamental protocol that provides:

- **Reliable delivery**: Guarantees that data arrives in order and without errors
- **Connection-oriented**: Establishes a dedicated connection between two endpoints
- **Stream-based**: Data flows as a continuous stream of bytes
- **Error detection**: Detects corrupted packets and retransmits them
- **Flow control**: Prevents sender from overwhelming the receiver

### Why Do We Need TCP in libp2p?

Think of TCP as the **postal service** for the internet:

```
Without TCP:
    App A ---> [packets might get lost, arrive out of order] ---> App B

With TCP:
    App A ---> [TCP ensures all packets arrive correctly] ---> App B
```

**libp2p needs TCP because:**

1. **Foundation Layer**: TCP provides the basic reliable connection that other protocols build upon
2. **Universal Support**: Almost every device/network supports TCP
3. **NAT Traversal**: TCP connections can work through Network Address Translation (NAT)
4. **Simple to Implement**: Well-understood protocol with good library support

### Real-World Analogy

Imagine you want to have a phone conversation:

- **TCP** = The phone line that ensures your voice reaches the other person clearly
- **Noise Protocol** = Encryption so nobody can eavesdrop on your conversation
- **Yamux** = Conference call capability - multiple conversations on the same phone line
- **libp2p Streams** = Individual conversations about different topics

---

## 2. libp2p Architecture Overview {#libp2p-architecture}

### The libp2p Stack

libp2p organizes networking into clear layers, like a layered cake:

```
┌─────────────────────────────────────────┐
│   Application Layer (Your Code)        │  ← You write protocol handlers
├─────────────────────────────────────────┤
│   Streams (Protocol Identification)    │  ← /chat/1.0.0, /dht/1.0.0
├─────────────────────────────────────────┤
│   Multiplexer (Yamux/mplex)            │  ← Multiple streams over 1 connection
├─────────────────────────────────────────┤
│   Security (Noise/TLS)                 │  ← Encryption + Authentication
├─────────────────────────────────────────┤
│   Transport (TCP/QUIC/WebSocket)       │  ← Physical connection
├─────────────────────────────────────────┤
│   Network (IP Layer)                   │  ← Internet infrastructure
└─────────────────────────────────────────┘
```

### Key Components

#### 1. **Host**
The main entry point - represents your node in the network:
```python
# A Host is like your "office building" in the network
host = new_host()
# It has:
# - A unique peer ID (like a street address)
# - Transport protocols (how to receive visitors)
# - Security protocols (how to verify visitors)
# - A router for handling incoming connections
```

#### 2. **Transport**
Creates raw connections between peers:
- TCP, QUIC, WebSocket, etc.
- Each transport knows how to dial and listen on specific network protocols

#### 3. **Connection**
A physical link between two peers:
```
Peer A (TCP Transport) <----Connection----> Peer B (TCP Transport)
         |                                           |
    [127.0.0.1:8000]                         [127.0.0.1:9000]
```

#### 4. **Upgrader**
Takes a raw connection and adds security + multiplexing:
```
Raw TCP Connection
        ↓
    [Upgrader]
        ↓
    Apply Security (Noise Handshake)
        ↓
    Apply Multiplexing (Yamux)
        ↓
Secure, Multiplexed Connection
```

#### 5. **Streams**
Logical channels within a connection:
```
Connection
    ├─ Stream 1: /chat/1.0.0
    ├─ Stream 2: /file-transfer/1.0.0
    └─ Stream 3: /dht/1.0.0
```

---

## 3. TCP Transport in py-libp2p {#tcp-transport}

### What Does TCP Transport Do?

The TCP transport in py-libp2p is responsible for:

1. **Listening** for incoming TCP connections
2. **Dialing** (initiating) outgoing TCP connections
3. **Creating** raw connection objects from TCP sockets

### Code Structure

In py-libp2p, the TCP transport is implemented in `libp2p/transport/tcp/tcp.py`:

```python
class TCP(ITransport):
    """
    TCP transport implementation for libp2p
    """
    
    async def dial(self, maddr: Multiaddr) -> IRawConnection:
        """
        Dial (connect to) a peer at the given multiaddress
        
        Args:
            maddr: Multiaddress like "/ip4/127.0.0.1/tcp/8000"
        
        Returns:
            A raw connection to the peer
        """
        # 1. Parse the multiaddress to extract IP and port
        # 2. Create an asyncio TCP connection
        # 3. Wrap it in a RawConnection object
        # 4. Return the raw connection
    
    def create_listener(
        self, 
        handler_function: Callable
    ) -> TCPListener:
        """
        Create a TCP listener for incoming connections
        
        Args:
            handler_function: Called when a new connection arrives
        
        Returns:
            A TCPListener object
        """
        # Returns a listener that will accept incoming TCP connections
```

### Multiaddress Format

libp2p uses **multiaddress** to represent network addresses:

```python
# Traditional format:
"127.0.0.1:8000"

# Multiaddress format:
"/ip4/127.0.0.1/tcp/8000"

# With peer ID:
"/ip4/127.0.0.1/tcp/8000/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
```

**Benefits of Multiaddress:**
- Self-describing: You can see it's IPv4 + TCP
- Composable: Can chain multiple protocols
- Future-proof: Easy to add new address types

---

## 4. Complete Connection Workflow {#connection-workflow}

Let's trace the entire journey from "Host Creation" to "Sending a Message":

### Step 1: Create a Host

```python
import trio
from libp2p import new_host
from libp2p.crypto.secp256k1 import create_new_key_pair

async def create_host(port: int):
    # 1. Generate a cryptographic key pair
    # This becomes the host's identity
    key_pair = create_new_key_pair()
    
    # 2. Create the host
    host = new_host(
        key_pair=key_pair
    )
    
    # 3. Start listening on a TCP port
    listen_addr = f"/ip4/0.0.0.0/tcp/{port}"
    await host.get_network().listen(listen_addr)
    
    return host
```

**What happens internally:**

```
1. Key Pair Generation
   ├─ Private Key: Used for signing/authentication
   └─ Public Key: Hashed to create Peer ID

2. Host Initialization
   ├─ Creates Network Manager
   ├─ Registers TCP Transport
   ├─ Registers Security Protocols (Noise)
   ├─ Registers Multiplexers (Yamux)
   └─ Initializes Protocol Handlers

3. Start Listening
   ├─ TCP Transport creates socket
   ├─ Binds to 0.0.0.0:port
   └─ Starts accepting connections
```

### Step 2: Peer A Dials Peer B

```python
# Peer A wants to connect to Peer B
peer_b_addr = "/ip4/127.0.0.1/tcp/9000/p2p/QmPeerBID..."

# Dial the peer
stream = await host_a.new_stream(peer_b_id, ["/chat/1.0.0"])
```

**Detailed Flow:**

```
Peer A                                              Peer B
  |                                                    |
  | 1. host.new_stream(peer_b_id, protocols)          |
  |    ↓                                               |
  | 2. Check if connection exists                     |
  |    ↓                                               |
  | 3. No connection? Need to dial                    |
  |    ↓                                               |
  | 4. TCP.dial(multiaddr)                            |
  |    ├─ Parse IP: 127.0.0.1                        |
  |    ├─ Parse Port: 9000                           |
  |    └─ Create TCP socket                          |
  |                                                   |
  | 5. TCP SYN --------------------------------->    |
  |                                                   | 6. TCP SYN-ACK
  | 7. TCP ACK <---------------------------------    |
  |                                                   |
  | 8. Raw TCP Connection Established                |
  |    (but not secured or multiplexed yet)          |
  |                                                   |
```

### Step 3: Connection Upgrade - Security Negotiation

Now we have a raw TCP connection, but it's not secure. The **Upgrader** kicks in:

```
Raw TCP Connection
        ↓
[Protocol Negotiation - multistream-select]
        ↓
Peer A → "/noise"
        ↓
Peer B → "/noise" (agreed!)
        ↓
[NOISE HANDSHAKE BEGINS]
```

### Step 4: Noise Handshake (Detailed in Next Section)

After Noise completes, we have an **encrypted, authenticated connection**.

### Step 5: Multiplexer Negotiation

```
Encrypted Connection
        ↓
[Protocol Negotiation - multistream-select]
        ↓
Peer A → "/yamux/1.0.0"
        ↓
Peer B → "/yamux/1.0.0" (agreed!)
        ↓
[YAMUX SESSION ESTABLISHED]
```

### Step 6: Open a Stream

```python
# Now we can open multiple streams
stream = await connection.open_stream("/chat/1.0.0")
```

```
Yamux Multiplexed Connection
        ↓
Open new stream (Stream ID = 1)
        ↓
[Negotiate stream protocol: "/chat/1.0.0"]
        ↓
Stream ready for application data
```

### Step 7: Send/Receive Data

```python
# Send a message
await stream.write(b"Hello, Peer B!")

# Receive a message
data = await stream.read()
print(f"Received: {data}")
```

**What happens at each layer:**

```
Application: stream.write(b"Hello, Peer B!")
        ↓
Stream: Adds protocol framing
        ↓
Yamux: Wraps with stream ID header
        ↓
Noise: Encrypts the frame
        ↓
TCP: Sends encrypted bytes over network
        ↓
Network: IP routing to destination
```

---

## 5. Security Layer: Noise Handshake {#noise-handshake}

### What is Noise?

**Noise Protocol Framework** is a modern cryptographic framework that provides:
- **Encryption**: Nobody can read your messages
- **Authentication**: You know who you're talking to
- **Forward Secrecy**: Past messages stay secure even if keys are compromised

### Why Not Just TLS?

- **Flexibility**: Noise is simpler and more modular than TLS
- **Performance**: Fewer round trips than TLS
- **Peer-to-Peer**: Designed for P2P, where both sides are equal (unlike client-server TLS)

### The Noise XX Pattern

libp2p uses the **Noise XX** handshake pattern:

```
XX Pattern:
    -> e (send ephemeral public key)
    <- e, ee, s, es (receive ephemeral, do DH, receive static, do DH)
    -> s, se (send static, do DH)
```

**Key Types:**
- **Ephemeral Key**: Temporary key for this session only
- **Static Key**: Long-term key tied to identity
- **DH**: Diffie-Hellman key exchange

### Complete Noise Handshake Flow

```
Initiator (Peer A)                      Responder (Peer B)
      |                                         |
      | Generate ephemeral keypair             |
      |                                         |
      | ---> Message 1: e ---------------->    | Receive ephemeral key
      |                                         | Generate ephemeral keypair
      |                                         | Generate static keypair
      |                                         | Compute shared secrets
      |                                         |
      | <--- Message 2: e, ee, s, es <-----    | Send ephemeral, static keys
      |                                         |
      | Verify peer's identity                  |
      | Compute shared secrets                  |
      |                                         |
      | ---> Message 3: s, se ------------->   | Verify peer's identity
      |                                         | Handshake complete!
      | Handshake complete!                     |
      |                                         |
      | <===== Encrypted Communication =====>  |
```

### Noise Handshake Payload

In each handshake message, peers exchange a **payload** containing:

```protobuf
message NoiseHandshakePayload {
    bytes identity_key = 1;        // libp2p public key
    bytes identity_sig = 2;        // Signature over noise static key
    bytes data = 3;                // Optional early data
}
```

**Purpose:**
- **identity_key**: The peer's libp2p identity (not the Noise key)
- **identity_sig**: Proves the peer controls their libp2p identity
- **data**: Can send application data early to reduce latency

### Code Example in py-libp2p

```python
from libp2p.security.noise.transport import Transport as NoiseTransport
from libp2p.crypto.secp256k1 import create_new_key_pair

# Create a Noise transport
key_pair = create_new_key_pair()
noise_transport = NoiseTransport(
    libp2p_keypair=key_pair,
    noise_privkey=key_pair.private_key,
)

# When a raw connection arrives, upgrade it
async def upgrade_connection(raw_conn):
    # As the initiator (dialer)
    secure_conn = await noise_transport.secure_outbound(
        raw_conn, 
        peer_id
    )
    
    # As the responder (listener)
    secure_conn = await noise_transport.secure_inbound(raw_conn)
    
    # Now we have an encrypted connection!
    return secure_conn
```

### What Noise Gives You

After the handshake:

1. **Shared Secret Keys**: Both peers have the same encryption keys
2. **Authenticated Identity**: Each peer knows the other's libp2p Peer ID
3. **Encrypted Channel**: All future data is encrypted
4. **Forward Secrecy**: Ephemeral keys ensure past sessions stay secure

---

## 6. Multiplexing Layer: Yamux {#yamux-multiplexer}

### What is Stream Multiplexing?

Imagine you have **one phone line** but want to have **multiple conversations**:

```
Without Multiplexing:
    Phone call about topic A  → Needs its own phone line
    Phone call about topic B  → Needs another phone line
    Phone call about topic C  → Needs yet another phone line

With Multiplexing (Yamux):
    Single phone line → Conference call with topics A, B, C
```

### Why Do We Need Yamux?

**Problem**: Opening multiple TCP connections is expensive:
- Each connection requires a new TCP handshake (3 packets)
- Each connection requires a new Noise handshake (3 messages)
- Operating systems limit the number of open connections

**Solution**: Yamux multiplexes many logical streams over one physical connection.

### How Yamux Works

Yamux wraps each message with a **header** that identifies which stream it belongs to:

```
Physical Connection:
    [Header: Stream 1][Data: "Hello"]
    [Header: Stream 2][Data: "File chunk 1"]
    [Header: Stream 1][Data: "World"]
    [Header: Stream 3][Data: "DHT query"]
    [Header: Stream 2][Data: "File chunk 2"]
```

### Yamux Frame Format

Every Yamux message starts with a 12-byte header:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|Version|       Type      |         Flags                       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        Stream ID                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        Length                                 |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

**Fields:**
- **Version**: Always 0 (current version)
- **Type**: Data, Window Update, Ping, Go Away
- **Flags**: SYN (new stream), ACK (acknowledge), FIN (close), RST (reset)
- **Stream ID**: Which stream this frame belongs to
- **Length**: Size of data following the header

### Stream Lifecycle

```
1. Open Stream
   Initiator → [SYN, Stream ID=1] → Responder
   Initiator ← [ACK, Stream ID=1] ← Responder

2. Send Data
   Initiator → [Data, Stream ID=1, "Hello"] → Responder

3. Flow Control
   Responder → [Window Update, Stream ID=1, 64KB] → Initiator
   (Tells initiator it can send more data)

4. Close Stream
   Initiator → [FIN, Stream ID=1] → Responder
   Initiator ← [ACK, Stream ID=1] ← Responder
```

### Yamux Flow Control

Yamux prevents fast senders from overwhelming slow receivers:

```
Initial window size: 256 KB

Sender's View:
    Window Remaining: 256 KB
    ↓
    Send 100 KB of data
    ↓
    Window Remaining: 156 KB
    ↓
    Receiver sends Window Update: +200 KB
    ↓
    Window Remaining: 356 KB
```

### Code Example

```python
from libp2p.stream_muxer.yamux import Yamux

# After Noise handshake, create Yamux session
muxer = Yamux(secure_connection)

# Open a new stream
stream = await muxer.open_stream()

# Send data on the stream
await stream.write(b"Hello over Yamux!")

# Read from the stream
data = await stream.read()
```

### Yamux vs mplex

| Feature | Yamux | mplex |
|---------|-------|-------|
| Flow Control | ✅ Yes | ❌ No |
| Backpressure | ✅ Yes | ❌ No |
| Stream Limits | ✅ Configurable | ❌ None |
| Status | ✅ Recommended | ⚠️ Being deprecated |

---

## 7. Complete Code Example {#complete-example}

Here's a complete example showing two peers communicating over TCP with Noise and Yamux:

```python
import trio
import secrets
from libp2p import new_host
from libp2p.crypto.secp256k1 import create_new_key_pair
from libp2p.network.stream.net_stream_interface import INetStream

# Protocol ID for our chat application
PROTOCOL_ID = "/chat/1.0.0"

async def read_data(stream: INetStream) -> None:
    """Continuously read data from the stream"""
    while True:
        try:
            data = await stream.read()
            if not data:
                break
            print(f"Received: {data.decode()}")
        except Exception as e:
            print(f"Read error: {e}")
            break

async def write_data(stream: INetStream) -> None:
    """Send user input to the stream"""
    while True:
        try:
            message = await trio.lowlevel.open_stdin().receive_some()
            await stream.write(message)
        except Exception as e:
            print(f"Write error: {e}")
            break

async def chat_handler(stream: INetStream) -> None:
    """Handle incoming chat connections"""
    print(f"New connection from {stream.mplex_conn.peer_id}")
    
    async with trio.open_nursery() as nursery:
        nursery.start_soon(read_data, stream)
        nursery.start_soon(write_data, stream)

async def create_and_run_host(port: int, destination: str = None):
    """
    Create a libp2p host and optionally connect to another peer
    
    Args:
        port: Port to listen on
        destination: Multiaddress of peer to connect to (optional)
    """
    # Step 1: Generate identity
    secret = secrets.token_bytes(32)
    key_pair = create_new_key_pair(secret)
    
    # Step 2: Create host with TCP transport
    # (Noise and Yamux are added by default)
    host = new_host(key_pair=key_pair)
    
    # Step 3: Register our chat protocol handler
    host.set_stream_handler(PROTOCOL_ID, chat_handler)
    
    # Step 4: Start listening on TCP
    listen_addr = f"/ip4/0.0.0.0/tcp/{port}"
    await host.get_network().listen(listen_addr)
    
    print(f"Host created with ID: {host.get_id()}")
    print(f"Listening on: {listen_addr}")
    print(f"Full address: {listen_addr}/p2p/{host.get_id()}")
    
    # Step 5: If destination provided, dial the peer
    if destination:
        print(f"Dialing {destination}...")
        
        # Extract peer ID from multiaddress
        from multiaddr import Multiaddr
        maddr = Multiaddr(destination)
        peer_id = maddr.value_for_protocol('p2p')
        
        # Add peer to peerstore
        await host.connect(maddr)
        
        # Open a stream to the peer
        stream = await host.new_stream(peer_id, [PROTOCOL_ID])
        print(f"Connected to {peer_id}")
        
        # Start reading and writing
        async with trio.open_nursery() as nursery:
            nursery.start_soon(read_data, stream)
            nursery.start_soon(write_data, stream)
    else:
        # Just wait for incoming connections
        await trio.sleep_forever()

# Run the host
if __name__ == "__main__":
    import sys
    
    port = int(sys.argv[1])
    destination = sys.argv[2] if len(sys.argv) > 2 else None
    
    trio.run(create_and_run_host, port, destination)
```

### Running the Example

**Terminal 1 (Listener):**
```bash
python chat.py 8000
# Output:
# Host created with ID: QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N
# Listening on: /ip4/0.0.0.0/tcp/8000
# Full address: /ip4/0.0.0.0/tcp/8000/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N
```

**Terminal 2 (Dialer):**
```bash
python chat.py 9000 /ip4/127.0.0.1/tcp/8000/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N
# Output:
# Host created with ID: QmPeerB...
# Listening on: /ip4/0.0.0.0/tcp/9000
# Dialing /ip4/127.0.0.1/tcp/8000/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N...
# Connected to QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N
```

Now you can type messages in either terminal and they'll appear in the other!

### What Happened Under the Hood

```
Terminal 1 (Listener)                    Terminal 2 (Dialer)
      |                                         |
      | 1. Create Host                         | 1. Create Host
      | 2. Listen on TCP 8000                  | 2. Listen on TCP 9000
      | 3. Register /chat/1.0.0 handler        | 3. Register /chat/1.0.0 handler
      |                                         |
      |                                         | 4. Dial listener's address
      |                                         |    TCP.dial("/ip4/.../tcp/8000")
      |                                         |
      | 5. Accept TCP connection               | 6. TCP connection established
      |                                         |
      | 7. Noise handshake ↔                   | 7. Noise handshake ↔
      |    (3 messages exchanged)               |
      |                                         |
      | 8. Yamux negotiation ↔                 | 8. Yamux negotiation ↔
      |                                         |
      | 9. Stream opened for /chat/1.0.0       | 9. Stream opened for /chat/1.0.0
      |                                         |
      | 10. User types "Hello"                 |
      |     └─> stream.write(b"Hello")         |
      |         └─> Yamux frames it            |
      |             └─> Noise encrypts it      |
      |                 └─> TCP sends it ─────>| 11. TCP receives bytes
      |                                         |     └─> Noise decrypts
      |                                         |         └─> Yamux deframes
      |                                         |             └─> Stream receives
      |                                         |                 └─> Print "Hello"
```

---

## 8. Real-World Examples {#real-world-examples}

### Example 1: File Transfer Application

```python
import trio
from libp2p import new_host

PROTOCOL_ID = "/file-transfer/1.0.0"

async def file_transfer_handler(stream):
    """Receive a file and save it"""
    # Read file name
    name_length = int.from_bytes(await stream.read(4), 'big')
    file_name = (await stream.read(name_length)).decode()
    
    # Read file size
    file_size = int.from_bytes(await stream.read(8), 'big')
    
    print(f"Receiving file: {file_name} ({file_size} bytes)")
    
    # Read file data
    with open(f"received_{file_name}", 'wb') as f:
        remaining = file_size
        while remaining > 0:
            chunk_size = min(remaining, 8192)
            chunk = await stream.read(chunk_size)
            f.write(chunk)
            remaining -= len(chunk)
    
    print(f"File received: received_{file_name}")
    await stream.close()

async def send_file(stream, file_path):
    """Send a file over the stream"""
    import os
    
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    # Send file name
    name_bytes = file_name.encode()
    await stream.write(len(name_bytes).to_bytes(4, 'big'))
    await stream.write(name_bytes)
    
    # Send file size
    await stream.write(file_size.to_bytes(8, 'big'))
    
    print(f"Sending file: {file_name} ({file_size} bytes)")
    
    # Send file data
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            await stream.write(chunk)
    
    print(f"File sent: {file_name}")
    await stream.close()
```

**What's happening:**
1. TCP provides the reliable byte stream
2. Noise encrypts the file during transfer
3. Yamux allows file transfer and chat to happen simultaneously
4. The application protocol defines the file transfer format

### Example 2: Distributed Hash Table (DHT) Node

```python
import trio
from libp2p import new_host

DHT_PROTOCOL = "/dht/1.0.0"

class DHTNode:
    def __init__(self):
        self.storage = {}  # key -> value storage
        self.peers = set()  # known peers
    
    async def handle_dht_request(self, stream):
        """Handle DHT protocol messages"""
        # Read the request type
        request_type = (await stream.read(1))[0]
        
        if request_type == 0x01:  # PUT request
            key_len = int.from_bytes(await stream.read(2), 'big')
            key = await stream.read(key_len)
            
            value_len = int.from_bytes(await stream.read(4), 'big')
            value = await stream.read(value_len)
            
            self.storage[key] = value
            await stream.write(b'\x00')  # Success
            print(f"Stored: {key} = {value}")
        
        elif request_type == 0x02:  # GET request
            key_len = int.from_bytes(await stream.read(2), 'big')
            key = await stream.read(key_len)
            
            if key in self.storage:
                value = self.storage[key]
                await stream.write(b'\x00')  # Found
                await stream.write(len(value).to_bytes(4, 'big'))
                await stream.write(value)
                print(f"Retrieved: {key} = {value}")
            else:
                await stream.write(b'\x01')  # Not found
                print(f"Not found: {key}")
        
        await stream.close()
    
    async def put(self, host, peer_id, key, value):
        """Store a key-value pair in a remote DHT node"""
        stream = await host.new_stream(peer_id, [DHT_PROTOCOL])
        
        # Send PUT request
        await stream.write(b'\x01')  # PUT opcode
        await stream.write(len(key).to_bytes(2, 'big'))
        await stream.write(key)
        await stream.write(len(value).to_bytes(4, 'big'))
        await stream.write(value)
        
        # Wait for acknowledgment
        response = await stream.read(1)
        await stream.close()
        
        return response == b'\x00'
    
    async def get(self, host, peer_id, key):
        """Retrieve a value from a remote DHT node"""
        stream = await host.new_stream(peer_id, [DHT_PROTOCOL])
        
        # Send GET request
        await stream.write(b'\x02')  # GET opcode
        await stream.write(len(key).to_bytes(2, 'big'))
        await stream.write(key)
        
        # Read response
        status = await stream.read(1)
        if status == b'\x00':  # Found
            value_len = int.from_bytes(await stream.read(4), 'big')
            value = await stream.read(value_len)
            await stream.close()
            return value
        else:
            await stream.close()
            return None
```

**Usage:**
```python
# Node 1 (DHT server)
async def run_dht_server():
    host = new_host()
    dht = DHTNode()
    host.set_stream_handler(DHT_PROTOCOL, dht.handle_dht_request)
    await host.get_network().listen("/ip4/0.0.0.0/tcp/8000")
    await trio.sleep_forever()

# Node 2 (DHT client)
async def run_dht_client():
    host = new_host()
    dht = DHTNode()
    await host.get_network().listen("/ip4/0.0.0.0/tcp/9000")
    
    peer_addr = "/ip4/127.0.0.1/tcp/8000/p2p/QmNode1..."
    await host.connect(peer_addr)
    
    # Store a value
    await dht.put(host, "QmNode1...", b"my-key", b"my-value")
    
    # Retrieve a value
    value = await dht.get(host, "QmNode1...", b"my-key")
    print(f"Retrieved: {value}")
```

**Real-world benefit:**
- **Single TCP connection** handles many DHT operations
- **Yamux** allows concurrent GET/PUT requests
- **Noise** ensures data privacy and authenticity
- **TCP** ensures reliable delivery of DHT data

### Example 3: Pub/Sub System (Gossipsub)

```python
import trio
from libp2p import new_host
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub

async def message_handler(peer_id, message):
    """Handle incoming pubsub messages"""
    print(f"Received from {peer_id}: {message.data.decode()}")

async def run_pubsub_node(port: int, topic: str, bootstrap_peers=None):
    """
    Create a node that participates in a pub/sub network
    """
    # Create host
    host = new_host()
    await host.get_network().listen(f"/ip4/0.0.0.0/tcp/{port}")
    
    # Initialize GossipSub (pub/sub protocol)
    gossipsub = GossipSub(
        protocols=["/meshsub/1.0.0"],
        degree=6,  # Number of peers to maintain in mesh
        degree_low=4,
        degree_high=12
    )
    
    pubsub = Pubsub(host, gossipsub)
    
    # Subscribe to topic
    await pubsub.subscribe(topic)
    pubsub.set_topic_validator(topic, message_handler)
    
    print(f"Node {host.get_id()} listening on port {port}")
    print(f"Subscribed to topic: {topic}")
    
    # Connect to bootstrap peers
    if bootstrap_peers:
        for peer_addr in bootstrap_peers:
            await host.connect(peer_addr)
            print(f"Connected to {peer_addr}")
    
    # Publish messages periodically
    async def publish_messages():
        count = 0
        while True:
            await trio.sleep(5)
            message = f"Hello from {host.get_id()[:8]} - {count}"
            await pubsub.publish(topic, message.encode())
            print(f"Published: {message}")
            count += 1
    
    async with trio.open_nursery() as nursery:
        nursery.start_soon(publish_messages)

# Run multiple nodes
if __name__ == "__main__":
    # Node 1 (bootstrap)
    # python pubsub.py 8000 /my-topic
    
    # Node 2 (joins network)
    # python pubsub.py 9000 /my-topic /ip4/127.0.0.1/tcp/8000/p2p/QmNode1...
```

**How it works:**
1. **TCP connections** between all participating nodes
2. **Noise** secures all gossip messages
3. **Yamux** allows multiple topics over same connection
4. **GossipSub protocol** runs on top, handling message routing

### Example 4: NAT Traversal with TCP

Sometimes peers are behind NATs (routers) and can't accept incoming connections directly. libp2p has solutions:

```python
from libp2p import new_host
from libp2p.network.connection.swarm_connection import SwarmConn

async def setup_relay_client():
    """
    Use a relay node to receive connections when behind NAT
    """
    host = new_host()
    await host.get_network().listen("/ip4/0.0.0.0/tcp/0")
    
    # Connect to a relay node
    relay_addr = "/ip4/relay.libp2p.io/tcp/4001/p2p/QmRelay..."
    await host.connect(relay_addr)
    
    # Enable circuit relay (relay mode)
    # Now other peers can reach us via:
    # /ip4/relay.libp2p.io/tcp/4001/p2p/QmRelay.../p2p-circuit/p2p/QmOurID
    
    print(f"Reachable via relay: {relay_addr}/p2p-circuit/p2p/{host.get_id()}")
    
    await trio.sleep_forever()
```

**Circuit Relay Flow:**
```
Peer A (behind NAT)          Relay Node          Peer B (behind NAT)
        |                         |                        |
        | TCP connect             |                        |
        |------------------------>|                        |
        |                         |<-----------------------|
        |                         |       TCP connect      |
        |                         |                        |
        |  "Please relay to B"    |                        |
        |------------------------>|                        |
        |                         |  "A wants to talk"     |
        |                         |----------------------->|
        |                         |                        |
        |<------- Data relayed through relay node -------->|
```

### Example 5: Performance Monitoring

```python
import trio
import time
from libp2p import new_host

BENCHMARK_PROTOCOL = "/benchmark/1.0.0"

async def benchmark_handler(stream):
    """Echo back received data for benchmarking"""
    total_bytes = 0
    start_time = time.time()
    
    while True:
        data = await stream.read()
        if not data:
            break
        await stream.write(data)
        total_bytes += len(data)
    
    duration = time.time() - start_time
    throughput = total_bytes / duration / 1024 / 1024  # MB/s
    
    print(f"Benchmark complete:")
    print(f"  Total: {total_bytes / 1024 / 1024:.2f} MB")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Throughput: {throughput:.2f} MB/s")
    
    await stream.close()

async def run_benchmark(host, peer_id, size_mb=100, chunk_size=8192):
    """Send data and measure throughput"""
    stream = await host.new_stream(peer_id, [BENCHMARK_PROTOCOL])
    
    total_bytes = size_mb * 1024 * 1024
    data_chunk = b'x' * chunk_size
    
    print(f"Sending {size_mb} MB of data...")
    start_time = time.time()
    
    sent = 0
    while sent < total_bytes:
        to_send = min(chunk_size, total_bytes - sent)
        await stream.write(data_chunk[:to_send])
        sent += to_send
    
    # Close write side to signal completion
    await stream.close()
    
    # Calculate throughput
    duration = time.time() - start_time
    throughput = size_mb / duration
    
    print(f"Benchmark results:")
    print(f"  Sent: {size_mb} MB")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Throughput: {throughput:.2f} MB/s")
    print(f"  Latency: {duration/sent*1000:.2f} ms per message")
```

**What this measures:**
- **TCP performance**: Baseline connection speed
- **Noise overhead**: Encryption/decryption cost
- **Yamux overhead**: Multiplexing frame overhead
- **Application throughput**: End-to-end performance

---

## 9. Advanced Topics

### Connection Pooling

libp2p maintains a **connection pool** to reuse connections:

```python
# When you dial the same peer multiple times:
stream1 = await host.new_stream(peer_id, ["/chat/1.0.0"])
stream2 = await host.new_stream(peer_id, ["/dht/1.0.0"])

# Both streams use the SAME underlying TCP connection!
# This saves time and resources.
```

**Benefits:**
- No repeated TCP handshakes
- No repeated Noise handshakes
- Reduced latency for new streams
- Better resource utilization

### Flow Control in Detail

**Problem**: Fast sender overwhelms slow receiver

```
Sender                              Receiver
  |                                    |
  | Send 1 MB/s                        | Can only process 100 KB/s
  |--------------------------------->  | Buffer fills up...
  |--------------------------------->  | Buffer full!
  |--------------------------------->  | Drops data or crashes
```

**Solution**: Yamux flow control

```
Sender (window: 256 KB)               Receiver
  |                                    |
  | Send 100 KB                        |
  |--------------------------------->  | Process 100 KB
  | (window: 156 KB remaining)         |
  |                                    |
  | Send 156 KB                        |
  |--------------------------------->  | Process 156 KB
  | (window: 0 KB - BLOCKED)           |
  |                                    |
  | Wait...                            | Send window update: +200 KB
  |<-----------------------------------|
  | (window: 200 KB - can send!)       |
```

### Security Considerations

**What Noise Protects Against:**
1. ✅ **Eavesdropping**: Nobody can read your messages
2. ✅ **Tampering**: Nobody can modify messages
3. ✅ **Impersonation**: Peers prove their identity
4. ✅ **Replay attacks**: Old messages can't be replayed

**What Noise Doesn't Protect Against:**
1. ❌ **Traffic analysis**: Attackers can see connection patterns
2. ❌ **Denial of Service**: Attackers can still flood connections
3. ❌ **Application-layer attacks**: Your protocol must be secure

**Best Practices:**
```python
# Always validate peer IDs
expected_peer = "QmExpectedPeerID..."
stream = await host.new_stream(expected_peer, [PROTOCOL])

# Use timeouts
async with trio.move_on_after(30):  # 30 second timeout
    data = await stream.read()

# Limit message sizes
MAX_MESSAGE_SIZE = 1024 * 1024  # 1 MB
data = await stream.read(MAX_MESSAGE_SIZE)
if len(data) > MAX_MESSAGE_SIZE:
    raise ValueError("Message too large")

# Validate application data
import json
try:
    message = json.loads(data)
    # Validate message structure
except json.JSONDecodeError:
    # Handle invalid data
    pass
```

### Debugging Tips

**Enable Debug Logging:**
```python
import logging

# Enable libp2p debug logs
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("libp2p")
logger.setLevel(logging.DEBUG)
```

**Common Issues:**

1. **Connection Refused**
   - Check if listener is running
   - Verify IP address and port
   - Check firewall settings

2. **Noise Handshake Failed**
   - Mismatched libp2p versions
   - Wrong peer ID in multiaddress
   - Network corruption

3. **Stream Closed Unexpectedly**
   - Peer crashed or disconnected
   - Protocol mismatch
   - Timeout exceeded

4. **Slow Performance**
   - Check network bandwidth
   - Monitor CPU usage (encryption is CPU-intensive)
   - Look for flow control issues (windows too small)

**Inspecting Connection State:**
```python
# Get all connections
connections = host.get_network().connections

for conn in connections:
    print(f"Peer: {conn.peer_id}")
    print(f"Streams: {len(conn.streams)}")
    print(f"Local addr: {conn.local_addr}")
    print(f"Remote addr: {conn.remote_addr}")
```

---

## 10. Summary: The Complete Picture

Let's recap the entire journey from creating a host to exchanging messages:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. HOST CREATION                                            │
│    - Generate cryptographic identity (key pair)             │
│    - Create network manager                                 │
│    - Register transports (TCP, QUIC, etc.)                  │
│    - Register security protocols (Noise)                    │
│    - Register multiplexers (Yamux)                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. START LISTENING                                          │
│    - TCP transport creates socket                           │
│    - Bind to IP:Port (e.g., 0.0.0.0:8000)                  │
│    - Listen for incoming connections                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. PEER DIALS (Outgoing Connection)                        │
│    - Parse multiaddress to extract IP and port              │
│    - TCP.dial() creates TCP socket                          │
│    - TCP 3-way handshake (SYN, SYN-ACK, ACK)               │
│    - Raw TCP connection established                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. SECURITY UPGRADE (Noise Handshake)                      │
│    - Multistream negotiation: agree on /noise               │
│    - Message 1: Initiator sends ephemeral key               │
│    - Message 2: Responder sends ephemeral + static keys     │
│    - Message 3: Initiator sends static key                  │
│    - Both peers verify identities                           │
│    - Encrypted connection established                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. MULTIPLEXER UPGRADE (Yamux)                             │
│    - Multistream negotiation: agree on /yamux/1.0.0         │
│    - Yamux session established                              │
│    - Can now open multiple streams                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. OPEN STREAM                                              │
│    - Send Yamux SYN frame with new stream ID                │
│    - Negotiate application protocol (e.g., /chat/1.0.0)     │
│    - Stream ready for application data                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. SEND/RECEIVE APPLICATION DATA                            │
│    Application: stream.write(b"Hello")                      │
│         ↓                                                    │
│    Stream: Add protocol framing                             │
│         ↓                                                    │
│    Yamux: Wrap with stream ID header                        │
│         ↓                                                    │
│    Noise: Encrypt the frame                                 │
│         ↓                                                    │
│    TCP: Send encrypted bytes                                │
│         ↓                                                    │
│    [NETWORK]                                                │
│         ↓                                                    │
│    TCP: Receive bytes                                       │
│         ↓                                                    │
│    Noise: Decrypt                                           │
│         ↓                                                    │
│    Yamux: Extract stream data                               │
│         ↓                                                    │
│    Stream: Deliver to application                           │
│         ↓                                                    │
│    Application: stream.read() → b"Hello"                    │
└─────────────────────────────────────────────────────────────┘
```

### Key Takeaways

1. **TCP** provides the reliable, ordered byte stream foundation
2. **Noise** adds encryption and authentication
3. **Yamux** enables multiple logical streams over one connection
4. **Protocols** define application-specific message formats
5. **libp2p** handles all the complexity, letting you focus on your application

### Why This Design?

**Modularity**: Each layer has a clear purpose
- Want better security? Swap Noise for TLS
- Want better multiplexing? Swap Yamux for QUIC
- Your application doesn't change!

**Efficiency**: Resources are used wisely
- One TCP connection serves many streams
- Connection pooling reduces overhead
- Flow control prevents resource exhaustion

**Flexibility**: Works in many environments
- Can run over TCP, QUIC, WebSocket, Bluetooth, etc.
- NAT traversal through relays
- Works peer-to-peer or client-server

---

## 11. Further Reading

**Official Documentation:**
- [libp2p Specifications](https://github.com/libp2p/specs)
- [py-libp2p GitHub](https://github.com/libp2p/py-libp2p)
- [Noise Protocol Framework](https://noiseprotocol.org/)
- [Yamux Specification](https://github.com/hashicorp/yamux/blob/master/spec.md)

**Related Concepts:**
- **QUIC**: Modern transport combining TCP + TLS + multiplexing
- **WebRTC**: Browser-based peer-to-peer communication
- **Kademlia DHT**: Distributed hash table routing
- **GossipSub**: Efficient pub/sub for large networks

**Next Steps:**
1. Build a simple chat application
2. Experiment with different transports (QUIC, WebSocket)
3. Implement a custom protocol
4. Deploy nodes across the internet
5. Integrate with existing libp2p networks (IPFS, Filecoin, Ethereum 2.0)

---

## Appendix: Quick Reference

### Common Multiaddress Formats
```
TCP:      /ip4/127.0.0.1/tcp/8000
QUIC:     /ip4/127.0.0.1/udp/9000/quic
WebSocket: /ip4/127.0.0.1/tcp/8080/ws
With Peer: /ip4/127.0.0.1/tcp/8000/p2p/QmPeerID...
IPv6:     /ip6/::1/tcp/8000
DNS:      /dns4/example.com/tcp/8000
```

### Protocol IDs by Category
```
Transport:     /tcp, /quic, /ws
Security:      /noise, /tls/1.0.0
Multiplexing:  /yamux/1.0.0, /mplex/6.7.0
Protocols:     /ipfs/id/1.0.0, /ipfs/bitswap/1.2.0
Custom:        /your-app/your-protocol/1.0.0
```

### Typical Connection Timeline
```
0ms:    TCP dial begins
10ms:   TCP connection established
20ms:   Noise handshake message 1
30ms:   Noise handshake message 2
40ms:   Noise handshake message 3
50ms:   Yamux negotiation
60ms:   Stream open + protocol negotiation
70ms:   Application data flowing
```

This guide should give you a solid foundation for understanding TCP in py-libp2p and how all the pieces fit together!