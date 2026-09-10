#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cyber_lion.mission_control.adapters import LpclEventStreamAdapter, OssRepositoryTestAdapter, VktR3Adapter
from cyber_lion.mission_control.events import EventSocketServer
from cyber_lion.mission_control.reconciliation import Reconciler
from cyber_lion.mission_control.registry import AdapterRegistry
from cyber_lion.mission_control.server import MissionControl, serve
from cyber_lion.mission_control.storage import Store


def source_identity(path: str) -> tuple[str, str]:
    value = json.loads(Path(path).read_text())
    head = value.get('source_head')
    tree = value.get('source_tree')
    if not isinstance(head, str) or len(head) != 40 or not isinstance(tree, str) or len(tree) != 40:
        raise SystemExit('invalid source identity')
    return head, tree


def build(args):
    head, tree = source_identity(args.source_identity)
    store = Store(args.db)
    registry = AdapterRegistry()
    registry.register(VktR3Adapter(head, tree, args.read_socket))
    registry.register(OssRepositoryTestAdapter(head, tree, args.read_socket))
    registry.register(LpclEventStreamAdapter())
    reconciler = Reconciler(store, registry)
    reconciler.import_known_history()
    mc = MissionControl(store, registry, reconciler, args.interval)
    event_server = EventSocketServer(store, args.event_socket)
    return mc, event_server


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-identity', default='/opt/lion/k3s-vkt-r3/source-identity.json')
    parser.add_argument('--read-socket', default='/run/lion-mission-control-read.sock')
    parser.add_argument('--db', default='/var/lib/sentinelx/uploads/lion-mission-control/mission-control.db')
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--event-socket', default='/run/lion-mission-control/events.sock')
    sub = parser.add_subparsers(dest='command', required=True)
    serve_p = sub.add_parser('serve')
    serve_p.add_argument('--host', default='127.0.0.1')
    serve_p.add_argument('--port', type=int, default=8765)
    serve_p.add_argument('--fallback-port', type=int, action='append', default=[])
    serve_p.add_argument('--listen-state', default='/run/lion-mission-control/listen.json')
    serve_p.add_argument('--legacy-listen-state', default='/run/lion-vkt-mission-control/listen.json')
    sub.add_parser('status')
    sub.add_parser('export')
    sub.add_parser('import-history')
    args = parser.parse_args()
    mc, event_server = build(args)
    if args.command == 'serve':
        serve(mc, event_server, args.host, args.port, args.fallback_port, args.listen_state, args.legacy_listen_state)
        return 0
    if args.command == 'status':
        mc.poll_once()
        print(json.dumps({'summary': mc.summary(), 'runs': mc.store.list_runs()}, sort_keys=True))
        return 0
    if args.command == 'export':
        print(json.dumps(mc.store.export(), sort_keys=True))
        return 0
    if args.command == 'import-history':
        print(json.dumps(mc.reconciler.import_known_history(), sort_keys=True))
        return 0
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
