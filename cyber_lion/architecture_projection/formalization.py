"""Deterministic formalization projection for architecture-affecting changes."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any, Tuple
from cyber_lion.contracts.formalization_registry import FormalizationRegistry, domain_digest
from cyber_lion.contracts.architecture_formalization_manifest import ArchitectureFormalizationManifest, GLOBAL_CHANGE_CLASSES
SCHEMA_ID = "lion.required-formalization-set/v1"
DIGEST_DOMAIN = b"LION/REQUIRED-FORMALIZATION-SET/1\0"
_CHANGE_TRIGGERS = {
    "ARCHITECTURE_CONCEPT": {"SOURCE_CHANGE", "CONTRACT_CHANGE", "SEMANTIC_OWNER_CHANGE", "CURRENTNESS_CHANGE"},
    "MIXED_ARCHITECTURE": {"SOURCE_CHANGE", "CONTRACT_CHANGE", "CAPABILITY_CHANGE", "SEMANTIC_OWNER_CHANGE", "FLOW_CHANGE", "CURRENTNESS_CHANGE"},
    "SEMANTIC_OWNER": {"SEMANTIC_OWNER_CHANGE", "CURRENTNESS_CHANGE"},
    "FLOW": {"FLOW_CHANGE", "CONTRACT_CHANGE", "CURRENTNESS_CHANGE"},
    "CONTRACT": {"CONTRACT_CHANGE", "CURRENTNESS_CHANGE"},
    "CAPABILITY": {"CAPABILITY_CHANGE", "CURRENTNESS_CHANGE"},
    "CURRENTNESS": {"CURRENTNESS_CHANGE"},
    "RAG": {"RAG_RELEASE", "CURRENTNESS_CHANGE"},
    "EVAL": {"CONTRACT_CHANGE"},
    "DOCUMENTATION": {"SOURCE_CHANGE", "CURRENTNESS_CHANGE"},
}
@dataclass(frozen=True)
class RequiredFormalizationItem:
    artifact_id: str
    path: str
    classification: str
    reason: str
    triggers: Tuple[str, ...]
@dataclass(frozen=True)
class RequiredFormalizationSet:
    manifest_digest: str
    registry_digest: str
    items: Tuple[RequiredFormalizationItem, ...]
    set_digest: str
    schema_id: str = SCHEMA_ID
    def to_dict(self) -> dict[str, Any]: return asdict(self)
def _trigger_set(manifest: ArchitectureFormalizationManifest) -> set[str]:
    result=set(_CHANGE_TRIGGERS[manifest.change_class])
    if manifest.semantic_owner_delta: result.add("SEMANTIC_OWNER_CHANGE")
    if manifest.rag_delta.required: result.add("RAG_RELEASE")
    if manifest.currentness_invalidations: result.add("CURRENTNESS_CHANGE")
    return result
def derive_required_formalization_set(manifest: ArchitectureFormalizationManifest, registry: FormalizationRegistry) -> RequiredFormalizationSet:
    manifest.validate(registry); registry.validate()
    explicit={item.artifact_id:item for item in manifest.formalization_updates}; triggers=_trigger_set(manifest); rows=[]
    for artifact_id, artifact in registry.by_id().items():
        exp=explicit.get(artifact_id); matched=tuple(sorted(set(artifact.refresh_triggers).intersection(triggers)))
        if exp is not None: rows.append(RequiredFormalizationItem(artifact_id,artifact.path,exp.operation,exp.reason,matched))
        elif matched: rows.append(RequiredFormalizationItem(artifact_id,artifact.path,"VALIDATE_ONLY","registry refresh trigger matched",matched))
    rows=tuple(sorted(rows,key=lambda x:x.artifact_id))
    payload={"schema_id":SCHEMA_ID,"manifest_digest":manifest.manifest_digest,"registry_digest":registry.registry_digest,"items":[asdict(x) for x in rows]}
    digest=domain_digest(DIGEST_DOMAIN,payload)
    return RequiredFormalizationSet(manifest.manifest_digest,registry.registry_digest,rows,digest)
