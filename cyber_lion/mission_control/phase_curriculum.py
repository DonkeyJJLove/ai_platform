"""Durable phase curriculum and adaptive evidence composition.

This module learns only from receipt-backed completed phases.  Lessons may
select or compose evidence producers, but never widen authority or manufacture
a completion verdict.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from . import global_scheduler as artifact_store

SCHEMA_VERSION="lion.phase-curriculum/v1"
RESOLVER_VERSION="lion.adaptive-evidence-resolver/1"
LESSON_STATES=frozenset({"OBSERVED","RECEIPT_VERIFIED","REPLAY_VERIFIED","PROMOTED","RETIRED"})
PHASE_CLASSES=frozenset({"LOCAL_DETERMINISTIC","LIVE_CONNECTOR","COGNITIVE_SYNTHESIS","HUMAN_INTENT"})

LOCAL_CURRENTNESS=frozenset({"CURRENT_MISSION_DB","LIVE_SOURCE","LIVE_RUNTIME","ASIS_GRAPH","CAPABILITY_GRAPH","AUTHORITY_GRAPH","DATA_GRAPH","RUNTIME_GRAPH"})
EXTERNAL_CURRENTNESS=frozenset({"LIVE_GIT","LIVE_GITHUB","CURRENT_REGISTRY","LIVE_FIRST","FINAL_CANONICAL_SOURCE","EXACT_CANDIDATE_SOURCE"})
COGNITIVE_OUTPUTS=frozenset({"TARGET_MODEL","SURVIVOR_SET","DISPOSITION_LEDGER","CONTRADICTION_MATRIX","GHOST_STATE_MAP","CURRENTNESS_CONFLICTS","REQUIRED_WORK_SET","CRITICAL_PATH","CONSOLIDATION_DAG"})
LINEAGE_OUTPUTS=frozenset({"LINEAGE_GRAPH","PROVENANCE_MAP","SUPERSESSION_MAP"})
LINEAGE_INGREDIENTS=frozenset({"REPOSITORY_CENSUS","DEPENDENCY_MAP","TASK_LEDGER","MISSION_LEDGER","CAPABILITY_GRAPH","RUNTIME_CONSUMERS"})


def _canon(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)


def digest(value):
    return hashlib.sha256(_canon(value).encode()).hexdigest()


def _json(value,default):
    if isinstance(value,(dict,list)):return value
    try:return json.loads(value or "")
    except Exception:return default


def _contract_sets(contract):
    return (
      set(contract.get("currentness_requirements") or _json(contract.get("currentness_requirements_json"),[])),
      set(contract.get("evidence_requirements") or _json(contract.get("evidence_requirements_json"),[])),
      list(contract.get("completion_predicates") or _json(contract.get("completion_predicates_json"),[])),
    )


def contract_signature(contract):
    currentness,evidence,_=_contract_sets(contract)
    value={
      "execution_class":contract.get("execution_class"),
      "capability_classes":sorted(contract.get("capability_classes") or _json(contract.get("capability_classes_json"),[])),
      "effect_ceiling":contract.get("effect_ceiling"),
      "verify_before_mutate":bool(contract.get("verify_before_mutate")),
      "currentness":sorted(currentness),
      "evidence":sorted(evidence),
    }
    return digest(value)


def classify_contract(contract):
    currentness,evidence,_=_contract_sets(contract)
    if evidence & COGNITIVE_OUTPUTS:
        return "COGNITIVE_SYNTHESIS"
    if currentness & EXTERNAL_CURRENTNESS or evidence & LINEAGE_OUTPUTS:
        return "LIVE_CONNECTOR"
    if currentness <= LOCAL_CURRENTNESS:
        return "LOCAL_DETERMINISTIC"
    return "COGNITIVE_SYNTHESIS"


def migrate(conn,now_fn):
    """Curriculum reuses the existing mission_artifacts store.

    The owning Mission Control migration must materialize global scheduler
    storage first.  This function deliberately creates no new persistence
    surface.
    """
    row=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mission_artifacts'").fetchone()
    if row is None:
        raise ValueError("mission artifact store unavailable")


def _contract_row(conn,mission_id,phase_id):
    row=conn.execute("SELECT * FROM mission_phase_execution_contracts WHERE mission_id=? AND phase_id=?",(mission_id,phase_id)).fetchone()
    return dict(row) if row else None


def _recursive_find(value,wanted):
    target=wanted.lower()
    if isinstance(value,dict):
      for key,item in value.items():
       if str(key).lower()==target:return item
      for item in value.values():
       found=_recursive_find(item,wanted)
       if found is not None:return found
    elif isinstance(value,list):
      for item in value:
       found=_recursive_find(item,wanted)
       if found is not None:return found
    return None


def _phase_evidence(conn,mission_id,phase_id):
    row=conn.execute("SELECT evidence_json,evidence_digest,state,effect_receipt_digest FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id=?",(mission_id,phase_id)).fetchone()
    if row and row["evidence_json"]:
      value=_json(row["evidence_json"],{})
      if isinstance(value,dict):
       return value,row["evidence_digest"],row["effect_receipt_digest"],row["state"]
    rows=conn.execute(
      "SELECT payload_json,payload_digest,observed_at FROM protocol_messages "
      "WHERE mission_id=? AND phase=? AND protocol='EVIDENCE' ORDER BY id DESC",(mission_id,phase_id)
    ).fetchall()
    for item in rows:
      value=_json(item["payload_json"],{})
      if isinstance(value,dict) and value.get("event")=="EPOCH_CLOSURE_EVIDENCE":
       return value,item["payload_digest"],"protocol:"+str(item["observed_at"]),"PASS"
    return {},None,None,None


def _artifact_content(row):
    if not row:return None
    if isinstance(row,dict) and isinstance(row.get("content"),dict):return row["content"]
    try:return _json(row["content_json"],{})
    except Exception:return None


def learn_completed(conn,mission_id,now_fn):
    migrate(conn,now_fn)
    rows=conn.execute(
      "SELECT p.phase_id,p.status,c.* FROM mission_phases p "
      "JOIN mission_phase_execution_contracts c ON c.mission_id=p.mission_id AND c.phase_id=p.phase_id "
      "WHERE p.mission_id=? AND p.status IN ('PASS','COMPLETE') ORDER BY p.ordinal",(mission_id,)
    ).fetchall()
    learned=[]
    for raw in rows:
      row=dict(raw);phase_id=row["phase_id"];contract=row
      currentness,evidence_outputs,_=_contract_sets(contract)
      evidence,evidence_digest,receipt_ref,plan_state=_phase_evidence(conn,mission_id,phase_id)
      if not evidence_digest:continue
      local=bool(evidence.get("local_evidence_producer"))
      producer_ref=evidence.get("producer") or evidence.get("producer_mode")
      producer_kind="LOCAL_DETERMINISTIC" if local else ("SAAS_RECEIPT_BOUND" if evidence.get("epoch_closure_evidence") or evidence.get("request_id") else "GENERIC_RECEIPT")
      state="PROMOTED" if local and plan_state=="PASS" else "RECEIPT_VERIFIED"
      sig=contract_signature(contract)
      lesson_id="lesson-"+hashlib.sha256((mission_id+"|"+phase_id+"|"+sig).encode()).hexdigest()[:32]
      content={
        "lesson_id":lesson_id,"schema_version":SCHEMA_VERSION,"mission_id":mission_id,
        "source_phase_id":phase_id,"phase_class":classify_contract(contract),
        "contract_signature":sig,"contract_digest":contract.get("contract_digest"),
        "currentness":sorted(currentness),"evidence_outputs":sorted(evidence_outputs),
        "producer_kind":producer_kind,"producer_ref":str(producer_ref or ""),
        "evidence_digest":evidence_digest,"receipt_ref":str(receipt_ref or ""),
        "lesson_state":state,"replay_verified":bool(state=="PROMOTED"),
        "authority_effect":"NONE",
      }
      artifact_store.put_artifact(
        conn,mission_id,"PHASE_CURRICULUM_LESSON",content,now_fn,
        phase_id=phase_id,schema_id=SCHEMA_VERSION,authority_effect="NONE",
      )
      learned.append(lesson_id)
    return learned


def lessons(conn,mission_id,states=("PROMOTED","RECEIPT_VERIFIED","REPLAY_VERIFIED")):
    out=[]
    allowed=set(states)
    for artifact in artifact_store.list_artifacts(conn,mission_id):
      if artifact.get("artifact_type")!="PHASE_CURRICULUM_LESSON":continue
      item=_artifact_content(artifact)
      if not isinstance(item,dict) or item.get("lesson_state") not in allowed:continue
      value=dict(item)
      value["artifact_id"]=artifact.get("artifact_id")
      value["artifact_revision"]=artifact.get("revision")
      value["artifact_digest"]=artifact.get("content_digest")
      out.append(value)
    return sorted(out,key=lambda x:(x.get("source_phase_id") or "",x.get("lesson_id") or ""))


def _resolution_recipe(evidence_requirements):
    req=set(evidence_requirements)
    if req==LINEAGE_OUTPUTS:
      return "COMPOSE_LINEAGE_V1",set(LINEAGE_INGREDIENTS)
    if req & COGNITIVE_OUTPUTS:
      return "COGNITIVE_SYNTHESIS",set()
    return None,set()


def _question_meta(question):
    text=str(question or "");pos=text.find("{")
    if pos<0:return None
    try:value=json.loads(text[pos:])
    except Exception:return None
    return value if isinstance(value,dict) else None


def supervisor_request_snapshot(conn,mission_id,phase_id,contract):
    rows=conn.execute(
      "SELECT request_id,status,progress_state,created_at,expires_at,claimed_at,responded_at,response_digest,receipt_digest,question,transport,authority_effect "
      "FROM saas_handoff_requests WHERE mission_id=? ORDER BY created_at DESC",(mission_id,)
    ).fetchall()
    wanted_digest=contract.get("contract_digest")
    for row in rows:
      if row["authority_effect"]!="NONE":continue
      meta=_question_meta(row["question"])
      if not meta or meta.get("mission_id")!=mission_id or meta.get("phase_id")!=phase_id:continue
      if meta.get("contract_digest")!=wanted_digest:continue
      status=str(row["status"] or "")
      if status in {"SUPERSEDED","CANCELLED","FAILED","FAIL"}:continue
      value={
        "request_id":row["request_id"],"status":status,"progress_state":row["progress_state"],
        "created_at":row["created_at"],"expires_at":row["expires_at"],"claimed_at":row["claimed_at"],
        "responded_at":row["responded_at"],"transport":row["transport"],"authority_effect":"NONE",
      }
      if status=="RESPONDED" and row["progress_state"]=="RECEIPT_BOUND" and row["response_digest"] and row["receipt_digest"]:
        value["wait_state"]="SUPERVISOR_RECEIPT_BOUND";value["next_expected"]="AUTO_RECEIPT_WAKE"
      elif status=="WAITING_OPERATOR_OVERDUE":
        value["wait_state"]="WAITING_SUPERVISOR_OVERDUE";value["next_expected"]="EXPLICIT_RETRY_OR_LATE_RECEIPT"
      elif status=="CLAIMED":
        value["wait_state"]="WAITING_SUPERVISOR";value["next_expected"]="SUPERVISOR_RESPONSE"
      else:
        value["wait_state"]="WAITING_SUPERVISOR";value["next_expected"]="SUPERVISOR_CLAIM_OR_RESPONSE"
      return value
    return None


def resolve(conn,mission_id,phase_id,contract,now_fn):
    learn_completed(conn,mission_id,now_fn)
    currentness,evidence_requirements,_=_contract_sets(contract)
    phase_class=classify_contract(contract)
    recipe,ingredients=_resolution_recipe(evidence_requirements)
    pool=lessons(conn,mission_id)
    covered=set()
    reused=[]
    for lesson in pool:
      outputs=set(lesson.get("evidence_outputs") or [])
      hit=outputs & ingredients
      if hit:
       covered|=hit
       reused.append({"lesson_id":lesson["lesson_id"],"source_phase_id":lesson["source_phase_id"],"covers":sorted(hit),"state":lesson["lesson_state"],"evidence_digest":lesson["evidence_digest"]})
    missing_evidence=sorted(ingredients-covered)
    local_current=sorted(x for x in currentness if x in LOCAL_CURRENTNESS)
    missing_currentness=sorted(x for x in currentness if x not in LOCAL_CURRENTNESS)
    if recipe=="COMPOSE_LINEAGE_V1" and not missing_evidence:
      state="WAITING_CURRENTNESS" if missing_currentness else "READY"
      step="ACQUIRE_CURRENTNESS" if missing_currentness else "COMPOSE"
    elif recipe=="COGNITIVE_SYNTHESIS":
      supervisor=supervisor_request_snapshot(conn,mission_id,phase_id,contract)
      if supervisor and supervisor.get("wait_state")=="SUPERVISOR_RECEIPT_BOUND":
       state="SUPERVISOR_RECEIPT_BOUND";step="CONSUME_SUPERVISOR_RECEIPT"
      elif supervisor and supervisor.get("wait_state")=="WAITING_SUPERVISOR_OVERDUE":
       state="WAITING_SUPERVISOR_OVERDUE";step="RETRY_SUPERVISOR_AVAILABLE"
      elif supervisor:
       state="WAITING_SUPERVISOR";step="AWAIT_SUPERVISOR_RECEIPT"
      else:
       state="NEEDS_COGNITIVE_SYNTHESIS";step="DELEGATE_COGNITIVE"
    elif recipe:
      state="MISSING_LESSON_INPUTS";step="LEARN_OR_ACQUIRE"
    else:
      state="NO_RECIPE";step="DISCOVER"
    result={
      "schema_version":SCHEMA_VERSION,"resolver_version":RESOLVER_VERSION,
      "mission_id":mission_id,"phase_id":phase_id,"phase_class":phase_class,
      "contract_signature":contract_signature(contract),"recipe":recipe,
      "state":state,"step":step,"reused_lessons":reused,
      "covered_evidence":sorted(covered),"missing_evidence":missing_evidence,
      "local_currentness":local_current,"missing_currentness":missing_currentness,
      "supervisor_request":supervisor_request_snapshot(conn,mission_id,phase_id,contract) if recipe=="COGNITIVE_SYNTHESIS" else None,
      "authority_effect":"NONE",
    }
    record_run(conn,result,now_fn)
    return result


def record_run(conn,resolution,now_fn,result_digest=None):
    run_id="curriculum-run-"+hashlib.sha256((resolution["mission_id"]+"|"+resolution["phase_id"]+"|"+resolution["contract_signature"]).encode()).hexdigest()[:32]
    content={
      "run_id":run_id,"schema_version":SCHEMA_VERSION,"resolver_version":RESOLVER_VERSION,
      "mission_id":resolution["mission_id"],"phase_id":resolution["phase_id"],
      "contract_signature":resolution["contract_signature"],"phase_class":resolution["phase_class"],
      "state":resolution["state"],"step":resolution["step"],
      "reused_lessons":resolution.get("reused_lessons") or [],
      "missing_currentness":resolution.get("missing_currentness") or [],
      "missing_evidence":resolution.get("missing_evidence") or [],
      "resolution":resolution,"result_digest":result_digest,"authority_effect":"NONE",
    }
    artifact_store.put_artifact(
      conn,resolution["mission_id"],"PHASE_CURRICULUM_RUN",content,now_fn,
      phase_id=resolution["phase_id"],schema_id=SCHEMA_VERSION,authority_effect="NONE",
    )
    return run_id


def latest_runs(conn,mission_id):
    out={}
    for artifact in artifact_store.list_artifacts(conn,mission_id):
      if artifact.get("artifact_type")!="PHASE_CURRICULUM_RUN":continue
      item=_artifact_content(artifact)
      if not isinstance(item,dict):continue
      value=dict(item)
      value["artifact_id"]=artifact.get("artifact_id")
      value["artifact_revision"]=artifact.get("revision")
      value["artifact_digest"]=artifact.get("content_digest")
      out[str(value.get("phase_id") or artifact.get("phase_id"))]=value
    return out


def _lesson_artifacts(conn,mission_id):
    result={}
    for lesson in lessons(conn,mission_id):
      evidence,_,_,_=_phase_evidence(conn,mission_id,lesson["source_phase_id"])
      for output in lesson.get("evidence_outputs") or []:
       value=_recursive_find(evidence,output.lower())
       if value is not None:
        result[output]={"value":value,"lesson":lesson}
    return result


def _extract_task_ids(value,out):
    if isinstance(value,dict):
      for key,item in value.items():
       if str(key).lower() in {"task_id","source_task_id","parent_task_id"} and isinstance(item,str) and item.strip():out.add(item.strip())
       _extract_task_ids(item,out)
    elif isinstance(value,list):
      for item in value:_extract_task_ids(item,out)


def compose_lineage(conn,mission_id,phase_id,contract,resolution,currentness_receipt,now_fn):
    if resolution.get("recipe")!="COMPOSE_LINEAGE_V1":return None
    if resolution.get("missing_evidence"):return None
    required_external=set(resolution.get("missing_currentness") or [])
    passed=set((currentness_receipt or {}).get("passed_currentness") or [])
    if not required_external<=passed:return None
    artifacts=_lesson_artifacts(conn,mission_id)
    repo=(artifacts.get("REPOSITORY_CENSUS") or {}).get("value") or {}
    dependencies=(artifacts.get("DEPENDENCY_MAP") or {}).get("value") or []
    task_ledger=(artifacts.get("TASK_LEDGER") or {}).get("value") or {}
    capability=(artifacts.get("CAPABILITY_GRAPH") or {}).get("value") or {}
    consumers=(artifacts.get("RUNTIME_CONSUMERS") or {}).get("value") or {}
    nodes=[];edges=[];seen=set()
    def node(kind,key,**extra):
      nid=kind+":"+str(key)
      if nid not in seen:
       nodes.append({"id":nid,"kind":kind,**extra});seen.add(nid)
      return nid
    heads=(repo.get("default_heads") or {}) if isinstance(repo,dict) else {}
    for name,head in sorted(heads.items()):node("repository",name,head=head)
    for edge in dependencies if isinstance(dependencies,list) else []:
      if not isinstance(edge,dict):continue
      a=node("repository",edge.get("from"));b=node("repository",edge.get("to"))
      edges.append({"from":a,"to":b,"relation":"DEPENDS_ON","kind":edge.get("kind")})
    mission_rows=[dict(r) for r in conn.execute("SELECT mission_id,state,runtime_state,source_head,source_tree,spec_json FROM missions ORDER BY mission_id").fetchall()]
    task_map={}
    for m in mission_rows:
      mid=m["mission_id"];mn=node("mission",mid,state=m["state"],runtime_state=m["runtime_state"],source_head=m["source_head"],source_tree=m["source_tree"])
      tids=set()
      try:_extract_task_ids(json.loads(m.get("spec_json") or "{}"),tids)
      except Exception:pass
      for tid in sorted(tids):
       tn=node("task",tid);edges.append({"from":tn,"to":mn,"relation":"REALIZED_BY"});task_map.setdefault(tid,[]).append(mid)
      for repo_name,head in heads.items():
       if m.get("source_head")==head:edges.append({"from":mn,"to":"repository:"+repo_name,"relation":"SOURCED_FROM_DEFAULT_HEAD"})
    if isinstance(task_ledger,dict):
      for tid in task_ledger.get("task_ids") or []:node("task",tid)
    cap_entries=capability.get("entries") if isinstance(capability,dict) else []
    for item in cap_entries or []:
      if isinstance(item,dict):node("capability",item.get("capability_id"),executor=item.get("executor_id"),effect_ceiling=item.get("effect_ceiling"))
    consumer_items=consumers.get("items") if isinstance(consumers,dict) else []
    for group in consumer_items or []:
      if not isinstance(group,dict):continue
      cid="capability:"+str(group.get("capability_id"))
      node("capability",group.get("capability_id"))
      for consumer in group.get("consumers") or []:
       if not isinstance(consumer,dict):continue
       mn=node("mission",consumer.get("mission_id"))
       edges.append({"from":mn,"to":cid,"relation":"CONSUMES_CAPABILITY","phase_id":consumer.get("phase_id"),"executor_id":consumer.get("executor_id")})
    lineage_rows=[dict(r) for r in conn.execute("SELECT * FROM mission_lineage ORDER BY mission_id,revision").fetchall()]
    superseded=[]
    for item in lineage_rows:
      child=node("mission",item["mission_id"])
      parent=item.get("parent_mission_id")
      if parent:
       pn=node("mission",parent);edges.append({"from":child,"to":pn,"relation":item.get("relation") or "DERIVED_FROM","revision":item.get("revision")})
      if str(item.get("relation") or "").upper() in {"SUPERSEDES","SUPERSEDED_BY","SUCCESSOR_OF","REPLACED_BY"}:
       superseded.append(item)
    for row in mission_rows:
      if row.get("state")=="SUPERSEDED":superseded.append({"mission_id":row["mission_id"],"relation":"STATE_SUPERSEDED"})
    revisions=[dict(r) for r in conn.execute("SELECT revision_id,mission_id,successor_mission_id,state,created_at,activated_at FROM mission_revision_compilations ORDER BY created_at").fetchall()]
    for item in revisions:
      if item.get("successor_mission_id"):
       a=node("mission",item["mission_id"]);b=node("mission",item["successor_mission_id"])
       edges.append({"from":a,"to":b,"relation":"REVISION_SUCCESSOR","revision_id":item["revision_id"],"state":item["state"]})
       if item.get("state") in {"ACTIVATED","COMPLETE"}:superseded.append(item)
    nodes=sorted(nodes,key=lambda x:x["id"]);edges=sorted(edges,key=lambda x:(x["from"],x["to"],str(x.get("relation"))))
    source_lessons=[]
    for name,item in sorted(artifacts.items()):
      if name not in LINEAGE_INGREDIENTS:continue
      lesson=item["lesson"];source_lessons.append({"artifact":name,"lesson_id":lesson["lesson_id"],"source_phase_id":lesson["source_phase_id"],"evidence_digest":lesson["evidence_digest"]})
    lineage_graph={"node_count":len(nodes),"edge_count":len(edges),"nodes":nodes,"edges":edges,"digest":digest({"nodes":nodes,"edges":edges})}
    provenance_map={"source_count":len(source_lessons)+1,"sources":source_lessons+[{"artifact":"CURRENTNESS","receipt":currentness_receipt}],"digest":digest(source_lessons+[currentness_receipt])}
    supersession_map={"explicit_count":len(superseded),"entries":superseded,"inference_policy":"EXPLICIT_ONLY","digest":digest(superseded)}
    _,required,_=_contract_sets(contract)
    checks={
      "CURRICULUM_LESSONS_COMPOSED":"PASS" if resolution.get("reused_lessons") else "FAIL",
      "CURRENTNESS_VERIFIED":"PASS" if required_external<=passed else "FAIL",
      "LINEAGE_GRAPH_NONEMPTY":"PASS" if nodes and edges else "FAIL",
      "PROVENANCE_BOUND":"PASS" if source_lessons else "FAIL",
      "SUPERSESSION_MAP_MATERIALIZED":"PASS",
      "EVIDENCE_REQUIREMENTS_EXACT":"PASS" if required==LINEAGE_OUTPUTS else "FAIL",
    }
    pred=str((_contract_sets(contract)[2] or ["P06_LINEAGE_REGISTER_VERIFIED=PASS"])[0]).split("=",1)[0]
    ok=all(v=="PASS" for v in checks.values())
    checks[pred]="PASS" if ok else "FAIL"
    evidence={
      "producer":"PHASE_CURRICULUM_ADAPTIVE_RESOLVER","producer_mode":"LESSON_COMPOSITION",
      "authority_effect":"NONE","schema_version":SCHEMA_VERSION,"resolver_version":RESOLVER_VERSION,
      "requirements_covered":sorted(LINEAGE_OUTPUTS),"checks":checks,
      "curriculum":{**resolution,"state":"PASS" if ok else "BLOCKED","step":"COMPLETE" if ok else resolution.get("step")},
      "lineage_graph":lineage_graph,"provenance_map":provenance_map,"supersession_map":supersession_map,
      "evidence_refs":["curriculum:"+x["lesson_id"] for x in resolution.get("reused_lessons") or []]+list((currentness_receipt or {}).get("evidence_refs") or []),
    }
    record_run(conn,{**resolution,"state":"PASS" if ok else "BLOCKED","step":"COMPLETE" if ok else resolution.get("step")},now_fn,digest(evidence))
    return evidence


def curriculum_summary(conn,mission_id):
    lesson_rows=lessons(conn,mission_id)
    run_rows=latest_runs(conn,mission_id)
    return {
      "schema_version":SCHEMA_VERSION,"resolver_version":RESOLVER_VERSION,
      "lesson_count":len(lesson_rows),"lessons":lesson_rows,"runs":run_rows,
    }

