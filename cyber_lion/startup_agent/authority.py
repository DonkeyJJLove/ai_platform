"""Authority boundary for startup experiments.

Planning never grants execution rights. This module converts experiment authority classes
into deterministic allow/review/deny decisions based on explicit gate evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Experiment


@dataclass(frozen=True)
class GateDecision:
    decision: str
    reason: str
    gate_event_id: Optional[str] = None


class StartupAuthorityGate:
    SAFE_AUTONOMOUS = {"analysis", "local_prototype"}
    EXTERNAL = {"external_write", "deploy", "financial"}

    def decide(self, experiment: Experiment, *, gate_event_id: Optional[str] = None) -> GateDecision:
        experiment.validate()
        if experiment.authority_class in self.SAFE_AUTONOMOUS:
            return GateDecision("ALLOW", "bounded non-external experiment")
        if experiment.authority_class in self.EXTERNAL:
            if gate_event_id:
                return GateDecision("ALLOW_WITH_GATE", "external consequence has applied gate", gate_event_id)
            return GateDecision("REQUIRE_APPROVAL", "external/financial/deploy consequence requires applied gate")
        return GateDecision("DENY", "unknown authority class")
