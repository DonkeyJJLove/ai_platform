"""Effect-free repository convergence planner. No git command is executed here."""
from dataclasses import dataclass
@dataclass(frozen=True)
class RepositoryObservation:
    instance_id:str; repository:str; head:str; tree:str; dirty:bool; storage_identity:str; runtime_bound:bool=False
@dataclass(frozen=True)
class SyncPlan:
    instance_id:str; action:str; reason:str; effect:str="NONE"
def plan_sync(observations,remote_heads):
    if type(observations) is not tuple or type(remote_heads) is not dict: raise ValueError("immutable observations and remote map required")
    seen_storage={};out=[]
    for o in observations:
        if type(o) is not RepositoryObservation: raise ValueError("exact observation required")
        if o.storage_identity in seen_storage:
            out.append(SyncPlan(o.instance_id,"ALIAS_NO_ACTION",f"shared storage with {seen_storage[o.storage_identity]}"));continue
        seen_storage[o.storage_identity]=o.instance_id
        remote=remote_heads.get(o.repository)
        if remote is None: out.append(SyncPlan(o.instance_id,"DEFER","remote identity unknown"));continue
        rhead,rtree=remote
        if o.dirty: out.append(SyncPlan(o.instance_id,"PRESERVE_DIRTY","operator changes protected"));continue
        if o.runtime_bound: out.append(SyncPlan(o.instance_id,"PRESERVE_RUNTIME_BOUND","runtime source requires separate rebind"));continue
        if o.head==rhead and o.tree==rtree: out.append(SyncPlan(o.instance_id,"NO_ACTION","exact remote match"));continue
        if o.head==rhead and o.tree!=rtree: out.append(SyncPlan(o.instance_id,"BLOCK","same head with different tree"));continue
        out.append(SyncPlan(o.instance_id,"RECONCILE_ANCESTRY","never force/reset from head mismatch"))
    return tuple(out)
