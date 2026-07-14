# py-ipfs-lite — Bug & Test Coverage Analysis

**Repository:** https://github.com/IPFS-Meshkit/py-ipfs-lite
**Commit analyzed:** `2629eee60c7ffd21ed8714e6b69984c9d455c96b` (2026-07-12)
**Dependency versions:** `libp2p==0.7.0` (PyPI), Python 3.12.3
**Analysis date:** 2026-07-14

## Methodology

- Cloned the repo and installed it (`pip install -e ".[test,dev]"`) into a clean venv.
- Read every file in `py_ipfs_lite/`, cross-referencing against the installed `libp2p` and `cid` package internals where behavior depended on them.
- Ran the full test suite (`pytest`), `mypy --strict`-adjacent checks against the project's own `[tool.mypy]` config, and `pytest-cov` for line coverage.
- For every suspected bug, wrote a standalone reproduction script rather than relying on code-reading alone. All findings below marked **Confirmed** were actually triggered and observed; those marked **Static** are code-review findings not independently exercised.
- All 40 existing tests pass. Nothing here was caught by CI as currently configured — that's the point of the second half of this document.
- Bugs #12 and #13 were reported independently by a developer integrating `py-ipfs-lite` into a downstream project; both were verified against the same environment (`libp2p==0.7.0`) and reproduced directly rather than taken on faith.

---

## Part 1 — Bugs

### Severity summary

| # | Bug | File | Severity | Status |
|---|-----|------|----------|--------|
| 1 | `export_car` crashes on non-local blocks | `car.py` | High | Confirmed |
| 2 | Direct pins leak one level to children | `dag_utils.py` | High | Confirmed |
| 3 | Default config makes real network calls, even when local | `peer.py`, `routing.py`, `config.py` | High | Confirmed |
| 4 | `daemon --api` never bootstraps the DHT | `cli.py` | High | Static |
| 5 | Routing HTTP client is never closed | `peer.py` | Medium | Confirmed |
| 6 | `import_car` doesn't verify block hashes | `car.py` | Medium | Static |
| 7 | `BlockStore` protocol type contract violated | `interfaces.py`, `peer.py`, `api.py` | Medium (latent) | Confirmed |
| 8 | `swarm_peers` inconsistent error handling | `api.py` | Low | Static |
| 9 | `block_stat` TOCTOU + redundant lookup | `api.py` | Low | Static |
| 10 | GC doc example crashes; no exception-safety in `Peer` | `docs/…`, `peer.py` | Low | Confirmed |
| 11 | Metrics double-count on idempotent `put`; global metrics across peers | `metrics.py` | Low | Static |
| 12 | `add_file()` crashes on raw `bytes`/stream input | `peer.py` | High | Confirmed (user-reported) |
| 13 | `ExchangeAdapter.get_block()` signature mismatch with `MerkleDag` | `peer.py` | Medium–High | Confirmed (user-reported) |

---

### 1. `export_car` crashes when a referenced block isn't in the local blockstore

**File:** `py_ipfs_lite/car.py`, line 107
**Severity:** High — breaks an advertised feature outright.

```python
data = await peer.blockstore.get(curr_cid_bytes)
if data is None:
    data = await peer.exchange.get_block(curr_cid_bytes)   # <-- bug
    if data is None:
        continue
```

`Peer.exchange` is a **method**, not a property:

```python
# peer.py
def exchange(self) -> Any:
    return self._exchange
```

So `peer.exchange.get_block(...)` accesses `.get_block` on the bound-method object itself, not on the exchange. This only matters when `export_car` needs to fall back to Bitswap — i.e. exactly the "partial DAG" case the README explicitly promises ("Export and import full **or partial** DAGs as Content Addressable aRchives").

**Reproduction:**

```python
peer = Peer(Config(blockstore_type="memory", offline=True), listen_addrs=[...])
await peer.start()
child_cid = await peer.add_node({"msg": "child"}, codec="dag-cbor")
parent_cid = await peer.add_node({"link": {"/": child_cid}}, codec="dag-cbor")
await peer.blockstore.delete(cid_to_bytes(parse_cid(child_cid)))  # simulate partial availability
await peer.export_car(parent_cid, "out.car")
```

```
export_car CRASHED: AttributeError: 'function' object has no attribute 'get_block'
```

**Why it's hidden:** `tests/test_car.py::test_car_export_import` only exports a fully-local DAG, so `data` is never `None` and line 107 never executes. Coverage confirms: lines 107-109 show 0% coverage.

**Fix:** `peer.exchange().get_block(curr_cid_bytes)`, or better, use `peer._exchange` directly (or expose a real `exchange` property instead of a same-named method).

---

### 2. A "direct" pin also protects the pinned node's immediate children from GC

**File:** `py_ipfs_lite/dag_utils.py`, `walk_dag()`, lines 38-57
**Severity:** High — silently contradicts the project's own documented semantics.

```python
async def walk_dag(root_cid_bytes, get_block, recursive=True):
    queue = [root_cid_bytes]
    visited = set()
    while queue:
        curr_cid = queue.pop(0)
        if curr_cid in visited:
            continue
        visited.add(curr_cid)
        yield curr_cid

        if not recursive and curr_cid != root_cid_bytes:
            continue   # <-- only stops recursion PAST the root

        data = await get_block(curr_cid)
        ...  # expands curr_cid's links into queue regardless
```

On the very first loop iteration `curr_cid == root_cid_bytes`, so the `not recursive` guard doesn't fire yet — the root's own children get fetched and enqueued *before* the guard has a chance to stop anything. The result: a "direct" (`recursive=False`) pin protects the root **plus its immediate children**, not just the root.

This directly contradicts the project's own docs:

- `docs/guides/persistence-and-gc.md`: `direct` → *"Root block only"*; *"Direct pinning is useful when you have a large DAG and only want to protect the root node itself, not its children."*
- `docs/reference/http-api.md`: `# Direct pin only (root block only)`
- `docs/reference/python-sdk.md`: `"direct"` → *"Root block explicitly pinned with `recursive=False`"*

**Reproduction:**

```python
child_cid = await peer.add_node({"msg": "child leaf"}, codec="dag-cbor")
parent_cid = await peer.add_node({"link": {"/": child_cid}, "msg": "parent"}, codec="dag-cbor")
await peer.add_pin(parent_cid, recursive=False)   # direct pin
await peer.gc()
```

```
parent survived GC: True   (expected True)
child survived GC:  True   (expected False for a true *direct* pin)
```

**Extra nuance:** `Peer.list_pins()` does **not** hit this bug — it only walks children for pins where `pin_type == "recursive"`, so it never reports these children as "indirect." That means `gc()` retains blocks that `list_pins()` doesn't even claim are protected by anything — an internally inconsistent picture of what's pinned vs. what survives GC.

**Why it's hidden:** the only direct-pin test (`test_pin_and_gc` in `tests/test_peer.py`) pins a leaf node with no children, so it can't distinguish "protects only itself" from "protects itself + children." Coverage also shows the dag-pb/link-expansion branches of `walk_dag` (lines 63-69, 80-90) are only partially exercised.

**Fix:** the `continue` needs to fire before expanding a non-recursive root's own children too — e.g. only enter the block-fetch/expand section at all when `recursive` is `True`, or explicitly stop after yielding the root when `recursive=False` regardless of whether it's the first item.

---

### 3. Default configuration makes real, and sometimes unnecessary, third-party network calls

**Files:** `py_ipfs_lite/config.py`, `py_ipfs_lite/routing.py`, `py_ipfs_lite/peer.py`
**Severity:** High — affects the literal quickstart example in the README.

`Config` defaults to `offline=False` and `use_ipni=True`. Combined, every `Peer` — including a purely in-memory, "ephemeral" one as shown in the README's first example — builds a `TieredRouting([DelegatedHTTPRouting("https://cid.contact"), KadDHT(...)])`. `add_node`/`add_file` call `routing.provide()`, and `get_node`/`get_file` call `routing.find_providers()`, both of which hit `https://cid.contact` over real HTTPS.

**Reproduction** (logging enabled, `blockstore_type="memory"`, no explicit `offline=True`):

```
DEBUG:httpcore.connection:connect_tcp.started host='cid.contact' port=443 ...
INFO:httpx:HTTP Request: PUT https://cid.contact/routing/v1/providers/bafkrei... "HTTP/1.1 403 Forbidden"
added cid bafkreidyatsw27dtvkxqzgar66li6wsujtix3q5raov5kxwkz242nbgwja
INFO:httpx:HTTP Request: GET https://cid.contact/routing/v1/providers/bafkrei... "HTTP/1.1 403 Forbidden"
INFO:httpx:HTTP Request: GET https://cid.contact/cid/bafkrei... "HTTP/1.1 403 Forbidden"
get_file took 0.007584778000023107 seconds, content: b'hello world timing test'
```

(The 403s are my sandbox's egress proxy blocking the host — in a normal environment these would be real, and slower, round trips.)

**Compounding issue:** `get_node()` checks the local blockstore *first* and only engages routing on a local miss. `get_file()` does not — it unconditionally calls `routing.find_providers()` before ever touching local storage or the exchange, even for content the peer added to itself moments earlier. This is a real latency/behavior asymmetry between the two read paths, not just a "goes online by default" issue.

**Secondary evidence:** the project's own test suite works around this. `tests/test_ipns.py`'s `client` fixture does:
```python
await peer.start()
peer.routing = MockRouting()   # replace AFTER start(), to "avoid network delays"
```
…but `tests/test_peer.py`, `tests/test_pin.py`, and `tests/test_car.py` do **not** do this, so those tests make live calls to `cid.contact` today (masked in CI only if they happen to fail fast).

**Fix suggestions:** default `use_ipni=False` (or `offline=True`) for the SDK-embedding use case, and/or check local storage before any provider lookup in `get_file()` to match `get_node()`'s behavior; make the README's basic example explicit about what network behavior to expect.

---

### 4. `daemon --api` never joins the DHT bootstrap network

**File:** `py_ipfs_lite/cli.py`, lines 193-214
**Severity:** High — this is the exact command shown in the README quickstart.

The plain daemon path uses the shared helper, which bootstraps:

```python
async def run_daemon(port, seed, config):
    async with create_and_start_peer(port, seed, config, bootstrap=True) as peer:
        ...
```
```python
async def create_and_start_peer(port, seed, config, bootstrap=True):
    ...
    await peer.start()
    if bootstrap and not config.offline:
        await peer.bootstrap(DEFAULT_BOOTSTRAP_PEERS)
    yield peer
```

The `--api` branch bypasses this helper entirely:

```python
if parsed_args.api:
    ...
    peer = Peer(config, host_key=key_pair, listen_addrs=listen_addrs)
    app.state.peer = peer          # peer.start() happens later, inside FastAPI's lifespan()
    ...
    trio.run(hypercorn.trio.serve, app, hyperconfig)
```

`app.state.peer` gets `.start()`-ed by `api.py`'s `lifespan()`, but nothing ever calls `peer.bootstrap(...)`. A node started via `py-ipfs-lite daemon --api --api-port 5001` (the exact README command) instantiates DHT + IPNI routing objects that *look* functional but never connect to a single bootstrap peer, so DHT-based provider discovery is silently non-functional in this mode. There is also no HTTP endpoint (e.g. `/api/v0/swarm/connect`) to trigger bootstrapping after the fact.

**Fix:** call `await peer.bootstrap(DEFAULT_BOOTSTRAP_PEERS)` inside `lifespan()` (mirroring `create_and_start_peer`) when `not config.offline`, or route the `--api` path through `create_and_start_peer` as well.

---

### 5. `Peer.close()` never closes the routing layer's HTTP client

**File:** `py_ipfs_lite/peer.py`, `close()`, lines 341-355
**Severity:** Medium — resource leak on every non-offline peer.

`DelegatedHTTPRouting` and `TieredRouting` both define `close()`/`aclose()` for exactly this purpose:

```python
# routing.py
class DelegatedHTTPRouting:
    async def close(self) -> None:
        await self.client.aclose()

class TieredRouting:
    async def close(self) -> None:
        for r in self.routers:
            if hasattr(r, "close"):
                await r.close()
```

But `Peer.close()` never calls `self.routing.close()`:

```python
async def close(self) -> None:
    if not self._started:
        return
    if hasattr(self, "_nursery") and self._nursery:
        self._nursery.cancel_scope.cancel()
    await self.reprovider.stop()
    await self._exchange.stop()
    if self._auto_connector:
        await self._auto_connector.stop()
    if self._connection_pruner:
        await self._connection_pruner.stop()
    await self._exit_stack.aclose()
    self._started = False
```

**Reproduction:**

```python
await peer.start()
client = peer.routing.routers[0].client
print(client.is_closed)   # False
await peer.close()
print(client.is_closed)   # still False
```

**Fix:** add `if self.routing and hasattr(self.routing, "close"): await self.routing.close()` to `Peer.close()`.

---

### 6. `import_car` stores blocks without verifying they hash to their claimed CID

**File:** `py_ipfs_lite/car.py`, `import_car()`, line 186
**Severity:** Medium — content-addressing integrity gap.

```python
cid_len = get_cid_len(block_data_full)
cid_bytes = block_data_full[:cid_len]
data = block_data_full[cid_len:]
await peer.blockstore.put(cid_bytes, data)   # no hash check
```

Nothing here (or in `MemoryBlockStore`/`FilesystemBlockStore.put_block`) checks that `hash(data)` actually matches `cid_bytes`. A corrupted or maliciously-crafted `.car` file can poison the local blockstore with data under an arbitrary CID. This matters more than it would for a toy project given the repo's own use cases lean on content-addressing as a trust boundary (`docs/guides/car-files-and-filecoin.md`, `examples/08_verifiable_inference.py`, `examples/18_ipns_trust_boundary.py`).

**Fix:** recompute the CID from `data` (matching the codec/hash function encoded in `cid_bytes`) and reject the block (or at least warn) on mismatch before storing.

---

### 7. `BlockStore` protocol says `bytes`; some call sites pass CID objects — and mypy can't see it

**Files:** `py_ipfs_lite/interfaces.py`, `peer.py` (`remove_node`, `has_block`), `api.py` (`block_stat`)
**Severity:** Medium, currently latent.

```python
# interfaces.py
class BlockStore(Protocol):
    async def put(self, cid: bytes, data: bytes) -> None: ...
    async def get(self, cid: bytes) -> bytes | None: ...
    async def has(self, cid: bytes) -> bool: ...
    async def delete(self, cid: bytes) -> None: ...
```

`add_node`/`get_node`/`gc()` correctly pass `bytes` (via `compute_cid_v1()` or `cid_to_bytes()`). But:

```python
# peer.py
async def remove_node(self, cid_str: str) -> None:
    cid = parse_cid(cid_str)          # returns a CIDv0/CIDv1 OBJECT
    await self.blockstore.delete(cid) # passed directly, not bytes

async def has_block(self, cid_str: str) -> bool:
    cid = parse_cid(cid_str)
    return await self.blockstore.has(cid)  # same
```
```python
# api.py — block_stat
cid = parse_cid(arg)
has = await peer.blockstore.has(cid)
data = await peer.blockstore.get(cid)
```

This currently "works" only because `libp2p.bitswap.block_store`'s concrete implementations defensively re-normalize *any* CID-like input:

```python
def _normalize_cid(cid: CIDInput) -> CIDObject:
    return parse_cid(cid)
```

It's a real latent fragility: swap in a different `BlockStore` implementation that takes the `bytes` contract literally (e.g. a naive Redis/KV-backed store), and `remove_node`/`has_block`/`block_stat` silently stop matching what `add_node`/`get_node` stored.

**Why mypy doesn't catch it:** confirmed via `reveal_type`:
```
check_types.py:6: note: Revealed type is "Any"     # parse_cid(cid_str)
check_types.py:8: note: Revealed type is "bytes"    # compute_cid_v1(...)
```
`CIDv0`/`CIDv1` come from the `cid` package, which has no `py.typed` marker. With `ignore_missing_imports = true` in `[tool.mypy]`, `parse_cid`'s return type degrades to `Any`, which is assignable anywhere — so passing a CID object where `bytes` is declared produces zero mypy errors, even under `--strict`. `mypy py_ipfs_lite/` currently reports "Success: no issues found in 17 source files" despite this.

**Fix:** convert to bytes at every call site (`cid_to_bytes(parse_cid(cid_str))`, consistent with `get_node`/`gc()`), and consider vendoring minimal type stubs for the `cid` package so this class of bug is actually visible to mypy going forward.

---

### 8. `swarm_peers` has an error path that bypasses the API's own error handling

**File:** `py_ipfs_lite/api.py`, lines 312-347
**Severity:** Low.

```python
async def swarm_peers(request: Request) -> Any:
    peer: Peer = request.app.state.peer
    network = peer.host.get_network()   # <-- outside the try block
    peers_data = []
    try:
        if hasattr(network, "connections"):
            ...
    except Exception as e:
        logger.warning(f"Failed to list swarm peers: {e}")
    return JSONResponse(content={"Peers": peers_data})
```

Every other handler in `api.py` wraps its core logic in `try/except` and re-raises as `HTTPException`/lets `IPFSLiteError` propagate to the registered exception handler. Here, if `peer.host.get_network()` itself ever raised, it would bypass all of that and surface as a bare unhandled 500, inconsistent with the rest of the file.

**Fix:** move the `get_network()` call inside the try block, for consistency with the rest of the module.

---

### 9. `block_stat` does a `has()` then a separate `get()` — TOCTOU + redundant read

**File:** `py_ipfs_lite/api.py`, lines 147-172
**Severity:** Low.

```python
cid = parse_cid(arg)
has = await peer.blockstore.has(cid)
if not has:
    raise HTTPException(status_code=404, detail="Block not found locally")
data = await peer.blockstore.get(cid)
return JSONResponse(content={"Key": arg, "Size": len(data)})
```

Two lookups instead of one, and a window between them where a concurrent `block/rm` or `gc()` could remove the block, turning a "found" into a `None` from `get()` (which would then need yet another check). Since `BlockNotFoundError` is already registered to map to HTTP 404 (see the app-level exception handler), this could simply call `get()` once.

**Fix:**
```python
data = await peer.blockstore.get(cid)
if data is None:
    raise BlockNotFoundError(f"Block not found: {arg}")
return JSONResponse(content={"Key": arg, "Size": len(data)})
```

---

### 10. The project's own GC documentation example crashes, and exposes a `Peer` exception-safety gap

**Files:** `docs/guides/persistence-and-gc.md`, `py_ipfs_lite/peer.py`
**Severity:** Low, but user-facing (first thing a new user might copy-paste).

The documented walkthrough does:
```python
stats = await peer.gc()
print(f"Reclaimed: {stats.get('reclaimed_blocks')} blocks")
```
but `peer.gc()` returns a `GCResult` **dataclass** (`reclaimed_blocks: int; retained_blocks: int`), which has no `.get()` method. Running the example verbatim:
```
AttributeError: 'GCResult' object has no attribute 'get'
```
Should be `stats.reclaimed_blocks` (the doc even says a few lines later "stats is a GCResult dataclass," contradicting its own runnable snippet above it).

More interesting: because this exception happens *before* the example's `await peer.close()`, and `Peer` has no `__aenter__`/`__aexit__` (grepped the whole repo — it's never used as an async context manager anywhere, including this doc), the live nursery inside `peer.start()` never gets torn down cleanly. Trio's shutdown then reports:
```
AssertionError: Nursery misnesting detected!
...
RuntimeError: Nursery stack corrupted: Nursery surrounding <Task '__main__.main'> was closed before the task exited
```
instead of a clean `AttributeError`. So any exception between `start()` and `close()` — not just this one — turns into a confusing double-fault.

**Fix:** correct the doc snippet; consider adding `__aenter__`/`__aexit__` to `Peer` so `async with Peer(...) as peer:` is possible and exception-safe, and recommend it in docs/examples.

---

### 11. Metrics can drift from reality

**File:** `py_ipfs_lite/metrics.py`
**Severity:** Low — observability accuracy, not correctness of data.

```python
class MetricsBlockStore:
    async def put_block(self, cid: bytes, data: bytes) -> None:
        await self._store.put_block(cid, data)
        IPFS_BLOCKSTORE_BLOCKS_TOTAL.inc()
        IPFS_BLOCKSTORE_SIZE_BYTES.inc(len(data))
```

`put_block` is an idempotent overwrite in content-addressed storage (re-adding the same content is a no-op storage-wise), but the counters increment unconditionally on every call, with no matching decrement unless `delete_block` is later called. Re-adding existing content repeatedly inflates `ipfs_blockstore_blocks_total`/`ipfs_blockstore_size_bytes` beyond the real blockstore state.

Separately, `IPFS_BLOCKSTORE_BLOCKS_TOTAL` etc. are module-level Prometheus objects — global to the process, not per-`Peer`. Any process running more than one `Peer` (several of the project's own tests instantiate two, e.g. `test_car_export_import`) will have both peers' metrics merged into the same gauges/counters, making `/debug/metrics/prometheus` ambiguous in that scenario.

**Fix:** check `has_block()` before incrementing on `put_block` (or accept the imprecision explicitly in docs); consider per-instance metric labels (e.g. a peer-id label) if multi-peer-per-process is a supported scenario.

---

### 12. `add_file()` crashes on raw `bytes` (and on any non-`str` input) against `libp2p==0.7.0`

**File:** `py_ipfs_lite/peer.py`, `add_file()`, lines 366-403
**Severity:** High.
**Reported by:** user, while migrating a downstream project onto `py-ipfs-lite`. Confirmed by reproduction.

```python
kwargs: dict[str, Any] = {"wrap_with_directory": False}
...
async with self._gc_lock.read_lock():
    if isinstance(path_or_stream, str):
        cid = await self.dag_service.add_file(path_or_stream, **kwargs)
    else:
        cid = await self.dag_service.add_stream(path_or_stream, **kwargs)
```

Any non-`str` argument — including raw `bytes`, which the type hint (`str | BinaryIO`) doesn't claim to support but nothing stops you from passing — is routed to `dag_service.add_stream()`. Two independent problems there:

1. `MerkleDag.add_stream()`'s real signature in `libp2p==0.7.0` is:
   ```python
   async def add_stream(
       self,
       stream: io.IOBase,
       chunk_size: int | None = None,
       progress_callback: ProgressCallback | None = None,
   ) -> bytes:
   ```
   It has **no `wrap_with_directory` parameter at all** — that only exists on `add_file()`. So the `wrap_with_directory=False` that `Peer.add_file()` always includes in `kwargs` makes this call fail immediately, regardless of what `path_or_stream` actually is.
2. Even with that fixed, `add_stream()` expects a real `io.IOBase`-like object — its internals call `chunk_stream(stream, chunk_size)`, which reads it incrementally. Raw `bytes` doesn't implement that interface.
3. `libp2p` 0.7.0 ships a purpose-built method for exactly this case, `MerkleDag.add_bytes(data: bytes, chunk_size=None, progress_callback=None)` — no `wrap_with_directory`, since directory-wrapping only makes sense for named files. `Peer.add_file()` never calls it; there's no bytes-specific branch at all.

**Reproduction:**
```python
await peer.add_file(b"hello world, this is raw bytes not a path")
```
```
TypeError: MerkleDag.add_stream() got an unexpected keyword argument 'wrap_with_directory'
```

This fires for **any** non-`str` input, not just `bytes` — passing a correctly-constructed `io.BytesIO(...)` hits the identical `TypeError` before ever reaching the type-mismatch problem, since Python validates keyword arguments before the function body runs.

**Fix:** branch on `bytes`/`bytearray` and call `dag_service.add_bytes(data, chunk_size=..., progress_callback=...)`; for genuine `io.IOBase` streams, drop `wrap_with_directory` from the kwargs passed to `add_stream()` — it isn't accepted there either.

---

### 13. `ExchangeAdapter.get_block()` doesn't match the signature `MerkleDag` calls it with

**File:** `py_ipfs_lite/peer.py`, `_create_exchange()` (`ExchangeAdapter` class)
**Severity:** Medium–High — currently latent inside `Peer`'s own public methods, but immediately reachable via `peer.dag_service`.
**Reported by:** user, confirmed by reproduction.

```python
class ExchangeAdapter:
    def __init__(self, exchange: Any) -> None:
        self._exchange = exchange

    async def get_block(self, cid: Any) -> Any:
        data = await self._exchange.get_block(cid)
        if data:
            IPFS_BITSWAP_BYTES_RECEIVED_TOTAL.inc(len(data))
        return data

    def __getattr__(self, name: Any) -> Any:
        return getattr(self._exchange, name)
```

`ExchangeAdapter.get_block` takes one argument beyond `self` — matching `interfaces.py`'s own `Exchange` Protocol exactly (`async def get_block(self, cid: bytes) -> bytes | None: ...`). The problem is that `Peer._create_dag_service()` hands this adapter to `MerkleDag`, a `libp2p` class built to expect the fuller `BitswapClient` interface, not the narrower `Exchange` Protocol `ExchangeAdapter` was written against:

```python
# peer.py
def _create_dag_service(self) -> Any:
    return MerkleDag(self._exchange)
```

`libp2p==0.7.0`'s `MerkleDag._get_block()` (used internally by `fetch_file()` and its batch-fetch helpers) calls:

```python
return await self.bitswap.get_block(cid, peer_id, timeout)
```

— three positional arguments, matching `BitswapClient.get_block(self, cid, peer_id=None, timeout=DEFAULT_TIMEOUT)`'s real signature, but not `ExchangeAdapter`'s narrower one.

**Reproduction:**
```python
data, filename = await peer.dag_service.fetch_file(cid_str)
```
```
TypeError: Peer._create_exchange.<locals>.ExchangeAdapter.get_block() takes 2 positional arguments but 4 were given
```
Confirmed `peer.dag_service.bitswap is peer._exchange` — `peer.dag_service` is wired to the exact same adapter instance `Peer` uses internally, so this isn't a separate-object fluke.

**Important nuance, worth preserving for whoever fixes this:** `Peer.get_file()`/`Peer.get_node()`, as currently written, do **not** call into `dag_service` for reads — they reimplement their own traversal by hand, calling `self._exchange.get_block(current_cid)` with exactly one argument, which matches `ExchangeAdapter` and works fine today. Confirmed: round-tripped a 300KB / 2-chunk file through `Peer.get_file()` with no error. So this bug does not currently break `Peer.get_file()`/`Peer.get_node()` themselves. It breaks the moment anything calls `dag_service`'s own read path directly — exactly what reaching for `dag_service.fetch_file()` does, and exactly what a future refactor of `get_file()`/`get_node()` to delegate to `dag_service.fetch_file()` (arguably the more correct fix long-term, since it would pick up directory-wrapper handling, CID verification via `verify_cid`, and batch-fetching for free instead of today's hand-rolled, one-block-at-a-time duplicate) would immediately reintroduce.

Also confirmed directly: constructing a **fresh** `MerkleDag` against the raw, un-adapted `BitswapClient` (`peer._exchange._exchange`, bypassing `ExchangeAdapter` entirely) fetches correctly. This is almost certainly what "bypassing the wrappers" achieves in practice — a fresh `MerkleDag(raw_bitswap_client)` — rather than calling `peer.dag_service` itself, which is still wired to the same adapter and would crash identically on `fetch_file()`.

**Fix:** widen `ExchangeAdapter.get_block` to accept and forward the extra parameters:
```python
async def get_block(self, cid: Any, peer_id: Any = None, timeout: Any = None) -> Any:
    data = await self._exchange.get_block(cid, peer_id, timeout)
    if data:
        IPFS_BITSWAP_BYTES_RECEIVED_TOTAL.inc(len(data))
    return data
```
and update `interfaces.py`'s `Exchange` Protocol to match — it currently models the narrower surface `ExchangeAdapter` originally implemented, not what `libp2p.bitswap.dag.MerkleDag` actually requires from whatever `bitswap` object it's given. This is the same underlying category of problem as Bug #7: a thin py-ipfs-lite wrapper models a subset of an upstream `libp2p` interface, and nothing catches the drift until a specific code path actually runs.

---

## Part 2 — Test Coverage Analysis

### Overall: 64% statement coverage (`pytest-cov`, 40 tests, all passing)

| File | Stmts | Miss | Cover | Notably missing |
|---|---|---|---|---|
| `__init__.py` | 5 | 0 | **100%** | — |
| `config.py` | 23 | 0 | **100%** | — |
| `exceptions.py` | 10 | 0 | **100%** | — |
| `versioning.py` | 22 | 1 | 95% | — |
| `reprovider.py` | 43 | 5 | 88% | a couple error branches |
| `peer.py` | 450 | 79 | 82% | provider-retry logic inside `get_file`/`get_node`, parts of `fetch_stream`'s directory/DAG walk |
| `ipns.py` | 101 | 18 | 82% | pubkey-missing / malformed-record edge cases |
| `metrics.py` | 44 | 8 | 82% | `put_many`, error-swallow branches in `delete_block` |
| `interfaces.py` | 65 | 13 | 80% | adapter pass-through methods |
| `car.py` | 141 | 31 | 78% | **the exact `exchange.get_block` fallback line (Bug #1)** |
| `dag_utils.py` | 64 | 24 | 62% | dag-pb link expansion, `extract_links` recursion (**Bug #2's blind spot**) |
| `pin.py` | 66 | 26 | 61% | `_save()`/`_load()` failure paths |
| `api.py` | 244 | 127 | **48%** | see below — this is the "public endpoints" surface |
| `routing.py` | 153 | 88 | **42%** | most of `DelegatedHTTPRouting.provide()` and response-parsing branches in `find_providers()` |
| `cli.py` | 142 | 118 | **17%** | almost the entire file — no `test_cli.py` exists |
| `parser.py` | 37 | 34 | **8%** | argparse wiring never exercised directly |
| `main.py` | 5 | 5 | **0%** | trivial passthrough, low priority |

### `api.py` in detail — this is the part you asked about directly

Of 18 routes, only these are exercised through the actual FastAPI app (`ASGITransport` + `AsyncClient`/`TestClient`):
- `POST /api/v0/version`, `POST/GET /api/v0/id`, `POST /api/v0/repo/stat`, `POST /api/v0/swarm/peers` (`test_api.py`)
- `POST /api/v0/name/publish`, `GET /api/v0/name/resolve` (`test_ipns.py`)
- `GET /debug/metrics/prometheus` (`test_metrics.py`)
- `POST/GET /api/v0/repo/version` (`test_versioning.py`)
- `POST /api/v0/dag/get` error path only, for the 404/503 cases (`test_exceptions.py`)

**Zero HTTP-level coverage** for:
- `POST /api/v0/add` — file upload, temp-file handling, multipart parsing
- `POST/GET /api/v0/cat` — `StreamingResponse` path
- `POST /api/v0/dag/put` — JSON body parsing, codec selection
- `POST /api/v0/block/stat`, `POST /api/v0/block/rm`
- `POST /api/v0/pin/add`, `POST /api/v0/pin/rm`
- `POST /api/v0/repo/gc`
- `POST /api/v0/refs/local`

The underlying `Peer` methods behind most of these (`add_file`, `get_file`, `add_node`, `add_pin`, etc.) **are** tested directly in `test_peer.py`/`test_pin.py` — but the FastAPI request/response glue (query-param parsing, multipart handling, JSON-body parsing, status-code mapping, `StreamingResponse`) around them is not, which is exactly the layer where bugs like #8 and #9 live and would be caught.

Also uncovered: `lifespan()` (lines 31-55) — the default-peer auto-creation path used whenever `app.state.peer` isn't pre-set — is never triggered by any test, since every test manually assigns `app.state.peer` before making requests via `ASGITransport`, sidestepping the FastAPI lifespan mechanism entirely.

### `routing.py` and `cli.py` — thin and, in one case, misleading

- `tests/test_routing.py::test_delegated_routing` calls the real `https://cid.contact` over the network and asserts only `isinstance(providers, list)` — true whether the request succeeds, times out, or 403s. Confirmed by running it in a network-restricted sandbox: it still passes, taking 5.7s (the single slowest test in the 40-test suite, ~2x the runtime of the rest of the suite combined).
- `cli.py` has no dedicated test file. Its 293 lines cover argument-to-`Config` wiring for five subcommands and the `daemon --api` hypercorn bootstrap — including Bug #4, which untested code let through.
- `parser.py`'s argparse setup (choices, defaults, dest names) is only ever exercised indirectly by whichever `cli.py` paths happen to run, i.e. not at all in CI.

### Recommended additions, roughly in priority order

1. **HTTP-level tests for every write endpoint** (`add`, `cat`, `dag/put`, `dag/get`, `block/stat`, `block/rm`, `pin/add`, `pin/rm`, `repo/gc`, `refs/local`) through the real ASGI app, not just the underlying `Peer` methods. Include at least one round-trip (`add` → `cat`, `dag/put` → `dag/get`) per endpoint pair.
2. **A CAR export test where a needed block is missing locally** and must come from the exchange — would have caught Bug #1 immediately.
3. **A GC test with a direct pin on a node that has children** — would have caught Bug #2 immediately.
4. **`test_cli.py`** covering `main()`'s argument routing for all five subcommands, specifically including the `daemon --api` branch (Bug #4) and the plain `daemon` bootstrap call, likely via mocking `trio.run`/`hypercorn.trio.serve` and asserting `peer.bootstrap` was (or wasn't) called.
5. **Replace the live-network routing test** with `httpx.MockTransport` so `find_providers()`'s two response-format branches (IPIP-337 ndjson and the IPNI-native fallback) are actually exercised and asserted against known payloads, deterministically and offline.
6. **A `close()` test asserting the routing HTTP client is actually closed** (`peer.routing.routers[0].client.is_closed is True`), and a `close()`-after-partial-failure test.
7. **A metrics test** that puts the same CID twice and asserts the gauge doesn't double-count, plus a two-peers-in-one-process test checking metric attribution.
8. **`lifespan()` coverage** — a test that boots the app without pre-setting `app.state.peer`, to exercise the default-peer-creation path.

---

## Appendix: reproduction environment

```bash
git clone https://github.com/IPFS-Meshkit/py-ipfs-lite.git
cd py-ipfs-lite
python3 -m venv venv && source venv/bin/activate
apt-get install -y libgmp-dev   # needed to build fastecdsa, a transitive dep
pip install -e ".[test,dev]"
pytest tests/ -v                                    # 40 passed
mypy py_ipfs_lite/                                   # Success: no issues found
pytest tests/ --cov=py_ipfs_lite --cov-report=term-missing
```
