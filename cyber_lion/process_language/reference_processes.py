"""Positive LPCL/ProcessIR reference corpus using one shared semantic kernel."""
from __future__ import annotations

from cyber_lion.contracts.process_ir import CanonicalProcessIR

SCENARIOS = (
    "read-only-live-reacquisition",
    "candidate-preparation",
    "exact-head-gated-candidate-integration",
    "scientific-experiment",
    "bounded-autonomous-continuation",
    "stale-state-recovery",
    "fleet-mission",
    "documentation-homeostasis",
    "local-model-benchmark",
    "runtime-admission-research",
    "simulation-only-cyber-physical-task",
    "multi-repository-migration",
)

_ACTION_SCENARIOS = frozenset({
    "candidate-preparation",
    "exact-head-gated-candidate-integration",
    "local-model-benchmark",
    "simulation-only-cyber-physical-task",
    "multi-repository-migration",
})


def reference_process(name: str) -> CanonicalProcessIR:
    if name not in SCENARIOS:
        raise KeyError(name)
    action = name in _ACTION_SCENARIOS
    transition_class = "ACTION_REQUIRED" if action else "INTERNAL"
    operator = "EMIT_ACTION_INTENT" if action else "REACQUIRE"
    evidence = ["evidence:baseline"] if action else ["evidence:input"]
    currentness = ["currentness:exact"] if action else ["currentness:observed"]
    authority = ["authority-context:required"] if action else []
    outcome_map = {"PASS": "DONE", "FAIL": "STOP", "UNKNOWN": "HANDOFF", "DRIFT": "HANDOFF"}
    if action:
        # The positive reference corpus proves the Process->Action boundary but does
        # not fabricate downstream runtime evidence.  Full ACTION_REQUIRED+PASS is
        # covered separately with the existing canonical Action/runtime chain.
        outcome_map["AUTHORITY_BOUNDARY"] = "HANDOFF"
    model = {
        "schema_version": "1.0.0",
        "process_id": "reference:" + name,
        "mission_ref": "mission:" + name,
        "goal_ref": "goal:" + name,
        "scope": {"domains": ["reference"], "resources": ["scenario:" + name], "widening_allowed": False},
        "initial_state": "READY",
        "states": ["READY", "DONE"],
        "dependencies": [],
        "transitions": [{
            "transition_id": "step",
            "transition_class": transition_class,
            "source_states": ["READY"],
            "trigger": "start",
            "dependencies": [],
            "guards": [],
            "evidence_requirements": evidence,
            "currentness_requirements": currentness,
            "authority_requirements": authority,
            "operator": operator,
            "expected_postconditions": ["scenario-bounded"],
            "outcome_map": outcome_map,
            "retry_policy": {"max_attempts": 0, "on_exhausted": "HANDOFF"},
            "replay_policy": "DENY",
            "idempotency_class": "PURE" if not action else "IDEMPOTENT",
            "resource_claims": {
                "read_scopes": ["scenario:" + name],
                "write_scopes": ["candidate:" + name] if action else [],
                "authority_budgets": ["authority-context:required"] if action else [],
                "currentness_subjects": currentness,
                "replay_domain": "reference:" + name,
                "reconciliation_group": "reference:" + name,
            },
        }],
        "scheduling_policy": {"strategy": "DECLARED_ORDER", "order": ["step"], "priorities": {"step": 0}, "max_wip": 1, "parallel_safe_groups": []},
        "termination_policy": {"terminal_states": ["DONE"], "allow_no_legal_transition": False, "on_unknown": "HANDOFF"},
        "lineage": {"parent_process_digests": [], "generation": 0, "source_refs": ["reference-corpus:" + name]},
    }
    return CanonicalProcessIR.from_mapping(model)


def all_reference_processes() -> tuple[CanonicalProcessIR, ...]:
    return tuple(reference_process(name) for name in SCENARIOS)
