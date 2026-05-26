# Python v0.4 transport interop: Docker build workaround → upstream fix

This document explains the root problem addressed in two PRs authored by **@sumanjeet0012** in `libp2p/test-plans`, and how the fix evolved from a **Docker build workaround** to a **proper library fix**.

- PR 1: **#729** — _chore: stabilize Python v0.4 Docker build and unify multi-implementation fixes_  
  https://github.com/libp2p/test-plans/pull/729
- PR 2: **#750** — _fix: python interop test_  
  https://github.com/libp2p/test-plans/pull/750

---

## 1) What was the issue?

### 1.1 Multihash dependency conflict in the Python v0.4 image
During the Python v0.4 Docker build / runtime environment setup, two different multihash Python packages were pulled in:

- `multiaddr` depends on **`py-multihash`**
- `py-libp2p` depends on **`pymultihash`**

These end up conflicting (same “problem space” / overlapping behavior). Depending on install order, you can end up with the *wrong* multihash implementation effectively being used, causing imports and/or runtime behavior to break in interop runs.

### 1.2 Python ↔ Rust Yamux interop issue (data with SYN/ACK)
In addition to the dependency conflict, Python v0.4 had trouble interoperating with Rust over **yamux** due to how Rust can send payload data alongside SYN/ACK frames. Python’s yamux implementation needed to read that data to avoid protocol/stream issues.

---

## 2) How PR #729 solved it (workaround in Docker build)

PR: https://github.com/libp2p/test-plans/pull/729  
Author: **@sumanjeet0012**  
Merged: **2025-11-13**  
Title: _chore: stabilize Python v0.4 Docker build and unify multi-implementation fixes_

### 2.1 Force the correct multihash package to “win” (Dockerfile fix)
File changed: `transport-interop/impl/python/v0.4/Dockerfile`

After installing dependencies, PR #729 adds explicit steps to correct the conflicting state:

- install the project (`pip install -e .`)
- then:
  - uninstall `py-multihash`
  - force-reinstall `pymultihash>=0.8.2`

This is the key “stabilization” workaround: it makes the Docker build deterministic by ensuring `pymultihash` is installed in the final environment, even if `py-multihash` was pulled in by `multiaddr`.

**Conceptually:**
- **Problem:** dependency resolver/install order leads to conflicting packages.
- **Workaround:** enforce the desired final state manually during the Docker build.

### 2.2 Patch yamux to interop with Rust
Files changed/added:

- `transport-interop/impl/python/v0.4/Dockerfile` (apply patch step)
- `transport-interop/impl/python/v0.4/yamux-rust-fix.patch` (new)

The patch makes the yamux implementation read any data that comes with SYN and ACK frames (which Rust sends). This improves Python↔Rust transport interop reliability.

### 2.3 Supporting stability work (ping test hardening)
File changed: `transport-interop/impl/python/v0.4/ping_test.py`

PR #729 also includes a large set of improvements to make the interop test more stable and diagnosable (timeouts, redis retry logic, stream creation retries, better address handling, optional debug logging, etc.). While not the *root* packaging conflict fix, these changes reduce flakiness and improve observability.

---

## 3) How PR #750 solved it (fix in the library, remove need for Docker hacks)

PR: https://github.com/libp2p/test-plans/pull/750  
Author: **@sumanjeet0012**  
Merged: **2025-12-14**  
Title: _fix: python interop test_

### 3.1 Switch Python v0.4 implementation to a fixed py-libp2p commit
File changed: `transport/impls.yaml`

PR #750 updates the Python v0.4 implementation source:

- From:
  - `repo: libp2p/py-libp2p`
- To:
  - `repo: sumanjeet0012/py-libp2p`
- And pins it to a commit:
  - `commit: e79b6e9f2d7adf6cd1d089e6696d39f43af12c6f`

**Meaning:** instead of relying on custom Dockerfile steps to “repair” dependency conflicts at build time, test-plans now points at a **py-libp2p version that includes the real fix**.

So the flow becomes:

- **PR #729:** fix it in *test-plans Docker build* so CI and local builds become stable.
- **PR #750:** once the fix is in *py-libp2p*, update test-plans to use that fixed lib version and remove reliance on special Docker modifications.

---

## 4) Timeline summary (issue → workaround → proper fix)

### Root problem
- Python v0.4 interop container could fail because:
  1) **multihash dependency conflict** (`py-multihash` vs `pymultihash`)
  2) **yamux interop** differences with Rust (data with SYN/ACK frames)

### Phase 1 (PR #729)
- Add deterministic Docker build steps to enforce the correct multihash package.
- Add a yamux patch for Rust interop.
- Harden ping test behavior and logging.
- Result: builds/tests become stable again, but fix is partly a “build-time workaround”.

### Phase 2 (PR #750)
- Update test-plans to use a py-libp2p commit that contains the upstream fix.
- Result: the solution is now owned by the library, and the “custom Docker reinstall workaround” is no longer needed long term.

---

## 5) References

- PR #729: https://github.com/libp2p/test-plans/pull/729
- PR #750: https://github.com/libp2p/test-plans/pull/750
