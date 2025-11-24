# py-cid: Comprehensive Repository Guide

## Table of Contents
1. [Overview](#overview)
2. [What is CID?](#what-is-cid)
3. [Repository Structure](#repository-structure)
4. [Core Concepts](#core-concepts)
5. [Installation & Setup](#installation--setup)
6. [Module Architecture](#module-architecture)
7. [Key Classes and Methods](#key-classes-and-methods)
8. [CID Versions](#cid-versions)
9. [Usage Examples](#usage-examples)
10. [Testing](#testing)
11. [Contributing Guidelines](#contributing-guidelines)
12. [Advanced Features](#advanced-features)

---

## Overview

**Repository**: [ipld/py-cid](https://github.com/ipld/py-cid)  
**Language**: Python  
**License**: MIT  
**Status**: Stable  
**Python Version**: 3.10-3.14  
**Documentation**: https://py-cid.readthedocs.io

### Purpose
`py-cid` is the Python implementation of the CID (Content Identifier) specification. It provides a self-describing, content-addressed identifier format used as the core addressing mechanism for IPFS, IPLD, libp2p, and Filecoin.

### Key Features
- ✅ Full CIDv0 and CIDv1 support
- ✅ Multiple encoding formats (base58, base32, base64, etc.)
- ✅ Content addressing with cryptographic hashing
- ✅ Self-describing format with multicodec and multihash
- ✅ Conversion between CID versions
- ✅ Type-safe with full type hints

---

## What is CID?

### The Problem: Location Addressing

Traditional web uses **location addressing**:
- `https://example.com/image.jpg` - Points to WHERE content is stored
- Content at that URL can change over time
- Centralized control
- Broken links when servers go down

### The Solution: Content Addressing

CID uses **content addressing**:
- Identifier derived from content itself
- Same content = same CID (content integrity)
- Decentralized - content can be anywhere
- Verifiable - can prove content matches CID

```python
# Traditional URL
https://example.com/document.pdf  # Can change or disappear

# CID
QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4  # Forever identifies that content
```

### CID Anatomy

A CID is composed of multiple parts:

```
QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4
└─────────────────┬─────────────────────────┘
                  │
         Base58-encoded multihash
         (CIDv0 format)

zdj7WhuEjrB52m1BisYCtmjH1hSKa7yZ3jEZ9JcXaFRD51wVz
└┬┘└─────────────────┬─────────────────────────┘
 │                   │
 │                   └─ Version + Codec + Multihash (base32-encoded)
 │
 └─ Multibase prefix ('z' = base58btc)
         (CIDv1 format)
```

**Components**:
1. **Multibase prefix**: Specifies the encoding (CIDv1 only)
2. **CID version**: 0 or 1
3. **Multicodec**: Content type (dag-pb, raw, dag-cbor, etc.)
4. **Multihash**: Hash algorithm + hash value

### Why CID?

**Benefits**:
- **Content Integrity**: Tampering changes the CID
- **Deduplication**: Same content = same CID across the network
- **Permanent Addressing**: CID doesn't break if server moves
- **Verifiable**: Can cryptographically verify content matches CID
- **Self-Describing**: CID contains metadata about itself
- **Future-Proof**: Extensible for new hash algorithms and codecs

**Use Cases**:
- IPFS: Primary content identifier
- IPLD: Linking structured data
- Filecoin: Proof of storage
- libp2p: Peer identification and content routing
- Any distributed system needing content addressing

---

## Repository Structure

```
py-cid/
├── cid/                    # Main package directory
│   ├── __init__.py        # Package initialization, exports
│   ├── cid.py             # Core CID classes (CIDv0, CIDv1)
│   ├── base.py            # Base CID abstract class
│   └── version.py         # Version information
├── tests/                 # Test suite
│   ├── __init__.py
│   ├── test_cid.py        # CID functionality tests
│   ├── test_codec.py      # Codec tests
│   ├── test_conversions.py # Version conversion tests
│   └── conftest.py        # Pytest configuration
├── docs/                  # Documentation
│   ├── index.rst
│   ├── usage.rst          # Usage examples
│   ├── api.rst            # API reference
│   └── conf.py            # Sphinx configuration
├── pyproject.toml         # Modern Python project config
├── setup.py               # Package setup (legacy)
├── setup.cfg              # Setup configuration
├── Makefile               # Development automation
├── tox.ini                # Tox testing configuration
├── .github/               # GitHub Actions CI/CD
│   └── workflows/
├── CONTRIBUTING.md        # Contribution guidelines
├── README.md              # Repository documentation
├── LICENSE                # MIT license
└── HISTORY.md             # Changelog

```

---

## Core Concepts

### 1. Content Addressing

Content addressing means the identifier is derived from the content itself using a cryptographic hash function.

```python
Content → Hash Function → Hash → CID

"Hello, IPFS!" → SHA2-256 → [binary hash] → QmWATWQ7fVPP2EFGu71UkfnqhYXDYH566qy47CnJDgvs8u
```

**Key Properties**:
- **Deterministic**: Same content always produces same CID
- **One-way**: Can't reverse CID to get original content
- **Unique**: Different content produces different CID (collision-resistant)
- **Fixed size**: Hash output is fixed length regardless of content size

### 2. Self-Describing Formats (Multiformats)

CID uses several multiformats to be self-describing:

**Multihash**: Self-describing hash
```
<hash-function-code><hash-length><hash-value>
```

**Multicodec**: Self-describing content type
```
<codec-code> identifies how to interpret the content
```

**Multibase**: Self-describing base encoding
```
<base-encoding-prefix><encoded-data>
```

### 3. CID Versions

**CIDv0**:
- Original IPFS format
- Always 46 characters, starts with "Qm"
- Base58btc encoding only
- Always uses dag-pb codec
- Always uses SHA-256 hash

**CIDv1**:
- Modern format (recommended for new projects)
- Fully self-describing with multibase prefix
- Supports multiple encodings (base32, base64, etc.)
- Supports multiple codecs and hash functions
- Variable length

### 4. Codecs

Codecs specify how to interpret the content:

| Code | Name | Description |
|------|------|-------------|
| 0x55 | raw | Raw binary data |
| 0x70 | dag-pb | Protocol Buffers (IPFS UnixFS) |
| 0x71 | dag-cbor | CBOR-encoded IPLD |
| 0x72 | libp2p-key | libp2p public keys |
| 0x78 | git-raw | Raw git object |
| 0x85 | dag-json | JSON-encoded IPLD |

### 5. Hash Functions

Common hash functions used in CIDs:

| Code | Name | Output Size |
|------|------|-------------|
| 0x11 | sha1 | 160 bits (deprecated) |
| 0x12 | sha2-256 | 256 bits (default) |
| 0x13 | sha2-512 | 512 bits |
| 0xb220 | blake2b-256 | 256 bits |
| 0xb240 | blake2s-256 | 256 bits |
| 0x1b | sha3-256 | 256 bits |

---

## Installation & Setup

### Installation

```bash
# From PyPI (recommended)
pip install py-cid

# With development dependencies
pip install py-cid[dev]

# From source (for contributors)
git clone https://github.com/ipld/py-cid.git
cd py-cid
pip install -e ".[dev]"
```

### Dependencies

**Runtime**:
- `py-multibase` (>=1.0.0) - Base encoding/decoding
- `py-multicodec` (>=0.2.0) - Codec identifiers
- `py-multihash` (>=0.2.0) - Multihash support
- `morphys` - Base58 encoding
- `base58` - Additional base58 support

**Development**:
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `mypy` - Type checking
- `black` - Code formatting
- `flake8` - Linting
- `sphinx` - Documentation generation

### Quick Verification

```python
# Verify installation
from cid import make_cid

# Test with a known CIDv0
cid = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')
print(cid)
# CIDv0(version=0, codec=dag-pb, multihash=b"\x12 \xb9M'...")

# Success! py-cid is working
```

---

## Module Architecture

### 1. `cid/__init__.py` - Package Interface

The main entry point that exports public API:

```python
"""
py-cid: Content Identifiers for Python
"""

from cid.cid import CIDv0, CIDv1
from cid.base import BaseCID

# Factory function for creating CID objects
def make_cid(cid_str):
    """
    Create a CID object from a string.
    
    Automatically detects version and creates appropriate CID object.
    
    Args:
        cid_str: CID string (base-encoded)
        
    Returns:
        CIDv0 or CIDv1 object
        
    Raises:
        ValueError: If string is not a valid CID
    """
    # Detect version and create appropriate object
    pass

__all__ = ['make_cid', 'CIDv0', 'CIDv1', 'BaseCID']
__version__ = '0.3.0'
```

### 2. `cid/base.py` - Abstract Base Class

Defines the interface for all CID versions:

```python
from abc import ABC, abstractmethod

class BaseCID(ABC):
    """
    Abstract base class for CID objects.
    
    All CID versions must implement this interface.
    """
    
    @property
    @abstractmethod
    def version(self):
        """CID version (0 or 1)"""
        pass
    
    @property
    @abstractmethod
    def codec(self):
        """Content codec (e.g., 'dag-pb', 'raw')"""
        pass
    
    @property
    @abstractmethod
    def multihash(self):
        """Multihash bytes"""
        pass
    
    @abstractmethod
    def encode(self, encoding=None):
        """Encode CID to string with specified base encoding"""
        pass
    
    @abstractmethod
    def __str__(self):
        """String representation"""
        pass
    
    @abstractmethod
    def __repr__(self):
        """Debug representation"""
        pass
    
    @abstractmethod
    def __eq__(self, other):
        """Equality comparison"""
        pass
    
    @abstractmethod
    def __hash__(self):
        """Hash for use in sets/dicts"""
        pass
```

### 3. `cid/cid.py` - CID Implementations

The core implementations of CIDv0 and CIDv1:

```python
import multibase
import multicodec
import multihash
from cid.base import BaseCID

class CIDv0(BaseCID):
    """
    CID version 0 implementation.
    
    CIDv0 is the original IPFS format:
    - Always base58btc encoded
    - Always uses dag-pb codec
    - Always uses SHA-256 hash
    - Format: base58btc(multihash)
    
    Attributes:
        _multihash: The multihash bytes
    """
    
    def __init__(self, multihash_bytes):
        """
        Initialize CIDv0 from multihash bytes.
        
        Args:
            multihash_bytes: Multihash as bytes
            
        Raises:
            ValueError: If not SHA-256 hash or invalid multihash
        """
        # Validate multihash
        mh = multihash.decode(multihash_bytes)
        if mh['code'] != 0x12:  # SHA-256
            raise ValueError("CIDv0 only supports SHA-256")
        
        self._multihash = multihash_bytes
    
    @property
    def version(self):
        """Always returns 0 for CIDv0"""
        return 0
    
    @property
    def codec(self):
        """Always returns 'dag-pb' for CIDv0"""
        return 'dag-pb'
    
    @property
    def multihash(self):
        """Returns the multihash bytes"""
        return self._multihash
    
    def encode(self, encoding='base58btc'):
        """
        Encode CID as string.
        
        Args:
            encoding: Must be 'base58btc' for CIDv0
            
        Returns:
            Encoded CID string (bytes)
            
        Raises:
            ValueError: If encoding is not base58btc
        """
        if encoding not in (None, 'base58btc'):
            raise ValueError("CIDv0 only supports base58btc encoding")
        
        import base58
        return base58.b58encode(self._multihash)
    
    def to_v1(self):
        """
        Convert to CIDv1.
        
        Returns:
            CIDv1 object with same content
        """
        return CIDv1('dag-pb', self._multihash)
    
    def __str__(self):
        """String representation (base58-encoded)"""
        return self.encode().decode('ascii')
    
    def __repr__(self):
        """Debug representation"""
        hash_preview = self._multihash[:10].hex() + '...' if len(self._multihash) > 10 else self._multihash.hex()
        return f'CIDv0(version={self.version}, codec={self.codec}, multihash=b"{hash_preview}")'
    
    def __eq__(self, other):
        """Equality based on multihash"""
        if not isinstance(other, CIDv0):
            return False
        return self._multihash == other._multihash
    
    def __hash__(self):
        """Hash for use in sets/dicts"""
        return hash(('CIDv0', self._multihash))
    
    @classmethod
    def from_string(cls, cid_str):
        """
        Create CIDv0 from base58 string.
        
        Args:
            cid_str: Base58-encoded CID string
            
        Returns:
            CIDv0 object
        """
        import base58
        multihash_bytes = base58.b58decode(cid_str)
        return cls(multihash_bytes)


class CIDv1(BaseCID):
    """
    CID version 1 implementation.
    
    CIDv1 is the modern, fully self-describing format:
    - Supports multiple base encodings (via multibase)
    - Supports multiple codecs (via multicodec)
    - Supports multiple hash functions (via multihash)
    - Format: multibase(version + multicodec + multihash)
    
    Attributes:
        _codec: The codec string
        _multihash: The multihash bytes
    """
    
    def __init__(self, codec, multihash_bytes):
        """
        Initialize CIDv1.
        
        Args:
            codec: Codec string (e.g., 'dag-pb', 'raw')
            multihash_bytes: Multihash as bytes
            
        Raises:
            ValueError: If codec is invalid or multihash is malformed
        """
        # Validate codec
        try:
            multicodec.get_codec(codec)
        except KeyError:
            raise ValueError(f"Unknown codec: {codec}")
        
        # Validate multihash
        multihash.decode(multihash_bytes)
        
        self._codec = codec
        self._multihash = multihash_bytes
    
    @property
    def version(self):
        """Always returns 1 for CIDv1"""
        return 1
    
    @property
    def codec(self):
        """Returns the codec string"""
        return self._codec
    
    @property
    def multihash(self):
        """Returns the multihash bytes"""
        return self._multihash
    
    def encode(self, encoding='base32'):
        """
        Encode CID as string with specified base encoding.
        
        Args:
            encoding: Base encoding to use (default: base32)
                     Supported: base32, base58btc, base64, etc.
            
        Returns:
            Encoded CID string (bytes)
        """
        # Build CID bytes: version + codec + multihash
        codec_code = multicodec.get_codec(self._codec).code
        cid_bytes = bytes([1]) + codec_code + self._multihash
        
        # Encode with multibase
        return multibase.encode(encoding, cid_bytes)
    
    def to_v0(self):
        """
        Convert to CIDv0 if possible.
        
        Returns:
            CIDv0 object
            
        Raises:
            ValueError: If codec is not dag-pb or hash is not SHA-256
        """
        if self._codec != 'dag-pb':
            raise ValueError("Can only convert dag-pb CIDv1 to CIDv0")
        
        mh = multihash.decode(self._multihash)
        if mh['code'] != 0x12:  # SHA-256
            raise ValueError("Can only convert SHA-256 CIDv1 to CIDv0")
        
        return CIDv0(self._multihash)
    
    def __str__(self):
        """String representation (base32-encoded by default)"""
        return self.encode().decode('ascii')
    
    def __repr__(self):
        """Debug representation"""
        hash_preview = self._multihash[:10].hex() + '...' if len(self._multihash) > 10 else self._multihash.hex()
        return f'CIDv1(version={self.version}, codec={self.codec}, multihash=b"{hash_preview}")'
    
    def __eq__(self, other):
        """Equality based on codec and multihash"""
        if not isinstance(other, CIDv1):
            return False
        return self._codec == other._codec and self._multihash == other._multihash
    
    def __hash__(self):
        """Hash for use in sets/dicts"""
        return hash(('CIDv1', self._codec, self._multihash))
    
    @classmethod
    def from_string(cls, cid_str):
        """
        Create CIDv1 from multibase-encoded string.
        
        Args:
            cid_str: Multibase-encoded CID string
            
        Returns:
            CIDv1 object
        """
        # Decode multibase
        cid_bytes = multibase.decode(cid_str)
        
        # Parse: version + codec + multihash
        if cid_bytes[0] != 1:
            raise ValueError("Not a CIDv1")
        
        codec_code, codec_length = multicodec.read_varint(cid_bytes[1:])
        codec = multicodec.get_codec_by_code(codec_code).name
        multihash_bytes = cid_bytes[1 + codec_length:]
        
        return cls(codec, multihash_bytes)


def make_cid(cid_str):
    """
    Factory function to create CID from string.
    
    Automatically detects CID version and creates appropriate object.
    
    Args:
        cid_str: CID string (any encoding)
        
    Returns:
        CIDv0 or CIDv1 object
        
    Raises:
        ValueError: If not a valid CID
    """
    if isinstance(cid_str, bytes):
        cid_str = cid_str.decode('utf-8')
    
    # CIDv0: 46 chars, starts with 'Qm'
    if len(cid_str) == 46 and cid_str.startswith('Qm'):
        return CIDv0.from_string(cid_str)
    
    # CIDv1: has multibase prefix
    try:
        return CIDv1.from_string(cid_str)
    except Exception:
        pass
    
    # Try as CIDv0 anyway
    try:
        return CIDv0.from_string(cid_str)
    except Exception as e:
        raise ValueError(f"Invalid CID: {cid_str}") from e
```

---

## Key Classes and Methods

### make_cid() - Factory Function

The primary way to create CID objects:

```python
from cid import make_cid

# Works with CIDv0
cid_v0 = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')
print(type(cid_v0))  # <class 'cid.cid.CIDv0'>

# Works with CIDv1 (any encoding)
cid_v1_base32 = make_cid('bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi')
cid_v1_base58 = make_cid('zdj7WhuEjrB52m1BisYCtmjH1hSKa7yZ3jEZ9JcXaFRD51wVz')

# Automatically detects version
print(cid_v1_base32.version)  # 1
```

### CIDv0 Class

#### Properties

```python
# Version (always 0)
cid.version  # 0

# Codec (always 'dag-pb')
cid.codec  # 'dag-pb'

# Multihash bytes
cid.multihash  # b'\x12 ...'
```

#### Methods

```python
# Encoding (always base58btc)
encoded = cid.encode()
# or
encoded = cid.encode('base58btc')

# Convert to CIDv1
cid_v1 = cid.to_v1()

# String representation
str(cid)  # 'QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4'

# Equality
cid1 == cid2  # True if same multihash

# Hashing (for use in sets/dicts)
hash(cid)
```

### CIDv1 Class

#### Properties

```python
# Version (always 1)
cid.version  # 1

# Codec
cid.codec  # 'dag-pb', 'raw', 'dag-cbor', etc.

# Multihash bytes
cid.multihash  # b'\x12 ...'
```

#### Methods

```python
# Encoding with different bases
cid.encode()  # base32 (default)
cid.encode('base58btc')  # base58
cid.encode('base64')  # base64
cid.encode('base16')  # hex

# Convert to CIDv0 (if possible)
try:
    cid_v0 = cid.to_v0()
except ValueError:
    # Can only convert if codec is dag-pb and hash is SHA-256
    pass

# String representation
str(cid)  # base32-encoded by default

# Equality
cid1 == cid2  # True if same codec and multihash
```

---

## CID Versions

### CIDv0 Deep Dive

**Format**:
```
base58btc(SHA-256-multihash)
```

**Characteristics**:
- **Fixed format**: Always base58btc, always dag-pb, always SHA-256
- **Length**: Always 46 characters
- **Prefix**: Always starts with "Qm"
- **Compatibility**: Original IPFS format, widely supported

**Example**:
```python
from cid import CIDv0
import multihash

# Create from multihash
mh = multihash.digest(b'hello world', 'sha2-256')
cid = CIDv0(mh.encode())

print(cid)  # Qm...
print(cid.version)  # 0
print(cid.codec)  # dag-pb
```

**Limitations**:
- Only one codec (dag-pb)
- Only one hash function (SHA-256)
- Only one encoding (base58btc)
- Not fully self-describing

### CIDv1 Deep Dive

**Format**:
```
multibase(CID-version + multicodec + multihash)
```

**Characteristics**:
- **Flexible**: Multiple codecs, hashes, encodings
- **Self-describing**: All metadata included
- **Variable length**: Depends on hash function and encoding
- **Future-proof**: Can add new codecs/hashes

**Example**:
```python
from cid import CIDv1
import multihash

# Create with specific codec
mh = multihash.digest(b'hello world', 'sha2-256')
cid = CIDv1('raw', mh.encode())

print(cid)  # bafk...
print(cid.version)  # 1
print(cid.codec)  # raw

# Encode in different bases
print(cid.encode('base32'))  # bafk...
print(cid.encode('base58btc'))  # z...
print(cid.encode('base64'))  # m...
```

**Advantages**:
- Supports any codec
- Supports any hash function
- Supports any base encoding
- Fully self-describing
- Better for URLs (base32 is case-insensitive)

### Version Conversion

```python
from cid import make_cid

# CIDv0 to CIDv1
v0 = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')
v1 = v0.to_v1()
print(v1)  # bafybei...

# CIDv1 to CIDv0 (only if dag-pb + SHA-256)
v1 = make_cid('bafybeihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku')
v0 = v1.to_v0()
print(v0)  # Qm...

# Attempting invalid conversion
v1_raw = make_cid('bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy')
try:
    v0 = v1_raw.to_v0()
except ValueError as e:
    print(e)  # Can only convert dag-pb CIDv1 to CIDv0
```

---

## Usage Examples

### Basic Usage

```python
from cid import make_cid

# Parse existing CID
cid = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')

# Access properties
print(f"Version: {cid.version}")
print(f"Codec: {cid.codec}")
print(f"Multihash (hex): {cid.multihash.hex()}")

# Get string representation
print(str(cid))
print(cid.encode())
```

### Creating CIDs from Content

```python
import multihash
from cid import CIDv0, CIDv1

# Hash some content
content = b"Hello, IPFS!"
mh = multihash.digest(content, 'sha2-256')

# Create CIDv0
cid_v0 = CIDv0(mh.encode())
print(f"CIDv0: {cid_v0}")

# Create CIDv1 with different codecs
cid_v1_dagpb = CIDv1('dag-pb', mh.encode())
cid_v1_raw = CIDv1('raw', mh.encode())

print(f"CIDv1 (dag-pb): {cid_v1_dagpb}")
print(f"CIDv1 (raw): {cid_v1_raw}")
```

### Working with Different Encodings

```python
from cid import make_cid

# Create CIDv1
cid = make_cid('bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi')

# Encode in different bases
bases = ['base32', 'base58btc', 'base64', 'base16']

for base in bases:
    encoded = cid.encode(base)
    print(f"{base:12s}: {encoded.decode('utf-8')}")

# Output:
# base32      : bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi
# base58btc   : zdj7WhuEjrB52m1BisYCtmjH1hSKa7yZ3jEZ9JcXaFRD51wVz
# base64      : mAXASIJdEMt0 sKQbhYT84eCu4dxdWE8U7vzJFYZdwHYbm9x
# base16      : f01701220... (hex)
```

### Comparing CIDs

```python
from cid import make_cid

cid1 = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')
cid2 = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')
cid3 = make_cid('QmPZ9gcCEpqKTo6aq61g2nXGUhM4iCL3ewB6LDXZCtioEB')

# Equality comparison
print(cid1 == cid2)  # True (same content)
print(cid1 == cid3)  # False (different content)

# Use in sets (requires __hash__)
cid_set = {cid1, cid2, cid3}
print(len(cid_set))  # 2 (cid1 and cid2 are same)

# Use as dict keys
cid_map = {
    cid1: "Document A",
    cid3: "Document B"
}
print(cid_map[cid2])  # "Document A" (cid2 == cid1)
```

### Version Conversion Workflow

```python
from cid import make_cid

# Start with CIDv0
cid_v0 = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')
print(f"Original (v0): {cid_v0}")

# Convert to v1
cid_v1 = cid_v0.to_v1()
print(f"Converted (v1): {cid_v1}")

# Encode v1 in different format for URLs (base32 is case-insensitive)
url_safe = cid_v1.encode('base32').decode('utf-8')
print(f"URL-safe: {url_safe}")

# Convert back to v0
cid_v0_again = cid_v1.to_v0()
print(f"Back to v0: {cid_v0_again}")
assert cid_v0 == cid_v0_again
```

### IPFS Integration Example

```python
"""
Working with IPFS CIDs in practice.
"""
import multihash
from cid import make_cid, CIDv1

class IPFSFile:
    """Represents a file in IPFS"""
    
    def __init__(self, content: bytes):
        self.content = content
        self._cid = None
    
    def calculate_cid(self, version=1, codec='raw'):
        """Calculate CID for file content"""
        # Hash the content
        mh = multihash.digest(self.content, 'sha2-256')
        
        if version == 0:
            from cid import CIDv0
            self._cid = CIDv0(mh.encode())
        else:
            self._cid = CIDv1(codec, mh.encode())
        
        return self._cid
    
    @property
    def cid(self):
        """Get CID (calculate if needed)"""
        if self._cid is None:
            self.calculate_cid()
        return self._cid
    
    def verify_integrity(self, claimed_cid: str) -> bool:
        """Verify content matches claimed CID"""
        actual_cid = self.calculate_cid()
        claimed = make_cid(claimed_cid)
        return actual_cid == claimed

# Usage
file = IPFSFile(b"Hello, IPFS!")
cid = file.calculate_cid(version=1, codec='raw')
print(f"File CID: {cid}")

# Verify integrity
is_valid = file.verify_integrity(str(cid))
print(f"Integrity check: {is_valid}")
```

### Content Deduplication

```python
"""
Using CIDs for deduplication.
"""
from cid import CIDv1
import multihash

class ContentStore:
    """Simple content-addressed storage"""
    
    def __init__(self):
        self.storage = {}  # cid -> content mapping
    
    def add(self, content: bytes, codec='raw') -> str:
        """
        Add content to store.
        Returns CID. If content already exists, returns existing CID.
        """
        # Calculate CID
        mh = multihash.digest(content, 'sha2-256')
        cid = CIDv1(codec, mh.encode())
        cid_str = str(cid)
        
        # Check if already stored (deduplication)
        if cid_str in self.storage:
            print(f"Content already exists: {cid_str}")
            return cid_str
        
        # Store new content
        self.storage[cid_str] = content
        print(f"Stored new content: {cid_str}")
        return cid_str
    
    def get(self, cid_str: str) -> bytes:
        """Retrieve content by CID"""
        return self.storage.get(cid_str)
    
    def verify(self, cid_str: str) -> bool:
        """Verify stored content matches its CID"""
        content = self.get(cid_str)
        if content is None:
            return False
        
        # Recalculate CID from content
        mh = multihash.digest(content, 'sha2-256')
        cid = make_cid(cid_str)
        calculated_cid = CIDv1(cid.codec, mh.encode())
        
        return str(calculated_cid) == cid_str

# Usage
store = ContentStore()

# Add same content multiple times
cid1 = store.add(b"Hello, World!")
cid2 = store.add(b"Hello, World!")  # Deduplication
cid3 = store.add(b"Different content")

assert cid1 == cid2  # Same CID for same content
assert cid1 != cid3  # Different CID for different content

print(f"Total unique items: {len(store.storage)}")  # 2

# Verify integrity
print(f"CID1 valid: {store.verify(cid1)}")
print(f"CID3 valid: {store.verify(cid3)}")
```

### Working with Different Hash Functions

```python
"""
Using different hash algorithms.
"""
import multihash
from cid import CIDv1

content = b"Sample content for hashing"

# Different hash functions
hash_functions = ['sha2-256', 'sha2-512', 'blake2b-256', 'sha3-256']

print("Same content, different hash functions:\n")
for hash_func in hash_functions:
    mh = multihash.digest(content, hash_func)
    cid = CIDv1('raw', mh.encode())
    
    print(f"{hash_func:15s}: {cid}")
    print(f"  Hash size: {len(mh.digest)} bytes")
    print()
```

---

## Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures and configuration
├── test_cid.py              # Core CID functionality tests
├── test_cidv0.py            # CIDv0-specific tests
├── test_cidv1.py            # CIDv1-specific tests
├── test_conversions.py      # Version conversion tests
├── test_encoding.py         # Encoding/decoding tests
└── test_edge_cases.py       # Edge cases and error handling
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cid --cov-report=html

# Run specific test file
pytest tests/test_cid.py

# Run specific test
pytest tests/test_cid.py::test_make_cid_v0

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Run tests for specific Python version
tox -e py310
tox -e py311
tox -e py312
```

### Example Test Cases

```python
# tests/test_cid.py
import pytest
from cid import make_cid, CIDv0, CIDv1
import multihash

class TestMakeCID:
    """Test the make_cid factory function"""
    
    def test_make_cid_v0(self):
        """Test creating CIDv0 from string"""
        cid_str = 'QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4'
        cid = make_cid(cid_str)
        
        assert isinstance(cid, CIDv0)
        assert cid.version == 0
        assert cid.codec == 'dag-pb'
        assert str(cid) == cid_str
    
    def test_make_cid_v1_base32(self):
        """Test creating CIDv1 from base32 string"""
        cid_str = 'bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi'
        cid = make_cid(cid_str)
        
        assert isinstance(cid, CIDv1)
        assert cid.version == 1
    
    def test_make_cid_v1_base58(self):
        """Test creating CIDv1 from base58 string"""
        cid_str = 'zdj7WhuEjrB52m1BisYCtmjH1hSKa7yZ3jEZ9JcXaFRD51wVz'
        cid = make_cid(cid_str)
        
        assert isinstance(cid, CIDv1)
        assert cid.version == 1
    
    def test_make_cid_invalid(self):
        """Test that invalid CID raises ValueError"""
        with pytest.raises(ValueError):
            make_cid('invalid-cid-string')


class TestCIDv0:
    """Test CIDv0 functionality"""
    
    @pytest.fixture
    def sample_multihash(self):
        """Fixture providing sample multihash"""
        content = b"test content"
        mh = multihash.digest(content, 'sha2-256')
        return mh.encode()
    
    def test_cidv0_creation(self, sample_multihash):
        """Test CIDv0 object creation"""
        cid = CIDv0(sample_multihash)
        
        assert cid.version == 0
        assert cid.codec == 'dag-pb'
        assert cid.multihash == sample_multihash
    
    def test_cidv0_encoding(self, sample_multihash):
        """Test CIDv0 encoding"""
        cid = CIDv0(sample_multihash)
        encoded = cid.encode()
        
        assert isinstance(encoded, bytes)
        assert encoded.decode('ascii').startswith('Qm')
    
    def test_cidv0_string_representation(self, sample_multihash):
        """Test string conversion"""
        cid = CIDv0(sample_multihash)
        cid_str = str(cid)
        
        assert cid_str.startswith('Qm')
        assert len(cid_str) == 46
    
    def test_cidv0_to_v1_conversion(self, sample_multihash):
        """Test converting CIDv0 to CIDv1"""
        cid_v0 = CIDv0(sample_multihash)
        cid_v1 = cid_v0.to_v1()
        
        assert isinstance(cid_v1, CIDv1)
        assert cid_v1.version == 1
        assert cid_v1.codec == 'dag-pb'
        assert cid_v1.multihash == sample_multihash
    
    def test_cidv0_equality(self, sample_multihash):
        """Test CIDv0 equality"""
        cid1 = CIDv0(sample_multihash)
        cid2 = CIDv0(sample_multihash)
        
        assert cid1 == cid2
        assert hash(cid1) == hash(cid2)
    
    def test_cidv0_only_accepts_sha256(self):
        """Test that CIDv0 only accepts SHA-256"""
        content = b"test"
        mh_sha512 = multihash.digest(content, 'sha2-512').encode()
        
        with pytest.raises(ValueError, match="SHA-256"):
            CIDv0(mh_sha512)


class TestCIDv1:
    """Test CIDv1 functionality"""
    
    @pytest.fixture
    def sample_multihash(self):
        """Fixture providing sample multihash"""
        content = b"test content"
        mh = multihash.digest(content, 'sha2-256')
        return mh.encode()
    
    def test_cidv1_creation(self, sample_multihash):
        """Test CIDv1 object creation"""
        cid = CIDv1('raw', sample_multihash)
        
        assert cid.version == 1
        assert cid.codec == 'raw'
        assert cid.multihash == sample_multihash
    
    def test_cidv1_encoding_base32(self, sample_multihash):
        """Test CIDv1 base32 encoding"""
        cid = CIDv1('raw', sample_multihash)
        encoded = cid.encode('base32')
        
        assert isinstance(encoded, bytes)
        decoded = encoded.decode('ascii')
        assert decoded.startswith('bafk')  # base32 + raw codec
    
    def test_cidv1_encoding_base58(self, sample_multihash):
        """Test CIDv1 base58 encoding"""
        cid = CIDv1('raw', sample_multihash)
        encoded = cid.encode('base58btc')
        
        assert isinstance(encoded, bytes)
        decoded = encoded.decode('ascii')
        assert decoded.startswith('z')  # base58btc prefix
    
    def test_cidv1_multiple_codecs(self, sample_multihash):
        """Test CIDv1 with different codecs"""
        codecs = ['raw', 'dag-pb', 'dag-cbor', 'dag-json']
        
        for codec in codecs:
            cid = CIDv1(codec, sample_multihash)
            assert cid.codec == codec
    
    def test_cidv1_to_v0_conversion(self, sample_multihash):
        """Test converting CIDv1 to CIDv0"""
        cid_v1 = CIDv1('dag-pb', sample_multihash)
        cid_v0 = cid_v1.to_v0()
        
        assert isinstance(cid_v0, CIDv0)
        assert cid_v0.version == 0
        assert cid_v0.multihash == sample_multihash
    
    def test_cidv1_to_v0_only_dagpb(self, sample_multihash):
        """Test that only dag-pb CIDv1 can convert to v0"""
        cid_raw = CIDv1('raw', sample_multihash)
        
        with pytest.raises(ValueError, match="dag-pb"):
            cid_raw.to_v0()
    
    def test_cidv1_equality(self, sample_multihash):
        """Test CIDv1 equality"""
        cid1 = CIDv1('raw', sample_multihash)
        cid2 = CIDv1('raw', sample_multihash)
        cid3 = CIDv1('dag-pb', sample_multihash)
        
        assert cid1 == cid2
        assert cid1 != cid3  # Different codec
        assert hash(cid1) == hash(cid2)


class TestConversions:
    """Test version conversions"""
    
    def test_roundtrip_v0_to_v1_to_v0(self):
        """Test v0 -> v1 -> v0 conversion"""
        original = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')
        v1 = original.to_v1()
        back_to_v0 = v1.to_v0()
        
        assert original == back_to_v0
    
    def test_same_content_different_versions(self):
        """Test that same content has different string repr in different versions"""
        v0 = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')
        v1 = v0.to_v1()
        
        # Same content (multihash)
        assert v0.multihash == v1.multihash
        
        # Different string representation
        assert str(v0) != str(v1)
        
        # Both valid
        assert v0.version == 0
        assert v1.version == 1


@pytest.mark.parametrize("cid_str,expected_version", [
    ('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4', 0),
    ('bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi', 1),
    ('zdj7WhuEjrB52m1BisYCtmjH1hSKa7yZ3jEZ9JcXaFRD51wVz', 1),
])
def test_version_detection(cid_str, expected_version):
    """Test automatic version detection"""
    cid = make_cid(cid_str)
    assert cid.version == expected_version
```

### Fixtures

```python
# tests/conftest.py
import pytest
import multihash
from cid import CIDv0, CIDv1

@pytest.fixture
def sample_content():
    """Sample content for testing"""
    return b"Hello, IPFS! This is test content."

@pytest.fixture
def sample_multihash_sha256(sample_content):
    """SHA-256 multihash of sample content"""
    mh = multihash.digest(sample_content, 'sha2-256')
    return mh.encode()

@pytest.fixture
def sample_multihash_sha512(sample_content):
    """SHA-512 multihash of sample content"""
    mh = multihash.digest(sample_content, 'sha2-512')
    return mh.encode()

@pytest.fixture
def sample_cidv0(sample_multihash_sha256):
    """Sample CIDv0 object"""
    return CIDv0(sample_multihash_sha256)

@pytest.fixture
def sample_cidv1_raw(sample_multihash_sha256):
    """Sample CIDv1 with raw codec"""
    return CIDv1('raw', sample_multihash_sha256)

@pytest.fixture
def sample_cidv1_dagpb(sample_multihash_sha256):
    """Sample CIDv1 with dag-pb codec"""
    return CIDv1('dag-pb', sample_multihash_sha256)

@pytest.fixture
def known_cids():
    """Known CID test vectors"""
    return {
        'v0': 'QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4',
        'v1_base32': 'bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi',
        'v1_base58': 'zdj7WhuEjrB52m1BisYCtmjH1hSKa7yZ3jEZ9JcXaFRD51wVz',
    }
```

---

## Contributing Guidelines

### Development Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/py-cid.git
cd py-cid

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install in development mode
pip install -e ".[dev]"

# 4. Install pre-commit hooks (if available)
pre-commit install

# 5. Run tests to verify setup
pytest
```

### Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/my-feature

# 2. Make changes and add tests

# 3. Run tests
pytest

# 4. Check code style
black cid tests
flake8 cid tests

# 5. Type checking
mypy cid

# 6. Run full test suite with tox
tox

# 7. Commit changes
git add .
git commit -m "feat: add new feature"

# 8. Push and create PR
git push origin feature/my-feature
```

### Code Style

**Formatting**: Black (line length 100)
```bash
black --line-length 100 cid tests
```

**Linting**: Flake8
```bash
flake8 cid tests --max-line-length=100
```

**Type Hints**: Required for public APIs
```python
def make_cid(cid_str: Union[str, bytes]) -> Union[CIDv0, CIDv1]:
    """
    Create CID from string.
    
    Args:
        cid_str: CID string or bytes
        
    Returns:
        CIDv0 or CIDv1 object
        
    Raises:
        ValueError: If invalid CID
    """
    pass
```

**Docstrings**: Google style
```python
def encode(self, encoding: str = 'base32') -> bytes:
    """
    Encode CID with specified base encoding.
    
    Args:
        encoding: Base encoding name (default: base32).
                 Supported: base32, base58btc, base64, etc.
    
    Returns:
        Encoded CID as bytes.
        
    Raises:
        ValueError: If encoding is not supported.
        
    Example:
        >>> cid = CIDv1('raw', multihash_bytes)
        >>> cid.encode('base32')
        b'bafk...'
    """
    pass
```

### Testing Requirements

- All new features must have tests
- Maintain or improve code coverage
- Test edge cases and error conditions
- Use fixtures for common test data

```python
# Good test structure
def test_feature_happy_path():
    """Test normal operation"""
    pass

def test_feature_edge_case():
    """Test edge case"""
    pass

def test_feature_error_handling():
    """Test error conditions"""
    with pytest.raises(ValueError):
        # code that should raise
        pass
```

### Pull Request Process

1. **Update tests**: Add/update tests for changes
2. **Update docs**: Update docstrings and README if needed
3. **Run full test suite**: `tox` or `pytest`
4. **Update HISTORY.md**: Add entry for changes
5. **Create PR**: Provide clear description
6. **Respond to reviews**: Address feedback promptly

### Commit Message Format

Follow conventional commits:

```
type(scope): brief description

Longer explanation if needed.

Fixes #123
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions/changes
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `chore`: Maintenance tasks

**Examples**:
```
feat(cid): add support for blake3 hash function

fix(cidv1): handle edge case in base32 encoding

docs(readme): update installation instructions

test(conversions): add roundtrip conversion tests
```

---

## Advanced Features

### Custom Hash Functions

```python
"""
Using custom or newer hash functions.
"""
import multihash
from cid import CIDv1

# Use Blake2b (faster than SHA-256)
content = b"Large file content..."
mh_blake2b = multihash.digest(content, 'blake2b-256')
cid_blake2b = CIDv1('raw', mh_blake2b.encode())

print(f"Blake2b CID: {cid_blake2b}")

# Use SHA3
mh_sha3 = multihash.digest(content, 'sha3-256')
cid_sha3 = CIDv1('raw', mh_sha3.encode())

print(f"SHA3 CID: {cid_sha3}")
```

### Working with IPLD Data Structures

```python
"""
CIDs for IPLD (InterPlanetary Linked Data) structures.
"""
import cbor2
import multihash
from cid import CIDv1

# IPLD document with links to other content
ipld_doc = {
    "name": "My Document",
    "content": {"/" : "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy"},
    "metadata": {
        "author": "Alice",
        "date": "2024-01-01"
    }
}

# Serialize with CBOR
cbor_data = cbor2.dumps(ipld_doc)

# Create CID with dag-cbor codec
mh = multihash.digest(cbor_data, 'sha2-256')
cid = CIDv1('dag-cbor', mh.encode())

print(f"IPLD Document CID: {cid}")
```

### Content Verification

```python
"""
Verify content integrity using CIDs.
"""
import multihash
from cid import make_cid, CIDv1

def verify_content(content: bytes, claimed_cid: str) -> tuple[bool, str]:
    """
    Verify that content matches the claimed CID.
    
    Args:
        content: The actual content bytes
        claimed_cid: The CID string to verify against
        
    Returns:
        (is_valid, message): Verification result and message
    """
    try:
        # Parse claimed CID
        cid = make_cid(claimed_cid)
        
        # Get hash function from CID's multihash
        mh_info = multihash.decode(cid.multihash)
        hash_name = mh_info['name']
        
        # Hash the content with same algorithm
        calculated_mh = multihash.digest(content, hash_name)
        
        # Create CID from calculated hash
        calculated_cid = CIDv1(cid.codec, calculated_mh.encode())
        
        # Compare
        if str(calculated_cid) == str(cid) or calculated_cid.multihash == cid.multihash:
            return True, "Content matches CID"
        else:
            return False, f"Content mismatch. Expected: {cid}, Got: {calculated_cid}"
    
    except Exception as e:
        return False, f"Verification error: {e}"

# Usage
content = b"Hello, IPFS!"
cid_str = "bafkreifzjut3te2nhyekklss27nh3k72ysco7y32koao5eei66wof36n5e"

is_valid, message = verify_content(content, cid_str)
print(f"Valid: {is_valid}")
print(f"Message: {message}")
```

### CID in URLs

```python
"""
Using CIDs in URLs (web3 gateway pattern).
"""
from cid import make_cid

def create_ipfs_url(cid_str: str, path: str = "", gateway: str = "https://ipfs.io") -> str:
    """
    Create IPFS gateway URL from CID.
    
    Args:
        cid_str: CID string
        path: Optional path within the content
        gateway: IPFS gateway URL
        
    Returns:
        Full gateway URL
    """
    cid = make_cid(cid_str)
    
    # Convert to v1 base32 for URL compatibility (case-insensitive)
    if cid.version == 0:
        cid = cid.to_v1()
    
    cid_base32 = cid.encode('base32').decode('utf-8')
    
    # Build URL
    url = f"{gateway}/ipfs/{cid_base32}"
    if path:
        url += f"/{path.lstrip('/')}"
    
    return url

# Usage
cid = "QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4"
url = create_ipfs_url(cid, path="readme.md")
print(url)
# https://ipfs.io/ipfs/bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi/readme.md
```

### Batch Operations

```python
"""
Efficient batch processing of CIDs.
"""
from typing import List, Dict
from cid import make_cid, CIDv0, CIDv1
import multihash

class CIDBatch:
    """Batch processor for CID operations"""
    
    def __init__(self):
        self.cids: List[Union[CIDv0, CIDv1]] = []
    
    def add_from_content(self, contents: List[bytes], codec='raw') -> List[str]:
        """
        Create CIDs from multiple content items.
        
        Args:
            contents: List of content bytes
            codec: Codec to use for all CIDs
            
        Returns:
            List of CID strings
        """
        cid_strings = []
        
        for content in contents:
            mh = multihash.digest(content, 'sha2-256')
            cid = CIDv1(codec, mh.encode())
            self.cids.append(cid)
            cid_strings.append(str(cid))
        
        return cid_strings
    
    def convert_all_to_v1(self) -> List[CIDv1]:
        """Convert all CIDs to v1"""
        v1_cids = []
        
        for cid in self.cids:
            if isinstance(cid, CIDv0):
                v1_cids.append(cid.to_v1())
            else:
                v1_cids.append(cid)
        
        return v1_cids
    
    def encode_all(self, encoding='base32') -> List[str]:
        """Encode all CIDs with specified encoding"""
        return [cid.encode(encoding).decode('utf-8') for cid in self.cids]
    
    def group_by_codec(self) -> Dict[str, List[str]]:
        """Group CIDs by their codec"""
        groups = {}
        
        for cid in self.cids:
            codec = cid.codec
            if codec not in groups:
                groups[codec] = []
            groups[codec].append(str(cid))
        
        return groups

# Usage
batch = CIDBatch()

# Process multiple files
files = [b"File 1", b"File 2", b"File 3"]
cids = batch.add_from_content(files, codec='raw')

print(f"Created {len(cids)} CIDs")
for i, cid in enumerate(cids):
    print(f"  {i+1}. {cid}")

# Convert all to v1 and encode as base58
v1_cids = batch.convert_all_to_v1()
base58_encoded = [cid.encode('base58btc').decode('utf-8') for cid in v1_cids]
```

### Performance Optimization

```python
"""
Performance tips for working with CIDs.
"""
from cid import make_cid, CIDv1
import multihash
from functools import lru_cache

# 1. Cache CID parsing for frequently used CIDs
@lru_cache(maxsize=1000)
def parse_cid_cached(cid_str: str):
    """Cached CID parsing for performance"""
    return make_cid(cid_str)

# 2. Pre-compute CIDs for static content
class StaticContent:
    """Pre-computed CIDs for static files"""
    
    def __init__(self):
        self._cid_cache = {}
    
    def register(self, name: str, content: bytes):
        """Register content with pre-computed CID"""
        mh = multihash.digest(content, 'sha2-256')
        cid = CIDv1('raw', mh.encode())
        self._cid_cache[name] = (str(cid), content)
    
    def get_cid(self, name: str) -> str:
        """Get pre-computed CID (O(1) lookup)"""
        return self._cid_cache[name][0]
    
    def get_content(self, name: str) -> bytes:
        """Get content by name"""
        return self._cid_cache[name][1]

# 3. Batch hash computation
def compute_cids_batch(contents: List[bytes]) -> List[str]:
    """Compute multiple CIDs efficiently"""
    cids = []
    for content in contents:
        mh = multihash.digest(content, 'sha2-256')
        cid = CIDv1('raw', mh.encode())
        cids.append(str(cid))
    return cids
```

---

## Deep Dive: Implementation Details

### Multihash Structure

Understanding the multihash format within CIDs:

```python
"""
Multihash anatomy and parsing.
"""
import multihash

# Create a multihash
content = b"Hello, World!"
mh = multihash.digest(content, 'sha2-256')

print("Multihash components:")
print(f"  Algorithm: {mh.name}")      # sha2-256
print(f"  Code: 0x{mh.code:02x}")     # 0x12
print(f"  Length: {mh.length} bytes") # 32
print(f"  Digest: {mh.digest.hex()[:20]}...")

# Encoded multihash format: <hash-code><hash-length><hash-value>
encoded = mh.encode()
print(f"\nEncoded multihash: {encoded.hex()[:20]}...")
print(f"  First byte (code): 0x{encoded[0]:02x}")
print(f"  Second byte (length): {encoded[1]}")
print(f"  Remaining bytes: hash value")

# Decode multihash
decoded = multihash.decode(encoded)
print(f"\nDecoded:")
print(f"  Code: 0x{decoded['code']:02x}")
print(f"  Name: {decoded['name']}")
print(f"  Length: {decoded['length']}")
print(f"  Digest: {decoded['digest'].hex()[:20]}...")
```

### CIDv0 Binary Format

```python
"""
CIDv0 binary representation.
"""
from cid import CIDv0
import multihash
import base58

content = b"test"
mh = multihash.digest(content, 'sha2-256')
cid_v0 = CIDv0(mh.encode())

print("CIDv0 Format:")
print("  base58btc(multihash)")
print()

# The multihash
mh_bytes = cid_v0.multihash
print(f"Multihash bytes: {mh_bytes.hex()}")
print(f"  Length: {len(mh_bytes)} bytes")
print()

# Base58 encoding
encoded = base58.b58encode(mh_bytes)
print(f"Base58-encoded: {encoded.decode()}")
print(f"  Starts with: Qm (always for CIDv0)")
print(f"  Length: {len(encoded.decode())} chars (always 46)")
```

### CIDv1 Binary Format

```python
"""
CIDv1 binary representation and multibase encoding.
"""
from cid import CIDv1
import multihash
import multicodec
import multibase

content = b"test"
mh = multihash.digest(content, 'sha2-256')
cid_v1 = CIDv1('raw', mh.encode())

print("CIDv1 Format:")
print("  multibase(version + codec + multihash)")
print()

# Components
print("Components:")
print(f"  Version: {cid_v1.version}")
print(f"  Codec: {cid_v1.codec}")
print(f"  Multihash: {cid_v1.multihash.hex()[:40]}...")
print()

# Binary format (before base encoding)
codec_code = multicodec.get_codec(cid_v1.codec).code
version_byte = bytes([1])
cid_bytes = version_byte + codec_code + cid_v1.multihash

print("Binary CID (before encoding):")
print(f"  Total: {len(cid_bytes)} bytes")
print(f"  Hex: {cid_bytes.hex()[:40]}...")
print(f"    [0]: version (0x01)")
print(f"    [1-n]: codec code (varint)")
print(f"    [n+1...]: multihash")
print()

# Different encodings
encodings = ['base32', 'base58btc', 'base64']
print("Encoded representations:")
for enc in encodings:
    encoded = cid_v1.encode(enc)
    print(f"  {enc:12s}: {encoded.decode()[:60]}...")
```

### Varint Encoding in CIDv1

```python
"""
Understanding varint encoding in codec codes.
"""

def encode_varint(n: int) -> bytes:
    """
    Encode integer as unsigned varint.
    
    Used for codec codes in CIDv1.
    """
    buf = []
    while n >= 0x80:
        buf.append((n & 0xff) | 0x80)
        n >>= 7
    buf.append(n & 0xff)
    return bytes(buf)

def decode_varint(buf: bytes) -> tuple:
    """
    Decode unsigned varint.
    
    Returns (value, bytes_consumed).
    """
    x = 0
    s = 0
    for i, b in enumerate(buf):
        if b < 0x80:
            return x | (b << s), i + 1
        x |= ((b & 0x7f) << s)
        s += 7
    return 0, 0

# Example codec codes
codes = {
    'raw': 0x55,
    'dag-pb': 0x70,
    'dag-cbor': 0x71,
    'dag-json': 0x85,
}

print("Codec varint encoding:")
for name, code in codes.items():
    encoded = encode_varint(code)
    print(f"  {name:12s} (0x{code:02x}): {encoded.hex()}")
    
    # Decode to verify
    decoded, length = decode_varint(encoded)
    assert decoded == code
```

---

## Common Use Cases

### 1. IPFS File Storage

```python
"""
Simulating IPFS file storage with CIDs.
"""
from cid import CIDv1
import multihash
from typing import Dict

class SimpleIPFS:
    """Simple IPFS-like storage using CIDs"""
    
    def __init__(self):
        self.blocks: Dict[str, bytes] = {}
    
    def add(self, content: bytes) -> str:
        """
        Add content to IPFS.
        
        Args:
            content: File content
            
        Returns:
            CID string
        """
        # Hash content
        mh = multihash.digest(content, 'sha2-256')
        cid = CIDv1('raw', mh.encode())
        cid_str = str(cid)
        
        # Store block
        self.blocks[cid_str] = content
        
        print(f"Added block: {cid_str}")
        return cid_str
    
    def get(self, cid_str: str) -> bytes:
        """
        Retrieve content by CID.
        
        Args:
            cid_str: CID string
            
        Returns:
            Content bytes
            
        Raises:
            KeyError: If CID not found
        """
        if cid_str not in self.blocks:
            raise KeyError(f"Block not found: {cid_str}")
        
        return self.blocks[cid_str]
    
    def pin(self, cid_str: str):
        """Mark content as important (prevent garbage collection)"""
        if cid_str not in self.blocks:
            raise KeyError(f"Cannot pin non-existent block: {cid_str}")
        print(f"Pinned: {cid_str}")
    
    def cat(self, cid_str: str) -> str:
        """Get content as string (like ipfs cat)"""
        content = self.get(cid_str)
        return content.decode('utf-8')

# Usage
ipfs = SimpleIPFS()

# Add file
file_content = b"Hello from IPFS!"
cid = ipfs.add(file_content)

# Retrieve file
retrieved = ipfs.get(cid)
assert retrieved == file_content

# Pin important content
ipfs.pin(cid)

# Cat (read as text)
text = ipfs.cat(cid)
print(f"Content: {text}")
```

### 2. Content Deduplication System

```python
"""
Deduplication system using content addressing.
"""
from cid import CIDv1
import multihash
from collections import defaultdict

class DeduplicationStore:
    """Storage system with automatic deduplication"""
    
    def __init__(self):
        self.blocks = {}  # cid -> content
        self.references = defaultdict(set)  # cid -> set of file paths
        self.stats = {
            'total_files': 0,
            'unique_blocks': 0,
            'bytes_stored': 0,
            'bytes_saved': 0,
        }
    
    def store_file(self, path: str, content: bytes) -> str:
        """
        Store file content.
        
        Args:
            path: File path (for reference)
            content: File content
            
        Returns:
            CID of stored content
        """
        # Calculate CID
        mh = multihash.digest(content, 'sha2-256')
        cid = CIDv1('raw', mh.encode())
        cid_str = str(cid)
        
        # Check if content already exists
        if cid_str in self.blocks:
            # Deduplicated!
            self.stats['bytes_saved'] += len(content)
            print(f"Deduplicated: {path} -> {cid_str[:20]}...")
        else:
            # New unique content
            self.blocks[cid_str] = content
            self.stats['unique_blocks'] += 1
            self.stats['bytes_stored'] += len(content)
            print(f"Stored: {path} -> {cid_str[:20]}...")
        
        # Add reference
        self.references[cid_str].add(path)
        self.stats['total_files'] += 1
        
        return cid_str
    
    def get_file(self, cid_str: str) -> bytes:
        """Retrieve content by CID"""
        return self.blocks[cid_str]
    
    def get_references(self, cid_str: str) -> set:
        """Get all file paths referencing this CID"""
        return self.references[cid_str]
    
    def print_stats(self):
        """Print deduplication statistics"""
        print("\n=== Deduplication Statistics ===")
        print(f"Total files: {self.stats['total_files']}")
        print(f"Unique blocks: {self.stats['unique_blocks']}")
        print(f"Bytes stored: {self.stats['bytes_stored']:,}")
        print(f"Bytes saved: {self.stats['bytes_saved']:,}")
        
        if self.stats['total_files'] > 0:
            dedup_rate = (self.stats['bytes_saved'] / 
                         (self.stats['bytes_stored'] + self.stats['bytes_saved']) * 100)
            print(f"Deduplication rate: {dedup_rate:.1f}%")

# Usage
store = DeduplicationStore()

# Store same content with different names
content = b"This content appears in multiple files"
store.store_file("file1.txt", content)
store.store_file("file2.txt", content)
store.store_file("backup/file1.txt", content)

# Store different content
store.store_file("other.txt", b"Different content")

store.print_stats()

# Output:
# Stored: file1.txt -> bafkreigj7ckqwpbc...
# Deduplicated: file2.txt -> bafkreigj7ckqwpbc...
# Deduplicated: backup/file1.txt -> bafkreigj7ckqwpbc...
# Stored: other.txt -> bafkreifxfzrxfpa...
# 
# === Deduplication Statistics ===
# Total files: 4
# Unique blocks: 2
# Bytes stored: 79
# Bytes saved: 78
# Deduplication rate: 49.7%
```

### 3. Blockchain / Distributed Ledger

```python
"""
Using CIDs in a blockchain-like structure.
"""
from cid import CIDv1
import multihash
import json
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Block:
    """Blockchain block with CID-based linking"""
    index: int
    timestamp: str
    data: dict
    previous_cid: Optional[str]
    cid: Optional[str] = None
    
    def to_bytes(self) -> bytes:
        """Serialize block for hashing"""
        block_dict = {
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_cid': self.previous_cid,
        }
        return json.dumps(block_dict, sort_keys=True).encode('utf-8')
    
    def calculate_cid(self) -> str:
        """Calculate CID for this block"""
        content = self.to_bytes()
        mh = multihash.digest(content, 'sha2-256')
        cid = CIDv1('dag-json', mh.encode())
        self.cid = str(cid)
        return self.cid

class Blockchain:
    """Simple blockchain using CIDs"""
    
    def __init__(self):
        self.chain = []
        self.create_genesis_block()
    
    def create_genesis_block(self):
        """Create the first block"""
        genesis = Block(
            index=0,
            timestamp="2024-01-01T00:00:00Z",
            data={"message": "Genesis Block"},
            previous_cid=None
        )
        genesis.calculate_cid()
        self.chain.append(genesis)
        print(f"Genesis block created: {genesis.cid}")
    
    def add_block(self, data: dict):
        """Add new block to chain"""
        previous_block = self.chain[-1]
        
        new_block = Block(
            index=len(self.chain),
            timestamp="2024-01-01T00:00:00Z",  # Simplified
            data=data,
            previous_cid=previous_block.cid
        )
        new_block.calculate_cid()
        
        self.chain.append(new_block)
        print(f"Block {new_block.index} added: {new_block.cid}")
        return new_block.cid
    
    def verify_chain(self) -> bool:
        """Verify blockchain integrity using CIDs"""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i-1]
            
            # Verify link
            if current.previous_cid != previous.cid:
                print(f"Chain broken at block {i}: previous_cid mismatch")
                return False
            
            # Verify CID
            recalculated_cid = Block(
                index=current.index,
                timestamp=current.timestamp,
                data=current.data,
                previous_cid=current.previous_cid
            ).calculate_cid()
            
            if recalculated_cid != current.cid:
                print(f"Block {i} tampered: CID mismatch")
                return False
        
        print("Blockchain verified: all CIDs valid")
        return True

# Usage
chain = Blockchain()

# Add blocks
chain.add_block({"transaction": "Alice -> Bob: 10 coins"})
chain.add_block({"transaction": "Bob -> Charlie: 5 coins"})
chain.add_block({"transaction": "Charlie -> Alice: 3 coins"})

# Verify integrity
chain.verify_chain()

# Try to tamper
print("\nAttempting to tamper with block 1...")
chain.chain[1].data["transaction"] = "Alice -> Bob: 1000 coins"
chain.verify_chain()  # Will fail
```

### 4. Version Control System

```python
"""
Git-like version control using CIDs.
"""
from cid import CIDv1
import multihash
from typing import Dict, List, Optional

class Commit:
    """Version control commit"""
    
    def __init__(self, message: str, files: Dict[str, bytes], parent: Optional[str] = None):
        self.message = message
        self.files = files  # path -> content
        self.parent = parent  # parent commit CID
        self.file_cids = {}
        self.cid = None
    
    def calculate_cid(self) -> str:
        """Calculate CID for this commit"""
        # Calculate CID for each file
        for path, content in self.files.items():
            mh = multihash.digest(content, 'sha2-256')
            file_cid = CIDv1('raw', mh.encode())
            self.file_cids[path] = str(file_cid)
        
        # Create commit object
        commit_data = {
            'message': self.message,
            'files': self.file_cids,
            'parent': self.parent,
        }
        
        # Calculate commit CID
        import json
        commit_bytes = json.dumps(commit_data, sort_keys=True).encode('utf-8')
        mh = multihash.digest(commit_bytes, 'sha2-256')
        commit_cid = CIDv1('dag-json', mh.encode())
        self.cid = str(commit_cid)
        
        return self.cid

class VersionControl:
    """Simple version control system"""
    
    def __init__(self):
        self.commits: Dict[str, Commit] = {}
        self.blobs: Dict[str, bytes] = {}  # file CID -> content
        self.head: Optional[str] = None
    
    def commit(self, message: str, files: Dict[str, bytes]) -> str:
        """Create new commit"""
        # Create commit
        commit = Commit(message, files, parent=self.head)
        cid = commit.calculate_cid()
        
        # Store commit
        self.commits[cid] = commit
        
        # Store file blobs
        for file_cid, content in zip(commit.file_cids.values(), files.values()):
            if file_cid not in self.blobs:
                self.blobs[file_cid] = content
        
        # Update head
        self.head = cid
        
        print(f"Committed: {cid[:20]}... - {message}")
        return cid
    
    def checkout(self, commit_cid: str) -> Dict[str, bytes]:
        """Checkout files from commit"""
        if commit_cid not in self.commits:
            raise ValueError(f"Commit not found: {commit_cid}")
        
        commit = self.commits[commit_cid]
        files = {}
        
        for path, file_cid in commit.file_cids.items():
            files[path] = self.blobs[file_cid]
        
        return files
    
    def log(self):
        """Show commit history"""
        print("\n=== Commit History ===")
        current = self.head
        
        while current:
            commit = self.commits[current]
            print(f"\nCommit: {current[:20]}...")
            print(f"Message: {commit.message}")
            print(f"Files: {len(commit.files)}")
            current = commit.parent

# Usage
vcs = VersionControl()

# Initial commit
vcs.commit("Initial commit", {
    "README.md": b"# My Project\n\nWelcome!",
    "main.py": b"print('Hello, World!')",
})

# Second commit (modify file)
vcs.commit("Update greeting", {
    "README.md": b"# My Project\n\nWelcome!",
    "main.py": b"print('Hello, IPFS!')",
})

# Third commit (add file)
vcs.commit("Add config", {
    "README.md": b"# My Project\n\nWelcome!",
    "main.py": b"print('Hello, IPFS!')",
    "config.json": b'{"version": "1.0"}',
})

# Show history
vcs.log()

# Checkout first commit
first_commit_cid = list(vcs.commits.keys())[0]
files = vcs.checkout(first_commit_cid)
print(f"\n=== Files in first commit ===")
for path in files:
    print(f"  - {path}")
```

---

## Debugging and Troubleshooting

### Common Issues

#### Issue 1: Invalid CID Format

```python
from cid import make_cid

# Problem: Invalid CID string
try:
    cid = make_cid("invalid-string")
except ValueError as e:
    print(f"Error: {e}")
    # Solution: Ensure CID is properly formatted

# Valid formats:
# CIDv0: Starts with Qm, 46 chars, base58
valid_v0 = make_cid("QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4")

# CIDv1: Has multibase prefix (b for base32, z for base58, etc.)
valid_v1 = make_cid("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
```

#### Issue 2: Version Conversion Errors

```python
from cid import make_cid

# Problem: Cannot convert non-dag-pb CIDv1 to v0
cid_raw = make_cid("bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy")

try:
    v0 = cid_raw.to_v0()
except ValueError as e:
    print(f"Error: {e}")
    # Solution: Only dag-pb + SHA-256 CIDv1 can convert to v0
    print(f"CID codec: {cid_raw.codec}")  # 'raw' - cannot convert

# This works:
cid_dagpb = make_cid("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
v0 = cid_dagpb.to_v0()
print(f"Converted: {v0}")
```

#### Issue 3: Encoding Errors

```python
from cid import CIDv0

# Problem: CIDv0 only supports base58btc
import multihash
mh = multihash.digest(b"test", 'sha2-256')
cid_v0 = CIDv0(mh.encode())

try:
    encoded = cid_v0.encode('base32')
except ValueError as e:
    print(f"Error: {e}")
    # Solution: Use base58btc for v0, or convert to v1 first

# Correct approach:
encoded = cid_v0.encode('base58btc')  # OK
# or
cid_v1 = cid_v0.to_v1()
encoded = cid_v1.encode('base32')  # OK
```

### Debugging Utilities

```python
"""
Utilities for debugging CID issues.
"""
from cid import make_cid
import multihash

def debug_cid(cid_str: str):
    """Print detailed CID information for debugging"""
    try:
        cid = make_cid(cid_str)
        
        print("=== CID Debug Info ===")
        print(f"Input: {cid_str}")
        print(f"Version: {cid.version}")
        print(f"Codec: {cid.codec}")
        print()
        
        # Multihash details
        mh_info = multihash.decode(cid.multihash)
        print("Multihash:")
        print(f"  Algorithm: {mh_info['name']}")
        print(f"  Code: 0x{mh_info['code']:02x}")
        print(f"  Length: {mh_info['length']} bytes")
        print(f"  Digest: {mh_info['digest'].hex()[:40]}...")
        print()
        
        # Encodings
        if cid.version == 1:
            print("Available encodings:")
            for enc in ['base32', 'base58btc', 'base64']:
                encoded = cid.encode(enc)
                print(f"  {enc:12s}: {encoded.decode()[:60]}...")
        else:
            print(f"Encoding: base58btc only")
            print(f"  {cid.encode().decode()}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        print(f"Input might not be a valid CID")


def verify_cid_content(content: bytes, cid_str: str) -> bool:
    """Verify content matches CID"""
    try:
        cid = make_cid(cid_str)
        mh_info = multihash.decode(cid.multihash)
        
        # Hash content
        calculated_mh = multihash.digest(content, mh_info['name'])
        
        # Compare digests
        if calculated_mh.digest == mh_info['digest']:
            print("✓ Content matches CID")
            return True
        else:
            print("✗ Content does NOT match CID")
            print(f"  Expected: {mh_info['digest'].hex()[:40]}...")
            print(f"  Got:      {calculated_mh.digest.hex()[:40]}...")
            return False
            
    except Exception as e:
        print(f"Error during verification: {e}")
        return False

# Usage
debug_cid("QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4")
print("\n")
debug_cid("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
```

---

## Performance Benchmarks

### Typical Operations

```python
"""
Benchmark common CID operations.
"""
import time
from cid import make_cid, CIDv1
import multihash

def benchmark(func, iterations=1000):
    """Simple benchmark helper"""
    start = time.time()
    for _ in range(iterations):
        func()
    elapsed = time.time() - start
    per_op = (elapsed / iterations) * 1000000  # microseconds
    return per_op

# Test data
content = b"x" * 1024  # 1 KB
mh = multihash.digest(content, 'sha2-256')
cid_v0_str = "QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4"
cid_v1_str = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"

print("=== Performance Benchmarks (1000 iterations) ===\n")

# Hash computation
time_hash = benchmark(lambda: multihash.digest(content, 'sha2-256'))
print(f"Hash computation (SHA-256, 1KB): {time_hash:.2f} µs")

# CID creation
time_cid_create = benchmark(lambda: CIDv1('raw', mh.encode()))
print(f"CID creation: {time_cid_create:.2f} µs")

# String parsing
time_parse_v0 = benchmark(lambda: make_cid(cid_v0_str))
print(f"Parse CIDv0 string: {time_parse_v0:.2f} µs")

time_parse_v1 = benchmark(lambda: make_cid(cid_v1_str))
print(f"Parse CIDv1 string: {time_parse_v1:.2f} µs")

# Encoding
cid_v1 = make_cid(cid_v1_str)
time_encode_b32 = benchmark(lambda: cid_v1.encode('base32'))
print(f"Encode to base32: {time_encode_b32:.2f} µs")

time_encode_b58 = benchmark(lambda: cid_v1.encode('base58btc'))
print(f"Encode to base58btc: {time_encode_b58:.2f} µs")

# Version conversion
cid_v0 = make_cid(cid_v0_str)
time_v0_to_v1 = benchmark(lambda: cid_v0.to_v1())
print(f"Convert v0 to v1: {time_v0_to_v1:.2f} µs")

cid_v1_dagpb = cid_v0.to_v1()
time_v1_to_v0 = benchmark(lambda: cid_v1_dagpb.to_v0())
print(f"Convert v1 to v0: {time_v1_to_v0:.2f} µs")

# Equality comparison
cid1 = make_cid(cid_v0_str)
cid2 = make_cid(cid_v0_str)
time_eq = benchmark(lambda: cid1 == cid2)
print(f"Equality comparison: {time_eq:.2f} µs")

# Hash for dict/set
time_hash = benchmark(lambda: hash(cid1))
print(f"Hash calculation: {time_hash:.2f} µs")
```

**Typical Results** (on modern hardware):
- Hash computation (SHA-256, 1KB): ~50-100 µs
- CID creation: ~5-10 µs
- Parse string: ~10-20 µs
- Encode to string: ~5-15 µs
- Version conversion: ~10-20 µs
- Equality comparison: ~0.5-1 µs
- Hash calculation: ~0.5-1 µs

---

## Resources & References

### Official Documentation
- **CID Specification**: https://github.com/ipld/cid
- **py-cid Repository**: https://github.com/ipld/py-cid
- **ReadTheDocs**: https://py-cid.readthedocs.io/
- **Multiformats**: https://multiformats.io/

### Related Specifications
- **Multihash**: https://github.com/multiformats/multihash
- **Multicodec**: https://github.com/multiformats/multicodec
- **Multibase**: https://github.com/multiformats/multibase
- **IPLD**: https://ipld.io/

### Related Python Libraries
- **py-multihash**: https://github.com/multiformats/py-multihash
- **py-multicodec**: https://github.com/multiformats/py-multicodec
- **py-multibase**: https://github.com/multiformats/py-multibase
- **py-multiaddr**: https://github.com/multiformats/py-multiaddr

### IPFS & IPLD Resources
- **IPFS Documentation**: https://docs.ipfs.io/
- **IPLD Documentation**: https://ipld.io/docs/
- **IPFS Specifications**: https://github.com/ipfs/specs
- **Content Addressing**: https://docs.ipfs.io/concepts/content-addressing/

### Community
- **IPFS Forums**: https://discuss.ipfs.io/
- **IPLD Discord**: https://discord.gg/ipfs
- **GitHub Issues**: https://github.com/ipld/py-cid/issues
- **Stack Overflow**: Tag `ipfs` or `ipld`

### Learning Resources
- **ProtoSchool IPFS**: https://proto.school/course/ipfs
- **IPFS Camp Content**: https://github.com/ipfs/camp
- **Content Addressing Guide**: https://proto.school/content-addressing

---

## Appendix

### A. CID Specifications Summary

**CIDv0**:
```
Format: base58btc(<multihash>)
Length: 46 characters
Prefix: Always starts with "Qm"
Codec: Always dag-pb (0x70)
Hash: Always SHA-256 (0x12)
Example: QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4
```

**CIDv1**:
```
Format: <multibase-prefix><version><codec><multihash>
Length: Variable
Prefix: Depends on encoding (b=base32, z=base58btc, etc.)
Codec: Any supported codec
Hash: Any supported hash function
Example: bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi
```

### B. Common Multicodec Codes

| Code | Codec | Description |
|------|-------|-------------|
| 0x55 | raw | Raw binary data |
| 0x70 | dag-pb | MerkleDAG protobuf (IPFS) |
| 0x71 | dag-cbor | IPLD CBOR |
| 0x72 | libp2p-key | libp2p public key |
| 0x78 | git-raw | Git raw object |
| 0x85 | dag-json | IPLD JSON |
| 0x90 | eth-block | Ethereum block |
| 0x91 | eth-block-list | Ethereum block list |
| 0x93 | eth-tx-trie | Ethereum transaction trie |
| 0x94 | eth-tx | Ethereum transaction |

### C. Common Hash Functions

| Code | Name | Output Size | Description |
|------|------|-------------|-------------|
| 0x11 | sha1 | 160 bits | SHA-1 (deprecated) |
| 0x12 | sha2-256 | 256 bits | SHA-2 256 (default) |
| 0x13 | sha2-512 | 512 bits | SHA-2 512 |
| 0x14 | sha3-512 | 512 bits | SHA-3 512 |
| 0x16 | sha3-256 | 256 bits | SHA-3 256 |
| 0x17 | sha3-384 | 384 bits | SHA-3 384 |
| 0x1b | sha3-224 | 224 bits | SHA-3 224 |
| 0xb220 | blake2b-256 | 256 bits | Blake2b 256 |
| 0xb240 | blake2s-256 | 256 bits | Blake2s 256 |
| 0x1e | blake3 | 256 bits | Blake3 |

### D. Multibase Prefixes

| Prefix | Encoding | Description |
|--------|----------|-------------|
| f | base16 (hex) | Hexadecimal lowercase |
| F | base16upper | Hexadecimal uppercase |
| b | base32 | RFC4648 case-insensitive |
| B | base32upper | RFC4648 uppercase |
| z | base58btc | Bitcoin base58 |
| Z | base58flickr | Flickr base58 |
| m | base64 | RFC4648 standard |
| u | base64url | RFC4648 URL-safe |

### E. Error Messages Reference

| Error | Cause | Solution |
|-------|-------|----------|
| `ValueError: Invalid CID` | Malformed CID string | Check CID format and encoding |
| `ValueError: CIDv0 only supports SHA-256` | Wrong hash for v0 | Use SHA-256 or CIDv1 |
| `ValueError: Can only convert dag-pb` | Wrong codec for v0 | Only dag-pb CIDv1 converts to v0 |
| `ValueError: Unknown codec` | Invalid codec name | Check supported codecs |
| `ValueError: CIDv0 only supports base58btc` | Wrong encoding for v0 | Use base58btc or convert to v1 |
| `KeyError: Block not found` | CID not in storage | Verify CID exists |

### F. Quick Reference

**Creating CIDs**:
```python
from cid import make_cid, CIDv0, CIDv1
import multihash

# From string
cid = make_cid('QmaozNR...')

# From content
mh = multihash.digest(content, 'sha2-256')
cid_v0 = CIDv0(mh.encode())
cid_v1 = CIDv1('raw', mh.encode())
```

**Common Operations**:
```python
# Properties
cid.version        # 0 or 1
cid.codec          # 'dag-pb', 'raw', etc.
cid.multihash      # bytes

# Encoding
cid.encode()                    # Default (v0: base58, v1: base32)
cid.encode('base58btc')         # Specific encoding

# String conversion
str(cid)           # Human-readable string

# Comparison
cid1 == cid2       # Equality
hash(cid)          # For sets/dicts

# Version conversion
v1 = cid_v0.to_v1()
v0 = cid_v1.to_v0()  # Only if dag-pb + SHA-256
```

**Testing Commands**:
```bash
pytest                          # Run all tests
pytest -v                       # Verbose
pytest --cov=cid               # With coverage
pytest tests/test_cid.py       # Specific file
tox                            # Test all Python versions
```

---

## Frequently Asked Questions

### Q: What's the difference between CIDv0 and CIDv1?

**A:** CIDv0 is the original IPFS format with fixed parameters (base58btc, dag-pb, SHA-256). CIDv1 is modern and fully self-describing, supporting multiple codecs, hash functions, and encodings. Use CIDv1 for new projects.

### Q: When should I use CIDv0 vs CIDv1?

**A:** Use CIDv1 for new projects. Use CIDv0 only for compatibility with legacy IPFS content. CIDv1 offers better flexibility and is case-insensitive when using base32 (better for URLs).

### Q: Can I convert any CIDv1 to CIDv0?

**A:** No. Only CIDv1 with dag-pb codec and SHA-256 hash can convert to CIDv0, since those are the only parameters CIDv0 supports.

### Q: Why do CIDv0 and CIDv1 look so different for the same content?

**A:** They use different encodings. CIDv0 uses base58btc, while CIDv1 typically uses base32. The underlying multihash is the same, but the string representation differs due to the version byte, codec, and base encoding.

### Q: How do I verify content matches a CID?

**A:** Hash the content with the same algorithm used in the CID, create a new CID, and compare. See the "Content Verification" example in the Advanced Features section.

### Q: Can I create a CID without storing the content?

**A:** No. CIDs are derived from content by hashing. You need the actual content (or at least its hash) to create a CID. This ensures content integrity.

### Q: What hash function should I use?

**A:** SHA-256 (the default) is recommended for most use cases. It's secure, well-supported, and widely used in IPFS. For performance-critical applications, consider Blake2b or Blake3.

### Q: Are CIDs case-sensitive?

**A:** CIDv0 (base58btc) is case-sensitive. CIDv1 with base32 is case-insensitive, making it better for URLs and user input.

### Q: Can I use CIDs in URLs?

**A:** Yes! CIDv1 with base32 encoding is designed for URLs. Convert CIDv0 to CIDv1 base32 for URL usage: `cid.to_v1().encode('base32')`.

### Q: How big are CIDs?

**A:** CIDv0 is always 46 characters. CIDv1 size varies based on hash function and encoding, typically 50-100 characters. Binary format is more compact.

### Q: Is py-cid thread-safe?

**A:** CID objects are immutable, so they're safe to use across threads. Be careful with mutable state in your own code that uses CIDs.

### Q: Can I store CIDs in a database?

**A:** Yes! Store as strings (VARCHAR/TEXT) or bytes (BLOB). Strings are more readable; bytes are more compact. Consider indexing for lookups.

---

## Glossary

**CID (Content Identifier)**: Self-describing content-addressed identifier used in IPFS and IPLD.

**Content Addressing**: Addressing scheme where identifiers are derived from content, not location.

**Multihash**: Self-describing hash format that includes the hash algorithm identifier.

**Multicodec**: Self-describing codec format that identifies how to interpret data.

**Multibase**: Self-describing base encoding format with prefix indicating the encoding used.

**CIDv0**: Original IPFS CID format (base58btc, dag-pb, SHA-256 only).

**CIDv1**: Modern CID format supporting multiple codecs, hashes, and encodings.

**dag-pb**: Protocol Buffers-based codec used by IPFS for UnixFS.

**IPFS (InterPlanetary File System)**: Distributed file system using content addressing.

**IPLD (InterPlanetary Linked Data)**: Data model for content-addressed linked data.

**Codec**: Method for encoding/decoding data (raw, dag-pb, dag-cbor, etc.).

**Hash Function**: Cryptographic function that produces fixed-size output from arbitrary input.

**Base Encoding**: Method for encoding binary data as text (base58, base32, base64, etc.).

**Deduplication**: Eliminating duplicate data by storing each unique piece once.

**Content Integrity**: Ensuring content hasn't been tampered with using cryptographic hashes.

**Varint**: Variable-length integer encoding that uses fewer bytes for smaller numbers.

---

## Conclusion

**py-cid** is a robust, production-ready implementation of the CID specification. As a contributor, you now understand:

✅ **What CIDs are**: Self-describing content-addressed identifiers  
✅ **Why CIDs matter**: Content integrity, deduplication, distributed systems  
✅ **CID versions**: CIDv0 (legacy) vs CIDv1 (modern, flexible)  
✅ **Implementation**: Core classes, encoding/decoding, multiformats  
✅ **Usage patterns**: IPFS integration, verification, deduplication  
✅ **Testing**: Comprehensive test strategies  
✅ **Contributing**: Development workflow and guidelines  

### Next Steps for Contributors

1. **Explore the Codebase**
   ```bash
   git clone https://github.com/ipld/py-cid.git
   cd py-cid
   pip install -e ".[dev]"
   pytest  # Run tests
   ```

2. **Try the Examples**
   - Run code examples from this guide
   - Experiment with different codecs and encodings
   - Build small projects using py-cid

3. **Find Ways to Contribute**
   - Browse open issues: https://github.com/ipld/py-cid/issues
   - Look for "good first issue" or "help wanted" labels
   - Improve documentation or add examples
   - Report bugs or suggest enhancements

4. **Learn More**
   - Read the IPFS and IPLD documentation
   - Study the CID specification
   - Join the IPFS community forums

5. **Build Something**
   - Content-addressed storage system
   - Version control tool
   - Deduplication service
   - Integrity verification tool

### Key Takeaways

- **CIDs solve real problems** with location-based addressing
- **Content addressing** enables deduplication, integrity, and distribution
- **py-cid is production-ready** and powers critical infrastructure
- **The codebase is approachable** with clear structure
- **Testing is essential** - always include tests with changes
- **The community is welcoming** - don't hesitate to ask questions

---

## Quick Start Cheat Sheet

```python
# Install
pip install py-cid

# Import
from cid import make_cid, CIDv0, CIDv1
import multihash

# Parse existing CID
cid = make_cid('QmaozNR7DZHQK1ZcU9p7QdrshMvXqWK6gpu5rmrkPdT3L4')

# Create from content
content = b"Hello, IPFS!"
mh = multihash.digest(content, 'sha2-256')
cid = CIDv1('raw', mh.encode())

# Get properties
cid.version    # 0 or 1
cid.codec      # 'dag-pb', 'raw', etc.
cid.multihash  # bytes

# Encode
str(cid)                    # Default string
cid.encode('base32')        # Specific encoding

# Convert versions
v1 = cid_v0.to_v1()        # v0 -> v1
v0 = cid_v1.to_v0()        # v1 -> v0 (if dag-pb + SHA-256)

# Compare
cid1 == cid2               # Equality
hash(cid)                  # For sets/dicts

# Verify content
mh = multihash.digest(content, 'sha2-256')
expected_cid = CIDv1('raw', mh.encode())
assert str(expected_cid) == str(actual_cid)
```

---

**Happy Contributing to py-cid! 🚀**

*Document Version: 1.0*  
*Last Updated: November 2025*  
*Repository: https://github.com/ipld/py-cid*