from __future__ import annotations
RUN_STATUSES={'DISCOVERED','STARTING','RUNNING','PASS','FAIL','DEFER','UNKNOWN','CLEANING','CLEANED'}
VERIFY_STATUSES={'DECLARED','OBSERVED','CORROBORATED','VERIFIED','DEGRADED','CONTRADICTED','UNKNOWN'}
def clean_run(v:dict)->dict:
    out=dict(v)
    out.setdefault('status','UNKNOWN'); out.setdefault('verification_status','UNKNOWN')
    if out['status'] not in RUN_STATUSES: out['status']='UNKNOWN'
    if out['verification_status'] not in VERIFY_STATUSES: out['verification_status']='UNKNOWN'
    for k in ('participants','metrics','evidence_classes'): out.setdefault(k, {} if k=='metrics' else [])
    for k in ('artifact_count','event_count','receipt_count'): out.setdefault(k,0)
    return out
