# py-libp2p: QUIC "Cannot start a closed connection" Crash on Shutdown

Repo: `sumanjeet0012/py-libp2p` @ `fix-1390` (commit `13a9d34` and earlier)

## Symptom

Server crashes during shutdown (`peer.close()` in py-ipfs-lite) with an
unhandled `ExceptionGroup` cascading through hypercorn's lifespan shutdown
handler. Root exception:
```
File ".../libp2p/transport/quic/connection.py", line 356, in start
    raise QUICConnectionError("Cannot start a closed connection")
libp2p.transport.quic.exceptions.QUICConnectionError: Cannot start a closed connection
```
The exception propagates all the way up through `network`'s background
service → `basic_host._run` → the ASGI lifespan context manager → hypercorn,
taking the whole process down instead of failing just the one connection.

## Root cause

`Swarm.add_conn()` schedules the muxed connection's startup as a
**background task**, not an inline call:
```python
self.manager.run_task(muxed_conn.start)
await muxed_conn.event_started.wait()
```
There's a real gap between "task scheduled" and "task actually runs." If
the connection closes in that window — plausible during shutdown, when many
connections are torn down at once, or under normal churn when a peer drops
right after being added — `start()` hits:
```python
if self._closed:
    raise QUICConnectionError("Cannot start a closed connection")
```
Because this runs as a **managed task** (via the `anyio_service`/
`trio_manager` framework), an unhandled exception here doesn't just fail
that one connection — it propagates up through the entire task tree. One
connection dying in a normal race with shutdown/churn takes the whole
process down with it.

There's a second, related gap in the same code path:
`Swarm.add_conn()` does `await muxed_conn.event_started.wait()` with no
timeout and no check against the closed state. If `start()` were changed to
silently return without setting `event_started`, `add_conn` would hang
forever instead of crashing — so both places need to change together.

## Fix

**1. `libp2p/transport/quic/connection.py` — don't raise; unblock waiters instead:**

```python
async def start(self) -> None:
    if self.event_started.is_set():
        logger.debug("Connection already signalled to Swarm")
        return

    if self._closed:
        logger.debug(
            f"Connection to {self._remote_peer_id} closed before it could "
            "be signalled to Swarm; skipping start instead of raising, so "
            "the connection manager task tree isn't taken down by a "
            "connection that died in a normal race with shutdown/churn."
        )
        # Still set event_started so Swarm.add_conn (which is waiting on
        # this) is unblocked instead of hanging forever on a connection
        # that will never actually start.
        self.event_started.set()
        return

    self._started = True
    logger.debug(f"QUIC connection ready for Swarm: {self._remote_peer_id}")
    self.event_started.set()
```

**2. `libp2p/network/swarm.py`, `add_conn` — detect the dead connection instead of treating it as live:**

```python
self.manager.run_task(muxed_conn.start)
await muxed_conn.event_started.wait()

if getattr(muxed_conn, "is_closed", False):
    raise SwarmException(
        f"Connection to {muxed_conn.peer_id} closed before it could be "
        "added to the swarm"
    )

logger.debug(
    f"Swarm::add_conn | event_started received for peer {muxed_conn.peer_id}"
)
```

Place this immediately after the existing `event_started.wait()` (before
the `is_established` checks that follow). `SwarmException` here is caught by
the same dial-failure handling already in place further up the call chain,
so this fails just that one connection attempt cleanly instead of
cascading into a process crash.

## Why this matters more now

This is a pre-existing race, not something introduced by the routing-table
or connection-manager fixes — but it surfaces more often now that
connection churn is higher (faster ramp-up, larger watermarks, more
concurrent activity), making the close-during-start window more likely to
be hit in practice, especially during shutdown when many connections close
in a short span.

## How to verify

1. Apply both changes and redeploy.
2. Trigger a shutdown while the node has an active, churning connection set
   (mid-ramp-up is a good time to test, since that's when this raced in
   practice).
3. Confirm shutdown completes cleanly with no `QUICConnectionError`/
   `ExceptionGroup` crash — a debug log line for the skipped connection is
   expected and fine.
4. Confirm no hangs on shutdown (checks the `add_conn` fix didn't introduce
   a wait that never resolves).
