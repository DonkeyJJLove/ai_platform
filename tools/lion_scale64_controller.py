#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = 'https://github.com/DonkeyJJLove/ai_platform.git'
BRANCH='experiment/local-swarm-p0-docker-polygon'
CANONICAL = Path('/opt/lion/scale64-control/canonical/lion-effect-admission-broker.py')
PUBLIC = Path('/opt/lion/scale64-control-state')
STATE = Path('/var/lib/lion-scale64-control')
MAIN = '/usr/local/bin/lion-effect-admission'
UPDATER = '/usr/local/bin/lion-broker-update'
ERROR_TAIL = 4096


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def write(name: str, obj: dict[str, Any]) -> None:
    raw = (json.dumps(obj, sort_keys=True, separators=(',', ':')) + '\n').encode()
    for root in (PUBLIC, STATE):
        root.mkdir(parents=True, exist_ok=True)
        tmp = root / (name + '.tmp')
        tmp.write_bytes(raw)
        os.replace(tmp, root / name)


def run(argv: list[str], timeout: int = 900) -> str:
    p = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if p.returncode:
        stdout_tail = p.stdout[-ERROR_TAIL:]
        stderr_tail = p.stderr[-ERROR_TAIL:]
        raise RuntimeError(
            f'command failed rc={p.returncode}; '
            f'stdout_tail={stdout_tail!r}; stderr_tail={stderr_tail!r}'
        )
    return p.stdout.strip()


def jcmd(argv: list[str], timeout: int = 900) -> dict[str, Any]:
    value = json.loads(run(argv, timeout))
    if not isinstance(value, dict) or value.get('ok') is not True:
        raise RuntimeError(f'operation denied: {value}')
    return value


def source() -> tuple[str, str]:
    out = run(['/usr/bin/git', 'ls-remote', '--exit-code', REPO, f'refs/heads/{BRANCH}'], 60)
    parts = out.split()
    head = parts[0] if parts else ''
    if len(parts) != 2 or len(head) != 40:
        raise RuntimeError('live head invalid')
    td = Path(tempfile.mkdtemp(prefix='lion-scale64-source-'))
    try:
        run(['/usr/bin/git', 'init', str(td)], 30)
        run(['/usr/bin/git', '-C', str(td), 'remote', 'add', 'origin', REPO], 30)
        run(['/usr/bin/git', '-C', str(td), 'fetch', '--no-tags', '--depth=1', 'origin', f'refs/heads/{BRANCH}'], 180)
        if run(['/usr/bin/git', '-C', str(td), 'rev-parse', 'FETCH_HEAD'], 30) != head:
            raise RuntimeError('head moved')
        tree = run(['/usr/bin/git', '-C', str(td), 'rev-parse', 'FETCH_HEAD^{tree}'], 30)
        return head, tree
    finally:
        shutil.rmtree(td, ignore_errors=True)


def prepared_current(ping: dict[str, Any], head: str, tree: str) -> bool:
    result = ping.get('result')
    if not isinstance(result, dict):
        return False
    prepared = result.get('prepared_scale64')
    return (
        isinstance(prepared, dict)
        and prepared.get('source_head') == head
        and prepared.get('source_tree') == tree
        and prepared.get('trust_class') == 'TEST_ONLY'
    )


def readiness(ping: dict[str, Any], pre: dict[str, Any], head: str, tree: str) -> dict[str, Any]:
    result = pre.get('result')
    if not isinstance(result, dict):
        raise RuntimeError('precheck result malformed')
    provider_current = result.get('provider_current') is True
    container_count = result.get('container_count')
    network_count = result.get('network_count')
    fleet_clean = provider_current and container_count == 0 and network_count == 0
    prepared = ping.get('result', {}).get('prepared_scale64') if isinstance(ping.get('result'), dict) else None
    prepared_ok = prepared_current(ping, head, tree)
    return {
        'source_head': head,
        'source_tree': tree,
        'provider_current': provider_current,
        'prepared_scale64': prepared,
        'prepared_scale64_current': prepared_ok,
        'container_count': container_count,
        'network_count': network_count,
        'fleet_clean': fleet_clean,
        'needs_prepare': (not provider_current) or (not prepared_ok),
        'observed_at': now(),
    }


def require_clean_if_observable(state: dict[str, Any]) -> None:
    if state['provider_current'] and not state['fleet_clean']:
        raise RuntimeError('pre-run inventory not clean')


def require_ready(state: dict[str, Any]) -> None:
    if state['provider_current'] is not True:
        raise RuntimeError('provider not current after prepare')
    if state['prepared_scale64_current'] is not True:
        raise RuntimeError('prepared Scale64 source not current after prepare')
    if state['fleet_clean'] is not True:
        raise RuntimeError('pre-run inventory not clean after prepare')


def main() -> int:
    write('status.json', {'state': 'RUNNING', 'started_at': now()})
    head, tree = source()
    write('source.json', {'head': head, 'tree': tree, 'branch': BRANCH})

    updater = jcmd([UPDATER, 'ping'])['result']
    current = updater['target_sha256']
    canonical_sha = hashlib.sha256(CANONICAL.read_bytes()).hexdigest()
    if current != canonical_sha:
        args = [
            '--expected-current-sha256', current,
            '--replacement-file', str(CANONICAL),
            '--source-head', head,
            '--source-tree', tree,
            '--reason', 'repository-native Scale64 convergence',
        ]
        write('broker-update.json', {
            'validate': jcmd([UPDATER, 'validate-update', *args]),
            'apply': jcmd([UPDATER, 'apply-update', *args]),
        })

    ping = jcmd([MAIN, 'ping'])
    write('broker-ping.json', ping)
    pre = jcmd([MAIN, 'precheck-scale64', '--source-head', head, '--source-tree', tree])
    write('precheck-before.json', pre)
    state = readiness(ping, pre, head, tree)
    write('readiness.json', state)
    require_clean_if_observable(state)

    if state['needs_prepare']:
        prepare = jcmd([MAIN, 'prepare-scale64', '--source-head', head, '--source-tree', tree], 600)
        write('prepare.json', prepare)
        ping = jcmd([MAIN, 'ping'])
        write('broker-ping-after-prepare.json', ping)
        pre = jcmd([MAIN, 'precheck-scale64', '--source-head', head, '--source-tree', tree])
        write('precheck-before.json', pre)
        state = readiness(ping, pre, head, tree)
        write('readiness-after-prepare.json', state)

    require_ready(state)

    run_value = jcmd([MAIN, 'run-scale64', '--source-head', head, '--source-tree', tree], 1200)
    write('run.json', run_value)
    summary = run_value['result']
    req = summary['run_request_id']
    write('evidence.json', jcmd([MAIN, 'evidence', '--run-request-id', req], 120))

    post = jcmd([MAIN, 'precheck-scale64', '--source-head', head, '--source-tree', tree])
    write('precheck-after.json', post)
    pr = post['result']
    ok = (
        summary.get('classification') == 'FULL_SUCCESS'
        and summary.get('evidence_relay_match') is True
        and summary.get('evidence_sha256') == summary.get('relay_evidence_sha256')
        and pr.get('container_count') == 0
        and pr.get('network_count') == 0
        and pr.get('clean_for_new_run') is True
    )
    recon = {
        'outcome': 'MATCHED' if ok else 'MISMATCHED',
        'source_head': head,
        'source_tree': tree,
        'run_request_id': req,
        'evidence_sha256': summary.get('evidence_sha256'),
        'relay_evidence_sha256': summary.get('relay_evidence_sha256'),
        'evidence_relay_match': summary.get('evidence_relay_match'),
        'finished_at': now(),
    }
    write('reconciliation.json', recon)
    write('status.json', {'state': 'SUCCEEDED' if ok else 'FAILED', 'finished_at': now(), 'reconciliation': recon})
    return 0 if ok else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        write('status.json', {'state': 'FAILED', 'finished_at': now(), 'error': type(exc).__name__ + ':' + str(exc)[:4000]})
        raise
