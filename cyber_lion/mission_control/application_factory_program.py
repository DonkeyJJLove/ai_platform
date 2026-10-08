"""Author the first cross-model LION application-factory mission from one spec.

The module emits two non-effectful representations of the same phase contracts:
1) the current Mission Control panel LPCL/1.2 key/value profile;
2) the canonical RUN/PHASE LPCL 1.2 surface.

Both are compiled and their PhaseExecutionContract payloads must be identical.
This module registers or activates nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable

from cyber_lion.contracts.phase_execution_contract import (
    compile_panel_phase_contracts,
    preflight_execution_contracts,
)
from cyber_lion.process_language.canonical_run import compile_canonical_run

MISSION_ID="LION-APPLICATION-FACTORY-CROSS-MODEL-R1"
TITLE="LION Application Factory · Cross-Model Artifact R1"
OBJECTIVE=(
    "Create and independently verify one useful artifact whose source lineage binds "
    "independent LOCAL trajectories and a responded SaaS advisory."
)
DESCRIPTION=(
    "Finite application-factory proof. Cross-model reconnaissance and one-worker "
    "preactivation run before the unchanged full-fleet provider readiness gate. "
    "A separately authorized deployment may occur while the mission waits at that gate."
)
LOGICAL_COUNT=4
MATERIAL_TARGET=32
MATERIAL_RUNTIME="DOCKER_LOCAL_MODEL"
PROTOCOLS=(
    "LPCL","AUTHORITY","CURRENTNESS","ASSIGNMENT","EVIDENCE","VALIDATION",
    "RECEIPT","RECOVERY","CONTROL","BROKER","THREAD","TRANSPORT","LINEAGE",
)


class ApplicationFactoryProgramError(ValueError):
    pass


@dataclass(frozen=True)
class PhaseSpec:
    phase_id:str
    title:str
    execution_class:str
    capability_classes:tuple[str,...]
    effect_ceiling:str
    currentness:tuple[str,...]
    evidence:tuple[str,...]
    completion:str
    role:str
    transition_class:str="INTERNAL"
    operator:str="VERIFY"
    idempotency_class:str="PURE"
    replay_policy:str="DENY"
    authority_requirements:tuple[str,...]=()
    write_scopes:tuple[str,...]=()

    def validate(self)->"PhaseSpec":
        if not self.phase_id or not self.title:
            raise ApplicationFactoryProgramError("phase identity")
        if not self.capability_classes or not self.currentness or not self.evidence:
            raise ApplicationFactoryProgramError("phase evidence/currentness/capability")
        if "=" not in self.completion:
            raise ApplicationFactoryProgramError("phase completion predicate")
        if self.transition_class=="ACTION_REQUIRED":
            if self.operator!="EMIT_ACTION_INTENT" or not self.authority_requirements:
                raise ApplicationFactoryProgramError("action-required phase contract")
        elif self.operator=="EMIT_ACTION_INTENT":
            raise ApplicationFactoryProgramError("internal phase cannot emit action intent")
        return self


PHASES=(
    PhaseSpec(
        phase_id="CROSS_MODEL_RECON",
        title="Acquire Independent LOCAL And SaaS Intelligence",
        execution_class="COGNITIVE",
        capability_classes=("CONTROL_PLANE_RECONNAISSANCE",),
        effect_ceiling="NONE",
        currentness=("RECON_EVIDENCE_SET","CURRENT_BROKER_DB","LIVE_8780_RUNTIME","LOCAL_MODEL_IDENTITY"),
        evidence=("INTELLIGENCE_BUNDLE","TRANSPORT_CLASSIFICATION","MODEL_ENDPOINT"),
        completion="CROSS_MODEL_INTELLIGENCE_BOUND=PASS",
        role="ANALYST",
        operator="RECONCILE",
    ),
    PhaseSpec(
        phase_id="PREACTIVATE_BUILDER",
        title="Qualify One Builder Without Artifact Effect",
        execution_class="VALIDATE",
        capability_classes=("COOPERATIVE_WORKER_PREACTIVATION",),
        effect_ceiling="NONE",
        currentness=("MISSION_CONTROL_DB","RECON_EVIDENCE_SET"),
        evidence=("CONTROL_PLANE_INTELLIGENCE_BUNDLE_READBACK","RESTART_DURABILITY"),
        completion="COOPERATIVE_WORKER_QUALIFIED=PASS",
        role="PREACTIVATOR",
        operator="VERIFY",
    ),
    PhaseSpec(
        phase_id="FULL_FLEET_PROVIDER_READINESS",
        title="Wait For Canonical Cooperative Provider On Full Fleet",
        execution_class="VERIFY",
        capability_classes=("COOPERATIVE_ARTIFACT_BOOTSTRAP",),
        effect_ceiling="NONE",
        currentness=("LIVE_DOCKER_FLEET","LOCAL_MODEL_IDENTITY"),
        evidence=("DOCKER_HEARTBEATS","UNIQUE_CONTAINER_IDS"),
        completion="COOPERATIVE_PROVIDER_READY=PASS",
        role="PREACTIVATOR",
        operator="VERIFY",
    ),
    PhaseSpec(
        phase_id="BUILD_CROSS_MODEL_ARTIFACT",
        title="Build Material Artifact From Cross-Model Evidence",
        execution_class="MUTATE",
        capability_classes=("COOPERATIVE_ARTIFACT_PRODUCTION",),
        effect_ceiling="BOUNDED_MATERIAL",
        currentness=("LIVE_DOCKER_FLEET","CURRENT_BROKER_DB"),
        evidence=("INTELLIGENCE_BUNDLE","RESTART_DURABILITY"),
        completion="COOPERATIVE_ARTIFACT_WRITTEN=PASS",
        role="BUILDER",
        transition_class="ACTION_REQUIRED",
        operator="EMIT_ACTION_INTENT",
        idempotency_class="NON_IDEMPOTENT",
        replay_policy="RECONCILE_FIRST",
        authority_requirements=("authority-context:local-write",),
        write_scopes=("artifact:LION-APPLICATION-FACTORY-CROSS-MODEL-R1",),
    ),
    PhaseSpec(
        phase_id="VERIFY_CROSS_MODEL_ARTIFACT",
        title="Independently Verify Artifact Bytes",
        execution_class="VERIFY",
        capability_classes=("COOPERATIVE_ARTIFACT_VERIFY",),
        effect_ceiling="NONE",
        currentness=("LIVE_DOCKER_FLEET",),
        evidence=("STATE_DIFF","RESTART_DURABILITY"),
        completion="COOPERATIVE_ARTIFACT_VERIFIED=PASS",
        role="VERIFIER",
        operator="VERIFY",
    ),
)


def _csv(values:Iterable[str])->str:
    return ",".join(values)


def panel_lpcl_text()->str:
    lines=[
        f"RUN={MISSION_ID}",
        "PROJECT=LION_EVOLUSION",
        "MODE=AUTONOMOUS_EXECUTE",
        "CONTROL_LANGUAGE=LPCL/1.2",
        f"MISSION_ID={MISSION_ID}",
        f"MISSION_TITLE={TITLE}",
        f"MISSION_OBJECTIVE={OBJECTIVE}",
        f"MISSION_DESCRIPTION={DESCRIPTION}",
        f"LOGICAL_DRONE_COUNT={LOGICAL_COUNT}",
        f"MATERIAL_DRONE_COUNT={MATERIAL_TARGET}",
        f"MATERIAL_RUNTIME={MATERIAL_RUNTIME}",
        "DEPLOYMENT_BOUNDARY=AFTER_PREACTIVATE_BEFORE_FULL_FLEET_PROVIDER_READINESS",
        "DEPLOYMENT_AUTHORITY=SEPARATE_CURRENT_DEPLOYMENT_AUTHORITY_REQUIRED",
        "BUILDER_WORKER=MD001",
        "VERIFIER_WORKER=MD002",
        "PREACTIVATION_WORKER=MD001",
        "PROTOCOLS="+_csv(PROTOCOLS),
    ]
    for index,phase in enumerate(PHASES,1):
        phase.validate()
        p=f"PHASE_{index:02d}"
        lines.extend((
            f"{p}={phase.phase_id}|{phase.title}",
            f"{p}_EXECUTION_CLASS={phase.execution_class}",
            f"{p}_CAPABILITY_CLASS={_csv(phase.capability_classes)}",
            f"{p}_EFFECT_CEILING={phase.effect_ceiling}",
            f"{p}_BINDING_MODE=DYNAMIC",
            f"{p}_ON_MISSING_CAPABILITY=WAIT_AND_DISCOVER",
            f"{p}_AUTO_RESUME=TRUE",
            f"{p}_VERIFY_BEFORE_MUTATE=TRUE",
            f"{p}_CURRENTNESS={_csv(phase.currentness)}",
            f"{p}_EVIDENCE={_csv(phase.evidence)}",
            f"{p}_COMPLETION_01={phase.completion}",
        ))
    return "\n".join(lines)+"\n"


def _block(key:str,values:Iterable[str])->list[str]:
    vals=tuple(values)
    if not vals:
        return [key+"="]
    return [key+"=",*vals,""]


def canonical_run_text(source_head:str,source_tree:str)->str:
    if len(source_head)!=40 or len(source_tree)!=40:
        raise ApplicationFactoryProgramError("source identity")
    lines=[
        f"RUN={MISSION_ID}",
        "PROCESS_LANGUAGE=LPCL",
        "LPCL_VERSION=1.2",
        "MISSION_CLASS=HYBRID_FLEET_MISSION",
        f"MISSION_ID={MISSION_ID}",
        "PRIMARY_GOAL=",
        "CREATE_ONE_CROSS_MODEL_BOUND_ARTIFACT",
        "VERIFY_EXACT_ARTIFACT_BYTES",
        "",
        "SCOPE_DOMAINS=",
        "repository",
        "runtime",
        "conversation",
        "evidence",
        "artifact",
        "",
        "SCOPE_RESOURCES=",
        "repo:DonkeyJJLove/ai_platform",
        "runtime:MOON",
        "mission:"+MISSION_ID,
        "",
        "WIDENING_ALLOWED=FALSE",
        "LOGICAL_FLEET_ROLES=",
        "ANALYST",
        "",
        "LOCAL_FLEET_ROLES=",
        "PREACTIVATOR",
        "BUILDER",
        "VERIFIER",
        "",
        "ROLE_SEPARATION=",
        "BUILDER!=VERIFIER",
        "",
        "MAX_WIP=1",
        "ON_UNKNOWN=HANDOFF",
        "TERMINATION=COMPLETE_ON_DONE",
        "AUTHORITY_EFFECT=NONE",
        "RUNTIME_EFFECT=NONE",
        "LINEAGE=",
        "source-head:"+source_head,
        "source-tree:"+source_tree,
        "panel-lpcl-sha256:"+sha256(panel_lpcl_text().encode("utf-8")).hexdigest(),
        "",
    ]
    for idx,phase in enumerate(PHASES):
        phase.validate()
        lines.extend((f"PHASE_{idx}=",phase.phase_id,""))
        lines.extend((f"TRANSITION_CLASS=",phase.transition_class,""))
        lines.extend((f"OPERATOR=",phase.operator,""))
        lines.extend((f"ROLE=",phase.role,""))
        lines.extend(_block("EVIDENCE_REQUIREMENTS",("evidence:"+phase.phase_id.lower(),)))
        lines.extend(_block("CURRENTNESS_REQUIREMENTS",("currentness:"+phase.phase_id.lower(),)))
        lines.extend(_block("AUTHORITY_REQUIREMENTS",phase.authority_requirements))
        lines.extend(_block("EXPECTED_POSTCONDITIONS",("postcondition:"+phase.phase_id.lower(),)))
        lines.extend((f"REPLAY_POLICY=",phase.replay_policy,""))
        lines.extend((f"IDEMPOTENCY_CLASS=",phase.idempotency_class,""))
        lines.extend(("RETRY_MAX_ATTEMPTS=","0",""))
        lines.extend(("RETRY_ON_EXHAUSTED=","HANDOFF",""))
        if phase.write_scopes:
            lines.extend(_block("WRITE_SCOPES",phase.write_scopes))
        lines.extend(("EXECUTION_CLASS=",phase.execution_class,""))
        lines.extend(_block("CAPABILITY_CLASS",phase.capability_classes))
        lines.extend(("EFFECT_CEILING=",phase.effect_ceiling,""))
        lines.extend(("BINDING_MODE=","DYNAMIC",""))
        lines.extend(("ON_MISSING_CAPABILITY=","WAIT_AND_DISCOVER",""))
        lines.extend(("AUTO_RESUME=","TRUE",""))
        lines.extend(("VERIFY_BEFORE_MUTATE=","TRUE",""))
        lines.extend(_block("CURRENTNESS_CONTRACT",phase.currentness))
        lines.extend(_block("EVIDENCE_CONTRACT",phase.evidence))
        lines.append("COMPLETION="+phase.completion)
        lines.append("")
    lines.append("END")
    return "\n".join(lines)+"\n"


def phase_rows()->list[dict[str,str]]:
    return [{"id":phase.phase_id,"title":phase.title} for phase in PHASES]


def panel_contracts():
    text=panel_lpcl_text()
    pairs={}
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        key,sep,value=raw.partition("=")
        if not sep or key in pairs:
            raise ApplicationFactoryProgramError("panel LPCL key/value syntax")
        pairs[key]=value
    return compile_panel_phase_contracts(
        pairs,MISSION_ID,phase_rows(),"LPCL/1.2"
    )


def canonical_compilation(source_head:str,source_tree:str):
    return compile_canonical_run(canonical_run_text(source_head,source_tree))


def _contract_core(contract)->dict[str,Any]:
    value=contract.as_dict()
    return {
        key:value[key] for key in (
            "phase_id","ordinal","execution_class","capability_classes",
            "effect_ceiling","binding_mode","on_missing_capability","auto_resume",
            "verify_before_mutate","currentness_requirements",
            "evidence_requirements","completion_predicates","contract_source",
            "contract_version","compiler_version","contract_digest",
        )
    }


def validate_semantic_equivalence(source_head:str,source_tree:str)->dict[str,Any]:
    panel=tuple(panel_contracts())
    canonical=tuple(canonical_compilation(source_head,source_tree).phase_execution_contracts)
    if len(panel)!=len(canonical):
        raise ApplicationFactoryProgramError("phase contract count drift")
    for left,right in zip(panel,canonical):
        if _contract_core(left)!=_contract_core(right):
            raise ApplicationFactoryProgramError(
                "panel/canonical phase contract drift:"+left.phase_id
            )
    preflight=preflight_execution_contracts(panel,{})
    return {
        "schema":"lion.application-factory-program-validation/v1",
        "mission_id":MISSION_ID,
        "phase_count":len(panel),
        "panel_lpcl_digest":sha256(panel_lpcl_text().encode("utf-8")).hexdigest(),
        "canonical_run_digest":sha256(canonical_run_text(source_head,source_tree).encode("utf-8")).hexdigest(),
        "contract_digests":[item.contract_digest for item in panel],
        "semantic_equivalence":"PASS",
        "preflight_without_runtime_registry":preflight.as_dict(),
        "authority_effect":"NONE",
        "execution_effect":"NONE",
    }


def capability_preflight_profiles()->dict[str,Any]:
    from cyber_lion.mission_control import cooperative_preactivation as pre
    from cyber_lion.mission_control import cooperative_production as cp
    from cyber_lion.mission_control import control_plane_reconnaissance as recon

    contracts=panel_contracts()
    recon_cap={
        "capability_id":recon.CAPABILITY_ID,
        "executor_id":"MISSION_CONTROL_CONTROL_PLANE_RECONCILER",
        "effect_ceiling":"NONE",
        "mode":"READ_ONLY_RECON",
    }
    predeployment={
        "CONTROL_PLANE_RECONNAISSANCE":(recon_cap,),
        **pre.capability_registry_entries(),
        cp.CAPABILITY_BOOTSTRAP:cp.capability_registry_entries()[cp.CAPABILITY_BOOTSTRAP],
    }
    full=dict(predeployment)
    full[cp.CAPABILITY_PRODUCTION]=cp.capability_registry_entries()[cp.CAPABILITY_PRODUCTION]
    full[cp.CAPABILITY_VERIFY]=cp.capability_registry_entries()[cp.CAPABILITY_VERIFY]
    return {
        "no_runtime_registry":preflight_execution_contracts(contracts,{}).as_dict(),
        "preactivation_ready_production_unbound":preflight_execution_contracts(
            contracts,predeployment
        ).as_dict(),
        "full_cooperative_runtime_ready":preflight_execution_contracts(
            contracts,full
        ).as_dict(),
    }


def mission_program_manifest(source_head:str,source_tree:str)->dict[str,Any]:
    validation=validate_semantic_equivalence(source_head,source_tree)
    profiles=capability_preflight_profiles()
    return {
        "schema":"lion.application-factory-mission-program/v1",
        "mission_id":MISSION_ID,
        "classification":"CURRENT_SOURCE_SUCCESSOR_CANDIDATE_NOT_REGISTERED_NOT_ACTIVATED",
        "source_parent":{"head":source_head,"tree":source_tree},
        "panel_lpcl_digest":validation["panel_lpcl_digest"],
        "canonical_run_digest":validation["canonical_run_digest"],
        "phase_contract_digests":validation["contract_digests"],
        "phases":[
            {
                "id":phase.phase_id,
                "title":phase.title,
                "execution_class":phase.execution_class,
                "capability_classes":list(phase.capability_classes),
                "effect_ceiling":phase.effect_ceiling,
                "completion":phase.completion,
            }
            for phase in PHASES
        ],
        "cross_model_source":{
            "recon_phase":"CROSS_MODEL_RECON",
            "required_local_trajectories":True,
            "required_saas_response":True,
            "intelligence_artifact":"CONTROL_PLANE_INTELLIGENCE_BUNDLE",
            "artifact_generation_binds_exact_bundle_digest":True,
        },
        "deployment_boundaries":{
            "prerequisite_source_deployment":{
                "required":True,
                "reason":"R6.18-R6.23 source and pinned process/preactivation providers must exist in the deployed runtime before this mission can execute.",
                "inside_mission":False,
                "authority_requirement":"SEPARATE_CURRENT_DEPLOYMENT_AUTHORITY_REQUIRED",
            },
            "post_preactivation_fleet_activation":{
                "required":True,
                "after_phase":"PREACTIVATE_BUILDER",
                "before_phase":"FULL_FLEET_PROVIDER_READINESS",
                "inside_mission":False,
                "authority_requirement":"SEPARATE_CURRENT_DEPLOYMENT_AUTHORITY_REQUIRED",
            },
        },
        "capability_preflights":profiles,
        "registration":{
            "performed":False,
            "activation_performed":False,
            "exact_payload_rule":"REGENERATE_REGISTRATION_PAYLOAD_FROM_DEPLOYED_CURRENT_HEAD_TREE_IMMEDIATELY_BEFORE_REGISTRATION",
            "preview_source_identity_only":True,
        },
        "authority_effect":"NONE",
        "execution_effect":"NONE",
    }


def registration_payload(source_head:str,source_tree:str)->dict[str,Any]:
    validation=validate_semantic_equivalence(source_head,source_tree)
    text=panel_lpcl_text()
    return {
        "mission_id":MISSION_ID,
        "title":TITLE,
        "objective":OBJECTIVE,
        "description":DESCRIPTION,
        "lpcl_digest":validation["panel_lpcl_digest"],
        "lpcl_text":text,
        "source_head":source_head,
        "source_tree":source_tree,
        "logical_count":LOGICAL_COUNT,
        "material_target":MATERIAL_TARGET,
        "phases":phase_rows(),
        "protocols":list(PROTOCOLS),
    }
