def verification(run):
 e=set(run.get('evidence_classes') or [])
 if run.get('status')=='PASS' and len(e)>=2:return 'VERIFIED'
 if run.get('status') in {'RUNNING','PASS'}:return 'OBSERVED'
 return run.get('verification_status','UNKNOWN')
