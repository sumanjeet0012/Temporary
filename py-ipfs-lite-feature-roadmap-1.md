# py-ipfs-lite: Feature & Gap-Closing Roadmap

This document lays out the features discussed for `py-ipfs-lite`, split into two
groups:

1. **Parity gaps** — things `go-ipfs-lite` (hsanjuan/ipfs-lite) already has that
   `py-ipfs-lite` is missing. `API_SPEC_GO_IPFS_LITE.txt` already describes the
   target shape for most of these; they just aren't implemented yet.
2. **Additional features** — things beyond `go-ipfs-lite` parity that are worth
   adding, especially given where this project is headed (GooseSwarm, the
   Filecoin grant work, agent-to-agent payments).

For every item: **why** it matters, **how** to approach it at a high level (no
code), and **where** the change belongs — inside `py-ipfs-lite` itself, or
upstream in the local `py-libp2p` dependency.

A quick note on "where": `py-ipfs-lite` is the orchestration/application layer
(daemon, CLI, file/DAG logic). `py-libp2p` is the lower-level networking layer
(host, transports, DHT, bitswap wire protocol, block storage primitives). As a
rule of thumb — if something is "how do I structure/use the network," it
belongs in `py-ipfs-lite`. If something is "the network protocol itself can't
do X," it belongs in `py-libp2p`.

---

## Part 1 — Closing the gap with go-ipfs-lite

### 1.1 Embeddable `Peer` class

**Why:** Right now everything is a set of module-level functions in
`main.py` driven by the CLI. `go-ipfs-lite`'s entire value proposition is that
you can `import` it and instantiate a `Peer` inside any application. Without
this class, `py-ipfs-lite` can only ever be a standalone daemon, not a library
other projects (like GooseSwarm) can embed directly.

**How:** Introduce a `Peer` object that owns one host, one routing table, one
blockstore, one exchange (bitswap client), and one DAG service. Its
constructor takes the already-defined `Config` plus optional pre-built
host/routing/datastore (so advanced users can bring their own), and it exposes
lifecycle methods (`bootstrap`, `close`) and data methods (`add`, `get`,
`remove`, `add_file`, `get_file`). Everything that's currently inline in
`run_daemon`/`run_add`/`run_get` in `main.py` gets lifted into methods on this
class; the CLI commands become thin wrappers that create a `Peer` and call its
methods.

**Where:** New file in `py-ipfs-lite`, e.g. `py_ipfs_lite/peer.py`. This is
pure orchestration of existing `py-libp2p` primitives (`new_host`, `KadDHT`,
`BitswapClient`) — no changes needed in `py-libp2p` for the class itself.

---

### 1.2 Generic DAG service (arbitrary IPLD nodes, not just files)

**Why:** Today, `add`/`get` only exist at the file level through
`MerkleDag`, which is UnixFS-chunking-specific. `go-ipfs-lite` exposes
`Add`/`Get`/`Remove` for arbitrary IPLD nodes — this is the foundation for
storing anything that isn't a flat file, which is exactly what's needed for
the "verifiable inference logs as IPLD DAGs" grant milestone (a log entry is a
structured node, not a chunked file).

**How:** Build a thin DAG layer that works directly against raw block
put/get rather than going through the UnixFS chunker. `add(node)` serializes
an IPLD node to bytes, computes its CID, and stores the block; `get(cid)`
fetches the block and deserializes it back into a node; `remove(cid)` deletes
it from the local blockstore only (matching go-ipfs-lite's semantics — it's
not a network-wide delete). File add/get stay as a separate, higher-level
convenience that's built on top of this generic layer rather than replacing
it.

**Where:** Mostly `py-ipfs-lite` — new module, e.g. `py_ipfs_lite/dag.py`,
sitting alongside (not replacing) the existing UnixFS-specific `MerkleDag`
usage. It will call into `py-libp2p`'s block storage and bitswap client for
the actual put/get/exchange. If those calls turn out to be hardcoded to
UnixFS shapes inside `py-libp2p`'s bitswap module rather than generic
byte-blob storage, a small adjustment in `py-libp2p` (libp2p/bitswap) to
expose a generic "put/get raw block" path would be the one upstream change
needed.

---

### 1.3 Persistent (on-disk) datastore

**Why:** The blockstore today is `MemoryBlockStore` — everything is lost on
restart. A long-running production node (which is what GooseSwarm needs) has
to survive restarts, hold a meaningful amount of content, and not blow up
memory usage. `go-ipfs-lite` supports pluggable on-disk datastores
(BadgerDB, flatfs) for exactly this reason.

**How:** Implement a new blockstore backed by something simple and
dependency-light to start (SQLite is a good first choice — single file,
no extra service to run, easy backup). It needs to satisfy the same
get/put/has/delete/get_size/all_keys surface the in-memory one does, so it can
be swapped in without touching the bitswap/DAG code that consumes it. Once
that contract is solid, a second backend (e.g. LMDB) can be added later for
higher throughput.

**Where:** `py-ipfs-lite` — new module, e.g. `py_ipfs_lite/datastore_sqlite.py`.
Because Python is duck-typed, this likely doesn't require any `py-libp2p`
change as long as `BitswapClient`/`MerkleDag` only call blockstore methods
generically rather than assuming `MemoryBlockStore` internals. Worth a quick
check of `libp2p/bitswap` for that assumption before starting — if it's there,
a small generalization patch goes upstream into `py-libp2p`.

---

### 1.4 Bootstrap + provider discovery via the DHT

**Why:** `get` currently requires manually passing a provider's multiaddr.
That's fine for two-machine testing but isn't how a real IPFS-style network
works — peers should be discoverable by CID alone, using the DHT to find who
has the content. `KadDHT` is already instantiated in `main.py`, it's just not
wired into the add/get flow.

**How:** On `add`, after storing a block, call the routing layer's "provide"
operation so the DHT announces "I have this CID." On `get`, when no explicit
provider is given, call the routing layer's "find providers" operation first
to get a list of multiaddrs, then connect to one (or several) and fetch
normally. A `bootstrap(peers)` method on the new `Peer` class (1.1) is also
needed so a node can join the wider DHT using a list of known bootstrap
addresses, the same way go-ipfs-lite's `Bootstrap()` works.

**Where:** Primarily wiring inside `py-ipfs-lite` (`peer.py` / `main.py`),
since the actual provide/find-providers Kademlia operations should already
exist inside `py-libp2p`'s `kad_dht` module (that's standard DHT
functionality). Worth confirming those methods are exposed publicly on
`KadDHT` — if not, that's a small upstream addition in `py-libp2p`.

---

### 1.5 Pinning + garbage collection

**Why:** Without pinning, there's no way to say "never delete this block."
Without garbage collection, there's no way to reclaim space from blocks
nobody cares about anymore. Both are basic hygiene any long-running node
needs, and both are present in the full IPFS/go-ipfs-lite ecosystem.

**How:** Maintain a pin set — a small persisted list of "pinned" root CIDs,
optionally marked recursive (meaning all of that DAG's children are also
protected). Garbage collection walks the blockstore, walks outward from every
pinned root to mark everything reachable, and removes anything left over
that isn't reachable from a pin.

**Where:** Entirely `py-ipfs-lite` — new module, e.g. `py_ipfs_lite/pin.py`,
plus a `gc()` method on `Peer`. This is pure application logic sitting on top
of the existing blockstore; no `py-libp2p` changes needed.

---

### 1.6 Reprovider loop

**Why:** The `Config` dataclass already has a `reprovide_interval_seconds`
field, but nothing actually uses it. Content needs to be re-announced to the
DHT periodically, otherwise provider records expire and the content becomes
effectively unfindable by anyone who isn't already directly connected.

**How:** A background task that wakes up every `reprovide_interval_seconds`
and re-announces every locally stored (or pinned) CID to the DHT, reusing the
same "provide" call from 1.4. Treat a negative interval as "disabled," which
is already the convention noted in the API spec.

**Where:** `py-ipfs-lite` — small new module, e.g.
`py_ipfs_lite/reprovider.py`, started as a background task when the `Peer`
starts. Built entirely on top of the `py-libp2p` provide() call from 1.4, so
no upstream change expected here specifically.

---

### 1.7 Swappable interfaces (Datastore / BlockStore / Exchange / Routing / Host)

**Why:** `API_SPEC_GO_IPFS_LITE.txt` section 8 already names these
interfaces, but nothing in the code currently enforces them — everything is
wired directly to concrete `py-libp2p` classes. Without a real interface
boundary, every future backend (1.3's persistent datastore, a future
alternate DHT, etc.) becomes a one-off hack instead of a clean swap.

**How:** Define formal interfaces (Python `Protocol` or abstract base
classes) matching the five contracts already sketched in the spec file
(Datastore, BlockStore, Exchange, DagService, Routing, Host). Then make sure
the concrete `py-libp2p` classes already in use (`MemoryBlockStore`,
`BitswapClient`, `KadDHT`, the libp2p `Host`) satisfy those contracts — either
because they already match structurally, or via a thin adapter/wrapper class
on the `py-ipfs-lite` side.

**Where:** `py-ipfs-lite` — new module, e.g. `py_ipfs_lite/interfaces.py`.
This should not require `py-libp2p` changes in most cases (Python duck typing
covers most of it); only the genuinely structural mismatches (if any) found
while doing 1.2/1.3 would need a small upstream tweak.

---

## Part 2 — Additional features beyond go-ipfs-lite parity

### 2.1 CAR file import/export

**Why:** CAR (Content Addressable aRchive) is the standard way to package a
DAG — root CID plus all its blocks — into one portable, verifiable file.
This maps directly onto the grant milestone for "verifiable inference logs as
IPLD DAGs": a CAR file is the natural deliverable format for a log/proof that
someone else needs to verify independently, and it's also the format Filecoin
deal-making tooling expects.

**How:** Add export (walk a DAG from a root CID, write out every block plus a
small header in CARv1 format) and import (read a CAR file, verify each
block's bytes hash to its claimed CID, and store the blocks). This sits on
top of the generic DAG service from 1.2 — it doesn't need anything new from
the network layer, just block read/write.

**Where:** `py-ipfs-lite` — new module, e.g. `py_ipfs_lite/car.py`. No
`py-libp2p` involvement; this is a pure serialization format on top of
already-stored blocks.

---

### 2.2 DAG-CBOR / generic IPLD codec support

**Why:** UnixFS (the current file format) is meant for files and
directories. Structured application data — like an agent's inference log
entry, with fields such as model name, prompt hash, timestamps, and a
signature — is a much better fit for DAG-CBOR, the IPLD codec built for
exactly this kind of structured, linkable data.

**How:** Add an encode/decode layer that can turn a plain Python
dict-like structure into DAG-CBOR bytes (and back), with proper multicodec
prefixing so the resulting CID correctly identifies it as DAG-CBOR rather
than DAG-PB. This plugs directly into the generic DAG service from 1.2 — adding
a DAG-CBOR node is just "encode struct to bytes, then call the same add(bytes)
the file DAG uses."

**Where:** Mostly `py-ipfs-lite` — new module, e.g. `py_ipfs_lite/codecs.py`.
If CID parsing/formatting utilities currently hardcode an assumption about
codec type (worth checking `libp2p/bitswap/cid` for this), a small addition
there in `py-libp2p` would be needed so CIDs can correctly round-trip a
DAG-CBOR multicodec tag, not just the file-codec one currently in use.

---

### 2.3 HTTP gateway

**Why:** Right now the only way to pull content out of a `py-ipfs-lite`
node is the custom newline-delimited TCP/JSON protocol in `api.py`. A
standard HTTP gateway (`/ipfs/<cid>`) makes content viewable in any browser
and trivially fetchable by any HTTP client, with zero custom protocol
knowledge required — this is what makes IPFS content actually shareable
outside the IPFS ecosystem.

**How:** A small HTTP server that, given a path like `/ipfs/<cid>`, resolves
the CID through the DAG/file service and streams the bytes back with
appropriate content headers. Directory listings (for UnixFS directories) can
be a simple HTML index page.

**Where:** `py-ipfs-lite` — new module, e.g. `py_ipfs_lite/gateway.py`, plus a
new CLI subcommand (`gateway`) in `parser.py`/`main.py`. No `py-libp2p`
changes needed — this only reads from things already exposed by the DAG
service.

---

### 2.4 Filecoin/FVM retrieval & deal hooks

**Why:** The grant work already includes an FVM AgentPayment contract and
x402-compatible payments. There's a natural opportunity to let
`py-ipfs-lite` (or a thin companion module) talk to Filecoin directly —
making a storage deal for a CID, or retrieving content from a Filecoin
storage provider when it isn't available over plain libp2p/bitswap. This
turns the "lite" peer into something that can fall back to Filecoin's much
larger storage network instead of being limited to whatever's currently
online over bitswap.

**How:** A module that wraps calls to a Filecoin node's API (e.g. a Lotus
JSON-RPC endpoint) for the two operations that matter here: starting a
storage deal for a given CID/CAR file, and retrieving content for a CID from
a storage provider when local/bitswap retrieval fails. This is intentionally
kept as an optional, separate concern — it should not be a hard dependency
for users who just want a plain embeddable libp2p-based peer.

**Where:** `py-ipfs-lite` (or, depending on how tightly it should couple to
the grant work, a separate companion package consumed by GooseSwarm) — new
module, e.g. `py_ipfs_lite/filecoin.py`. Entirely outside the libp2p protocol
layer, so no `py-libp2p` changes are involved.

---

### 2.5 Metrics & observability

**Why:** Once this runs as a long-lived production daemon, "is it actually
working" needs to be answerable without reading logs line by line. Counters
for blocks sent/received, active peer connections, and DHT lookups are the
minimum needed to notice when something's degraded.

**How:** Add lightweight counters/gauges (a small in-process metrics object
is enough to start; a Prometheus-compatible exporter can be layered on top
later) around the key events: block sent, block received, peer connected,
peer disconnected, DHT lookup attempted/succeeded. Expose them either via a
CLI subcommand that prints current stats, or via the HTTP gateway (2.3) on a
`/metrics` path.

**Where:** Mostly `py-ipfs-lite` — new module, e.g. `py_ipfs_lite/metrics.py`,
wired into the `Peer` class. If `BitswapClient` doesn't currently expose any
kind of callback/hook for "block sent" / "block received" events, a small
upstream addition in `py-libp2p`'s bitswap module to add such hooks would be
needed; otherwise this is fully self-contained in `py-ipfs-lite`.

---

### 2.6 Async context manager support on `Peer`

**Why:** Once the `Peer` class (1.1) exists, the most natural way to use it
in real code is `async with Peer(...) as p:` — guaranteeing the host/DHT/
bitswap client get cleanly shut down even if an exception happens partway
through, instead of relying on every caller remembering to call `close()`.

**How:** Add the two async context-manager methods to the `Peer` class —
entering returns the (already-started) peer, exiting calls the existing
`close()` method.

**Where:** `py-ipfs-lite` only — a small addition to `peer.py` once 1.1 is
in place. No `py-libp2p` involvement.

---

### 2.7 MCP-compatible RPC API (replacing the raw TCP/JSON protocol)

**Why:** The grant work includes a "decentralized MCP server registry on
Filecoin" milestone. Right now `api.py` speaks a one-off, hand-rolled
newline-delimited JSON protocol. Exposing the daemon's operations (add, get,
pin, gc, peer info) as proper MCP-style tools instead would let any
MCP-compatible client (including Claude itself) drive the node directly,
and keeps the project's API surface consistent with the rest of the
GooseSwarm/MCP-registry work rather than being a bespoke protocol nobody else
can reuse.

**How:** Wrap the existing daemon operations behind an MCP server interface
— each current "command" (add, get, etc.) becomes one MCP tool with a typed
input/output schema instead of an ad-hoc JSON dict. The underlying logic
(once the `Peer`/DAG service from 1.1/1.2 exist) doesn't change; only the
transport/interface wrapping it does.

**Where:** `py-ipfs-lite` — replaces (or sits alongside, during a transition
period) `api.py`. No `py-libp2p` involvement; this is purely an
application-layer interface choice.

---

### 2.8 Private network / swarm key support

**Why:** For a multi-tenant or agent-coordination use case like GooseSwarm,
it's useful to be able to run an isolated swarm that only nodes with a shared
secret can join, rather than always being part of the open public network.
This is standard libp2p private-network functionality, just not currently
wired up in `py-ipfs-lite`.

**How:** Accept an optional pre-shared key in the `Config`, and pass it
through when constructing the host so all connections are encrypted with
that shared secret rather than (or in addition to) the existing Noise/SecIO
transport security. Any node without the correct key simply can't complete a
handshake.

**Where:** Mostly `py-ipfs-lite` wiring (`config.py`, `peer.py` /
`main.py`'s host construction) to pass the key through. The actual
private-network (PNet) transport support needs to already exist in
`py-libp2p`'s security/transport layer — if it doesn't, that's the one
upstream addition required there.

---

## Suggested order of implementation

The items above aren't independent — several bonus features build directly
on top of the parity gaps. A reasonable order:

1. **1.1 Peer class** — everything else gets easier to slot in once this
   exists instead of being scattered across `main.py`.
2. **1.7 Swappable interfaces** — defining these early avoids having to
   retrofit them after 1.2/1.3 are already built against concrete classes.
3. **1.2 Generic DAG service** and **1.3 Persistent datastore** — these are
   the two biggest functional gaps and unblock the grant's "verifiable logs"
   milestone directly.
4. **1.4 Bootstrap/provider discovery**, **1.5 Pinning/GC**, **1.6 Reprovider**
   — round out parity with go-ipfs-lite.
5. **2.1 CAR files** and **2.2 DAG-CBOR** — natural next step once the DAG
   service exists; these are what make the "verifiable inference logs"
   milestone concrete and shippable.
6. **2.3 HTTP gateway**, **2.5 Metrics**, **2.6 Context manager** — quality-of-life
   and operability improvements once the core is stable.
7. **2.4 Filecoin/FVM hooks** and **2.7 MCP-compatible API** — these align
   most directly with the grant's later milestones (AgentPayment contract,
   MCP server registry) and make sense to build once the foundation above is
   solid.
8. **2.8 Private network support** — can be added whenever multi-tenant
   isolation actually becomes a requirement; it's the most independent item
   on this list.

---

## References

Repos and files consulted while putting this together:

- [sumanjeet0012/py-ipfs-lite](https://github.com/sumanjeet0012/py-ipfs-lite) — the repo this roadmap is for.
- [API_SPEC_GO_IPFS_LITE.txt](https://github.com/sumanjeet0012/py-ipfs-lite/blob/main/API_SPEC_GO_IPFS_LITE.txt) — the parity target spec already in the repo.
- [roadmap.txt](https://github.com/sumanjeet0012/py-ipfs-lite/blob/main/roadmap.txt) — the existing phased roadmap in the repo.
- [hsanjuan/ipfs-lite](https://github.com/hsanjuan/ipfs-lite) — the Go reference implementation (go-ipfs-lite) used for the parity comparison.
- [hsanjuan/ipfs-lite — pkg.go.dev reference](https://pkg.go.dev/github.com/hsanjuan/ipfs-lite) — Go API documentation for go-ipfs-lite (Peer, SetupLibp2p, DefaultBootstrapPeers, etc.).
