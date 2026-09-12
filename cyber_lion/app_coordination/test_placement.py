"""Pure test-placement and semantic-cache planner for a shared hardware pool."""
from dataclasses import dataclass
from hashlib import sha256
import json
@dataclass(frozen=True)
class TestSpec:
    test_id:str; tier:str; source_digest:str; environment_digest:str; currentness_sensitive:bool=False; exclusive_store:str|None=None; heavy:bool=False
@dataclass(frozen=True)
class Placement:
    test_id:str; executor_class:str; cache_key:str|None; parallelism:int; reason:str

def plan_test(spec,*,environment_qualified=True):
    if type(spec) is not TestSpec: raise ValueError("exact TestSpec required")
    if spec.tier not in {"T1","T2","T3","T4","T5","T6"}: raise ValueError("tier")
    if not environment_qualified: return Placement(spec.test_id,"DEFER",None,0,"environment unqualified")
    if spec.tier=="T5": return Placement(spec.test_id,"REMOTE_EXACT_HEAD",None,1,"platform CI evidence")
    if spec.tier=="T6": return Placement(spec.test_id,"AUTHORITY_BOUND",None,0,"separate admission required")
    key=None if spec.currentness_sensitive else sha256(json.dumps([spec.source_digest,spec.environment_digest,spec.tier],separators=(",",":")).encode()).hexdigest()
    par=1 if spec.exclusive_store or spec.heavy else 4
    return Placement(spec.test_id,"LOCAL_DETERMINISTIC",key,par,"bounded local deterministic test")
