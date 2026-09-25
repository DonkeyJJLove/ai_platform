"""Non-effectful ArchitectureFormalizationManifest sidecar for EvolutionDelta."""
from dataclasses import asdict,dataclass,replace
from typing import Any,Tuple
from .formalization_registry import FormalizationRegistry,_id,_tuple_text,domain_digest,validate_sha256
from .formalization_manifest_types import *
SCHEMA_ID="lion.architecture-formalization-manifest/v1";BINDING_SCHEMA_ID="lion.formalization-proposal-binding/v1"
DIGEST_DOMAIN=b"LION/ARCHITECTURE-FORMALIZATION-MANIFEST/1\0";BINDING_DIGEST_DOMAIN=b"LION/FORMALIZATION-PROPOSAL-BINDING/1\0"
AUTHORITY_EFFECT=EXECUTION_EFFECT="NONE"
CHANGE_CLASSES=frozenset("ARCHITECTURE_CONCEPT MIXED_ARCHITECTURE SEMANTIC_OWNER FLOW CONTRACT CAPABILITY CURRENTNESS RAG EVAL DOCUMENTATION".split())
GLOBAL_CHANGE_CLASSES=frozenset("ARCHITECTURE_CONCEPT MIXED_ARCHITECTURE SEMANTIC_OWNER FLOW".split())
GLOBAL_REQUIRED_ARTIFACTS=frozenset("semantic-owners contract-catalog capability-catalog architecture-projection event-state-catalog gap-projection evolution-evals discoverability-bootstrap rag-routing currentness-carriers".split())
@dataclass(frozen=True)
class ArchitectureFormalizationManifest:
 manifest_id:str;baseline:BaselineIdentity;source_evolution_delta:EvolutionDeltaRef;change_class:str;affected_concepts:Tuple[str,...];layer_bindings:Tuple[LayerBinding,...];semantic_owner_delta:Tuple[SemanticOwnerDelta,...];formalization_updates:Tuple[FormalizationUpdate,...];currentness_invalidations:Tuple[str,...];migration:MigrationPlan;rollback:MigrationPlan;tests_required:Tuple[str,...];evals_required:Tuple[str,...];falsifiers:Tuple[str,...];discoverability:DiscoverabilityPlan;rag_delta:RagDelta;authority_effect:str="NONE";execution_effect:str="NONE";manifest_digest:str="";schema_id:str=SCHEMA_ID
 def canonical_payload(s):d=asdict(s);d.pop("manifest_digest",None);return d
 def compute_digest(s):return domain_digest(DIGEST_DOMAIN,s.canonical_payload())
 def validate(s,registry:FormalizationRegistry,*,require_digest=True):
  registry.validate();_id(s.manifest_id,"manifest_id");s.baseline.validate();s.source_evolution_delta.validate()
  if s.schema_id!=SCHEMA_ID or s.change_class not in CHANGE_CLASSES:raise ArchitectureFormalizationManifestError("schema/change class")
  _tuple_text(s.affected_concepts,"affected_concepts")
  if not s.affected_concepts or type(s.layer_bindings) is not tuple or not s.layer_bindings:raise ArchitectureFormalizationManifestError("concept/layer required")
  for x in s.layer_bindings:x.validate()
  for x in s.semantic_owner_delta:x.validate()
  for x in s.formalization_updates:x.validate()
  owners=[x.concept for x in s.semantic_owner_delta];updates=[x.artifact_id for x in s.formalization_updates]
  if len(owners)!=len(set(owners)):raise ArchitectureFormalizationManifestError("duplicate semantic owner")
  if len(updates)!=len(set(updates)):raise ArchitectureFormalizationManifestError("duplicate formalization update")
  known=set(registry.by_id())
  if not set(updates)<=known:raise ArchitectureFormalizationManifestError("unknown formalization artifact")
  if s.change_class in GLOBAL_CHANGE_CLASSES:
   missing=GLOBAL_REQUIRED_ARTIFACTS-set(updates)
   if missing:raise ArchitectureFormalizationManifestError(f"global analysis incomplete:{sorted(missing)}")
  _tuple_text(s.currentness_invalidations,"currentness_invalidations")
  if not set(s.currentness_invalidations)<=known:raise ArchitectureFormalizationManifestError("unknown invalidation")
  material={x.artifact_id for x in s.formalization_updates if x.operation in {"UPDATE","REGENERATE","ADD","SUPERSEDE"}}
  if not material<=set(s.currentness_invalidations)|{"evolution-evals","discoverability-bootstrap"}:raise ArchitectureFormalizationManifestError("material update lacks invalidation")
  s.migration.validate("migration");s.rollback.validate("rollback")
  for n,v in (("tests",s.tests_required),("evals",s.evals_required),("falsifiers",s.falsifiers)):_tuple_text(v,n)
  if not s.tests_required or not s.evals_required or not s.falsifiers:raise ArchitectureFormalizationManifestError("tests/evals/falsifiers required")
  s.discoverability.validate();s.rag_delta.validate()
  if s.authority_effect!="NONE" or s.execution_effect!="NONE":raise ArchitectureFormalizationManifestError("effect forbidden")
  if require_digest:
   validate_sha256(s.manifest_digest,"manifest_digest")
   if s.manifest_digest!=s.compute_digest():raise ArchitectureFormalizationManifestError("manifest digest mismatch")
  elif s.manifest_digest:validate_sha256(s.manifest_digest,"manifest_digest")
  return s
 def sealed(s,registry):s.validate(registry,require_digest=False);return replace(s,manifest_digest=s.compute_digest()).validate(registry)
@dataclass(frozen=True)
class FormalizationProposalBinding:
 binding_id:str;proposal_digest:str;formalization_manifest_digest:str;authority_effect:str="NONE";execution_effect:str="NONE";binding_digest:str="";schema_id:str=BINDING_SCHEMA_ID
 def canonical_payload(s):d=asdict(s);d.pop("binding_digest",None);return d
 def compute_digest(s):return domain_digest(BINDING_DIGEST_DOMAIN,s.canonical_payload())
 def validate(s,*,require_digest=True):
  if s.schema_id!=BINDING_SCHEMA_ID:raise ArchitectureFormalizationManifestError("binding schema")
  _id(s.binding_id,"binding_id");validate_sha256(s.proposal_digest,"proposal_digest");validate_sha256(s.formalization_manifest_digest,"formalization_manifest_digest")
  if s.authority_effect!="NONE" or s.execution_effect!="NONE":raise ArchitectureFormalizationManifestError("binding effect")
  if require_digest:
   validate_sha256(s.binding_digest,"binding_digest")
   if s.binding_digest!=s.compute_digest():raise ArchitectureFormalizationManifestError("binding digest mismatch")
  return s
 def sealed(s):s.validate(require_digest=False);return replace(s,binding_digest=s.compute_digest()).validate()
