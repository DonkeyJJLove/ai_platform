"""Explicit migration profiles for legacy LPCL missions.

Profiles convert known historical LPCL/1.1 phase intent into explicit
PhaseExecutionContract objects. They are semantic migrations only: they do not
mint authority, execute effects, or mark phases complete.
"""
from __future__ import annotations

from .phase_execution_contract import PhaseExecutionContract, migrated_explicit_contract

GENERIC_ADAPTER_REPAIR_MISSION = "LION-GENERIC-LPCL-MISSION-EXECUTION-ADAPTER-REPAIR-R1"
POST_ASTRA_MISSION = "LION-POST-ASTRA-SAAS-TRANSPORT-TRUTH-REACQUIRE-R1"
SAAS_AUTOMATIC_MEDIATOR_MISSION = "LION-SAAS-AUTOMATIC-MEDIATOR-REAL-ROUNDTRIP-R1"
PROFILE_ID = "lion.mission-contract-profile/generic-adapter-repair-r1/v1"
POST_ASTRA_PROFILE_ID = "lion.mission-contract-profile/post-astra-transport-closure-r1/v1"

_COMMON_CURRENTNESS = (
    "CURRENT_MISSION_RUNTIME",
    "CURRENT_MATERIAL_BINDING",
    "CURRENT_PROCESS_CONTRACTS",
)
_COMMON_EVIDENCE = (
    "LIVE_RUNTIME_READBACK",
    "POSTCONDITION_RECONCILIATION",
    "DURABLE_RECEIPT",
)

_PHASES = {
    "REPAIR_EXECUTION_BINDER": dict(
        execution_class="VERIFY_THEN_REPAIR",
        capability_classes=("REPOSITORY_AND_RUNTIME_RECONCILIATION",),
        effect_ceiling="BOUNDED_REPOSITORY",
        currentness_requirements=("EXACT_CURRENT_REPOSITORY", "CURRENT_MISSION_RUNTIME", "CURRENT_MATERIAL_BINDING"),
        evidence_requirements=("LIVE_RUNTIME_READBACK", "FOCUSED_REGRESSION", "POSTCONDITION_RECONCILIATION"),
        completion_predicates=(
            "FRESH_LPCL_WITHOUT_PARENT=PASS","GENERIC_ADAPTER_BOUND=PASS","LOGICAL_COUNT_128=PASS",
            "MATERIAL_READY_64=PASS","UNIQUE_MATERIAL_64=PASS","GENERIC_PHASE_COMPILER=PASS",
            "GENERIC_PHASE_HANDLER=PASS","DURABLE_DRIVER=PASS","GLOBAL_SCHEDULER_DISPATCH=PASS",
            "LOCAL_PLANNING_RECEIPT=PASS","FAIL_CLOSED_MISSING_CAPABILITY=PASS","RESTART_DURABILITY=PASS","DB_INTEGRITY=PASS",
        ),
    ),
    "REPAIR_BASE_TOPOLOGY_BOOTSTRAP": dict(
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        completion_predicates=(
            "LOGICAL_COUNT_128=PASS","MATERIAL_READY_64=PASS","UNIQUE_MATERIAL_64=PASS",
            "TOPOLOGY_ASSIGNMENTS_128=PASS","TOPOLOGY_CANONICAL_IDS=PASS","TOPOLOGY_RATIO_2_TO_1=PASS",
            "TOPOLOGY_GENERIC_ROLES_16=PASS","DB_INTEGRITY=PASS",
        ),
    ),
    "IMPLEMENT_GENERIC_PHASE_COMPILER": dict(
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        completion_predicates=(
            "PHASE_SPEC_COUNT_MATCH=PASS","ALL_MISSION_PHASES_GENERIC_HANDLER=PASS",
            "LPCL12_COMPILER_AVAILABLE=PASS","PROCESS_CONTRACT_PREFLIGHT_VALID=PASS","DB_INTEGRITY=PASS",
        ),
    ),
    "IMPLEMENT_GENERIC_PHASE_HANDLER": dict(
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        completion_predicates=(
            "LOCAL_PLAN_ASSIGNMENT_AUTONOMOUS=PASS","LOCAL_PLAN_RECEIPT_PRESENT=PASS",
            "ACTION_IR_READ_ONLY_BOUNDARY=PASS","GENERIC_ACTION_RECEIPT_PRESENT=PASS",
            "CAPABILITY_FAIL_CLOSED_PROVEN=PASS","NO_RAW_MODEL_TO_SHELL=PASS","DB_INTEGRITY=PASS",
        ),
    ),
    "MATERIALIZE_DRIVER": dict(
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        completion_predicates=(
            "DRIVER_PRESENT=PASS","DRIVER_GENERATION_POSITIVE=PASS","DRIVER_CHECKPOINT_PRESENT=PASS",
            "DRIVER_CURRENT_PHASE_TRACKED=PASS","WAITING_LEASE_RELEASED=PASS","DB_INTEGRITY=PASS",
        ),
    ),
    "GLOBAL_SCHEDULER_ACCEPTANCE": dict(
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        completion_predicates=(
            "SCHEDULER_ACTIVE=PASS","MISSION_SCHEDULER_TURN_PRESENT=PASS","MISSION_DISPATCH_COUNT_POSITIVE=PASS",
            "AUTOMATIC_PHASE_ADVANCE_PROVEN=PASS","DB_INTEGRITY=PASS",
        ),
    ),
    "DYNAMIC_DELEGATION_ACCEPTANCE": dict(
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        completion_predicates=(
            "LOCAL_DELEGATION_PROVEN=PASS","MATERIAL_DELEGATION_PROVEN=PASS","DYNAMIC_CAPABILITY_BINDING_PROVEN=PASS",
            "SAAS_BROKER_AVAILABLE=PASS","SAAS_TRANSPORT_TRUTHFUL=PASS","DB_INTEGRITY=PASS",
        ),
    ),
    "RESTART_DURABILITY": dict(
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        completion_predicates=(
            "RESTART_BACKUP_PRESENT=PASS","DRIVER_SURVIVED_RESTART=PASS","NO_DUPLICATE_PHASE3_PLANNING=PASS",
            "NO_DUPLICATE_PHASE3_ACTION_RECEIPT=PASS","DB_INTEGRITY=PASS",
        ),
    ),
    "REAL_PANEL_MISSION_ACCEPTANCE": dict(
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        completion_predicates=(
            "PANEL_REGISTRATION_PROVEN=PASS","OPERATOR_ACTIVATION_PROVEN=PASS",
            "AUTONOMOUS_MULTI_PHASE_TRANSITION_PROVEN=PASS","GENERIC_ADAPTER_BOUND=PASS","DB_INTEGRITY=PASS",
        ),
    ),
    "RETRY_POST_ASTRA_SAAS_MISSION": dict(
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        currentness_requirements=("CURRENT_MISSION_RUNTIME","CURRENT_POST_ASTRA_MISSION","CURRENT_SAAS_BROKER_STATE"),
        evidence_requirements=("LIVE_RUNTIME_READBACK","POST_ASTRA_FAIL_CLOSED_READBACK","SAAS_TRANSPORT_CLASSIFICATION"),
        completion_predicates=(
            "POST_ASTRA_MISSION_EXISTS=PASS","POST_ASTRA_GENERIC_ADAPTER=PASS","POST_ASTRA_MATERIAL_READY_64=PASS",
            "POST_ASTRA_DRIVER_WAITING=PASS","POST_ASTRA_LOCAL_PLAN_RECEIPT=PASS","POST_ASTRA_FAIL_CLOSED_CAPABILITY_GATE=PASS",
            "SAAS_SESSION_MEDIATED_RECEIPT_EXISTS=PASS","SAAS_AUTOMATIC_HOP_NOT_CLAIMED=PASS","DB_INTEGRITY=PASS",
        ),
    ),
}


_POST_ASTRA_PHASES = (
    "REACQUIRE_LIVE_STATE",
    "REACQUIRE_PENDING_SAAS",
    "RECONSTRUCT_TRANSPORT_PATH",
    "IDENTIFY_AUTOMATIC_CONSUMER",
    "TRANSPORT_CAPABILITY_CLASSIFICATION",
    "BROKER_RUNTIME_RECONCILIATION",
    "PANEL_TRUTH_PROJECTION",
    "AUTONOMOUS_SAAS_TWO_QUERY_TEST",
    "FAIL_CLOSED_TRANSPORT_GATE",
    "MISSION_INDEPENDENCE_CHECK",
    "FULL_SAAS_PATH_VALIDATION",
    "RETURN_TO_LION_SCAFFOLD",
)

def _post_astra_contract(mission_id: str, phase_id: str, ordinal: int) -> PhaseExecutionContract | None:
    if mission_id != POST_ASTRA_MISSION or phase_id not in _POST_ASTRA_PHASES:
        return None
    return migrated_explicit_contract(
        mission_id=mission_id,
        phase_id=phase_id,
        ordinal=ordinal,
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        binding_mode="DYNAMIC",
        on_missing_capability="WAIT_AND_DISCOVER",
        auto_resume=True,
        verify_before_mutate=True,
        currentness_requirements=("CURRENT_POST_ASTRA_MISSION", "CURRENT_SAAS_BROKER_STATE", "CURRENT_CONTROL_PLANE_RECON_EVIDENCE"),
        evidence_requirements=("POST_ASTRA_PHASE_EVIDENCE", "DURABLE_RECEIPT"),
        completion_predicates=("POST_ASTRA_PHASE_EVIDENCE=PASS",),
    )



_SAAS_AUTOMATIC_MEDIATOR_PHASES = (
    "REACQUIRE_CANONICAL_SOURCE",
    "RECONSTRUCT_CURRENT_FAILURE",
    "DISCOVER_SUPPORTED_AUTOMATIC_TRANSPORTS",
    "CHATGPT_AUTOMATIC_INGRESS_FALSIFICATION",
    "TRANSPORT_DECISION_GATE",
    "MEDIATOR_PROTOCOL_CONTRACT",
    "SECRET_AND_IDENTITY_BOUNDARY",
    "IMPLEMENT_AUTOMATIC_MEDIATOR",
    "IMPLEMENT_MEDIATOR_SERVICE",
    "BROKER_CLAIM_AND_IDEMPOTENCY_HARDENING",
    "IMPLEMENT_PROVIDER_ADAPTER",
    "IMPLEMENT_PROVIDER_FAILURE_MODEL",
    "RESPONSE_RECEIPT_BINDING",
    "THREAD_DELIVERY_RECONCILIATION",
    "PANEL_TRANSPORT_PROJECTION",
    "FOCUSED_UNIT_TESTS",
    "SECURITY_NEGATIVE_TESTS",
    "RESTART_DURABILITY_TEST",
    "FULL_LOCAL_REGRESSION",
    "STATIC_SECURITY_AND_SYMBOL_CENSUS",
    "PRODUCTION_EFFECT_RECONCILIATION",
    "TRUTH_CARRIER_REBIND",
    "PUBLISH_PR_AND_EXACT_HEAD_CI",
    "MERGE_AND_POST_MERGE_CI",
    "DEPLOY_8766_AND_MEDIATOR",
    "DEPLOY_8780_PANEL_RUNTIME",
    "REAL_UNATTENDED_PRIMARY_ACCEPTANCE",
    "DUPLICATE_AND_RESTART_ACCEPTANCE",
    "FAILURE_INJECTION_ACCEPTANCE",
    "LIFECYCLE_R2_CURRENTNESS_RECONCILIATION",
    "TERMINAL_RECONCILIATION",
    "RETURN_TO_LION_SCAFFOLD",
)

def _saas_automatic_mediator_contract(mission_id: str, phase_id: str, ordinal: int) -> PhaseExecutionContract | None:
    if mission_id != SAAS_AUTOMATIC_MEDIATOR_MISSION or phase_id not in _SAAS_AUTOMATIC_MEDIATOR_PHASES:
        return None
    return migrated_explicit_contract(
        mission_id=mission_id,
        phase_id=phase_id,
        ordinal=ordinal,
        execution_class="VERIFY",
        capability_classes=("MISSION_RUNTIME_RECONCILIATION",),
        effect_ceiling="NONE",
        binding_mode="DYNAMIC",
        on_missing_capability="WAIT_AND_DISCOVER",
        auto_resume=True,
        verify_before_mutate=True,
        currentness_requirements=("EXACT_CURRENT_REPOSITORY", "CURRENT_MISSION_RUNTIME", "CURRENT_SAAS_BROKER_STATE"),
        evidence_requirements=("SAAS_MEDIATOR_PHASE_EVIDENCE", "DURABLE_RECEIPT"),
        completion_predicates=("SAAS_MEDIATOR_PHASE_EVIDENCE=PASS",),
    )

def migrated_contract_for(mission_id: str, phase_id: str, ordinal: int) -> PhaseExecutionContract | None:
    mediator=_saas_automatic_mediator_contract(mission_id,phase_id,ordinal)
    if mediator is not None:
        return mediator
    post=_post_astra_contract(mission_id,phase_id,ordinal)
    if post is not None:
        return post
    if mission_id != GENERIC_ADAPTER_REPAIR_MISSION:
        return None
    spec = _PHASES.get(phase_id)
    if spec is None:
        return None
    return migrated_explicit_contract(
        mission_id=mission_id,
        phase_id=phase_id,
        ordinal=ordinal,
        execution_class=spec["execution_class"],
        capability_classes=spec["capability_classes"],
        effect_ceiling=spec["effect_ceiling"],
        binding_mode="DYNAMIC",
        on_missing_capability="WAIT_AND_DISCOVER",
        auto_resume=True,
        verify_before_mutate=True,
        currentness_requirements=spec.get("currentness_requirements", _COMMON_CURRENTNESS),
        evidence_requirements=spec.get("evidence_requirements", _COMMON_EVIDENCE),
        completion_predicates=spec["completion_predicates"],
    )


def profile_phase_ids() -> tuple[str, ...]:
    return tuple(_PHASES)

def post_astra_profile_phase_ids() -> tuple[str, ...]:
    return _POST_ASTRA_PHASES

def saas_automatic_mediator_profile_phase_ids() -> tuple[str, ...]:
    return _SAAS_AUTOMATIC_MEDIATOR_PHASES
