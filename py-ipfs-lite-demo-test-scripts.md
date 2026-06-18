# py-ipfs-lite: Test Scripts for the 7 Demo Cases

Each case below is a small, self-contained script you can run directly with
`python <file>.py` (they call `trio.run(...)` internally, so no extra runner
is needed). They double as both a meeting demo (clear `print()` output) and a
real test (each one has an `assert` that fails loudly if the behavior
regresses).

## Prerequisites

- Run from the repo root, with the package installed in editable mode:
  `pip install -e ".[test]"`
- Python 3.10+, same as the rest of the repo.
- Save each script below as its own file (suggested names given per case) —
  some cases need two separate script files run one after another.
- None of these need internet access; everything runs on `127.0.0.1`.

---

## Case 1 — Embeddable Peer: two independent peers in one process

**Situation:** Prove `Peer` is a real importable object, not tied to one
global CLI daemon. We start two fully independent peers (own host, own DHT,
own blockstore, own bitswap client) inside a single Python script.

`demo_1_embeddable_peers.py`:

```python
import trio
from py_ipfs_lite.peer import Peer
from py_ipfs_lite.config import Config


async def main():
    peer_a = Peer(Config(reprovide_interval_seconds=-1), listen_addrs=["/ip4/127.0.0.1/tcp/0"])
    peer_b = Peer(Config(reprovide_interval_seconds=-1), listen_addrs=["/ip4/127.0.0.1/tcp/0"])

    await peer_a.start()
    await peer_b.start()

    print("Peer A id:   ", peer_a.host.id())
    print("Peer A addrs:", peer_a.host.addrs())
    print("Peer B id:   ", peer_b.host.id())
    print("Peer B addrs:", peer_b.host.addrs())

    assert peer_a.host.id() != peer_b.host.id()
    assert peer_a._started and peer_b._started

    await peer_a.close()
    await peer_b.close()
    print("Both peers closed cleanly.")


trio.run(main)
```

**What to look for:** two different peer IDs and two different listen
addresses printed from one process. This is the thing that simply wasn't
possible before — the old code had one global daemon state.

---

## Case 2 — Content discovery by CID alone (DHT bootstrap + find providers)

**Situation:** Peer A adds a file. Peer B fetches it by CID only — no
provider multiaddr passed in. Peer B has to bootstrap into Peer A's DHT
first (otherwise it has nobody to ask), then `get_file` internally calls
`find_providers` and connects automatically.

`demo_2_dht_discovery.py`:

```python
import trio
from py_ipfs_lite.peer import Peer
from py_ipfs_lite.config import Config


async def main():
    peer_a = Peer(Config(reprovide_interval_seconds=-1), listen_addrs=["/ip4/127.0.0.1/tcp/0"])
    peer_b = Peer(Config(reprovide_interval_seconds=-1), listen_addrs=["/ip4/127.0.0.1/tcp/0"])

    await peer_a.start()
    await peer_b.start()

    peer_a_addr = str(peer_a.host.addrs()[0])
    print("Bootstrapping Peer B against Peer A:", peer_a_addr)
    await peer_b.bootstrap([peer_a_addr])

    cid = await peer_a.add_file(__file__)  # adds this script as the demo content
    print("Peer A added file. CID:", cid)

    # Note: no provider_addr argument here on purpose.
    content = await peer_b.get_file(cid)
    print(f"Peer B fetched {len(content)} bytes without being told who has it.")

    assert len(content) > 0

    await peer_a.close()
    await peer_b.close()


trio.run(main)
```

**What to look for:** Peer B's fetch succeeds with zero knowledge of Peer A
beyond the bootstrap address — it found Peer A as a provider through the DHT
on its own. (With only two peers in the network this resolves almost
instantly since Peer A is the only entry in Peer B's routing table; the same
mechanism is what lets it scale to real networks with many peers.)

---

## Case 3 — Structured data as an IPLD node (inference-log shape)

**Situation:** Store something that isn't a flat file — a dict shaped like
an agent inference-log entry — using a real IPLD codec (`dag-cbor`), then
read it back. This is the exact mechanism the "verifiable inference logs"
grant milestone needs.

`demo_3_ipld_node.py`:

```python
import trio
from py_ipfs_lite.peer import Peer
from py_ipfs_lite.config import Config


async def main():
    peer = Peer(Config(reprovide_interval_seconds=-1), listen_addrs=["/ip4/127.0.0.1/tcp/0"])
    await peer.start()

    log_entry = {
        "agent": "summarizer-agent-01",
        "model": "claude-sonnet-4-6",
        "prompt_hash": "bafy...exampleprompthash",
        "timestamp": "2026-06-18T12:00:00Z",
    }

    cid = await peer.add_node(log_entry, codec="dag-cbor")
    print("Stored inference log as a dag-cbor node. CID:", cid)

    fetched = await peer.get_node(cid)
    print("Fetched back:", fetched)

    assert fetched == log_entry

    await peer.close()


trio.run(main)
```

**What to look for:** the round-tripped dict matches exactly, and the CID
printed is a real content address for structured data — not a file CID.
Worth pointing out in the meeting that swapping `codec="dag-cbor"` for
`codec="dag-json"` works identically, since both go through the same
generic `add_node`/`get_node` path.

---

## Case 4 — Pinning + garbage collection

**Situation:** Store two nodes, pin only one, run GC, confirm the unpinned
one is gone and the pinned one survives.

`demo_4_pin_and_gc.py`:

```python
import trio
from py_ipfs_lite.peer import Peer
from py_ipfs_lite.config import Config
from libp2p.bitswap.cid import parse_cid


async def main():
    peer = Peer(Config(reprovide_interval_seconds=-1), listen_addrs=["/ip4/127.0.0.1/tcp/0"])
    await peer.start()

    cid_keep = await peer.add_node({"name": "pinned-log"})
    cid_drop = await peer.add_node({"name": "unpinned-log"})
    print("Stored two nodes:")
    print("  keep:", cid_keep)
    print("  drop:", cid_drop)

    await peer.add_pin(cid_keep, recursive=False)
    print("Pinned:", cid_keep)

    stats = await peer.gc()
    print("GC stats:", stats)

    keep_present = await peer.blockstore.has(parse_cid(cid_keep))
    drop_present = await peer.blockstore.has(parse_cid(cid_drop))
    print("Pinned block still present:  ", keep_present)
    print("Unpinned block still present:", drop_present)

    assert keep_present is True
    assert drop_present is False

    await peer.close()


trio.run(main)
```

**What to look for:** the GC stats dict showing one block reclaimed and one
retained, then the two boolean checks confirming exactly which block
survived.

---

## Case 5 — Restart durability (filesystem blockstore)

**Situation:** This one needs two separate process runs to actually prove
durability — the whole point is that the second process knows nothing
except a CID and a folder path. Run the first script, let it fully exit,
then run the second one with the CID it printed.

`demo_5a_write.py`:

```python
import trio
from py_ipfs_lite.peer import Peer
from py_ipfs_lite.config import Config


async def main():
    config = Config(
        blockstore_type="filesystem",
        blockstore_path="./demo_blocks",
        reprovide_interval_seconds=-1,
    )
    peer = Peer(config, listen_addrs=["/ip4/127.0.0.1/tcp/0"])
    await peer.start()

    cid = await peer.add_node({"note": "this should survive a process restart"})
    print("Stored node. CID:", cid)
    print("Copy this CID — pass it to demo_5b_read.py")

    await peer.close()


trio.run(main)
```

`demo_5b_read.py` (run as a brand new process, after the first one has
fully exited):

```python
import sys
import trio
from py_ipfs_lite.peer import Peer
from py_ipfs_lite.config import Config


async def main(cid):
    config = Config(
        blockstore_type="filesystem",
        blockstore_path="./demo_blocks",
        reprovide_interval_seconds=-1,
    )
    peer = Peer(config, listen_addrs=["/ip4/127.0.0.1/tcp/0"])
    await peer.start()

    node = await peer.get_node(cid)
    print("Fetched after a full process restart:", node)

    assert node == {"note": "this should survive a process restart"}

    await peer.close()


trio.run(main, sys.argv[1])
```

**Run it as:**
```
python demo_5a_write.py
# copy the printed CID, then in a fresh terminal/process:
python demo_5b_read.py <the CID printed above>
```

**What to look for:** the second process — which never saw the first one
running — reads the exact same data straight off disk via
`./demo_blocks`. This is the proof that the in-memory-only limitation is
gone.

---

## Case 6 — Kubo-compatible HTTP API

**Situation:** No Python script needed here — this is best demoed with the
daemon running in one terminal and `curl` in another, since the whole point
is showing it speaks the same HTTP shape as Kubo/go-ipfs.

**Terminal 1 — start the daemon with the API enabled:**
```
python -m py_ipfs_lite.main daemon --api --api-host 127.0.0.1 --api-port 5001 \
  --blockstore-type filesystem --blockstore-path ./demo_blocks
```

**Terminal 2 — exercise the API:**
```
echo "hello from py-ipfs-lite" > hello.txt

# add a file
curl -s -F file=@hello.txt http://127.0.0.1:5001/api/v0/add

# cat it back (use the Hash/CID returned above)
curl -s "http://127.0.0.1:5001/api/v0/cat?arg=<CID_FROM_ADD>"

# store a structured node
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"hello":"world"}' \
  "http://127.0.0.1:5001/api/v0/dag/put?store-codec=dag-json"

# fetch it back
curl -s "http://127.0.0.1:5001/api/v0/dag/get?arg=<CID_FROM_DAG_PUT>"

# pin it, then garbage collect
curl -s -X POST "http://127.0.0.1:5001/api/v0/pin/add?arg=<CID_FROM_DAG_PUT>&recursive=true"
curl -s -X POST "http://127.0.0.1:5001/api/v0/repo/gc"
```

**What to look for:** every response shape (`Hash`, `Cid./`, `Pins`, GC
stats) mirrors what the real Kubo HTTP RPC API returns for the equivalent
endpoint — worth saying out loud, since it's what makes "existing IPFS
tooling could plausibly talk to this" a credible claim rather than a stretch.

---

## Case 7 — Reprovider running on a visible interval

**Situation:** The default reprovide interval (12 hours) is too long to show
live, so for the demo only, override it to a few seconds and watch the log
lines confirm it's actually re-announcing content to the DHT on a loop.

```
python -m py_ipfs_lite.main --debug daemon --reprovide-interval 10 \
  --blockstore-type filesystem --blockstore-path ./demo_blocks
```

**What to look for:** roughly every 10 seconds, log lines like:
```
Reproviding N blocks to the DHT...
Finished reproviding N/N blocks.
```
appear without any manual trigger — this is the background task confirming
content stays discoverable over time instead of only right after it was
added.

---

## Notes for the meeting

- Cases 1–5 are pure Python and can run completely offline, back to back, in
  a single demo session — good for a tight time slot.
- Case 6 is the one most likely to land with anyone who's used `ipfs` /
  Kubo before, since the curl output looks immediately familiar.
- Case 7 is the weakest "wow" moment live (it's just log lines), so it's
  fine to mention it rather than run it if time is short.
