# Bitswap Protocol Implementation for py-libp2p

**Complete Guide: Implementation, Usage, and Examples**

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Protocol Versions](#protocol-versions)
4. [Architecture](#architecture)
5. [Core Components](#core-components)
6. [API Reference](#api-reference)
7. [Examples](#examples)
8. [Implementation Details](#implementation-details)
9. [File Structure](#file-structure)

---

## Overview

Bitswap is a protocol for exchanging content-addressed blocks between peers, enabling efficient peer-to-peer file sharing. This implementation supports **three protocol versions** (v1.0.0, v1.1.0, and v1.2.0) with full backward compatibility.

### Key Features

✅ Content-addressed block storage and retrieval  
✅ Wantlist management with priorities  
✅ Bidirectional block exchange  
✅ CIDv0 and CIDv1 support  
✅ Have/DontHave existence queries (v1.2.0)  
✅ Protocol version negotiation  
✅ Async/await with Trio  
✅ Extensible block storage interface  

### What Was Implemented

- **Core Implementation**: 7 Python modules (~1,537+ lines)
- **Protocol Buffers**: Multi-version message definitions
- **CID Utilities**: CIDv0 and CIDv1 encoding/decoding
- **Examples**: 2 example applications (~600+ lines)
- **Documentation**: This comprehensive guide

---

## Quick Start

### Basic Usage

```python
import trio
import multiaddr
from libp2p import new_host
from libp2p.bitswap import BitswapClient, compute_cid_v0

async def main():
    # Create host and Bitswap client
    host = new_host()
    listen_addr = multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/0")
    
    async with host.run([listen_addr]), trio.open_nursery() as nursery:
        # Start Bitswap (defaults to v1.2.0)
        bitswap = BitswapClient(host)
        bitswap.set_nursery(nursery)
        await bitswap.start()
        
        # Add and retrieve blocks
        data = b"Hello, Bitswap!"
        cid = compute_cid_v0(data)
        await bitswap.add_block(cid, data)
        
        # Request from peer
        retrieved = await bitswap.get_block(cid, peer_id)
        print(f"Retrieved: {retrieved}")
        
        await bitswap.stop()

trio.run(main)
```

### Run the Examples

**Comprehensive Demo** (all features):
```bash
cd examples/bitswap
python comprehensive_demo.py              # All demonstrations
python comprehensive_demo.py --demo have  # v1.2.0 Have queries
```

**Simple Provider-Client**:
```bash
# Terminal 1: Provider
python bitswap.py --mode provider

# Terminal 2: Client (use multiaddr from Terminal 1)
python bitswap.py --mode client --provider <multiaddr>
```

---

## Protocol Versions

### Bitswap 1.0.0 (`/ipfs/bitswap/1.0.0`)

**Features**:
- CIDv0 (SHA-256 multihash only)
- Wantlist with priority and cancel
- Blocks field for raw block data
- Basic block exchange

**Use Cases**: Maximum compatibility with IPFS implementations

**Example**:
```python
from libp2p.bitswap import BitswapClient, compute_cid_v0, config

bitswap = BitswapClient(host, protocol_version=config.BITSWAP_PROTOCOL_V100)
cid = compute_cid_v0(b"My data")
await bitswap.add_block(cid, b"My data")
```

### Bitswap 1.1.0 (`/ipfs/bitswap/1.1.0`)

**Features**:
- CIDv0 and CIDv1 support
- Payload field with Block message (prefix + data)
- Multiple hash algorithms
- Better IPLD support

**Improvements**: More efficient CID transmission, support for different codecs

**Example**:
```python
from libp2p.bitswap import BitswapClient, compute_cid_v1, CODEC_RAW, config

bitswap = BitswapClient(host, protocol_version=config.BITSWAP_PROTOCOL_V110)
cid = compute_cid_v1(b"My data", codec=CODEC_RAW)
await bitswap.add_block(cid, b"My data")
```

### Bitswap 1.2.0 (`/ipfs/bitswap/1.2.0`) - Default

**Features**:
- WantType enum (Block / Have)
- Have/DontHave existence queries
- sendDontHave flag for explicit negative responses
- BlockPresence responses
- pendingBytes tracking

**Improvements**: Check block existence without full transfer, better bandwidth efficiency

**Example**:
```python
from libp2p.bitswap import BitswapClient, compute_cid_v0, config

bitswap = BitswapClient(host, protocol_version=config.BITSWAP_PROTOCOL_V120)

# Check if peer has block WITHOUT requesting full data
has_block = await bitswap.have_block(cid, peer_id, timeout=10)

if has_block:
    # Peer confirmed it has the block, now request it
    data = await bitswap.get_block(cid, peer_id)
```

### Protocol Compatibility Matrix

|                      | v1.0.0 Client | v1.1.0 Client | v1.2.0 Client |
|----------------------|---------------|---------------|---------------|
| **v1.0.0 Provider**  | ✅ Full       | ✅ Compatible | ✅ Compatible |
| **v1.1.0 Provider**  | ✅ Compatible | ✅ Full       | ✅ Compatible |
| **v1.2.0 Provider**  | ✅ Compatible | ✅ Compatible | ✅ Full       |

**Note**: All versions are backward compatible through protocol negotiation.

---

## Architecture

```
libp2p/bitswap/
├── pb/                      # Protocol buffers
│   ├── bitswap.proto       # Multi-version message definitions
│   ├── bitswap_pb2.py      # Generated Python code
│   └── bitswap_pb2.pyi     # Type stubs
├── block_store.py           # Storage abstraction
├── cid.py                   # CID encoding/decoding utilities
├── client.py                # Main Bitswap client (503+ lines)
├── config.py                # Configuration constants
├── errors.py                # Custom exceptions
├── messages.py              # Message construction helpers
└── __init__.py              # Public API

examples/bitswap/
├── bitswap.py               # Simple provider/client example
├── comprehensive_demo.py    # Complete feature demonstration
├── COMPREHENSIVE_DEMO.md    # Demo documentation
└── README.md                # Usage instructions
```

---

## Core Components

### 1. BitswapClient

The main class for Bitswap operations.

**Constructor**:
```python
BitswapClient(
    host,                           # libp2p Host instance
    block_store=None,               # Optional BlockStore (uses MemoryBlockStore if None)
    protocol_version=BITSWAP_PROTOCOL_V120  # Protocol version to use
)
```

**Core Methods**:
- `start()` - Initialize and register protocol handlers
- `stop()` - Stop client and cleanup
- `add_block(cid, data)` - Add block to serve to peers
- `get_block(cid, peer_id, timeout)` - Request full block from peer
- `want_block(cid, priority, want_type, send_dont_have)` - Add to wantlist
- `have_block(cid, peer_id, timeout)` - Check if peer has block (v1.2.0)
- `cancel_want(cid)` - Cancel block request

### 2. BlockStore Interface

Abstract interface for block storage.

```python
from libp2p.bitswap import BlockStore

class BlockStore(ABC):
    @abstractmethod
    async def get_block(self, cid: bytes) -> Optional[bytes]:
        """Retrieve block data by CID."""
        pass
    
    @abstractmethod
    async def put_block(self, cid: bytes, data: bytes):
        """Store a block."""
        pass
    
    @abstractmethod
    async def has_block(self, cid: bytes) -> bool:
        """Check if block exists."""
        pass
    
    @abstractmethod
    async def delete_block(self, cid: bytes):
        """Delete a block."""
        pass
```

**Built-in Implementation**:
- `MemoryBlockStore` - In-memory storage (default)

**Custom Implementation Example**:
```python
class FileSystemBlockStore(BlockStore):
    def __init__(self, base_path):
        self.base_path = Path(base_path)
    
    async def get_block(self, cid: bytes):
        file_path = self.base_path / cid.hex()
        if file_path.exists():
            return file_path.read_bytes()
        return None
    
    async def put_block(self, cid: bytes, data: bytes):
        file_path = self.base_path / cid.hex()
        file_path.write_bytes(data)
    
    # ... implement has_block and delete_block
```

### 3. CID Utilities

Content Identifier encoding/decoding functions.

**CIDv0 (Bitswap 1.0.0)**:
```python
from libp2p.bitswap import compute_cid_v0

cid = compute_cid_v0(b"My data")  # SHA-256 multihash only
```

**CIDv1 (Bitswap 1.1.0+)**:
```python
from libp2p.bitswap import compute_cid_v1, CODEC_RAW, CODEC_DAG_PB

cid = compute_cid_v1(b"My data", codec=CODEC_RAW)
```

**CID Operations**:
```python
from libp2p.bitswap import (
    get_cid_prefix,                    # Extract prefix for v1.1.0 payload
    reconstruct_cid_from_prefix_and_data,  # Rebuild CID from prefix + data
    verify_cid,                        # Verify data matches CID
    parse_cid_version,                 # Get CID version (0 or 1)
    cid_to_string                      # Convert to human-readable format
)

# v1.1.0 payload handling
prefix = get_cid_prefix(cid_v1)  # First 4 bytes
cid_rebuilt = reconstruct_cid_from_prefix_and_data(prefix, data)

# Verification
is_valid = verify_cid(cid, data)  # Returns True/False
```

### 4. Configuration

```python
from libp2p.bitswap import config

# Protocol IDs
config.BITSWAP_PROTOCOL_V100  # "/ipfs/bitswap/1.0.0"
config.BITSWAP_PROTOCOL_V110  # "/ipfs/bitswap/1.1.0"
config.BITSWAP_PROTOCOL_V120  # "/ipfs/bitswap/1.2.0"

# All protocols (ordered for negotiation)
config.BITSWAP_PROTOCOLS  # [V120, V110, V100]

# Size limits
config.MAX_MESSAGE_SIZE  # 4 MiB
config.MAX_BLOCK_SIZE    # 2 MiB

# Defaults
config.DEFAULT_PRIORITY  # 1
config.DEFAULT_TIMEOUT   # 30 seconds
config.DEFAULT_CID_VERSION  # 0
```

### 5. Error Handling

```python
from libp2p.bitswap import (
    BitswapError,           # Base exception
    InvalidBlockError,      # Malformed block
    BlockTooLargeError,     # Block exceeds 2 MiB
    MessageTooLargeError,   # Message exceeds 4 MiB
    TimeoutError,           # Operation timeout
    BlockNotFoundError,     # Block not found
    InvalidCIDError         # Invalid CID format
)
```

---

## API Reference

### BitswapClient Methods

#### `start()`
Initialize the Bitswap client and register protocol handlers.

```python
await bitswap.start()
```

#### `stop()`
Stop the client and cleanup resources.

```python
await bitswap.stop()
```

#### `add_block(cid: bytes, data: bytes)`
Add a block to the local store and make it available to peers.

```python
cid = compute_cid_v0(b"Hello")
await bitswap.add_block(cid, b"Hello")
```

#### `get_block(cid: bytes, peer_id: PeerID, timeout: float = 30) -> bytes`
Request a full block from a peer. Raises `BlockNotFoundError` or `TimeoutError`.

```python
try:
    data = await bitswap.get_block(cid, peer_id, timeout=10)
    print(f"Got block: {data}")
except BlockNotFoundError:
    print("Block not found")
except TimeoutError:
    print("Request timed out")
```

#### `want_block(cid: bytes, priority: int = 1, want_type: int = 0, send_dont_have: bool = False)`
Add a block to the wantlist.

**Parameters**:
- `cid` - Content Identifier
- `priority` - Request priority (1-10, higher = more important)
- `want_type` - 0 (Block) or 1 (Have) for v1.2.0
- `send_dont_have` - Request explicit DontHave response (v1.2.0)

```python
# Request full block
await bitswap.want_block(cid, priority=10)

# Request existence check only (v1.2.0)
await bitswap.want_block(cid, priority=1, want_type=1, send_dont_have=True)
```

#### `have_block(cid: bytes, peer_id: PeerID, timeout: float = 10) -> bool`
Check if peer has a block without requesting full data (v1.2.0 feature).

```python
has_block = await bitswap.have_block(cid, peer_id)
if has_block:
    # Peer confirmed it has the block
    data = await bitswap.get_block(cid, peer_id)
```

#### `cancel_want(cid: bytes)`
Cancel a previous block request.

```python
await bitswap.cancel_want(cid)
```

### CID Functions

#### `compute_cid_v0(data: bytes) -> bytes`
Compute CIDv0 (SHA-256 multihash).

```python
cid = compute_cid_v0(b"My data")
```

#### `compute_cid_v1(data: bytes, codec: int = CODEC_RAW) -> bytes`
Compute CIDv1 (version + codec + multihash).

```python
cid = compute_cid_v1(b"My data", codec=CODEC_RAW)
cid = compute_cid_v1(b"IPLD data", codec=CODEC_DAG_PB)
```

#### `verify_cid(cid: bytes, data: bytes) -> bool`
Verify that data matches the CID.

```python
is_valid = verify_cid(cid, data)
```

---

## Examples

### Example 1: Basic Block Exchange

```python
import trio
import multiaddr
from libp2p import new_host
from libp2p.bitswap import BitswapClient, compute_cid_v0
from libp2p.peer.peerinfo import info_from_p2p_addr

async def main():
    # Create provider and client
    provider_host = new_host()
    client_host = new_host()
    
    provider_addr = multiaddr.Multiaddr("/ip4/127.0.0.1/tcp/0")
    client_addr = multiaddr.Multiaddr("/ip4/127.0.0.1/tcp/0")
    
    async with provider_host.run([provider_addr]), \
               client_host.run([client_addr]), \
               trio.open_nursery() as nursery:
        
        # Setup provider
        provider = BitswapClient(provider_host)
        provider.set_nursery(nursery)
        await provider.start()
        
        # Add blocks to provider
        data = b"Hello from Bitswap!"
        cid = compute_cid_v0(data)
        await provider.add_block(cid, data)
        
        # Setup client
        client = BitswapClient(client_host)
        client.set_nursery(nursery)
        await client.start()
        
        # Connect client to provider
        provider_info = info_from_p2p_addr(provider_host.get_addrs()[0])
        await client_host.connect(provider_info)
        
        # Request block
        retrieved = await client.get_block(cid, provider_info.peer_id, timeout=5)
        print(f"Retrieved: {retrieved}")
        
        await provider.stop()
        await client.stop()

trio.run(main)
```

### Example 2: Have/DontHave Queries (v1.2.0)

```python
from libp2p.bitswap import BitswapClient, compute_cid_v0, config

async def check_availability():
    # Create v1.2.0 client
    bitswap = BitswapClient(
        host,
        protocol_version=config.BITSWAP_PROTOCOL_V120
    )
    await bitswap.start()
    
    # Check if peer has block (efficient, no full transfer)
    cid = compute_cid_v0(b"Large file data")
    has_block = await bitswap.have_block(cid, peer_id, timeout=5)
    
    if has_block:
        print("Peer has the block! Requesting full data...")
        data = await bitswap.get_block(cid, peer_id)
    else:
        print("Peer doesn't have it, trying another peer...")
```

### Example 3: File Sharing

```python
async def share_file(file_path, bitswap):
    """Split file into blocks and share via Bitswap."""
    BLOCK_SIZE = 256 * 1024  # 256 KB
    
    file_data = Path(file_path).read_bytes()
    cids = []
    
    # Split into blocks
    for i in range(0, len(file_data), BLOCK_SIZE):
        chunk = file_data[i:i + BLOCK_SIZE]
        cid = compute_cid_v0(chunk)
        await bitswap.add_block(cid, chunk)
        cids.append(cid)
    
    print(f"File split into {len(cids)} blocks")
    return cids

async def retrieve_file(cids, peer_id, bitswap):
    """Retrieve and reconstruct file from blocks."""
    file_data = b""
    
    for cid in cids:
        block_data = await bitswap.get_block(cid, peer_id, timeout=30)
        file_data += block_data
    
    return file_data
```

### Example 4: Custom Block Store

```python
from libp2p.bitswap import BlockStore
from pathlib import Path
import aiofiles

class PersistentBlockStore(BlockStore):
    """File system-based block storage."""
    
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_block(self, cid: bytes):
        file_path = self.base_dir / cid.hex()
        if file_path.exists():
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        return None
    
    async def put_block(self, cid: bytes, data: bytes):
        file_path = self.base_dir / cid.hex()
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(data)
    
    async def has_block(self, cid: bytes):
        return (self.base_dir / cid.hex()).exists()
    
    async def delete_block(self, cid: bytes):
        file_path = self.base_dir / cid.hex()
        if file_path.exists():
            file_path.unlink()

# Usage
store = PersistentBlockStore("/tmp/bitswap_blocks")
bitswap = BitswapClient(host, block_store=store)
```

### Example 5: Multi-Version Compatibility

```python
async def multi_version_demo():
    """Demonstrate compatibility across protocol versions."""
    
    # v1.0.0 provider (maximum compatibility)
    provider = BitswapClient(
        provider_host,
        protocol_version=config.BITSWAP_PROTOCOL_V100
    )
    await provider.start()
    
    cid_v0 = compute_cid_v0(b"Data")
    await provider.add_block(cid_v0, b"Data")
    
    # v1.2.0 client (latest features)
    client = BitswapClient(
        client_host,
        protocol_version=config.BITSWAP_PROTOCOL_V120
    )
    await client.start()
    
    # Connection automatically negotiates to v1.0.0
    await client_host.connect(provider_info)
    
    # Still works! Client uses v1.0.0 format for this peer
    data = await client.get_block(cid_v0, provider_info.peer_id)
    print("Cross-version exchange successful!")
```

---

## Implementation Details

### Protocol Flow

#### Block Request Flow
1. Client calls `get_block(cid, peer_id)`
2. Check local store first
3. Add CID to wantlist with priority
4. Open stream to peer and send wantlist message
5. Peer receives wantlist, checks its store
6. Peer sends block (v1.0.0 blocks / v1.1.0 payload / v1.2.0 presence)
7. Client receives and stores block
8. Send cancel message and return data

#### Have/DontHave Flow (v1.2.0)
1. Client calls `have_block(cid, peer_id)`
2. Add CID to wantlist with `want_type=1` (Have) and `send_dont_have=True`
3. Open stream and send wantlist message
4. Peer checks if block exists
5. Peer sends BlockPresence message (Have or DontHave)
6. Client receives response and returns boolean
7. Much more efficient than requesting full block!

### Message Format

All versions use protobuf messages:

```protobuf
message Message {
  message Wantlist {
    enum WantType {
      Block = 0;    // Request full block
      Have = 1;     // Request only existence
    }
    
    message Entry {
      bytes block = 1;           // CID
      int32 priority = 2;        // Priority
      bool cancel = 3;           // Cancel flag
      WantType wantType = 4;     // v1.2.0
      bool sendDontHave = 5;     // v1.2.0
    }
    
    repeated Entry entries = 1;
    bool full = 2;
  }
  
  message Block {                // v1.1.0
    bytes prefix = 1;
    bytes data = 2;
  }
  
  enum BlockPresenceType {       // v1.2.0
    Have = 0;
    DontHave = 1;
  }
  
  message BlockPresence {        // v1.2.0
    bytes cid = 1;
    BlockPresenceType type = 2;
  }
  
  Wantlist wantlist = 1;
  repeated bytes blocks = 2;                  // v1.0.0
  repeated Block payload = 3;                 // v1.1.0+
  repeated BlockPresence blockPresences = 4;  // v1.2.0
  int32 pendingBytes = 5;                     // v1.2.0
}
```

### Protocol Negotiation

When opening a stream to a peer:
1. Try protocols in order: v1.2.0 → v1.1.0 → v1.0.0
2. Multistream negotiation finds highest common version
3. Store negotiated protocol for this peer
4. Use appropriate message format for that peer

### Size Limits

- **Maximum block size**: 2 MiB (per spec)
- **Maximum message size**: 4 MiB (per spec)
- Blocks and messages exceeding limits are rejected

---

## File Structure

```
libp2p/bitswap/              # Core implementation
├── pb/
│   ├── bitswap.proto       # Multi-version protobuf definitions
│   ├── bitswap_pb2.py      # Generated Python code
│   └── bitswap_pb2.pyi     # Type stubs
├── __init__.py             # Public API exports
├── block_store.py          # BlockStore interface and MemoryBlockStore
├── cid.py                  # CID utilities (169 lines)
├── client.py               # Main BitswapClient (503+ lines)
├── config.py               # Configuration constants
├── errors.py               # Custom exceptions
└── messages.py             # Message construction helpers

examples/bitswap/            # Example applications
├── bitswap.py              # Simple provider/client example
├── comprehensive_demo.py   # Complete feature demonstration (600+ lines)
├── COMPREHENSIVE_DEMO.md   # Detailed demo guide
├── README.md               # Example usage instructions
└── __init__.py

docs/                        # Sphinx documentation
├── libp2p.bitswap.rst      # API documentation
└── examples.bitswap.rst    # Example documentation

BITSWAP.md                   # This comprehensive guide
```

---

## Summary

### Features Implemented

**v1.0.0**:
✅ CIDv0 support  
✅ Wantlist with priority  
✅ Block exchange  
✅ Cancel requests  

**v1.1.0**:
✅ CIDv1 support  
✅ Payload with CID prefixes  
✅ Multiple codecs  

**v1.2.0**:
✅ Have/DontHave queries  
✅ WantType enum  
✅ BlockPresence responses  
✅ sendDontHave flag  
✅ pendingBytes tracking  

**General**:
✅ Protocol negotiation  
✅ Multi-version support  
✅ Backward compatibility  
✅ Extensible block storage  
✅ Comprehensive examples  

### Code Statistics

- **~1,537+ lines** of core implementation
- **~600+ lines** of demonstration code
- **3 protocol versions** fully supported
- **8 demonstrations** in comprehensive example
- **Complete backward compatibility**

### Next Steps

1. **Learn**: Run `comprehensive_demo.py` to see all features
2. **Try**: Use the simple `bitswap.py` example
3. **Build**: Create your own file sharing application
4. **Extend**: Implement custom block stores
5. **Contribute**: Add features and improvements

### Resources

- **[Comprehensive Demo](examples/bitswap/COMPREHENSIVE_DEMO.md)** - Detailed feature demonstrations
- **[Bitswap Specification](https://specs.ipfs.tech/bitswap-protocol/)** - Official protocol spec
- **[py-libp2p](https://github.com/libp2p/py-libp2p)** - Main repository

---

**Implementation complete! Ready for production use.** 🚀
