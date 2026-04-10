# p2pCalc — Deep Dive: From EtherCalc to Decentralized P2P Spreadsheets

> **Source:** https://github.com/yashksaini-coder/p2pCalc  
> **Stack:** Python 3.10+, py-libp2p, Trio, Starlette/Hypercorn, SQLite, EtherCalc (Node.js)

---

## Table of Contents

1. [What Was EtherCalc?](#1-what-was-ethercalc)
2. [The Problem with EtherCalc's Architecture](#2-the-problem-with-ethercalcs-architecture)
3. [What is p2pCalc?](#3-what-is-p2pcalc)
4. [High-Level Architecture](#4-high-level-architecture)
5. [The Three Processes Per Peer](#5-the-three-processes-per-peer)
6. [libp2p in p2pCalc — Deep Focus](#6-libp2p-in-p2pcalc--deep-focus)
   - 6.1 [The libp2p Host](#61-the-libp2p-host)
   - 6.2 [Transport: WebSocket](#62-transport-websocket)
   - 6.3 [Peer Identity: secp256k1 Keys](#63-peer-identity-secp256k1-keys)
   - 6.4 [GossipSub — Real-Time Edit Broadcast](#64-gossipsub--real-time-edit-broadcast)
   - 6.5 [Custom Stream Protocol — State Sync](#65-custom-stream-protocol--state-sync)
   - 6.6 [mDNS Discovery — LAN Auto-Connect](#66-mdns-discovery--lan-auto-connect)
   - 6.7 [Kademlia DHT — WAN Discovery](#67-kademlia-dht--wan-discovery)
   - 6.8 [Trio: The Async Runtime Glue](#68-trio-the-async-runtime-glue)
7. [The Adapter — The P2P Bridge](#7-the-adapter--the-p2p-bridge)
8. [Data Flows — Step by Step](#8-data-flows--step-by-step)
   - 8.1 [Local Edit Flow](#81-local-edit-flow)
   - 8.2 [Remote Edit Flow](#82-remote-edit-flow)
   - 8.3 [Late Join / Reconnect Flow](#83-late-join--reconnect-flow)
   - 8.4 [mDNS Auto-Discovery Flow](#84-mdns-auto-discovery-flow)
9. [The OperationMessage Format](#9-the-operationmessage-format)
10. [Conflict Resolution: Last-Write-Wins](#10-conflict-resolution-last-write-wins)
11. [Persistence: SQLite Schema](#11-persistence-sqlite-schema)
12. [Module Map and Responsibilities](#12-module-map-and-responsibilities)
13. [Port Layout](#13-port-layout)
14. [Startup Sequence](#14-startup-sequence)
15. [EtherCalc vs p2pCalc: Side-by-Side Comparison](#15-ethercalc-vs-p2pcalc-side-by-side-comparison)
16. [Key Design Decisions](#16-key-design-decisions)

---

## 1. What Was EtherCalc?

EtherCalc is a **collaborative, web-based spreadsheet** built on top of SocialCalc (a JavaScript spreadsheet engine originally created by Dan Bricklin, the inventor of VisiCalc). It was designed so multiple users could edit the same spreadsheet simultaneously in their browsers and see each other's changes in real time.

### How EtherCalc Works Internally

EtherCalc runs as a **Node.js server**. The server does the following:

- Serves the SocialCalc browser UI (HTML/CSS/JS) to connected browsers.
- Maintains the **authoritative in-memory state** of each spreadsheet (called a "sheet").
- Exposes a **REST API** at `/_/{sheet_id}` for reading and writing cell data.
- Opens a **WebSocket connection** to every connected browser for real-time bidirectional sync.

When user Alice types `42` into cell `A1`, this is what happens in vanilla EtherCalc:

```
Browser (Alice)
  → WebSocket frame: "set A1 value n 42"
  → EtherCalc Server (central)
    → Updates in-memory cell model
    → Broadcasts via WebSocket to all connected browsers (Bob, Carol, etc.)
Browser (Bob) receives the update and re-renders A1
```

The **central EtherCalc server** is the single source of truth. Every client reads from it, every write goes through it, and every broadcast comes from it. This is a classic hub-and-spoke model.

### EtherCalc's Persistence

EtherCalc by default uses **Redis** for persistence. The sheet state is serialized as a SocialCalc "serialization" string, a text format that encodes all cell values, formulas, formats, and column/row metadata.

### EtherCalc's REST API (used by p2pCalc)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/_/{sheet_id}` | Return the full sheet as a SocialCalc serialization string |
| `PUT` | `/_/{sheet_id}` | Replace the entire sheet with a new SocialCalc serialization |
| `POST` | `/_/{sheet_id}` | Execute a SocialCalc command (e.g., `set A1 value n 42`) |
| `GET` | `/_/{sheet_id}/cells/{cell}` | Read a single cell value |

p2pCalc uses these endpoints extensively and treats EtherCalc purely as a **local dumb storage engine** — stripping it of any sync or broadcast role.

---

## 2. The Problem with EtherCalc's Architecture

EtherCalc's design has a fundamental structural dependency: **the central server**. Every peer's browser must reach that server. If the server dies:

- No new edits can be saved.
- No updates are broadcast.
- The entire collaborative session stops.

Additional consequences of centralization:

- **Single point of failure**: One crashed Node.js process kills collaboration for everyone.
- **Single point of trust**: Whoever runs the server controls the data.
- **No offline resilience**: Disconnect from the server, lose your ability to sync.
- **No P2P model**: Two users on the same LAN still route all traffic through a remote server.
- **Scalability ceiling**: All WebSocket connections and sync load fall on one process.

p2pCalc's thesis is: the **real value** of EtherCalc is SocialCalc's in-browser rendering engine and REST API. The central sync server can be **replaced entirely with a libp2p GossipSub mesh**, and users get all the same UI with none of the centralization.

---

## 3. What is p2pCalc?

p2pCalc is a **Python layer** that wraps EtherCalc and makes it behave as a peer in a decentralized mesh network. Each user running p2pCalc:

1. Runs their own EtherCalc instance **locally** (in Docker or via npm).
2. Runs the p2pCalc **Adapter** process, which their browser talks to instead of EtherCalc directly.
3. Connects to other peers via **py-libp2p**.

The EtherCalc UI and REST API remain completely unchanged. The browser has no idea it's connected to a P2P system — it just talks to the Adapter as if it were a normal EtherCalc server.

**Core capabilities added by p2pCalc:**

- Real-time broadcast of cell edits via **GossipSub pubsub**.
- Automatic peer discovery on LAN via **mDNS**.
- Peer discovery across the internet via **Kademlia DHT**.
- Full state sync for late-joining peers via a **custom libp2p stream protocol**.
- Conflict-safe merging of concurrent edits using **Last-Write-Wins (LWW)**.
- Offline resilience via **SQLite** persistence.

---

## 4. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         PEER A (your machine)                        │
│                                                                      │
│  ┌─────────┐    HTTP      ┌──────────────────┐    HTTP    ┌────────┐│
│  │ Browser │◄────────────►│  Adapter :8001   │◄──────────►│  EC    ││
│  │(SocialC)│              │ (Starlette/ASGI) │            │ :8000  ││
│  └─────────┘              └────────┬─────────┘            │(Node.js││
│                                    │                       │+Redis) ││
│                                    │publish/subscribe      └────────┘│
│                                    ▼                                  │
│                        ┌───────────────────────┐                     │
│                        │  libp2p Host :9000/ws  │                     │
│                        │  ┌─────────────────┐  │                     │
│                        │  │   GossipSub     │  │                     │
│                        │  │ /p2pcalc/sheet/ │  │                     │
│                        │  │   {sheet_id}    │  │                     │
│                        │  └────────┬────────┘  │                     │
│                        │           │            │                     │
│                        │  ┌────────────────┐   │                     │
│                        │  │  Sync Stream   │   │                     │
│                        │  │/p2pcalc/sync/  │   │                     │
│                        │  │   1.0.0        │   │                     │
│                        │  └────────────────┘   │                     │
│                        └──────────┬────────────┘                     │
│                                   │ WebSocket                        │
│                         ┌─────────┴─────────┐                        │
│                         │   mDNS 224.0.0.251│ ← LAN peer discovery   │
│                         └───────────────────┘                        │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ libp2p WebSocket
                    ┌──────────────┴───────────────┐
                    │          P2P MESH             │
                    │  Peer B ◄───────────► Peer C  │
                    │    │                    │     │
                    │  Peer D ◄──────────── Peer E  │
                    └──────────────────────────────┘
```

Key principle: **the browser only ever talks to the Adapter**. EtherCalc and libp2p are internal implementation details invisible to the user.

---

## 5. The Three Processes Per Peer

Every p2pCalc peer runs exactly three co-operating services:

### Process 1: EtherCalc (`:8000`)

- A Node.js process, typically in a Docker container.
- Serves the SocialCalc browser UI.
- Maintains cell state in Redis (inside the container).
- **Completely unmodified** — p2pCalc never touches EtherCalc's source.
- Accessed only by the Adapter, never directly by the browser.

### Process 2: Adapter (`:8001`)

- A Python **Starlette ASGI app** served by Hypercorn (with Trio as the async worker).
- Acts as a **reverse proxy** sitting between the browser and EtherCalc.
- Intercepts `POST /_/{sheet_id}` requests (cell edits).
- On every intercepted edit: runs LWW check → saves to SQLite → broadcasts via GossipSub.
- On every inbound GossipSub message: deduplicates → resolves conflict → POSTs to local EtherCalc.

### Process 3: libp2p Host (`:9000`)

- A Python **py-libp2p** host listening on WebSocket transport.
- Runs GossipSub and the custom sync stream protocol.
- Handles mDNS and optionally Kademlia DHT discovery.

All three processes run **inside the same Python process**, composed together by Trio's structured concurrency. They don't communicate via network — the Adapter holds direct references to the libp2p node and GossipSub publisher.

---

## 6. libp2p in p2pCalc — Deep Focus

This is the core of the project. Here's every way libp2p is used.

### 6.1 The libp2p Host

In py-libp2p, a "host" is the central object that combines transport, security, muxing, and protocol dispatch. In p2pCalc, the host is created in `p2p_node.py` with:

- A **secp256k1 key pair** for identity (loaded from disk or generated fresh).
- A **WebSocket TCP transport** listener.
- **GossipSub** as the pubsub router.
- A **stream handler** registered for the sync protocol ID.

```python
# Conceptual — what p2p_node.py does
host = new_node(
    key_pair=load_or_generate_secp256k1_key(data_dir),
    transport=TCP_WebSocket(port=libp2p_port),
    pubsub=GossipSub(params=GOSSIPSUB_PARAMS),
)
host.set_stream_handler("/p2pcalc/sync/1.0.0", handle_sync_request)
```

The host's **Peer ID** is derived cryptographically from the public key. It looks like:

```
16Uiu2HAm7Qwe4Zxn7odaYTBbX94y3uWrBXdGh5zPbFXDscFG4rZx
```

This Peer ID is stable across restarts (because the key is saved to disk in `{data_dir}/`), and it serves double duty as the **tiebreaker in LWW conflict resolution** (lexicographic comparison of Peer ID strings).

### 6.2 Transport: WebSocket

p2pCalc uses the **TCP WebSocket transport** exclusively:

```
Multiaddr: /ip4/0.0.0.0/tcp/9000/ws
```

Why WebSocket and not raw TCP? Because the EtherCalc frontend is already browser-based, and browsers can only open WebSocket connections (not raw TCP). In a future scenario where the browser itself becomes a peer (e.g., using `js-libp2p`), WebSocket transport is the only option. Using it consistently also simplifies firewall and proxy rules.

When a peer connects to another, the full multiaddr looks like:

```
/ip4/192.168.1.5/tcp/9000/ws/p2p/16Uiu2HAm...
```

The `/p2p/{PeerID}` suffix is a libp2p convention that allows the dialer to verify the remote peer's identity after the TLS/Noise handshake, preventing MITM attacks.

### 6.3 Peer Identity: secp256k1 Keys

py-libp2p generates an **secp256k1 key pair** for each peer (the same curve used by Bitcoin and Ethereum). This key is persisted to `{data_dir}/` so the peer always has the same ID across restarts.

The key serves three purposes in p2pCalc:

1. **libp2p identity** — the Peer ID in all protocol handshakes.
2. **GossipSub message signing** — every published message is signed by the publisher's private key.
3. **LWW tiebreaking** — the Peer ID string is used as a deterministic tiebreaker when two peers write to the same cell at the exact same millisecond.

### 6.4 GossipSub — Real-Time Edit Broadcast

GossipSub is the **pubsub protocol** at the heart of p2pCalc's real-time sync. It is a mesh-based gossip protocol defined in the libp2p spec (`/meshsub/1.1.0`).

#### How GossipSub Works (briefly)

In GossipSub, peers organize into a **mesh** for each topic. The mesh is a sparse overlay where each peer maintains `D` (degree) bidirectional connections to other peers subscribed to the same topic. When a peer publishes a message:

1. It sends the full message to all its mesh peers (eager push).
2. It also gossips **message IDs** (not full messages) to non-mesh peers (lazy push).
3. Non-mesh peers that see a new message ID they haven't received can **pull** the full message.

This hybrid eager+lazy approach ensures both low latency (mesh peers get it immediately) and resilience (gossip ensures eventual delivery even if some mesh links fail).

#### GossipSub in p2pCalc

**Topic naming:** Each sheet gets its own topic:

```
/p2pcalc/sheet/{sheet_id}
```

For example, a sheet named `demo` uses the topic `/p2pcalc/sheet/demo`. This means peers only receive messages for sheets they are actually collaborating on. Different teams using different sheet IDs are completely isolated.

**GossipSub parameters** (from `config.py`):

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `degree` (D) | 6 | Target number of mesh peers per topic |
| `degree_low` (D_low) | 4 | If mesh drops below this, graft new peers |
| `degree_high` (D_high) | 8 | If mesh exceeds this, prune peers |
| `heartbeat_interval` | 1 second | How often mesh maintenance runs |
| `time_to_live` | 60 | Maximum number of hops a message travels |
| `gossip_window` | 3 | How many recent heartbeats to include in IHAVE messages |
| `gossip_history` | 5 | How many heartbeat ticks of message IDs to retain |

The `D=6` target means that in a 10-peer network, each peer is directly meshed with 6 others, achieving robust delivery with only 6 direct connections.

**Publishing an edit:**

When the Adapter intercepts a `POST /_/{sheet_id}` from the browser:

```python
# Inside adapter.py handle_post_command
op_msg = OperationMessage(
    op_id=str(uuid4()),
    peer_id=self.host.get_id(),
    timestamp=time.time(),
    sheet_id=sheet_id,
    command=command,        # e.g. "set A1 value n 42"
    cell_ref=extract_cell_ref(command),  # e.g. "A1"
    msg_type="OPERATION",
)
await self.pubsub.publish(
    topic_id=f"/p2pcalc/sheet/{sheet_id}",
    data=json.dumps(op_msg.to_dict()).encode("utf-8"),
)
```

**Receiving a remote edit:**

The Adapter registers a callback with the GossipSub subscription. When a message arrives:

```python
async def on_remote_message(msg: GossipSub.Message) -> None:
    op = OperationMessage.from_json(msg.data)
    if op.op_id in dedup_cache:
        return  # already seen
    dedup_cache.add(op.op_id)
    if conflict_resolver.should_accept(op):
        await httpx_client.post(
            f"http://localhost:{ethercalc_port}/_/{op.sheet_id}",
            content=op.command,
        )
        persistence.save_op(op)
        conflict_resolver.update(op)
```

The dedup cache is an **LRU of 10,000 op IDs**. This is necessary because GossipSub can deliver the same message multiple times (from different mesh peers), and because the originating peer's own published message bounces back to it.

#### Why GossipSub over simpler approaches?

Alternatives like raw TCP broadcast or WebSocket broadcast have well-known problems:

- A simple "broadcast to all peers you know" approach requires knowing all peers (full mesh), which doesn't scale.
- It has no deduplication, no ordering guarantees, no resilience to churn.

GossipSub provides all of this: partial mesh (scales to thousands of peers), built-in dedup via message IDs, message signing, and flood-fill fallback for reliability.

### 6.5 Custom Stream Protocol — State Sync

GossipSub is great for real-time streaming of new edits, but it doesn't help a **late-joining peer** catch up on everything it missed. For that, p2pCalc defines a custom **request/response stream protocol**:

```
Protocol ID: /p2pcalc/sync/1.0.0
```

This protocol uses libp2p's **streams** — lightweight bidirectional byte channels multiplexed over a single connection. Unlike GossipSub messages (which are fire-and-forget broadcasts), a stream is a **direct point-to-point channel** between two specific peers.

#### The Sync Protocol Flow

```
New Peer (requester)                 Existing Peer (responder)
      │                                      │
      │  open stream /p2pcalc/sync/1.0.0     │
      │─────────────────────────────────────►│
      │                                      │
      │  {"type":"STATE_REQUEST",            │
      │   "sheet_id":"my-sheet"}             │
      │─────────────────────────────────────►│
      │                                      │  GET /_/my-sheet  →  EtherCalc
      │                                      │  SELECT * FROM op_log
      │                                      │   WHERE sheet_id='my-sheet'
      │                                      │   ORDER BY timestamp DESC
      │                                      │   LIMIT 200
      │                                      │
      │  {"type":"STATE_RESPONSE",           │
      │   "snapshot": "<full SocialCalc>",   │
      │   "op_log_tail": [...200 ops...]}    │
      │◄─────────────────────────────────────│
      │                                      │
      │  PUT /_/my-sheet  →  local EtherCalc │
      │  (apply snapshot)                    │
      │                                      │
      │  replay op_log_tail in timestamp     │
      │  order, skipping already-known ops   │
      │                                      │
```

The responder fetches the snapshot via `GET /_/{sheet_id}` from its own local EtherCalc and the last 200 operations from SQLite. It returns both in a single JSON message over the stream.

The requester first applies the snapshot (via `PUT`), which replaces the entire sheet, then replays the op log tail in timestamp order, applying each op via `POST` — but skipping any `op_id` already in its local SQLite (to avoid double-application).

The 200-op tail is an empirically chosen window. For most real-world sessions, 200 operations cover all edits in a typical offline absence. For long-running sheets, the snapshot carries all state regardless of how many ops have been made.

**When is sync triggered?**

- On startup when `--connect /ip4/.../tcp/9000/ws/p2p/<ID>` is provided.
- When `/connect <multiaddr>` is typed in the CLI.
- Automatically when mDNS discovers a new peer on the LAN.
- Automatically when DHT discovery finds a new peer.

### 6.6 mDNS Discovery — LAN Auto-Connect

mDNS (multicast DNS) allows peers on the same local network to find each other with zero configuration. p2pCalc uses py-libp2p's `libp2p.discovery.mdns` module, which in turn uses the `zeroconf` Python library.

#### How It Works

Each peer broadcasts a `_p2p._udp.local.` DNS service record via UDP multicast to `224.0.0.251:5353` (the standard mDNS multicast address). This record contains the peer's ID and port. Every other peer on the same LAN receives this record via multicast and learns the new peer's contact details.

```
Peer A broadcasts:
  _p2p._udp.local.  TXT  PeerID=16Uiu2HAm...  Port=9000

Peer B (on same LAN) receives this via multicast:
  → discovers Peer A
  → connects to /ip4/192.168.1.5/tcp/9000/ws
  → requests state sync
```

#### The Thread-Bridging Problem

zeroconf runs its discovery callbacks in a **background OS thread**, not inside Trio's event loop. This is a classic concurrency mismatch: you can't call `await` from a non-Trio thread.

p2pCalc solves this using a `trio.MemoryChannel` as a thread-safe queue:

```python
# In the zeroconf callback (runs in a background thread)
def on_service_added(info: ServiceInfo) -> None:
    peer_info = PeerInfo(...)
    trio.from_thread.run_sync(send_channel.send_nowait, peer_info)

# In a Trio task (runs in the event loop)
async def discovery_consumer(receive_channel):
    async for peer_info in receive_channel:
        addr = fix_ws_multiaddr(peer_info.addrs[0])  # append /ws
        await host.connect(addr)
        await request_state_sync(peer_info.peer_id)
```

#### The /ws Multiaddr Fix

py-libp2p's mDNS module constructs discovered multiaddrs as TCP-only:

```
/ip4/192.168.1.5/tcp/9000
```

But p2pCalc listens on WebSocket, not raw TCP. The discovery handler explicitly appends `/ws` before connecting:

```
Discovered:    /ip4/192.168.1.5/tcp/9000
After fix:     /ip4/192.168.1.5/tcp/9000/ws
```

This is a small but essential fix — without it, the connection attempt would fail because the remote peer's libp2p host only knows how to speak WebSocket on that port.

### 6.7 Kademlia DHT — WAN Discovery

For peers **across the internet** (not on the same LAN), p2pCalc optionally enables the **Kademlia DHT** via `--dht`. This is the same DHT used by IPFS for content routing.

In Kademlia, the keyspace is a 256-bit space and peers/values are addressed by their XOR distance. p2pCalc uses the DHT for **provider records**: each peer advertises itself as a "provider" of the key `sha256("/p2pcalc/sheet/{sheet_id}")`. Other peers looking for collaborators on the same sheet perform a DHT lookup on the same key and find the peers who advertised.

```
Peer A (on cloud VM):
  uv run p2pcalc --dht --sheet demo

Peer B (on home machine):
  uv run p2pcalc --dht --sheet demo \
    --bootstrap /ip4/<PEER_A_IP>/tcp/9000/ws/p2p/<PEER_A_ID>
```

Peer B uses the `--bootstrap` address to enter the DHT, then performs a content-routing lookup for the sheet ID key to find Peer A and any other peers working on `demo`.

DHT uses **random walk** for routing table refresh: periodically, the peer generates a random key and routes a `FIND_NODE` query toward it, filling in any unknown closer peers along the way.

mDNS and DHT work **side by side**: LAN peers are found instantly via mDNS (zero round trips), while WAN peers are discovered through DHT routing (a few round trips but globally reachable).

### 6.8 Trio: The Async Runtime Glue

py-libp2p is built on **Trio**, not asyncio. This is not an implementation detail you can ignore — it's a hard constraint that shapes everything.

Trio is a structured-concurrency async runtime. Its key property is that all async tasks live in an explicit tree: every task has a parent nursery that owns its lifetime. This makes error propagation and cancellation completely predictable.

In p2pCalc, the entire application is a single Trio program. The startup sequence in `main.py` opens a nursery and spawns all long-running tasks:

```python
async def main_async(config):
    async with trio.open_nursery() as nursery:
        nursery.start_soon(run_libp2p_host, host)        # libp2p event loop
        nursery.start_soon(run_pubsub, pubsub)           # GossipSub heartbeat
        nursery.start_soon(run_mdns_consumer, channel)   # mDNS bridge consumer
        nursery.start_soon(run_hypercorn, adapter_app)   # HTTP adapter server
        nursery.start_soon(run_cli, host, pubsub)        # interactive CLI
```

Hypercorn (the ASGI server) has a Trio worker backend, so the HTTP adapter runs natively inside the same Trio nursery as libp2p — no threads, no asyncio bridging, just structured concurrency.

---

## 7. The Adapter — The P2P Bridge

The Adapter (`adapter.py`) is a **Starlette ASGI application** that does three distinct things:

### Route 1: `GET /_p2pcalc/peer-id`

Returns the libp2p Peer ID as plain text. Used by `demo.sh` to auto-discover Peer A's ID before launching Peer B with `--connect`.

### Route 2: `POST /_/{sheet_id}` — The Core Intercept

This is the path the browser sends every cell edit through (e.g., `set A1 value n 42`). The Adapter:

1. Forwards the POST body to local EtherCalc (`http://127.0.0.1:8000/_/{sheet_id}`).
2. Creates an `OperationMessage` with a fresh UUID, the current timestamp, and the Peer ID.
3. Runs LWW check (should it accept its own edit? Almost always yes — unless somehow a concurrent remote write with a newer timestamp arrived first).
4. Saves the op to SQLite `op_log`.
5. Publishes the `OperationMessage` as JSON to GossipSub.
6. Returns `200 OK` to the browser (the browser never waits for P2P propagation).

### Route 3: Everything Else — Transparent Proxy

All other HTTP requests (serving the SocialCalc UI, WebSocket upgrades for live browser sync within EtherCalc, static assets, etc.) are forwarded transparently to local EtherCalc using `httpx` in async proxy mode.

The browser has no idea it's not talking to a real EtherCalc server. The UI renders identically.

---

## 8. Data Flows — Step by Step

### 8.1 Local Edit Flow

```
User types "42" in cell A1 in browser
        │
        ▼
Browser: POST http://localhost:8001/_/my-sheet
         body: "set A1 value n 42"
        │
        ▼
Adapter: intercepts POST /_/{sheet_id}
  1. httpx.post("http://localhost:8000/_/my-sheet", "set A1 value n 42")
     → EtherCalc updates its in-memory state, returns 200
  2. op = OperationMessage(
         op_id=uuid4(),
         peer_id="16Uiu2HAm...",
         timestamp=1711468800.123,
         sheet_id="my-sheet",
         command="set A1 value n 42",
         cell_ref="A1",
     )
  3. conflict_resolver.should_accept(op)  → True
  4. persistence.save_op(op)             → INSERT INTO op_log
  5. pubsub.publish("/p2pcalc/sheet/my-sheet", json(op))
  6. return 200 to browser
        │
        ▼
GossipSub mesh: message propagates to all subscribed peers
```

### 8.2 Remote Edit Flow

```
Peer B's GossipSub delivers a message to Peer A's on_remote_message callback
        │
        ▼
on_remote_message(msg):
  1. op = OperationMessage.from_json(msg.data)
  2. if op.op_id in dedup_cache: return   ← 10k LRU cache check
  3. dedup_cache.add(op.op_id)
  4. if not conflict_resolver.should_accept(op): return  ← LWW check
  5. httpx.post("http://localhost:8000/_/my-sheet", op.command)
     → EtherCalc applies the cell edit
  6. persistence.save_op(op)        → INSERT INTO op_log
  7. conflict_resolver.update(op)   → UPDATE cell_meta for this cell
        │
        ▼
Browser (polling or WebSocket from EtherCalc) eventually sees A1=42
```

Note: The browser sees the remote update not because the Adapter pushes it, but because EtherCalc's own WebSocket broadcasts to connected browsers whenever its cell state changes (via a `POST` from the Adapter on behalf of the remote peer).

### 8.3 Late Join / Reconnect Flow

```
New Peer C starts, runs: --connect /ip4/.../tcp/9000/ws/p2p/<PeerA_ID>
        │
        ▼
1. libp2p host dials /ip4/.../tcp/9000/ws/p2p/<PeerA_ID>
   → TCP connection established
   → WebSocket upgrade
   → libp2p handshake (identity verification via secp256k1)
        │
        ▼
2. Peer C opens stream to Peer A with protocol /p2pcalc/sync/1.0.0
   Sends: {"type": "STATE_REQUEST", "sheet_id": "my-sheet"}
        │
        ▼
3. Peer A receives STATE_REQUEST:
   a. GET http://localhost:8000/_/my-sheet  → full SocialCalc snapshot
   b. SELECT from op_log WHERE sheet_id='my-sheet'
      ORDER BY timestamp DESC LIMIT 200    → last 200 ops
   c. Sends STATE_RESPONSE:
      {"snapshot": "<SocialCalc data>", "op_log_tail": [...]}
        │
        ▼
4. Peer C receives STATE_RESPONSE:
   a. PUT http://localhost:8000/_/my-sheet  [snapshot]
      → replaces entire sheet in Peer C's EtherCalc
   b. For each op in op_log_tail (sorted by timestamp):
      - if op.op_id already in local SQLite: skip
      - else: POST the command to local EtherCalc, save to SQLite
        │
        ▼
5. Peer C is now fully up-to-date
   It subscribes to GossipSub topic and future edits flow normally
```

### 8.4 mDNS Auto-Discovery Flow

```
Peer A starts on LAN (--sheet demo, no --connect)
  → zeroconf broadcasts: _p2p._udp.local. PeerID=<A_ID> Port=9000
        │ multicast UDP to 224.0.0.251:5353
        ▼
Peer B starts on same LAN (--sheet demo, no --connect)
  → zeroconf listener fires on_service_added(info) in background thread
  → trio.from_thread.run_sync sends PeerInfo into MemoryChannel
        │
        ▼
Trio consumer task receives PeerInfo:
  1. Constructs /ip4/192.168.1.5/tcp/9000/ws (appends /ws to TCP multiaddr)
  2. await host.connect(multiaddr)
     → WebSocket + libp2p handshake
  3. await request_state_sync(peer_a_id)
     → sends STATE_REQUEST, receives STATE_RESPONSE, applies it
  4. Peer B subscribes to /p2pcalc/sheet/demo
        │
        ▼
Both peers are now in the GossipSub mesh for /p2pcalc/sheet/demo
Real-time edits flow in both directions
```

---

## 9. The OperationMessage Format

Every cell edit is wrapped in an `OperationMessage` (defined in `messages.py`). This is the payload that travels over GossipSub:

```json
{
  "op_id":    "550e8400-e29b-41d4-a716-446655440000",
  "peer_id":  "16Uiu2HAm7Qwe4Zxn7odaYTBbX94y3uWrBXdGh5zPbFXDscFG4rZx",
  "timestamp": 1711468800.123,
  "sheet_id": "my-sheet",
  "command":  "set A1 value n 42",
  "cell_ref": "A1",
  "msg_type": "OPERATION"
}
```

| Field | Source | Purpose |
|-------|--------|---------|
| `op_id` | `uuid4()` | Globally unique dedup key. No two ops should ever have the same ID even across peers. |
| `peer_id` | `host.get_id()` | libp2p Peer ID of the originator. Used in LWW tiebreak. |
| `timestamp` | `time.time()` | Unix time in float seconds (sub-millisecond precision). The primary LWW ordering key. |
| `sheet_id` | `--sheet` CLI flag | Scopes the operation. Matches the GossipSub topic. |
| `command` | SocialCalc syntax | The actual mutation. `set A1 value n 42` means "set cell A1 to numeric value 42". |
| `cell_ref` | Extracted from command | The target cell (e.g. `A1`). Empty string for structural ops (insertrow, deletecolumn). |
| `msg_type` | Always `"OPERATION"` | Protocol field, distinguishes from sync protocol messages. |

The message is serialized as **UTF-8 JSON** and passed to GossipSub as raw bytes. GossipSub adds its own framing (message ID, sender, signature) on top.

---

## 10. Conflict Resolution: Last-Write-Wins

Concurrent edits are inevitable in a distributed system. If Alice and Bob both type into cell A1 at the same millisecond, both peers will receive both operations. Without conflict resolution, different peers could end up with different values for A1.

p2pCalc uses **Last-Write-Wins (LWW)** with deterministic tiebreaking, implemented in `conflict.py`.

### The Algorithm

For each cell, the system maintains a `(timestamp, peer_id)` metadata tuple stored in the SQLite `cell_meta` table and mirrored in memory as a `ConflictResolver` dict.

When an incoming operation arrives for cell `A1`:

```
existing = cell_meta["my-sheet"]["A1"]  # (ts=1000.100, pid="16Uiu2...")
incoming = op.timestamp, op.peer_id    # (ts=1000.200, pid="QmXyz...")

if incoming.ts > existing.ts:
    ACCEPT  ← newer timestamp wins
elif incoming.ts == existing.ts:
    ACCEPT if incoming.pid > existing.pid  ← lexicographic Peer ID tiebreak
else:
    REJECT  ← older operation, already have a newer value
```

### Structural Operations

Operations that don't target a specific cell (e.g., `insertrow 3`, `deletecolumn B`) have `cell_ref = ""`. These are **always accepted** — they have no LWW semantics. This is a simplification; CRDTs would be needed for truly safe structural ops, but for a practical MVP, always-apply is reasonable.

### Convergence Guarantee

Because the resolution rule is **deterministic** (same inputs always produce the same decision) and **commutative** (the order in which ops arrive doesn't matter — the highest `(timestamp, peer_id)` always wins), all peers will converge to the same state eventually, even if they receive ops in different orders.

---

## 11. Persistence: SQLite Schema

p2pCalc uses SQLite in **WAL (Write-Ahead Logging) mode** for offline resilience. The database is at `{data_dir}/p2pcalc.db`.

### Table: `snapshots`

Stores the most recent full SocialCalc sheet snapshot received during a state sync.

```sql
CREATE TABLE snapshots (
    sheet_id  TEXT PRIMARY KEY,
    data      TEXT,    -- full SocialCalc serialization
    timestamp REAL     -- when this snapshot was saved
);
```

One row per sheet. Overwritten on each sync.

### Table: `op_log`

The append-only log of every accepted operation, both local and remote.

```sql
CREATE TABLE op_log (
    op_id     TEXT PRIMARY KEY,
    sheet_id  TEXT,
    peer_id   TEXT,
    timestamp REAL,
    command   TEXT,    -- e.g. "set A1 value n 42"
    cell_ref  TEXT     -- e.g. "A1", or "" for structural ops
);

CREATE INDEX idx_op_log_sheet_ts ON op_log (sheet_id, timestamp);
```

Used for two purposes:
- **Sync responses**: `SELECT ... ORDER BY timestamp DESC LIMIT 200` to build the `op_log_tail`.
- **Dedup on sync receive**: checking whether a replayed op is already known locally.

### Table: `cell_meta`

Per-cell LWW metadata, persisted so conflict resolution survives restarts.

```sql
CREATE TABLE cell_meta (
    sheet_id  TEXT,
    cell_ref  TEXT,
    timestamp REAL,   -- timestamp of last accepted write
    peer_id   TEXT,   -- peer_id of last accepted write
    PRIMARY KEY (sheet_id, cell_ref)
);
```

On startup, the entire `cell_meta` table is loaded into the in-memory `ConflictResolver`. This means a peer that restarts still makes correct LWW decisions against operations it previously accepted.

---

## 12. Module Map and Responsibilities

```
src/p2pcalc/
├── main.py        Entry point. Parses CLI args. Opens SQLite. Wires all
│                  components together into a single Trio nursery. Starts
│                  everything: host, pubsub, mDNS, hypercorn, CLI loop.
│
├── config.py      All constants. GossipSub params (D=6, D_low=4, D_high=8,
│                  heartbeat=1s). Protocol IDs (/p2pcalc/sync/1.0.0).
│                  Default ports (8000, 8001, 9000). Sheet topic template.
│
├── p2p_node.py    The libp2p node. Creates host with secp256k1 key + WS
│                  transport. Creates GossipSub router + Pubsub service.
│                  Registers sync stream handler. Manages mDNS: starts
│                  zeroconf, bridges thread callbacks into Trio via
│                  MemoryChannel, appends /ws to discovered addrs.
│                  Handles DHT setup when --dht is passed.
│
├── adapter.py     Starlette ASGI app. Routes:
│                  - GET /_p2pcalc/peer-id → peer ID string
│                  - POST /_/{id} → intercept, forward to EC, publish
│                  - * → transparent proxy to EtherCalc
│                  Holds on_remote_message callback used by p2p_node.
│                  Manages dedup LRU cache (10k op IDs).
│
├── messages.py    OperationMessage dataclass. from_json / to_dict.
│                  Validation. cell_ref extraction from SocialCalc commands.
│
├── conflict.py    ConflictResolver class. In-memory dict: cell → (ts, pid).
│                  should_accept(op) → bool. update(op). Loaded from
│                  cell_meta on startup, written back on each accept.
│
├── persistence.py PersistenceStore class wrapping SQLite in WAL mode.
│                  create_tables(). save_op(op). get_op_log_tail(sheet, n).
│                  save_snapshot(sheet, data). get_snapshot(sheet).
│                  load_cell_meta(sheet) → dict for ConflictResolver init.
│
└── state_sync.py  build_state_response(sheet_id, ec_client, store) →
│                  fetches snapshot from EtherCalc + op_log tail from SQLite.
│                  apply_state_response(response, ec_client, store) →
│                  PUTs snapshot, replays op_log_tail skipping known ops.
```

---

## 13. Port Layout

### Single Peer (defaults)

| Port | Process | Protocol | Who connects |
|------|---------|----------|-------------|
| `8000` | EtherCalc | HTTP + WebSocket | Adapter only (internal) |
| `8001` | Adapter (Hypercorn) | HTTP | Your browser |
| `9000` | libp2p host | WebSocket | Other peers |
| `5353` | mDNS (system multicast) | UDP | System-managed |

### Two-Peer Demo (`demo.sh`)

| Peer | EtherCalc | Adapter | libp2p |
|------|-----------|---------|--------|
| Peer A | `:8000` | `:8001` | `:9000` |
| Peer B | `:8010` | `:8011` | `:9010` |

### Three-Peer Docker Compose

| Peer | EtherCalc | Adapter | libp2p |
|------|-----------|---------|--------|
| Peer 1 | `:8000` | `:8001` | `:9000` |
| Peer 2 | `:8010` | `:8011` | `:9010` |
| Peer 3 | `:8020` | `:8021` | `:9020` |

---

## 14. Startup Sequence

When you run `uv run p2pcalc --sheet my-sheet`:

```
 1.  Parse CLI args                       (main.py)
 2.  Open SQLite, CREATE TABLE IF EXISTS  (persistence.py)
 3.  Load cell_meta → ConflictResolver    (conflict.py)
 4.  Load or generate secp256k1 key pair  (p2p_node.py)
 5.  Create libp2p Host                   (p2p_node.py)
 6.  Create GossipSub router + Pubsub     (p2p_node.py)
 7.  Register /p2pcalc/sync/1.0.0 handler (p2p_node.py)
 8.  Create Adapter app, wire callbacks   (adapter.py)
 9.  host.start() → listen on :9000/ws    (p2p_node.py)
10.  pubsub.start() → GossipSub heartbeat (p2p_node.py)
11.  pubsub.subscribe("/p2pcalc/sheet/my-sheet")
12.  Start mDNS (if --no-mdns not set):
       - zeroconf broadcasts service record
       - starts MemoryChannel + Trio consumer task
13.  If --connect provided:
       - host.connect(multiaddr)
       - request_state_sync(remote_peer_id)
14.  If --dht provided:
       - start Kademlia DHT
       - advertise sheet key, start peer discovery loop
15.  hypercorn.serve(adapter_app, :8001) → HTTP ready
16.  Start CLI loop (if TTY)
17.  Print banner showing Peer ID + multiaddr + mDNS/DHT status
18.  Run forever (Trio nursery)
```

---

## 15. EtherCalc vs p2pCalc: Side-by-Side Comparison

| Dimension | Vanilla EtherCalc | p2pCalc |
|-----------|------------------|---------|
| **Sync model** | Central server broadcasts via WebSocket to all browsers | GossipSub pubsub mesh; all peers are equal |
| **Single point of failure** | Yes — server crash = everyone disconnected | No — any peer can leave, others keep syncing |
| **Peer discovery** | Manual (share URL pointing to server) | Automatic on LAN (mDNS) or WAN (DHT) |
| **Late join / catch-up** | Server sends current state via WebSocket | Custom sync stream: snapshot + op log tail |
| **Offline resilience** | None — disconnect = no sync | SQLite persists all ops; resync on reconnect |
| **Conflict resolution** | Server serializes all writes (implicit LWW via order of arrival) | Explicit LWW with `(timestamp, peer_id)` tiebreak |
| **Trust model** | Trust the server | No central authority; each peer verifies via secp256k1 identity |
| **UI changes** | N/A (this IS EtherCalc) | Zero — SocialCalc browser UI is unmodified |
| **Infrastructure** | Requires a running Node.js server (+ Redis) reachable by all peers | Each peer runs their own local EtherCalc; Python adapter bridges to P2P mesh |
| **Language** | Node.js | Python (py-libp2p, Trio, Starlette) |
| **Persistence** | Redis (in-memory + optional dump) | Redis (EtherCalc internal) + SQLite (p2pCalc op log) |
| **Scalability** | Single server = hard ceiling on connections | GossipSub mesh scales to thousands of peers |

---

## 16. Key Design Decisions

**EtherCalc as a local dumb store, not a sync engine.**  
Rather than modifying EtherCalc's source (which is complex Node.js), p2pCalc wraps it as a black-box REST API. EtherCalc becomes just a local cell database and UI server. All sync responsibility is moved to the Python layer.

**Adapter as a transparent proxy.**  
The browser never knows it's in a P2P system. The SocialCalc UI works without any changes because the Adapter faithfully proxies everything except the specific POST endpoint for edits.

**GossipSub topic = sheet ID.**  
One topic per sheet means perfect isolation between collaborators on different documents. It also means you could theoretically have thousands of concurrent p2pCalc sessions on the same mesh, each scoped to its own topic.

**Explicit op log instead of CRDT.**  
CRDTs (Conflict-free Replicated Data Types) would give stronger consistency guarantees for concurrent structural ops (insertrow, deletecolumn). p2pCalc takes the pragmatic path of LWW for cell ops and always-apply for structural ops. Good enough for a collaborative spreadsheet where conflicts are rare in practice.

**SQLite in WAL mode.**  
WAL mode allows concurrent reads while a write is happening. Since the Adapter reads from SQLite (for dedup checks) and writes to it (for op_log) on every edit, WAL mode prevents reader-writer contention and gives better throughput on low-end hardware.

**secp256k1 for Peer ID.**  
This is the same key curve as Ethereum accounts. In a future version, Peer IDs could be linked to Ethereum wallet addresses, enabling stake-based reputation or payment-gated collaboration — a direct bridge to the GooseSwarm/x402 pattern.

**Trio throughout.**  
py-libp2p is Trio-native and cannot run in asyncio. Rather than bridging (which is complex and fragile), p2pCalc commits to Trio for everything: Hypercorn (which has a Trio backend), httpx (Trio-compatible), and the discovery channel bridge. This gives a single coherent structured-concurrency model across the entire application.

---

*Document compiled from the p2pCalc repository: README.md, docs/Architecture.md, pyproject.toml, and source structure as of April 2026.*
