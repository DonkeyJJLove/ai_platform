from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC = Path(__file__).resolve().parent / 'static'


def _frame(payload: bytes) -> bytes:
    n = len(payload)
    if n < 126:
        return bytes([0x81, n]) + payload
    if n < 65536:
        return bytes([0x81, 126]) + n.to_bytes(2, 'big') + payload
    return bytes([0x81, 127]) + n.to_bytes(8, 'big') + payload


def _safe_header_value(value: str) -> str:
    if '\r' in value or '\n' in value:
        raise ValueError('invalid HTTP header value')
    return value


def _safe_static_target(request_path: str) -> Path | None:
    rel = 'index.html' if request_path == '/' else request_path.lstrip('/')
    candidate = (STATIC / rel).resolve()
    static_root = STATIC.resolve()
    try:
        candidate.relative_to(static_root)
    except ValueError:
        return None
    return candidate


def make_handler(source):
    class H(BaseHTTPRequestHandler):
        server_version = 'LION-VKT-Mission-Control/1.0'

        def log_message(self, *_):
            pass

        def send_json(self, obj, code=200):
            body = json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split('?', 1)[0]
            if path == '/api/state':
                return self.send_json(source.state())
            if path == '/ws' and self.headers.get('Upgrade', '').lower() == 'websocket':
                key = self.headers.get('Sec-WebSocket-Key', '')
                if not key or '\r' in key or '\n' in key:
                    return self.send_json({'ok': False, 'error': 'invalid websocket key'}, 400)
                accept = base64.b64encode(
                    hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode(), usedforsecurity=False).digest()
                ).decode()
                self.send_response(101)
                self.send_header('Upgrade', 'websocket')
                self.send_header('Connection', 'Upgrade')
                self.send_header('Sec-WebSocket-Accept', _safe_header_value(accept))
                self.end_headers()
                try:
                    while True:
                        body = json.dumps(source.state(), sort_keys=True, separators=(',', ':')).encode()
                        self.wfile.write(_frame(body))
                        self.wfile.flush()
                        time.sleep(1)
                except Exception:
                    pass
                return
            target = _safe_static_target(path)
            if target is None:
                self.send_error(403)
                return
            if not target.is_file():
                self.send_error(404)
                return
            body = target.read_bytes()
            content_type = _safe_header_value(mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

    return H


def serve(source, host='127.0.0.1', port=8765):
    httpd = ThreadingHTTPServer((host, port), make_handler(source))
    thread = threading.Thread(target=source.loop, daemon=True)
    thread.start()
    try:
        httpd.serve_forever()
    finally:
        source.stop_event.set()
        httpd.server_close()
