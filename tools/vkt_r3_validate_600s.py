#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path
from cyber_lion.vkt_r3.mission_control.models import normalize
from cyber_lion.vkt_r3.mission_control.source import EvidenceSource

PHASES=['TIGER_RELATION_ANALYSIS','SPECTRA_FALSIFIER','LION_LOCAL_EXECUTION','LION_RECEIPT','SPECTRA_PROOF_UPDATE','TIGER_ADJACENCY']
EXPECTED_FRESH={'TIGER':128,'SPECTRA':128,'LION':128}

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def digest(x): return hashlib.sha256(canonical(x)).hexdigest()

def check_snapshot(s:dict,baseline_uid:str|None=None,require_semantic:bool=True)->list[str]:
    e=[]
    if s.get('materialized')!=384:e.append('MATERIALIZED_NOT_384')
    if s.get('ready')!=384:e.append('READY_NOT_384')
    if s.get('unique_uid_count')!=384:e.append('UID_COUNT_NOT_384')
    if s.get('restarts')!=0:e.append('RESTARTS_NONZERO')
    if s.get('vendor_requests')!=0:e.append('VENDOR_REQUESTS_NONZERO')
    if baseline_uid is not None and s.get('uid_set')!=baseline_uid:e.append('UID_SET_DRIFT')
    if require_semantic:
        if s.get('fresh_drones')!=384:e.append('FRESH_DRONES_NOT_384')
        if s.get('fresh_by_fleet')!=EXPECTED_FRESH:e.append('FRESH_FLEET_CARDINALITY')
        if s.get('cases_total')!=36 or s.get('cases_seen')!=36:e.append('CASES_NOT_36')
        if s.get('cases_proven')!=36:e.append('CASES_NOT_PROVEN')
        if s.get('duplicates')!=0:e.append('DUPLICATES_NONZERO')
        if s.get('orphans')!=0:e.append('ORPHANS_NONZERO')
        if float(s.get('ack_rate') or 0)<0.95:e.append('ACK_RATE_LOW')
        parts=s.get('participants') or {}
        for p in PHASES:
            if int(parts.get(p) or 0)!=128:e.append('PARTICIPANTS_'+p)
        mission=s.get('mission') or {}
        if mission.get('completed') is not True:e.append('SEMANTIC_MISSION_NOT_COMPLETE')
    return e

def run_validation(source,duration=600.0,interval=5.0,now=time.monotonic,sleep=time.sleep):
    started=now(); samples=[]; first=normalize(source.read()); baseline=first.get('uid_set'); errs=check_snapshot(first,baseline)
    samples.append({'elapsed':0.0,'state':first,'errors':errs})
    if errs:return {'status':'DEFERRED','reason':'PREFLIGHT','elapsed':0.0,'baseline_uid_set':baseline,'samples':samples}
    while True:
        elapsed=now()-started
        if elapsed>=duration:break
        sleep(min(interval,max(0.0,duration-elapsed)))
        s=normalize(source.read()); errs=check_snapshot(s,baseline); samples.append({'elapsed':now()-started,'state':s,'errors':errs})
        if errs:return {'status':'FAIL','reason':'RUNTIME_INVARIANT','elapsed':now()-started,'baseline_uid_set':baseline,'samples':samples}
    final=normalize(source.read()); elapsed=now()-started; errs=check_snapshot(final,baseline)
    if not (duration-5.0<=elapsed<=duration+30.0):errs.append('ELAPSED_OUT_OF_RANGE')
    status='PASS' if not errs else 'FAIL'
    return {'status':status,'elapsed':elapsed,'baseline_uid_set':baseline,'final_uid_set':final.get('uid_set'),'errors':errs,'samples':samples+[{'elapsed':elapsed,'state':final,'errors':errs}]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-head',required=True);p.add_argument('--source-tree',required=True);p.add_argument('--duration',type=float,default=600.0);p.add_argument('--interval',type=float,default=5.0);p.add_argument('--out',default='/var/lib/sentinelx/uploads/vkt-r3-mission-control/validation-600s.json');a=p.parse_args()
    result=run_validation(EvidenceSource(a.source_head,a.source_tree),a.duration,a.interval); path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(result)+b'\n'); receipt={'result_path':str(path),'result_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':result['status'],'elapsed':result.get('elapsed'),'vendor_requests':0};print(json.dumps(receipt,sort_keys=True));return 0 if result['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
