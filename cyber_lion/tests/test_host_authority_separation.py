from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile, unittest
from cyber_lion.contracts.host_authority_separation import *
from cyber_lion.enterprise.host_authority_separation import *
import cyber_lion.enterprise.host_authority_separation as hostsep
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

T="2026-08-27T17:00:00Z"; H="a"*64; H2="b"*64; H3="c"*64
BASE="cee225c637524df5b35fa322114c1336d4d5eaf3"; BASE_TREE="8dd5ccb76e6722c95d42f38e7bd31db6519af0dd"
CAND="e091cf86cc297df92c8c82a2e877ddbf4c81ff6d"; CAND_TREE="7b49fea124e14a0032b148608b21ecdbbc89c0c6"

class HostAuthoritySeparationTests(unittest.TestCase):
    def binding(self): return TrustedRuntimeReadBinding("/opt/lion/trusted-runtime/workflow-dispatch-test/runtime_provider.py",H)
    def plan(self): return HostAuthoritySeparationBroker.canonical_plan(baseline_sha=BASE,baseline_tree=BASE_TREE,candidate_sha=CAND,candidate_tree=CAND_TREE,trusted_runtime_reads=(self.binding(),),generated_at=T)
    def obs(self,**kw):
        d=dict(hostname="MOON",runtime_user=RUNTIME_USER,runner_user=RUNNER_USER,runner_groups=(RUNNER_USER,CONTROL_PLANE_GROUP),runner_db_read=True,runner_db_write=True,runner_service_env_read=True,runtime_code_write=False,runner_actions_private_key_read=False,runner_authority_private_key_read=False,live_db_sha256=H,deployed_manifest_sha256=H2,service_unit_sha256=H3,observed_at=T); d.update(kw); return HostAuthorityObservation(**d).validate()
    def authority(self,**kw):
        d=dict(issuer_subject_id="prod-issuer-1",trust_domain="prod.example",key_id="kms://issuer/1",algorithm="opaque-external",provenance_class="PRODUCTION_EXTERNAL",host_principal=None,private_key_on_host=False); d.update(kw); return ExternalAuthorityIdentity(**d).validate()
    def deploy_req(self,plan=None,**kw):
        p=plan or self.plan(); d=dict(request_id="deploy-1",repository=CANONICAL_REPOSITORY,baseline_sha=BASE,baseline_tree=BASE_TREE,candidate_sha=CAND,candidate_tree=CAND_TREE,source_manifest_sha256=H,current_deployed_manifest_sha256=H2,service_unit_sha256=H3,separation_plan_digest=p.digest(),requester_principal="candidate-builder",requested_at=T); d.update(kw); return DeploymentRequest(**d).validate()
    def schema_before(self,**kw):
        d=dict(database_sha256=H,schema_digest=H2,pr_bootstrap_rows=0,authority_lineage_rows=2,objects=PRESERVED_TABLES,integrity_check="ok",observed_at=T); d.update(kw); return SchemaObservation(**d).validate()
    def migration_req(self,plan=None,**kw):
        p=plan or self.plan(); d=dict(request_id="migrate-1",candidate_sha=CAND,candidate_tree=CAND_TREE,live_database_sha256=H,pre_schema_digest=H2,schema_sql_sha256=schema_sql_digest(),separation_plan_digest=p.digest(),requester_principal="candidate-builder",requested_at=T); d.update(kw); return SchemaMigrationRequest(**d).validate()
    def snapshot(self,**kw):
        d=dict(snapshot_path=SNAPSHOT_DIR+"/control-plane.pre.sqlite",source_database_sha256=H,snapshot_sha256=H3,integrity_check="ok",created_at=T); d.update(kw); return SnapshotAttestation(**d).validate()

    def test_observed_bypass_requires_host_transition(self):
        o=self.obs(); p=self.plan(); self.assertFalse(HostAuthoritySeparationBroker.target_observation_is_separated(o))
        tr=HostAuthoritySeparationBroker.derive_transition(o,p,generated_at=T); kinds={x.kind for x in tr.operations}
        self.assertIn("REMOVE_RUNNER_CONTROL_PLANE_GROUP",kinds); self.assertIn("DENY_RUNNER_DB_ACCESS",kinds); self.assertIn("DENY_RUNNER_SERVICE_ENV_ACCESS",kinds); self.assertIn("REOWN_RUNTIME_CODE_ROOT",kinds)
        self.assertNotIn(CONTROL_PLANE_GROUP,p.runner_target_groups); self.assertEqual(p.runtime_code_owner,"root")

    def test_target_state_closes_runner_capabilities(self):
        o=self.obs(runner_groups=(RUNNER_USER,TRUST_CLIENT_GROUP),runner_db_read=False,runner_db_write=False,runner_service_env_read=False)
        self.assertTrue(HostAuthoritySeparationBroker.target_observation_is_separated(o))

    def test_multiple_digest_pinned_runtime_reads_are_supported(self):
        binds=(self.binding(),TrustedRuntimeReadBinding("/opt/lion/trusted-runtime/actions-run-cancel-test/runtime_provider.py",H2))
        p=HostAuthoritySeparationBroker.canonical_plan(baseline_sha=BASE,baseline_tree=BASE_TREE,candidate_sha=CAND,candidate_tree=CAND_TREE,trusted_runtime_reads=binds,generated_at=T)
        tr=HostAuthoritySeparationBroker.derive_transition(self.obs(),p,generated_at=T)
        pins=[x for x in tr.operations if x.kind=="PIN_TRUST_CLIENT_RUNTIME_READ"]
        self.assertEqual(len(pins),2); self.assertEqual({x.expected_digest for x in pins},{H,H2})

    def test_role_separation_and_test_authority_promotion_denied(self):
        with self.assertRaises(HostAuthorityContractError): self.authority(provenance_class="TEST_ONLY")
        p=self.plan(); r=self.deploy_req(p)
        for principal in (DEPLOYER_USER,MIGRATOR_USER,RUNTIME_USER,RUNNER_USER):
            with self.subTest(principal=principal), self.assertRaises(HostAuthoritySeparationError):
                BoundedDeploymentBroker.admit(r,plan=p,authority=self.authority(host_principal=principal),current_master_sha=BASE,current_master_tree=BASE_TREE,current_candidate_sha=CAND,current_candidate_tree=CAND_TREE,current_deployed_manifest_sha256=H2,current_service_unit_sha256=H3,issued_at=T)

    def test_candidate_builder_cannot_self_deploy_or_migrate(self):
        for principal in (DEPLOYER_USER,MIGRATOR_USER,RUNTIME_USER):
            with self.subTest(principal=principal), self.assertRaises(HostAuthorityContractError): self.deploy_req(requester_principal=principal)
            with self.subTest(migration=principal), self.assertRaises(HostAuthorityContractError): self.migration_req(requester_principal=principal)

    def test_deployment_exact_binding_substitutions_denied(self):
        p=self.plan(); r=self.deploy_req(p); a=self.authority(); args=dict(plan=p,authority=a,current_master_sha=BASE,current_master_tree=BASE_TREE,current_candidate_sha=CAND,current_candidate_tree=CAND_TREE,current_deployed_manifest_sha256=H2,current_service_unit_sha256=H3,issued_at=T)
        self.assertEqual(BoundedDeploymentBroker.admit(r,**args).fixed_destination,RUNTIME_CODE_PATH)
        variants=(dict(current_master_sha="1"*40),dict(current_master_tree="1"*64),dict(current_candidate_sha="2"*40),dict(current_candidate_tree="2"*64),dict(current_deployed_manifest_sha256="3"*64),dict(current_service_unit_sha256="4"*64))
        for patch in variants:
            bad=args|patch
            with self.subTest(patch=patch), self.assertRaises(HostAuthoritySeparationError): BoundedDeploymentBroker.admit(r,**bad)

    def test_migration_requires_snapshot_exact_schema_and_add_only_payload(self):
        p=self.plan(); r=self.migration_req(p); b=self.schema_before(); s=self.snapshot(); a=self.authority()
        permit=BoundedSchemaMigrationBroker.admit(r,plan=p,authority=a,before=b,snapshot=s,current_candidate_sha=CAND,current_candidate_tree=CAND_TREE,issued_at=T)
        self.assertEqual(permit.fixed_destination,LIVE_DB_PATH)
        self.assertEqual(permit.fixed_payload_digest,schema_sql_digest())
        with self.assertRaises(HostAuthoritySeparationError): BoundedSchemaMigrationBroker.admit(replace(r,schema_sql_sha256="9"*64),plan=p,authority=a,before=b,snapshot=s,current_candidate_sha=CAND,current_candidate_tree=CAND_TREE,issued_at=T)
        with self.assertRaises(HostAuthoritySeparationError): BoundedSchemaMigrationBroker.admit(r,plan=p,authority=a,before=b,snapshot=replace(s,source_database_sha256="8"*64),current_candidate_sha=CAND,current_candidate_tree=CAND_TREE,issued_at=T)
        with self.assertRaises(HostAuthoritySeparationError): hostsep._validate_add_only_schema_sql("DROP TABLE pr_bootstrap;")
        with self.assertRaises(HostAuthoritySeparationError): hostsep._validate_add_only_schema_sql("INSERT INTO authority_lineage VALUES ('x');")

    def test_migration_postcondition_preserves_historical_authority(self):
        before=self.schema_before(); after=SchemaObservation(database_sha256=H3,schema_digest="d"*64,pr_bootstrap_rows=0,authority_lineage_rows=2,objects=PRESERVED_TABLES+PROVISIONING_TABLES+PROVISIONING_TRIGGERS,integrity_check="ok",observed_at=T).validate()
        self.assertIs(BoundedSchemaMigrationBroker.verify_postcondition(before,after),after)
        with self.assertRaises(HostAuthoritySeparationError): BoundedSchemaMigrationBroker.verify_postcondition(before,replace(after,authority_lineage_rows=3))
        with self.assertRaises(HostAuthoritySeparationError): BoundedSchemaMigrationBroker.verify_postcondition(before,replace(after,objects=PRESERVED_TABLES+PROVISIONING_TABLES))

    def test_no_shell_destination_verifier_or_secret_selection_from_requests(self):
        fields=set(DeploymentRequest.__dataclass_fields__)|set(SchemaMigrationRequest.__dataclass_fields__)
        for forbidden in ("shell","command","destination","deployer","migrator","verifier","private_key","secret","token","ddl","sql"):
            self.assertNotIn(forbidden,fields)
        src=Path("cyber_lion/enterprise/host_authority_separation.py").read_text()
        for forbidden in ("subprocess","os.system","requests","urllib","signing_secret","os.environ","os.getenv","importlib","eval(","exec(","open(","read_text(","read_bytes("):
            self.assertNotIn(forbidden,src)

    def test_complete_mediation_inventory_adds_no_unclassified_or_effect_surface(self):
        paths=("cyber_lion/contracts/host_authority_separation.py","cyber_lion/enterprise/host_authority_separation.py")
        sources={p:Path(p).read_text() for p in paths}
        inv=EffectSurfaceScanner().scan(repository=CANONICAL_REPOSITORY,revision=CAND,tree_digest=CAND_TREE,sources=sources)
        self.assertEqual(inv.unclassified_refs,())
        self.assertEqual(inv.surfaces,())

    def test_external_read_binding_is_digest_pinned_and_no_control_plane_escape(self):
        with self.assertRaises(HostAuthorityContractError): TrustedRuntimeReadBinding(LIVE_DB_PATH,H).validate()
        with self.assertRaises(HostAuthorityContractError): TrustedRuntimeReadBinding("/opt/lion/trusted-runtime/../control-plane-code/x",H).validate()

    def test_permit_is_evidence_not_authority_or_effect(self):
        p=self.plan(); permit=BoundedDeploymentBroker.admit(self.deploy_req(p),plan=p,authority=self.authority(),current_master_sha=BASE,current_master_tree=BASE_TREE,current_candidate_sha=CAND,current_candidate_tree=CAND_TREE,current_deployed_manifest_sha256=H2,current_service_unit_sha256=H3,issued_at=T)
        self.assertEqual(permit.fixed_executor_principal,"root")
        self.assertFalse(hasattr(permit,"execute")); self.assertFalse(hasattr(permit,"authority_grant")); self.assertFalse(hasattr(permit,"credential"))

if __name__=="__main__": unittest.main()
