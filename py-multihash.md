# Comprehensive Guide to Multihash and Multiformat

## Table of Contents
1. [Introduction](#introduction)
2. [What is Multiformat?](#what-is-multiformat)
3. [What is Multihash?](#what-is-multihash)
4. [Why Do We Use Multihash?](#why-do-we-use-multihash)
5. [Multihash Structure & Format](#multihash-structure--format)
6. [Related Multiformat Protocols](#related-multiformat-protocols)
7. [Multihash Workflow](#multihash-workflow)
8. [Code Examples](#code-examples)
9. [Practical Use Cases](#practical-use-cases)
10. [Best Practices](#best-practices)

---

## Introduction

In the world of distributed systems, content addressing, and cryptography, hash functions play a crucial role. However, as systems evolve, hash functions can become obsolete or compromised. **Multihash** is a protocol designed to future-proof systems by making hash values self-describing, allowing multiple hash functions to coexist seamlessly.

---

## What is Multiformat?

### Definition
**Multiformat** is a collection of protocols that aim to future-proof systems by adding **self-description** to format values. This allows for:
- **Interoperability** between different systems
- **Protocol agility** (ability to change protocols easily)
- **Avoiding vendor lock-in**

### Core Principles
All Multiformat protocols follow these principles:

1. **In-band**: The metadata is embedded within the value itself, not stored separately
2. **Avoid lock-in**: Systems can evolve without breaking existing implementations
3. **Compact**: Binary-packed representation for efficiency
4. **Human-readable**: Alternative representations for debugging and display

### Multiformat Family
The Multiformat project includes several protocols:

- **Multihash** - Self-describing hash digests
- **Multibase** - Self-describing base encodings (base32, base58, base64, etc.)
- **Multicodec** - Self-describing serialization formats
- **Multiaddr** - Self-describing network addresses
- **CID (Content IDentifier)** - Self-describing content-addressed identifiers (combines multihash + multicodec)

---

## What is Multihash?

### Definition
**Multihash** is a protocol for differentiating outputs from various well-established hash functions. It encodes not just the hash digest, but also:
- What hash function was used
- The length of the digest

### The Problem Multihash Solves
Consider this scenario:
```
9ceb0f9889b786a37fd5e754af12f721aa3d8cb18276dd2616d031d2de53a4f2
```

Looking at this hash, you cannot determine:
- What hash function created it? (SHA-256? SHA-512? BLAKE2?)
- What encoding is this? (hex? base64?)
- How long is the full digest?

**Without this information, systems are brittle and hard to upgrade.**

### Real-World Example: Git
Git uses SHA-1 hashes everywhere:
- How many programs assume a Git hash is SHA-1?
- How many scripts assume it's exactly 160 bits?
- What happens when Git needs to migrate to SHA-256?

**Answer**: Chaos. Thousands of tools break. This is the problem Multihash solves.

---

## Why Do We Use Multihash?

### 1. **Future-Proofing**
Hash functions can become:
- **Cryptographically broken** (MD5, SHA-1)
- **Too slow** for modern needs
- **Too weak** against new attack vectors

Multihash allows seamless upgrades without breaking existing systems.

### 2. **Multiple Hash Functions Coexisting**
Different parts of a system might use different hash functions:
- Legacy data uses SHA-1
- New data uses SHA-256
- Future data might use BLAKE3

All can coexist peacefully.

### 3. **Simplified Upgrades**
When a hash function needs upgrading:
- **Without Multihash**: Every tool that reads hashes must be updated
- **With Multihash**: Only tools that verify hashes need updates; readers can just pass them along

This saves **hundreds or thousands of engineering hours**.

### 4. **Self-Describing Data**
Anyone receiving a multihash immediately knows:
- Which hash function to use for verification
- The expected digest length
- No guesswork, no assumptions

---

## Multihash Structure & Format

### TLV Pattern (Type-Length-Value)

Multihash follows the **TLV (Type-Length-Value)** pattern:

```
<hash-function-code><digest-length><digest-value>
```

#### Components:

1. **hash-function-code**: Unsigned varint identifying the hash function
2. **digest-length**: Unsigned varint specifying the digest size in bytes
3. **digest-value**: The actual hash digest output

### Binary Format

```
┌─────────────────────┬───────────────────┬─────────────────────────────┐
│ Hash Function Code  │  Digest Length    │      Digest Value           │
│   (varint)          │   (varint)        │      (bytes)                │
└─────────────────────┴───────────────────┴─────────────────────────────┘
```

### Example Breakdown: SHA-256

Let's hash the string `"multihash"` with SHA-256:

```
Original SHA-256 hash (hex):
41dd7b6443542e75701aa98a0c235951a28a0d851b11564d20022ab11d2589a8

Multihash encoding:
12 20 41dd7b6443542e75701aa98a0c235951a28a0d851b11564d20022ab11d2589a8

Breaking it down:
┌────┬────┬──────────────────────────────────────────────────────────────┐
│ 12 │ 20 │ 41dd7b6443542e75701aa98a0c235951a28a0d851b11564d20022ab11d2589a8 │
└────┴────┴──────────────────────────────────────────────────────────────┘
  │    │    └─ Digest value (32 bytes)
  │    └────── Digest length: 0x20 = 32 bytes
  └─────────── Hash function: 0x12 = SHA-256
```

### Common Hash Function Codes

| Hash Function | Hex Code | Decimal |
|---------------|----------|---------|
| identity      | 0x00     | 0       |
| sha1          | 0x11     | 17      |
| sha2-256      | 0x12     | 18      |
| sha2-512      | 0x13     | 19      |
| sha3-512      | 0x14     | 20      |
| sha3-384      | 0x15     | 21      |
| blake2b-256   | 0xb220   | varies  |
| blake2b-512   | 0xb240   | varies  |
| keccak-256    | 0x1b     | 27      |

Complete table: [Multicodec Table](https://github.com/multiformats/multicodec/blob/master/table.csv)

### Multiple Digest Lengths Example

The same input `"multihash"` with different hash functions:

#### SHA-1 (20 bytes)
```
11 14 8a173fd3e32c0fa78b90fe42d305f202244e2739
```

#### SHA-256 (32 bytes)
```
12 20 41dd7b6443542e75701aa98a0c235951a28a0d851b11564d20022ab11d2589a8
```

#### SHA-512 (64 bytes)
```
13 40 52eb4dd19f1ec522859e12d89706156570f8fbab1824870bc6f8c7d235eef5f4c2cbbafd365f96fb12b1d98a0334870c2ce90355da25e6a1108a6e17c4aaebb0
```

#### BLAKE2b-512 (64 bytes)
```
c0e402 40 d91ae0cb0e48022053ab0f8f0dc78d28593d0f1c13ae39c9b169c136a779f21a0496337b6f776a73c1742805c1cc15e792ddb3c92ee1fe300389456ef3dc97e2
```

Notice how each includes the function code and length, making them self-describing!

### Unsigned Varint Encoding

Multihash uses **unsigned varints** for efficient encoding of integers:

- Values 0-127: Encoded as a single byte
- Larger values: Use multiple bytes with continuation bits
- Maximum: 9 bytes (2^63 - 1)

Example:
```
Value 18 (0x12) = single byte: 0x12
Value 300      = two bytes: 0xAC 0x02
```

---

## Related Multiformat Protocols

### Multibase

**Multibase** adds self-describing base encodings to values.

Format: `<base-encoding-character><encoded-data>`

Common prefixes:
- `b` = base32
- `z` = base58btc
- `m` = base64
- `f` = base16 (hex)

Example:
```
z4MzquE2q5PN6jjLmvTAKpj4uq  # base58
mEiCTojlxqRTl6svwqNJRVM2j   # base64
```

### Multicodec

**Multicodec** provides self-describing serialization formats.

It uses the same varint code table as Multihash to identify:
- Data serialization formats (JSON, CBOR, Protobuf)
- Network protocols
- Hash functions (shared with Multihash)

### CID (Content Identifier)

**CID** combines multiple Multiformat protocols:

```
<version><multicodec><multihash>
```

Example CID v1:
```
bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi
```

Breaking it down:
- `b` = base32 encoding (Multibase)
- `afy` = CID version 1 + dag-pb codec (Multicodec)
- Rest = Multihash

Used extensively in:
- **IPFS** (InterPlanetary File System)
- **Filecoin**
- **libp2p**

---

## Multihash Workflow

### Creating a Multihash

```
┌─────────────┐
│   Raw Data  │
│ "multihash" │
└──────┬──────┘
       │
       │ 1. Choose hash function (SHA-256)
       ▼
┌─────────────────────────┐
│  Apply Hash Function    │
│  SHA-256("multihash")   │
└──────┬──────────────────┘
       │
       │ 2. Get digest
       ▼
┌──────────────────────────────────────────────────────────┐
│  41dd7b6443542e75701aa98a0c235951a28a0d851b11564d...   │
│  (32 bytes)                                              │
└──────┬───────────────────────────────────────────────────┘
       │
       │ 3. Prepend function code (0x12)
       │ 4. Prepend digest length (0x20)
       ▼
┌──────────────────────────────────────────────────────────┐
│  12 20 41dd7b6443542e75701aa98a0c235951a28a0d851b...   │
│  (Multihash)                                             │
└──────────────────────────────────────────────────────────┘
```

### Verifying Data with Multihash

```
┌────────────────┐      ┌──────────────────┐
│   Raw Data     │      │    Multihash     │
│  "multihash"   │      │  12 20 41dd7b... │
└───────┬────────┘      └─────────┬────────┘
        │                         │
        │                         │ 1. Parse multihash
        │                         ▼
        │               ┌──────────────────┐
        │               │ Extract:         │
        │               │ - Function: 0x12 │
        │               │ - Length: 32     │
        │               │ - Digest: 41dd.. │
        │               └─────────┬────────┘
        │                         │
        │                         │ 2. Identify function (SHA-256)
        ▼                         ▼
┌───────────────────────────────────────┐
│  Hash data with same function         │
│  SHA-256("multihash")                 │
└───────────────┬───────────────────────┘
                │
                │ 3. Compare digests
                ▼
        ┌───────────────────┐
        │  Match? ✓ or ✗    │
        └───────────────────┘
```

---

## Code Examples

### Python Implementation

#### Basic Usage

```python
import hashlib
import multihash

# Create a multihash from data
data = b"multihash"

# Method 1: Using the digest helper function
mh = multihash.digest(data, 'sha2-256')
print(f"Multihash: {mh.hex()}")
# Output: 122041dd7b6443542e75701aa98a0c235951a28a0d851b11564d20022ab11d2589a8

# Method 2: Creating manually
hash_digest = hashlib.sha256(data).digest()
mh = multihash.encode(hash_digest, 'sha2-256')
print(f"Multihash: {mh.hex()}")
```

#### Decoding a Multihash

```python
import multihash

# Decode a multihash
encoded = bytes.fromhex('122041dd7b6443542e75701aa98a0c235951a28a0d851b11564d20022ab11d2589a8')
decoded = multihash.decode(encoded)

print(f"Function: {decoded.name}")      # sha2-256
print(f"Code: 0x{decoded.code:02x}")    # 0x12
print(f"Length: {decoded.length}")      # 32
print(f"Digest: {decoded.digest.hex()}") # 41dd7b...
```

#### Verifying Data

```python
import multihash

data = b"multihash"
mh = multihash.digest(data, 'sha2-256')

# Later, verify the data matches the multihash
is_valid = multihash.is_valid(mh, data)
print(f"Valid: {is_valid}")  # True

# Try with wrong data
wrong_data = b"wrong"
is_valid = multihash.is_valid(mh, wrong_data)
print(f"Valid: {is_valid}")  # False
```

#### Working with Multiple Hash Functions

```python
import multihash

data = b"multihash"

# Create multihashes with different functions
sha1_mh = multihash.digest(data, 'sha1')
sha256_mh = multihash.digest(data, 'sha2-256')
sha512_mh = multihash.digest(data, 'sha2-512')
blake2b_mh = multihash.digest(data, 'blake2b-256')

print(f"SHA-1:   {sha1_mh.hex()}")
print(f"SHA-256: {sha256_mh.hex()}")
print(f"SHA-512: {sha512_mh.hex()}")
print(f"BLAKE2b: {blake2b_mh.hex()}")

# All can be decoded and verified independently
for mh in [sha1_mh, sha256_mh, sha512_mh, blake2b_mh]:
    decoded = multihash.decode(mh)
    print(f"{decoded.name}: {multihash.is_valid(mh, data)}")
```

#### Base Encoding Multihashes

```python
import multihash
import base58

data = b"multihash"
mh = multihash.digest(data, 'sha2-256')

# Encode in different bases
hex_encoded = mh.hex()
base58_encoded = base58.b58encode(mh).decode()
base64_encoded = base64.b64encode(mh).decode()

print(f"Hex:    {hex_encoded}")
print(f"Base58: {base58_encoded}")
print(f"Base64: {base64_encoded}")

# Decode from base58
decoded_bytes = base58.b58decode(base58_encoded)
decoded_mh = multihash.decode(decoded_bytes)
print(f"Decoded function: {decoded_mh.name}")
```

### JavaScript/TypeScript Example

```javascript
import * as multihash from 'multiformats/hashes/digest'
import { sha256 } from 'multiformats/hashes/sha2'

// Create multihash
const data = new TextEncoder().encode('multihash')
const hash = await sha256.digest(data)

console.log('Code:', hash.code)      // 18 (0x12)
console.log('Size:', hash.size)      // 32
console.log('Bytes:', hash.bytes)    // Uint8Array
console.log('Digest:', hash.digest)  // Uint8Array of digest

// Encode to hex
const hex = Array.from(hash.bytes)
  .map(b => b.toString(16).padStart(2, '0'))
  .join('')
console.log('Hex:', hex)
```

### Advanced Python: Custom Hash Function

```python
import multihash
from multihash import Func

# Register a custom hash function
def custom_hash(data):
    # Your custom hashing logic
    import hashlib
    return hashlib.sha3_256(data).digest()

# Use with application-specific code
custom_code = 0x17  # sha3-256
data = b"multihash"

# Create multihash with custom function
digest = custom_hash(data)
mh = multihash.encode(digest, custom_code)

print(f"Custom multihash: {mh.hex()}")

# Decode
decoded = multihash.decode(mh)
print(f"Code: 0x{decoded.code:02x}")
print(f"Length: {decoded.length}")
```

### Real-World Example: File Integrity

```python
import multihash
import hashlib

def create_file_multihash(filepath, hash_function='sha2-256'):
    """Create a multihash for a file"""
    hasher = hashlib.sha256()
    
    with open(filepath, 'rb') as f:
        # Read file in chunks for memory efficiency
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    
    digest = hasher.digest()
    return multihash.encode(digest, hash_function)

def verify_file_multihash(filepath, expected_multihash):
    """Verify a file matches a multihash"""
    # Decode to get hash function
    decoded = multihash.decode(expected_multihash)
    
    # Get hash function name
    hash_func_name = decoded.name
    
    # Map to hashlib function
    hash_func_map = {
        'sha1': hashlib.sha1,
        'sha2-256': hashlib.sha256,
        'sha2-512': hashlib.sha512,
    }
    
    hasher = hash_func_map[hash_func_name]()
    
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    
    computed_digest = hasher.digest()
    return computed_digest == decoded.digest

# Usage
file_mh = create_file_multihash('document.pdf')
print(f"File multihash: {file_mh.hex()}")

# Later verify
is_valid = verify_file_multihash('document.pdf', file_mh)
print(f"File valid: {is_valid}")
```

---

## Practical Use Cases

### 1. **Content-Addressed Storage (IPFS)**

IPFS uses CIDs (which contain multihashes) to address content:

```python
# Each file gets a unique CID based on its content
file_content = b"Hello IPFS"
mh = multihash.digest(file_content, 'sha2-256')

# This multihash becomes part of the CID
# Users can retrieve content by this address
# If content changes, the CID changes
```

### 2. **Blockchain & Distributed Systems**

```python
# Blocks can use different hash functions over time
class Block:
    def __init__(self, data, prev_hash_mh):
        self.data = data
        self.prev_hash = prev_hash_mh
        self.hash = self.calculate_hash()
    
    def calculate_hash(self):
        # Can upgrade hash function without breaking chain
        block_data = f"{self.data}{self.prev_hash}".encode()
        return multihash.digest(block_data, 'sha2-256')
```

### 3. **Package Management**

```python
# Package integrity verification
class Package:
    def __init__(self, name, version, content):
        self.name = name
        self.version = version
        self.content = content
        self.integrity_hash = multihash.digest(content, 'sha2-512')
    
    def verify(self):
        return multihash.is_valid(self.integrity_hash, self.content)
```

### 4. **Git-like Version Control**

```python
# Future-proof commit hashes
class Commit:
    def __init__(self, message, tree, parent=None):
        self.message = message
        self.tree = tree
        self.parent = parent
        self.hash = self.calculate_hash()
    
    def calculate_hash(self):
        commit_data = f"{self.message}{self.tree}".encode()
        # Can migrate from SHA-1 to SHA-256 gradually
        return multihash.digest(commit_data, 'sha2-256')
```

### 5. **Digital Signatures & Certificates**

```python
# Document signing with flexible hash functions
class SignedDocument:
    def __init__(self, content, signature_hash_func='sha2-256'):
        self.content = content
        self.content_hash = multihash.digest(content, signature_hash_func)
        # Signature algorithm knows which hash was used
```

---

## Best Practices

### 1. **Choose Appropriate Hash Functions**

```python
# For cryptographic security
secure_hash = multihash.digest(data, 'sha2-256')  # Good
secure_hash = multihash.digest(data, 'sha2-512')  # Better
secure_hash = multihash.digest(data, 'blake2b-512')  # Modern

# Avoid for security
weak_hash = multihash.digest(data, 'sha1')  # Deprecated
weak_hash = multihash.digest(data, 'md5')   # Broken
```

### 2. **Handle Truncated Hashes Carefully**

```python
# Multihash supports truncated digests
full_hash = multihash.digest(data, 'sha2-512')  # 64 bytes
truncated = multihash.encode(
    hashlib.sha512(data).digest()[:32],  # Only 32 bytes
    'sha2-512'
)

# Length field accurately reflects truncation: 0x20 instead of 0x40
```

### 3. **Store in Binary, Display in Human-Readable**

```python
import multihash
import base58

# Store efficiently
mh_binary = multihash.digest(data, 'sha2-256')
save_to_database(mh_binary)  # Store as bytes

# Display to users
mh_base58 = base58.b58encode(mh_binary)
print(f"Hash: {mh_base58}")  # Human-readable
```

### 4. **Version Your Systems**

```python
class ContentStore:
    def __init__(self, default_hash='sha2-256'):
        self.default_hash = default_hash
    
    def store(self, content):
        # Allow migration to better hash functions
        mh = multihash.digest(content, self.default_hash)
        return mh
    
    def retrieve(self, multihash_key):
        # System works regardless of hash function used
        decoded = multihash.decode(multihash_key)
        # Lookup by multihash...
```

### 5. **Document Hash Function Choices**

```python
# Good: Explicit and documented
class DataRecord:
    """
    Data record with integrity verification.
    
    Uses SHA-256 multihash by default for balance of
    security and performance. Can be upgraded to SHA-512
    or BLAKE2b for higher security requirements.
    """
    def __init__(self, data, hash_func='sha2-256'):
        self.data = data
        self.hash_func = hash_func
        self.integrity_hash = multihash.digest(data, hash_func)
```

### 6. **Validate Before Trusting**

```python
def safe_decode(multihash_bytes):
    """Safely decode and validate multihash"""
    try:
        decoded = multihash.decode(multihash_bytes)
        
        # Check for deprecated functions
        if decoded.name in ['md5', 'sha1']:
            print(f"Warning: Weak hash function {decoded.name}")
        
        # Check digest length is reasonable
        if decoded.length < 16:
            raise ValueError("Digest too short for security")
        
        return decoded
    except Exception as e:
        print(f"Invalid multihash: {e}")
        return None
```

### 7. **Plan for Migration**

```python
class MigratableHashStore:
    def __init__(self):
        self.hashes = {}
        self.migration_target = 'sha2-512'
    
    def add(self, key, data):
        # Store with current best practice
        mh = multihash.digest(data, self.migration_target)
        self.hashes[key] = mh
    
    def migrate_hash(self, key, data):
        """Upgrade old hashes to new function"""
        old_mh = self.hashes[key]
        old_decoded = multihash.decode(old_mh)
        
        if old_decoded.name != self.migration_target:
            # Recompute with new function
            new_mh = multihash.digest(data, self.migration_target)
            self.hashes[key] = new_mh
            return True
        return False
```

---

## Key Takeaways

### What You Need to Remember

1. **Multihash = Self-Describing Hash**: Contains function code + length + digest
2. **TLV Format**: `<function-code><digest-length><digest-value>`
3. **Varint Encoding**: Efficient integer encoding for codes and lengths
4. **Future-Proof**: Allows seamless hash function upgrades
5. **Part of Multiformat Family**: Works with Multibase, Multicodec, CID

### When to Use Multihash

✅ **DO use Multihash when:**
- Building distributed systems
- Content-addressed storage (IPFS, etc.)
- Long-lived data structures
- Cross-system interoperability needed
- Future hash function changes likely

❌ **DON'T use Multihash when:**
- Simple, short-lived scripts
- Performance is absolutely critical (adds 2 bytes overhead)
- All parties agree on a fixed hash function forever
- Legacy system integration requires specific formats

### Common Pitfalls

1. **Not handling varints correctly** - Use proper libraries
2. **Assuming fixed hash lengths** - Always read the length field
3. **Using broken hash functions** - Avoid MD5, SHA-1 for security
4. **Not validating multihash format** - Always decode before trusting
5. **Confusing multihash with multibase** - They're different layers!

---

## Additional Resources

- **Official Specification**: [Multihash Spec](https://github.com/multiformats/multihash)
- **Multiformat Project**: [multiformats.io](https://multiformats.io)
- **Multicodec Table**: [Function Codes](https://github.com/multiformats/multicodec/blob/master/table.csv)
- **IPFS Documentation**: [IPFS Docs](https://docs.ipfs.io)
- **Python Implementation**: [py-multihash](https://github.com/multiformats/py-multihash)
- **JavaScript Implementation**: [js-multiformats](https://github.com/multiformats/js-multiformats)

---

## Conclusion

Multihash is a simple but powerful protocol that solves a critical problem in distributed systems: how to make hash values future-proof. By embedding metadata about the hash function and digest length directly into the hash value itself, systems become more resilient, upgradeable, and interoperable.

As you build systems that need to last, consider using Multihash. Your future self (and the engineers who maintain your code) will thank you!

**Remember**: *The best time to plan for future hash function changes is before you need them.*