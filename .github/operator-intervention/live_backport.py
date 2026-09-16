from pathlib import Path
import hashlib
import subprocess


def replace_exact(path, old, new, label):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}_CARDINALITY={count}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

replace_exact(
    'cyber_lion/mission_control/operator_control.py',
    '''    cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=? WHERE mission_id=? AND state='READY'",(int(generation),mission_id))
    if "control_epoch" in cols:conn.execute("UPDATE mission_execution_assignments SET control_epoch=? WHERE mission_id=? AND state='READY'",(int(state["control_epoch"]),mission_id))
    if "dispatch_authority" in cols:conn.execute("UPDATE mission_execution_assignments SET dispatch_authority=? WHERE mission_id=? AND state='READY'",(authority_owner,mission_id))
    return {"rebound_ready":int(cur.rowcount)}''',
    '''    has_epoch="control_epoch" in cols;has_authority="dispatch_authority" in cols
    if has_epoch and has_authority:
        cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=?,control_epoch=?,dispatch_authority=? WHERE mission_id=? AND state='READY'",(int(generation),int(state["control_epoch"]),authority_owner,mission_id))
    elif has_epoch:
        cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=?,control_epoch=? WHERE mission_id=? AND state='READY'",(int(generation),int(state["control_epoch"]),mission_id))
    elif has_authority:
        cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=?,dispatch_authority=? WHERE mission_id=? AND state='READY'",(int(generation),authority_owner,mission_id))
    else:
        cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=? WHERE mission_id=? AND state='READY'",(int(generation),mission_id))
    return {"rebound_ready":int(cur.rowcount)}''',
    'REBIND_LIVE_HARDENING',
)

replace_exact(
    'cyber_lion/mission_control/operator_control.py',
    '''                cols={r[1] for r in conn.execute("PRAGMA table_info(mission_execution_assignments)")};values={"assignment_id":new_id,"mission_id":cmd.mission_id,"phase_id":old["phase_id"],"logical_drone_id":old["logical_drone_id"],"material_drone_id":material,"input_digest":old["input_digest"],"input_json":old["input_json"],"state":"READY","lease_generation":generation,"created_at":now_fn(),"claimed_at":None,"finished_at":None}
                if "control_epoch" in cols:values["control_epoch"]=int(current["control_epoch"])
                if "context_revision" in cols:values["context_revision"]=int(current["context_revision"])
                if "plan_revision" in cols:values["plan_revision"]=int(current["plan_revision"])
                if "dispatch_authority" in cols:values["dispatch_authority"]=principal_id
                conn.execute("INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,created_at,claimed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(new_id,cmd.mission_id,old["phase_id"],old["logical_drone_id"],material,old["input_digest"],old["input_json"],"READY",generation,values["created_at"],None,None))
                if "control_epoch" in cols:conn.execute("UPDATE mission_execution_assignments SET control_epoch=? WHERE assignment_id=?",(int(current["control_epoch"]),new_id))
                if "context_revision" in cols:conn.execute("UPDATE mission_execution_assignments SET context_revision=? WHERE assignment_id=?",(int(current["context_revision"]),new_id))
                if "plan_revision" in cols:conn.execute("UPDATE mission_execution_assignments SET plan_revision=? WHERE assignment_id=?",(int(current["plan_revision"]),new_id))
                if "dispatch_authority" in cols:conn.execute("UPDATE mission_execution_assignments SET dispatch_authority=? WHERE assignment_id=?",(principal_id,new_id))
                result={"previous_assignment_id":assignment_id,"assignment_id":new_id,"material_drone_id":material,"state":"READY","control_epoch":current["control_epoch"],"driver_fence":fence,"lease_generation":generation}''',
    '''                cols={r[1] for r in conn.execute("PRAGMA table_info(mission_execution_assignments)")}
                required={"control_epoch","context_revision","plan_revision","dispatch_authority"}
                if not required.issubset(cols):raise ValueError("operator assignment schema unavailable")
                conn.execute("INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,control_epoch,context_revision,plan_revision,dispatch_authority,created_at,claimed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(new_id,cmd.mission_id,old["phase_id"],old["logical_drone_id"],material,old["input_digest"],old["input_json"],"READY",generation,int(current["control_epoch"]),int(current["context_revision"]),int(current["plan_revision"]),principal_id,now_fn(),None,None))
                result={"previous_assignment_id":assignment_id,"assignment_id":new_id,"material_drone_id":material,"state":"READY","control_epoch":current["control_epoch"],"driver_fence":fence,"lease_generation":generation}''',
    'REASSIGN_LIVE_HARDENING',
)

operator = Path('cyber_lion/mission_control/operator_control.py')
sha = hashlib.sha256(operator.read_bytes()).hexdigest()
expected = 'bb54522751a8ff92bf7769e7a355270c61a62db882130582e1fa25e4f5440179'
if sha != expected:
    raise SystemExit(f'LIVE_OPERATOR_SHA_MISMATCH={sha}')

replace_exact(
    'tools/lion_effect_admission_broker.py',
    'e6d609f709f8ca5c5adbe0f4699fb704867d55066794219d5ebd75f5b893af86',
    expected,
    'RESTART_MANIFEST_LIVE_BINDING',
)

expected_paths={
    'cyber_lion/mission_control/operator_control.py',
    'tools/lion_effect_admission_broker.py',
}
actual=set(subprocess.check_output(['git','diff','--name-only'],text=True).splitlines())
if actual != expected_paths:
    raise SystemExit('UNEXPECTED_DIFF='+','.join(sorted(actual)))
print('LIVE_HARDENING_BACKPORT=PASS')
print('OPERATOR_CONTROL_SHA256='+sha)
