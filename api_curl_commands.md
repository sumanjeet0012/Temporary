# py-ipfs-lite Complete API Reference

This document provides a comprehensive reference for all stable HTTP API endpoints currently supported by the `py-ipfs-lite` node. 
The examples target a live node running at `http://52.7.183.75:5001`. 

> **Note:** Some endpoints like `/api/v0/add` and `/api/v0/cat` may hang on certain EC2 deployments due to unchunked stream timeouts or proxy limitations, but they are fully implemented in the daemon.

---

## 1. Node Identity & Version

### `POST /api/v0/version`
Returns the software version and system identifier of the daemon.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/version
```

**Expected JSON Response:**
```json
{"Version":"0.1.1","Commit":"","System":"py-ipfs-lite"}
```

---

### `POST /api/v0/id`
Retrieves the node's cryptographic Peer ID, public key, and active listening addresses (multiaddrs).

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/id
```

**Expected JSON Response:**
```json
{"ID":"12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff","Addresses":["/ip4/0.0.0.0/udp/4001/quic-v1/p2p/12D3KooWSb6D54jy..."]}
```

---

## 2. Swarm (Networking)

### `POST /api/v0/swarm/peers`
Lists all peers the node is currently connected to over the Libp2p network. (Returns a flat list of IDs).

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/swarm/peers
```

**Expected JSON Response:**
```json
{"count": 273, "peers": ["12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff", "..."]}
```

---

### `POST /api/v0/swarm/connect`
Manually dial and connect to a remote peer using their multiaddr.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/swarm/connect?arg=/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
```

**Expected JSON Response:**
```json
{"Strings": ["connect /ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ success"]}
```

---

### `POST /api/v0/swarm/disconnect`
Disconnect from a remote peer using their multiaddr.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/swarm/disconnect?arg=/ip4/104.131.131.82/tcp/4001/p2p/QmaCp..."
```

**Expected JSON Response:**
```json
{"Strings": ["disconnect /ip4/104.131.131.82/tcp/4001/p2p/QmaCp... success"]}
```

---

## 3. Core IPFS (Adding and Fetching Data)

### `POST /api/v0/add`
Adds a file or data stream to IPFS, pins it locally, and returns its CID.

**cURL Command:**
```bash
curl -s -X POST -F file=@"hello.txt" http://52.7.183.75:5001/api/v0/add
```

**Expected JSON Response:**
```json
{"Name": "hello.txt", "Hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG", "Size": "12"}
```

---

### `POST /api/v0/cat`
Fetches the contents of an IPFS object (file) by its CID.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/cat?arg=QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
```

**Expected Result (Raw Content):**
```text
Hello World!
```

---

## 4. DAG & Blocks (Low-level Data)

### `POST /api/v0/dag/put`
Store an IPLD DAG node.

**cURL Command:**
```bash
curl -s -X POST -F file=@"dag.json" http://52.7.183.75:5001/api/v0/dag/put
```

**Expected JSON Response:**
```json
{"Cid": {"/": "bafyreib...var"}}
```

---

### `POST /api/v0/block/put`
Store a raw block.

**cURL Command:**
```bash
curl -s -X POST -F file=@"block.bin" http://52.7.183.75:5001/api/v0/block/put
```

**Expected JSON Response:**
```json
{"Key": "b'\\x01U\\x12...'", "Size": 128}
```

---

### `POST /api/v0/block/stat`
Get statistics of a raw block.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/block/stat?arg=QmYwAPJzv..."
```

**Expected JSON Response:**
```json
{"Key": "QmYwAPJzv...", "Size": 128}
```

---

### `POST /api/v0/block/rm`
Remove a raw block.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/block/rm?arg=QmYwAPJzv..."
```

**Expected JSON Response:**
```json
{"Hash": "QmYwAPJzv...", "Error": ""}
```

---

## 5. Repository Management & Pinning

### `POST /api/v0/repo/stat`
Returns statistics about the IPFS datastore (size, block count, etc.).

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/repo/stat
```

**Expected JSON Response:**
```json
{"NumObjects":1,"RepoSize":13,"RepoPath":".py_ipfs_lite/blocks","Version":"1"}
```

---

### `POST /api/v0/repo/gc`
Performs garbage collection, sweeping unpinned blocks.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/repo/gc
```

**Expected JSON Response:**
```json
{"Key": []}
```

---

### `POST /api/v0/pin/ls`
Lists all data objects (CIDs) currently pinned to local storage.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/pin/ls
```

**Expected JSON Response:**
```json
{"Keys": {}}
```

---

### `POST /api/v0/pin/add`
Pins an object to local storage, preventing it from being garbage collected.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/pin/add?arg=QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
```

**Expected JSON Response:**
```json
{"Pins": ["QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"]}
```

---

## 6. IPNS (Naming)

### `POST /api/v0/name/publish`
Publish an IPNS record.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/name/publish?arg=QmYwAPJzv..."
```

**Expected JSON Response:**
```json
{"Name": "12D3Koo...", "Value": "/ipfs/QmYwAPJzv..."}
```

---

### `POST /api/v0/name/resolve`
Resolve an IPNS name.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/name/resolve?arg=12D3Koo..."
```

**Expected JSON Response:**
```json
{"Path": "/ipfs/QmYwAPJzv..."}
```

---

## 7. Debugging

### `GET /debug/conns`
Get total connections count.

**cURL Command:**
```bash
curl -s http://52.7.183.75:5001/debug/conns
```

**Expected JSON Response:**
```json
{"total_connections": 273}
```

---

### `POST /api/v0/debug/peerstore`
Dump peerstore data.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/debug/peerstore
```

**Expected JSON Response:**
```json
{"count": 100, "peers": ["12D3Koo...", "..."]}
```
