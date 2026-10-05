"""Bounded execution of one registered trusted recipe; no raw shell interface."""
from __future__ import annotations
import base64
from pathlib import Path
import os
import signal
import subprocess
import sys
import tempfile
import shutil
import threading
import time
import psutil
from cyber_lion.mission_control.edge_support import canonical,digest,object_bytes,read_regular,EdgeRejected
from cyber_lion.mission_control.edge_work_unit import validate_work_unit
from cyber_lion.mission_control.artifact_transfer import verify_bundle
REPO = Path(__file__).resolve().parents[3]

def _stop_child(proc, winjob):
    """Terminate only the child tree we created and wait for Windows handles to drain."""
    if proc is None:
        return
    if winjob is not None:
        winjob.close()
    elif os.name != 'nt':
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                raise EdgeRejected('EXEC_CHILD_DID_NOT_TERMINATE')
    if proc.stdin is not None and not proc.stdin.closed:
        try:
            proc.stdin.close()
        except OSError:
            pass

def _remove_workspace(path, *, timeout=3.0):
    """Retry Windows cleanup after terminated children release inherited handles."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except PermissionError as exc:
            if time.monotonic() >= deadline:
                raise EdgeRejected('EXEC_WORKSPACE_CLEANUP_FAILED') from exc
            time.sleep(0.05)

def run_registered(job,input_bytes,*,host_id,worker_id,private_parent,gate,endpoint=None,timeout=90,memory_bytes=268435456):
    validate_work_unit(job,host_id,worker_id)
    verify_bundle(input_bytes,job['input_sha256'],job['input_binding'])
    gate.require_clear()
    if not 0 < timeout <= 100 or not 67108864 <= memory_bytes <= 1073741824:
        raise EdgeRejected('execution budget')
    env = {k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','PATH','LANG'}}
    env['PYTHONUTF8'] = '1'
    request = canonical(dict(job=job,input_b64=base64.b64encode(input_bytes).decode(),host_id=host_id,worker_id=worker_id,endpoint=endpoint))
    code = 'import sys;sys.path.insert(0,sys.argv[1]);from cyber_lion.mission_control.edge_worker import main;raise SystemExit(main())'
    td = Path(tempfile.mkdtemp(prefix='lion-exec-', dir=private_parent))
    try:
        op, ep = td/'stdout', td/'stderr'
        proc = winjob = sender = None
        with op.open('wb') as out, ep.open('wb') as err:
            try:
                proc = subprocess.Popen([sys.executable,'-I','-B','-c',code,str(REPO)],cwd=td,env=env,
                    stdin=subprocess.PIPE,stdout=out,stderr=err,shell=False,start_new_session=os.name!='nt')
                if os.name == 'nt':
                    from .winjob import WindowsJob
                    winjob = WindowsJob(proc,memory_bytes)
                gate.require_clear()
                errors = []
                def send():
                    try:
                        proc.stdin.write(request)
                        proc.stdin.close()
                    except (OSError,ValueError) as exc:
                        errors.append(exc)
                sender = threading.Thread(target=send,daemon=True);sender.start()
                start = time.monotonic();observed = psutil.Process(proc.pid)
                while proc.poll() is None:
                    gate.require_clear()
                    if time.monotonic()-start > timeout:
                        raise EdgeRejected('EXEC_TIMEOUT_EFFECT_UNKNOWN')
                    if op.stat().st_size > 1100000 or ep.stat().st_size > 65536:
                        raise EdgeRejected('EXEC_OUTPUT_LIMIT')
                    try:
                        if observed.memory_info().rss > memory_bytes:
                            raise EdgeRejected('EXEC_MEMORY_LIMIT')
                    except psutil.NoSuchProcess:
                        pass
                    time.sleep(0.03)
                sender.join(timeout=1)
                gate.require_clear()
                if proc.returncode != 0 or errors or sender.is_alive():
                    raise EdgeRejected('WORKER_FAILED:'+read_regular(ep,65536).decode('utf-8','replace')[:500])
                value = object_bytes(read_regular(op,1100000),1100000)
                raw = base64.b64decode(value['output_b64'],validate=True)
                verify_bundle(raw,value['output_sha256'],job['output_binding'])
                return raw,dict(scope='OPERATOR_QUALIFICATION',task_id=job['task_id'],host_id=host_id,worker_id=worker_id,
                    pid=proc.pid,input_sha256=digest(input_bytes),output_sha256=digest(raw),exit_code=proc.returncode,
                    native_supervision='WINDOWS_JOB' if os.name=='nt' else 'POSIX_PROCESS_GROUP',live_admission=False)
            finally:
                _stop_child(proc, winjob)
                if sender is not None and sender.is_alive():
                    sender.join(timeout=1)
    finally:
        _remove_workspace(td)
