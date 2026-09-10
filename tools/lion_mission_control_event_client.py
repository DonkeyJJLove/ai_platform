#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time

from cyber_lion.mission_control.schema import EVENT_SCHEMA, EVENT_TYPES, validate_event

SOCKET = '/run/lion-mission-control/events.sock'


def rid() -> str:
    return hashlib.sha256(os.urandom(32)).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--socket', default=SOCKET)
    sub = p.add_subparsers(dest='command', required=True)
    e = sub.add_parser('emit')
    e.add_argument('--run-id', required=True)
    e.add_argument('--event-type', choices=sorted(EVENT_TYPES), required=True)
    e.add_argument('--process-class', default='UNKNOWN')
    e.add_argument('--adapter-type', default='LPCL_EVENT_STREAM')
    e.add_argument('--phase')
    e.add_argument('--status')
    e.add_argument('--host', default='LION-AUTH-LAB')
    e.add_argument('--runtime', default='K3S')
    e.add_argument('--target-json', default='{}')
    e.add_argument('--source-json', default='{}')
    e.add_argument('--authority-json', default='{}')
    e.add_argument('--payload-json', default='{}')
    a = p.parse_args()
    event = {
        'schema_version': EVENT_SCHEMA,
        'event_id': rid(),
        'run_id': a.run_id,
        'timestamp': time.time(),
        'event_type': a.event_type,
        'process_language': 'LPCL-1_0',
        'process_class': a.process_class,
        'adapter_type': a.adapter_type,
        'host': a.host,
        'runtime': a.runtime,
        'phase': a.phase,
        'status': a.status,
        'source': json.loads(a.source_json),
        'target': json.loads(a.target_json),
        'authority': json.loads(a.authority_json),
        'payload': json.loads(a.payload_json),
        'artifact_refs': [],
        'receipt_refs': [],
    }
    event = validate_event(event)
    raw = json.dumps(event, sort_keys=True, separators=(',', ':')).encode() + b'\n'
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(a.socket)
    s.sendall(raw)
    s.shutdown(socket.SHUT_WR)
    data = b''
    while True:
        part = s.recv(65536)
        if not part:
            break
        data += part
    s.close()
    value = json.loads(data.decode())
    print(json.dumps(value, sort_keys=True, separators=(',', ':')))
    return 0 if value.get('ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
