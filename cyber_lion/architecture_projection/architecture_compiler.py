"""Deterministic, non-authoritative architecture candidate compiler.

The compiler extends the existing EvolutionDelta -> AFM -> RequiredFormalizationSet
spine and stops before authority/admission.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import re
from typing import Mapping, Tuple

from cyber_lion.contracts.architecture_formalization_manifest import (
    ArchitectureFormalizationManifest,
    GLOBAL_REQUIRED_ARTIFACTS,
)
from cyber_lion.contracts.evolutionary_rnd import EvolutionDelta, RISK_CLASSES
from cyber_lion.contracts.formalization_manifest_types import (
    BaselineIdentity, DiscoverabilityPlan, EvolutionDeltaRef, FormalizationUpdate,
    LayerBinding, MigrationPlan, RagDelta, SemanticOwnerDelta,
)
from cyber_lion.contracts.formalization_registry import FormalizationRegistry
from .flows import ARCHITECTURE_LAYERS, canonical_flows
from .formalization import RequiredFormalizationSet, derive_required_formalization_set
from .full_architecture import FullArchitectureModel

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_CANDIDATE_DOMAIN = b"LION/ARCHITECTURE-CANDIDATE-DESIGN/1\0"
_COMPILATION_DOMAIN = b"LION/ARCHITECTURE-COMPILATION/1\0"
_GLOBAL_CHANGE_CLASSES = frozenset({"ARCHITECTURE_CONCEPT", "MIXED_ARCHITECTURE", "SEMANTIC_OWNER", "FLOW"})
_EFFECT_METHOD_NAMES = frozenset({"authorize","admit","execute","write","push","merge","deploy","release","schedule","dispatch"})


class ArchitectureCompilerError(ValueError):
    pass


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ArchitectureCompilerError(f"{name} invalid")
    return value


def _sorted_unique(values: Tuple[str, ...], name: str, *, required: bool = True) -> Tuple[str, ...]:
    if type(values) is not tuple or (required and not values):
        raise ArchitectureCompilerError(f"{name} must be {'non-empty ' if required else ''}tuple")
    for value in values:
        _text(value, name)
    if values != tuple(sorted(set(values))):
        raise ArchitectureCompilerError(f"{name} must be sorted unique")
    return values


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True, order=True)
class CandidateLayerBinding:
    concept: str
    layers: Tuple[str, ...]

    def validate(self) -> "CandidateLayerBinding":
        if not _SAFE_ID.fullmatch(_text(self.concept, "concept")):
            raise ArchitectureCompilerError("concept invalid")
        _sorted_unique(self.layers, "layers")
        if not set(self.layers).issubset(ARCHITECTURE_LAYERS):
            raise ArchitectureCompilerError("new top-level architecture layer denied")
        return self


@dataclass(frozen=True)
class CandidateDesign:
    candidate_id: str
    baseline: BaselineIdentity
    target_component: str
    motivation: str
    evidence_refs: Tuple[str, ...]
    expected_outcome: str
    falsification_conditions: Tuple[str, ...]
    candidate_scope: Tuple[str, ...]
    dependency_ids: Tuple[str, ...]
    risk_class: str
    change_class: str
    affected_concepts: Tuple[str, ...]
    layer_bindings: Tuple[CandidateLayerBinding, ...]
    tests_required: Tuple[str, ...]
    evals_required: Tuple[str, ...]
    falsifiers: Tuple[str, ...]
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"

    def validate(self) -> "CandidateDesign":
        if not _SAFE_ID.fullmatch(_text(self.candidate_id, "candidate_id")):
            raise ArchitectureCompilerError("candidate_id invalid")
        self.baseline.validate()
        _text(self.target_component, "target_component"); _text(self.motivation, "motivation"); _text(self.expected_outcome, "expected_outcome")
        for name in ("evidence_refs","falsification_conditions","candidate_scope","affected_concepts","tests_required","evals_required","falsifiers"):
            _sorted_unique(getattr(self, name), name)
        _sorted_unique(self.dependency_ids, "dependency_ids", required=False)
        if self.risk_class not in RISK_CLASSES:
            raise ArchitectureCompilerError("risk_class invalid")
        if self.change_class not in {
            "ARCHITECTURE_CONCEPT","MIXED_ARCHITECTURE","SEMANTIC_OWNER","FLOW",
            "CONTRACT","CAPABILITY","CURRENTNESS","RAG","EVAL","DOCUMENTATION",
        }:
            raise ArchitectureCompilerError("change_class invalid")
        if type(self.layer_bindings) is not tuple or not self.layer_bindings:
            raise ArchitectureCompilerError("layer_bindings required")
        for binding in self.layer_bindings:
            binding.validate()
        concepts = tuple(binding.concept for binding in self.layer_bindings)
        if concepts != tuple(sorted(set(concepts))) or set(concepts) != set(self.affected_concepts):
            raise ArchitectureCompilerError("affected concepts and layer bindings must match exactly")
        if self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise ArchitectureCompilerError("candidate cannot carry authority/effect")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(_CANDIDATE_DOMAIN + _bytes(asdict(self))).hexdigest()


@dataclass(frozen=True)
class ArchitectureCompilationResult:
    candidate_digest: str
    current_head: str
    current_tree: str
    architecture_model_digest: str
    evolution_delta: EvolutionDelta
    formalization_manifest: ArchitectureFormalizationManifest
    required_formalization_set: RequiredFormalizationSet
    ends_before_admission: bool = True
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    compilation_digest: str = ""

    def compute_digest(self) -> str:
        payload = {
            "candidate_digest": self.candidate_digest,
            "current_head": self.current_head,
            "current_tree": self.current_tree,
            "architecture_model_digest": self.architecture_model_digest,
            "evolution_delta_digest": self.evolution_delta.delta_digest,
            "formalization_manifest_digest": self.formalization_manifest.manifest_digest,
            "required_formalization_set_digest": self.required_formalization_set.set_digest,
            "ends_before_admission": self.ends_before_admission,
            "authority_effect": self.authority_effect,
            "execution_effect": self.execution_effect,
        }
        return sha256(_COMPILATION_DOMAIN + _bytes(payload)).hexdigest()

    def validate(self) -> "ArchitectureCompilationResult":
        if not _SHA40.fullmatch(self.current_head) or not _SHA40.fullmatch(self.current_tree):
            raise ArchitectureCompilerError("exact current HEAD/TREE required")
        if not self.ends_before_admission or self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise ArchitectureCompilerError("compiler cannot cross admission/effect boundary")
        if self.compilation_digest and self.compilation_digest != self.compute_digest():
            raise ArchitectureCompilerError("compilation digest mismatch")
        return self


class ArchitectureCompiler:
    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHOD_NAMES:
            if hasattr(cls, name):
                raise ArchitectureCompilerError(f"effect surface present: {name}")

    def compile(
        self, *, candidate: CandidateDesign, architecture: FullArchitectureModel,
        registry: FormalizationRegistry, semantic_owners: Mapping[str, str],
        current_head: str, current_tree: str,
    ) -> ArchitectureCompilationResult:
        self.assert_no_effect_surface()
        candidate.validate(); architecture.validate(); registry.validate()
        if not _SHA40.fullmatch(current_head) or not _SHA40.fullmatch(current_tree):
            raise ArchitectureCompilerError("exact current HEAD/TREE required")
        if (candidate.baseline.head, candidate.baseline.tree) != (current_head, current_tree):
            raise ArchitectureCompilerError("candidate baseline is stale or substituted")
        if architecture.source_tree_sha != current_tree:
            raise ArchitectureCompilerError("architecture projection is stale or substituted")
        if architecture.flows != canonical_flows():
            raise ArchitectureCompilerError("canonical FLOW-01..FLOW-10 changed or substituted")
        for concept in candidate.affected_concepts:
            if not isinstance(semantic_owners.get(concept), str) or not semantic_owners[concept].strip():
                raise ArchitectureCompilerError(f"unknown semantic owner: {concept}")

        delta = EvolutionDelta(
            delta_id=f"architecture:{candidate.digest()[:24]}",
            target_component=candidate.target_component,
            motivation=candidate.motivation,
            evidence_refs=candidate.evidence_refs,
            expected_outcome=candidate.expected_outcome,
            falsification_conditions=candidate.falsification_conditions,
            candidate_scope=candidate.candidate_scope,
            dependency_ids=candidate.dependency_ids,
            risk_class=candidate.risk_class,
        ).sealed()

        registry_ids = set(registry.by_id())
        if candidate.change_class in _GLOBAL_CHANGE_CLASSES:
            missing = set(GLOBAL_REQUIRED_ARTIFACTS).difference(registry_ids)
            if missing:
                raise ArchitectureCompilerError(f"formalization registry incomplete: {sorted(missing)}")
            updates = tuple(FormalizationUpdate(
                artifact_id, "VALIDATE_ONLY",
                "compiler preview requires explicit formalization classification before source mutation",
            ).validate() for artifact_id in sorted(GLOBAL_REQUIRED_ARTIFACTS))
        else:
            updates = ()

        manifest = ArchitectureFormalizationManifest(
            manifest_id=f"afm-preview:{candidate.digest()[:24]}",
            baseline=candidate.baseline,
            source_evolution_delta=EvolutionDeltaRef(f"compiler:{delta.delta_id}", delta.delta_digest),
            change_class=candidate.change_class,
            affected_concepts=candidate.affected_concepts,
            layer_bindings=tuple(LayerBinding(x.concept, x.layers, False).validate() for x in candidate.layer_bindings),
            semantic_owner_delta=tuple(SemanticOwnerDelta(
                concept, semantic_owners[concept], (), "VALIDATE_ONLY"
            ).validate() for concept in candidate.affected_concepts),
            formalization_updates=updates,
            currentness_invalidations=(),
            migration=MigrationPlan(
                ("validate candidate through existing formalization owner",), None,
                "formalization preview classified without source mutation",
            ),
            rollback=MigrationPlan(
                ("discard unadmitted compiler preview",), None,
                "no repository or runtime effect remains",
            ),
            tests_required=candidate.tests_required,
            evals_required=candidate.evals_required,
            falsifiers=candidate.falsifiers,
            discoverability=DiscoverabilityPlan((), (), 1),
            rag_delta=RagDelta(False, (), ()),
        ).sealed(registry)

        required = derive_required_formalization_set(manifest, registry)
        result = ArchitectureCompilationResult(
            candidate.digest(), current_head, current_tree, architecture.digest(),
            delta, manifest, required,
        )
        return replace(result, compilation_digest=result.compute_digest()).validate()
