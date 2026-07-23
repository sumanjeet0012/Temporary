# py-ipfs-lite API Status Report (52.7.200.90)

This document provides a report on the HTTP API endpoints for the old node running at `http://52.7.200.90:5001`. It categorizes the APIs into those that are working (responsive) and those that are hanging or broken.

---

## ✅ Working APIs

These endpoints respond in a timely manner and return the expected IPFS/Kubo compatible data formats.

### `POST /api/v0/version`
Returns the software version of the daemon.
```bash
curl -s -X POST http://52.7.200.90:5001/api/v0/version
```
**Output:** `{"Version":"0.1.1","Commit":"","System":"py-ipfs-lite"}`

---

### `POST /api/v0/id`
Retrieves the node's cryptographic Peer ID and multiaddrs.
```bash
curl -s -X POST http://52.7.200.90:5001/api/v0/id
```
**Output:** `{"ID":"12D3KooW...","Addresses":["/ip4/..."]}`

---

### `POST /api/v0/swarm/peers`
Lists connected peers.
```bash
curl -s -X POST http://52.7.200.90:5001/api/v0/swarm/peers
```
**Output:** `{"count": 273, "peers": ["12D3KooW..."]}`

---

### `POST /api/v0/swarm/connect`
Connect to a remote peer.
```bash
curl -s -X POST "http://52.7.200.90:5001/api/v0/swarm/connect?arg=/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
```

---

### `POST /api/v0/block/put`
Store a raw block.
```bash
curl -s -X POST -F file=@"block.bin" http://52.7.200.90:5001/api/v0/block/put
```

---

### `POST /api/v0/repo/stat`
Returns datastore statistics.
```bash
curl -s -X POST http://52.7.200.90:5001/api/v0/repo/stat
```

---

### `POST /api/v0/repo/gc`
Performs garbage collection.
```bash
curl -s -X POST http://52.7.200.90:5001/api/v0/repo/gc
```

---

### `POST /api/v0/pin/ls`
Lists pinned objects.
```bash
curl -s -X POST http://52.7.200.90:5001/api/v0/pin/ls
```

---

### `POST /api/v0/debug/peerstore`
Dump peerstore data.
```bash
curl -s -X POST http://52.7.200.90:5001/api/v0/debug/peerstore
```

---

### `GET /debug/conns`
Get total active connections.
```bash
curl -s http://52.7.200.90:5001/debug/conns
```

---

## ❌ Not Working APIs (Timed out / Hanging)

The following endpoints hang indefinitely or time out on this specific node, likely due to proxy blocking or a bug in the multipart upload chunking code inside `py-ipfs-lite`'s `files_service`.

### `POST /api/v0/add`
**Purpose:** Adds a file to IPFS.
**Command:** 
```bash
curl -s -X POST -F file=@"hello.txt" http://52.7.200.90:5001/api/v0/add
```
**Status:** Request times out without receiving a response.

---

### `POST /api/v0/cat`
**Purpose:** Fetches a file by its CID.
**Command:** 
```bash
curl -s -X POST "http://52.7.200.90:5001/api/v0/cat?arg=QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
```
**Status:** Request times out without receiving a response.
