"""Per-competency coordinator evidence; intentionally no aggregate quality score."""
from dataclasses import dataclass
from typing import Tuple
COMPETENCIES=(
"PHASE_CONTRACT_INTERPRETATION","CAPABILITY_GAP_DETECTION","ROLE_AND_CONSTRAINT_ASSIGNMENT","MODEL_ROUTE_WITHIN_POLICY","WAIT_OR_ACT_DISCRIMINATION","TRANSPORT_VS_COGNITION_STATE","UNKNOWN_RECOVERY","DUAL_LEG_CORRELATION","STALE_RESULT_REJECTION","RECONCILIATION_NO_FALSE_PASS")
RESULTS=frozenset({"PASS","FAIL","PARTIAL","UNKNOWN"});AUTHORITY_EFFECT="NONE"
class CoordinatorCompetencyError(ValueError):pass
@dataclass(frozen=True)
class CompetencyEvidence:
    competency:str;task_refs:Tuple[str,...];evidence_refs:Tuple[str,...];result:str
    def validate(self):
        if self.competency not in COMPETENCIES or self.result not in RESULTS or type(self.task_refs) is not tuple or type(self.evidence_refs) is not tuple or not self.task_refs or not self.evidence_refs:raise CoordinatorCompetencyError("competency evidence")
        return self
@dataclass(frozen=True)
class CoordinatorCompetencyProfile:
    profile_id:str;model_release_ref:str;records:Tuple[CompetencyEvidence,...];authority_effect:str="NONE"
    def validate(self):
        if not isinstance(self.profile_id,str) or not self.profile_id or not isinstance(self.model_release_ref,str) or not self.model_release_ref or self.authority_effect!="NONE":raise CoordinatorCompetencyError("profile")
        if type(self.records) is not tuple:raise CoordinatorCompetencyError("records")
        for r in self.records:r.validate()
        ids=[r.competency for r in self.records]
        if len(ids)!=len(set(ids)) or set(ids)!=set(COMPETENCIES):raise CoordinatorCompetencyError("each competency requires separate evidence")
        return self
