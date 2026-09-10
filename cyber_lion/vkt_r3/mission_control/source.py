from __future__ import annotations
import json, subprocess, uuid
CLIENT='/usr/local/libexec/lion-vkt-effect-admission-client.py'
class EvidenceSource:
    def __init__(self,head:str,tree:str,client:str=CLIENT): self.head=head; self.tree=tree; self.client=client
    def read(self):
        run_id='vkt-r3-mc-'+uuid.uuid4().hex[:16]
        p=subprocess.run([self.client,'evidence','--source-head',self.head,'--source-tree',self.tree,'--run-id',run_id],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=45,check=False)
        if p.returncode!=0: raise RuntimeError('evidence-client-failed:'+p.stderr[-500:])
        data=json.loads(p.stdout)
        if not data.get('ok'): raise RuntimeError(str(data.get('error') or 'evidence-denied'))
        result=data.get('result')
        if not isinstance(result,dict): raise RuntimeError('evidence-result-not-object')
        return result
