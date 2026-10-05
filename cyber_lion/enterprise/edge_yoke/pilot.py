"""Finite two-process qualification. It does not register or activate a mission."""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys
import time
import uuid
from cyber_lion.mission_control.edge_support import canonical,digest,read_regular,object_bytes,private_directory,write_new,EdgeRejected
from cyber_lion.mission_control.edge_work_unit import worker_digest
from cyber_lion.mission_control.artifact_transfer import create_bundle,verify_bundle,materialize_bundle
from .observer import initialize,REPO
from .policy import YokePolicy
from .gate import YokeGate
from .executor import run_registered
BASE_HEAD = '59f21b0db4c2d516c7e6f37df8affef3aca36d28'
BASE_TREE = '23dcafbcf42d0bd8947c88bd068b81dde0b7b040'

def initial(run_id):
    spec = canonical(dict(recipe='integrity-cli-v1',test_count=8))
    ctx = digest(spec)
    b = dict(repository='DonkeyJJLove/ai_platform',source_head=BASE_HEAD,mission_id=run_id,
             assignment_id=run_id+'-intent',conversation_id='qualification-not-live-conversation',
             binding_epoch=1,generation=1,lease_generation=1,context_digest=ctx,projection_digest=ctx,
             request_id=run_id+'-intent',producer_ref='OPERATOR_PLAN')
    return create_bundle({'spec.json':spec},b), b

def make_job(run_id,operation,worker,raw,binding,host):
    tid = run_id+'-'+worker
    ob = dict(binding,assignment_id=tid,request_id=tid,producer_ref=worker)
    return dict(schema='lion.edge.work-unit/v2',scope='OPERATOR_QUALIFICATION',task_id=tid,host_id=host,
        worker_id=worker,operation=operation,expires_at=time.time()+180,input_sha256=digest(raw),
        input_binding=binding,output_binding=ob,executor_source_digest=worker_digest(),use_local_model=False,
        coordinates=dict(lane='qualification',provider_session_ref='qualification-session',message_id=tid,
                         correlation_id=run_id,causation_id=binding['request_id'],source_tree=BASE_TREE,
                         context_bytes_sha256=binding['context_digest']))

def collect_product(root,built,binding,verified,vbinding):
    _, files = verify_bundle(verified,digest(verified),vbinding)
    report = object_bytes(files['verification.json'])
    if report.get('status') != 'PASS' or report.get('distinct_worker') is not True or report.get('input_sha256') != digest(built):
        raise EdgeRejected('verification binding')
    received = materialize_bundle(built,digest(built),binding,private_directory(root/'products'))
    write_new(root/'verification.json',files['verification.json'])
    fixture = private_directory(root/'cli-input')
    data = b'actual CLI readback\n'
    write_new(fixture/'input.txt',data)
    manifest = dict(schema='lion.simple-product/v1',files=[dict(path='input.txt',size=len(data),sha256=digest(data))])
    write_new(root/'cli-manifest.json',canonical(manifest))
    p = subprocess.run([sys.executable,'-I',str(Path(received['workspace'])/'product_verifier.py'),
                         str(fixture),str(root/'cli-manifest.json')],capture_output=True,timeout=5)
    if p.returncode != 0 or object_bytes(p.stdout).get('status') != 'PASS':
        raise EdgeRejected('produced executable CLI failed')
    return dict(received,verification=report,product_cli_executed=True)

def demo(output,*,host_id='MOON',endpoint=None):
    root = Path(output).absolute()
    if root.exists():
        raise EdgeRejected('new output directory required')
    root = private_directory(root)
    home = private_directory(root/'observer')
    cfg = initialize(home,host_id,YokePolicy(cool_samples=2))
    gate = YokeGate(snapshot=home/'snapshot.json',host_id=host_id,public_key=cfg['public_key'],policy_sha256=cfg['policy_sha256'])
    log = (root/'observer.log').open('wb')
    proc = subprocess.Popen([sys.executable,'-B',str(REPO/'tools/lion_edge_yoke.py'),'watch','--home',str(home)],
                             cwd=REPO,stdout=log,stderr=log)
    try:
        deadline = time.monotonic()+20
        while True:
            try:
                gate.require_clear()
                break
            except EdgeRejected:
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise EdgeRejected('observer not ready; inspect observer.log and signed snapshot')
                time.sleep(.2)
        rid = 'QUAL-'+uuid.uuid4().hex[:16]
        raw, binding = initial(rid)
        write_new(root/'intent.bundle.json',raw)
        builder = make_job(rid,'BUILD_INTEGRITY_TOOL','Q-BUILD',raw,binding,host_id)
        builder['use_local_model'] = endpoint is not None
        built, br = run_registered(builder,raw,host_id=host_id,worker_id='Q-BUILD',private_parent=root,gate=gate,endpoint=endpoint)
        write_new(root/'built.bundle.json',built)
        verifier = make_job(rid,'VERIFY_INTEGRITY_TOOL','Q-VERIFY',built,builder['output_binding'],host_id)
        result, vr = run_registered(verifier,built,host_id=host_id,worker_id='Q-VERIFY',private_parent=root,gate=gate)
        write_new(root/'verified.bundle.json',result)
        product = collect_product(root,built,builder['output_binding'],result,verifier['output_binding'])
        report = dict(result='PASS_OPERATOR_QUALIFICATION',scope='TWO_NATIVE_WORKER_PROCESSES',
                      live_mission_executed=False,worker_receipts=[br,vr],observer_pid=proc.pid,
                      local_model_requested=endpoint is not None,product=product)
        write_new(root/'PILOT_RECEIPT.json',canonical(report))
        return report
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait(timeout=3)
        log.close()
