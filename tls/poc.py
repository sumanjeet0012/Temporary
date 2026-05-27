from __future__ import annotations

import json
import socket
import ssl
import time

import multiaddr
import trio

from libp2p import generate_new_rsa_identity, new_host
from libp2p.custom_types import TProtocol
from libp2p.security.tls.transport import PROTOCOL_ID as TLS_PROTOCOL_ID
from libp2p.security.tls.transport import TLSTransport
from libp2p.utils.varint import encode_delim, read_varint_prefixed_bytes_sync

from common import find_free_port, wait_for_event, write_json_artifact


class TracingTLSTransport(TLSTransport):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.accepted_event = trio.Event()
        self.accepted_sessions: list[dict[str, object]] = []

    async def secure_inbound(self, conn):
        session = await super().secure_inbound(conn)
        peer_cert = session.conn.get_peer_certificate()
        self.accepted_sessions.append(
            {
                "accepted": True,
                "peer_cert_present": peer_cert is not None,
                "remote_peer": str(session.get_remote_peer()),
                "local_peer": str(session.get_local_peer()),
                "used_placeholder_identity": peer_cert is None,
                "remote_address": session.get_remote_address(),
            }
        )
        self.accepted_event.set()
        return session


def _read_delim_sync(sock_file) -> bytes:
    data = read_varint_prefixed_bytes_sync(sock_file)
    if not data.endswith(b"\n"):
        raise RuntimeError(f"missing newline delimiter in {data!r}")
    return data[:-1]


def run_raw_tls_client(host: str, port: int) -> dict[str, object]:
    result: dict[str, object] = {
        "host": host,
        "port": port,
        "peer_cert_sent": False,
    }
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.settimeout(5)
        sock_file = sock.makefile("rwb", buffering=0)

        sock_file.write(encode_delim(b"/multistream/1.0.0"))
        result["multistream_response"] = _read_delim_sync(sock_file).decode()

        sock_file.write(encode_delim(b"/tls/1.0.0"))
        result["tls_select_response"] = _read_delim_sync(sock_file).decode()

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_alpn_protocols(["libp2p"])

        tls_sock = ctx.wrap_socket(sock, server_hostname=None)
        result["tls_handshake_completed"] = True
        result["selected_alpn"] = tls_sock.selected_alpn_protocol()
        result["cipher"] = tls_sock.cipher()
        time.sleep(1.0)
        tls_sock.close()
    return result


async def main() -> None:
    key_pair = generate_new_rsa_identity()
    tracing_tls = TracingTLSTransport(key_pair)
    host = new_host(key_pair=key_pair, sec_opt={TLS_PROTOCOL_ID: tracing_tls})

    port = find_free_port("tcp")
    listen_addr = multiaddr.Multiaddr(f"/ip4/127.0.0.1/tcp/{port}")

    async with host.run(listen_addrs=[listen_addr]):
        client_results = []
        for attempt in range(2):
            client_results.append(
                await trio.to_thread.run_sync(run_raw_tls_client, "127.0.0.1", port)
            )
            with trio.fail_after(10):
                while len(tracing_tls.accepted_sessions) < attempt + 1:
                    await tracing_tls.accepted_event.wait()
                    tracing_tls.accepted_event = trio.Event()

        placeholder_peer_ids = [
            session["remote_peer"]
            for session in tracing_tls.accepted_sessions
            if session["used_placeholder_identity"]
        ]

        result = {
            "finding": "tls_inbound_fail_open",
            "official_entrypoint": "new_host(..., sec_opt={/tls/1.0.0: TLSTransport(...)})",
            "listener_addr": str(host.get_addrs()[0]),
            "server_peer_id": str(host.get_id()),
            "client_results": client_results,
            "server_observation": {
                "accepted_session_count": len(tracing_tls.accepted_sessions),
                "accepted_sessions": tracing_tls.accepted_sessions,
                "all_sessions_used_placeholder_identity": all(
                    session["used_placeholder_identity"]
                    for session in tracing_tls.accepted_sessions
                ),
                "distinct_placeholder_peer_ids": len(set(placeholder_peer_ids)),
            },
            "impact": (
                "Two inbound TLS sessions were accepted even though the client sent "
                "no certificate and no libp2p identity, and each session was surfaced "
                "with a fresh synthetic placeholder peer identity."
            ),
        }
        write_json_artifact("result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    trio.run(main)
