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
    RepositoryProjection, SwarmProjection, TimelineProjection,
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

def build_timeline_projection(events:Iterable[Mapping[str,Any]],**h)->TimelineProjection:
    rows=[]
    for source in _rows(events,name="timeline events"):
        row=_project_fields(source,TIMELINE_FIELDS)
        if row.get("event_class","UNKNOWN") not in UI_EVENT_CLASSES: row["event_class"]="UNKNOWN"
        rows.append(row)
    rows.sort(key=lambda x:(str(x.get("timestamp") or ""),str(x.get("event_id") or "")))
    return TimelineProjection.build(_header(**h),{"event_count":len(rows),"events":rows})

def build_evolution_projection(changes:Iterable[Mapping[str,Any]],**h)->EvolutionProjection:
    rows=[_project_fields(x,EVOLUTION_FIELDS) for x in _rows(changes,name="evolution changes")]
    rows.sort(key=lambda x:(str(x.get("repository") or ""),str(x.get("task_id") or "")))
    return EvolutionProjection.build(_header(**h),{"change_count":len(rows),"changes":rows})
