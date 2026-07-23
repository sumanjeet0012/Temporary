# py-ipfs-lite API Reference

This document provides a reference for the stable HTTP API endpoints supported by the `py-ipfs-lite` node. The examples target a live node running at `http://52.7.183.75:5001`.

All expected JSON outputs below were verified directly against the live node.

---

## 1. Node Identity & Version

### `POST /api/v0/version`
Returns the software version and system identifier of the daemon.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/version
```

**Actual Output:**
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

**Actual Output:**
```json
{"ID":"12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff","Addresses":["/ip4/0.0.0.0/udp/4001/quic-v1/p2p/12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff","/ip4/0.0.0.0/tcp/4001/ws/p2p/12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff","/ip4/0.0.0.0/tcp/4001/p2p/12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff"]}
```

---

## 2. Swarm (Networking)

### `POST /api/v0/swarm/peers`
Lists all peers the node is currently connected to over the Libp2p network. Unlike Kubo's verbose output, `py-ipfs-lite` returns a simple flat list of connected Peer IDs.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/swarm/peers
```

**Actual Output (Snippet):**
```json
{"count":273,"peers":["12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff","12D3KooWK3TpENqwcYetakPg6QpnEcEk8KqgBzjtrTRotfxuwD9E", "..."]}
```

---

### `POST /api/v0/swarm/connect`
Manually dial and connect to a remote peer using their multiaddr.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/swarm/connect?arg=/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
```

**Actual Output:**
```json
{"Strings":["connect /ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ success"]}
```

---

## 3. Repository Management & Pinning

### `POST /api/v0/repo/stat`
Returns statistics about the IPFS datastore (size, block count, etc.).

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/repo/stat
```

**Actual Output:**
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

**Actual Output:**
```json
{"Key":[]}
```

---

### `POST /api/v0/pin/ls`
Lists all data objects (CIDs) currently pinned to local storage so they are not deleted during garbage collection.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/pin/ls
```

**Actual Output:**
```json
{"Keys":{}}
```
