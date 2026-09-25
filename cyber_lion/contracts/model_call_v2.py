"""Compatible successor projection for lion.model-call/v2. Does not mutate v1 storage."""
from dataclasses import asdict,dataclass,replace
from hashlib import sha256
import json,re
SCHEMA_ID="lion.model-call/v2";AUTHORITY_EFFECT="NONE"
TRANSPORTS=frozenset({"LOCAL","SENTINELX_MEDIATED_SAAS","CHATGPT_OPENAI_SECURE_MCP_TUNNEL","CHATGPT_FIREFOX_PROJECT_MEDIATED","OTHER_MEDIATED"})
HEX=re.compile(r"^[0-9a-f]{64}$")
class ModelCallV2Error(ValueError):pass
def _t(v,n):
    if not isinstance(v,str) or not v.strip():raise ModelCallV2Error(n)
    return v
def _h(v,n):
    if not isinstance(v,str) or not HEX.fullmatch(v):raise ModelCallV2Error(n)
    return v
@dataclass(frozen=True)
class ModelCallV2:
    model_call_id:str;mission_id:str;phase_id:str;task_id:str;assignment_id:str;invocation_ref:str;attempt_ref:str;provider_ref:str;model_release_ref:str;transport_profile_ref:str;causal_group_ref:str;requested_capability:str;transport:str;input_digest:str|None;result_digest:str|None;state:str;authority_effect:str="NONE";record_digest:str="";schema_id:str=SCHEMA_ID
    def payload(self):d=asdict(self);d.pop("record_digest",None);return d
    def compute_digest(self):return sha256(b"LION/MODEL-CALL-V2/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def validate(self,require_digest=True):
        for n in ("model_call_id","mission_id","phase_id","task_id","assignment_id","invocation_ref","attempt_ref","provider_ref","model_release_ref","transport_profile_ref","causal_group_ref","requested_capability","state"):_t(getattr(self,n),n)
        if self.transport not in TRANSPORTS or self.authority_effect!="NONE" or self.schema_id!=SCHEMA_ID:raise ModelCallV2Error("transport/schema/authority")
        if self.input_digest is not None:_h(self.input_digest,"input_digest")
        if self.result_digest is not None:_h(self.result_digest,"result_digest")
        if require_digest:
            _h(self.record_digest,"record_digest")
            if self.record_digest!=self.compute_digest():raise ModelCallV2Error("record digest")
        return self
    def sealed(self):return replace(self,record_digest=self.compute_digest()).validate()
def project_v1_to_v2(v1:dict,*,invocation_ref:str,attempt_ref:str,provider_ref:str,model_release_ref:str,transport_profile_ref:str,causal_group_ref:str)->ModelCallV2:
    if not isinstance(v1,dict):raise ModelCallV2Error("v1 record")
    transport_map={"LOCAL":"LOCAL","CHATGPT_OPENAI_SECURE_MCP_TUNNEL":"CHATGPT_OPENAI_SECURE_MCP_TUNNEL","CHATGPT_FIREFOX_PROJECT_MEDIATED":"CHATGPT_FIREFOX_PROJECT_MEDIATED"}
    return ModelCallV2(
        model_call_id=v1["model_call_id"],mission_id=v1["mission_id"],phase_id=v1["phase_id"],task_id=v1["task_id"],assignment_id=v1["assignment_id"],
        invocation_ref=invocation_ref,attempt_ref=attempt_ref,provider_ref=provider_ref,model_release_ref=model_release_ref,transport_profile_ref=transport_profile_ref,causal_group_ref=causal_group_ref,
        requested_capability=v1["requested_capability"],transport=transport_map.get(v1.get("transport"),"OTHER_MEDIATED"),input_digest=v1.get("input_digest"),result_digest=v1.get("result_digest"),state=v1["state"]
    ).sealed()
# Absence of a v1 model-call record is not evidence that no SaaS invocation occurred.
