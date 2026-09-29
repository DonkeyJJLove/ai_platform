"""Value objects shared by the v1.5 architecture formalization manifest."""
from dataclasses import dataclass
from typing import Tuple
from .formalization_registry import FormalizationRegistryError,_id,_text,_tuple_text,validate_repository,validate_sha40,validate_sha256
LAYERS=frozenset("SYSTEM_CONTEXT CONSTITUTION_AND_GOVERNANCE EVIDENCE_AND_EPISTEMIC_PLANE EVOLUTIONARY_EPOCH GOVERNED_SELF_IMPLEMENTATION AUTHORITY_AND_EFFECT REPOSITORY_MUTATION FLEET_AND_SWARM TRUSTED_RUNTIME OBSERVABILITY_AND_RECONCILIATION CODE_PERCEPTION ARCHITECTURE_PROJECTION STARTUP_EVOLUTION TARGET_BEAN_FACTORY QUARANTINED_AND_NONCANONICAL".split())
FORMALIZATION_OPERATIONS=frozenset("UPDATE REGENERATE ADD SUPERSEDE VALIDATE_ONLY NOT_APPLICABLE".split());OWNER_OPERATIONS=frozenset("ADD UPDATE REPLACE REMOVE VALIDATE_ONLY".split())
class ArchitectureFormalizationManifestError(FormalizationRegistryError):pass
@dataclass(frozen=True)
class BaselineIdentity:
 repository:str;branch:str;head:str;tree:str
 def validate(s):validate_repository(s.repository);_text(s.branch,"branch",limit=256);validate_sha40(s.head,"head");validate_sha40(s.tree,"tree");return s
@dataclass(frozen=True)
class EvolutionDeltaRef:
 ref:str;digest:str
 def validate(s):_text(s.ref,"source_evolution_delta.ref");validate_sha256(s.digest,"source_evolution_delta.digest");return s
@dataclass(frozen=True)
class LayerBinding:
 concept:str;layers:Tuple[str,...];new_top_level_layer_required:bool=False
 def validate(s):
  _id(s.concept,"concept");_tuple_text(s.layers,"layers")
  if not s.layers or not set(s.layers)<=LAYERS:raise ArchitectureFormalizationManifestError("invalid layer binding")
  if s.new_top_level_layer_required is not False:raise ArchitectureFormalizationManifestError("new top-level layer")
  return s
@dataclass(frozen=True)
class SemanticOwnerDelta:
 concept:str;primary:str|None;secondary:Tuple[str,...];operation:str
 def validate(s):
  _id(s.concept,"concept");_tuple_text(s.secondary,"secondary")
  if s.primary is not None:_text(s.primary,"primary")
  if s.operation not in OWNER_OPERATIONS or (s.operation in {"ADD","UPDATE","REPLACE"} and not s.primary):raise ArchitectureFormalizationManifestError("invalid owner mutation")
  return s
@dataclass(frozen=True)
class FormalizationUpdate:
 artifact_id:str;operation:str;reason:str
 def validate(s):
  _id(s.artifact_id,"artifact_id");_text(s.reason,"reason")
  if s.operation not in FORMALIZATION_OPERATIONS:raise ArchitectureFormalizationManifestError("invalid operation")
  if s.operation=="NOT_APPLICABLE" and len(s.reason.strip())<8:raise ArchitectureFormalizationManifestError("NOT_APPLICABLE needs reason")
  return s
@dataclass(frozen=True)
class MigrationPlan:
 steps:Tuple[str,...];compatibility_adapter:str|None;exit_condition:str
 def validate(s,name):
  _tuple_text(s.steps,name+".steps");_text(s.exit_condition,name+".exit")
  if not s.steps:raise ArchitectureFormalizationManifestError("steps required")
  if s.compatibility_adapter is not None:_text(s.compatibility_adapter,name+".adapter")
  return s
@dataclass(frozen=True)
class DiscoverabilityPlan:
 bootstrap_routes:Tuple[str,...];probe_questions:Tuple[str,...];max_reads_to_owner:int
 def validate(s):
  _tuple_text(s.bootstrap_routes,"routes");_tuple_text(s.probe_questions,"probes")
  if isinstance(s.max_reads_to_owner,bool) or not isinstance(s.max_reads_to_owner,int) or not 1<=s.max_reads_to_owner<=16:raise ArchitectureFormalizationManifestError("invalid max reads")
  if s.probe_questions and not s.bootstrap_routes:raise ArchitectureFormalizationManifestError("probes need route")
  return s
@dataclass(frozen=True)
class RagDelta:
 required:bool;record_ids:Tuple[str,...];retrieval_probes:Tuple[str,...]
 def validate(s):
  if type(s.required) is not bool:raise ArchitectureFormalizationManifestError("required invalid")
  _tuple_text(s.record_ids,"record_ids");_tuple_text(s.retrieval_probes,"retrieval_probes")
  if s.required and (not s.record_ids or not s.retrieval_probes):raise ArchitectureFormalizationManifestError("RAG records/probes required")
  return s
