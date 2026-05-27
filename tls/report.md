# TLS Inbound Mutual-Auth Fail-Open

## Summary

Affected entrypoint: `new_host(..., sec_opt={/tls/1.0.0: TLSTransport(...)})`

This issue was validated against the latest upstream `main` at test time,
commit `1e113ca309c866dd6f6125d57882adbf26f668fa` (`libp2p` version `0.6.0`
from `pyproject.toml`).

A remote client can complete the inbound libp2p TLS path without presenting a client certificate or a libp2p peer identity. The server still returns a `SecureSession` and assigns a synthetic placeholder peer identity to the remote side.

The attached PoC is in [attachments/poc.py](attachments/poc.py). The observed result is in [attachments/result.json](attachments/result.json).

Relevant spec: libp2p TLS requires mutual authentication and peer ID binding during the TLS 1.3 handshake.

## Root Cause Analysis

- `libp2p/security/tls/transport.py:126-138` builds the server `SSLContext` with `ssl.CERT_NONE`.
- `libp2p/security/tls/transport.py:305-355` handles `get_peer_certificate() is None` as a warning path, not a failure path.
- In that branch, the code generates a placeholder keypair and returns a normal `SecureSession` instead of aborting the inbound handshake.

The result is a secure-transport success path that does not authenticate the remote peer at all.

## Reproduce Steps

1. From the repository root, run:

   ```bash
   PYTHONPATH=. python3 reports/01-tls-inbound-fail-open/attachments/poc.py
   ```

2. The PoC opens two raw TCP connections, negotiates `/tls/1.0.0`, and completes a TLS 1.3 handshake without sending a client certificate on either session.
3. Inspect [attachments/result.json](attachments/result.json).

Observed result:

- both entries in `client_results` have `peer_cert_sent = false`
- `server_observation.accepted_session_count = 2`
- every accepted session has `peer_cert_present = false`
- `server_observation.all_sessions_used_placeholder_identity = true`
- `server_observation.distinct_placeholder_peer_ids = 2`

## Impact

This is an authentication bypass in a secure transport.

- Any remote party can obtain an accepted inbound TLS session without proving a libp2p identity.
- The connection is upgraded into normal secure-session state even though no remote identity was authenticated.
- Downstream code that treats an accepted `SecureSession` as an authenticated peer can be misled.
- The host associates the connection with a synthetic peer ID that did not come from the wire, which is unsafe for accounting, allowlists, logging, and policy enforcement.
- Repeated unauthenticated connections are assigned fresh synthetic peer IDs, so the same remote party is surfaced to higher layers as a sequence of unrelated authenticated-looking peers.

The core security property of libp2p TLS is mutual peer authentication. Returning a valid `SecureSession` without a remote certificate breaks that property directly.

## Recommended Fix

- Require a client certificate on inbound TLS.
- Treat `get_peer_certificate() is None` as a hard handshake failure.
- Remove the placeholder peer-ID fallback from the normal TLS transport path.
- Keep any AutoTLS bootstrap logic separate from the authenticated libp2p TLS path.
