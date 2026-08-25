from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath

from .extractor import ArchitectureProjectionExtractor
from .flows import ARCHITECTURE_LAYERS, canonical_flows
from .gap import canonical_target_gaps
from .layout import canonical_layout
from .status import ArchitectureStatus

_MODEL_DOMAIN = b"LION/UML/FULL-ARCHITECTURE/1\0"


@dataclass(frozen=True, order=True)
class ArchitectureElement:
    element_id: str
    layer: str
    label: str
    status: ArchitectureStatus
    source_path: str = ""
    symbol: str = ""
    target_ref: str = ""

    def validate(self) -> "ArchitectureElement":
        if not self.element_id.strip() or not self.label.strip():
            raise ValueError("architecture element identity and label are required")
        if self.layer not in ARCHITECTURE_LAYERS:
            raise ValueError("architecture element layer is invalid")
        self.status.validate()
        if self.status.status == "TARGET_ONLY":
            if not self.target_ref:
                raise ValueError("TARGET_ONLY element requires target_ref")
            if self.source_path or self.symbol:
                raise ValueError("TARGET_ONLY element cannot claim source implementation")
        else:
            if not self.source_path:
                raise ValueError("implemented/observed architecture element requires source_path")
            if not self.symbol.strip():
                raise ValueError("implemented/observed architecture element requires source symbol or contract")
            if not self.status.source_digest:
                raise ValueError("implemented/observed architecture element requires source digest")
        return self


@dataclass(frozen=True)
class FullArchitectureModel:
    source_tree_sha: str
    elements: tuple[ArchitectureElement, ...]
    flows: tuple[object, ...]
    gaps: tuple[object, ...]
    layout: tuple[object, ...]
    derived_only: bool = True
    authority_effect: str = "NONE"
    runtime_evidence: str = "NONE"

    def validate(self) -> "FullArchitectureModel":
        if len(self.source_tree_sha) != 40:
            raise ValueError("full architecture model requires SHA-40 source tree")
        if not self.derived_only or self.authority_effect != "NONE" or self.runtime_evidence != "NONE":
            raise ValueError("full architecture model must remain derived and non-authoritative")
        ids = [element.element_id for element in self.elements]
        if ids != sorted(set(ids)):
            raise ValueError("architecture element identities must be sorted unique")
        represented = {element.layer for element in self.elements}
        if represented != set(ARCHITECTURE_LAYERS):
            raise ValueError("all 15 architecture layers must be represented")
        for element in self.elements:
            element.validate()
        if len(self.flows) != 9:
            raise ValueError("all 9 canonical flows are required")
        return self

    def canonical_bytes(self) -> bytes:
        self.validate()
        payload = asdict(self)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def digest(self) -> str:
        return sha256(_MODEL_DOMAIN + self.canonical_bytes()).hexdigest()


_ELEMENT_SPECS = (
    ("architecture-projection", "ARCHITECTURE_PROJECTION", "Canonical architecture projection", "VERIFIED_REFERENCE", "cyber_lion/architecture_projection/extractor.py", "ArchitectureProjectionExtractor", "LIVE_CODE"),
    ("authority-effect", "AUTHORITY_AND_EFFECT", "Authority and effect boundary", "VERIFIED_REFERENCE", "cyber_lion/enterprise/policy_gate.py", "CanonicalPolicyDecisionPoint", "LIVE_CODE"),
    ("code-perception", "CODE_PERCEPTION", "Deterministic code perception", "VERIFIED_REFERENCE", "cyber_lion/enterprise/code_perception.py", "CodePerception", "LIVE_CODE"),
    ("constitution-governance", "CONSTITUTION_AND_GOVERNANCE", "Constitution and governance", "VERIFIED_REFERENCE", "cyber_lion/enterprise/policy_gate.py", "CanonicalPolicyDecisionPoint", "LIVE_CODE"),
    ("evidence-epistemic", "EVIDENCE_AND_EPISTEMIC_PLANE", "Evidence and epistemic R&D", "VERIFIED_REFERENCE", "cyber_lion/contracts/evolutionary_rnd.py", "EvidenceObservation", "LIVE_CODE"),
    ("evolutionary-epoch", "EVOLUTIONARY_EPOCH", "Evolutionary epoch", "VERIFIED_REFERENCE", "cyber_lion/enterprise/evolutionary_epoch.py", "EvolutionaryEpochEngine", "LIVE_CODE"),
    ("fleet-swarm", "FLEET_AND_SWARM", "Fleet and swarm organization", "PARTIALLY_IMPLEMENTED", "cyber_lion/enterprise/models.py", "MissionSpec", "LIVE_CODE"),
    ("governed-self-implementation", "GOVERNED_SELF_IMPLEMENTATION", "Governed self-implementation", "VERIFIED_REFERENCE", "cyber_lion/contracts/governed_change_proposal.py", "GovernedChangeProposal", "LIVE_CODE"),
    ("observability-reconciliation", "OBSERVABILITY_AND_RECONCILIATION", "Observability and reconciliation", "VERIFIED_REFERENCE", "cyber_lion/enterprise/runtime_reconciliation.py", "RuntimeReconciliation", "LIVE_CODE"),
    ("quarantined-f005", "QUARANTINED_AND_NONCANONICAL", "F005 runtime plane", "QUARANTINED", ".lion/runtime/f005-runtime-plane-state.json", "f005-local-runtime-v1", "EXACT_GIT_STATE"),
    ("repository-mutation", "REPOSITORY_MUTATION", "Repository mutation reference path", "VERIFIED_REFERENCE", "cyber_lion/enterprise/repository_mutation_pep.py", "RepositoryMutationPEP", "LIVE_CODE"),
    ("startup-evolution", "STARTUP_EVOLUTION", "Startup Evolution Agent", "IMPLEMENTED", "cyber_lion/startup_agent/orchestrator.py", "AIDrivenStartupAgent", "LIVE_CODE"),
    ("system-context", "SYSTEM_CONTEXT", "System context and target boundary", "PARTIALLY_IMPLEMENTED", "cyber_lion/TARGET_ARCHITECTURE.md", "SYSTEM_CONTEXT", "CANONICAL_DOCUMENTATION"),
    ("trusted-runtime", "TRUSTED_RUNTIME", "Trusted runtime enforcement", "PARTIALLY_IMPLEMENTED", "cyber_lion/enterprise/runtime_enforcement.py", "RuntimeAdmission", "LIVE_CODE"),
)

_TARGET_ELEMENTS = (
    ("bean-factory", "TARGET_BEAN_FACTORY", "Target Bean Factory", "cyber_lion/TARGET_ARCHITECTURE.md#bean-factory"),
)


def _sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _require_source_symbol(extractor: ArchitectureProjectionExtractor, *, path: str, symbol: str, text: str) -> None:
    if not symbol.strip():
        raise ValueError("architecture source symbol or contract is required")
    if PurePosixPath(path).suffix == ".py":
        if symbol not in extractor._symbol_names(text, path):
            raise ValueError(f"architecture source symbol missing: {path}:{symbol}")
        return
    if symbol not in text:
        raise ValueError(f"architecture source contract missing: {path}:{symbol}")


def build_full_architecture_model(*, source_tree_sha: str, source_root: str | Path | None = None) -> FullArchitectureModel:
    extractor = ArchitectureProjectionExtractor(source_tree_sha=source_tree_sha, source_root=source_root)
    elements: list[ArchitectureElement] = []
    for element_id, layer, label, status, path, symbol, evidence_class in _ELEMENT_SPECS:
        text = extractor._source(path)
        _require_source_symbol(extractor, path=path, symbol=symbol, text=text)
        if path.endswith("f005-runtime-plane-state.json"):
            state = json.loads(text)
            if state.get("state") != "QUARANTINED" or state.get("effect_authority") != "DENY":
                raise ValueError("F005 must remain QUARANTINED with DENY effect authority")
        architecture_status = ArchitectureStatus(
            status=status,
            evidence_class=evidence_class,
            rationale=f"source-bound E005 classification for {label}",
            source_path=path,
            symbol=symbol,
            source_digest=_sha256_text(text),
        ).validate()
        elements.append(ArchitectureElement(element_id, layer, label, architecture_status, path, symbol).validate())
    for element_id, layer, label, target_ref in _TARGET_ELEMENTS:
        architecture_status = ArchitectureStatus(
            status="TARGET_ONLY",
            evidence_class="TARGET_ARCHITECTURE",
            rationale=f"target-only E005 classification for {label}",
        ).validate()
        elements.append(ArchitectureElement(element_id, layer, label, architecture_status, target_ref=target_ref).validate())
    return FullArchitectureModel(
        source_tree_sha=source_tree_sha,
        elements=tuple(sorted(elements)),
        flows=canonical_flows(),
        gaps=canonical_target_gaps(),
        layout=canonical_layout(),
    ).validate()
