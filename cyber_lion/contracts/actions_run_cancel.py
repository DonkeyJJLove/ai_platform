from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json, re

_HEX40=re.compile(r"^[0-9a-f]{40}$")

class ActionsRunCancelContractError(RuntimeError): pass

def canonical_json(value: object)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

@dataclass(frozen=True)
class ActionsRunCancelRequest:
    repository:str
    run_id:int
    expected_workflow:str
    expected_event:str
    expected_head_sha:str
    reason_code:str
    request_id:str
    def validate(self)->"ActionsRunCancelRequest":
        if self.repository!="DonkeyJJLove/ai_platform": raise ActionsRunCancelContractError("repository denied")
        if not isinstance(self.run_id,int) or isinstance(self.run_id,bool) or self.run_id<=0: raise ActionsRunCancelContractError("run_id invalid")
        if not self.expected_workflow or not self.expected_event or not self.reason_code or not self.request_id: raise ActionsRunCancelContractError("identity invalid")
        if _HEX40.fullmatch(self.expected_head_sha) is None: raise ActionsRunCancelContractError("expected_head_sha invalid")
        if self.expected_event not in {"issue_comment","workflow_dispatch","pull_request"}: raise ActionsRunCancelContractError("event denied")
        return self
    def payload_digest(self)->str:
        self.validate(); return sha256(b"LION/ACTIONS-RUN-CANCEL-REQUEST/1\0"+canonical_json(asdict(self))).hexdigest()
