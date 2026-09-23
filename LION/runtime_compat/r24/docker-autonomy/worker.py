#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from tools.lion_local_intelligence_runtime import LpclControlBridge, local_assignment_worker_once
from cyber_lion.mission_control.material_worker_runtime import (
    PROFILE,
    STATUS_SCHEMA,
    MODEL_NAME,
    DIRECT_ASSIGNMENT_KINDS,
    architecture_profile,
    digest_payload,
    identity_probe,
    load_worker_identity,
    validate_action_ir_payload,
    validate_runtime_envelope_payload,
)

WORKER_ID = os.environ["LION_MATERIAL_WORKER_ID"]
MC = os.environ.get("LION_MISSION_CONTROL_URL", "http://host.docker.internal:8766")
MODEL = os.environ.get("LION_LOCAL_MODEL_URL", "http://host.docker.internal:8772")
STATUS = Path("/status") / (WORKER_ID + ".json")
LOCK = Path("/gate/model.lock")
IDENTITY_PATH = Path(os.environ.get("LION_WORKER_IDENTITY_FILE", "/identity/current.json"))
WORKER_PATH = Path("/runtime/worker.py")
RUNTIME_CONTRACT_PATH = Path("/src/cyber_lion/mission_control/material_worker_runtime.py")
RUNTIME_INSTANCE_ID = socket.gethostname()
BOOT_ID_PATH = Path("/proc/sys/kernel/random/boot_id")
MODEL_HEALTH = Path("/gate/model-health.json")
WORKER_INDEX = max(1, int(WORKER_ID[-3:]))
POLL_INTERVAL_SECONDS = float(os.environ.get("LION_WORKER_POLL_INTERVAL_SECONDS", "2.0"))
STARTUP_SPREAD_SECONDS = float(os.environ.get("LION_WORKER_STARTUP_SPREAD_SECONDS", "2.0"))
MODEL_HEALTH_TTL_SECONDS = float(os.environ.get("LION_MODEL_HEALTH_TTL_SECONDS", "60"))
MODEL_LOCAL_CHECK_INTERVAL_SECONDS = float(os.environ.get("LION_MODEL_LOCAL_CHECK_INTERVAL_SECONDS", "15"))
TRANSPORT_DEGRADED_AFTER_ERRORS = int(os.environ.get("LION_TRANSPORT_DEGRADED_AFTER_ERRORS", "4"))
TRANSPORT_STALE_AFTER_SECONDS = float(os.environ.get("LION_TRANSPORT_STALE_AFTER_SECONDS", "20"))
STATUS_HEARTBEAT_SECONDS = float(os.environ.get("LION_WORKER_STATUS_HEARTBEAT_SECONDS", "5"))
STARTUP_JITTER_SECONDS = ((WORKER_INDEX - 1) % 32) / 32.0 * STARTUP_SPREAD_SECONDS


def stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def boot_id():
    try:
        return BOOT_ID_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return "UNKNOWN"


IDENTITY = load_worker_identity(IDENTITY_PATH, WORKER_PATH, RUNTIME_CONTRACT_PATH)
ARCH = architecture_profile(IDENTITY, runtime_instance_id=RUNTIME_INSTANCE_ID, boot_id=boot_id())


def write_status(**values):
    value = {
        "schema": STATUS_SCHEMA,
        "observed_at": stamp(),
        "material_worker_id": WORKER_ID,
        "mission_control": MC,
        "model_endpoint": MODEL,
        "model": MODEL_NAME,
        "worker_profile": PROFILE,
        "architecture": ARCH,
        **values,
    }
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o640)
    os.replace(tmp, STATUS)


def force_ipv4_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname != "host.docker.internal":
        return url
    ip = socket.gethostbyname(parsed.hostname)
    netloc = ip + ((":" + str(parsed.port)) if parsed.port else "")
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def request(url, body=None, timeout=10):
    data = None
    headers = {"User-Agent": "LION-R24-Material-Worker/2"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        force_ipv4_url(url),
        data=data,
        headers=headers,
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def transient_transport_error(exc):
    if isinstance(exc, (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in {101, 110, 111, 113}:
        return True
    reason = getattr(exc, "reason", None)
    if isinstance(reason, OSError) and getattr(reason, "errno", None) in {101, 110, 111, 113}:
        return True
    return False


def _model_cache_read():
    try:
        value=json.loads(MODEL_HEALTH.read_text(encoding="utf-8"))
    except Exception:
        return None
    checked=float(value.get("checked_at_epoch") or 0)
    if time.time()-checked > MODEL_HEALTH_TTL_SECONDS:
        return None
    if value.get("model") != MODEL_NAME or value.get("state") != "READY":
        return None
    return value


def _ensure_model_identity_locked(force=False):
    if not force:
        cached=_model_cache_read()
        if cached is not None:
            return cached
    models=request(MODEL.rstrip("/") + "/v1/models", timeout=5)
    ids=[
        str(x.get("id") or x.get("name") or x.get("model") or "")
        for x in (models.get("data") or models.get("models") or [])
        if isinstance(x, dict)
    ]
    if not any(MODEL_NAME in x for x in ids):
        raise RuntimeError("local model identity mismatch")
    value={
        "state":"READY",
        "model":MODEL_NAME,
        "checked_at_epoch":time.time(),
        "checked_at":stamp(),
        "checker":WORKER_ID,
    }
    tmp=MODEL_HEALTH.with_suffix(".tmp-"+WORKER_ID)
    tmp.write_text(json.dumps(value,sort_keys=True)+"\n",encoding="utf-8")
    os.chmod(tmp,0o640)
    os.replace(tmp,MODEL_HEALTH)
    return value


def ensure_model_identity(force=False):
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            return _ensure_model_identity_locked(force=force)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def transport_degraded(consecutive_errors,last_success_monotonic):
    if consecutive_errors >= TRANSPORT_DEGRADED_AFTER_ERRORS:
        return True
    if last_success_monotonic <= 0:
        return True
    return (time.monotonic()-last_success_monotonic) >= TRANSPORT_STALE_AFTER_SECONDS


bridge = LpclControlBridge(None, MC)


def modelprov(messages, max_tokens=384):
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            _ensure_model_identity_locked(force=False)
            out = request(
                MODEL.rstrip("/") + "/v1/chat/completions",
                {"messages": messages, "max_tokens": int(max_tokens), "temperature": 0.1, "stream": False},
                timeout=120,
            )
            return out["choices"][0]["message"]["content"]
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def assignment_input(row):
    value = row.get("input")
    if isinstance(value, dict):
        return value
    raw = row.get("input_json")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def receipt(assignment_id, claimed, status, result):
    return request(
        MC.rstrip("/") + "/api/v3/local/assignments/receipt",
        {
            "assignment_id": assignment_id,
            "material_drone_id": WORKER_ID,
            "lease_generation": claimed.get("lease_generation"),
            "status": status,
            "result": result,
            "effect_receipt_digest": None,
            "authority_effect": "NONE",
        },
        timeout=10,
    )


def material_contract_assignment_once(listing):
    supported = {
        "CANONICAL_ACTION_IR_VALIDATE",
        "RUNTIME_EXECUTION_ENVELOPE_VALIDATE",
        "MATERIAL_PAYLOAD_DIGEST",
        "MATERIAL_CURRENTNESS_PROBE",
    }
    for row in listing.get("assignments") or []:
        if row.get("material_drone_id") != WORKER_ID:
            continue
        payload = assignment_input(row)
        kind = payload.get("kind")
        if kind not in supported:
            continue
        aid = str(row.get("assignment_id") or "")
        if not aid:
            continue
        claimed = request(
            MC.rstrip("/") + "/api/v3/local/assignments/claim",
            {"assignment_id": aid, "material_drone_id": WORKER_ID},
            timeout=10,
        )
        payload = assignment_input(claimed) or payload
        try:
            if kind == "CANONICAL_ACTION_IR_VALIDATE":
                result = validate_action_ir_payload(payload)
            elif kind == "RUNTIME_EXECUTION_ENVELOPE_VALIDATE":
                result = validate_runtime_envelope_payload(payload)
            elif kind == "MATERIAL_PAYLOAD_DIGEST":
                result = digest_payload(payload)
            else:
                result = identity_probe(
                    IDENTITY,
                    worker_id=WORKER_ID,
                    runtime_instance_id=RUNTIME_INSTANCE_ID,
                    boot_id=boot_id(),
                )
            result.update({
                "worker_profile": PROFILE,
                "material_worker_id": WORKER_ID,
                "runtime_instance_id": RUNTIME_INSTANCE_ID,
                "source_head": IDENTITY["source_head"],
                "source_tree": IDENTITY["source_tree"],
            })
            return receipt(aid, claimed, "PASS", result)
        except Exception as exc:
            result = {
                "kind": str(kind),
                "error": type(exc).__name__ + ":" + str(exc)[:600],
                "worker_profile": PROFILE,
                "material_worker_id": WORKER_ID,
                "runtime_instance_id": RUNTIME_INSTANCE_ID,
                "authority_effect": "NONE",
            }
            return receipt(aid, claimed, "FAIL", result)
    return None


def material_sandbox_canary_once(listing):
    for row in listing.get("assignments") or []:
        if row.get("material_drone_id") != WORKER_ID:
            continue
        value = assignment_input(row)
        if value.get("kind") != "MATERIAL_SANDBOX_CANARY":
            continue
        aid = str(row.get("assignment_id") or "")
        if not aid:
            continue
        claimed = request(
            MC.rstrip("/") + "/api/v3/local/assignments/claim",
            {"assignment_id": aid, "material_drone_id": WORKER_ID},
            timeout=10,
        )
        value = assignment_input(claimed) or value
        token = str(value.get("token") or "")
        target_name = str(value.get("target_name") or "")
        content = str(value.get("content") or "")
        expected = str(value.get("expected_sha256") or "")
        if not token or not target_name or target_name != Path(target_name).name or len(content.encode("utf-8")) > 4096:
            raise RuntimeError("invalid material sandbox canary contract")
        data = content.encode("utf-8")
        if __import__("hashlib").sha256(data).hexdigest() != expected:
            raise RuntimeError("material sandbox canary expected digest mismatch")
        root = Path("/tmp/lion-r24-material-canary")
        root.mkdir(parents=True, exist_ok=True)
        target = root / target_name
        tmp = target.with_suffix(".tmp")
        with tmp.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
        observed = target.read_bytes()
        observed_sha = __import__("hashlib").sha256(observed).hexdigest()
        if observed_sha != expected or observed != data:
            raise RuntimeError("material sandbox canary readback mismatch")
        result = {
            "kind": "MATERIAL_SANDBOX_CANARY",
            "token": token,
            "material_worker_id": WORKER_ID,
            "worker_profile": PROFILE,
            "runtime_instance_id": RUNTIME_INSTANCE_ID,
            "target": str(target),
            "bytes_written": len(data),
            "expected_sha256": expected,
            "observed_sha256": observed_sha,
            "readback_match": True,
            "sandbox_scope": "CONTAINER_TMPFS",
            "authority_effect": "NONE",
        }
        return receipt(aid, claimed, "PASS", result)
    return None


write_status(
    state="STARTING",
    self_test="IDENTITY_VERIFIED",
    direct_assignment_kinds=list(DIRECT_ASSIGNMENT_KINDS),
    transport_state="STARTING",
    mission_control_reachability="UNKNOWN",
    model_reachability="UNKNOWN",
    poll_interval_seconds=POLL_INTERVAL_SECONDS,
    startup_jitter_seconds=STARTUP_JITTER_SECONDS,
    consecutive_transport_errors=0,
    last_receipt=None,
    last_error=None,
)

consecutive_transport_errors=0
last_success_monotonic=0.0
last_model_local_check_monotonic=0.0
last_status_monotonic=0.0
last_receipt=None
last_mc_ok_at=None
last_model_ok_at=None
time.sleep(STARTUP_JITTER_SECONDS)

while True:
    operation="MC_POLL"
    try:
        listing=request(MC.rstrip("/") + "/api/v3/local/assignments?limit=64", timeout=5)
        now_mono=time.monotonic()
        last_mc_ok_at=stamp()

        if last_model_local_check_monotonic<=0 or now_mono-last_model_local_check_monotonic>=MODEL_LOCAL_CHECK_INTERVAL_SECONDS:
            operation="MODEL_HEALTH"
            model_health=ensure_model_identity(force=False)
            last_model_ok_at=str(model_health.get("checked_at") or stamp())
            last_model_local_check_monotonic=now_mono

        consecutive_transport_errors=0
        last_success_monotonic=now_mono
        operation="CONTRACT_ASSIGNMENT"
        result=material_contract_assignment_once(listing)
        if result is None:
            operation="SANDBOX_ASSIGNMENT"
            result=material_sandbox_canary_once(listing)
        if result is None:
            operation="LOCAL_MODEL_ASSIGNMENT"
            result=local_assignment_worker_once(
                bridge,
                modelprov,
                material_drone_id=WORKER_ID,
                pending=listing.get("assignments") or [],
            )
        if result is not None:
            last_receipt=result
            print(json.dumps({"event":"LION_WORKER_RECEIPT","worker":WORKER_ID,"receipt":result},ensure_ascii=False),flush=True)

        now_mono=time.monotonic()
        if result is not None or now_mono-last_status_monotonic>=STATUS_HEARTBEAT_SECONDS:
            write_status(
                state="READY",
                self_test="PASS",
                direct_assignment_kinds=list(DIRECT_ASSIGNMENT_KINDS),
                transport_state="READY",
                mission_control_reachability="OK",
                model_reachability="OK" if last_model_ok_at else "UNKNOWN",
                last_mission_control_ok_at=last_mc_ok_at,
                last_model_ok_at=last_model_ok_at,
                poll_interval_seconds=POLL_INTERVAL_SECONDS,
                startup_jitter_seconds=STARTUP_JITTER_SECONDS,
                consecutive_transport_errors=0,
                last_transport_operation=operation,
                last_receipt=last_receipt,
                last_error=None,
            )
            last_status_monotonic=now_mono
        time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        write_status(
            state="STOPPED",
            self_test="PASS",
            direct_assignment_kinds=list(DIRECT_ASSIGNMENT_KINDS),
            transport_state="STOPPED",
            mission_control_reachability="UNKNOWN",
            model_reachability="UNKNOWN",
            consecutive_transport_errors=consecutive_transport_errors,
            last_receipt=last_receipt,
            last_error=None,
        )
        raise
    except Exception as exc:
        err=type(exc).__name__+":"+str(exc)[:800]
        transient=transient_transport_error(exc)
        if transient:
            consecutive_transport_errors+=1
        else:
            consecutive_transport_errors=max(consecutive_transport_errors+1,TRANSPORT_DEGRADED_AFTER_ERRORS)
        degraded=transport_degraded(consecutive_transport_errors,last_success_monotonic)
        state="DEGRADED" if degraded else "READY"
        self_test="FAIL" if degraded else "PASS"
        transport_state="DEGRADED" if degraded else "TRANSIENT_ERROR"
        print(json.dumps({
            "event":"LION_WORKER_ERROR",
            "worker":WORKER_ID,
            "operation":operation,
            "transient":transient,
            "consecutive_transport_errors":consecutive_transport_errors,
            "error":err,
        }),flush=True)
        write_status(
            state=state,
            self_test=self_test,
            direct_assignment_kinds=list(DIRECT_ASSIGNMENT_KINDS),
            transport_state=transport_state,
            mission_control_reachability="OK" if last_mc_ok_at and not degraded else "STALE",
            model_reachability="OK" if last_model_ok_at and not degraded else "STALE",
            last_mission_control_ok_at=last_mc_ok_at,
            last_model_ok_at=last_model_ok_at,
            poll_interval_seconds=POLL_INTERVAL_SECONDS,
            startup_jitter_seconds=STARTUP_JITTER_SECONDS,
            consecutive_transport_errors=consecutive_transport_errors,
            last_transport_operation=operation,
            last_receipt=last_receipt,
            last_error=err,
        )
        delay=min(10.0,1.0*(2**min(max(consecutive_transport_errors-1,0),3)))
        delay+=((WORKER_INDEX-1)%8)*0.05
        time.sleep(delay)
