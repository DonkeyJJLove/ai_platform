"""Immutable contracts for host authority separation and bounded deployment/migration.

These contracts describe a root-owned deployment/migration plane. They do not mutate a host,
carry production authority, select a verifier, or grant merge capability.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json, re
from typing import Any

_SHA40=re.compile(r"^[0-9a-f]{40}$"); _SHA256=re.compile(r"^[0-9a-f]{64}$")
CANONICAL_REPOSITORY="DonkeyJJLove/ai_platform"
RUNTIME_USER="lion-control-plane"; RUNNER_USER="lion-maintenance-runner"
DEPLOYER_USER="root"; MIGRATOR_USER="root"
CONTROL_PLANE_GROUP="lion-control-plane"; TRUST_CLIENT_GROUP="lion-trust-client"
RUNTIME_CODE_PATH="/opt/lion/control-plane-code"
LIVE_DB_PATH="/var/lib/lion/control-plane/control-plane.sqlite"
SERVICE_ENV_PATH="/etc/lion/maintenance-bundle.env"
SERVICE_UNIT_PATH="/etc/systemd/system/lion-maintenance-bundle.service"
SNAPSHOT_DIR="/var/lib/lion/control-plane/snapshots"
PROVISIONING_TABLES=("authority_epoch_state","authority_root_anchor","authority_provisioning_receipt")
PRESERVED_TABLES=("pr_bootstrap","authority_lineage")
PROVISIONING_TRIGGERS=("authority_provisioning_receipt_no_update","authority_provisioning_receipt_no_delete")
HOST_OPERATIONS=frozenset({
    "REMOVE_RUNNER_CONTROL_PLANE_GROUP","ENSURE_TRUST_CLIENT_GROUP","ADD_RUNNER_TRUST_CLIENT_GROUP",
    "REOWN_RUNTIME_CODE_ROOT","SET_RUNTIME_CODE_READ_ONLY","PIN_TRUST_CLIENT_RUNTIME_READ",
    "DENY_RUNNER_DB_ACCESS","DENY_RUNNER_SERVICE_ENV_ACCESS","INSTALL_BOUNDED_DEPLOYMENT_BROKER",
    "INSTALL_BOUNDED_SCHEMA_MIGRATION_BROKER",
})

class HostAuthorityContractError(ValueError): pass

def _txt(v:Any,n:str,limit:int=1024)->str:
    if not isinstance(v,str) or not v.strip() or len(v)>limit or "\x00" in v: raise HostAuthorityContractError(f"{n} invalid")
    return v
def _sha40(v:Any,n:str)->str:
    v=_txt(v,n,40)
    if not _SHA40.fullmatch(v): raise HostAuthorityContractError(f"{n} must be lowercase sha40")
    return v
def _sha256(v:Any,n:str)->str:
    v=_txt(v,n,64)
    if not _SHA256.fullmatch(v): raise HostAuthorityContractError(f"{n} must be sha256")
    return v
def _utc(v:Any,n:str):
    v=_txt(v,n,128)
    try: d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as e: raise HostAuthorityContractError(f"{n} invalid") from e
    if d.tzinfo is None: raise HostAuthorityContractError(f"{n} must be timezone aware")
    return d
def _canon(v:Any)->bytes: return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _digest(domain:bytes,v:Any)->str: return sha256(domain+_canon(v)).hexdigest()

def _tuple_text(v:Any,n:str,allow_empty:bool=False)->tuple[str,...]:
    if type(v) is not tuple or (not allow_empty and not v): raise HostAuthorityContractError(f"{n} must be tuple")
    for x in v: _txt(x,n)
    if len(v)!=len(set(v)): raise HostAuthorityContractError(f"{n} duplicate")
    return v

@dataclass(frozen=True)
class TrustedRuntimeReadBinding:
    path:str; sha256_digest:str
    def validate(self):
        p=_txt(self.path,"trusted runtime path",4096)
        if not p.startswith("/opt/lion/trusted-runtime/") or ".." in p.split("/"): raise HostAuthorityContractError("trusted runtime path outside canonical root")
        _sha256(self.sha256_digest,"trusted runtime digest"); return self

@dataclass(frozen=True)
class HostAuthorityObservation:
    hostname:str; runtime_user:str; runner_user:str; runner_groups:tuple[str,...]
    runner_db_read:bool; runner_db_write:bool; runner_service_env_read:bool; runtime_code_write:bool
    runner_actions_private_key_read:bool; runner_authority_private_key_read:bool
    live_db_sha256:str; deployed_manifest_sha256:str; service_unit_sha256:str
    observed_at:str
    def validate(self):
        _txt(self.hostname,"hostname"); _txt(self.runtime_user,"runtime_user"); _txt(self.runner_user,"runner_user")
        _tuple_text(self.runner_groups,"runner_groups")
        for n in ("runner_db_read","runner_db_write","runner_service_env_read","runtime_code_write","runner_actions_private_key_read","runner_authority_private_key_read"):
            if type(getattr(self,n)) is not bool: raise HostAuthorityContractError(f"{n} must be bool")
        for n in ("live_db_sha256","deployed_manifest_sha256","service_unit_sha256"): _sha256(getattr(self,n),n)
        _utc(self.observed_at,"observed_at"); return self
    def digest(self): self.validate(); return _digest(b"LION/HOST-AUTHORITY-OBSERVATION/1\0",asdict(self))

@dataclass(frozen=True)
class HostAuthoritySeparationPlan:
    plan_id:str; repository:str; baseline_sha:str; baseline_tree:str; certified_candidate_sha:str; certified_candidate_tree:str
    certified_synthetic_sha:str; certified_source_manifest_sha256:str; certified_post_schema_digest:str
    runtime_user:str; runner_user:str; deployer_user:str; migrator_user:str; control_plane_group:str; trust_client_group:str
    runtime_code_path:str; live_db_path:str; service_env_path:str; service_unit_path:str
    runtime_code_owner:str; runtime_code_group:str; runtime_code_dir_mode:int; runtime_code_file_mode:int
    runner_target_groups:tuple[str,...]; trusted_runtime_reads:tuple[TrustedRuntimeReadBinding,...]
    production_private_key_on_host:bool; generated_at:str
    def validate(self):
        _txt(self.plan_id,"plan_id")
        if self.repository!=CANONICAL_REPOSITORY: raise HostAuthorityContractError("repository mismatch")
        _sha40(self.baseline_sha,"baseline_sha"); _sha40(self.certified_candidate_sha,"certified_candidate_sha")
        _sha40(self.baseline_tree,"baseline_tree"); _sha40(self.certified_candidate_tree,"certified_candidate_tree"); _sha40(self.certified_synthetic_sha,"certified_synthetic_sha")
        _sha256(self.certified_source_manifest_sha256,"certified_source_manifest_sha256"); _sha256(self.certified_post_schema_digest,"certified_post_schema_digest")
        exact=(self.runtime_user,self.runner_user,self.deployer_user,self.migrator_user,self.control_plane_group,self.trust_client_group,self.runtime_code_path,self.live_db_path,self.service_env_path,self.service_unit_path,self.runtime_code_owner,self.runtime_code_group)
        expected=(RUNTIME_USER,RUNNER_USER,DEPLOYER_USER,MIGRATOR_USER,CONTROL_PLANE_GROUP,TRUST_CLIENT_GROUP,RUNTIME_CODE_PATH,LIVE_DB_PATH,SERVICE_ENV_PATH,SERVICE_UNIT_PATH,"root",CONTROL_PLANE_GROUP)
        if exact!=expected: raise HostAuthorityContractError("canonical host ownership boundary changed")
        if self.runtime_user==self.runner_user or self.runtime_user==self.deployer_user or self.runner_user==self.deployer_user: raise HostAuthorityContractError("principal separation failed")
        if self.runtime_code_dir_mode!=0o550 or self.runtime_code_file_mode!=0o440: raise HostAuthorityContractError("runtime code must be root-owned read-only")
        _tuple_text(self.runner_target_groups,"runner_target_groups")
        if CONTROL_PLANE_GROUP in self.runner_target_groups or TRUST_CLIENT_GROUP not in self.runner_target_groups: raise HostAuthorityContractError("runner target groups violate separation")
        if type(self.trusted_runtime_reads) is not tuple: raise HostAuthorityContractError("trusted_runtime_reads must be tuple")
        paths=[]
        for b in self.trusted_runtime_reads:
            if type(b) is not TrustedRuntimeReadBinding: raise HostAuthorityContractError("trusted runtime binding type invalid")
            b.validate(); paths.append(b.path)
        if len(paths)!=len(set(paths)): raise HostAuthorityContractError("trusted runtime path duplicate")
        if self.production_private_key_on_host is not False: raise HostAuthorityContractError("production private key on host forbidden")
        _utc(self.generated_at,"generated_at"); return self
    def digest(self):
        self.validate(); d=asdict(self); d["trusted_runtime_reads"]=[asdict(x) for x in self.trusted_runtime_reads]
        return _digest(b"LION/HOST-AUTHORITY-SEPARATION-PLAN/1\0",d)

@dataclass(frozen=True)
class HostOperation:
    kind:str; subject:str; target:str; expected_digest:str|None; detail:str
    def validate(self):
        if self.kind not in HOST_OPERATIONS: raise HostAuthorityContractError("host operation kind invalid")
        _txt(self.subject,"operation subject"); _txt(self.target,"operation target",4096); _txt(self.detail,"operation detail",4096)
        if self.expected_digest is not None: _sha256(self.expected_digest,"operation expected_digest")
        if any(x in self.target for x in (";","|","\n","\r","$(","`")): raise HostAuthorityContractError("operation target contains shell syntax")
        return self
    def digest(self): self.validate(); return _digest(b"LION/HOST-OPERATION/1\0",asdict(self))

@dataclass(frozen=True)
class HostTransitionPlan:
    transition_id:str; observation_digest:str; separation_plan_digest:str; operations:tuple[HostOperation,...]; generated_at:str
    def validate(self):
        _txt(self.transition_id,"transition_id"); _sha256(self.observation_digest,"observation_digest"); _sha256(self.separation_plan_digest,"separation_plan_digest")
        if type(self.operations) is not tuple or not self.operations: raise HostAuthorityContractError("operations required")
        keys=[]
        for op in self.operations:
            if type(op) is not HostOperation: raise HostAuthorityContractError("operation type invalid")
            op.validate(); keys.append((op.kind,op.target))
        if len(keys)!=len(set(keys)): raise HostAuthorityContractError("operation target duplicate")
        _utc(self.generated_at,"generated_at"); return self
    def digest(self): self.validate(); return _digest(b"LION/HOST-TRANSITION-PLAN/1\0",{"transition_id":self.transition_id,"observation_digest":self.observation_digest,"separation_plan_digest":self.separation_plan_digest,"operations":[asdict(x) for x in self.operations],"generated_at":self.generated_at})

@dataclass(frozen=True)
class ExternalAuthorityIdentity:
    issuer_subject_id:str; trust_domain:str; key_id:str; algorithm:str; provenance_class:str; host_principal:str|None; private_key_on_host:bool
    def validate(self):
        for n in ("issuer_subject_id","trust_domain","key_id","algorithm","provenance_class"): _txt(getattr(self,n),n)
        if self.provenance_class!="PRODUCTION_EXTERNAL": raise HostAuthorityContractError("test/fixture authority cannot be promoted")
        if self.host_principal is not None: _txt(self.host_principal,"host_principal")
        if self.private_key_on_host is not False: raise HostAuthorityContractError("production signing key must remain off host")
        return self

@dataclass(frozen=True)
class DeploymentRequest:
    request_id:str; repository:str; baseline_sha:str; baseline_tree:str; candidate_sha:str; candidate_tree:str; synthetic_sha:str
    source_manifest_sha256:str; current_deployed_manifest_sha256:str; service_unit_sha256:str; separation_plan_digest:str
    requester_principal:str; requested_at:str
    def validate(self):
        _txt(self.request_id,"request_id"); _txt(self.requester_principal,"requester_principal")
        if self.repository!=CANONICAL_REPOSITORY: raise HostAuthorityContractError("repository mismatch")
        _sha40(self.baseline_sha,"baseline_sha"); _sha40(self.candidate_sha,"candidate_sha"); _sha40(self.synthetic_sha,"synthetic_sha")
        _sha40(self.baseline_tree,"baseline_tree"); _sha40(self.candidate_tree,"candidate_tree")
        for n in ("source_manifest_sha256","current_deployed_manifest_sha256","service_unit_sha256","separation_plan_digest"): _sha256(getattr(self,n),n)
        if self.requester_principal in {DEPLOYER_USER,MIGRATOR_USER,RUNTIME_USER}: raise HostAuthorityContractError("candidate builder/requester cannot be deployer, migrator, or runtime")
        _utc(self.requested_at,"requested_at"); return self
    def digest(self): self.validate(); return _digest(b"LION/BOUNDED-DEPLOYMENT-REQUEST/1\0",asdict(self))

@dataclass(frozen=True)
class SchemaObservation:
    database_sha256:str; schema_digest:str; pr_bootstrap_rows:int; authority_lineage_rows:int; objects:tuple[str,...]; integrity_check:str; observed_at:str
    def validate(self):
        _sha256(self.database_sha256,"database_sha256"); _sha256(self.schema_digest,"schema_digest")
        if type(self.pr_bootstrap_rows) is not int or self.pr_bootstrap_rows<0 or type(self.authority_lineage_rows) is not int or self.authority_lineage_rows<0: raise HostAuthorityContractError("row count invalid")
        _tuple_text(self.objects,"objects",allow_empty=True)
        if self.integrity_check!="ok": raise HostAuthorityContractError("sqlite integrity check not ok")
        _utc(self.observed_at,"observed_at"); return self
    def digest(self): self.validate(); return _digest(b"LION/SCHEMA-OBSERVATION/1\0",asdict(self))

@dataclass(frozen=True)
class SnapshotAttestation:
    snapshot_path:str; source_database_sha256:str; snapshot_sha256:str; integrity_check:str; created_at:str
    def validate(self):
        p=_txt(self.snapshot_path,"snapshot_path",4096)
        if not p.startswith(SNAPSHOT_DIR+"/") or ".." in p.split("/"): raise HostAuthorityContractError("snapshot outside canonical directory")
        _sha256(self.source_database_sha256,"source_database_sha256"); _sha256(self.snapshot_sha256,"snapshot_sha256")
        if self.integrity_check!="ok": raise HostAuthorityContractError("snapshot integrity check not ok")
        _utc(self.created_at,"created_at"); return self

@dataclass(frozen=True)
class SchemaMigrationRequest:
    request_id:str; candidate_sha:str; candidate_tree:str; synthetic_sha:str; live_database_sha256:str; pre_schema_digest:str
    schema_sql_sha256:str; snapshot_sha256:str; expected_post_schema_digest:str; separation_plan_digest:str; requester_principal:str; requested_at:str
    def validate(self):
        _txt(self.request_id,"request_id"); _txt(self.requester_principal,"requester_principal")
        _sha40(self.candidate_sha,"candidate_sha"); _sha40(self.synthetic_sha,"synthetic_sha")
        _sha40(self.candidate_tree,"candidate_tree")
        for n in ("live_database_sha256","pre_schema_digest","schema_sql_sha256","snapshot_sha256","expected_post_schema_digest","separation_plan_digest"): _sha256(getattr(self,n),n)
        if self.requester_principal in {DEPLOYER_USER,MIGRATOR_USER,RUNTIME_USER}: raise HostAuthorityContractError("requester cannot own migration effect")
        _utc(self.requested_at,"requested_at"); return self
    def digest(self): self.validate(); return _digest(b"LION/BOUNDED-SCHEMA-MIGRATION-REQUEST/1\0",asdict(self))

@dataclass(frozen=True)
class BrokerPermit:
    permit_id:str; operation_kind:str; request_digest:str; separation_plan_digest:str; fixed_executor_principal:str
    fixed_destination:str; fixed_payload_digest:str; currentness_digest:str; recovery_evidence_digest:str; authority_identity_digest:str; issued_at:str
    def validate(self):
        _txt(self.permit_id,"permit_id"); _txt(self.operation_kind,"operation_kind"); _sha256(self.request_digest,"request_digest"); _sha256(self.separation_plan_digest,"separation_plan_digest")
        _txt(self.fixed_executor_principal,"fixed_executor_principal"); _txt(self.fixed_destination,"fixed_destination",4096)
        for n in ("fixed_payload_digest","currentness_digest","recovery_evidence_digest","authority_identity_digest"): _sha256(getattr(self,n),n)
        _utc(self.issued_at,"issued_at")
        if self.operation_kind=="DEPLOY_EXACT_CANDIDATE":
            if self.fixed_executor_principal!=DEPLOYER_USER or self.fixed_destination!=RUNTIME_CODE_PATH: raise HostAuthorityContractError("deployment permit widened")
        elif self.operation_kind=="MIGRATE_EXACT_SCHEMA":
            if self.fixed_executor_principal!=MIGRATOR_USER or self.fixed_destination!=LIVE_DB_PATH: raise HostAuthorityContractError("migration permit widened")
        else: raise HostAuthorityContractError("permit operation invalid")
        return self
    def digest(self): self.validate(); return _digest(b"LION/BROKER-PERMIT/1\0",asdict(self))

@dataclass(frozen=True)
class DeploymentReceipt:
    receipt_id:str; request_digest:str; permit_digest:str; status:str; pre_manifest_sha256:str; post_manifest_sha256:str; deployed_candidate_sha:str; deployed_candidate_tree:str; observed_at:str
    def validate(self):
        _txt(self.receipt_id,"receipt_id"); _sha256(self.request_digest,"request_digest"); _sha256(self.permit_digest,"permit_digest")
        if self.status not in {"DEPLOYED","ROLLED_BACK"}: raise HostAuthorityContractError("deployment receipt status invalid")
        _sha256(self.pre_manifest_sha256,"pre_manifest_sha256"); _sha256(self.post_manifest_sha256,"post_manifest_sha256")
        _sha40(self.deployed_candidate_sha,"deployed_candidate_sha"); _sha40(self.deployed_candidate_tree,"deployed_candidate_tree"); _utc(self.observed_at,"observed_at"); return self

@dataclass(frozen=True)
class MigrationReceipt:
    receipt_id:str; request_digest:str; permit_digest:str; snapshot_sha256:str; pre_schema_digest:str; post_schema_digest:str
    preserved_pr_bootstrap_rows:int; preserved_authority_lineage_rows:int; status:str; observed_at:str
    def validate(self):
        _txt(self.receipt_id,"receipt_id"); _sha256(self.request_digest,"request_digest"); _sha256(self.permit_digest,"permit_digest"); _sha256(self.snapshot_sha256,"snapshot_sha256"); _sha256(self.pre_schema_digest,"pre_schema_digest"); _sha256(self.post_schema_digest,"post_schema_digest")
        if self.status not in {"MIGRATED","ROLLED_BACK"}: raise HostAuthorityContractError("migration receipt status invalid")
        if type(self.preserved_pr_bootstrap_rows) is not int or self.preserved_pr_bootstrap_rows<0 or type(self.preserved_authority_lineage_rows) is not int or self.preserved_authority_lineage_rows<0: raise HostAuthorityContractError("preserved row count invalid")
        _utc(self.observed_at,"observed_at"); return self
