#!/usr/bin/env python3
"""One-time, explicit provisioning for OPERATOR_PRIMARY.

Creates a WAL-safe pre-migration backup, provisions a local gateway key if one
does not already exist, migrates the operator ledger and grants the primary
human operator the task-defined mission scope. The secret is never printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cyber_lion.mission_control import operator_control

TASK_ID="LION-OPERATOR-DRONE-SUPREMACY-AND-LIVE-MISSION-INTERVENTION-R1"
DEFAULT_PROXY_GRANT_HOURS=8


def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def atomic_secret(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as h:h.write(value+'\n');h.flush();os.fsync(h.fileno())
        os.chmod(name,0o600);os.replace(name,path)
    finally:
        try:
            if os.path.exists(name):os.unlink(name)
        except OSError:pass

def backup_database(db,state):
    state.mkdir(parents=True,exist_ok=True);stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=state/f'mission-control-v3.pre-operator.{stamp}.sqlite3'
    src=sqlite3.connect(db,timeout=10);dst=sqlite3.connect(target)
    try:src.backup(dst);dst.execute('PRAGMA wal_checkpoint(TRUNCATE)');dst.commit()
    finally:dst.close();src.close()
    os.chmod(target,0o400)
    return {'path':str(target),'sha256':sha256_file(target),'bytes':target.stat().st_size}

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',default='/var/lib/sentinelx/uploads/lion-mission-control-v3/mission-control-v3.db');p.add_argument('--key-file',default='/var/lib/sentinelx/uploads/lion-mission-control-v3/operator-gateway.key');p.add_argument('--proxy-key-file',default='/var/lib/sentinelx/uploads/lion-mission-control-v3/operator-sentinelx-proxy.key');p.add_argument('--panel-proxy-key-file',default='/var/lib/sentinelx/uploads/lion-mission-control-v3/operator-panel-proxy.key');p.add_argument('--pairing-key-file',default='/var/lib/sentinelx/uploads/lion-mission-control-v3/operator-pairing.key');p.add_argument('--state-dir',default='/var/lib/sentinelx/uploads/lion-operator-control');p.add_argument('--mission-scope',default='*');p.add_argument('--proxy-grant-hours',type=int,default=DEFAULT_PROXY_GRANT_HOURS);p.add_argument('--confirm',required=True);a=p.parse_args()
    if a.confirm!=TASK_ID:raise SystemExit('exact task activation confirmation required')
    if not 1<=a.proxy_grant_hours<=168:raise SystemExit('proxy grant hours must be 1..168')
    proxy_expires_at=(datetime.now(timezone.utc)+timedelta(hours=a.proxy_grant_hours)).isoformat().replace('+00:00','Z')
    db=Path(a.db).resolve();key=Path(a.key_file).resolve();proxy_key=Path(a.proxy_key_file).resolve();panel_proxy_key=Path(a.panel_proxy_key_file).resolve();pairing_key=Path(a.pairing_key_file).resolve();state=Path(a.state_dir).resolve()
    if not db.is_file():raise SystemExit('mission control database unavailable')
    backup=backup_database(db,state/'backups')
    key_created=False;proxy_key_created=False;panel_proxy_key_created=False;pairing_key_created=False
    if key.exists():
        current=key.read_text(encoding='utf-8').strip()
        if len(current)<64:raise SystemExit('existing operator key malformed')
        os.chmod(key,0o600)
    else:
        atomic_secret(key,secrets.token_hex(32));key_created=True
    if proxy_key.exists():
        current=proxy_key.read_text(encoding='utf-8').strip()
        if len(current)<64:raise SystemExit('existing SentinelX proxy key malformed')
        os.chmod(proxy_key,0o600)
    else:
        atomic_secret(proxy_key,secrets.token_hex(32));proxy_key_created=True
    if panel_proxy_key.exists():
        current=panel_proxy_key.read_text(encoding='utf-8').strip()
        if len(current)<64:raise SystemExit('existing panel proxy key malformed')
        os.chmod(panel_proxy_key,0o600)
    else:
        atomic_secret(panel_proxy_key,secrets.token_hex(32));panel_proxy_key_created=True
    if pairing_key.exists():
        current=pairing_key.read_text(encoding='utf-8').strip()
        if len(current)<64:raise SystemExit('existing operator pairing key malformed')
        os.chmod(pairing_key,0o600)
    else:
        atomic_secret(pairing_key,secrets.token_hex(32));pairing_key_created=True
    c=sqlite3.connect(db,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA foreign_keys=ON')
    try:
        before=c.execute('PRAGMA integrity_check').fetchone()[0]
        if before!='ok':raise SystemExit('database integrity preflight failed')
        operator_control.migrate(c,now);participant=operator_control.ensure_primary_operator(c,now,mission_scope=a.mission_scope);operator_control.revoke_active_grants(c,operator_control.SENTINELX_PROXY_PRINCIPAL,now,mission_scope=a.mission_scope);proxy=operator_control.ensure_operator_proxy(c,now,mission_scope=a.mission_scope,expires_at=proxy_expires_at);panel_proxy=operator_control.ensure_panel_proxy(c,now)
        after=c.execute('PRAGMA integrity_check').fetchone()[0]
        if after!='ok':raise SystemExit('database integrity after migration failed')
    finally:c.close()
    receipt={'schema':'lion.operator-provision-receipt/v1','task_id':TASK_ID,'db':str(db),'backup':backup,'key_file':str(key),'key_created':key_created,'key_sha256':hashlib.sha256(key.read_bytes()).hexdigest(),'proxy_key_file':str(proxy_key),'proxy_key_created':proxy_key_created,'proxy_key_sha256':hashlib.sha256(proxy_key.read_bytes()).hexdigest(),'panel_proxy_key_file':str(panel_proxy_key),'panel_proxy_key_created':panel_proxy_key_created,'panel_proxy_key_sha256':hashlib.sha256(panel_proxy_key.read_bytes()).hexdigest(),'pairing_key_file':str(pairing_key),'pairing_key_created':pairing_key_created,'pairing_key_sha256':hashlib.sha256(pairing_key.read_bytes()).hexdigest(),'principal_id':'OPERATOR_PRIMARY','participant_id':'operator:primary','proxy_principal_id':operator_control.SENTINELX_PROXY_PRINCIPAL,'proxy_participant_id':operator_control.SENTINELX_PROXY_PARTICIPANT,'proxy_actions':sorted(operator_control.DEFAULT_PROXY_ACTIONS),'proxy_grant_hours':a.proxy_grant_hours,'proxy_grant_expires_at':proxy_expires_at,'panel_proxy_principal_id':operator_control.PANEL_PROXY_PRINCIPAL,'panel_proxy_participant_id':operator_control.PANEL_PROXY_PARTICIPANT,'mission_scope':a.mission_scope,'integrity':'ok','provisioned_at':now(),'secret_exposed':False}
    receipt['receipt_digest']=hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    out=state/'provision-receipt.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(receipt,sort_keys=True,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.chmod(out,0o600)
    print(json.dumps(receipt,sort_keys=True,ensure_ascii=False))
if __name__=='__main__':main()