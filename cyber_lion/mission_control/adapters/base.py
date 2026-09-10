class Adapter:
 adapter_id='base'; supported_process_classes=()
 def probe(self): return True
 def discover_runs(self): return []
 def snapshot(self,run_id): return {}
 def events(self,run_id): return []
 def metrics(self,run_id): return {}
 def participants(self,run_id): return []
 def artifacts(self,run_id): return []
 def receipts(self,run_id): return []
 def reconcile(self,run_id): return {'verification_status':'UNKNOWN'}
