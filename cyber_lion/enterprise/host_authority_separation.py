"""Pure fail-closed admission brokers for host separation, deployment and schema migration.

No method in this module performs an OS, filesystem, SQLite, GitHub, network, or process effect.
It only derives fixed operation manifests and permits that an external root-owned broker may
later execute after a separate effect-authority decision.
"""
from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import json,re
from cyber_lion.contracts.host_authority_separation import (
    BrokerPermit, CANONICAL_REPOSITORY, CONTROL_PLANE_GROUP, DEPLOYER_USER, DeploymentReceipt, DeploymentRequest,
    ExternalAuthorityIdentity, HostAuthorityContractError, HostAuthorityObservation,
    HostAuthoritySeparationPlan, HostOperation, HostTransitionPlan, LIVE_DB_PATH, MIGRATOR_USER, MigrationReceipt,
    PRESERVED_TABLES, PROVISIONING_TABLES, PROVISIONING_TRIGGERS, RUNTIME_CODE_PATH, RUNTIME_USER,
    RUNNER_USER, SERVICE_ENV_PATH, SERVICE_UNIT_PATH, SchemaMigrationRequest, SchemaObservation,
    SnapshotAttestation, TRUST_CLIENT_GROUP, TrustedRuntimeReadBinding,
)
from cyber_lion.enterprise.authority_provisioning import authority_provisioning_schema_sql

class HostAuthoritySeparationError(HostAuthorityContractError): pass

def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _digest(domain,v): return sha256(domain+_canon(v)).hexdigest()
def schema_sql_digest(): return sha256(authority_provisioning_schema_sql().encode()).hexdigest()

def _validate_add_only_schema_sql(sql:str)->None:
    low=sql.lower()
    if low.count("create table if not exists ")!=5 or low.count("create trigger if not exists ")!=2:
        raise HostAuthoritySeparationError("canonical add-only object count mismatch")
    if re.search(r"\bdrop\b|\balter\b|\binsert\s+into\b|\bupdate\s+\w+\s+set\b|\bdelete\s+from\b|\breplace\s+into\b|\bvacuum\b|\battach\b|\bdetach\b",low):
        raise HostAuthoritySeparationError("destructive or data-mutating schema SQL denied")
    for trigger in PROVISIONING_TRIGGERS:
        if trigger not in low:
            raise HostAuthoritySeparationError("append-only trigger missing")
    if low.count("select raise(abort")!=2:
        raise HostAuthoritySeparationError("append-only trigger guards missing")
    required=set(PROVISIONING_TABLES+PRESERVED_TABLES+PROVISIONING_TRIGGERS)
    if any(name not in low for name in required):
        raise HostAuthoritySeparationError("schema SQL missing canonical objects")

class HostAuthoritySeparationBroker:
    @staticmethod
    def canonical_plan(*,baseline_sha:str,baseline_tree:str,candidate_sha:str,candidate_tree:str,certified_synthetic_sha:str,certified_source_manifest_sha256:str,certified_post_schema_digest:str,trusted_runtime_reads:tuple[TrustedRuntimeReadBinding,...],generated_at:str)->HostAuthoritySeparationPlan:
        plan=HostAuthoritySeparationPlan(
            plan_id=f"host-separation:{candidate_sha}",repository=CANONICAL_REPOSITORY,baseline_sha=baseline_sha,baseline_tree=baseline_tree,
            certified_candidate_sha=candidate_sha,certified_candidate_tree=candidate_tree,certified_synthetic_sha=certified_synthetic_sha,
            certified_source_manifest_sha256=certified_source_manifest_sha256,certified_post_schema_digest=certified_post_schema_digest,
            runtime_user=RUNTIME_USER,runner_user=RUNNER_USER,deployer_user=DEPLOYER_USER,migrator_user=MIGRATOR_USER,
            control_plane_group=CONTROL_PLANE_GROUP,trust_client_group=TRUST_CLIENT_GROUP,runtime_code_path=RUNTIME_CODE_PATH,
            live_db_path=LIVE_DB_PATH,service_env_path=SERVICE_ENV_PATH,service_unit_path=SERVICE_UNIT_PATH,
            runtime_code_owner="root",runtime_code_group=CONTROL_PLANE_GROUP,runtime_code_dir_mode=0o550,runtime_code_file_mode=0o440,
            runner_target_groups=(RUNNER_USER,TRUST_CLIENT_GROUP),trusted_runtime_reads=trusted_runtime_reads,
            production_private_key_on_host=False,generated_at=generated_at)
        return plan.validate()

    @staticmethod
    def derive_transition(observation:HostAuthorityObservation,plan:HostAuthoritySeparationPlan,*,generated_at:str)->HostTransitionPlan:
        if type(observation) is not HostAuthorityObservation or type(plan) is not HostAuthoritySeparationPlan: raise HostAuthoritySeparationError("exact observation and plan required")
        observation.validate(); plan.validate()
        if (observation.runtime_user,observation.runner_user)!=(plan.runtime_user,plan.runner_user): raise HostAuthoritySeparationError("host principal currentness drift")
        ops=[]
        if CONTROL_PLANE_GROUP in observation.runner_groups: ops.append(HostOperation("REMOVE_RUNNER_CONTROL_PLANE_GROUP",RUNNER_USER,CONTROL_PLANE_GROUP,None,"remove runner from control-plane supplementary group"))
        if TRUST_CLIENT_GROUP not in observation.runner_groups: ops.append(HostOperation("ENSURE_TRUST_CLIENT_GROUP",DEPLOYER_USER,TRUST_CLIENT_GROUP,None,"ensure dedicated non-authority trust-client group")); ops.append(HostOperation("ADD_RUNNER_TRUST_CLIENT_GROUP",RUNNER_USER,TRUST_CLIENT_GROUP,None,"grant only bounded external-runtime read membership"))
        ops.append(HostOperation("REOWN_RUNTIME_CODE_ROOT",DEPLOYER_USER,RUNTIME_CODE_PATH,observation.deployed_manifest_sha256,"root owns immutable runtime code"))
        ops.append(HostOperation("SET_RUNTIME_CODE_READ_ONLY",DEPLOYER_USER,RUNTIME_CODE_PATH,observation.deployed_manifest_sha256,"directories 0550 files 0440; runtime is read-only"))
        for b in plan.trusted_runtime_reads: ops.append(HostOperation("PIN_TRUST_CLIENT_RUNTIME_READ",DEPLOYER_USER,b.path,b.sha256_digest,"expose this file read-only to trust-client group only"))
        ops.append(HostOperation("DENY_RUNNER_DB_ACCESS",DEPLOYER_USER,LIVE_DB_PATH,observation.live_db_sha256,"runner must have neither read nor write access"))
        ops.append(HostOperation("DENY_RUNNER_SERVICE_ENV_ACCESS",DEPLOYER_USER,SERVICE_ENV_PATH,None,"runner must not read service credential environment"))
        ops.append(HostOperation("INSTALL_BOUNDED_DEPLOYMENT_BROKER",DEPLOYER_USER,RUNTIME_CODE_PATH,None,"fixed operation, fixed destination, no arbitrary shell"))
        ops.append(HostOperation("INSTALL_BOUNDED_SCHEMA_MIGRATION_BROKER",MIGRATOR_USER,LIVE_DB_PATH,None,"exact add-only schema transition only"))
        uniq=[]; seen=set()
        for op in ops:
            op.validate(); key=(op.kind,op.target)
            if key not in seen: seen.add(key); uniq.append(op)
        return HostTransitionPlan(f"host-transition:{observation.digest()[:20]}:{plan.digest()[:20]}",observation.digest(),plan.digest(),tuple(uniq),generated_at).validate()

    @staticmethod
    def target_observation_is_separated(observation:HostAuthorityObservation)->bool:
        observation.validate()
        return (CONTROL_PLANE_GROUP not in observation.runner_groups and TRUST_CLIENT_GROUP in observation.runner_groups and not observation.runner_db_read and not observation.runner_db_write and not observation.runner_service_env_read and not observation.runtime_code_write and not observation.runner_actions_private_key_read and not observation.runner_authority_private_key_read)


def _deployment_currentness_digest(request:DeploymentRequest,*,current_master_sha:str,current_master_tree:str,current_candidate_sha:str,current_candidate_tree:str,current_synthetic_sha:str,current_source_manifest_sha256:str,current_deployed_manifest_sha256:str,current_service_unit_sha256:str)->str:
    return _digest(b"LION/DEPLOYMENT-CURRENTNESS/1\0",{
        "repository":request.repository,"baseline_sha":current_master_sha,"baseline_tree":current_master_tree,
        "candidate_sha":current_candidate_sha,"candidate_tree":current_candidate_tree,"synthetic_sha":current_synthetic_sha,
        "source_manifest_sha256":current_source_manifest_sha256,"deployed_manifest_sha256":current_deployed_manifest_sha256,
        "service_unit_sha256":current_service_unit_sha256,
    })


def _migration_currentness_digest(request:SchemaMigrationRequest,*,current_candidate_sha:str,current_candidate_tree:str,current_synthetic_sha:str,before:SchemaObservation,snapshot:SnapshotAttestation)->str:
    return _digest(b"LION/MIGRATION-CURRENTNESS/1\0",{
        "candidate_sha":current_candidate_sha,"candidate_tree":current_candidate_tree,"synthetic_sha":current_synthetic_sha,
        "live_database_sha256":before.database_sha256,"pre_schema_digest":before.schema_digest,
        "schema_sql_sha256":request.schema_sql_sha256,"snapshot_source_database_sha256":snapshot.source_database_sha256,
        "snapshot_sha256":snapshot.snapshot_sha256,"expected_post_schema_digest":request.expected_post_schema_digest,
    })


class BoundedDeploymentBroker:
    @staticmethod
    def admit(request:DeploymentRequest,*,plan:HostAuthoritySeparationPlan,authority:ExternalAuthorityIdentity,current_master_sha:str,current_master_tree:str,current_candidate_sha:str,current_candidate_tree:str,current_synthetic_sha:str,current_source_manifest_sha256:str,current_deployed_manifest_sha256:str,current_service_unit_sha256:str,issued_at:str)->BrokerPermit:
        if type(request) is not DeploymentRequest or type(plan) is not HostAuthoritySeparationPlan or type(authority) is not ExternalAuthorityIdentity: raise HostAuthoritySeparationError("exact deployment admission types required")
        request.validate(); plan.validate(); authority.validate()
        if authority.host_principal in {plan.deployer_user,plan.migrator_user,plan.runtime_user,plan.runner_user}: raise HostAuthoritySeparationError("authority issuer overlaps host execution principal")
        if request.separation_plan_digest!=plan.digest(): raise HostAuthoritySeparationError("deployment plan digest mismatch")
        if (request.baseline_sha,request.baseline_tree)!=(current_master_sha,current_master_tree): raise HostAuthoritySeparationError("master currentness drift")
        if (request.candidate_sha,request.candidate_tree)!=(current_candidate_sha,current_candidate_tree): raise HostAuthoritySeparationError("candidate currentness drift")
        if request.synthetic_sha!=current_synthetic_sha: raise HostAuthoritySeparationError("synthetic merge currentness drift")
        if request.source_manifest_sha256!=current_source_manifest_sha256: raise HostAuthoritySeparationError("source manifest currentness drift")
        if (request.current_deployed_manifest_sha256,request.service_unit_sha256)!=(current_deployed_manifest_sha256,current_service_unit_sha256): raise HostAuthoritySeparationError("deployed host currentness drift")
        if (request.baseline_sha,request.baseline_tree,request.candidate_sha,request.candidate_tree,request.synthetic_sha,request.source_manifest_sha256)!=(plan.baseline_sha,plan.baseline_tree,plan.certified_candidate_sha,plan.certified_candidate_tree,plan.certified_synthetic_sha,plan.certified_source_manifest_sha256): raise HostAuthoritySeparationError("request not bound to certified plan")
        aid=_digest(b"LION/EXTERNAL-AUTHORITY-IDENTITY/1\0",asdict(authority))
        currentness=_deployment_currentness_digest(request,current_master_sha=current_master_sha,current_master_tree=current_master_tree,current_candidate_sha=current_candidate_sha,current_candidate_tree=current_candidate_tree,current_synthetic_sha=current_synthetic_sha,current_source_manifest_sha256=current_source_manifest_sha256,current_deployed_manifest_sha256=current_deployed_manifest_sha256,current_service_unit_sha256=current_service_unit_sha256)
        return BrokerPermit(f"deployment-permit:{request.digest()}","DEPLOY_EXACT_CANDIDATE",request.digest(),plan.digest(),DEPLOYER_USER,RUNTIME_CODE_PATH,request.source_manifest_sha256,currentness,current_deployed_manifest_sha256,aid,issued_at).validate()

    @staticmethod
    def revalidate_before_effect(request:DeploymentRequest,permit:BrokerPermit,*,plan:HostAuthoritySeparationPlan,current_master_sha:str,current_master_tree:str,current_candidate_sha:str,current_candidate_tree:str,current_synthetic_sha:str,current_source_manifest_sha256:str,current_deployed_manifest_sha256:str,current_service_unit_sha256:str)->BrokerPermit:
        if type(request) is not DeploymentRequest or type(permit) is not BrokerPermit or type(plan) is not HostAuthoritySeparationPlan: raise HostAuthoritySeparationError("exact deployment revalidation types required")
        request.validate(); permit.validate(); plan.validate()
        if permit.operation_kind!="DEPLOY_EXACT_CANDIDATE" or permit.fixed_executor_principal!=DEPLOYER_USER or permit.fixed_destination!=RUNTIME_CODE_PATH: raise HostAuthoritySeparationError("deployment permit identity mismatch")
        if permit.request_digest!=request.digest() or permit.separation_plan_digest!=plan.digest(): raise HostAuthoritySeparationError("deployment permit binding mismatch")
        if permit.fixed_payload_digest!=request.source_manifest_sha256: raise HostAuthoritySeparationError("deployment payload digest mismatch")
        if (request.baseline_sha,request.baseline_tree)!=(current_master_sha,current_master_tree) or (request.baseline_sha,request.baseline_tree)!=(plan.baseline_sha,plan.baseline_tree): raise HostAuthoritySeparationError("master currentness drift")
        if (request.candidate_sha,request.candidate_tree)!=(current_candidate_sha,current_candidate_tree) or (request.candidate_sha,request.candidate_tree)!=(plan.certified_candidate_sha,plan.certified_candidate_tree): raise HostAuthoritySeparationError("candidate currentness drift")
        if request.synthetic_sha!=current_synthetic_sha or request.synthetic_sha!=plan.certified_synthetic_sha: raise HostAuthoritySeparationError("synthetic merge currentness drift")
        if request.source_manifest_sha256!=current_source_manifest_sha256 or request.source_manifest_sha256!=plan.certified_source_manifest_sha256: raise HostAuthoritySeparationError("source manifest currentness drift")
        if (request.current_deployed_manifest_sha256,request.service_unit_sha256)!=(current_deployed_manifest_sha256,current_service_unit_sha256): raise HostAuthoritySeparationError("deployed host currentness drift")
        expected=_deployment_currentness_digest(request,current_master_sha=current_master_sha,current_master_tree=current_master_tree,current_candidate_sha=current_candidate_sha,current_candidate_tree=current_candidate_tree,current_synthetic_sha=current_synthetic_sha,current_source_manifest_sha256=current_source_manifest_sha256,current_deployed_manifest_sha256=current_deployed_manifest_sha256,current_service_unit_sha256=current_service_unit_sha256)
        if permit.currentness_digest!=expected or permit.recovery_evidence_digest!=current_deployed_manifest_sha256: raise HostAuthoritySeparationError("deployment permit stale currentness evidence")
        return permit

    @staticmethod
    def verify_receipt(request:DeploymentRequest,permit:BrokerPermit,receipt:DeploymentReceipt)->DeploymentReceipt:
        if type(request) is not DeploymentRequest or type(permit) is not BrokerPermit or type(receipt) is not DeploymentReceipt: raise HostAuthoritySeparationError("exact deployment receipt types required")
        request.validate(); permit.validate(); receipt.validate()
        if permit.operation_kind!="DEPLOY_EXACT_CANDIDATE" or permit.request_digest!=request.digest(): raise HostAuthoritySeparationError("deployment permit/request mismatch")
        if receipt.request_digest!=request.digest() or receipt.permit_digest!=permit.digest(): raise HostAuthoritySeparationError("deployment receipt binding mismatch")
        if receipt.pre_manifest_sha256!=request.current_deployed_manifest_sha256: raise HostAuthoritySeparationError("deployment receipt pre-state mismatch")
        if (receipt.deployed_candidate_sha,receipt.deployed_candidate_tree)!=(request.candidate_sha,request.candidate_tree): raise HostAuthoritySeparationError("deployment receipt candidate mismatch")
        if receipt.status=="ROLLED_BACK" and receipt.post_manifest_sha256!=receipt.pre_manifest_sha256: raise HostAuthoritySeparationError("deployment rollback receipt mismatch")
        return receipt


class BoundedSchemaMigrationBroker:
    @staticmethod
    def admit(request:SchemaMigrationRequest,*,plan:HostAuthoritySeparationPlan,authority:ExternalAuthorityIdentity,before:SchemaObservation,snapshot:SnapshotAttestation,current_candidate_sha:str,current_candidate_tree:str,current_synthetic_sha:str,issued_at:str)->BrokerPermit:
        if type(request) is not SchemaMigrationRequest or type(plan) is not HostAuthoritySeparationPlan or type(authority) is not ExternalAuthorityIdentity or type(before) is not SchemaObservation or type(snapshot) is not SnapshotAttestation: raise HostAuthoritySeparationError("exact migration admission types required")
        request.validate(); plan.validate(); authority.validate(); before.validate(); snapshot.validate()
        if authority.host_principal in {plan.deployer_user,plan.migrator_user,plan.runtime_user,plan.runner_user}: raise HostAuthoritySeparationError("authority issuer overlaps migration principal")
        _validate_add_only_schema_sql(authority_provisioning_schema_sql())
        if request.schema_sql_sha256!=schema_sql_digest(): raise HostAuthoritySeparationError("schema digest substitution denied")
        if request.separation_plan_digest!=plan.digest(): raise HostAuthoritySeparationError("migration plan digest mismatch")
        if (request.candidate_sha,request.candidate_tree)!=(current_candidate_sha,current_candidate_tree) or (request.candidate_sha,request.candidate_tree)!=(plan.certified_candidate_sha,plan.certified_candidate_tree): raise HostAuthoritySeparationError("candidate currentness drift")
        if request.synthetic_sha!=current_synthetic_sha or request.synthetic_sha!=plan.certified_synthetic_sha: raise HostAuthoritySeparationError("synthetic merge currentness drift")
        if request.live_database_sha256!=before.database_sha256 or request.pre_schema_digest!=before.schema_digest: raise HostAuthoritySeparationError("database/schema substitution denied")
        if snapshot.source_database_sha256!=before.database_sha256: raise HostAuthoritySeparationError("snapshot source digest mismatch")
        if request.snapshot_sha256!=snapshot.snapshot_sha256: raise HostAuthoritySeparationError("snapshot digest substitution denied")
        if request.expected_post_schema_digest!=plan.certified_post_schema_digest: raise HostAuthoritySeparationError("post-schema digest not bound to certified plan")
        aid=_digest(b"LION/EXTERNAL-AUTHORITY-IDENTITY/1\0",asdict(authority))
        currentness=_migration_currentness_digest(request,current_candidate_sha=current_candidate_sha,current_candidate_tree=current_candidate_tree,current_synthetic_sha=current_synthetic_sha,before=before,snapshot=snapshot)
        return BrokerPermit(f"migration-permit:{request.digest()}","MIGRATE_EXACT_SCHEMA",request.digest(),plan.digest(),MIGRATOR_USER,LIVE_DB_PATH,request.schema_sql_sha256,currentness,snapshot.snapshot_sha256,aid,issued_at).validate()

    @staticmethod
    def revalidate_before_effect(request:SchemaMigrationRequest,permit:BrokerPermit,*,plan:HostAuthoritySeparationPlan,before:SchemaObservation,snapshot:SnapshotAttestation,current_candidate_sha:str,current_candidate_tree:str,current_synthetic_sha:str)->BrokerPermit:
        if type(request) is not SchemaMigrationRequest or type(permit) is not BrokerPermit or type(plan) is not HostAuthoritySeparationPlan or type(before) is not SchemaObservation or type(snapshot) is not SnapshotAttestation: raise HostAuthoritySeparationError("exact migration revalidation types required")
        request.validate(); permit.validate(); plan.validate(); before.validate(); snapshot.validate()
        if permit.operation_kind!="MIGRATE_EXACT_SCHEMA" or permit.fixed_executor_principal!=MIGRATOR_USER or permit.fixed_destination!=LIVE_DB_PATH: raise HostAuthoritySeparationError("migration permit identity mismatch")
        if permit.request_digest!=request.digest() or permit.separation_plan_digest!=plan.digest() or permit.fixed_payload_digest!=request.schema_sql_sha256: raise HostAuthoritySeparationError("migration permit binding mismatch")
        if (request.candidate_sha,request.candidate_tree)!=(current_candidate_sha,current_candidate_tree) or (request.candidate_sha,request.candidate_tree)!=(plan.certified_candidate_sha,plan.certified_candidate_tree): raise HostAuthoritySeparationError("candidate currentness drift")
        if request.synthetic_sha!=current_synthetic_sha or request.synthetic_sha!=plan.certified_synthetic_sha: raise HostAuthoritySeparationError("synthetic merge currentness drift")
        if request.live_database_sha256!=before.database_sha256 or request.pre_schema_digest!=before.schema_digest: raise HostAuthoritySeparationError("database/schema substitution denied")
        if snapshot.source_database_sha256!=before.database_sha256 or request.snapshot_sha256!=snapshot.snapshot_sha256: raise HostAuthoritySeparationError("snapshot currentness drift")
        if request.expected_post_schema_digest!=plan.certified_post_schema_digest: raise HostAuthoritySeparationError("post-schema digest not bound to certified plan")
        expected=_migration_currentness_digest(request,current_candidate_sha=current_candidate_sha,current_candidate_tree=current_candidate_tree,current_synthetic_sha=current_synthetic_sha,before=before,snapshot=snapshot)
        if permit.currentness_digest!=expected or permit.recovery_evidence_digest!=snapshot.snapshot_sha256: raise HostAuthoritySeparationError("migration permit stale currentness evidence")
        return permit

    @staticmethod
    def verify_postcondition(before:SchemaObservation,after:SchemaObservation,*,expected_post_schema_digest:str)->SchemaObservation:
        if type(before) is not SchemaObservation or type(after) is not SchemaObservation: raise HostAuthoritySeparationError("exact schema observations required")
        before.validate(); after.validate()
        if after.schema_digest!=expected_post_schema_digest: raise HostAuthoritySeparationError("post-schema digest mismatch")
        if before.pr_bootstrap_rows!=after.pr_bootstrap_rows or before.authority_lineage_rows!=after.authority_lineage_rows: raise HostAuthoritySeparationError("historical authority rows changed during migration")
        required=set(PROVISIONING_TABLES+PRESERVED_TABLES+PROVISIONING_TRIGGERS)
        if not required.issubset(set(after.objects)): raise HostAuthoritySeparationError("partial migration denied")
        if after.database_sha256==before.database_sha256: raise HostAuthoritySeparationError("migration produced no database state change")
        return after

    @staticmethod
    def verify_receipt(request:SchemaMigrationRequest,permit:BrokerPermit,before:SchemaObservation,snapshot:SnapshotAttestation,after:SchemaObservation,receipt:MigrationReceipt)->MigrationReceipt:
        if type(request) is not SchemaMigrationRequest or type(permit) is not BrokerPermit or type(before) is not SchemaObservation or type(snapshot) is not SnapshotAttestation or type(after) is not SchemaObservation or type(receipt) is not MigrationReceipt: raise HostAuthoritySeparationError("exact migration receipt types required")
        request.validate(); permit.validate(); before.validate(); snapshot.validate(); after.validate(); receipt.validate()
        if permit.operation_kind!="MIGRATE_EXACT_SCHEMA" or permit.request_digest!=request.digest(): raise HostAuthoritySeparationError("migration permit/request mismatch")
        if receipt.request_digest!=request.digest() or receipt.permit_digest!=permit.digest(): raise HostAuthoritySeparationError("migration receipt binding mismatch")
        if receipt.snapshot_sha256!=request.snapshot_sha256 or receipt.snapshot_sha256!=snapshot.snapshot_sha256: raise HostAuthoritySeparationError("migration receipt snapshot mismatch")
        if receipt.pre_schema_digest!=request.pre_schema_digest or receipt.pre_schema_digest!=before.schema_digest: raise HostAuthoritySeparationError("migration receipt pre-schema mismatch")
        if (receipt.preserved_pr_bootstrap_rows,receipt.preserved_authority_lineage_rows)!=(before.pr_bootstrap_rows,before.authority_lineage_rows): raise HostAuthoritySeparationError("migration receipt historical row mismatch")
        if receipt.status=="MIGRATED":
            BoundedSchemaMigrationBroker.verify_postcondition(before,after,expected_post_schema_digest=request.expected_post_schema_digest)
            if receipt.post_schema_digest!=after.schema_digest: raise HostAuthoritySeparationError("migration receipt post-schema mismatch")
        else:
            if after.database_sha256!=before.database_sha256 or after.schema_digest!=before.schema_digest or receipt.post_schema_digest!=before.schema_digest: raise HostAuthoritySeparationError("migration rollback receipt mismatch")
        return receipt
