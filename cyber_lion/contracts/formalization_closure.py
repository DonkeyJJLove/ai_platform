"""Fail-closed FormalizationClosureRecord contract."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping, Tuple
from .formalization_registry import FormalizationRegistry, FormalizationRegistryError, _id, _text, _tuple_text, domain_digest, validate_sha40, validate_sha256
from .architecture_formalization_manifest import ArchitectureFormalizationManifest
from cyber_lion.architecture_projection.formalization import derive_required_formalization_set
SCHEMA_ID = "lion.formalization-closure-record/v1"
DIGEST_DOMAIN = b"LION/FORMALIZATION-CLOSURE-RECORD/1\0"
AUTHORITY_EFFECT = "NONE"
DECISIONS = frozenset({"PASS", "BLOCKED", "FAIL"})
RESULT_STATES = frozenset({"PASS", "FAIL", "STALE", "UNKNOWN", "NOT_APPLICABLE"})
class FormalizationClosureError(FormalizationRegistryError): pass
@dataclass(frozen=True)
class CandidateBinding:
    candidate_digest: str
    head: str
    tree: str
    verification_digest: str
    def validate(self) -> "CandidateBinding":
        validate_sha256(self.candidate_digest,"candidate_digest"); validate_sha40(self.head,"candidate.head"); validate_sha40(self.tree,"candidate.tree"); validate_sha256(self.verification_digest,"verification_digest"); return self
@dataclass(frozen=True)
class ArtifactResult:
    artifact_id: str
    classification: str
    state: str
    evidence_refs: Tuple[str, ...]
    def validate(self) -> "ArtifactResult":
        _id(self.artifact_id,"artifact_result.artifact_id"); _text(self.classification,"artifact_result.classification")
        if self.state not in RESULT_STATES: raise FormalizationClosureError("artifact result state invalid")
        _tuple_text(self.evidence_refs,"artifact_result.evidence_refs")
        if self.state in {"PASS","NOT_APPLICABLE"} and not self.evidence_refs: raise FormalizationClosureError("positive artifact result requires evidence")
        return self
@dataclass(frozen=True)
class GateResult:
    id: str
    result: str
    evidence_refs: Tuple[str, ...]
    def validate(self, name: str) -> "GateResult":
        _id(self.id,f"{name}.id")
        if self.result not in {"PASS","FAIL","UNKNOWN","NOT_APPLICABLE"}: raise FormalizationClosureError(f"{name}.result invalid")
        _tuple_text(self.evidence_refs,f"{name}.evidence_refs")
        if self.result == "PASS" and not self.evidence_refs: raise FormalizationClosureError(f"{name} PASS requires evidence")
        return self
@dataclass(frozen=True)
class FormalizationClosureRecord:
    closure_id: str
    candidate: CandidateBinding
    formalization_manifest_digest: str
    artifact_results: Tuple[ArtifactResult, ...]
    semantic_owner_uniqueness: str
    catalog_coverage: str
    discoverability_result: str
    rag_result: str
    required_test_results: Tuple[GateResult, ...]
    required_eval_results: Tuple[GateResult, ...]
    currentness_result: str
    unknowns: Tuple[str, ...]
    decision: str
    authority_effect: str = AUTHORITY_EFFECT
    closure_digest: str = ""
    schema_id: str = SCHEMA_ID
    def canonical_payload(self) -> dict[str, Any]:
        data=asdict(self); data.pop("closure_digest",None); return data
    def compute_digest(self) -> str: return domain_digest(DIGEST_DOMAIN,self.canonical_payload())
    def validate(self, manifest: ArchitectureFormalizationManifest, registry: FormalizationRegistry, *, require_digest: bool=True) -> "FormalizationClosureRecord":
        manifest.validate(registry); registry.validate()
        if self.schema_id != SCHEMA_ID: raise FormalizationClosureError("closure schema")
        _id(self.closure_id,"closure_id"); self.candidate.validate(); validate_sha256(self.formalization_manifest_digest,"formalization_manifest_digest")
        if self.formalization_manifest_digest != manifest.manifest_digest: raise FormalizationClosureError("manifest digest substitution")
        if self.authority_effect != "NONE": raise FormalizationClosureError("closure cannot carry authority")
        if self.decision not in DECISIONS: raise FormalizationClosureError("closure decision invalid")
        _tuple_text(self.unknowns,"unknowns")
        for x in self.artifact_results: x.validate()
        for x in self.required_test_results: x.validate("required_test_result")
        for x in self.required_eval_results: x.validate("required_eval_result")
        required=derive_required_formalization_set(manifest,registry); required_by_id={x.artifact_id:x for x in required.items}; results={x.artifact_id:x for x in self.artifact_results}
        if len(results) != len(self.artifact_results): raise FormalizationClosureError("duplicate artifact result")
        missing=set(required_by_id).difference(results)
        if missing: raise FormalizationClosureError(f"missing formalization result: {sorted(missing)}")
        test_results={x.id:x for x in self.required_test_results}; eval_results={x.id:x for x in self.required_eval_results}
        if len(test_results)!=len(self.required_test_results) or len(eval_results)!=len(self.required_eval_results): raise FormalizationClosureError("duplicate test/eval result")
        if set(manifest.tests_required)-set(test_results) or set(manifest.evals_required)-set(eval_results): raise FormalizationClosureError("missing required test/eval result")
        if self.decision == "PASS":
            if self.unknowns: raise FormalizationClosureError("PASS forbidden with UNKNOWN")
            if self.semantic_owner_uniqueness != "PASS": raise FormalizationClosureError("semantic owner uniqueness not PASS")
            if self.catalog_coverage != "PASS": raise FormalizationClosureError("catalog coverage not PASS")
            if self.currentness_result != "CURRENT_CANDIDATE": raise FormalizationClosureError("required projection stale or candidate currentness not PASS")
            if manifest.discoverability.probe_questions and self.discoverability_result != "PASS": raise FormalizationClosureError("discoverability not PASS")
            if manifest.rag_delta.required and self.rag_result != "PASS": raise FormalizationClosureError("RAG retrieval not PASS")
            for artifact_id,item in required_by_id.items():
                result=results[artifact_id]
                if item.classification == "NOT_APPLICABLE":
                    if result.state != "NOT_APPLICABLE": raise FormalizationClosureError("NOT_APPLICABLE classification mismatch")
                elif result.state != "PASS": raise FormalizationClosureError("required formalization artifact not PASS")
            if any(test_results[x].result != "PASS" for x in manifest.tests_required): raise FormalizationClosureError("required test not PASS")
            if any(eval_results[x].result != "PASS" for x in manifest.evals_required): raise FormalizationClosureError("required eval not PASS")
        if require_digest:
            validate_sha256(self.closure_digest,"closure_digest")
            if self.closure_digest != self.compute_digest(): raise FormalizationClosureError("closure_digest mismatch")
        elif self.closure_digest: validate_sha256(self.closure_digest,"closure_digest")
        return self
    def sealed(self, manifest: ArchitectureFormalizationManifest, registry: FormalizationRegistry) -> "FormalizationClosureRecord":
        self.validate(manifest,registry,require_digest=False); return replace(self,closure_digest=self.compute_digest()).validate(manifest,registry)
