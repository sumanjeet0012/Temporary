# py-ipfs-lite bug hunt

**Repo:** [IPFS-Meshkit/py-ipfs-lite](https://github.com/IPFS-Meshkit/py-ipfs-lite)
**Commit:** `89fd7c80e6a4531c4757ee8a25cd7c2fd9f95c1e` ("Fix docs deploy workflow: pin python to 3.12", 2026-07-14)
**Method:** Installed the package from source (Python 3.12), ran the existing test suite as a baseline (51/51 pass), then read every module under `py_ipfs_lite/` and wrote targeted fuzzing/repro scripts against the public surface: the `Peer` class, the `PinStore`, the CAR import/export code, the IPNS record validator, the config dataclasses, and the FastAPI HTTP API (via `ASGITransport`, no real network needed — same pattern the project's own tests use). Every finding below is a confirmed, reproduced result, not a hypothesis from reading code.

19 issues found, grouped by severity. The most serious ones are silent-failure / silent-data-loss bugs rather than crashes — those are the ones I'd fix first.

---

## High severity

### 1. `import_car()` can report success while silently discarding blocks

**File:** `py_ipfs_lite/car.py`, `import_car()` (~L150-200), root cause in `BufferedAsyncReader.read_exactly()` (~L26-40)

Truncating a legitimate CAR file at specific byte offsets makes `import_car()` return the correct root CID and raise **no exception**, while storing **fewer blocks than the file actually contained** — in one case, zero.

Repro: exported a real 230-byte, 2-block CAR file (parent node linking to a child node) via `Peer.export_car()`, then truncated it at every possible byte offset and re-imported each with `Peer.import_car()`:

```
full file (230 bytes):        roots=[root_cid], 2 blocks stored
truncated to 177 bytes:       roots=[root_cid], 1 block stored   <- no error
truncated to  59 bytes:       roots=[root_cid], 0 blocks stored  <- no error
```

Root cause: `import_car`'s block-reading loop uses `read_varint()` raising a plain `TypeError` as its sentinel for "cleanly reached end of file," and `read_varint()` raises that *same* `TypeError` whenever the stream happens to end at the start of a block-length varint — which is indistinguishable from genuine EOF. Separately, `read_exactly()` doesn't raise when the underlying stream can't supply the requested byte count; it just returns however many bytes happen to be available (confirmed directly: asking a 5-byte stream for 100 bytes returns `b'de'` with no exception, and the internal `offset` then drifts past `len(buffer)` on subsequent calls). The hash-verification check later in `import_car` does catch most corruption (161/229 truncation points in my test correctly raised `ValueError: Hash mismatch`), but it can be bypassed entirely if the cut lands on one of these boundaries.

Practical impact: a CAR file that gets cut short (flaky transfer, disk full mid-write, a peer sending a partial file) can be imported with `roots` reporting full success, and the resulting "root" CID looks fine right up until something tries to actually walk the DAG and hits `BlockNotFoundError` — with no way to trace that failure back to a bad import.

Suggested fix: after the read loop, verify that every declared root (and reachable descendant, if you want to be thorough) actually has a corresponding block in the store before returning `roots`; and make `read_exactly` raise on a short read rather than silently returning less than requested.

---

### 2. dag-json NaN/Infinity: write succeeds, that exact CID becomes permanently unreadable via the HTTP API

**File:** `py_ipfs_lite/peer.py`, `encode_node()`/`decode_node()` (~L54-76); `py_ipfs_lite/api.py`, `dag_get` (~L136-149)

`encode_node(node, "dag-json")` calls `json.dumps(node, separators=(",", ":"))` with Python's default `allow_nan=True`, so a NaN or Infinity anywhere in the node tree gets silently serialized to the bare tokens `NaN`/`Infinity` — not valid JSON per RFC 8259, and something no conformant DAG-JSON parser in another language will accept. Minimal end-to-end repro against the real HTTP API:

```
POST /api/v0/dag/put?store-codec=dag-json   body: {"value": NaN}
  -> 200 OK, {"Cid": {"/": "baguqeeracwpztyb6y3p3p3ok3..."}}

GET /api/v0/dag/get?arg=baguqeeracwpztyb6y3p3p3ok3...
  -> 500 Internal Server Error
     {"detail":"Out of range float values are not JSON compliant: nan"}
```

The write path is permissive; Starlette's `JSONResponse` (used by `dag_get`) is strict about NaN by default. The block itself is fine — `peer.get_node(cid)` called directly in Python returns `{'value': nan}` without error — so the data isn't lost, but it's unreachable through the one HTTP endpoint that's supposed to serve it back, permanently, for as long as that CID exists.

Suggested fix: pass `allow_nan=False` in `encode_node`'s `json.dumps` call so this is rejected at write time with a clear error, matching what dag-json actually requires.

---

### 3. `Config.blockstore_type` typos silently fall back to in-memory storage

**File:** `py_ipfs_lite/config.py` (`Config`, no validation); `py_ipfs_lite/peer.py`, `_create_blockstore()` (~L246-260)

```python
_create_blockstore():
    if self.config.blockstore_type == "filesystem":
        ...  # FilesystemBlockStore
    else:
        raw_bs = MemoryBlockStore()   # <- anything else lands here
```

There's no validation anywhere that `blockstore_type` is one of the two supported values. Tested a matrix of inputs and checked which underlying store class actually got constructed:

```
blockstore_type='filesystem'   -> FilesystemBlockStore   (correct)
blockstore_type='FILESYSTEM'   -> MemoryBlockStore        <- silent fallback
blockstore_type='file-system'  -> MemoryBlockStore        <- silent fallback
blockstore_type='sqlite'       -> MemoryBlockStore        <- silent fallback
blockstore_type=''             -> MemoryBlockStore        <- silent fallback
```

A single case typo on the config value that's supposed to give you persistence gives you a node that silently runs in-memory-only, with no error and no warning — all data is gone on process restart, discovered only much later.

Suggested fix: validate `blockstore_type in ("filesystem", "memory")` in `Config.__post_init__` or in `_create_blockstore`, and raise `ValueError` otherwise.

---

### 4. IPNS record validation crashes on a malformed `validity` timestamp instead of raising a clean error

**File:** `py_ipfs_lite/ipns.py`, `validate_ipns_record()` (~L139-163)

The expiry check does `if validity_dt < datetime.now(timezone.utc):` after manually reformatting the record's `validity` string. If that string has no timezone marker (no `Z`, no `+HH:MM`) or uses a `-HH:MM` offset, `datetime.fromisoformat` returns a naive datetime, and comparing it against the timezone-aware `datetime.now(timezone.utc)` raises `TypeError: can't compare offset-naive and offset-aware datetimes` — which the surrounding `except ValueError:` does not catch, so it propagates unhandled.

Repro (constructed a validly-signed record — correct pubkey, correct V1 and V2 signatures — with only the validity string varied, calling `validate_ipns_record` directly):

```
validity=b'2099-05-10T12:00:00.123456'          (no tz)   -> TypeError, unhandled
validity=b'2099-05-10T12:00:00'                  (no tz)   -> TypeError, unhandled
validity=b'2099-05-10T12:00:00.123456-05:00'     (neg tz)  -> TypeError, unhandled
validity=b'2099-05-10T12:00:00.123456+05:00'     (pos tz)  -> OK, validates correctly
validity=b'not-a-date-at-all'                              -> OK, clean RoutingError
```

Only the `+HH:MM` case is handled — the parsing code has an explicit branch for `"+" in frac_tz` and nothing for a missing offset or a `-` offset, so it produces a naive datetime in exactly those two cases. `resolve_name()` doesn't catch `TypeError` either, so this propagates all the way to the caller; via the HTTP API, `/api/v0/name/resolve` returns a 500 with the raw Python message instead of the `RoutingError("Invalid IPNS validity format")` the code clearly intends to raise for bad records. Since IPNS records are resolved from data published by other peers, this means a record with a validity string that's syntactically slightly off from Kubo's exact format (which is easy to produce by accident, not just adversarially) can't be resolved at all, with a confusing error.

Suggested fix: catch `TypeError` alongside `ValueError` around the `fromisoformat`/comparison, or normalize non-`Z`/non-`+` offsets the same way the `+` case is already normalized.

---

### 5. CAR parsing surfaces three different unhandled exception types depending on where the file is truncated

**File:** `py_ipfs_lite/car.py`, `get_cid_len()` (~L69-79) and `import_car()` (~L150-200)

Same truncation sweep as finding #1, but looking at *which* exception type comes out (rather than the silent-success cases):

```
161/229 offsets -> ValueError            (the intended, documented "Hash mismatch"/parse error)
 57/229 offsets -> cbor2.CBORDecodeEOF: premature end of stream (...)
  6/229 offsets -> TypeError: ord() expected a character, but string of length 0 found
  3/229 offsets -> EOFError
  2/229 offsets -> no error (finding #1)
```

The `TypeError` comes from `get_cid_len()`, which hand-rolls CID-prefix parsing with raw byte indexing (`data[0]`, `data[1]`) and calls into the third-party `varint` package's `decode_stream`, which internally does the equivalent of `ord(stream.read(1))` — on a truncated stream that returns `ord(b'')`, which is the confusing `TypeError` above, not an `IndexError` or `EOFError`. `get_cid_len` also has a more subtle problem: it treats the two bytes `0x12 0x20` as sufficient evidence of a full 34-byte legacy CIDv0 prefix and returns `34` unconditionally, without checking that 34 bytes actually exist — so `import_car` can slice past the end of a short buffer without any error at that point either (Python slicing doesn't raise on an out-of-range end index, so this only surfaces later, if at all).

The `cbor2.CBORDecodeEOF` comes from the unguarded `loads(header_bytes)` call — `CBORDecodeEOF` is a subclass of `CBORDecodeError`/`CBORError`, not of `ValueError` or `EOFError`, so it isn't caught by anything in `import_car` and isn't one of `py_ipfs_lite`'s own `IPFSLiteError` types either.

Net effect: a truncated or corrupted CAR file — again, this doesn't require malice, just an interrupted transfer — produces four different outcomes depending on the exact byte offset, three of which are raw, unwrapped, third-party exception types rather than anything `py_ipfs_lite.exceptions` defines, and one of which is silent success with missing data (#1).

Suggested fix: wrap the header/block reads in `import_car` to catch `(cbor2.CBORError, TypeError, IndexError, EOFError)` and re-raise as a single documented `CarParseError`; have `get_cid_len` check `len(data) >= 34` before trusting the legacy-prefix shortcut.

---

## Medium severity

### 6. `Peer.add_pin()` / `PinStore` accept anything as a CID — no format validation at all

**File:** `py_ipfs_lite/pin.py`, `PinStore.add_pin()` (~L55-59); confirmed at the `Peer.add_pin()` level too

```python
peer = <started Peer>
for v in ["", "not-a-cid", "x"*5000, None, 123, 3.14, True, b"..."]:
    await peer.add_pin(v)   # every single one: accepted, no exception
```

Only genuinely unhashable types (`[]`, `{}`) are rejected, and only because Python dicts require hashable keys — that's an accident of implementation, not intentional validation. Contrast with `Peer.list_pins(type_filter=...)`, which *does* validate its `type_filter` argument and raises a clean `ValueError` for anything outside `{"all","direct","recursive","indirect"}` — so the codebase clearly knows how to validate string arguments, it just doesn't do it here.

This isn't just inert either: every garbage value that gets "pinned" is later visited by `list_pins()`'s indirect-pin DAG walk, which fails to parse it, logs a warning, and moves on — meaning every subsequent `list_pins("all")` or `list_pins("recursive")` call pays the cost of re-attempting (and re-failing) to traverse each piece of garbage that was ever pinned, for the life of the pin store.

At the HTTP layer this is directly reachable: `POST /api/v0/pin/add?arg=not-a-valid-cid` returns **`200 OK`**, `{"Pins": ["not-a-valid-cid"]}`.

Suggested fix: call `parse_cid(cid_str)` (already used everywhere else in `peer.py`) at the top of `add_pin` and let it raise its existing clean `ValueError`.

---

### 7. Malformed client input returns HTTP 500, not 4xx, across several endpoints — and leaks raw internal error text

**File:** `py_ipfs_lite/api.py`, multiple handlers

Every handler follows the same pattern: catch `IPFSLiteError` and let the registered exception handler map it to 404/503; catch everything else and turn it into `HTTPException(500, detail=str(e))`. Since `parse_cid`, `json.loads`, and `ID.from_base58` all raise plain `ValueError`/`json.JSONDecodeError` (not `IPFSLiteError`) for bad input, all of the following are 100% client-caused and all come back as 500:

```
GET  /api/v0/dag/get?arg=not-a-valid-cid          -> 500  "Invalid CID string: not-a-valid-cid"
GET  /api/v0/name/resolve?arg=not-a-valid-peerid  -> 500  "Invalid character '-'"
POST /api/v0/dag/put   body: b"{not valid json!!"  -> 500  "Expecting property name enclosed in double quotes: ..."
POST /api/v0/dag/put   body: b""                   -> 500  "Expecting value: line 1 column 1 (char 0)"
```

Beyond the semantically-wrong status code, the raw exception text (parser internals, dependency-specific wording) goes straight into the JSON response's `detail` field.

Suggested fix: catch `(ValueError, TypeError, json.JSONDecodeError)` explicitly where user-supplied strings/bodies are parsed and map those to 400/422, reserving 500 for genuine server-side failures.

---

### 8. A small, deeply-nested JSON body to `/api/v0/dag/put` reliably triggers `RecursionError`

**File:** `py_ipfs_lite/api.py`, `dag_put()`

```
body = "[" * depth + "1" + "]" * depth

depth=5000    (10 KB)  -> 200 OK
depth=20000   (40 KB)  -> 500, "maximum recursion depth exceeded while decoding a JSON array from a unicode string"
depth=100000  (200 KB) -> same
```

This is caught by `dag_put`'s own `except Exception` (so it's a clean-ish 500 for that one request, not a process crash — Starlette handles each request independently), but it's still a client-triggerable, cheap-to-construct (40 KB), CPU-burning failure mode reachable on an unauthenticated endpoint, and — same as #7 — it comes back as a 500 for what is unambiguously bad client input.

Suggested fix: bound nesting depth (or overall body size) before/while parsing, or catch `RecursionError` explicitly and map it to 400/413.

---

### 9. `reprovide_interval_seconds=0` causes an uncontrolled busy loop, not "disabled"

**File:** `py_ipfs_lite/reprovider.py`, `Reprovider.start()` (~L15-24)

```python
async def start(self):
    if self.interval < 0:
        return   # disabled
    ...
    while True:
        await self.reprovide()
        await trio.sleep(self.interval)   # sleep(0) is just a checkpoint, not a delay
```

Only strictly-negative values disable the reprovider; `0` is treated as "reprovide as fast as possible." Measured directly: with `reprovide_interval_seconds=0` and 2 fake CIDs to reprovide, `routing.provide()` was called **8,236 times in 0.5 seconds of wall-clock time** — an unbounded loop hammering the routing layer.

Suggested fix: treat `interval <= 0` as disabled, or enforce a sane minimum sleep.

---

### 10. Passing `bytes` instead of `str` as a CID doesn't fail fast — for `get_node()` it can hang for the full timeout

**File:** `py_ipfs_lite/peer.py`, `get_node()` (~L547-590), via `libp2p.bitswap.cid.parse_cid`

The underlying `parse_cid` intentionally accepts `bytes` as raw CID bytes (a documented, legitimate use case for constructing CIDs programmatically) — but every `Peer` method typed as taking `cid_str: str` accepts it too, with no type check, silently reinterpreting it as something totally different from what a "CID string" argument implies:

```python
await peer.remove_node(b"bytes-not-str")   # no exception, silently no-ops
await peer.has_block(b"bytes-not-str")     # no exception, returns False
await peer.get_node(b"bytes-not-str")      # hangs ~30s (the default_timeout), then TooSlowError
```

For `get_node`, the arbitrary bytes happen to parse as *some* structurally valid CID, so the local-blockstore lookup misses, and (with routing available) the code falls through to `self._exchange.get_block(cid)`, which blocks until `trio.fail_after(default_timeout)` fires — 30 seconds by default — and raises a bare `trio.TooSlowError` with no message explaining what went wrong. A plausible, easy-to-make mistake (passing `bytes` where `str` was intended) turns into either a silent no-op or a half-minute hang depending on which method you called, rather than an immediate, clear error either way.

Suggested fix: `isinstance(cid_str, str)` check at the top of the `cid_str`-taking methods.

---

### 11. `resolve_name()` / `publish_name()` crash with a bare `AttributeError` when the peer is offline

**File:** `py_ipfs_lite/peer.py`, `resolve_name()` (~L688-700), `publish_name()` (~L701-724)

`Config(offline=True)` is a documented, supported mode (`_create_routing` deliberately returns `None` for it), but neither method checks `self.routing` before using it:

```python
peer = Peer(Config(offline=True, blockstore_type="memory"), ...); await peer.start()
await peer.resolve_name("12D3Koo...")   # AttributeError: 'NoneType' object has no attribute 'get_value'
await peer.publish_name("/ipfs/x")      # AttributeError: 'NoneType' object has no attribute 'put_value'
```

Via HTTP, `/api/v0/name/publish` and `/api/v0/name/resolve` against an offline daemon fall into the generic exception handler and return a 500 with that same raw attribute-error text.

Suggested fix: `if self.routing is None: raise RoutingError("IPNS requires network routing; this peer is offline")` at the top of both methods.

---

## Lower severity / smaller findings

| # | Finding | Where |
|---|---|---|
| 12 | `MetricsBlockStore.delete_block()` unconditionally decrements the `ipfs_blockstore_blocks_total` gauge even when the block never existed — confirmed it going to **-1.0** after deleting a nonexistent CID from a fresh store. | `metrics.py` `MetricsBlockStore.delete_block` |
| 13 | `TieredRouting.put_value()` swallows exceptions from *every* sub-router silently and returns `None` either way — no way to tell "stored somewhere" from "stored nowhere," unlike `provide()`, which does return a success bool. | `routing.py` `TieredRouting.put_value` |
| 14 | `AddParams.chunker` values like `"size-abc"`, `"size-"`, `"SIZE-1024"` (wrong case) are silently ignored (falls back to default chunking, no warning); `"size-0"` is accepted and passed through as a literal `chunk_size=0` with no validation. | `peer.py` `add_file()`, inline chunker parsing |
| 15 | `lifetime_hours` on `create_ipns_record`/`publish_name` isn't validated. Very large magnitude values crash with two *different* unhandled `OverflowError`s (`date value out of range` for `-999999999`; `Python int too large to convert to C int` for `10**18`) rather than a clean validation error. Also accepts `0`/negative silently, producing already-expired records. | `ipns.py` `create_ipns_record` |
| 16 | `versioning.init_repo_version("")` crashes with a raw `FileNotFoundError: [Errno 2] No such file or directory: ''` instead of a clear message about an invalid path. | `versioning.py` |
| 17 | Two separate, behaviorally-different `encode_node`/`decode_node` pairs exist: `peer.py`'s (used by `add_node`/`get_node`, raises `ValueError` on an unknown codec) and `dag_utils.py`'s (used by `walk_dag`/`export_car`'s link-following, silently falls back to JSON for an unknown codec — and its `encode_node` isn't called from anywhere in the shipped code at all, confirmed via grep). Not currently exploitable through the normal call graph since callers pre-filter the codec, but it's a maintenance trap and dead code. | `dag_utils.py` vs `peer.py` |
| 18 | `add_node(node, codec="raw")` crashes with `AttributeError: 'dict' object has no attribute 'encode'` if `node` is a dict or list — `add_node`'s type signature (`dict | list | str | int | bytes`) advertises support for all of those, but the `"raw"` branch in `encode_node` only actually handles `str`/`bytes`. | `peer.py` `encode_node` |
| 19 | Re-pinning an already-pinned CID with a different `recursive` value silently changes the pin type (recursive → direct observed) with no error or warning — children of that CID lose GC protection with no signal to the caller. | `pin.py` `PinStore.add_pin` |

---

## A pattern worth naming

Several of these (3, 6, 9, 14, 15, plus the negative connection-watermark values I also tried and which `Peer.start()` accepted without complaint) are instances of the same thing: **`Config`/`AddParams` fields and free-form string "enum" arguments throughout the codebase aren't validated against their allowed set.** Where validation *does* exist (`list_pins`'s `type_filter`, the codec checks in `peer.py`'s `encode_node`/`decode_node`), it's solid — clean `ValueError`s with good messages. It just isn't applied consistently to config construction or to some of the sibling functions doing the same conceptual job (`PinStore.get_pins` vs. `Peer.list_pins`). A single validation pass over `Config.__post_init__` and the handful of string-typed knobs would close most of the medium/low findings at once.

---

## What I didn't cover

This was a black/gray-box pass from the outside — public `Peer` methods, the HTTP API, and the standalone parsing modules (`car.py`, `ipns.py`, `dag_utils.py`, `pin.py`, `versioning.py`). I didn't fuzz the real libp2p networking/DHT/Bitswap paths (those live in the `libp2p` dependency, not this repo), and I didn't look at the CLI argument parser (`parser.py`/`cli.py`) beyond reading it — that'd be a reasonable next pass, especially given how many of the bugs above trace back to unvalidated strings turning into `Config` fields, which is exactly what the CLI constructs from argv.
