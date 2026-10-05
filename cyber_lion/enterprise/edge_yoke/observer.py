"""Foreground observer; signed telemetry and veto. Not an autonomy scheduler."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import time
import uuid
import psutil
from cyber_lion.mission_control.edge_support import (
    EdgeRejected, canonical, digest, object_bytes, read_regular, private_directory,
    write_new, replace_owned, identifier, exclusive_local_file,
)
from .policy import YokePolicy, VetoMachine
from .evidence import EvidenceJournal, new_key, read_key, public_hex, sign, verify
REPO = Path(__file__).resolve().parents[3]

def source_pins():
    paths = list(Path(__file__).parent.glob('*.py'))
    paths += list((REPO/'cyber_lion/mission_control').glob('edge_*.py'))
    paths += [REPO/'cyber_lion/mission_control/artifact_transfer.py']
    return {p.relative_to(REPO).as_posix(): digest(read_regular(p)) for p in sorted(paths)}

def initialize(home, host_id, policy=None):
    home = private_directory(home)
    identifier(host_id)
    if any(home.iterdir()):
        raise EdgeRejected('new empty observer directory required')
    policy = (policy or YokePolicy()).validate()
    key = new_key(home/'observer.private.pem', home/'observer.public.hex')
    cfg = dict(schema='lion.edge.observer-config/v2', host_id=host_id, policy=asdict(policy),
               source_root=str(REPO), source_pins=source_pins())
    raw = canonical(cfg)
    write_new(home/'config.json', raw)
    write_new(home/'config.sha256', digest(raw).encode())
    private_directory(home/'events')
    return dict(home=str(home), host_id=host_id, public_key=public_hex(key), policy_sha256=policy.digest())

def load_config(home):
    raw = read_regular(Path(home)/'config.json')
    if digest(raw) != read_regular(Path(home)/'config.sha256', 128).decode():
        raise EdgeRejected('observer config pin mismatch')
    cfg = object_bytes(raw)
    if cfg.get('schema') != 'lion.edge.observer-config/v2':
        raise EdgeRejected('observer schema')
    return cfg

def pin_state(cfg):
    try:
        root = Path(cfg['source_root'])
        if not cfg['source_pins']:
            return 'UNKNOWN'
        for name, value in cfg['source_pins'].items():
            p = Path(name)
            if p.is_absolute() or '..' in p.parts:
                return 'MISMATCH'
            if digest(read_regular(root/p)) != value:
                return 'MISMATCH'
        return 'MATCH'
    except (OSError, ValueError):
        return 'UNKNOWN'

def sample_host(cfg, home):
    cpu = psutil.cpu_percent(interval=0.2)
    return dict(observed_at=time.time(), cpu_percent=cpu, memory_percent=psutil.virtual_memory().percent,
                free_bytes=psutil.disk_usage(str(home)).free, integrity=pin_state(cfg),
                boot_time=psutil.boot_time(), scope='HOST_AGGREGATES_NOT_TASK_ATTRIBUTION',
                gpu_state='NOT_COLLECTED')

def watch(home, *, seconds=None, interval=1.0):
    home = Path(home).resolve()
    if not home.is_dir():
        raise EdgeRejected('observer home missing')
    cfg = load_config(home)
    policy = YokePolicy(**cfg['policy']).validate()
    key = read_key(home/'observer.private.pem')
    pub = public_hex(key)
    with exclusive_local_file(home/'observer.lock'):
        journal = EvidenceJournal(home/'evidence.sqlite')
        journal.audit(pub)
        machine = VetoMachine(policy)
        if (home/'snapshot.json').exists():
            old = verify(object_bytes(read_regular(home/'snapshot.json')), pub)
            machine.quarantined = old.get('state') == 'QUARANTINE'
        start = time.monotonic()
        session = uuid.uuid4().hex
        previous = None
        def frame(decision):
            now = time.time()
            row = journal.append(dict(type='TELEMETRY_AND_VETO', host_id=cfg['host_id'],
                                     observer_session=session, observed_at=now, decision=decision), key)
            v = dict(decision, schema='lion.edge.veto/v2', host_id=cfg['host_id'], observer_session=session,
                     observed_at=now, expires_at=now+policy.snapshot_ttl, seq=row['seq'],
                     evidence_head=row['digest'], policy_sha256=policy.digest())
            replace_owned(home/'snapshot.json', canonical(sign(v, key)))
            return v
        try:
            while seconds is None or time.monotonic()-start < seconds:
                if sum(p.stat().st_size for p in home.glob('evidence.sqlite*')) > 67108864:
                    raise EdgeRejected('journal limit: witness/archive before a new segment')
                try:
                    sample = sample_host(cfg, home)
                except (OSError, psutil.Error):
                    sample = dict(integrity='UNKNOWN')
                decision = machine.update(sample, time.time())
                v = frame(dict(decision, sample=sample))
                if decision['state'] != previous or decision['notices']:
                    event = dict(schema='lion.edge.correction-request/v2', request_id=uuid.uuid4().hex,
                                 host_id=cfg['host_id'], observed_at=v['observed_at'], evidence_head=v['evidence_head'],
                                 reasons=decision['reasons'], notices=decision['notices'], authority_effect='NONE',
                                 type='REVIEW_REQUIRED' if decision['state'] != 'NO_VETO' or decision['notices'] else 'RESOURCE_RECOVERED',
                                 delivery_state='LOCAL_OUTBOX_NOT_SENT')
                    write_new(home/'events'/f"{v['seq']:012d}.json", canonical(sign(event, key)))
                    previous = decision['state']
                time.sleep(max(0.05, interval))
        finally:
            # Signed stop cannot clear a quarantine. SIGKILL still leads to TTL expiry.
            frame(machine.result('QUARANTINE' if machine.quarantined else 'HOLD',
                                 ['PINNED_SOURCE_MISMATCH', 'OBSERVER_STOPPED'] if machine.quarantined else ['OBSERVER_STOPPED']))
        return dict(status='STOPPED', head=journal.audit(pub))
