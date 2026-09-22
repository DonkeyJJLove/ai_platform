#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RUNTIME_DIR=Path(os.environ.get("LION_R24_RUNTIME_DIR","/srv/lion-e4-candidate-r1/r20-mission/r24-autonomy"))
SOURCE_DIR=RUNTIME_DIR/"source"
sys.path.insert(0,str(SOURCE_DIR))

from cyber_lion.mission_control.material_worker_runtime import (
    PROFILE, STATUS_SCHEMA, DIRECT_ASSIGNMENT_KINDS, ARCHITECTURE_CAPABILITIES,
    INDEPENDENCE_STATE, MODEL_NAME, load_worker_identity,
)

STATUS_DIR=RUNTIME_DIR/"status"
IDENTITY_PATH=RUNTIME_DIR/"identity.json"
WORKER_PATH=RUNTIME_DIR/"worker.py"
CONTRACT_PATH=SOURCE_DIR/"cyber_lion/mission_control/material_worker_runtime.py"
PRIMARY_OUT=Path("/mnt/c/Users/d2j3/AppData/Local/LION/r24-autonomy/fleet-currentness.json")
COMPAT_OUT=Path("/mnt/c/Users/d2j3/AppData/Local/LION/r23-autonomy/fleet-currentness.json")
LABEL="LION_WORKER_PROFILE="+PROFILE
EXPECTED=32


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except Exception:
        return None


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()


identity=load_worker_identity(IDENTITY_PATH,WORKER_PATH,CONTRACT_PATH)
observer_gid=int(identity.get("observation_gid",-1))
runtime_dirs_secure=observer_gid>=0 and all(
    p.is_dir() and (p.stat().st_uid,p.stat().st_gid,p.stat().st_mode & 0o7777)==(65532,observer_gid,0o2750)
    for p in (STATUS_DIR,RUNTIME_DIR/"gate")
)
names=subprocess.check_output(
    ["docker","ps","-a","--filter","label="+LABEL,"--format","{{.Names}}"],text=True
).splitlines()
rows=[]
observed=datetime.now(timezone.utc)

for name in sorted(x for x in names if x.startswith("lion-r24-md")):
    info=json.loads(subprocess.check_output(["docker","inspect",name],text=True))[0]
    config=info.get("Config") or {}
    labels=config.get("Labels") or {}
    host=info.get("HostConfig") or {}
    state=(info.get("State") or {}).get("Status","").lower()
    wid=labels.get("LION_MATERIAL_WORKER_ID")
    status_path=STATUS_DIR/(str(wid)+".json")
    heartbeat=None
    status_file_secure=False
    if status_path.is_file():
        try:
            st=status_path.stat()
            status_file_secure=(st.st_uid,st.st_gid,st.st_mode & 0o777)==(65532,observer_gid,0o640)
            heartbeat=json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            heartbeat=None
            status_file_secure=False
    hb_time=parse_time((heartbeat or {}).get("observed_at"))
    age=None if hb_time is None else max(0.0,(observed-hb_time).total_seconds())
    arch=(heartbeat or {}).get("architecture") or {}
    mounts={m.get("Destination"):m for m in (info.get("Mounts") or [])}
    security=bool(
        runtime_dirs_secure
        and status_file_secure
        and host.get("ReadonlyRootfs") is True
        and host.get("Privileged") is False
        and "ALL" in (host.get("CapDrop") or [])
        and "no-new-privileges:true" in (host.get("SecurityOpt") or [])
        and int(host.get("PidsLimit") or 0)==128
        and int(host.get("Memory") or 0)==536870912
        and int(host.get("NanoCpus") or 0)==500000000
        and all(d in mounts for d in ("/src","/runtime/worker.py","/identity/current.json","/status","/gate"))
        and not mounts["/src"].get("RW")
        and not mounts["/runtime/worker.py"].get("RW")
        and not mounts["/identity/current.json"].get("RW")
        and mounts["/status"].get("RW")
        and mounts["/gate"].get("RW")
    )
    container_id=str(info.get("Id") or "")
    runtime_instance=str(arch.get("runtime_instance_id") or "")
    profile_ok=bool(
        heartbeat
        and heartbeat.get("schema")==STATUS_SCHEMA
        and heartbeat.get("worker_profile")==PROFILE
        and heartbeat.get("state")=="READY"
        and heartbeat.get("self_test")=="PASS"
        and heartbeat.get("model")==MODEL_NAME
        and tuple(heartbeat.get("direct_assignment_kinds") or ())==DIRECT_ASSIGNMENT_KINDS
        and arch.get("profile")==PROFILE
        and arch.get("source_head")==identity["source_head"]
        and arch.get("source_tree")==identity["source_tree"]
        and arch.get("worker_source_sha256")==identity["worker_source_sha256"]
        and arch.get("runtime_contract_sha256")==identity["runtime_contract_sha256"]
        and arch.get("identity_digest")==identity["identity_digest"]
        and arch.get("authority_ceiling")=="NONE"
        and arch.get("material_executor_independence")==INDEPENDENCE_STATE
        and tuple(arch.get("architecture_capabilities") or ())==ARCHITECTURE_CAPABILITIES
        and arch.get("external_effects_require_admission") is True
        and arch.get("model_is_authority") is False
        and arch.get("logical_drone_is_material_executor") is False
        and runtime_instance
        and container_id.startswith(runtime_instance)
    )
    ready=bool(wid and state=="running" and age is not None and age<=20 and profile_ok and security)
    rows.append({
        "material_worker_id":wid,
        "container_name":name,
        "container_id":container_id,
        "image_id":info.get("Image"),
        "container_state":state,
        "started_at":(info.get("State") or {}).get("StartedAt"),
        "heartbeat_observed_at":(heartbeat or {}).get("observed_at"),
        "heartbeat_age_seconds":age,
        "worker_profile":(heartbeat or {}).get("worker_profile"),
        "runtime_instance_id":runtime_instance or None,
        "boot_id":arch.get("boot_id"),
        "source_head":arch.get("source_head"),
        "source_tree":arch.get("source_tree"),
        "worker_source_sha256":arch.get("worker_source_sha256"),
        "runtime_contract_sha256":arch.get("runtime_contract_sha256"),
        "identity_digest":arch.get("identity_digest"),
        "architecture_capabilities":arch.get("architecture_capabilities"),
        "direct_assignment_kinds":heartbeat.get("direct_assignment_kinds") if heartbeat else None,
        "material_executor_independence":arch.get("material_executor_independence"),
        "docker_security_profile_ok":security,
        "status_file_secure":status_file_secure,
        "model":(heartbeat or {}).get("model"),
        "mission_control":(heartbeat or {}).get("mission_control"),
        "model_endpoint":(heartbeat or {}).get("model_endpoint"),
        "ready":ready,
    })

ids=[r.get("material_worker_id") for r in rows]
containers=[r.get("container_id") for r in rows]
boots={r.get("boot_id") for r in rows if r.get("boot_id")}
healthy=bool(
    len(rows)==EXPECTED
    and len(set(ids))==EXPECTED and None not in ids
    and len(set(containers))==EXPECTED and None not in containers
    and all(r["ready"] for r in rows)
)
body={
    "schema":"lion.docker-local-model-fleet-currentness/v1",
    "worker_status_schema":STATUS_SCHEMA,
    "worker_profile":PROFILE,
    "observed_at":now(),
    "physical_host":"MOON",
    "physical_failure_domains":1,
    "material_executor_independence":INDEPENDENCE_STATE,
    "independent_material_executors_proven":0,
    "unique_boot_ids":len(boots),
    "runtime_directories_secure":runtime_dirs_secure,
    "observation_gid":observer_gid,
    "expected_material_workers":EXPECTED,
    "materialized":len(rows),
    "ready":sum(1 for r in rows if r["ready"]),
    "unique_worker_ids":len(set(x for x in ids if x)),
    "unique_container_ids":len(set(x for x in containers if x)),
    "source_head":identity["source_head"],
    "source_tree":identity["source_tree"],
    "worker_source_sha256":identity["worker_source_sha256"],
    "runtime_contract_sha256":identity["runtime_contract_sha256"],
    "identity_digest":identity["identity_digest"],
    "required_direct_assignment_kinds":list(DIRECT_ASSIGNMENT_KINDS),
    "required_architecture_capabilities":list(ARCHITECTURE_CAPABILITIES),
    "model":MODEL_NAME,
    "state":"READY" if healthy else "DEGRADED",
    "workers":rows,
}
body["currentness_digest"]=hashlib.sha256(canonical(body)).hexdigest()

for output in (PRIMARY_OUT,COMPAT_OUT):
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_suffix(".tmp")
    tmp.write_text(json.dumps(body,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    os.replace(tmp,output)

print(json.dumps({
    "state":body["state"],
    "materialized":body["materialized"],
    "ready":body["ready"],
    "profile":PROFILE,
    "source_head":body["source_head"],
    "source_tree":body["source_tree"],
    "unique_boot_ids":body["unique_boot_ids"],
    "material_executor_independence":body["material_executor_independence"],
    "digest":body["currentness_digest"],
},sort_keys=True))
