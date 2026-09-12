"""Bounded proposal-only local model adapter; provider is an explicit dependency."""
from dataclasses import dataclass
from hashlib import sha256
import json
from .hybrid_routing import TaskEnvelope,RouteDecision

@dataclass(frozen=True)
class LocalProposal:
    task_id:str; payload_json:str; payload_digest:str; attempts:int; authority_effect:str="NONE"; runtime_effect:str="NONE"

def _parse(raw):
    if type(raw) is not str: raise ValueError("provider output must be text")
    value=json.loads(raw)
    if type(value) is not dict or set(value)!={"proposal"} or type(value["proposal"]) is not str or not value["proposal"].strip(): raise ValueError("proposal schema")
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def materialize_local_proposal(task,decision,provider,*,token_counter,max_output_tokens=256):
    if type(task) is not TaskEnvelope or type(decision) is not RouteDecision: raise ValueError("exact task/decision required")
    task.validate();decision.validate()
    if decision.task_id!=task.task_id or decision.route!="LOCAL": raise ValueError("LOCAL route required")
    if not callable(provider) or not callable(token_counter): raise ValueError("explicit provider/token counter required")
    count=token_counter(task)
    if type(count) is not int or count<0: raise ValueError("token counter")
    if count>task.input_tokens: raise ValueError("measured token count exceeds routed envelope")
    raw=provider(task,max_output_tokens)
    attempts=1
    try: payload=_parse(raw)
    except (ValueError,json.JSONDecodeError):
        repair=provider(task,max_output_tokens)
        attempts=2
        payload=_parse(repair)
    d=sha256(payload.encode()).hexdigest()
    return LocalProposal(task.task_id,payload,d,attempts)
