#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
from typing import Any

DEFAULT_SOCKET = "/run/lion-docker-p0/provider.sock"
MAX_RESPONSE = 512 * 1024


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def send_request(request: dict[str, Any], *, socket_path: str = DEFAULT_SOCKET) -> dict[str, Any]:
    raw = canonical_json(request) + b"\n"
    if len(raw) > 128 * 1024:
        raise ValueError("request exceeds provider bound")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.connect(socket_path)
        conn.sendall(raw)
        conn.shutdown(socket.SHUT_WR)
        buf = bytearray()
        while True:
            part = conn.recv(8192)
            if not part:
                break
            buf.extend(part)
            if len(buf) > MAX_RESPONSE:
                raise RuntimeError("provider response exceeds bound")
    response = json.loads(bytes(buf).decode("utf-8"))
    if not isinstance(response, dict):
        raise RuntimeError("provider response malformed")
    return response


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, help="path to one canonical request JSON object")
    parser.add_argument("--socket", default=DEFAULT_SOCKET)
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise SystemExit("request must be a JSON object")
    response = send_request(request, socket_path=args.socket)
    print(canonical_json(response).decode("utf-8"))
    return 0 if response.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
