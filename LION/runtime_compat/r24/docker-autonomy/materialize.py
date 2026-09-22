#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CONFIRM="LION-R24-FULL-CONTROL-PLANE-FEDERATION-64L32M-R1"
PROFILE="LION_MATERIAL_EXECUTOR_V2"


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, stdin=subprocess.DEVNULL, **kwargs)


def output(args):
    return subprocess.check_output(args, text=True, stdin=subprocess.DEVNULL).strip()


def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk=f.read(1024*1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def canon(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")


def service_probe(url):
    with urllib.request.urlopen(url,timeout=5) as response:
        if response.status!=200:
            raise RuntimeError("service probe status "+str(response.status))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",default="/srv/lion-e4-candidate-r1/r20-mission/source")
    p.add_argument("--runtime",default="/srv/lion-e4-candidate-r1/r20-mission/r24-autonomy")
    p.add_argument("--confirm",required=True)
    p.add_argument("--up",action="store_true")
    p.add_argument("--timeout",type=int,default=90)
    args=p.parse_args()
    if args.confirm!=CONFIRM:
        raise SystemExit("confirmation mismatch")

    repo=Path(args.repo).resolve()
    runtime=Path(args.runtime).resolve()
    if not (repo/".git").exists():
        raise SystemExit("repo identity unavailable")

    active=output(["docker","ps","-a","--filter","label=LION_WORKER_PROFILE="+PROFILE,"--format","{{.Names}}"])
    if active.strip():
        raise SystemExit("R24 worker containers already exist; stop the fleet before rematerialization")

    run(["git","-C",str(repo),"fetch","--no-tags","origin","refs/heads/master"])
    head=output(["git","-C",str(repo),"rev-parse","FETCH_HEAD"])
    tree=output(["git","-C",str(repo),"rev-parse","FETCH_HEAD^{tree}"])
    remote=output(["git","-C",str(repo),"ls-remote","origin","refs/heads/master"]).split()[0]
    if head!=remote:
        raise SystemExit("remote master changed during materialization")

    archive=subprocess.check_output(["git","-C",str(repo),"archive","--format=tar",head])
    runtime.mkdir(parents=True,exist_ok=True)
    source=runtime/"source"
    if source.exists():
        shutil.rmtree(source)
    source.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive),mode="r:") as tf:
        tf.extractall(source,filter="data")

    canonical=source/"LION/runtime_compat/r24/docker-autonomy"
    for name in ("worker.py","compose.yaml","fleet-currentness.py"):
        src=canonical/name
        if not src.is_file():
            raise SystemExit("canonical R24 fleet artifact missing: "+name)
        shutil.copy2(src,runtime/name)

    for name in ("status","gate"):
        target=runtime/name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True,exist_ok=True)

    sys.path.insert(0,str(source))
    from cyber_lion.mission_control.material_worker_runtime import (
        PROFILE as RUNTIME_PROFILE,
        DIRECT_ASSIGNMENT_KINDS,
        ARCHITECTURE_CAPABILITIES,
        INDEPENDENCE_STATE,
    )
    if RUNTIME_PROFILE!=PROFILE:
        raise SystemExit("worker profile identity drift")

    worker_sha=sha256_file(runtime/"worker.py")
    contract_sha=sha256_file(source/"cyber_lion/mission_control/material_worker_runtime.py")
    compose_sha=sha256_file(runtime/"compose.yaml")
    body={
        "schema":"lion.material-worker-source-identity/v1",
        "profile":PROFILE,
        "repository":"DonkeyJJLove/ai_platform",
        "source_head":head,
        "source_tree":tree,
        "worker_source_sha256":worker_sha,
        "runtime_contract_sha256":contract_sha,
        "compose_sha256":compose_sha,
        "authority_ceiling":"NONE",
        "material_executor_independence":INDEPENDENCE_STATE,
        "direct_assignment_kinds":list(DIRECT_ASSIGNMENT_KINDS),
        "architecture_capabilities":list(ARCHITECTURE_CAPABILITIES),
        "materialized_at":utcnow(),
    }
    body["identity_digest"]=hashlib.sha256(canon(body)).hexdigest()
    tmp=runtime/"identity.tmp"
    tmp.write_text(json.dumps(body,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    os.replace(tmp,runtime/"identity.json")

    receipt={
        "schema":"lion.r24-material-fleet-materialization/v1",
        "observed_at":utcnow(),
        "profile":PROFILE,
        "source_head":head,
        "source_tree":tree,
        "worker_source_sha256":worker_sha,
        "runtime_contract_sha256":contract_sha,
        "compose_sha256":compose_sha,
        "identity_digest":body["identity_digest"],
        "runtime_dir":str(runtime),
        "requested_workers":32,
        "authority_effect":"NONE",
        "up":False,
    }

    if args.up:
        service_probe("http://127.0.0.1:8766/api/v3/local/assignments?limit=1")
        # The model endpoint is reachable from the Docker host-gateway path, not
        # from the WSL loopback. Each worker probes /v1/models itself and the
        # fleet is not READY until all 32 workers prove that exact path.
        run(["docker","compose","-p","lion-r24-autonomy","-f",str(runtime/"compose.yaml"),"up","-d"],cwd=runtime)
        deadline=time.time()+max(10,args.timeout)
        last=None
        while time.time()<deadline:
            try:
                raw=output([sys.executable,str(runtime/"fleet-currentness.py")])
                last=json.loads(raw.splitlines()[-1])
                if last.get("state")=="READY" and last.get("materialized")==32 and last.get("ready")==32:
                    break
            except Exception as exc:
                last={"state":"STARTING","error":type(exc).__name__+":"+str(exc)[:400]}
            time.sleep(1)
        if not last or last.get("state")!="READY":
            raise SystemExit("fleet failed to reach READY: "+json.dumps(last,sort_keys=True))
        receipt["up"]=True
        receipt["fleet_currentness"]=last

    receipt["receipt_digest"]=hashlib.sha256(canon(receipt)).hexdigest()
    out=runtime/"materialization-receipt.json"
    out.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(receipt,sort_keys=True))


if __name__=="__main__":
    main()
