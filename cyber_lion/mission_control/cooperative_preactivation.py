"""Single-worker cooperative preactivation before fleet readiness.

This module breaks the bootstrap cycle without weakening production readiness.
It prepares exactly one qualification-only cooperative WRITE assignment, runs
the existing R6.16 HELD->READY materialization, invokes the existing R6.17
single-worker qualification path, and stores the non-authoritative result in
Mission Control's existing mission_artifacts ledger.

The qualification assignment is never claimed or executed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from threading import RLock
from typing import Any, Callable, Mapping

from cyber_lion.mission_control import global_scheduler
from cyber_lion.mission_control.cooperative_artifacts import WRITE_KIND
from cyber_lion.mission_control import cooperative_production as cp

CAPABILITY_CLASS="COOPERATIVE_WORKER_PREACTIVATION"
CAPABILITY_ID="COOPERATIVE_WORKER_PREACTIVATION_R1"
EXECUTOR_ID="MISSION_CONTROL_COOPERATIVE_PREACTIVATION_PROVIDER"
ARTIFACT_TYPE="COOPERATIVE_WORKER_QUALIFICATION"
JOURNAL_TYPE="COOPERATIVE_WORKER_PREACTIVATION_JOURNAL"
QUALIFICATION_SCHEMA="lion.cooperative-worker-qualification/v1"
JOURNAL_SCHEMA="lion.cooperative-worker-preactivation-journal/v1"
ASSIGNMENT_SUFFIX="__COOP_PREACTIVATE"
PROVIDER_ID="COOPERATIVE_PREACTIVATION_PROVIDER_R1"
AUTHORITY_EFFECT="NONE"
EXECUTION_EFFECT="NONE"
_WORKER=re.compile(r"^MD[0-9]{3}$")

# Canonical R6.17 producer domain; the SHA is over the unwrapped evidence,
# never over worker-bootstrap metadata or a caller-controlled digest field.
_QUALIFICATION_DOMAIN=b"LION/COOPERATIVE-WORKER-QUALIFICATION/1\0"
_QUALIFICATION_FIELDS=frozenset({
    "schema","assignment_id","mission_id","worker_id","lease_generation",
    "release_evidence_digest","control_plane_evidence_digest",
    "private_context_pin_sha256","private_transfer_sha256",
    "private_materialization_digest","runtime_admission_digest",
    "provider_id","context_resolver","execution_engine",
    "writer_factory_built","execution_performed","authority_effect",
})
_WORKER_BOOTSTRAP_FIELDS=frozenset({"bootstrap_version","bootstrap_mode"})



class CooperativePreactivationError(RuntimeError):
    pass


def _require(condition:bool,reason:str)->None:
    if not condition:
        raise CooperativePreactivationError(reason)


def _sha(value:Any,label:str)->str:
    _require(
        isinstance(value,str) and len(value)==64
        and all(ch in "0123456789abcdef" for ch in value),
        label,
    )
    return value


@dataclass(frozen=True)
class CooperativePreactivationProvider:
    write_materializer: Callable[[Mapping[str,Any]],Mapping[str,Any]]
    qualifier: Callable[[str,str],Mapping[str,Any]]
    worker_id: str
    provider_id: str=PROVIDER_ID
    authority_effect: str=AUTHORITY_EFFECT

    def validate(self)->"CooperativePreactivationProvider":
        _require(type(self) is CooperativePreactivationProvider,"exact preactivation provider required")
        _require(callable(self.write_materializer),"preactivation write materializer")
        _require(callable(self.qualifier),"preactivation qualifier")
        _require(type(self.worker_id) is str and _WORKER.fullmatch(self.worker_id) is not None,
                 "preactivation worker identity")
        _require(self.provider_id==PROVIDER_ID and self.authority_effect==AUTHORITY_EFFECT,
                 "preactivation provider identity/authority")
        return self


class CooperativePreactivationRegistry:
    def __init__(self)->None:
        self._lock=RLock()
        self._provider:CooperativePreactivationProvider|None=None

    def install(self,provider:CooperativePreactivationProvider)->CooperativePreactivationProvider:
        provider.validate()
        with self._lock:
            if self._provider is not None:
                raise CooperativePreactivationError("preactivation provider already installed")
            self._provider=provider
        return provider

    def current(self)->CooperativePreactivationProvider|None:
        with self._lock:
            provider=self._provider
        return None if provider is None else provider.validate()

    def status(self)->dict[str,Any]:
        provider=self.current()
        return {
            "state":"READY" if provider is not None else "NOT_BOUND",
            "provider_id":provider.provider_id if provider is not None else PROVIDER_ID,
            "worker_id":provider.worker_id if provider is not None else None,
            "authority_effect":"NONE",
            "execution_effect":"NONE",
        }


def capability_registry_entries()->dict[str,tuple[dict[str,str],...]]:
    return {
        CAPABILITY_CLASS:({
            "capability_id":CAPABILITY_ID,
            "executor_id":EXECUTOR_ID,
            "effect_ceiling":"NONE",
            "mode":"ONE_WORKER_R616_R617_QUALIFICATION_ONLY",
        },),
    }


def _assignment(conn,mission_id:str,phase_id:str):
    row=conn.execute(
        """SELECT * FROM mission_execution_assignments
           WHERE mission_id=? AND phase_id=?
           ORDER BY created_at DESC,assignment_id DESC LIMIT 1""",
        (mission_id,phase_id+ASSIGNMENT_SUFFIX),
    ).fetchone()
    return dict(row) if row else None


def _validate_qualification(
    result:Mapping[str,Any], *,
    assignment:Mapping[str,Any],
    worker_id:str,
    release:Mapping[str,Any],
)->dict[str,Any]:
    """Bind canonical R6.17 receipt to both release-ledger and provider digests.

    The R6.17 *release_evidence_digest* is the SHA-256 of the entire persisted
    release JSON, not the nested materializer's evidence_digest.  The latter
    is returned separately as *control_plane_evidence_digest*.
    """
    _require(isinstance(result,Mapping),"qualification result")
    value=dict(result)
    extra=set(value)-_QUALIFICATION_FIELDS-{"qualification_digest"}
    _require(
        not extra or extra==_WORKER_BOOTSTRAP_FIELDS,
        "qualification unexpected result fields",
    )
    if extra:
        _require(value.get("bootstrap_version")=="1.0.0"
                 and value.get("bootstrap_mode")=="UNBOUND",
                 "qualification worker bootstrap evidence")
    evidence={k:v for k,v in value.items() if k in _QUALIFICATION_FIELDS}
    _require(set(evidence)==_QUALIFICATION_FIELDS,"qualification evidence schema")

    _require(isinstance(release,Mapping) and isinstance(release.get("evidence"),Mapping),
             "qualification canonical release unavailable")
    release_evidence=release["evidence"]
    outer=_sha(release.get("evidence_digest"),"qualification ledger release digest")
    inner=_sha(release_evidence.get("evidence_digest"),"qualification control plane digest")
    _require(global_scheduler.digest(dict(release_evidence))==outer,
             "qualification ledger release digest mismatch")
    _require(release.get("assignment_id")==assignment["assignment_id"]
             and release.get("mission_id")==assignment["mission_id"],
             "qualification canonical release identity")
    _require(value.get("schema")==QUALIFICATION_SCHEMA,"qualification schema")
    _require(value.get("assignment_id")==assignment["assignment_id"],
             "qualification assignment substitution")
    _require(value.get("mission_id")==assignment["mission_id"],
             "qualification mission substitution")
    _require(value.get("worker_id")==worker_id,"qualification worker substitution")
    _require(value.get("lease_generation")==int(assignment["lease_generation"]),
             "qualification generation substitution")
    _require(value.get("release_evidence_digest")==outer,
             "qualification release evidence substitution")
    _require(value.get("control_plane_evidence_digest")==inner,
             "qualification control-plane evidence substitution")
    _require(value.get("provider_id")==cp.WRITE_PROVIDER_ID,"qualification runtime provider")
    _require(value.get("writer_factory_built") is True,"qualification writer factory")
    _require(value.get("execution_performed") is False,"qualification executed effect")
    _require(value.get("authority_effect")=="NONE","qualification authority")
    for key in (
        "release_evidence_digest","control_plane_evidence_digest",
        "private_context_pin_sha256","private_transfer_sha256",
        "private_materialization_digest","runtime_admission_digest",
    ):
        _sha(value.get(key),"qualification "+key)
    for key in ("context_resolver","execution_engine"):
        _require(isinstance(value.get(key),str) and bool(value[key].strip()),
                 "qualification "+key)
    declared=_sha(value.get("qualification_digest"),"qualification digest")
    try:
        canonical=json.dumps(evidence,sort_keys=True,separators=(",",":"),
                             ensure_ascii=False,allow_nan=False).encode("utf-8")
    except (TypeError,ValueError,UnicodeError) as exc:
        raise CooperativePreactivationError("qualification canonical evidence invalid") from exc
    expected=sha256(_QUALIFICATION_DOMAIN+canonical).hexdigest()
    _require(declared==expected,"qualification canonical digest mismatch")
    return value


def _qualification_artifact(conn,mission_id:str,phase_id:str):
    row=global_scheduler.artifact(conn,mission_id,ARTIFACT_TYPE,phase_id=phase_id)
    if not row:
        return None
    content=row.get("content")
    _require(isinstance(content,dict),"qualification artifact content")
    _require(content.get("schema")==QUALIFICATION_SCHEMA,"qualification artifact schema")
    _require(content.get("authority_effect")=="NONE","qualification artifact authority")
    _require(content.get("execution_performed") is False,"qualification artifact effect")
    _sha(content.get("qualification_digest"),"qualification artifact digest")
    return row


def _journal_artifact(conn,mission_id:str,phase_id:str):
    row=global_scheduler.artifact(conn,mission_id,JOURNAL_TYPE,phase_id=phase_id)
    if not row:
        return None
    content=row.get("content")
    _require(isinstance(content,dict),"preactivation journal content")
    _require(content.get("schema")==JOURNAL_SCHEMA,"preactivation journal schema")
    _require(content.get("authority_effect")=="NONE","preactivation journal authority")
    _require(content.get("execution_effect")=="NONE","preactivation journal effect")
    return row


def _put_journal(conn,mission_id:str,phase_id:str,content:dict[str,Any],now_fn):
    value={
        "schema":JOURNAL_SCHEMA,
        **content,
        "authority_effect":"NONE",
        "execution_effect":"NONE",
    }
    return global_scheduler.put_artifact(
        conn,mission_id,JOURNAL_TYPE,value,now_fn,
        phase_id=phase_id,schema_id=JOURNAL_SCHEMA,authority_effect="NONE",
    )


def advance_preactivation(
    conn, *,
    mission_id:str,
    phase_id:str,
    generation:int,
    provider:CooperativePreactivationProvider,
    now_fn,
)->dict[str,Any]:
    """Advance at most one preactivation edge; never claim the assignment."""
    provider.validate()
    existing=_qualification_artifact(conn,mission_id,phase_id)
    if existing:
        content=existing["content"]
        return {
            "state":"PASS",
            "gate":"WORKER_QUALIFIED",
            "assignment_id":content["assignment_id"],
            "worker_id":content["worker_id"],
            "qualification_digest":content["qualification_digest"],
            "artifact_digest":existing["content_digest"],
            "authority_effect":"NONE",
            "execution_effect":"NONE",
        }

    assignment=_assignment(conn,mission_id,phase_id)
    if assignment is None:
        content=(
            "purpose=cooperative-preactivation\n"
            f"mission={mission_id}\n"
            f"worker={provider.worker_id}\n"
            "status=qualification-only\n"
        )
        content_digest=sha256(content.encode("utf-8")).hexdigest()
        payload={
            "kind":WRITE_KIND,
            "mission_id":mission_id,
            "generation":int(generation),
            "artifact_name":"lion-cooperative-preactivation.txt",
            "content":content,
            "expected_sha256":content_digest,
            "producer_model_call_id":"preactivation-source-r1",
            "parent_response_digest":content_digest,
            "capability":cp.CAPABILITY_PRODUCTION,
            "purpose":"COOPERATIVE_WORKER_PREACTIVATION",
            "lease_scope":"MISSION_DRIVER",
            "authority_effect":"NONE",
        }
        aid=global_scheduler.create_held_assignment(
            conn,mission_id,phase_id+ASSIGNMENT_SUFFIX,
            "LD001",provider.worker_id,payload,now_fn,
            lease_generation=int(generation),
        )
        assignment=dict(conn.execute(
            "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",(aid,)
        ).fetchone())

    if assignment["material_drone_id"]!=provider.worker_id:
        return {"state":"FAILED","gate":"PREACTIVATION_WORKER_SUBSTITUTION",
                "assignment_id":assignment["assignment_id"],"authority_effect":"NONE"}

    if assignment["state"]=="HELD":
        try:
            cp._materialize_and_release(
                conn,assignment["assignment_id"],
                materializer=provider.write_materializer,
                expected_kind=cp.WRITE_MATERIALIZATION_KIND,
                expected_provider=cp.WRITE_PROVIDER_ID,
                now_fn=now_fn,
            )
        except Exception as exc:
            return {
                "state":"FAILED",
                "gate":"PREACTIVATION_R616_FAILED",
                "assignment_id":assignment["assignment_id"],
                "error_class":type(exc).__name__,
                "authority_effect":"NONE",
            }
        assignment=dict(conn.execute(
            "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
            (assignment["assignment_id"],),
        ).fetchone())

    if assignment["state"]!="READY":
        return {
            "state":"BLOCKED",
            "gate":"PREACTIVATION_ASSIGNMENT_NOT_READY",
            "assignment_id":assignment["assignment_id"],
            "observed_state":assignment["state"],
            "authority_effect":"NONE",
        }

    release=global_scheduler.held_assignment_release_evidence(
        conn,assignment["assignment_id"]
    )
    if not release or not isinstance(release.get("evidence"),dict):
        return {
            "state":"BLOCKED",
            "gate":"PREACTIVATION_RELEASE_EVIDENCE_MISSING",
            "assignment_id":assignment["assignment_id"],
            "authority_effect":"NONE",
        }

    journal=_journal_artifact(conn,mission_id,phase_id)
    if journal is not None:
        journal_state=journal["content"].get("state")
        if journal_state in {"QUALIFYING","UNKNOWN","QUALIFIED"}:
            return {
                "state":"BLOCKED",
                "gate":"PREACTIVATION_QUALIFICATION_UNKNOWN",
                "assignment_id":assignment["assignment_id"],
                "journal_state":journal_state,
                "authority_effect":"NONE",
            }
        return {
            "state":"BLOCKED",
            "gate":"PREACTIVATION_JOURNAL_INVALID",
            "assignment_id":assignment["assignment_id"],
            "authority_effect":"NONE",
        }

    _put_journal(
        conn,mission_id,phase_id,{
            "state":"QUALIFYING",
            "assignment_id":assignment["assignment_id"],
            "worker_id":provider.worker_id,
            "release_evidence_digest":release["evidence"].get("evidence_digest"),
        },now_fn,
    )
    try:
        result=provider.qualifier(assignment["assignment_id"],provider.worker_id)
        value=_validate_qualification(
            result,
            assignment=assignment,
            worker_id=provider.worker_id,
            release=release,
        )
    except Exception as exc:
        _put_journal(
            conn,mission_id,phase_id,{
                "state":"UNKNOWN",
                "assignment_id":assignment["assignment_id"],
                "worker_id":provider.worker_id,
                "release_evidence_digest":release["evidence"].get("evidence_digest"),
                "error_class":type(exc).__name__,
            },now_fn,
        )
        return {
            "state":"BLOCKED",
            "gate":"PREACTIVATION_QUALIFICATION_UNKNOWN",
            "assignment_id":assignment["assignment_id"],
            "error_class":type(exc).__name__,
            "authority_effect":"NONE",
        }

    artifact=global_scheduler.put_artifact(
        conn,mission_id,ARTIFACT_TYPE,value,now_fn,
        phase_id=phase_id,schema_id=QUALIFICATION_SCHEMA,authority_effect="NONE",
    )
    _put_journal(
        conn,mission_id,phase_id,{
            "state":"QUALIFIED",
            "assignment_id":assignment["assignment_id"],
            "worker_id":provider.worker_id,
            "release_evidence_digest":release["evidence"].get("evidence_digest"),
            "qualification_digest":value["qualification_digest"],
            "qualification_artifact_digest":artifact["content_digest"],
        },now_fn,
    )
    return {
        "state":"PASS",
        "gate":"WORKER_QUALIFIED",
        "assignment_id":assignment["assignment_id"],
        "worker_id":provider.worker_id,
        "qualification_digest":value["qualification_digest"],
        "artifact_digest":artifact["content_digest"],
        "authority_effect":"NONE",
        "execution_effect":"NONE",
    }
