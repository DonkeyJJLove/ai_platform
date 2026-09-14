from __future__ import annotations

DRIVER_SCHEMA = "lion.mission-execution-driver/v1"
DRIVER_STATES = frozenset({"BOOTSTRAP_PAUSED","ACTIVE","PAUSED","WAITING","BLOCKED","STOPPED","COMPLETE","FAILED"})
ACTIVE_PHASE_STATES = frozenset({"RUNNING","WAITING","BLOCKED"})
TERMINAL_PHASE_STATES = frozenset({"PASS","COMPLETE","SKIPPED","FAIL","CANCELLED"})

# These phases are deliberately handled by the self-hosted driver after the
# bootstrap implementation/deployment work has produced that driver.
SELF_HOSTED_PHASES = (
    "SELF_HOSTING_TAKEOVER",
    "LIVE_AUTONOMY_CANARY",
    "PARENT_MISSION_RECONCILIATION",
    "PR337_FAST_FORWARD_AND_GREEN_EXACT_HEAD_CI",
    "READY_FOR_SYSTEM_ACCEPTANCE_TESTS",
)


def legal_driver_transition(old: str, new: str) -> bool:
    if old == new:
        return True
    allowed = {
        "BOOTSTRAP_PAUSED": {"ACTIVE", "STOPPED"},
        "ACTIVE": {"WAITING", "BLOCKED", "PAUSED", "STOPPED", "COMPLETE", "FAILED"},
        "WAITING": {"ACTIVE", "BLOCKED", "PAUSED", "STOPPED", "FAILED"},
        "BLOCKED": {"ACTIVE", "PAUSED", "STOPPED", "FAILED"},
        "PAUSED": {"ACTIVE", "STOPPED"},
        "STOPPED": {"ACTIVE"},
        "FAILED": {"ACTIVE", "STOPPED"},
        "COMPLETE": set(),
    }
    return new in allowed.get(old, set())
