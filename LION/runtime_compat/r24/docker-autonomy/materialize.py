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
WORKER_IDS=tuple(f"MD{i:03d}" for i in range(1,33))
PRIVATE_SUBDIRS=("artifacts","contexts","verifiers","state")


def cooperative_private_root(runtime: Path):
    runtime=Path(runtime)
    if not runtime.is_absolute() or runtime.is_symlink() or runtime.resolve(strict=True)!=runtime:
        raise SystemExit("runtime root unavailable or unsafe")
    private=runtime/"private"
    if private.exists():
        if private.is_symlink() or not private.is_dir() or private.resolve(strict=True)!=private:
            raise SystemExit("cooperative private root unavailable or unsafe")
    return private


def cooperative_private_paths(runtime: Path):
    root=cooperative_private_root(runtime)
    return tuple(root/worker for worker in WORKER_IDS)


def _ensure_private_directory(path: Path):
    if path.exists():
        if path.is_symlink() or not path.is_dir() or path.resolve(strict=True)!=path:
            raise SystemExit("cooperative private directory unavailable or unsafe: "+str(path))
    else:
        path.mkdir()
    return path


def ensure_cooperative_private_layout(runtime: Path):
    """Create only missing private directories; never delete persistent worker state."""
    private=cooperative_private_root(runtime)
    _ensure_private_directory(private)
    roots=[]
    for worker in WORKER_IDS:
        worker_root=_ensure_private_directory(private/worker)
        for name in PRIVATE_SUBDIRS:
            _ensure_private_directory(worker_root/name)
        roots.append(worker_root)
    return tuple(roots)


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

    provider_src=canonical/"cooperative-provider.py"
    if not provider_src.is_file():
        raise SystemExit("canonical cooperative provider artifact missing")
    provider_artifact=runtime/"provider-artifact"
    if provider_artifact.exists():
        if provider_artifact.is_symlink() or not provider_artifact.is_dir():
            raise SystemExit("cooperative provider artifact root unavailable or unsafe")
        shutil.rmtree(provider_artifact)
    provider_artifact.mkdir()
    shutil.copy2(provider_src,provider_artifact/"cooperative-provider.py")

    unbound=runtime/"unbound"
    _ensure_private_directory(unbound)
    for name in ("provider-state","control-state","mission-control"):
        _ensure_private_directory(unbound/name)

    observer_uid=os.getuid()
    observer_gid=os.getgid()

    private_root=cooperative_private_root(runtime)
    if private_root.exists():
        # Preserve replay/admission/budget/materialization bytes while temporarily
        # reclaiming ownership for structural validation/rematerialization.
        run([
            "docker","run","--rm","--user","0:0","--entrypoint","/bin/sh",
            "-v",str(private_root)+":/target",
            "lion-r20-worker:r1","-c",
            "chown -R "+str(observer_uid)+":"+str(observer_gid)+" /target && chmod -R u+rwX /target",
        ])
    private_workers=ensure_cooperative_private_layout(runtime)

    for name in ("status","gate"):
        target=runtime/name
        if target.exists():
            # Previous worker-owned 0640 files are intentionally not removable
            # by the read-only observation group. Reclaim only this bounded
            # runtime directory through the same local worker image, then remove it.
            run([
                "docker","run","--rm","--user","0:0","--entrypoint","/bin/sh",
                "-v",str(target)+":/target",
                "lion-r20-worker:r1","-c",
                "chown -R "+str(observer_uid)+":"+str(observer_gid)+" /target && chmod -R u+rwX /target",
            ])
            shutil.rmtree(target)
        target.mkdir(parents=True,exist_ok=True)
    # The worker image runs as 65532:65532. Preserve the hardened bind-mount
    # ownership used by the proven R23 fleet without making these directories
    # world-writable. Docker root performs only this bounded ownership repair.
    run([
        "docker","run","--rm","--user","0:0","--entrypoint","/bin/sh",
        "-v",str(runtime/"status")+":/status",
        "-v",str(runtime/"gate")+":/gate",
        "lion-r20-worker:r1","-c",
        "chown 65532:"+str(observer_gid)+" /status /gate && chmod 2750 /status /gate",
    ])
    for target in (runtime/"status",runtime/"gate"):
        stat=target.stat()
        if (stat.st_uid,stat.st_gid,stat.st_mode & 0o7777)!=(65532,observer_gid,0o2750):
            raise SystemExit("worker writable directory ownership mismatch: "+str(target))

    # Private cooperative state survives source rematerialization. Each container
    # receives only its own worker root at /cooperative.
    run([
        "docker","run","--rm","--user","0:0","--entrypoint","/bin/sh",
        "-v",str(private_root)+":/private",
        "lion-r20-worker:r1","-c",
        "chown -R 65532:"+str(observer_gid)+" /private && "
        "find /private -type d -exec chmod 2750 {} + && "
        "find /private -type f -exec chmod 0640 {} +",
    ])
    private_targets=(private_root,)+tuple(
        child
        for worker_root in private_workers
        for child in (worker_root,)+(tuple(worker_root/name for name in PRIVATE_SUBDIRS))
    )
    for target in private_targets:
        stat_value=target.stat()
        if (stat_value.st_uid,stat_value.st_gid,stat_value.st_mode & 0o7777)!=(65532,observer_gid,0o2750):
            raise SystemExit("cooperative private directory ownership mismatch: "+str(target))

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
    provider_artifact_sha=sha256_file(provider_artifact/"cooperative-provider.py")
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
        "observation_gid":observer_gid,
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
        "cooperative_provider_artifact_sha256":provider_artifact_sha,
        "cooperative_provider_artifact_path":str(provider_artifact/"cooperative-provider.py"),
        "cooperative_readonly_mount_contract":{
            "provider_state":"${LION_COOPERATIVE_PROVIDER_STATE_HOST_PATH}",
            "control_state":"${LION_COOPERATIVE_CONTROL_STATE_HOST_PATH}",
            "mission_control":"${LION_COOPERATIVE_MISSION_CONTROL_HOST_PATH}",
            "container_mode":"READ_ONLY",
        },
        "identity_digest":body["identity_digest"],
        "runtime_dir":str(runtime),
        "requested_workers":32,
        "cooperative_private_worker_roots":len(private_workers),
        "cooperative_private_root":str(private_root),
        "cooperative_bootstrap_mode":"UNBOUND",
        "cooperative_private_state_preserved":True,
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
