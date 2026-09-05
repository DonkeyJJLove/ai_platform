from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
import json

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from cyber_lion.contracts.moon_file_write import MoonFileWriteContractError,MoonFileWriteRequest,REPOSITORY,RUNNER_NAME
from cyber_lion.enterprise.moon_file_write import _PermissionAdmissionResolver
from cyber_lion.enterprise.moon_file_write_mediation import DurableMoonFileWriteFence,MoonFileWriteFenceRecord,MoonFileWriteMediationError,MoonFileWriteObserver
from tools.p0_moon_readonly_observer_falsification import MoonFenceReadOnlyObserverCandidate
from tools.p0_moon_same_connection_denial_contract import (
    AGENT,ATTACK_IDS,CONTROL_ISSUE,CREATE_TABLE_SURFACE,HOST,MACHINE,PRAGMA_SURFACE,RUNNER,
    MoonCarrierExecutionIdentity,MoonDenialAttackPlan,MoonDenialExecutionCarrierSpec,MoonDenialReceipt,
    MoonObservationExecutionCarrierSpec,MoonObservationReceipt,MoonSameConnectionCandidatePlan,
)
from tools.p0_moon_seven_binding import FENCE,PERMISSION
from tools.p0_moon_attack_registry import live_attacks
from tools.p0_readonly_sqlite_boundary import open_readonly_sqlite

EXPECTED_SCAN_DIGEST="2e509f22b7684e465dbebba73886aa9eae74f166480cb7e46d5be90a02a566d3"
FENCE_PATH="/home/d2j3/.lion-moon-file-write-fence.sqlite3"
TARGET_PATH="/home/d2j3/lion-p0-moon-replace-live-cert-r1.canary"
EFFECT_KEY="3ad38b9be4ea737d77c672f97f430cb32a4ba432327f5d1086e38f18327dc4c8"
CURRENT_CANARY_SHA="9ba5c66e707ca072580baf1b0c91983160e6199b4850f6cb77efd413479baf69"
SOURCE_EVENT_SHA="3e26319a2f7fa916898fac51a1d6cb2bdaa7627637cf78adbe8ab16b9d5d3b46"
CANONICAL_ACTOR="DonkeyJJLove"
SUBSTITUTED_ACTOR="lion-noncanonical-actor"

class MoonSameConnectionRuntimeError(RuntimeError):pass

def _now():return datetime.now(timezone.utc).isoformat()
def _canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str).encode()
def _row_state_digest():
    c=open_readonly_sqlite(FENCE_PATH)
    try:
        rows=c.execute("SELECT effect_key,admission_digest,request_digest,repository,target_path,state,prepared_at,attempted_at,observed_at,reconciled_at,pre_observation_digest,post_observation_digest,reconciliation_digest FROM moon_file_write_effect ORDER BY effect_key").fetchall()
        return sha256(b"LION/MOON-FENCE-ROW-STATE/1\0"+_canon(rows)).hexdigest()
    finally:c.close()

def _same_connection_pragmas(fence:DurableMoonFileWriteFence):
    if type(fence) is not DurableMoonFileWriteFence:raise MoonSameConnectionRuntimeError("exact durable fence required")
    c=fence._connect()
    try:
        journal=str(c.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        synchronous=int(c.execute("PRAGMA synchronous").fetchone()[0])
        return journal,synchronous
    finally:c.close()

def _baseline_request(*,actor=CANONICAL_ACTOR,repository=REPOSITORY,control_issue=CONTROL_ISSUE):
    return MoonFileWriteRequest(
        schema_version="1.0.0",request_id="p0-moon-denial-probe-r1",repository=repository,control_issue=control_issue,
        actor_login=actor,runner_name=RUNNER_NAME,target_path=TARGET_PATH,operation_mode="REPLACE_EXPECTED_DIGEST",
        expected_previous_state="PRESENT_EXACT",expected_previous_sha256=CURRENT_CANARY_SHA,
        intended_content_sha256=CURRENT_CANARY_SHA,intended_content_size=48,source_event_digest=SOURCE_EVENT_SHA,
    ).sealed()

def _attack_plans():
    variants={
        "WRONG_EXPECTED_STATE":"expected_previous_state=ABSENT",
        "REPLAYED_EFFECT_KEY":f"effect_key={EFFECT_KEY}",
        "REPOSITORY_SUBSTITUTION":"repository=DonkeyJJLove/ai_platform-substituted",
        "ACTOR_SUBSTITUTION":f"actor_login={SUBSTITUTED_ACTOR};expected_actor={CANONICAL_ACTOR}",
        "CONTROL_ISSUE_SUBSTITUTION":"control_issue=145",
    }
    return tuple(MoonDenialAttackPlan(a.attack_id,tuple(sorted(a.surface_digests)),a.pep,a.expected_denial,variants[a.attack_id],True,True,True,True,False,"CANDIDATE_UNEXECUTED").validate() for a in live_attacks())

def _exercise_nonhost_denial(attack_id:str):
    if attack_id=="WRONG_EXPECTED_STATE":
        r=_baseline_request();r=MoonFileWriteRequest(**{**r.payload(),"expected_previous_state":"ABSENT","expected_previous_sha256":None});r.validate()
    elif attack_id=="REPOSITORY_SUBSTITUTION":
        _baseline_request(repository="DonkeyJJLove/ai_platform-substituted")
    elif attack_id=="CONTROL_ISSUE_SUBSTITUTION":
        _baseline_request(control_issue=145)
    elif attack_id=="ACTOR_SUBSTITUTION":
        r=_baseline_request(actor=SUBSTITUTED_ACTOR)
        _PermissionAdmissionResolver(REPOSITORY,"unused",CANONICAL_ACTOR).resolve(r)
    else:raise MoonSameConnectionRuntimeError("nonhost denial id invalid")

def _replay_record(existing:MoonFileWriteFenceRecord):
    if existing.state!="RECONCILED":raise MoonSameConnectionRuntimeError("expected reconciled effect key")
    return MoonFileWriteFenceRecord(existing.effect_key,existing.admission_digest,existing.request_digest,existing.repository,existing.target_path,"PREPARED",existing.prepared_at,pre_observation_digest=existing.pre_observation_digest).validate()

class MoonObservationExecutionCarrierCandidate:
    @staticmethod
    def spec(parent_revision:str):
        return MoonObservationExecutionCarrierSpec(parent_revision,RUNNER,AGENT,HOST,MACHINE,CONTROL_ISSUE,FENCE_PATH,CREATE_TABLE_SURFACE,PRAGMA_SURFACE,True,True,False,"CANDIDATE_UNATTACHED").validate()
    @staticmethod
    def execute_schema(identity:MoonCarrierExecutionIdentity):
        identity.validate();before=_row_state_digest();readback=MoonFenceReadOnlyObserverCandidate().inspect();after=_row_state_digest()
        if before!=after:raise MoonSameConnectionRuntimeError("schema observation changed fence rows")
        return MoonObservationReceipt("SCHEMA_OBSERVATION",identity.revision,identity.tree,RUNNER,AGENT,HOST,MACHINE,FENCE_PATH,readback.database_device,readback.database_inode,CREATE_TABLE_SURFACE,"DurableMoonFileWriteFence._initialize",readback.journal_mode,readback.synchronous,readback.schema_digest,before,False,_now()).sealed()
    @staticmethod
    def execute_same_connection_pragma(identity:MoonCarrierExecutionIdentity):
        identity.validate();pre=MoonFenceReadOnlyObserverCandidate().inspect();rows_pre=_row_state_digest()
        if not pre.schema_exact or not pre.journal_mode_exact:raise MoonSameConnectionRuntimeError("pre-observation not exact")
        fence=DurableMoonFileWriteFence(FENCE_PATH)
        journal,synchronous=_same_connection_pragmas(fence)
        post=MoonFenceReadOnlyObserverCandidate().inspect();rows_post=_row_state_digest()
        if journal!="wal" or synchronous!=2:raise MoonSameConnectionRuntimeError("canonical same-connection pragma mismatch")
        if (pre.database_device,pre.database_inode)!=(post.database_device,post.database_inode) or pre.schema_digest!=post.schema_digest or rows_pre!=rows_post:raise MoonSameConnectionRuntimeError("same-connection probe changed bounded database state")
        return MoonObservationReceipt("SAME_CONNECTION_PRAGMA",identity.revision,identity.tree,RUNNER,AGENT,HOST,MACHINE,FENCE_PATH,post.database_device,post.database_inode,PRAGMA_SURFACE,"DurableMoonFileWriteFence._connect",journal,synchronous,post.schema_digest,rows_post,True,_now()).sealed()

class MoonDenialExecutionCarrierCandidate:
    @staticmethod
    def spec(parent_revision:str):
        plans=_attack_plans();return MoonDenialExecutionCarrierSpec(parent_revision,RUNNER,AGENT,HOST,MACHINE,CONTROL_ISSUE,TARGET_PATH,FENCE_PATH,ATTACK_IDS,tuple(p.digest() for p in plans),False,False,False,False,False,"CANDIDATE_UNATTACHED").validate()
    @staticmethod
    def execute(attack_id:str,identity:MoonCarrierExecutionIdentity):
        identity.validate();plans={p.attack_id:p for p in _attack_plans()}
        if attack_id not in plans:raise MoonSameConnectionRuntimeError("unknown attack id")
        plan=plans[attack_id]
        target_observer=MoonFileWriteObserver();pre_target=target_observer.observe(TARGET_PATH)
        if not pre_target.exists or not pre_target.regular_file or pre_target.symlink or pre_target.sha256 is None:raise MoonSameConnectionRuntimeError("canary pre-observation invalid")
        fence_pre=_row_state_digest();denial=None
        try:
            if attack_id=="REPLAYED_EFFECT_KEY":
                fence=DurableMoonFileWriteFence(FENCE_PATH);existing=fence.get(EFFECT_KEY);fence.prepare(_replay_record(existing))
            else:_exercise_nonhost_denial(attack_id)
        except (MoonFileWriteContractError,MoonFileWriteMediationError) as exc:
            denial=str(exc)
        if denial!=plan.expected_denial:raise MoonSameConnectionRuntimeError(f"unexpected denial: {denial!r}")
        post_target=target_observer.observe(TARGET_PATH);fence_post=_row_state_digest()
        if post_target.sha256!=pre_target.sha256 or fence_post!=fence_pre:raise MoonSameConnectionRuntimeError("denial changed bounded state")
        return MoonDenialReceipt(identity.revision,identity.tree,RUNNER,AGENT,HOST,MACHINE,attack_id,plan.pep,denial,pre_target.sha256,post_target.sha256,fence_pre,fence_post,False,False,_now()).sealed()

@dataclass(frozen=True)
class MoonSameConnectionCandidateArtifacts:
    observation_spec:object;denial_spec:object;attacks:tuple;plan:MoonSameConnectionCandidatePlan

def materialize_same_connection_candidate(*,inventory:EffectSurfaceInventory):
    inventory.validate()
    if inventory.scan_digest!=EXPECTED_SCAN_DIGEST:raise MoonSameConnectionRuntimeError("production scan digest drift")
    known={s.digest() for s in inventory.surfaces}
    if {CREATE_TABLE_SURFACE,PRAGMA_SURFACE}-known:raise MoonSameConnectionRuntimeError("observer surface drift")
    attacks=_attack_plans();obs=MoonObservationExecutionCarrierCandidate.spec(inventory.revision);denial=MoonDenialExecutionCarrierCandidate.spec(inventory.revision)
    refs=("parent-pr:264","observer-receipt-count:0","denial-receipt-count:0","bypass-result-count:0","same-connection-probe:not-executed")
    plan=MoonSameConnectionCandidatePlan(inventory.digest(),inventory.scan_digest,obs.digest(),denial.digest(),tuple(p.digest() for p in attacks),0,0,0,False,"UNKNOWN",refs).validate()
    return MoonSameConnectionCandidateArtifacts(obs,denial,attacks,plan)
