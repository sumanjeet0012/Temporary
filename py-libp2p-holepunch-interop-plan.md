# py-libp2p Hole Punching Interop — Implementation Plan

Target repo: `libp2p/unified-testing` (hole-punch test suite)
Scope: get py-libp2p (`main` branch) passing DCUtR hole-punch interop tests, verified locally.

py-libp2p already ships working DCUtR + CircuitV2 relay + AutoNAT primitives, with
reference scripts at `examples/nat/{relay,listener,dialer}.py` (added in PR #870).
That's the starting point for the test app rather than building from scratch.

---

## 1. Recon & Baseline Validation

Goal: confirm the framework itself works before touching py-libp2p.

- Clone `unified-testing`, read `docs/bash.md`, `hole-punch/README.md`, and
  `hole-punch/lib/run-single-test.sh` to internalize the 5-container topology
  (dialer-router, listener-router, relay, dialer, listener) and the Redis
  coordination protocol (`TEST_KEY`, `<TEST_KEY>_relay_multiaddr`,
  `<TEST_KEY>_listener_peer_id`).
- `hole-punch/images.yaml` currently registers one relay and one peer
  implementation: `rust-v0.56` (`quic-v1`/`tcp`, `noise`/`tls`,
  `yamux`/`mplex`). Use it as the baseline and as the schema template for
  adding py-libp2p (image name, build context, `transports`/
  `secureChannels`/`muxers` lists, separate `relays:` vs
  `implementations:` entries — a relay needs its own `Dockerfile.relay`
  in addition to the peer's `Dockerfile.peer`).
- Run it as a sanity check before adding a new implementation:
  ```bash
  cd hole-punch
  ./run.sh --impl-select "~rust"
  ```
  This confirms your local Docker setup (NET_ADMIN capability, bridge
  networking, Redis container) works before you introduce a new variable.

## 2. py-libp2p Capability Audit

- Pull latest `main` of py-libp2p, install in a fresh venv.
- Run `examples/nat/relay.py`, `listener.py`, `dialer.py` manually (not in
  Docker yet) on localhost or between two machines/VMs to confirm current
  DCUtR + CircuitV2 + AutoNAT actually completes a direct-connection upgrade
  on `main` — not just that the code exists.
- Note current gaps against the test app spec's requirements: env-var driven
  config (`TRANSPORT`, `SECURE_CHANNEL`, `MUXER`, `IS_DIALER`, `IS_RELAY`,
  `PEER_IP`, `ROUTER_IP`, `REDIS_ADDR`, `TEST_KEY`), Redis-based coordination
  (examples likely use CLI args/static multiaddrs instead), stdout YAML
  results (`handshakeTime`), and stderr-only logging.
- Check which transport/muxer/security combos py-libp2p actually supports
  today (likely tcp+noise+yamux, maybe quic-v1) — this becomes the initial
  test matrix scope; don't try to cover every combo on day one.

## 3. Build the Test Application

Single Python entrypoint (`main.py`) that branches on `IS_RELAY`/`IS_DIALER`,
reusing the three example scripts as a base:

- Add a small `redis` (or `redis.asyncio`) client for coordination —
  poll/set the two keys per the spec.
- Wire env vars into py-libp2p host construction (transport/security/muxer
  selection, listen addr = `PEER_IP`/`RELAY_IP`).
- **Relay**: publish its multiaddr to Redis, then just run.
- **Dialer**: poll relay multiaddr → connect → poll listener peer ID → dial
  through relay → start timer at DCUtR initiation → wait for the transport
  upgrade to report a **direct** (non-relayed) connection → stop timer →
  optionally ping over it → print `handshakeTime`/`unit: ms` YAML to stdout
  → exit 0/non-zero.
- **Listener**: register peer ID in Redis → connect to relay, make a
  reservation → wait passively for DCUtR to complete.
- Critical: verify "direct" by checking the actual established connection's
  remote multiaddr/transport in py-libp2p's connection manager, not just
  that DCUtR "succeeded" — false positives here are the most common
  interop bug.

## 4. Containerize & Register (local build only)

- Write a `Dockerfile` (multi-stage: install py-libp2p from the target
  commit/branch + deps, copy test app).
- Add an entry to `hole-punch/images.yaml` following the existing schema
  (implementation name/version, image build path, supported
  transport/security/muxer combos scoped to what was validated in step 2).
- Keep the initial matrix narrow: `tcp/noise/yamux` self-to-self
  (py-libp2p × py-libp2p) first, before adding cross-implementation combos.
- Build the image locally and confirm it starts cleanly before wiring it
  into the test runner:
  ```bash
  docker build -t unified-testing/python-holepunch:local .
  docker run --rm unified-testing/python-holepunch:local python -c "import libp2p"
  ```

## 5. Local Test Execution

```bash
cd hole-punch
./run.sh --impl-select "~python" --debug
```

- Use `--debug` first for verbose stderr logs from all 5 containers.
- Debug in this order when something fails:
  1. Do both peers get the relay multiaddr from Redis?
  2. Does the relayed connection establish?
  3. Does DCUtR negotiate at all?
  4. Does it produce a *direct* connection, or silently stay relayed?
- Once py-libp2p-only passes, expand the matrix to
  `--impl-select "~python|~rust"` to catch cross-implementation protocol
  mismatches (these are usually the real bugs — wire-format or
  muxer/security negotiation edge cases).
- Re-run the full local matrix after each fix and track `handshakeTime`
  trends to catch performance regressions, not just pass/fail.

## 6. Local Sign-off Checklist

- [ ] `~rust` baseline passes locally
- [ ] `examples/nat/*` scripts manually confirm DCUtR works on py-libp2p `main`
- [ ] Test app built, env-var contract matches spec, Redis coordination works
- [ ] Docker image builds and runs standalone
- [ ] `~python` self-to-self matrix passes locally under `--debug`
- [ ] `~python|~rust` cross-implementation matrix passes
- [ ] No flaky failures across at least 3 consecutive local runs
