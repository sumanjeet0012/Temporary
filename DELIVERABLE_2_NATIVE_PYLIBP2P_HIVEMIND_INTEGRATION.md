# Deliverable 2: Native py-libp2p Hivemind Integration

**Project:** RFP — Native py-libp2p NAT Traversal, Rendezvous Interoperability Testing with Hivemind
**Target:** `hivemind/p2p` in `hivemind-py-libp2p`, branch `feat/native-py-libp2p`
**Commit:** `a67a713` (pushed to `sumanjeet0012/hivemind-py-libp2p`, upstream untouched)
**Status:** Complete for basic P2P (TCP, identity, streams). Relay/AutoNAT/DCUtR/Rendezvous deferred to Phases 3–4 by RFP design.
**Date:** September 2026

---

## 1. What was done (summary)

The Go libp2p daemon (`p2pd` subprocess + Unix-socket Protobuf IPC) was **completely removed**
from the networking path. `hivemind.p2p.P2P` is now a pure-Python peer: an in-process
py-libp2p `BasicHost` running on a dedicated trio thread, exposed through the **unchanged**
asyncio API that DHT, averaging, and MoE already use. No Go toolchain, no `p2pd` binary,
no local IPC sockets are required at runtime.

**Files changed** (`git diff --stat`: +365 / −1371):

| File | Change |
|---|---|
| `hivemind/p2p/p2p_native.py` | **New** (~350 lines). Trio(system) gateway: host lifecycle, asyncio↔trio bridge, duplex byte pipes, dial-address cache, RSA identity loading |
| `hivemind/p2p/p2p_daemon.py` | **Rewritten** `P2P` (~700 lines). Same class name, same public methods; internals native-only. Filename kept so every existing import keeps working |
| `hivemind/p2p/p2p_daemon_bindings/p2pclient.py` | **Deleted** (122 lines). Go-IPC client, obsolete |
| `tests/test_p2p_daemon_bindings.py` | **Deleted** (633 lines). Tested the IPC protocol against a real daemon binary |
| `tests/test_utils/p2p_daemon.py` | **Deleted** (182 lines). Spawned `p2pd` pairs for tests |
| `tests/test_p2p_daemon.py` | **Ported** to native semantics (no PIDs, no startup-error strings, shared-host replicate) |
| `tests/test_dht_protocol.py` | One `xfail` added (multi-hop dial needs Phase-3 peer routing; see §7) |
| `tests/test_p2p_servicer.py` | **Unchanged** — passes 8/8 as-is, proving upper layers are unaffected |

**Test results** (Python 3.12, macOS, `pytest tests/test_p2p_servicer.py tests/test_p2p_daemon.py tests/test_dht_protocol.py`):
`26 passed, 1 skipped (QUIC, pre-existing skip), 1 xfailed (documented)` — exit code 0.

---

## 2. Why this architecture (the core constraint)

Hivemind is `asyncio` (+ `uvloop`); py-libp2p is `trio`-native (~70 files call `trio.*` directly:
TCP transport, Swarm, Yamux/Mplex, DHT, PubSub, Rendezvous, Relay). The two schedulers cannot
share a thread — calling `trio.open_nursery()` inside asyncio raises immediately.

Evaluated options (see Deliverable 1 for the full 6-way analysis): porting py-libp2p to
`anyio` (correct long-term, months of work), porting Hivemind to trio (impossible — DHT uses
`multiprocessing` fork), `trio_asyncio` bridge (breaks `asyncio.gather`, clashes with `uvloop`),
keeping the daemon (defeats the RFP). **Chosen: thread-isolated trio host + typed bridge**
(Approach 6). Zero changes to Hivemind layers 2–5, zero changes to py-libp2p.

---

## 3. How it works

### 3.1 Process model

```
BEFORE:  python ──unix socket/protobuf──▶ [separate Go p2pd process] ──▶ libp2p network
AFTER :  python process
         ├── asyncio thread (Hivemind: DHT, ServicerBase, your code)
         └── trio thread "hivemind-trio-gateway" (py-libp2p BasicHost)
                  ▲                    │
                  └── bridge ──────────┘
```

`TrioGateway` (`p2p_native.py`) owns one trio event loop + one `BasicHost` (`libp2p.new_host()`),
shared by N `P2P` facades via refcounting (`retain`/`release`; last `shutdown()` stops the host).
`P2P.replicate(token)` attaches a second facade to the same host — the native equivalent of the
old "connect to an already running daemon". The token is still exposed as
`P2P.daemon_listen_maddr` (now an opaque in-process identifier, never a real socket), so all
existing call sites work unchanged.

### 3.2 The bridge (two primitives)

1. **Unary calls** — `await asyncio.to_thread(trio.from_thread.run, afn, trio_token=token)`.
   asyncio parks a pool thread; trio runs the coroutine; the result comes back. Used for
   `get_id`, `connect`, `new_stream`, peerstore reads.
2. **Byte streams (full duplex)** — each libp2p stream gets two one-way pumps in a trio nursery:
   - **trio→asyncio**: pump reads `INetStream` chunks → `loop.call_soon_threadsafe(reader.feed_data)`
     into an `asyncio.StreamReader`. (Reads use an exact-length loop — `INetStream.read(n)` may
     short-read; this was a real bug in the first prototype.)
   - **asyncio→trio**: a `_AsyncioWriter` (minimal `StreamWriter`: `write/drain/close/wait_closed`)
     appends to a thread-safe `queue.Queue`; the trio pump polls it with a 50 ms timeout and
     writes to the libp2p stream. Polling (not blocking `get()`) matters: on teardown trio
     *abandons* the worker thread of a blocking call, so a bare `get()` would leak one thread
     per closed stream. The trio thread pool is also raised (40→256 tokens) for stream-heavy
     workloads like DHT/averaging.

### 3.3 Teardown model (drain-safe)

- `writer.close()` enqueues an end-of-write sentinel — already-queued bytes are **always flushed**
  before `close_write` (half-close). It never cancels pumps (an early version did, and raced
  with flushing — fixed).
- When a pump observes remote EOF/reset, it cancels the session nursery: asyncio readers get
  `feed_eof`, `session.done` fires, the libp2p stream closes. Client cancels therefore propagate
  to server handlers (verified by `test_unary_stream_cancel` and the cancel variants of
  `test_call_protobuf_handler`).
- `TrioGateway.stop()` is **non-blocking** (`token.run_sync_soon(scope.cancel)`) because it runs
  on refcount release, including from `P2P.__del__` during interpreter shutdown, where a blocking
  trio roundtrip wedges garbage collection forever (caught red-handed with faulthandler; fixed).
- `feed_reader` guards closed loops and each session remembers its own asyncio loop, so replicas
  created on different loops feed the right one.

### 3.4 Wire protocol and framing

- **Single namespace**: `/hivemind/{name}` for unary, streaming, and raw binary handlers —
  mirroring the daemon, whose `add_unary_handler`/`stream_handler` registries shared one name
  space. (An earlier draft used `/unary/` vs `/stream/` prefixes; it broke raw binary access to
  protobuf handlers and was unified.)
- **Framing** (byte-identical to the daemon, so the layers above can't tell): 1-byte marker
  (`0x00` message / `0x01` error) + 8-byte big-endian length + protobuf payload — same constants
  (`HEADER_LEN`, `MESSAGE_MARKER`, `ERROR_MARKER`) and same static helpers (`send_protobuf`,
  `receive_protobuf`, `send_raw_data`, `receive_raw_data`), untouched.
- **Unary over streams**: every protobuf handler is served by the streaming engine
  (`_handle_stream`, kept verbatim from the daemon code). Unary calls send request +
  `END_OF_STREAM` sentinel and read one response. The sentinel is load-bearing: the server's
  single-request adapter (`asingle`) requires a *terminated* one-item stream, otherwise it waits
  forever (this exact hang was diagnosed and fixed during development).
- **Errors**: server exceptions serialize to error-marker frames; clients raise `P2PHandlerError`
  with the original message (verified: `test_call_protobuf_handler_error`, `"boom"` propagates).
  Dialing an unknown/removed handler fails fast at multiselect negotiation, mapped to
  `P2PDaemonError` to match daemon error types; stale half-dead connections trigger one
  disconnect+reconnect retry before surfacing the error.

### 3.5 Identity, addresses, peers

- **Identity files** keep their exact format (RSA DER inside `crypto_pb2.PrivateKey`), so existing
  `identity_path` files produce byte-identical PeerIDs under py-libp2p (`test_identity` passes).
  Loading converts DER → `Crypto.PublicKey.RSA` → libp2p `KeyPair` for `new_host()`.
- **crypto_pb2 collision**: Hivemind's and py-libp2p's `crypto.proto` share package `crypto.pb`
  with wire-compatible schemas; importing both crashes the protobuf descriptor pool. The native
  backend canonically aliases py-libp2p's module under `hivemind.proto.crypto_pb2` (documented
  shim in `p2p_native.py`, must load first).
- **Multiaddrs**: Hivemind's vendored `Multiaddr` ↔ `multiaddr.Multiaddr` convert via string form;
  visible addrs are `/p2p/<id>`-encapsulated like before. Bootstrap dial requires the `/p2p/`
  suffix (unchanged).
- **Dial cache**: py-libp2p's peerstore can drop addresses on disconnect, permanently stranding
  redials ("not connected and no known addresses" — this broke DHT re-finds). The gateway keeps
  a last-known-address cache fed by every successful connect and peerstore sighting; reconnect
  does disconnect-then-redial from cache.
- **`list_peers`** maps `host.get_connected_peers()` + peerstore addrs to Hivemind `PeerInfo`.

---

## 4. API mapping (daemon → native)

| `P2P` API | Before (Go) | After (native) |
|---|---|---|
| `create(...)` | spawn `p2pd` subprocess, IPC handshake | start trio gateway, connect bootstraps; same signature, same validation |
| `replicate(token)` | attach to running daemon | attach facade to shared gateway (same peer ID) |
| `add/call/iterate_protobuf_handler` | daemon unary + stream RPCs | identical signatures; served by streaming engine over `INetStream` |
| `add/remove/call_binary_stream_handler` | daemon stream open | duplex-pipe adapter; returns real `StreamReader/Writer` |
| `get_visible_maddrs`, `list_peers`, `wait_for_at_least_n_peers` | daemon identify/peerstore | host addrs / `get_connected_peers` / peerstore |
| `send/recv_protobuf`, `send/recv_raw_data` | asyncio framing helpers | **unchanged code** |
| `generate_identity`, `is_identity_taken` | RSA file + probe daemon | RSA file (same format); probe via ephemeral native node (1-hop) |
| `shutdown`, `is_alive`, `daemon_listen_maddr` | kill subprocess | refcount release, non-blocking host stop; token stays for API compat |
| `P2PContext`, `PeerID/PeerInfo/StreamInfo`, `P2PDaemonError/P2PHandlerError` | bindings | **unchanged** |

Transport flags (`auto_nat`, `use_relay`, `conn_manager`, `dht_mode`, …) are accepted and
validated but currently no-ops, queued for Phases 3–4. `use_ipfs` raises (no native equivalent).

---

## 5. Semantics preserved vs. known divergences

**Preserved** (covered by tests): all 4 ServicerBase patterns, streaming cancel propagation,
duplicate-handler rejection (gateway-wide, incl. across replicas), dial-self rejection,
per-replica handler cleanup on shutdown, error-message propagation, identity persistence +
collision detection, replica-doesn't-kill-primary shutdown.

**Divergences** (conscious, documented in code/tests):
1. **Bootstrap is best-effort**: unreachable `initial_peers` warn instead of raising
   (daemon failed fast). Rationale: DHT restarts must survive dead bootstraps.
2. **Removed-handler dial fails at negotiation** (`P2PDaemonError` from `open`), whereas the
   daemon opened the stream then reset it (`IncompleteReadError` on read). Tests updated.
3. **Identity-collision check is 1-hop**: the probe node only sees direct bootstraps; swarm-wide
   detection needs peer routing (Phase 3). Test scoped accordingly.
4. **No `p2pd` stdout/log plumbing** (`GOLOG_*`, `_read_outputs` deleted).

---

## 6. How it was validated

- `tests/test_p2p_servicer.py` — **8/8, file untouched**: unary/streaming RPCs, cancel-by-close,
  cancel-by-generator-close, handler add/remove across replicas.
- `tests/test_p2p_daemon.py` — **17 passed, 1 skipped** (QUIC, pre-existing): identity, transports,
  replicas, unary edge cases, cancel variants, single/multi-process binary streams, error-closes-connection.
- `tests/test_dht_protocol.py::test_empty_table` — **passes**: real DHT store/find/ping over native.
- `test_dht_protocol::test_dht_protocol` — **xfailed (strict=False)**: dials a peer it never
  contacted; DHT exchanges node IDs only, never addresses, so resolution needs Phase-3 discovery.
- Debugging tools used along the way: wire hexdumps, pump-level tracing, faulthandler-on-SIGABRT
  for the shutdown hang, `trio`/`asyncio` bridge isolation scripts (kept in workspace, not repo).

---

## 7. Known gaps → next phases

- **Phase 3 (Rendezvous/discovery)**: peer routing for never-contacted IDs (un-xfail DHT test),
  swarm-wide identity check, `dht_mode` semantics.
- **Phase 4 (NAT)**: wire `auto_nat`/`use_relay`/relays/AutoNAT + Relay v2 + DCUtR; exercise the
  `unified-testing` matrices already cloned in the workspace.
- **Hardening**: `_ensure_connected` does a peer-listing roundtrip per RPC (cache it);
  per-stream trio worker usage under very high concurrency; QUIC transport parity.
- **Cleanup debt**: `p2p_daemon_bindings/control.py` still contains dead IPC server classes
  (constants + errors still used — trim in a follow-up); generated `*_pb2.py` are local build
  artifacts (gitignored); `hivemind_cli` still ships the Go build script (build-time only,
  untouched at runtime).
