#!/usr/bin/env python3
"""Scoped Windows 8780 -> MOON WSL read-only bridge (ports 8780/8783).

Never a canonical provider, never runtime authority, no mutation.
Accepts GET /health and scoped GET /api/missions/<id>/cognitive-readiness only.
It never opens or writes the ThreadStore DB and never calls material workers itself.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import subprocess
from threading import BoundedSemaphore, Thread
from urllib.error import HTTPError
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import urlopen

WINDOWS_POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
WINDOWS_CANONICAL = "http://127.0.0.1:8780"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PATH = re.compile(r"/api/missions/([A-Za-z0-9][A-Za-z0-9._:-]{0,255})/cognitive-readiness\Z")
MAX_BYTES = 1_048_576
INFLIGHT = BoundedSemaphore(2)


def _allowed_target(request_path: str) -> str | None:
    if len(request_path) > 900:
        return None
    parsed = urlsplit(request_path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        return None
    path = unquote(parsed.path)
    if path == "/health" and not parsed.query:
        return WINDOWS_CANONICAL + path
    match = PATH.fullmatch(path)
    if not match:
        return None
    try:
        query = parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True)
    except ValueError:
        return None
    if set(query) != {"conversation_id", "binding_epoch"}:
        return None
    cid = query["conversation_id"]
    epoch = query["binding_epoch"]
    if len(cid) != 1 or not ID.fullmatch(cid[0]) or len(epoch) != 1:
        return None
    if not epoch[0].isdigit() or not 1 <= int(epoch[0]) <= 2_147_483_647:
        return None
    # Keep the validated query representation exactly as the caller provided it.
    return WINDOWS_CANONICAL + request_path


def _windows_get(target: str) -> tuple[int, bytes]:
    encoded = base64.b64encode(target.encode("utf-8")).decode("ascii")
    ps = (
        "$ErrorActionPreference=\"Stop\";"
        "$u=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(\"" + encoded + "\"));"
        "$req=[Net.HttpWebRequest]::Create($u);"
        "$req.Method=\"GET\";$req.AllowAutoRedirect=$false;"
        "$req.Timeout=3500;$req.ReadWriteTimeout=3500;"
        "try{$resp=$req.GetResponse()}"
        "catch [Net.WebException]{$resp=$_.Exception.Response;"
        "if($null -eq $resp){exit 4}};"
        "$ms=New-Object IO.MemoryStream;"
        "$resp.GetResponseStream().CopyTo($ms);"
        "$status=[int]$resp.StatusCode;$resp.Close();"
        "Write-Output (\"LION_STATUS=\"+$status);"
        "Write-Output (\"LION_BODY=\"+[Convert]::ToBase64String($ms.ToArray()))"
    )
    result = subprocess.run(
        [WINDOWS_POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, timeout=8, check=False,
    )
    if result.returncode or len(result.stdout) > MAX_BYTES * 2:
        raise RuntimeError("Windows canonical transport unavailable")
    lines = [line.strip() for line in result.stdout.decode("ascii", "replace").splitlines()]
    statuses = [line[12:] for line in lines if line.startswith("LION_STATUS=")]
    payloads = [line[10:] for line in lines if line.startswith("LION_BODY=")]
    if len(statuses) != 1 or len(payloads) != 1:
        raise RuntimeError("Windows canonical response incomplete")
    status = int(statuses[0])
    if not 100 <= status <= 599:
        raise ValueError("invalid upstream HTTP status")
    data = base64.b64decode(payloads[0], validate=True)
    if len(data) > MAX_BYTES:
        raise ValueError("upstream response too large")
    body = json.loads(data.decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("upstream JSON object required")
    if status == 200:
        if body.get("authority_effect") != "NONE":
            raise ValueError("upstream authority classification invalid")
        if target.endswith("/health") and body.get("status") != "ok":
            raise ValueError("Windows provider health invalid")
        if "cognitive-readiness" in target:
            parsed = urlsplit(target)
            scope = PATH.fullmatch(unquote(parsed.path))
            query = parse_qs(parsed.query, strict_parsing=True)
            rd = body.get("readiness")
            if (
                scope is None
                or body.get("mission_id") != scope.group(1)
                or body.get("conversation_id") != query["conversation_id"][0]
                or type(body.get("binding_epoch")) is not int
                or body["binding_epoch"] != int(query["binding_epoch"][0])
                or not isinstance(rd, dict)
                or rd.get("mission_id") != body["mission_id"]
                or rd.get("conversation_id") != body["conversation_id"]
                or rd.get("binding_epoch") != body["binding_epoch"]
                or rd.get("authority_effect") != "NONE"
                or not HEX64.fullmatch(str(rd.get("projection_digest") or ""))
            ):
                raise ValueError("Windows readiness scope or projection invalid")
    return status, data


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _reply(self, status: int, data: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def _error(self, status: int, code: str):
        data = json.dumps({"error": code, "authority_effect": "NONE"}, separators=(",", ":")).encode("utf-8")
        self._reply(status, data)

    def do_GET(self):
        target = _allowed_target(self.path)
        if target is None:
            return self._error(404, "ROUTE_NOT_EXPOSED")
        if not INFLIGHT.acquire(blocking=False):
            return self._error(503, "READONLY_BRIDGE_BUSY")
        try:
            status, data = _windows_get(target)
        except (OSError, RuntimeError, ValueError, binascii.Error, json.JSONDecodeError,
                subprocess.TimeoutExpired, UnicodeDecodeError):
            self._error(502, "WINDOWS_CANONICAL_READBACK_UNAVAILABLE")
        else:
            self._reply(status, data)
        finally:
            INFLIGHT.release()

    def do_POST(self):
        self._error(405, "MUTATION_FORBIDDEN")

    do_PUT = do_POST
    do_DELETE = do_POST
    do_PATCH = do_POST


def self_test() -> dict:
    assert _allowed_target("/health") == WINDOWS_CANONICAL + "/health"
    assert _allowed_target("/api/missions/M/cognitive-readiness?conversation_id=conv-1&binding_epoch=1")
    for unsafe in ("/api/conversations", "/api/state", "/api/operator/commands",
                   "/api/missions/../cognitive-readiness?conversation_id=x&binding_epoch=1",
                   "/api/missions/M/cognitive-readiness?conversation_id=x&binding_epoch=0",
                   "/api/missions/M/cognitive-readiness?conversation_id=x&binding_epoch=1&extra=y"):
        assert _allowed_target(unsafe) is None, unsafe
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:" + str(server.server_port)
    try:
        with urlopen(base + "/health", timeout=12) as response:
            payload = json.load(response)
            assert response.status == 200
            assert payload == {"status": "ok", "authority_effect": "NONE"}
        try:
            urlopen(base + "/api/operator/commands", timeout=4)
            raise AssertionError("operator route escaped")
        except HTTPError as error:
            assert error.code == 404
        try:
            urlopen(base + "/api/missions/M/cognitive-readiness?conversation_id=x&binding_epoch=0", timeout=4)
            raise AssertionError("invalid epoch escaped")
        except HTTPError as error:
            assert error.code == 404
        from urllib.request import Request
        try:
            urlopen(Request(base + "/health", data=b"{}", method="POST"), timeout=4)
            raise AssertionError("mutation method escaped")
        except HTTPError as error:
            assert error.code == 405
        original = globals()["_windows_get"]
        try:
            globals()["_windows_get"] = lambda target: (_ for _ in ()).throw(RuntimeError("simulated transport loss"))
            try:
                urlopen(base + "/health", timeout=4)
                raise AssertionError("unavailable upstream promoted to health")
            except HTTPError as error:
                assert error.code == 502
        finally:
            globals()["_windows_get"] = original
        from types import SimpleNamespace
        from unittest.mock import patch
        wrong_scope = {
            "authority_effect": "NONE",
            "mission_id": "FOREIGN",
            "conversation_id": "conv-1",
            "binding_epoch": 1,
            "readiness": {
                "mission_id": "FOREIGN", "conversation_id": "conv-1",
                "binding_epoch": 1, "authority_effect": "NONE",
                "projection_digest": "a" * 64,
            },
        }
        bad_response = (
            b"LION_STATUS=200\nLION_BODY="
            + base64.b64encode(json.dumps(wrong_scope).encode("utf-8"))
            + b"\n"
        )
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=bad_response)):
            try:
                _windows_get(WINDOWS_CANONICAL + "/api/missions/M/cognitive-readiness?conversation_id=conv-1&binding_epoch=1")
                raise AssertionError("foreign mission identity was accepted")
            except ValueError:
                pass
        return {
            "mutation_method_denied": "PASS",
            "upstream_failure_failclosed": "PASS",
            "foreign_identity_denied": "PASS",
            "source_candidate": True,
            "ephemeral_only": True,
            "windows_canonical_health": "PASS",
            "strict_path_and_query": "PASS",
            "operator_route_denied": "PASS",
            "invalid_epoch_denied": "PASS",
            "scope": "READ_ONLY_TRANSPORT_CANARY_NO_LIVE_READINESS",
            "authority_effect": "NONE",
            "deployment": "NOT_PERFORMED",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def main():
    parser = argparse.ArgumentParser()
    opts = parser.add_mutually_exclusive_group(required=True)
    opts.add_argument("--self-test", action="store_true")
    opts.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8780)
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), sort_keys=True))
        return
    if args.port not in (8780, 8783):
        parser.error("read-only WSL bridge listener accepts only 8780 or 8783")
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
