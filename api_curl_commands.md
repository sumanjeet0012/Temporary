# py-ipfs-lite API Reference

This document provides a reference for the stable HTTP API endpoints supported by the `py-ipfs-lite` node. The examples target a live node running at `http://52.7.183.75:5001`.

Most endpoints are compatible with the official IPFS RPC API specification (Kubo).

---

## 1. Node Identity & Version

### `POST /api/v0/version`
Returns the software version and system identifier of the daemon.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/version
```

**Expected Result:**
```json
{
  "Version": "0.1.1",
  "Commit": "",
  "System": "py-ipfs-lite"
}
```

---

### `POST /api/v0/id`
Retrieves the node's cryptographic Peer ID, public key, and active listening addresses (multiaddrs).

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/id
```

**Expected Result:**
```json
{
  "ID": "12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff",
  "Addresses": [
    "/ip4/0.0.0.0/udp/4001/quic-v1/p2p/12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff",
    "/ip4/0.0.0.0/tcp/4001/ws/p2p/12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff",
    "/ip4/0.0.0.0/tcp/4001/p2p/12D3KooWSb6D54jyNPwaVPHhX11htWscpWmzuV5wrRH7sbRUj4ff"
  ]
}
```

---

## 2. Swarm (Networking)

### `POST /api/v0/swarm/peers`
Lists all peers the node is currently connected to over the Libp2p network.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/swarm/peers
```

**Expected Result:**
```json
{
  "Peers": [
    {
      "Peer": "12D3KooWQkhEVFkPvf5U93wRFfn88mC6n8JFfp1XARhMKqyyXEoA",
      "Address": "/ip4/142.93.81.164/tcp/4001",
      "Direction": "Inbound"
    },
    ...
  ]
}
```

---

### `POST /api/v0/swarm/connect`
Manually dial and connect to a remote peer using their multiaddr.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/swarm/connect?arg=/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
```

**Expected Result:**
```json
{
  "Strings": [
    "connect QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ success"
  ]
}
```

---

## 3. Core IPFS (Adding and Fetching Data)

### `POST /api/v0/add`
Adds a file or data stream to IPFS, pins it locally, and returns its CID (Content Identifier).

**cURL Command:**
```bash
curl -s -X POST -F file=@"hello.txt" http://52.7.183.75:5001/api/v0/add
```

**Expected Result:**
```json
{
  "Name": "hello.txt",
  "Hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
  "Size": "12"
}
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

## 4. Pinning (Data Persistence)

### `POST /api/v0/pin/ls`
Lists all data objects (CIDs) currently pinned to local storage so they are not deleted during garbage collection.

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/pin/ls
```

**Expected Result:**
```json
{
  "Keys": {
    "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG": {
      "Type": "recursive"
    }
  }
}
```

---

### `POST /api/v0/pin/add`
Pins an object to local storage, preventing it from being garbage collected.

**cURL Command:**
```bash
curl -s -X POST "http://52.7.183.75:5001/api/v0/pin/add?arg=QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
```

**Expected Result:**
```json
{
  "Pins": [
    "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
  ]
}
```

---

## 5. Repository Management

### `POST /api/v0/repo/stat`
Returns statistics about the IPFS datastore (size, block count, etc.).

**cURL Command:**
```bash
curl -s -X POST http://52.7.183.75:5001/api/v0/repo/stat
```

**Expected Result:**
```json
{
  "RepoSize": 10485760,
  "StorageMax": 10737418240,
  "NumObjects": 145,
  "RepoPath": "/home/user/.py_ipfs_lite",
  "Version": "12"
}
```
