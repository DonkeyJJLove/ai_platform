"""Operator pilot on EXISTING R24 MD001/MD002, no rollout or new assignments.

Docker CLI timeout is not remote cancellation. No automatic retry is attempted;
trusted worker code has a finite 100-second watchdog. Not a hostile-code runner.
"""
from __future__ import annotations
import base64
from pathlib import Path
import subprocess
import sys
import uuid
REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0,str(REPO))
from cyber_lion.mission_control.edge_support import canonical,digest,object_bytes,read_regular,write_new,private_directory,EdgeRejected
from cyber_lion.mission_control.edge_work_unit import WORKER_FILES
from cyber_lion.mission_control.artifact_transfer import verify_bundle
from cyber_lion.enterprise.edge_yoke.pilot import initial,make_job,collect_product

STAGE = '''import sys,json,base64,hashlib,pathlib,tempfile
v=json.load(sys.stdin);root=pathlib.Path(tempfile.mkdtemp(prefix='lion-edge-r6-',dir='/tmp'))
for name,item in v.items():
 p=pathlib.PurePosixPath(name)
 if p.is_absolute() or '..' in p.parts:raise ValueError('stage path')
 raw=base64.b64decode(item['data'],validate=True)
 if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('stage digest')
 t=root/name;t.parent.mkdir(parents=True,exist_ok=True)
 with t.open('xb') as f:f.write(raw)
 if t.read_bytes()!=raw:raise ValueError('stage readback')
print(json.dumps({'workspace':str(root),'files':len(v)}))
'''

def run(output,*,docker_exe,context='desktop-linux',local_model=False,gate):
    root = Path(output).absolute()
    if root.exists():
        raise EdgeRejected('new output directory required')
    root = private_directory(root)
    if not Path(docker_exe).is_absolute():
        raise EdgeRejected('absolute Docker executable required')
    def call(args,raw=None,timeout=15):
        gate.require_clear()
        p = subprocess.run([docker_exe,'--context',context,*args],input=raw,capture_output=True,timeout=timeout,shell=False)
        if p.returncode:
            raise EdgeRejected('Docker operation failed:'+p.stderr.decode('utf-8','replace')[:800])
        if len(p.stdout) > 1500000:
            raise EdgeRejected('Docker output limit')
        gate.require_clear()
        return p.stdout
    def inspect(worker):
        import json
        value = json.loads(call(['inspect','lion-r24-'+worker.lower()]))[0]
        labels = value['Config'].get('Labels') or {}
        if (value['State'].get('Running') is not True or labels.get('com.docker.compose.project') != 'lion-r24-autonomy'
                or labels.get('LION_MATERIAL_WORKER_ID') != worker or value['Config'].get('User') != '65532:65532'):
            raise EdgeRejected('R24 identity/configuration mismatch')
        return dict(id=value['Id'],image=value['Image'],started_at=value['State']['StartedAt'],worker=worker)
    workers = {w:inspect(w) for w in ('MD001','MD002')}
    if workers['MD001']['id'] == workers['MD002']['id']:
        raise EdgeRejected('distinct workers required')
    sources = {}
    for name in WORKER_FILES:
        raw = read_regular(REPO/name)
        sources[name] = dict(data=base64.b64encode(raw).decode(),sha256=digest(raw))
    locations = {}
    for w, info in workers.items():
        value = object_bytes(call(['exec','-i','--user','65532:65532',info['id'],'python3','-B','-c',STAGE],canonical(sources)))
        locations[w] = value['workspace']
    rid = 'QUAL-R24-'+uuid.uuid4().hex[:12]
    raw, binding = initial(rid)
    receipts = []
    write_new(root/'intent.bundle.json',raw)
    def execute(w,job,data):
        if inspect(w) != workers[w]:
            raise EdgeRejected('container changed')
        payload = canonical(dict(job=job,input_b64=base64.b64encode(data).decode(),host_id='MOON',worker_id=w,
                                 endpoint='http://host.docker.internal:8772' if job['use_local_model'] else None))
        code = 'import sys;sys.path.insert(0,sys.argv[1]);from cyber_lion.mission_control.edge_worker import main;raise SystemExit(main())'
        result = object_bytes(call(['exec','-i','--user','65532:65532','--workdir',locations[w],workers[w]['id'],
                                     'python3','-I','-B','-c',code,locations[w]],payload,timeout=110),1500000)
        if inspect(w) != workers[w]:
            raise EdgeRejected('container changed before readback')
        out = base64.b64decode(result['output_b64'],validate=True)
        verify_bundle(out,result['output_sha256'],job['output_binding'])
        receipts.append(dict(worker=workers[w],workspace=locations[w],task_id=job['task_id'],input_sha256=digest(data),output_sha256=digest(out)))
        return out
    builder = make_job(rid,'BUILD_INTEGRITY_TOOL','MD001',raw,binding,'MOON')
    builder['use_local_model'] = local_model
    built = execute('MD001',builder,raw)
    write_new(root/'built.bundle.json',built)
    verifier = make_job(rid,'VERIFY_INTEGRITY_TOOL','MD002',built,builder['output_binding'],'MOON')
    verified = execute('MD002',verifier,built)
    write_new(root/'verified.bundle.json',verified)
    product = collect_product(root,built,builder['output_binding'],verified,verifier['output_binding'])
    report = dict(result='PASS_OPERATOR_QUALIFICATION',scope='EXISTING_R24_TWO_CONTAINER_PILOT',receipts=receipts,product=product,
                  live_mission_executed=False,new_containers=False,main_workers_restarted=False,
                  local_model_requested=local_model,inflight_remote_cancellation=False,
                  source_sha256={n:v['sha256'] for n,v in sources.items()})
    write_new(root/'PILOT_RECEIPT.json',canonical(report))
    return report
