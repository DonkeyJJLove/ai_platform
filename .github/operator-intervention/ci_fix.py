from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import subprocess


def replace_exact(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}_CARDINALITY={count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_exact(
    "cyber_lion/mission_control/operator_control.py",
    '''    sets=["lease_generation=?"];args=[int(generation)]
    if "control_epoch" in cols:sets.append("control_epoch=?");args.append(int(state["control_epoch"]))
    if "dispatch_authority" in cols:sets.append("dispatch_authority=?");args.append(authority_owner)
    args.append(mission_id);cur=conn.execute("UPDATE mission_execution_assignments SET "+','.join(sets)+" WHERE mission_id=? AND state='READY'",tuple(args));return {"rebound_ready":int(cur.rowcount)}''',
    '''    cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=? WHERE mission_id=? AND state='READY'",(int(generation),mission_id))
    if "control_epoch" in cols:conn.execute("UPDATE mission_execution_assignments SET control_epoch=? WHERE mission_id=? AND state='READY'",(int(state["control_epoch"]),mission_id))
    if "dispatch_authority" in cols:conn.execute("UPDATE mission_execution_assignments SET dispatch_authority=? WHERE mission_id=? AND state='READY'",(authority_owner,mission_id))
    return {"rebound_ready":int(cur.rowcount)}''',
    "REBIND_SQL",
)
replace_exact(
    "cyber_lion/mission_control/operator_control.py",
    '''                names=list(values);conn.execute("INSERT INTO mission_execution_assignments("+",".join(names)+") VALUES("+",".join("?" for _ in names)+")",tuple(values[n] for n in names));result={"previous_assignment_id":assignment_id,"assignment_id":new_id,"material_drone_id":material,"state":"READY","control_epoch":current["control_epoch"],"driver_fence":fence,"lease_generation":generation}''',
    '''                conn.execute("INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,created_at,claimed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(new_id,cmd.mission_id,old["phase_id"],old["logical_drone_id"],material,old["input_digest"],old["input_json"],"READY",generation,values["created_at"],None,None))
                if "control_epoch" in cols:conn.execute("UPDATE mission_execution_assignments SET control_epoch=? WHERE assignment_id=?",(int(current["control_epoch"]),new_id))
                if "context_revision" in cols:conn.execute("UPDATE mission_execution_assignments SET context_revision=? WHERE assignment_id=?",(int(current["context_revision"]),new_id))
                if "plan_revision" in cols:conn.execute("UPDATE mission_execution_assignments SET plan_revision=? WHERE assignment_id=?",(int(current["plan_revision"]),new_id))
                if "dispatch_authority" in cols:conn.execute("UPDATE mission_execution_assignments SET dispatch_authority=? WHERE assignment_id=?",(principal_id,new_id))
                result={"previous_assignment_id":assignment_id,"assignment_id":new_id,"material_drone_id":material,"state":"READY","control_epoch":current["control_epoch"],"driver_fence":fence,"lease_generation":generation}''',
    "REASSIGN_SQL",
)

replace_exact(
    "tools/lion_local_intelligence_runtime.py",
    "from cyber_lion.mission_control import global_scheduler as mission_scheduler\n",
    "",
    "LOCAL_RUNTIME_SCHEDULER_IMPORT",
)
replace_exact(
    "tools/lion_local_intelligence_runtime.py",
    "def digest(v):return hashlib.sha256(canon(v)).hexdigest()\n",
    "def digest(v):return hashlib.sha256(canon(v)).hexdigest()\n"
    "def _assignment_lease_valid(assignment,observed_at):\n"
    "    expires=(assignment or {}).get('lease_expires_at') if isinstance(assignment,dict) else None\n"
    "    if not expires:return False\n"
    "    now_dt=datetime.fromisoformat(str(observed_at).replace('Z','+00:00'));exp_dt=datetime.fromisoformat(str(expires).replace('Z','+00:00'))\n"
    "    if now_dt.tzinfo is None:now_dt=now_dt.replace(tzinfo=timezone.utc)\n"
    "    if exp_dt.tzinfo is None:exp_dt=exp_dt.replace(tzinfo=timezone.utc)\n"
    "    return now_dt<exp_dt\n",
    "LOCAL_RUNTIME_LEASE_HELPER",
)
replace_exact(
    "tools/lion_local_intelligence_runtime.py",
    "            if not mission_scheduler.assignment_lease_valid(claimed,observed):raise ValueError('local assignment lease expired before effect')",
    "            if not _assignment_lease_valid(claimed,observed):raise ValueError('local assignment lease expired before effect')",
    "LOCAL_RUNTIME_LEASE_CALL",
)

operator_path = Path("cyber_lion/mission_control/operator_control.py")
operator_sha = hashlib.sha256(operator_path.read_bytes()).hexdigest()
expected_sha = "e6d609f709f8ca5c5adbe0f4699fb704867d55066794219d5ebd75f5b893af86"
if operator_sha != expected_sha:
    raise SystemExit(f"OPERATOR_CONTROL_SHA_DRIFT={operator_sha}")
replace_exact(
    "tools/lion_effect_admission_broker.py",
    "7ed9c6da9f5aa73f1079aae3581c8fdc6666be00982ec2d5f817eba0382ec337",
    expected_sha,
    "OPERATOR_CONTROL_MANIFEST_BINDING",
)

runtime_path = Path("tools/lion_local_intelligence_runtime.py")
tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
bad: list[str] = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        names = [alias.name for alias in node.names]
    elif isinstance(node, ast.ImportFrom):
        names = [node.module or ""]
    else:
        continue
    bad.extend(name for name in names if name.startswith("cyber_lion.mission_control"))
if bad:
    raise SystemExit("LOCAL_RUNTIME_AUTHORITY_IMPORT=" + ",".join(sorted(set(bad))))

expected_paths = {
    "cyber_lion/mission_control/operator_control.py",
    "tools/lion_effect_admission_broker.py",
    "tools/lion_local_intelligence_runtime.py",
}
actual_paths = set(subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines())
if actual_paths != expected_paths:
    raise SystemExit("SOURCE_DIFF_SET=" + ",".join(sorted(actual_paths)))

print("SOURCE_EDITS=PASS")
print("OPERATOR_CONTROL_SHA256=" + operator_sha)
print("LOCAL_RUNTIME_AUTHORITY_IMPORT=NONE")
print("SOURCE_DIFF_SET=PASS")
