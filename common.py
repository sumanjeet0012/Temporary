from __future__ import annotations

import json
from pathlib import Path
import socket
from typing import Any

import trio


ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT


def find_free_port(kind: str = "tcp") -> int:
    if kind not in {"tcp", "udp"}:
        raise ValueError(f"unsupported socket kind: {kind}")

    sock_type = socket.SOCK_STREAM if kind == "tcp" else socket.SOCK_DGRAM
    with socket.socket(socket.AF_INET, sock_type) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def write_json_artifact(name: str, data: Any) -> Path:
    path = ARTIFACTS / name
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path


def write_text_artifact(name: str, data: str) -> Path:
    path = ARTIFACTS / name
    path.write_text(data)
    return path


async def wait_for_event(event: trio.Event, timeout: float = 5.0) -> None:
    with trio.fail_after(timeout):
        await event.wait()
