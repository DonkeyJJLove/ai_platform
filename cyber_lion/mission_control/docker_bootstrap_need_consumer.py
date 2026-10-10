"""Source-bound consumer of an R7 Docker capability need.

This is a typed adapter to the existing R24 one-shot
DockerFleetBootstrapExecutor; it is NOT an admission issuer, scheduler,
materializer, or independent execution service. It can reach an external
effect only through the original RuntimeAdmission/LiveAuthority boundary.
All sources are injected by a trusted host composition root, never
provided by model output or a browser request.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from cyber_lion.contracts.runtime_enforcement import (
    RuntimeAdmission, RequestedRuntimeEffect, RuntimeIdentityBinding,
)
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority
from cyber_lion.mission_control.docker_fleet_bootstrap_executor import (
    ACTION, RESOURCE, DockerFleetBootstrapError,
    DockerFleetBootstrapExecutor, EXECUTOR_ID,
)
from cyber_lion.mission_control.docker_local_fleet_plan import deterministic_fleet_plan

SCHEMA = "lion.docker-bootstrap-need-consumer/v1"
NEED_SCHEMA = "lion.lpcl-runtime-capability-need/v1"
WAIT_GATES = frozenset({
    "DOCKER_FLEET_CURRENTNESS_REQUIRED",
    "DOCKER_FLEET_SOURCE_CURRENTNESS_DRIFT",
})
NEED_KEYS = frozenset({
    "schema","mission_id","source_head","source_tree","lpcl_digest",
    "material_runtime","logical_target","material_target","runtime_resource",
    "required_capability_class","effect_class","required_admission","gate",
    "authority_effect","runtime_effect",
})
ENVELOPE_KEYS = frozenset({
    "event","need","need_digest","operator_activation_preserved",
    "authority_effect",
})
_SHA40 = frozenset("0123456789abcdef")


class DockerBootstrapNeedError(ValueError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise DockerBootstrapNeedError(reason)


def _digest(value: Mapping[str,Any]) -> str:
    return sha256(
        json.dumps(dict(value),sort_keys=True,separators=(",",":"),
                   ensure_ascii=False,allow_nan=False).encode("utf-8")
    ).hexdigest()


def _sha40(value: Any) -> bool:
    return type(value) is str and len(value)==40 and set(value)<=_SHA40


def _sha64(value: Any) -> bool:
    return type(value) is str and len(value)==64 and set(value)<=_SHA40


def verified_durable_need(
    mission: Mapping[str,Any],
    current_source: Mapping[str,str],
) -> dict[str,Any]:
    """Verify the exact persisted R7 need and independent HEAD/TREE.

    The message is still a capability demand, never evidence of authority.
    A missing or compacted journal record fails closed; client-supplied
    active mission identity cannot create or replace the canonical record.
    """
    _require(isinstance(mission,Mapping),"CANONICAL_MISSION_REQUIRED")
    _require(isinstance(current_source,Mapping),"INDEPENDENT_SOURCE_REQUIRED")
    mid=mission.get("mission_id")
    _require(type(mid) is str and 1<=len(mid)<=128,"MISSION_IDENTITY_INVALID")
    _require(_sha40(mission.get("source_head")) and _sha40(mission.get("source_tree"))
             and _sha64(mission.get("spec_digest")),"REGISTERED_SOURCE_INVALID")
    _require(
        current_source.get("head")==mission["source_head"]
        and current_source.get("tree")==mission["source_tree"],
        "INDEPENDENT_SOURCE_DRIFT",
    )
    _require(mission.get("state") in {"AUTHORIZED","RUNNING"}
             and mission.get("runtime_state")=="DOCKER_FLEET_WAITING_FOR_ADMISSION"
             and mission.get("adapter") in (None,"LPCL_MISSION"),
             "ACTIVATED_DOCKER_MISSION_REQUIRED")
    _require(int(mission.get("materialized") or 0)==0
             and int(mission.get("ready") or 0)==0,
             "MATERIAL_COHORT_ALREADY_BOUND")
    process=mission.get("process") or {}
    _require(isinstance(process,Mapping)
             and process.get("authority_state")=="EXPLICIT_USER_ACTIVATION",
             "OPERATOR_ACTIVATION_REQUIRED")
    driver=mission.get("execution_driver") or {}
    _require(
        isinstance(driver,Mapping)
        and driver.get("state")=="WAITING"
        and driver.get("blocking_gate") in WAIT_GATES
        and driver.get("next_action")=="WAIT_FOR_ADMITTED_DOCKER_FLEET"
        and driver.get("lease_owner") is None,
        "DURABLE_RUNTIME_WAIT_DRIVER_REQUIRED",
    )
    _require(type(driver.get("generation")) is int and driver["generation"]>=1,
             "DRIVER_GENERATION_INVALID")
    messages=mission.get("protocol_messages")
    _require(type(messages) is list,"CANONICAL_MESSAGE_READBACK_REQUIRED")
    matching=[
        r for r in messages
        if isinstance(r,Mapping)
        and isinstance(r.get("payload"),Mapping)
        and r["payload"].get("event")=="DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED"
    ]
    _require(bool(matching),"CANONICAL_NEED_MISSING")
    ids=[r.get("id") for r in matching]
    _require(
        all(type(value) is int and value>=1 for value in ids)
        and len(set(ids))==len(ids),
        "CANONICAL_NEED_MESSAGE_ORDER_INVALID",
    )
    matching.sort(key=lambda r:r["id"],reverse=True)
    # A changed WAIT gate can legitimately create a successor demand record.
    # Treat its highest canonical message id as current, and reject any
    # historical envelope that has been substituted or tampered with.
    for historical in matching[1:]:
        p=historical.get("payload") or {}
        n=p.get("need") if isinstance(p,Mapping) else None
        _require(
            historical.get("protocol")=="CONTROL"
            and historical.get("from_id")=="GLOBAL_MISSION_SCHEDULER_V1"
            and historical.get("to_id")=="MISSION_CONTROL"
            and historical.get("direction")=="INTERNAL"
            and historical.get("phase") is None
            and isinstance(p,dict)
            and set(p)==ENVELOPE_KEYS
            and p.get("event")=="DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED"
            and p.get("operator_activation_preserved") is True
            and p.get("authority_effect")=="NONE"
            and _sha64(historical.get("payload_digest"))
            and _digest(p)==historical["payload_digest"]
            and type(n) is dict and set(n)==NEED_KEYS
            and _sha64(p.get("need_digest"))
            and _digest(n)==p["need_digest"]
            and n["gate"] in WAIT_GATES
            and n["mission_id"]==mid
            and n["source_head"]==mission["source_head"]
            and n["source_tree"]==mission["source_tree"]
            and n["lpcl_digest"]==mission["spec_digest"]
            and n["authority_effect"]=="NONE"
            and n["runtime_effect"]=="NONE",
            "HISTORICAL_NEED_JOURNAL_DRIFT",
        )
    row=matching[0]
    _require(
        row.get("protocol")=="CONTROL"
        and row.get("from_id")=="GLOBAL_MISSION_SCHEDULER_V1"
        and row.get("to_id")=="MISSION_CONTROL"
        and row.get("direction")=="INTERNAL"
        and row.get("phase") is None,
        "CANONICAL_NEED_MESSAGE_ROUTE_INVALID",
    )
    envelope=row["payload"]
    _require(set(envelope)==ENVELOPE_KEYS
             and envelope["event"]=="DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED"
             and envelope["operator_activation_preserved"] is True
             and envelope["authority_effect"]=="NONE",
             "CANONICAL_NEED_ENVELOPE_INVALID")
    _require(_sha64(row.get("payload_digest"))
             and _digest(envelope)==row["payload_digest"],
             "CANONICAL_MESSAGE_DIGEST_DRIFT")
    need=envelope.get("need")
    _require(type(need) is dict and set(need)==NEED_KEYS,
             "DOCKER_BOOTSTRAP_NEED_SCHEMA_DRIFT")
    _require(_sha64(envelope.get("need_digest"))
             and _digest(need)==envelope["need_digest"],
             "DOCKER_BOOTSTRAP_NEED_DIGEST_DRIFT")
    _require(
        need["schema"]==NEED_SCHEMA
        and need["mission_id"]==mid
        and need["source_head"]==mission["source_head"]
        and need["source_tree"]==mission["source_tree"]
        and need["lpcl_digest"]==mission["spec_digest"]
        and need["material_runtime"]=="DOCKER_LOCAL_MODEL"
        and type(need["logical_target"]) is int
        and need["logical_target"]==mission.get("logical_count")
        and type(need["material_target"]) is int
        and need["material_target"]==mission.get("material_target")==32
        and need["runtime_resource"]==RESOURCE
        and need["required_capability_class"]==ACTION
        and need["effect_class"]=="BOUNDED_MATERIAL"
        and need["required_admission"]=="CANONICAL_RUNTIME_ADMISSION_AND_EXPLICIT_LPCL"
        and need["gate"]==driver["blocking_gate"]
        and need["authority_effect"]=="NONE"
        and need["runtime_effect"]=="NONE",
        "DOCKER_BOOTSTRAP_NEED_SUBSTITUTION",
    )
    _require(not mission.get("workers"),"MATERIAL_COHORT_ALREADY_BOUND")
    return {
        "schema":SCHEMA,"mission_id":mid,"need":dict(need),
        "need_digest":envelope["need_digest"],
        "message_digest":row["payload_digest"],
        "driver_generation":driver["generation"],
        "authority_effect":"NONE","runtime_effect":"NONE",
    }


@dataclass(frozen=True)
class AdmittedDockerBootstrapInputs:
    """Only the existing canonical issuer can supply these exact receipts."""
    admission: RuntimeAdmission
    effect: RequestedRuntimeEffect
    identity: RuntimeIdentityBinding
    authority: LiveAdmittedAuthority
    execution_id: str

    def validate(self) -> "AdmittedDockerBootstrapInputs":
        _require(type(self.admission) is RuntimeAdmission,
                 "EXACT_ADMISSION_REQUIRED")
        _require(type(self.effect) is RequestedRuntimeEffect,
                 "EXACT_REQUESTED_EFFECT_REQUIRED")
        _require(type(self.identity) is RuntimeIdentityBinding,
                 "EXACT_RUNTIME_IDENTITY_REQUIRED")
        _require(type(self.authority) is LiveAdmittedAuthority,
                 "EXACT_LIVE_AUTHORITY_REQUIRED")
        for item in (self.admission,self.effect,self.identity,self.authority):
            item.validate()
        _require(type(self.execution_id) is str
                 and 1<=len(self.execution_id)<=256,
                 "EXECUTION_ID_REQUIRED")
        return self


class DockerBootstrapNeedConsumer:
    """Existing source-bound effect boundary, not a new scheduler.

    The trusted host composition root supplies a current mission snapshot,
    independent current source and independently-issued runtime admission.
    Admission absence returns WAITING; never fabricate PDP or grant evidence.
    """
    def __init__(
        self, *,
        snapshot_source: Callable[[str],Mapping[str,Any]],
        current_source: Callable[[],Mapping[str,str]],
        admission_source: Callable[[str,str,str],AdmittedDockerBootstrapInputs|None],
        executor: DockerFleetBootstrapExecutor,
    ) -> None:
        _require(callable(snapshot_source) and callable(current_source)
                 and callable(admission_source),"TRUSTED_SOURCE_CALLBACK_REQUIRED")
        _require(type(executor) is DockerFleetBootstrapExecutor,
                 "CANONICAL_DOCKER_EXECUTOR_REQUIRED")
        self.snapshot_source=snapshot_source
        self.current_source=current_source
        self.admission_source=admission_source
        self.executor=executor

    def advance(self, mission_id: str) -> dict[str,Any]:
        snapshot=self.snapshot_source(mission_id)
        basis=verified_durable_need(snapshot,self.current_source())
        mid=basis["mission_id"]
        source_mission=self.executor.mission_source(mid)
        _require(isinstance(source_mission,Mapping),"CANONICAL_LPCL_REQUIRED")
        _require(
            source_mission.get("mission_id")==mid
            and source_mission.get("source_head")==basis["need"]["source_head"]
            and source_mission.get("source_tree")==basis["need"]["source_tree"]
            and source_mission.get("spec_digest")==basis["need"]["lpcl_digest"]
            and source_mission.get("state") in {"AUTHORIZED","RUNNING"}
            and (source_mission.get("process") or {}).get("authority_state")
            == "EXPLICIT_USER_ACTIVATION"
            and (source_mission.get("operator_control") or {}).get("autonomy_allowed")
            is True,
            "CANONICAL_MISSION_IDENTITY_OR_FENCE_DRIFT",
        )
        # The existing R24 reader validates precisely 32 configured workers
        # and the sandbox mount policy. It cannot issue an external effect.
        compose=self.executor.runtime.compose_config()
        plan=deterministic_fleet_plan(source_mission,compose)
        _require(
            plan["mission_id"]==mid
            and plan["source_head"]==basis["need"]["source_head"]
            and plan["source_tree"]==basis["need"]["source_tree"]
            and plan["lpcl_digest"]==basis["need"]["lpcl_digest"]
            and plan["material_count"]==basis["need"]["material_target"]
            and plan["logical_count"]==basis["need"]["logical_target"],
            "PREPARED_BOOTSTRAP_PLAN_DRIFT",
        )
        # Old R24 identity/receipt divergence must stop *before* admission
        # lookup, not just inside a started effect or after consuming a token.
        try:
            identity,receipt=self.executor.runtime.identity_and_receipt()
        except DockerFleetBootstrapError as exc:
            return {
                "schema":SCHEMA,"state":"WAITING_PREPARED_RUNTIME",
                "gate":str(exc)[:160],"mission_id":mid,
                "need_digest":basis["need_digest"],
                "plan_digest":plan["plan_digest"],
                "effect_applied":False,"authority_effect":"NONE",
            }
        _require(
            identity.get("source_head")==plan["source_head"]
            and identity.get("source_tree")==plan["source_tree"]
            and receipt.get("source_head")==identity.get("source_head")
            and receipt.get("identity_digest")==identity.get("identity_digest"),
            "PREPARED_RUNTIME_SOURCE_OR_RECEIPT_DRIFT",
        )
        evidence=self.admission_source(mid,basis["need_digest"],plan["plan_digest"])
        if evidence is None:
            return {
                "schema":SCHEMA,"state":"WAITING_RUNTIME_ADMISSION",
                "mission_id":mid,"need_digest":basis["need_digest"],
                "plan_digest":plan["plan_digest"],
                "effect_applied":False,"authority_effect":"NONE",
            }
        _require(type(evidence) is AdmittedDockerBootstrapInputs,
                 "CANONICAL_ADMISSION_ENVELOPE_REQUIRED")
        evidence.validate()
        effect=evidence.effect
        _require(
            effect.mission_id==mid
            and effect.action_class==ACTION
            and effect.resource==RESOURCE
            and effect.payload_digest==plan["plan_digest"]
            and effect.runtime_identity_digest==evidence.identity.digest()
            and evidence.identity.execution_subject==EXECUTOR_ID
            and evidence.identity.workload_identity==EXECUTOR_ID
            and evidence.admission.requested_effect_digest==effect.digest()
            and evidence.admission.live_authority_digest==evidence.authority.digest()
            and evidence.authority.mission_id==mid,
            "RUNTIME_ADMISSION_OR_EFFECT_SCOPE_DRIFT",
        )
        # Close the gap between selecting an admission and entering the
        # original effect boundary. No admission can be consumed if the
        # operator removed or changed this WAIT in the meantime.
        latest=verified_durable_need(
            self.snapshot_source(mid),self.current_source()
        )
        _require(
            latest["need_digest"]==basis["need_digest"]
            and latest["message_digest"]==basis["message_digest"]
            and latest["driver_generation"]==basis["driver_generation"],
            "DURABLE_RUNTIME_NEED_CHANGED_PRE_EFFECT",
        )
        # The unchanged original executor independently revalidates canonical
        # runtime admission, authority, source, inventory and one-shot consume.
        result=self.executor.execute(
            plan=plan,admission=evidence.admission,effect=effect,
            runtime_identity=evidence.identity,
            admitted_authority=evidence.authority,
            execution_id=evidence.execution_id,
        )
        _require(result.get("result") in {
            "OBSERVED","ALREADY_SOURCE_BOUND_READY","EFFECT_UNKNOWN_RECONCILE",
        },"UNRECOGNIZED_DOCKER_EFFECT_RESULT")
        return {
            "schema":SCHEMA,
            "state":"RECONCILE_EFFECT" if result["result"]=="EFFECT_UNKNOWN_RECONCILE"
                    else "OBSERVED_BY_ORIGINAL_EXECUTOR",
            "mission_id":mid,"need_digest":basis["need_digest"],
            "plan_digest":plan["plan_digest"],
            "original_result":result,
            "effect_applied":result.get("effect_applied"),
            "effect_receipt_sha256":result.get("receipt_sha256"),
            "execution_effect":(
                "ALREADY_ADMITTED_BOUNDED_MATERIAL_EFFECT"
                if result.get("effect_applied") is True else "NONE"
            ),
            "authority_effect":"NONE",
        }
