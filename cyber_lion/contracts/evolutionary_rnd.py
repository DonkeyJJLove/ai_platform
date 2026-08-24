"""Machine-readable contracts for the Cyber-Lion evolutionary R&D loop.

R&D state is epistemic/organizational state. None of these records grants runtime,
repository, release, deployment, credential, or execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

SCHEMA_VERSION = "1.0.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")

EPISTEMIC_CLASSES = frozenset({
    "OBSERVED", "DERIVED", "CALIBRATED", "ASSUMED", "HYPOTHESIS",
    "SPECULATION", "STRESS_PARAMETER", "SIMULATED",
})
HYPOTHESIS_STATES = frozenset({
    "PROPOSED", "ADMITTED_FOR_TEST", "TESTING", "SUPPORTED",
    "FALSIFIED", "INCONCLUSIVE", "CONTRADICTED",
})
TERMINAL_HYPOTHESIS_STATES = frozenset({
    "SUPPORTED", "FALSIFIED", "INCONCLUSIVE", "CONTRADICTED",
})
RESULT_CLASSES = frozenset({
    "OBSERVED", "SIMULATED", "REPRODUCED", "FAILED", "UNKNOWN", "PARTIAL_UNKNOWN",
})
FALSIFICATION_DISPOSITIONS = frozenset({
    "SUPPORTED", "FALSIFIED", "INCONCLUSIVE", "CONTRADICTED", "UNKNOWN",
})
PROMOTION_DECISIONS = frozenset({"PROMOTE_KNOWLEDGE", "REJECT", "HOLD"})
MEMORY_KINDS = frozenset({
    "OBSERVATION", "HYPOTHESIS", "NEGATIVE_RESULT", "FALSIFICATION",
    "SUPPORTED_RESULT", "PROMOTED_KNOWLEDGE", "SUPERSESSION",
})
RISK_CLASSES = frozenset({"GREEN", "AMBER", "RED"})

_DOMAINS = {
    "evidence": b"LION/E004-RND-EVIDENCE/1\0",
    "hypothesis": b"LION/E004-RND-HYPOTHESIS/1\0",
    "experiment": b"LION/E004-RND-EXPERIMENT/1\0",
    "simulation": b"LION/E004-RND-SIMULATION/1\0",
    "result": b"LION/E004-RND-RESULT/1\0",
    "falsification": b"LION/E004-RND-FALSIFICATION/1\0",
    "promotion": b"LION/E004-RND-PROMOTION/1\0",
    "memory": b"LION/E004-RND-MEMORY/1\0",
    "delta": b"LION/E004-EVOLUTION-DELTA/1\0",
}


class EvolutionaryRnDContractError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def domain_digest(kind: str, payload: Mapping[str, Any]) -> str:
    try:
        prefix = _DOMAINS[kind]
    except KeyError as exc:
        raise EvolutionaryRnDContractError("unknown digest domain") from exc
    return sha256(prefix + canonical_json(dict(payload))).hexdigest()


def _text(value: Any, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise EvolutionaryRnDContractError(f"{name} invalid")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, limit=256)
    if not _SAFE_ID.fullmatch(value):
        raise EvolutionaryRnDContractError(f"{name} invalid")
    return value


def _digest(value: Any, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise EvolutionaryRnDContractError(f"{name} must be sha256 hex")
    return value


def _refs(value: Any, name: str, *, nonempty: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple or (nonempty and not value):
        raise EvolutionaryRnDContractError(f"{name} must be tuple")
    for ref in value:
        _text(ref, name, limit=1024)
    if len(set(value)) != len(value):
        raise EvolutionaryRnDContractError(f"{name} must be unique")
    return value


def _scope(value: Any) -> Tuple[str, ...]:
    _refs(value, "candidate_scope", nonempty=True)
    for path in value:
        if path.startswith("/") or ".." in path.split("/") or "\x00" in path:
            raise EvolutionaryRnDContractError("candidate_scope invalid")
    return value


def _forbid_effect_material(value: str, name: str) -> None:
    lowered = value.lower()
    forbidden = (
        "authorization: bearer", "ghp_", "github_pat_", "private key", "password=",
        "secret=", "token=", "shell=", "subprocess", "git push", "curl ", "wget ",
        "deploy", "release", "execute command", "rm -rf",
    )
    if any(token in lowered for token in forbidden):
        raise EvolutionaryRnDContractError(f"{name} contains prohibited effect/credential material")


class _DigestMixin:
    _digest_kind: str
    _digest_field: str

    def canonical_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop(self._digest_field)
        for key, value in tuple(data.items()):
            if isinstance(value, tuple):
                data[key] = list(value)
        return data

    def compute_digest(self) -> str:
        return domain_digest(self._digest_kind, self.canonical_payload())

    def _verify_digest(self) -> None:
        value = getattr(self, self._digest_field)
        if value:
            _digest(value, self._digest_field)
            if value != self.compute_digest():
                raise EvolutionaryRnDContractError(f"{self._digest_field} mismatch")


@dataclass(frozen=True)
class EvidenceObservation(_DigestMixin):
    observation_id: str
    observation_kind: str
    source_ref: str
    source_digest: str
    observed_at: str
    epistemic_class: str
    provenance_refs: Tuple[str, ...]
    content_digest: str
    observation_digest: str = ""
    schema_version: str = SCHEMA_VERSION
    _digest_kind = "evidence"
    _digest_field = "observation_digest"

    def validate(self):
        if self.schema_version != SCHEMA_VERSION:
            raise EvolutionaryRnDContractError("unsupported evidence schema")
        _id(self.observation_id, "observation_id"); _text(self.observation_kind, "observation_kind")
        _text(self.source_ref, "source_ref"); _digest(self.source_digest, "source_digest")
        _text(self.observed_at, "observed_at"); _digest(self.content_digest, "content_digest")
        _refs(self.provenance_refs, "provenance_refs", nonempty=True)
        if self.epistemic_class not in EPISTEMIC_CLASSES:
            raise EvolutionaryRnDContractError("invalid epistemic_class")
        self._verify_digest(); return self

    def sealed(self):
        self.validate(); return EvidenceObservation(**{**asdict(self), "observation_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class Hypothesis(_DigestMixin):
    hypothesis_id: str
    revision: int
    claim: str
    evidence_refs: Tuple[str, ...]
    counter_evidence_refs: Tuple[str, ...]
    falsifiers: Tuple[str, ...]
    alternative_explanations: Tuple[str, ...]
    state: str
    provenance_refs: Tuple[str, ...]
    supersedes_hypothesis_digest: str | None = None
    hypothesis_digest: str = ""
    schema_version: str = SCHEMA_VERSION
    _digest_kind = "hypothesis"
    _digest_field = "hypothesis_digest"

    def validate(self):
        if self.schema_version != SCHEMA_VERSION: raise EvolutionaryRnDContractError("unsupported hypothesis schema")
        _id(self.hypothesis_id, "hypothesis_id"); _text(self.claim, "claim")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise EvolutionaryRnDContractError("revision invalid")
        _refs(self.evidence_refs, "evidence_refs", nonempty=True); _refs(self.counter_evidence_refs, "counter_evidence_refs")
        _refs(self.falsifiers, "falsifiers", nonempty=True); _refs(self.alternative_explanations, "alternative_explanations")
        _refs(self.provenance_refs, "provenance_refs", nonempty=True)
        if self.state not in HYPOTHESIS_STATES: raise EvolutionaryRnDContractError("invalid hypothesis state")
        if self.revision == 1 and self.supersedes_hypothesis_digest is not None:
            raise EvolutionaryRnDContractError("first revision cannot supersede")
        if self.revision > 1:
            _digest(self.supersedes_hypothesis_digest, "supersedes_hypothesis_digest")
        self._verify_digest(); return self

    def sealed(self):
        self.validate(); return Hypothesis(**{**asdict(self), "hypothesis_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class ExperimentProposal(_DigestMixin):
    experiment_id: str
    hypothesis_digest: str
    evidence_refs: Tuple[str, ...]
    method: str
    expected_observables: Tuple[str, ...]
    falsification_conditions: Tuple[str, ...]
    risk_class: str
    provenance_refs: Tuple[str, ...]
    experiment_digest: str = ""
    schema_version: str = SCHEMA_VERSION
    _digest_kind = "experiment"
    _digest_field = "experiment_digest"

    def validate(self):
        if self.schema_version != SCHEMA_VERSION: raise EvolutionaryRnDContractError("unsupported experiment schema")
        _id(self.experiment_id, "experiment_id"); _digest(self.hypothesis_digest, "hypothesis_digest")
        _refs(self.evidence_refs, "evidence_refs", nonempty=True); _text(self.method, "method")
        _refs(self.expected_observables, "expected_observables", nonempty=True)
        _refs(self.falsification_conditions, "falsification_conditions", nonempty=True)
        _refs(self.provenance_refs, "provenance_refs", nonempty=True)
        if self.risk_class not in RISK_CLASSES: raise EvolutionaryRnDContractError("invalid risk_class")
        self._verify_digest(); return self

    def sealed(self):
        self.validate(); return ExperimentProposal(**{**asdict(self), "experiment_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class SimulationPlan(_DigestMixin):
    simulation_id: str
    experiment_digest: str
    model_id: str
    model_version: str
    scenario_digest: str
    parameter_distribution_digest: str
    seed_strategy: str
    assumption_refs: Tuple[str, ...]
    requested_metrics: Tuple[str, ...]
    stress_conditions: Tuple[str, ...]
    provenance_refs: Tuple[str, ...]
    simulation_digest: str = ""
    schema_version: str = SCHEMA_VERSION
    _digest_kind = "simulation"
    _digest_field = "simulation_digest"

    def validate(self):
        if self.schema_version != SCHEMA_VERSION: raise EvolutionaryRnDContractError("unsupported simulation schema")
        _id(self.simulation_id, "simulation_id"); _digest(self.experiment_digest, "experiment_digest")
        _text(self.model_id, "model_id"); _text(self.model_version, "model_version")
        _digest(self.scenario_digest, "scenario_digest"); _digest(self.parameter_distribution_digest, "parameter_distribution_digest")
        _text(self.seed_strategy, "seed_strategy"); _refs(self.assumption_refs, "assumption_refs", nonempty=True)
        _refs(self.requested_metrics, "requested_metrics", nonempty=True); _refs(self.stress_conditions, "stress_conditions")
        _refs(self.provenance_refs, "provenance_refs", nonempty=True)
        self._verify_digest(); return self

    def sealed(self):
        self.validate(); return SimulationPlan(**{**asdict(self), "simulation_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class ExperimentResult(_DigestMixin):
    result_id: str
    experiment_digest: str
    input_digest: str
    output_digest: str
    result_class: str
    observer_evidence_ref: str
    limitations: Tuple[str, ...]
    observed_at: str
    provenance_refs: Tuple[str, ...]
    result_digest: str = ""
    schema_version: str = SCHEMA_VERSION
    _digest_kind = "result"
    _digest_field = "result_digest"

    def validate(self):
        if self.schema_version != SCHEMA_VERSION: raise EvolutionaryRnDContractError("unsupported result schema")
        _id(self.result_id, "result_id"); _digest(self.experiment_digest, "experiment_digest")
        _digest(self.input_digest, "input_digest"); _digest(self.output_digest, "output_digest")
        _text(self.observer_evidence_ref, "observer_evidence_ref"); _refs(self.limitations, "limitations")
        _text(self.observed_at, "observed_at"); _refs(self.provenance_refs, "provenance_refs", nonempty=True)
        if self.result_class not in RESULT_CLASSES: raise EvolutionaryRnDContractError("invalid result_class")
        self._verify_digest(); return self

    def sealed(self):
        self.validate(); return ExperimentResult(**{**asdict(self), "result_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class FalsificationResult(_DigestMixin):
    falsification_id: str
    hypothesis_digest: str
    experiment_result_digests: Tuple[str, ...]
    attempted_falsifiers: Tuple[str, ...]
    contrary_evidence_refs: Tuple[str, ...]
    anomaly_codes: Tuple[str, ...]
    disposition: str
    provenance_refs: Tuple[str, ...]
    falsification_digest: str = ""
    schema_version: str = SCHEMA_VERSION
    _digest_kind = "falsification"
    _digest_field = "falsification_digest"

    def validate(self):
        if self.schema_version != SCHEMA_VERSION: raise EvolutionaryRnDContractError("unsupported falsification schema")
        _id(self.falsification_id, "falsification_id"); _digest(self.hypothesis_digest, "hypothesis_digest")
        _refs(self.experiment_result_digests, "experiment_result_digests", nonempty=True)
        for value in self.experiment_result_digests: _digest(value, "experiment_result_digest")
        _refs(self.attempted_falsifiers, "attempted_falsifiers", nonempty=True)
        _refs(self.contrary_evidence_refs, "contrary_evidence_refs")
        _refs(self.anomaly_codes, "anomaly_codes"); _refs(self.provenance_refs, "provenance_refs", nonempty=True)
        if self.disposition not in FALSIFICATION_DISPOSITIONS: raise EvolutionaryRnDContractError("invalid disposition")
        if self.disposition in {"CONTRADICTED", "UNKNOWN"} and not self.anomaly_codes:
            raise EvolutionaryRnDContractError("non-positive falsification requires anomaly evidence")
        self._verify_digest(); return self

    def sealed(self):
        self.validate(); return FalsificationResult(**{**asdict(self), "falsification_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class EvolutionDelta(_DigestMixin):
    delta_id: str
    target_component: str
    motivation: str
    evidence_refs: Tuple[str, ...]
    expected_outcome: str
    falsification_conditions: Tuple[str, ...]
    candidate_scope: Tuple[str, ...]
    dependency_ids: Tuple[str, ...]
    risk_class: str
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    delta_digest: str = ""
    schema_version: str = SCHEMA_VERSION
    _digest_kind = "delta"
    _digest_field = "delta_digest"

    def validate(self):
        if self.schema_version != SCHEMA_VERSION: raise EvolutionaryRnDContractError("unsupported delta schema")
        _id(self.delta_id, "delta_id"); _text(self.target_component, "target_component")
        _text(self.motivation, "motivation"); _forbid_effect_material(self.motivation, "motivation")
        _refs(self.evidence_refs, "evidence_refs", nonempty=True); _text(self.expected_outcome, "expected_outcome")
        _forbid_effect_material(self.expected_outcome, "expected_outcome")
        _refs(self.falsification_conditions, "falsification_conditions", nonempty=True)
        _scope(self.candidate_scope); _refs(self.dependency_ids, "dependency_ids")
        if self.risk_class not in RISK_CLASSES: raise EvolutionaryRnDContractError("invalid risk_class")
        if self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise EvolutionaryRnDContractError("EvolutionDelta cannot carry effect authority")
        for value in self.candidate_scope + self.falsification_conditions:
            _forbid_effect_material(value, "EvolutionDelta")
        self._verify_digest(); return self

    def sealed(self):
        self.validate(); return EvolutionDelta(**{**asdict(self), "delta_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class PromotionDecision(_DigestMixin):
    promotion_id: str
    hypothesis_digest: str
    hypothesis_state: str
    falsification_digest: str
    falsification_disposition: str
    evolution_delta_digest: str
    policy_decision_ref: str
    unresolved_contradictions: int
    contrary_evidence_complete: bool
    decision: str
    rationale: str
    promotion_digest: str = ""
    schema_version: str = SCHEMA_VERSION
    _digest_kind = "promotion"
    _digest_field = "promotion_digest"

    def validate(self):
        if self.schema_version != SCHEMA_VERSION: raise EvolutionaryRnDContractError("unsupported promotion schema")
        _id(self.promotion_id, "promotion_id"); _digest(self.hypothesis_digest, "hypothesis_digest")
        _digest(self.falsification_digest, "falsification_digest"); _digest(self.evolution_delta_digest, "evolution_delta_digest")
        _text(self.policy_decision_ref, "policy_decision_ref"); _text(self.rationale, "rationale")
        if self.hypothesis_state not in HYPOTHESIS_STATES: raise EvolutionaryRnDContractError("invalid hypothesis state")
        if self.falsification_disposition not in FALSIFICATION_DISPOSITIONS: raise EvolutionaryRnDContractError("invalid falsification disposition")
        if self.decision not in PROMOTION_DECISIONS: raise EvolutionaryRnDContractError("invalid promotion decision")
        if isinstance(self.unresolved_contradictions, bool) or not isinstance(self.unresolved_contradictions, int) or self.unresolved_contradictions < 0:
            raise EvolutionaryRnDContractError("unresolved_contradictions invalid")
        if type(self.contrary_evidence_complete) is not bool: raise EvolutionaryRnDContractError("contrary_evidence_complete invalid")
        if self.decision == "PROMOTE_KNOWLEDGE":
            if self.hypothesis_state != "SUPPORTED": raise EvolutionaryRnDContractError("promotion requires supported hypothesis")
            if self.falsification_disposition != "SUPPORTED": raise EvolutionaryRnDContractError("promotion requires supported falsification")
            if self.unresolved_contradictions != 0 or not self.contrary_evidence_complete:
                raise EvolutionaryRnDContractError("promotion requires contradiction completeness")
            if not self.policy_decision_ref.startswith("pdp:"):
                raise EvolutionaryRnDContractError("promotion requires canonical external PDP evidence ref")
        self._verify_digest(); return self

    def sealed(self):
        self.validate(); return PromotionDecision(**{**asdict(self), "promotion_digest": self.compute_digest()}).validate()


@dataclass(frozen=True)
class RnDMemoryRecord(_DigestMixin):
    memory_id: str
    revision: int
    record_kind: str
    subject_id: str
    source_digests: Tuple[str, ...]
    negative_evidence_refs: Tuple[str, ...]
    supersedes_memory_digest: str | None
    epistemic_status: str
    committed_event_ref: str
    previous_memory_head: str
    memory_digest: str = ""
    schema_version: str = SCHEMA_VERSION
    _digest_kind = "memory"
    _digest_field = "memory_digest"

    def validate(self):
        if self.schema_version != SCHEMA_VERSION: raise EvolutionaryRnDContractError("unsupported memory schema")
        _id(self.memory_id, "memory_id"); _id(self.subject_id, "subject_id")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise EvolutionaryRnDContractError("memory revision invalid")
        if self.record_kind not in MEMORY_KINDS: raise EvolutionaryRnDContractError("invalid memory record_kind")
        _refs(self.source_digests, "source_digests", nonempty=True)
        for value in self.source_digests: _digest(value, "source_digest")
        _refs(self.negative_evidence_refs, "negative_evidence_refs")
        if self.supersedes_memory_digest is not None: _digest(self.supersedes_memory_digest, "supersedes_memory_digest")
        _text(self.epistemic_status, "epistemic_status"); _text(self.committed_event_ref, "committed_event_ref")
        if self.revision == 1:
            if self.previous_memory_head != "GENESIS": raise EvolutionaryRnDContractError("first memory record requires GENESIS head")
        else:
            _digest(self.previous_memory_head, "previous_memory_head")
        self._verify_digest(); return self

    def sealed(self):
        self.validate(); return RnDMemoryRecord(**{**asdict(self), "memory_digest": self.compute_digest()}).validate()
