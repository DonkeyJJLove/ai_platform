EVENT_SCHEMA='lion.observation-event/v1'
EVENT_TYPES={'RUN_DISCOVERED','RUN_STARTED','PHASE_STARTED','PHASE_COMPLETED','METRIC','PARTICIPANT','ARTIFACT','RECEIPT','EVIDENCE','WARNING','ERROR','RUN_COMPLETED','CLEANUP_STARTED','CLEANUP_COMPLETED','RUN_RECONCILED'}
REQUIRED_EVENT_FIELDS={'schema_version','event_id','run_id','timestamp','event_type','process_language','process_class','adapter_type','host','runtime','phase','status','source','target','authority','evidence_class','payload','artifact_refs','receipt_refs'}
def validate_event(v):
    if not isinstance(v,dict) or set(v)!=REQUIRED_EVENT_FIELDS: raise ValueError('event fields must be exact')
    if v['schema_version']!=EVENT_SCHEMA or v['event_type'] not in EVENT_TYPES: raise ValueError('invalid event')
    if not isinstance(v['payload'],dict) or not isinstance(v['artifact_refs'],list) or not isinstance(v['receipt_refs'],list): raise ValueError('invalid event payload')
    return v
