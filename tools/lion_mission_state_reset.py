"""Offline operator cleanup after stopping Mission Control and pausing dispatch.

Not an HTTP endpoint or model tool. The caller must stop the identified service;
the persistent pause/reset markers prevent dispatch and bootstrap resurrection.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def discover(connection):
    tables={}
    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        name=row[0]
        columns=[r[1] for r in connection.execute('PRAGMA table_info('+quoted(name)+')')]
        fields=[c for c in columns if c in {'mission_id','root_mission_id','parent_mission_id'}]
        if fields:
            tables[name]=' OR '.join(quoted(c)+' IS NOT NULL' for c in fields)
    # Follow declared references, including descendants with no mission column.
    changed=True
    while changed:
        changed=False
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            name=row[0]
            if name in tables:continue
            clauses=[]
            for fk in connection.execute('PRAGMA foreign_key_list('+quoted(name)+')'):
                if fk[2] in tables:
                    if fk[1] or sum(r[0]==fk[0] for r in connection.execute('PRAGMA foreign_key_list('+quoted(name)+')'))>1:
                        raise ValueError('composite foreign key requires explicit review: '+name)
                    if not fk[4]:raise ValueError('implicit foreign key requires explicit review: '+name)
                    clauses.append(quoted(fk[3])+' IN (SELECT '+quoted(fk[4])+' FROM '+quoted(fk[2])+' WHERE '+tables[fk[2]]+')')
            if clauses:tables[name]=' OR '.join(clauses);changed=True
    # Historical schemas used logical references without declared foreign keys.
    names={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for child,parent,key in [('saas_broker_receipts','saas_handoff_requests','request_id'),('mission_dual_receipts','mission_dual_evaluations','request_id')]:
        if child in names and parent in tables and child not in tables:
            tables[child]=quoted(key)+' IN (SELECT '+quoted(key)+' FROM '+quoted(parent)+' WHERE '+tables[parent]+')'
    return tables


def reset_offline(database, archive_directory, stamp):
    database=Path(database).resolve(strict=True)
    directory=Path(archive_directory).resolve()
    directory.mkdir(parents=True,exist_ok=True)
    backup=directory/'mission-control-before-reset.sqlite3'
    archive=directory/'EPOCH3_MISSION_ARCHIVE.json'
    if backup.exists() or archive.exists():raise ValueError('archive destination already exists')
    connection=sqlite3.connect(database)
    connection.row_factory=sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        if connection.execute('PRAGMA integrity_check').fetchall()[0][0]!='ok':raise ValueError('database integrity failure')
        if not connection.execute("SELECT 1 FROM mission_meta WHERE key='mission_dispatch_paused' AND value='1'").fetchone():raise ValueError('dispatch must be paused first')
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('PRAGMA defer_foreign_keys=ON')
        plan=discover(connection)
        # Backup through an independent read connection while the write lock
        # prevents any concurrent mutation. The main connection has no writes yet.
        with closing(sqlite3.connect('file:'+database.as_posix()+'?mode=ro',uri=True)) as source:
            with closing(sqlite3.connect(backup)) as destination:source.backup(destination)
        backup.chmod(0o600)
        rows={};rowids={}
        for table,predicate in plan.items():
            rowids[table]=[r[0] for r in connection.execute('SELECT rowid FROM '+quoted(table)+' WHERE '+predicate)]
            rows[table]=[dict(r) for r in connection.execute('SELECT * FROM '+quoted(table)+' WHERE '+predicate)]
        for records in rows.values():
            for record in records:
                if 'response_token' in record:
                    record['response_token_sha256']=hashlib.sha256(record.pop('response_token').encode()).hexdigest()
        scheduler=[dict(r) for r in connection.execute('SELECT * FROM mission_scheduler_state')]
        document={'schema':'lion.mission-archive/v1','created_at':stamp,'database':str(database),'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'dependency_plan':plan,'mission_state':rows,'scheduler_state':scheduler}
        with archive.open('x',encoding='utf-8') as stream:
            json.dump(document,stream,ensure_ascii=False,sort_keys=True,indent=2)
            stream.flush()
            import os
            os.fsync(stream.fileno())
        # Materialized row identities keep logical dependencies valid regardless
        # of deletion order; FK constraints are checked before the commit.
        for table,ids in rowids.items():
            connection.executemany('DELETE FROM '+quoted(table)+' WHERE rowid=?',[(i,) for i in ids])
        connection.execute("DELETE FROM mission_meta WHERE key='focus_mission_id'")
        connection.execute("INSERT OR REPLACE INTO mission_meta VALUES('runtime_mission_reset','1',?)",(stamp,))
        connection.execute("UPDATE mission_scheduler_state SET state='PAUSED',queue_depth=0,active_run_count=0,last_error=NULL")
        if connection.execute('SELECT count(*) FROM missions').fetchone()[0]:raise ValueError('missions remain')
        violations=connection.execute('PRAGMA foreign_key_check').fetchall()
        if violations:raise ValueError('foreign key check failed')
        if connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('post-reset integrity failure')
        connection.commit()
        connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        return {'missions_before':len(rows.get('missions',[])),'missions_after':0,'deleted_rows':{t:len(ids) for t,ids in rowids.items()},'archive_path':str(archive),'backup_path':str(backup),'foreign_key_check':[],'integrity_check':'ok','focus_after':None,'scheduler_queue_after':0}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
