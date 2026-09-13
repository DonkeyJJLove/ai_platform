from dataclasses import dataclass
@dataclass(frozen=True)
class LocalCloneObservation:instance_id:str;repository:str;path:str;dirty:bool;ahead:int;behind:int;detached:bool=False;historical:bool=False
def plan_local_sync(rows):
    out=[]
    for x in rows:
        if x.dirty:a='PRESERVE_DIRTY'
        elif x.detached or x.historical:a='PRESERVE_HISTORICAL'
        elif x.ahead and x.behind:a='PRESERVE_DIVERGED'
        elif x.ahead:a='PRESERVE_AHEAD'
        elif x.behind:a='FAST_FORWARD_ELIGIBLE'
        else:a='NO_ACTION'
        out.append((x.instance_id,a))
    return tuple(out)
