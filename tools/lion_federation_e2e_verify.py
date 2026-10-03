"""Non-effectful federation composition verifier.

The verifier consumes closed, transport-neutral receipts emitted by peer
contracts. It does not import peer repositories, execute providers, mint
authority or promote epistemic classes.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass,replace
from hashlib import sha256
import json,re
from typing import Any,Mapping

SHA=re.compile(r"^[0-9a-f]{64}$")
GIT=re.compile(r"^[0-9a-f]{40}$")
class FederationE2EError(ValueError): pass

def _canon(v:object)->bytes:
 try:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
 except (TypeError,ValueError) as exc:raise FederationE2EError("strict json required") from exc
def _sha(v:Any,n:str)->str:
 if not isinstance(v,str) or SHA.fullmatch(v) is None:raise FederationE2EError(n)
 return v
def _git(v:Any,n:str)->str:
 if not isinstance(v,str) or GIT.fullmatch(v) is None:raise FederationE2EError(n)
 return v
def _text(v:Any,n:str)->str:
 if not isinstance(v,str) or not v.strip() or "\x00" in v:raise FederationE2EError(n)
 return v

@dataclass(frozen=True)
class StructureChainReceipt:
 process_spec_digest:str
 delta_observation_digest:str
 graph_projection_digest:str
 artifact_bytes_sha256:str
 artifact_origin_repository:str
 artifact_origin_head:str
 swarm_roundtrip_digest:str
 authority_effect:str="NONE"
 execution_effect:str="NONE"
 receipt_digest:str=""
 def payload(self):d=asdict(self);d.pop("receipt_digest",None);return d
 def compute(self):return sha256(b"LION/FEDERATION-STRUCTURE-E2E/1\0"+_canon(self.payload())).hexdigest()
 def validate(self,req=True):
  for n in ("process_spec_digest","delta_observation_digest","graph_projection_digest","artifact_bytes_sha256","swarm_roundtrip_digest"):_sha(getattr(self,n),n)
  _text(self.artifact_origin_repository,"artifact_origin_repository");_git(self.artifact_origin_head,"artifact_origin_head")
  if self.authority_effect!="NONE" or self.execution_effect!="NONE":raise FederationE2EError("effects")
  if req and (_sha(self.receipt_digest,"receipt_digest")!=self.compute()):raise FederationE2EError("receipt digest mismatch")
  return self
 def sealed(self):return replace(self,receipt_digest=self.compute()).validate()

@dataclass(frozen=True)
class EvidenceChainReceipt:
 hypothesis_digest:str
 experiment_digest:str
 simulation_result_digest:str
 model_risk_result_digest:str
 epistemic_class:str
 artifact_bytes_sha256:str
 research_index_digest:str
 context_snapshot_digest:str
 context_epoch:int
 authority_effect:str="NONE"
 execution_effect:str="NONE"
 receipt_digest:str=""
 def payload(self):d=asdict(self);d.pop("receipt_digest",None);return d
 def compute(self):return sha256(b"LION/FEDERATION-EVIDENCE-E2E/1\0"+_canon(self.payload())).hexdigest()
 def validate(self,req=True):
  for n in ("hypothesis_digest","experiment_digest","simulation_result_digest","model_risk_result_digest","artifact_bytes_sha256","research_index_digest","context_snapshot_digest"):_sha(getattr(self,n),n)
  if self.simulation_result_digest!=self.model_risk_result_digest:raise FederationE2EError("model risk is not bound to result")
  if self.epistemic_class not in {"SIMULATED","DERIVED"}:raise FederationE2EError("epistemic promotion denied")
  if isinstance(self.context_epoch,bool) or not isinstance(self.context_epoch,int) or self.context_epoch<1:raise FederationE2EError("context_epoch")
  if self.authority_effect!="NONE" or self.execution_effect!="NONE":raise FederationE2EError("effects")
  if req and (_sha(self.receipt_digest,"receipt_digest")!=self.compute()):raise FederationE2EError("receipt digest mismatch")
  return self
 def sealed(self):return replace(self,receipt_digest=self.compute()).validate()

def verify_structure_bundle(bundle:Mapping[str,Any],artifact_bytes:bytes)->StructureChainReceipt:
 required={"process_spec","delta_observation","graph_projection","artifact_identity","swarm_roundtrip"}
 if not isinstance(bundle,Mapping) or set(bundle)!=required:raise FederationE2EError("structure bundle fields")
 ps,delta,graph,aid,swarm=(bundle[x] for x in ("process_spec","delta_observation","graph_projection","artifact_identity","swarm_roundtrip"))
 if not all(isinstance(x,Mapping) for x in (ps,delta,graph,aid,swarm)):raise FederationE2EError("structure bundle objects")
 psd=_sha(ps.get("spec_digest"),"process spec digest")
 dd=_sha(delta.get("observation_digest"),"delta digest")
 if delta.get("process_semantics_digest")!=psd:raise FederationE2EError("delta/process semantics binding")
 gd=_sha(graph.get("projection_digest"),"graph digest")
 if graph.get("upstream_digest")!=dd:raise FederationE2EError("graph/delta binding")
 actual=sha256(artifact_bytes).hexdigest()
 aid_hash=_sha(aid.get("bytes_sha256"),"artifact bytes digest")
 if aid_hash!=actual:raise FederationE2EError("artifact bytes mismatch")
 if aid.get("authority_effect")!="NONE" or aid.get("publication_effect")!="NONE":raise FederationE2EError("artifact effect widening")
 if swarm.get("authority_effect")!="NONE" or swarm.get("execution_effect")!="NONE":raise FederationE2EError("swarm roundtrip effect widening")
 sr=_sha(swarm.get("roundtrip_digest"),"swarm roundtrip digest")
 return StructureChainReceipt(psd,dd,gd,actual,_text(aid.get("origin_repository"),"origin repository"),_git(aid.get("origin_head"),"origin head"),sr).sealed()

def verify_evidence_bundle(bundle:Mapping[str,Any],artifact_bytes:bytes)->EvidenceChainReceipt:
 required={"hypothesis","experiment","simulation","model_risk","artifact_identity","research_index","context_snapshot"}
 if not isinstance(bundle,Mapping) or set(bundle)!=required:raise FederationE2EError("evidence bundle fields")
 h,e,s,risk,aid,index,ctx=(bundle[x] for x in ("hypothesis","experiment","simulation","model_risk","artifact_identity","research_index","context_snapshot"))
 if not all(isinstance(x,Mapping) for x in (h,e,s,risk,aid,index,ctx)):raise FederationE2EError("evidence bundle objects")
 hd=_sha(h.get("digest"),"hypothesis digest");ed=_sha(e.get("digest"),"experiment digest")
 if e.get("hypothesis_ref")!=h.get("hypothesis_id"):raise FederationE2EError("experiment/hypothesis binding")
 if h.get("status")=="CONFIRMED":raise FederationE2EError("fixture hypothesis cannot be promoted to confirmed")
 sd=_sha(s.get("result_digest"),"simulation result digest")
 if risk.get("result_digest")!=sd:raise FederationE2EError("risk/result binding")
 ep=_text(s.get("epistemic_class"),"epistemic_class")
 if ep not in {"SIMULATED","DERIVED"}:raise FederationE2EError("observed-world promotion denied")
 actual=sha256(artifact_bytes).hexdigest()
 if aid.get("bytes_sha256")!=actual:raise FederationE2EError("artifact bytes mismatch")
 if aid.get("authority_effect")!="NONE" or aid.get("publication_effect")!="NONE":raise FederationE2EError("artifact effects")
 idx=_sha(index.get("index_digest"),"research index digest")
 if index.get("authority_effect")!="NONE" or index.get("execution_effect")!="NONE":raise FederationE2EError("research index effects")
 cd=_sha(ctx.get("snapshot_digest"),"context snapshot digest")
 epoch=ctx.get("epoch")
 return EvidenceChainReceipt(hd,ed,sd,sd,ep,actual,idx,cd,epoch).sealed()
