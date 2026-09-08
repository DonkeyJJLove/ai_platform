#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timezone
REPO='https://github.com/DonkeyJJLove/ai_platform.git'; BRANCH='experiment/local-swarm-p0-docker-polygon'
CANONICAL=Path('/opt/lion/scale64-control/canonical/lion-effect-admission-broker.py'); PUBLIC=Path('/opt/lion/scale64-control-state'); STATE=Path('/var/lib/lion-scale64-control')
MAIN='/usr/local/bin/lion-effect-admission'; UPDATER='/usr/local/bin/lion-broker-update'
def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def write(name,obj):
    raw=(json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n').encode()
    for root in (PUBLIC,STATE): root.mkdir(parents=True,exist_ok=True); tmp=root/(name+'.tmp'); tmp.write_bytes(raw); os.replace(tmp,root/name)
def run(argv,timeout=900):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout,check=False)
    if p.returncode: raise RuntimeError(f'command failed rc={p.returncode}: {p.stderr[-2000:]}')
    return p.stdout.strip()
def jcmd(argv,timeout=900):
    v=json.loads(run(argv,timeout));
    if not isinstance(v,dict) or v.get('ok') is not True: raise RuntimeError(f'operation denied: {v}')
    return v
def source():
    out=run(['/usr/bin/git','ls-remote','--exit-code',REPO,f'refs/heads/{BRANCH}'],60); parts=out.split(); head=parts[0]
    if len(parts)!=2 or len(head)!=40: raise RuntimeError('live head invalid')
    td=Path(tempfile.mkdtemp(prefix='lion-scale64-source-'))
    try:
        run(['/usr/bin/git','init',str(td)],30); run(['/usr/bin/git','-C',str(td),'remote','add','origin',REPO],30); run(['/usr/bin/git','-C',str(td),'fetch','--no-tags','--depth=1','origin',f'refs/heads/{BRANCH}'],180)
        if run(['/usr/bin/git','-C',str(td),'rev-parse','FETCH_HEAD'],30)!=head: raise RuntimeError('head moved')
        return head,run(['/usr/bin/git','-C',str(td),'rev-parse','FETCH_HEAD^{tree}'],30)
    finally: shutil.rmtree(td,ignore_errors=True)
def main():
    write('status.json',{'state':'RUNNING','started_at':now()}); head,tree=source(); write('source.json',{'head':head,'tree':tree,'branch':BRANCH})
    up=jcmd([UPDATER,'ping'])['result']; current=up['target_sha256']; csha=hashlib.sha256(CANONICAL.read_bytes()).hexdigest()
    if current!=csha:
        args=['--expected-current-sha256',current,'--replacement-file',str(CANONICAL),'--source-head',head,'--source-tree',tree,'--reason','repository-native Scale64 convergence']
        write('broker-update.json',{'validate':jcmd([UPDATER,'validate-update',*args]),'apply':jcmd([UPDATER,'apply-update',*args])})
    write('broker-ping.json',jcmd([MAIN,'ping']))
    pre=jcmd([MAIN,'precheck-scale64','--source-head',head,'--source-tree',tree]); write('precheck-before.json',pre)
    if pre['result'].get('provider_current') is not True:
        write('prepare.json',jcmd([MAIN,'prepare-scale64','--source-head',head,'--source-tree',tree],600)); pre=jcmd([MAIN,'precheck-scale64','--source-head',head,'--source-tree',tree]); write('precheck-before.json',pre)
    r=pre['result']
    if r.get('clean_for_new_run') is not True or r.get('container_count')!=0 or r.get('network_count')!=0: raise RuntimeError('pre-run inventory not clean')
    rv=jcmd([MAIN,'run-scale64','--source-head',head,'--source-tree',tree],1200); write('run.json',rv); summary=rv['result']; req=summary['run_request_id']
    write('evidence.json',jcmd([MAIN,'evidence','--run-request-id',req],120)); post=jcmd([MAIN,'precheck-scale64','--source-head',head,'--source-tree',tree]); write('precheck-after.json',post)
    pr=post['result']; ok=summary.get('classification')=='FULL_SUCCESS' and pr.get('container_count')==0 and pr.get('network_count')==0 and pr.get('clean_for_new_run') is True
    recon={'outcome':'MATCHED' if ok else 'MISMATCHED','source_head':head,'source_tree':tree,'run_request_id':req,'finished_at':now()}; write('reconciliation.json',recon); write('status.json',{'state':'SUCCEEDED' if ok else 'FAILED','finished_at':now(),'reconciliation':recon}); return 0 if ok else 2
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc: write('status.json',{'state':'FAILED','finished_at':now(),'error':type(exc).__name__+':'+str(exc)[:2000]}); raise
