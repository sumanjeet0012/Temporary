# KadDHT Signed PeerRecord Identity-Binding Bypass

## Summary

Affected entrypoint: `KadDHT.find_peer()` over `/ipfs/kad/1.0.0`

This issue was validated against the latest upstream `main` at test time,
commit `1e113ca309c866dd6f6125d57882adbf26f668fa` (`libp2p` version `0.6.0`
from `pyproject.toml`).

A malicious DHT responder can return a signed `PeerRecord` whose envelope is signed by the attacker but whose payload claims to belong to an arbitrary target peer ID. The record is accepted and stored in the victim's certified address book, so the target peer ID resolves to attacker-controlled addresses.

This is the KadDHT `signedRecord` ingestion variant of the same signed-peer-record identity-binding invariant previously fixed on the Identify / IdentifyPush path.

The attached PoC is in [attachments/poc.py](attachments/poc.py). The observed result is in [attachments/result.json](attachments/result.json).

Relevant specs: signed envelopes authenticate the envelope signer, and peer records are expected to be signed by the identity that owns the embedded peer ID.

## Root Cause Analysis

- `libp2p/peer/envelope.py:99-111` validates only the envelope signature.
- `libp2p/peer/peerstore.py:323-345` trusts `record.peer_id` from the payload when storing the peer record.
- `libp2p/kad_dht/utils.py:73-84` checks that `record.peer_id == msg.id`, but does not check that the envelope public key derives to the same peer ID.

As a result, the implementation verifies that the envelope was signed by someone, but does not verify that it was signed by the peer whose record is being stored.

## Reproduce Steps

1. From the repository root, run:

   ```bash
   PYTHONPATH=. python3 reports/05-dht-signed-peerrecord-poisoning/attachments/poc.py
   ```

2. The PoC starts a malicious DHT responder and a victim client.
3. The responder answers `KadDHT.find_peer()` with a `signedRecord` whose payload says `peer_id = target`, but whose envelope is signed with the attacker's private key.
4. After poisoning, the PoC performs an official `host.connect()` to the target peer ID with no direct addresses supplied.
5. Inspect [attachments/result.json](attachments/result.json).

Observed result:

- `find_peer_result.peer_id` equals the forged target peer ID
- `find_peer_result.addrs` contains the attacker-controlled address
- `stored_envelope_signer_peer_id` is the attacker
- `stored_envelope_record_peer_id` is the target
- `signer_matches_record_peer_id = false`
- `poisoned_dial_observation.victim_connect_reached_poisoned_addr = true`
- `poisoned_dial_observation.sink_first_bytes_hex = 132f6d756c746973747265616d2f312e302e300a`

The final line above is the varint-delimited `/multistream/1.0.0` preface, showing that the official dial path was redirected to the attacker-controlled endpoint.

## Impact

This is a discovery-integrity failure on the official DHT path.

- A victim can be made to resolve an arbitrary peer ID to attacker-controlled addresses.
- The poisoned record is stored in the certified address book, not just returned transiently.
- Future dials, peer selection, and higher-level protocols that consume the certified address book inherit the poisoned mapping.
- Official `host.connect()` attempts for the target peer ID are redirected to attacker-controlled endpoints.
- Even when a later secure dial rejects the identity mismatch, the victim still spends time and network attempts on attacker-selected endpoints and loses reachability to the legitimate peer.

The trust boundary here is the signed peer record itself. Accepting signer/payload mismatches defeats the purpose of using signed peer records as an authenticated routing primitive.

## Recommended Fix

- Enforce `ID.from_pubkey(envelope.public_key) == record.peer_id` before storing any `PeerRecord`.
- Put this check in `consume_peer_record()` so every caller benefits from the same invariant.
- Keep protocol-specific checks such as `record.peer_id == msg.id`, but do not rely on them as a substitute for signer binding.
