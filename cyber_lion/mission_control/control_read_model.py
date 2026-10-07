"""Pure bounded composers for LION control-surface read projections.

They accept already-observed canonical records and create non-effectful panel
projections. They do not open databases, execute providers, infer authority,
claim assignments, or project raw prompt/content fields.
"""
from __future__ import annotations
from typing import Any, Iterable, Mapping
from cyber_lion.contracts.panel_projection import (
    ArtifactProjection, EvolutionProjection, FederationProjection,
    MissionProjection, ModelProjection, ProjectionError, ProjectionHeader,
    RepositoryProjection, SwarmProjection, TimelineProjection, CommunicationProjection,
)

MAX_ROWS = 512
UI_EVENT_CLASSES = frozenset({
    "COMMUNICATION","SCHEDULING","COGNITION","EXECUTION","ARTIFACT",
    "VERIFICATION","AUTHORITY","CURRENTNESS","RECOVERY","REPOSITORY","UNKNOWN",
})
MISSION_FIELDS=("mission_id","title","state","runtime_state","ready","materialized","control_authority","projection_version","projection_revision")
PROCESS_FIELDS=("current_phase","progress","objective","authority_state")
DRIVER_FIELDS=("driver_id","generation","state","heartbeat_at","current_phase","waiting_reason","blocking_gate","next_action","last_currentness_at")
WORKER_FIELDS=("material_worker_id","state","self_test","cognitive_readiness","mission_control_reachability","model_reachability","last_mission_control_ok_at","last_model_ok_at","consecutive_transport_errors","last_transport_operation","transport_protocol","transport_state","worker_profile")
WORKER_ARCH_FIELDS=("runtime_instance_id","boot_id","source_head","source_tree","identity_digest","authority_ceiling","material_executor_independence")
MODEL_CALL_FIELDS=("model_call_id","mission_id","phase_id","task_id","assignment_id","logical_drone_id","material_worker_id","requested_capability","provider","model_requested","model_declared","model_attested","transport","selection_reason","candidate_set_digest","context_revision","input_digest","result_digest","state","created_at","updated_at","finished_at","authority_effect")
REPOSITORY_FIELDS=("repository","branch","head","tree","role","currentness","active_pr","ci_state","updated_at")
ARTIFACT_FIELDS=("artifact_id","mission_id","phase_id","artifact_type","schema_id","revision","content_digest","authority_effect","created_at","updated_at","byte_length","bytes_sha256","origin_repository","origin_head","verification_state","verifier_ref","publication_state")
ARTIFACT_CANDIDATE_FIELDS=("run_id","mission_id","task_id","generation","attempt","state","source_digest","stream_state","worker_state","observed_at","artifact_ref","artifact_digest","verifier_receipt_digest","authority_effect","observation_digest")
TIMELINE_FIELDS=("event_id","event_class","timestamp","mission_id","phase_id","participant_id","logical_drone_id","material_worker_id","model_call_id","assignment_id","artifact_id","correlation_id","causation_id","generation","state","authority_effect")
EVOLUTION_FIELDS=("repository","current_head","candidate_head","target_ref","active_pr","mission_id","task_id","worker_id","artifact_id","test_state","integration_state","deployment_state","currentness")

def _mapping(value:Any,name:str)->Mapping[str,Any]:
    if not isinstance(value,Mapping): raise ProjectionError(name)
    return value

def _project_fields(value:Mapping[str,Any],fields:tuple[str,...])->dict[str,Any]:
    return {k:value.get(k) for k in fields if k in value}

def _rows(values:Iterable[Mapping[str,Any]],*,name:str)->list[Mapping[str,Any]]:
    if isinstance(values,(str,bytes,Mapping)): raise ProjectionError(name)
    rows=list(values)
    if len(rows)>MAX_ROWS: raise ProjectionError(name+" exceeds bound")
    for row in rows:_mapping(row,name)
    return rows

def _header(*,observed_at:str,source_refs,source_revision:str,projection_version:str,currentness:str,gaps=())->ProjectionHeader:
    return ProjectionHeader.build(observed_at=observed_at,source_refs=source_refs,source_revision=source_revision,projection_version=projection_version,currentness=currentness,gaps=gaps)

def build_mission_projection(snapshot:Mapping[str,Any],**h)->MissionProjection:
    source=_mapping(snapshot,"mission snapshot")
    process=source.get("process") if isinstance(source.get("process"),Mapping) else {}
    driver=source.get("execution_driver") if isinstance(source.get("execution_driver"),Mapping) else {}
    payload=_project_fields(source,MISSION_FIELDS)
    payload["process"]=_project_fields(process,PROCESS_FIELDS)
    payload["execution_driver"]=_project_fields(driver,DRIVER_FIELDS)
    return MissionProjection.build(_header(**h),payload)

def build_swarm_projection(worker_statuses:Iterable[Mapping[str,Any]],**h)->SwarmProjection:
    rows=[]
    for row in _rows(worker_statuses,name="worker statuses"):
        value=_project_fields(row,WORKER_FIELDS)
        arch=row.get("architecture") if isinstance(row.get("architecture"),Mapping) else {}
        value["architecture"]=_project_fields(arch,WORKER_ARCH_FIELDS)
        tm=row.get("transport_metrics") if isinstance(row.get("transport_metrics"),Mapping) else {}
        value["transport_metrics"]={k:tm.get(k) for k in ("open_connections","connection_creations","reconnects") if k in tm}
        provider=row.get("cooperative_runtime_provider")
        if isinstance(provider,Mapping):
            value["cooperative_runtime_provider"]=_project_fields(provider,("state","provider_id","context_resolver","execution_engine","authority_effect"))
        rows.append(value)
    rows.sort(key=lambda x:str(x.get("material_worker_id") or ""))
    return SwarmProjection.build(_header(**h),{"worker_count":len(rows),"workers":rows,"ready_count":sum(1 for x in rows if x.get("state")=="READY")})

def build_model_projection(model_calls:Iterable[Mapping[str,Any]],**h)->ModelProjection:
    rows=[_project_fields(x,MODEL_CALL_FIELDS) for x in _rows(model_calls,name="model calls")]
    rows.sort(key=lambda x:(str(x.get("created_at") or ""),str(x.get("model_call_id") or "")))
    return ModelProjection.build(_header(**h),{"call_count":len(rows),"calls":rows})

def build_federation_projection(repositories:Iterable[Mapping[str,Any]],**h)->FederationProjection:
    rows=[_project_fields(x,REPOSITORY_FIELDS) for x in _rows(repositories,name="repositories")]
    rows.sort(key=lambda x:str(x.get("repository") or ""))
    return FederationProjection.build(_header(**h),{"repository_count":len(rows),"repositories":rows})

def build_repository_projection(repository:Mapping[str,Any],**h)->RepositoryProjection:
    return RepositoryProjection.build(_header(**h),_project_fields(_mapping(repository,"repository"),REPOSITORY_FIELDS))

def build_artifact_projection(artifacts:Iterable[Mapping[str,Any]],**h)->ArtifactProjection:
    rows=[_project_fields(x,ARTIFACT_FIELDS) for x in _rows(artifacts,name="artifacts")]
    rows.sort(key=lambda x:(str(x.get("created_at") or ""),str(x.get("artifact_id") or "")))
    return ArtifactProjection.build(_header(**h),{"artifact_count":len(rows),"artifacts":rows})

def build_artifact_candidate_projection(observations:Iterable[Mapping[str,Any]],**h)->ArtifactProjection:
    rows=[_project_fields(x,ARTIFACT_CANDIDATE_FIELDS) for x in _rows(observations,name="artifact candidate observations")]
    rows.sort(key=lambda x:(int(x.get("generation") or 0),int(x.get("attempt") or 0),str(x.get("run_id") or "")))
    terminal={"VERIFIED","REJECTED","SUPERSEDED"}
    degraded={"LOST","EXPIRED"}
    return ArtifactProjection.build(_header(**h),{
        "candidate_count":len(rows),
        "running_count":sum(1 for x in rows if x.get("state")=="RUNNING"),
        "terminal_count":sum(1 for x in rows if x.get("state") in terminal),
        "stream_degraded_count":sum(1 for x in rows if x.get("stream_state") in degraded),
        "candidates":rows,
    })

def build_timeline_projection(events:Iterable[Mapping[str,Any]],**h)->TimelineProjection:
    rows=[]
    for source in _rows(events,name="timeline events"):
        row=_project_fields(source,TIMELINE_FIELDS)
        if row.get("event_class","UNKNOWN") not in UI_EVENT_CLASSES: row["event_class"]="UNKNOWN"
        rows.append(row)
    rows.sort(key=lambda x:(str(x.get("timestamp") or ""),str(x.get("event_id") or "")))
    return TimelineProjection.build(_header(**h),{"event_count":len(rows),"events":rows})

def _identity(kind:str,value:Any)->str|None:
    if not isinstance(value,str) or not value:return None
    return kind+":"+value

def _communication_node_kind(node_id:str)->str:
    return node_id.split(":",1)[0].upper() if ":" in node_id else "UNKNOWN"

def build_communication_projection(
    *,
    operator_messages:Iterable[Mapping[str,Any]]=(),
    deliveries:Iterable[Mapping[str,Any]]=(),
    trajectories:Iterable[Mapping[str,Any]]=(),
    assignments:Iterable[Mapping[str,Any]]=(),
    model_calls:Iterable[Mapping[str,Any]]=(),
    artifacts:Iterable[Mapping[str,Any]]=(),
    conversation_messages:Iterable[Mapping[str,Any]]=(),
    conversation_events:Iterable[Mapping[str,Any]]=(),
    **h,
)->CommunicationProjection:
    """Project durable communication evidence into one graph without inventing edges."""
    edges=[]
    def add(edge_id,kind,source,target,source_ref,**fields):
        if not all(isinstance(x,str) and x for x in (edge_id,kind,source,target,source_ref)):raise ProjectionError("communication edge")
        row={"edge_id":edge_id,"edge_kind":kind,"source":source,"target":target,"source_ref":source_ref,"authority_effect":"NONE"}
        for key in ("mission_id","phase_id","participant_id","logical_drone_id","material_worker_id","assignment_id","model_call_id","artifact_id","conversation_id","correlation_id","causation_id","generation","state","timestamp"):
            value=fields.get(key)
            if value is not None:row[key]=value
        edges.append(row)

    messages=_rows(operator_messages,name="operator messages")
    for row in messages:
        mid=row.get("message_id")
        source=_identity("participant",row.get("from_participant"))
        target=_identity("target",row.get("target"))
        if isinstance(mid,str) and source and target:
            add("operator-message:"+mid,"MESSAGE",source,target,"operator_message:"+mid,
                mission_id=row.get("mission_id"),correlation_id=row.get("correlation_id"),causation_id=row.get("causation_id"),
                state=row.get("state"),timestamp=row.get("created_at"))

    for row in _rows(deliveries,name="operator deliveries"):
        mid=row.get("message_id");recipient=_identity("participant",row.get("recipient"))
        if isinstance(mid,str) and recipient:
            add("operator-delivery:"+mid+":"+str(row.get("recipient")),"DELIVER","operator-message:"+mid,recipient,
                "operator_delivery:"+mid+":"+str(row.get("recipient")),assignment_id=row.get("applied_assignment_id"),
                state=row.get("delivery_state"),timestamp=row.get("delivered_at") or row.get("applied_at"))

    for row in _rows(trajectories,name="cognitive trajectories"):
        tid=row.get("trajectory_id");mid=row.get("message_id");participant=_identity("participant",row.get("participant_id"))
        if isinstance(tid,str) and isinstance(mid,str) and participant:
            add("trajectory:"+tid,"PROJECT_TO","operator-message:"+mid,participant,"trajectory:"+tid,
                mission_id=row.get("mission_id"),participant_id=row.get("participant_id"),state=row.get("state"),timestamp=row.get("created_at"))
            for field,prefix,kind in (
                ("local_assignment_id","assignment","ASSIGNED_TO"),
                ("local_model_call_id","model-call","INVOKES"),
                ("saas_request_id","saas-request","INVOKES"),
                ("dual_request_id","dual-request","INVOKES"),
            ):
                value=row.get(field)
                if isinstance(value,str) and value:
                    add("trajectory-ref:"+tid+":"+field,kind,participant,prefix+":"+value,"trajectory:"+tid,
                        mission_id=row.get("mission_id"),participant_id=row.get("participant_id"),state=row.get("state"))

    for row in _rows(assignments,name="assignments"):
        aid=row.get("assignment_id");logical=_identity("drone",row.get("logical_drone_id"));material=_identity("worker",row.get("material_drone_id"))
        if isinstance(aid,str) and logical and material:
            add("assignment:"+aid,"ASSIGNED_TO",logical,material,"assignment:"+aid,
                mission_id=row.get("mission_id"),phase_id=row.get("phase_id"),logical_drone_id=row.get("logical_drone_id"),
                material_worker_id=row.get("material_drone_id"),assignment_id=aid,generation=row.get("lease_generation"),
                state=row.get("state"),timestamp=row.get("created_at"))

    for row in _rows(model_calls,name="communication model calls"):
        call=row.get("model_call_id");aid=row.get("assignment_id");provider=row.get("provider")
        model=row.get("model_attested") or row.get("model_declared") or row.get("model_requested") or "UNKNOWN"
        if isinstance(call,str) and isinstance(aid,str) and isinstance(provider,str):
            target="model:"+provider+":"+str(model)
            add("model-call:"+call,"INVOKES","assignment:"+aid,target,"model_call:"+call,
                mission_id=row.get("mission_id"),phase_id=row.get("phase_id"),logical_drone_id=row.get("logical_drone_id"),
                material_worker_id=row.get("material_worker_id"),assignment_id=aid,model_call_id=call,
                state=row.get("state"),timestamp=row.get("created_at"))

    for row in _rows(artifacts,name="communication artifacts"):
        artifact=row.get("artifact_id");mission=row.get("mission_id")
        if isinstance(artifact,str) and isinstance(mission,str):
            source="phase:"+str(row.get("phase_id")) if row.get("phase_id") else "mission:"+mission
            add("artifact:"+artifact,"PRODUCES",source,"artifact:"+artifact,"artifact:"+artifact,
                mission_id=mission,phase_id=row.get("phase_id"),artifact_id=artifact,state=row.get("verification_state"),
                timestamp=row.get("created_at"))

    for row in _rows(conversation_messages,name="conversation messages"):
        message=row.get("message_id");conversation=row.get("conversation_id")
        if isinstance(message,str) and isinstance(conversation,str):
            add("conversation-message:"+message,"MESSAGE","conversation:"+conversation,"conversation-message:"+message,
                "conversation_message:"+message,conversation_id=conversation,correlation_id=row.get("correlation_id"),
                causation_id=row.get("causation_id"),state=row.get("role"),timestamp=row.get("created_at"))

    for row in _rows(conversation_events,name="conversation events"):
        event=row.get("event_id");conversation=row.get("conversation_id");message=row.get("message_id")
        if isinstance(event,str) and isinstance(conversation,str) and isinstance(message,str):
            add("conversation-event:"+event,"DELIVER","conversation-message:"+message,"conversation:"+conversation,
                "conversation_event:"+event,conversation_id=conversation,correlation_id=row.get("correlation_id"),
                causation_id=row.get("causation_id"),state=row.get("state"),timestamp=row.get("created_at"))

    by_id={}
    for edge in edges:
        prior=by_id.get(edge["edge_id"])
        if prior is not None and prior!=edge:raise ProjectionError("communication edge id collision")
        by_id[edge["edge_id"]]=edge
    ordered=[by_id[key] for key in sorted(by_id)]
    if len(ordered)>MAX_ROWS:raise ProjectionError("communication edges exceeds bound")
    node_ids=sorted({edge["source"] for edge in ordered}|{edge["target"] for edge in ordered})
    if len(node_ids)>MAX_ROWS:raise ProjectionError("communication nodes exceeds bound")
    nodes=[{"node_id":node_id,"node_kind":_communication_node_kind(node_id)} for node_id in node_ids]
    return CommunicationProjection.build(_header(**h),{
        "node_count":len(nodes),"edge_count":len(ordered),"nodes":nodes,"edges":ordered,
    })

def build_evolution_projection(changes:Iterable[Mapping[str,Any]],**h)->EvolutionProjection:
    rows=[_project_fields(x,EVOLUTION_FIELDS) for x in _rows(changes,name="evolution changes")]
    rows.sort(key=lambda x:(str(x.get("repository") or ""),str(x.get("task_id") or "")))
    return EvolutionProjection.build(_header(**h),{"change_count":len(rows),"changes":rows})
