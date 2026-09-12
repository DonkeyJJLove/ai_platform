from __future__ import annotations

import base64
import errno
import hashlib
import json
import os
import struct
import threading
import time
from copy import deepcopy
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
        self.poll_lock = threading.Lock()
        self.poll_attempt_at = None
        self.poll_completed_at = None
        self.poll_success_at = None
        self.poll_success_monotonic = None
        self.poll_in_progress = False
        self.adapter_diagnostics = {}
        self.adapter_errors = {}

    def poll_once(self):
        # Serialize poll writers; readers see one completed snapshot, not half a poll.
        with self.poll_lock:
            with self.lock:
                self.poll_attempt_at = time.time()
                self.poll_in_progress = True
            try:
                observed = self.reconciler.poll_once()
                errors = dict(self.reconciler.errors)
                diagnostics = deepcopy(getattr(self.reconciler, 'poll_diagnostics', {}))
            except Exception:
                with self.lock:
                    self.error = 'POLL_ERROR'
                    self.fleet_observations = []
                    self.adapter_errors = {}
                    self.adapter_diagnostics = {}
                    self.poll_completed_at = time.time()
                    self.last_poll_at = time.monotonic()
                    self.poll_in_progress = False
                raise
            with self.lock:
                self.error = 'POLL_ERROR' if errors else None
                self.adapter_errors = {key: 'POLL_ERROR' for key in errors}
                self.adapter_diagnostics = diagnostics
                self.fleet_observations = deepcopy([run for run in observed if run.get('adapter_type') not in errors])
                self.last_poll_at = time.monotonic()
                self.poll_completed_at = time.time()
                self.poll_in_progress = False
                if not errors:
                    self.poll_success_at = self.poll_completed_at
                    self.poll_success_monotonic = self.last_poll_at
            return observed

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.poll_once()
            except Exception:
                # poll_once already published the failure. Do not overwrite a
                # newer successful poll that another caller may have completed.
                pass
            self.stop_event.wait(self.interval)

    def summary(self):
        runs = self.store.list_runs()
        with self.lock:
            now = time.monotonic()
            threshold = max(5.0, self.interval * 3)
            age = None if self.last_poll_at is None else max(0.0, now - self.last_poll_at)
            fresh = age is not None and age <= threshold
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
            reason = ('NEVER_POLLED' if age is None else 'POLL_STALE' if not fresh
                      else 'POLL_ERROR' if self.error else 'EMPTY_OBSERVATION' if not self.fleet_observations
                      else 'OBSERVED' if fleet['currentness'] == 'OBSERVED'
                      else 'NO_FLEET_OBSERVATION' if not any(
                          any(k in (r.get('metrics') or {}) for k in ('fleet_organizations', 'active_by_organization'))
                          and r.get('status') not in {'CLEANING', 'CLEANED'} for r in fleet_runs)
                      else 'INVALID_OBSERVATION')
            by_id = {r['run_id']: r for r in fleet_runs}
            observations = {}
            for run in runs:
                current = by_id.get(run['run_id'])
                metrics = (current or {}).get('metrics') or {}
                per_run_reason = reason
                if fresh and self.error is None:
                    if current is None:
                        per_run_reason = 'NOT_IN_CURRENT_OBSERVATION'
                    elif current.get('status') in {'CLEANING', 'CLEANED'}:
                        per_run_reason = 'TERMINAL_HISTORY'
                    elif any(key in metrics for key in ('fleet_organizations', 'active_by_organization')):
                        per_run_reason = ('OBSERVED' if fleet_summary_from_runs([current])['currentness'] == 'OBSERVED'
                                          else 'INVALID_OBSERVATION')
                    else:
                        per_run_reason = 'OBSERVED'
                count = metrics.get('fresh_drones')
                heartbeat = ('UNKNOWN' if per_run_reason != 'OBSERVED' or current is None
                             or isinstance(count, bool) or not isinstance(count, int) or count < 0
                             else 'NONE_FRESH' if count == 0 else 'FRESH_REPORTED')
                diagnostic = self.adapter_diagnostics.get(run.get('adapter_type'), {})
                source_reason = per_run_reason
                if per_run_reason == 'NOT_IN_CURRENT_OBSERVATION':
                    source_reason = diagnostic.get('empty_reason') or diagnostic.get('reason') or per_run_reason
                observations[run['run_id']] = {'recorded_status': run['status'],
                    'observation_status': per_run_reason,
                    'source_reason': source_reason,
                    'heartbeat_status': heartbeat}
            # A selected run needs its own topology. Aggregated fleet counts may
            # span several runs and must never be assigned to one run's panel.
            run_fleets = {run['run_id']: fleet_summary_from_runs([run]) for run in fleet_runs}
            for run in fleet_runs:
                run_fleets[run['run_id']]['pod_observations'] = [
                    {'run_id': run['run_id'], 'pods': (run.get('metrics') or {}).get('drone_pods') or []}
                ]
            summary = summary_from_runs(runs)
            summary['recorded_active_runs'] = summary['active_runs']
            summary['observed_active_runs'] = (sum(r['status'] in {'STARTING', 'RUNNING', 'CLEANING'}
                and observations.get(r['run_id'], {}).get('observation_status') == 'OBSERVED'
                for r in fleet_runs) if fresh and self.error is None and not any(
                    value['observation_status'] == 'INVALID_OBSERVATION' for value in observations.values()) else None)
            return {'ok': self.error is None, 'error': self.error, 'summary': summary,
                'fleet': fleet, 'run_fleets': run_fleets,
                'adapter_errors': dict(self.adapter_errors), 'run_observations': observations,
                'observation': {'reason': reason, 'attempt_at': self.poll_attempt_at,
                    'completed_at': self.poll_completed_at, 'success_at': self.poll_success_at,
                    'age_seconds': age, 'success_age_seconds': None if self.poll_success_monotonic is None
                    else max(0.0, now - self.poll_success_monotonic), 'threshold_seconds': threshold,
                    'in_progress': self.poll_in_progress, 'adapters': deepcopy(self.adapter_diagnostics)}}


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
    if request_path == '/passive.js':
        return STATIC / 'passive.js'
    return None


def _static_content_type(target: Path) -> str:
    if target.name == 'index.html':
        return 'text/html; charset=utf-8'
    if target.name == 'app.css':
        return 'text/css; charset=utf-8'
    if target.name in ('app.js', 'passive.js'):
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
    thread = None
    try:
        _write_listen(listen_state, host, selected)
        _write_listen(legacy_listen_state, host, selected)
        event_server.start()
        thread = threading.Thread(target=mc.loop, daemon=True)
        thread.start()
        httpd.serve_forever()
    finally:
        mc.stop_event.set()
        event_server.close()
        httpd.server_close()
        if thread is not None and thread.ident is not None:
            thread.join()
        for path in (listen_state, legacy_listen_state):
            if path:
                try:
                    Path(path).unlink()
                except FileNotFoundError:
                    pass
