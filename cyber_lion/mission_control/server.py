from __future__ import annotations

import base64
import errno
import hashlib
import json
import os
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from .models import fleet_summary_from_runs, summary_from_runs

STATIC = Path(__file__).resolve().parent / 'static'


class MissionControl:
    def __init__(self, store, registry, reconciler, interval: float = 1.0):
        self.store = store
        self.registry = registry
        self.reconciler = reconciler
        self.interval = interval
        self.stop_event = threading.Event()
        self.error: str | None = None
        self.lock = threading.RLock()
        self.fleet_observations = []
        self.last_poll_at: float | None = None

    def poll_once(self):
        observed = self.reconciler.poll_once()
        with self.lock:
            self.error = None if not self.reconciler.errors else json.dumps(self.reconciler.errors, sort_keys=True)
            self.fleet_observations = [run for run in observed if run.get('adapter_type') not in self.reconciler.errors]
            self.last_poll_at = time.monotonic()
        return observed

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.poll_once()
            except Exception as exc:
                with self.lock:
                    self.error = type(exc).__name__ + ':' + str(exc)[:1000]
            self.stop_event.wait(self.interval)

    def summary(self):
        runs = self.store.list_runs()
        with self.lock:
            fresh = self.last_poll_at is not None and time.monotonic() - self.last_poll_at <= max(5.0, self.interval * 3)
            current_status = {run['run_id']: run['status'] for run in runs}
            fleet_runs = [dict(run, status=current_status.get(run['run_id'], run['status'])) for run in self.fleet_observations] if fresh and self.error is None else []
            fleet = fleet_summary_from_runs(fleet_runs)
            # Only this successful poll supplies current pod identities. Persisted
            # run metrics intentionally remain historical after cleanup/errors.
            fleet['pod_observations'] = [
                {'run_id': run['run_id'], 'pods': (run.get('metrics') or {}).get('drone_pods', [])}
                for run in fleet_runs if fleet['currentness'] == 'OBSERVED'
                and run['run_id'] in fleet['run_ids']
            ]
        return {
            'ok': self.error is None,
            'error': self.error,
            'summary': summary_from_runs(runs),
            'fleet': fleet,
            'adapter_errors': dict(self.reconciler.errors),
        }


def _frame(payload: bytes) -> bytes:
    n = len(payload)
    if n < 126:
        return bytes([0x81, n]) + payload
    if n < 65536:
        return bytes([0x81, 126]) + struct.pack('!H', n) + payload
    return bytes([0x81, 127]) + struct.pack('!Q', n) + payload


def _safe_header_value(value: str) -> str:
    if '\r' in value or '\n' in value:
        raise ValueError('invalid HTTP header value')
    return value


def _safe_static_target(request_path: str) -> Path | None:
    if request_path in ('/', '/index.html'):
        return STATIC / 'index.html'
    if request_path == '/app.css':
        return STATIC / 'app.css'
    if request_path == '/app.js':
        return STATIC / 'app.js'
    return None


def _static_content_type(target: Path) -> str:
    if target.name == 'index.html':
        return 'text/html; charset=utf-8'
    if target.name == 'app.css':
        return 'text/css; charset=utf-8'
    if target.name == 'app.js':
        return 'text/javascript; charset=utf-8'
    raise ValueError('unknown static asset')


def make_handler(mc: MissionControl):
    class H(BaseHTTPRequestHandler):
        server_version = 'LION-Mission-Control/2.0'

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

        def _method_denied(self):
            self.send_json({'ok': False, 'error': 'READ_ONLY_MISSION_CONTROL'}, 405)

        do_POST = _method_denied
        do_PUT = _method_denied
        do_PATCH = _method_denied
        do_DELETE = _method_denied

        def do_GET(self):
            path = self.path.split('?', 1)[0]
            if path == '/health':
                return self.send_json({'ok': mc.error is None, 'error': mc.error})
            if path == '/api/summary':
                return self.send_json(mc.summary())
            if path == '/api/adapters':
                return self.send_json({'ok': True, 'adapters': mc.registry.describe()})
            if path == '/api/runs':
                return self.send_json({'ok': True, 'runs': mc.store.list_runs()})
            if path == '/api/export':
                return self.send_json({'ok': True, 'export': mc.store.export()})
            if path.startswith('/api/export/'):
                run_id = unquote(path[len('/api/export/'):])
                value = mc.store.export_run(run_id)
                return self.send_json({'ok': value is not None, 'export': value}, 200 if value is not None else 404)
            if path.startswith('/api/runs/'):
                tail = unquote(path[len('/api/runs/'):])
                parts = tail.split('/')
                run_id = parts[0]
                if len(parts) == 1:
                    run = mc.store.get_run(run_id)
                    return self.send_json({'ok': run is not None, 'run': run}, 200 if run else 404)
                if len(parts) == 2:
                    kind = parts[1]
                    getters = {
                        'events': mc.store.events,
                        'metrics': mc.store.metrics,
                        'participants': mc.store.participants,
                        'artifacts': mc.store.artifacts,
                        'receipts': mc.store.receipts,
                    }
                    if kind in getters:
                        if mc.store.get_run(run_id) is None:
                            return self.send_json({'ok': False, 'error': 'run-not-found'}, 404)
                        return self.send_json({'ok': True, kind: getters[kind](run_id)})
                return self.send_json({'ok': False, 'error': 'not-found'}, 404)
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
                    while not mc.stop_event.is_set():
                        body = json.dumps({'summary': mc.summary(), 'runs': mc.store.list_runs()}, sort_keys=True, separators=(',', ':')).encode()
                        self.wfile.write(_frame(body))
                        self.wfile.flush()
                        time.sleep(1)
                except Exception:
                    pass
                return
            target = _safe_static_target(path)
            if target is None:
                self.send_error(404)
                return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', _static_content_type(target))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

    return H


def _write_listen(path: str | None, host: str, port: int) -> None:
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps({'host': host, 'port': port, 'pid': os.getpid(), 'status': 'LISTENING'}, sort_keys=True) + '\n')
    os.replace(tmp, p)
    os.chmod(p, 0o644)


def serve(mc: MissionControl, event_server, host='127.0.0.1', port=8765, fallback_ports=(), listen_state=None, legacy_listen_state=None):
    candidates: list[int] = []
    for candidate in (port, *fallback_ports):
        candidate = int(candidate)
        if candidate not in candidates:
            candidates.append(candidate)
    httpd = None
    selected = None
    for candidate in candidates:
        try:
            httpd = ThreadingHTTPServer((host, candidate), make_handler(mc))
            selected = candidate
            break
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
    if httpd is None or selected is None:
        raise OSError(errno.EADDRINUSE, 'no Mission Control port available')
    _write_listen(listen_state, host, selected)
    _write_listen(legacy_listen_state, host, selected)
    event_server.start()
    thread = threading.Thread(target=mc.loop, daemon=True)
    thread.start()
    try:
        httpd.serve_forever()
    finally:
        mc.stop_event.set()
        event_server.close()
        httpd.server_close()
        for path in (listen_state, legacy_listen_state):
            if path:
                try:
                    Path(path).unlink()
                except FileNotFoundError:
                    pass
