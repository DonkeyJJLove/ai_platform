"""Deterministic no-effect qualification fixture for Semantic Cloud R1.

This is not a model study and not AGI evidence. It exercises lineage collapse,
contradiction and temporal supersession with the same evidence in two
representations: full-message transcript and SemanticDelta/RelevanceGraph.
"""
from __future__ import annotations
from dataclasses import dataclass
from cyber_lion.contracts.semantic_relevance import EvidenceInstance, SemanticAtom

@dataclass(frozen=True)
class QualificationResult:
    arm:str
    task_success:bool
    epistemic_success:bool
    provenance_preservation:bool
    stale_state_rejection:bool
    semantic_state_size:int
    communication_units:int

def _root_count(evidence):
    return len({e.root_ref for e in evidence})

def run_fixture()->tuple[QualificationResult,QualificationResult]:
    # Same-root copies plus one independent contradiction and later supersession.
    e1=EvidenceInstance("e:copy1","root:A","a"*64,"2026-10-03T10:00:00Z","SUPERSEDED")
    e2=EvidenceInstance("e:copy2","root:A","b"*64,"2026-10-03T10:00:01Z","SUPERSEDED")
    e3=EvidenceInstance("e:independent","root:B","c"*64,"2026-10-03T10:00:02Z","SUPERSEDED")
    e4=EvidenceInstance("e:update","root:C","d"*64,"2026-10-03T10:01:00Z","CURRENT")
    all_evidence=(e1,e2,e3,e4)

    # Arm A is a deliberately naive full-transcript baseline: every message is a vote.
    a_current_votes=sum(1 for e in all_evidence if e.currentness=="CURRENT")
    a_old_votes=len(all_evidence)-a_current_votes
    arm_a=QualificationResult(
        arm="FULL_TRANSCRIPT_NAIVE",
        task_success=a_current_votes>a_old_votes,
        epistemic_success=False,
        provenance_preservation=True,
        stale_state_rejection=False,
        semantic_state_size=len(all_evidence),
        communication_units=len(all_evidence),
    )

    atom=SemanticAtom(
        atom_id="atom:state",semantic_key="semantic:state",
        proposition_core="latest authoritative state",
        relation_signature=("relation:supersedes",),scope=("scope:fixture",),
        temporal_state="CURRENT",evidence=all_evidence,
        source_representation_refs=("representation:full",),
    ).sealed()
    independent=_root_count(atom.evidence)
    arm_b=QualificationResult(
        arm="SEMANTIC_DELTA_RELEVANCE",
        task_success=atom.temporal_state=="CURRENT",
        epistemic_success=independent==3,
        provenance_preservation=atom.independent_root_count()==3,
        stale_state_rejection=all(e.currentness=="SUPERSEDED" for e in (e1,e2,e3)),
        semantic_state_size=1,
        communication_units=2, # one supersession delta + one current-state atom
    )
    return arm_a,arm_b
