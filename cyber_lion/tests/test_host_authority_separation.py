from __future__ import annotations
from dataclasses import replace
from hashlib import sha1,sha256
import inspect,json
from pathlib import Path
import unittest
from cyber_lion.contracts.host_authority_separation import *
from cyber_lion.enterprise.host_authority_separation import *
import cyber_lion.enterprise.host_authority_separation as hostsep
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

T="2026-08-27T21:00:00Z"; H="a"*64; H2="b"*64; H3="c"*64; H4="d"*64; H5="e"*64
BASE_REF="mission/e006-r9d-9g3a1-authority-provisioning-plane"; HEAD_REF="mission/e006-r9d-9g3a1-host-authority-separation-deployment-plane"

def commit_obj(tree:str,parents:tuple[str,...]=(),message:str="fixture")->bytes:
    lines=[f"tree {tree}",*(f"parent {p}" for p in parents),"author Fixture <fixture@example> 1 +0000","committer Fixture <fixture@example> 1 +0000","",message,""]
    return "\n".join(lines).encode()
def oid(raw:bytes)->str: return sha1(f"commit {len(raw)}\0".encode()+raw).hexdigest()

class HostAuthoritySeparationTests(unittest.TestCase):
    def repo_provider(self,obs="repo-fixture"): return hostsep._mint_provider_token(CANONICAL_REPOSITORY_PROVIDER,obs)
    def tree_provider(self,obs="tree-fixture"): return hostsep._mint_provider_token(hostsep.CANDIDATE_TREE_PROVIDER,obs)
    def schema_provider(self,obs="schema-fixture"): return hostsep._mint_provider_token(hostsep.SCHEMA_MANIFEST_PROVIDER,obs)
    def snapshot_provider(self,obs="snapshot-fixture"): return hostsep._mint_provider_token(CANONICAL_SNAPSHOTTER_IDENTITY,obs)
    def tree_evidence(self):
        files=((".github/workflows/x.yml","100644",b"name: x\n"),("README.md","100644",b"fixture\n"),("cyber_lion/enterprise/x.py","100644",b"VALUE=1\n"),("cyber_lion/tests/test_x.py","100644",b"pass\n"))
        return derive_candidate_tree_evidence(self.tree_provider(),files)
    def repo_evidence(self,tree=None):
        tree=tree or self.tree_evidence(); base_raw=commit_obj("1"*40,(),"base"); base=oid(base_raw); head_raw=commit_obj(tree.tree_sha,(base,),"head"); head=oid(head_raw); syn_raw=commit_obj(tree.tree_sha,(base,head),"merge"); syn=oid(syn_raw)
        pr={"number":234,"base":{"ref":BASE_REF,"sha":base,"repo":{"full_name":CANONICAL_REPOSITORY}},"head":{"ref":HEAD_REF,"sha":head,"repo":{"full_name":CANONICAL_REPOSITORY}},"merge_commit_sha":syn}
        return derive_repository_currentness_evidence(self.repo_provider(),pr_payload=json.dumps(pr,sort_keys=True,separators=(",",":")).encode(),base_commit_object=base_raw,head_commit_object=head_raw,synthetic_commit_object=syn_raw,observed_at=T)
    def pre_schema(self):
        rows=(("table","pr_bootstrap","pr_bootstrap","CREATE TABLE pr_bootstrap(x TEXT)"),("table","authority_lineage","authority_lineage","CREATE TABLE authority_lineage(x TEXT)"))
        return derive_schema_manifest_evidence(self.schema_provider(),rows)
    def plan(self):
        tree=self.tree_evidence(); repo=self.repo_evidence(tree); pre=self.pre_schema()
        return HostAuthoritySeparationBroker.canonical_plan(repository_evidence=repo,candidate_tree_evidence=tree,pre_schema_evidence=pre,trusted_runtime_reads=(TrustedRuntimeReadBinding("/opt/lion/trusted-runtime/workflow-dispatch-test/runtime_provider.py",H),),generated_at=T),repo,tree,pre
    def authority(self,**kw):
        d=dict(issuer_subject_id="prod-issuer-1",trust_domain="prod.example",key_id="kms://issuer/1",algorithm="opaque-external",provenance_class="PRODUCTION_EXTERNAL",host_principal=None,private_key_on_host=False); d.update(kw); return ExternalAuthorityIdentity(**d).validate()
    def host_obs(self,**kw):
        d=dict(hostname="MOON",runtime_user=RUNTIME_USER,runner_user=RUNNER_USER,runner_groups=(RUNNER_USER,CONTROL_PLANE_GROUP),runner_db_read=True,runner_db_write=True,runner_service_env_read=True,runtime_code_write=False,runner_actions_private_key_read=False,runner_authority_private_key_read=False,live_db_sha256=H,deployed_manifest_sha256=H2,service_unit_sha256=H3,observed_at=T); d.update(kw); return HostAuthorityObservation(**d).validate()
    def deploy_req(self,p,repo,tree,**kw):
        d=dict(request_id="deploy-1",repository=repo.repository,pr_number=repo.pr_number,baseline_ref=repo.base_ref,baseline_sha=repo.base_sha,baseline_tree=repo.base_tree,candidate_ref=repo.head_ref,candidate_sha=repo.head_sha,candidate_tree=repo.head_tree,synthetic_sha=repo.synthetic_sha,repository_evidence_digest=repo.digest(),source_manifest_sha256=tree.production_manifest_sha256,current_deployed_manifest_sha256=H2,service_unit_sha256=H3,separation_plan_digest=p.digest(),requester_principal="candidate-builder",requested_at=T); d.update(kw); return DeploymentRequest(**d).validate()
    def deploy_args(self,p,repo,tree,**kw):
        d=dict(plan=p,authority=self.authority(),repository_evidence=repo,candidate_tree_evidence=tree,current_deployed_manifest_sha256=H2,current_service_unit_sha256=H3,issued_at=T); d.update(kw); return d
    def before(self,pre,**kw):
        d=dict(database_sha256=H,schema_digest=pre.digest(),pr_bootstrap_rows=0,authority_lineage_rows=2,objects=PRESERVED_TABLES,integrity_check="ok",observed_at=T); d.update(kw); return SchemaObservation(**d).validate()
    def snapshot(self,before): return derive_snapshot_provenance(self.snapshot_provider(),source_observation=before,snapshot_path=SNAPSHOT_DIR+"/control-plane.pre.sqlite",snapshot_bytes=b"actual-consistent-snapshot-bytes",integrity_check="ok",created_at=T)
    def migration_req(self,p,repo,pre,snap,**kw):
        d=dict(request_id="migrate-1",repository=repo.repository,pr_number=repo.pr_number,candidate_ref=repo.head_ref,candidate_sha=repo.head_sha,candidate_tree=repo.head_tree,synthetic_sha=repo.synthetic_sha,repository_evidence_digest=repo.digest(),live_database_sha256=H,pre_schema_digest=pre.digest(),schema_sql_sha256=CANONICAL_SCHEMA_SQL_SHA256,snapshot_sha256=snap.attestation.snapshot_sha256,expected_post_schema_digest=derive_expected_post_schema_evidence(pre).digest(),separation_plan_digest=p.digest(),requester_principal="candidate-builder",requested_at=T); d.update(kw); return SchemaMigrationRequest(**d).validate()

    def test_observed_bypass_requires_transition_and_target_closes(self):
        p,_,_,_=self.plan(); o=self.host_obs(); self.assertFalse(HostAuthoritySeparationBroker.target_observation_is_separated(o)); kinds={x.kind for x in HostAuthoritySeparationBroker.derive_transition(o,p,generated_at=T).operations}; self.assertIn("REMOVE_RUNNER_CONTROL_PLANE_GROUP",kinds); self.assertIn("DENY_RUNNER_DB_ACCESS",kinds)
        target=self.host_obs(runner_groups=(RUNNER_USER,TRUST_CLIENT_GROUP),runner_db_read=False,runner_db_write=False,runner_service_env_read=False); self.assertTrue(HostAuthoritySeparationBroker.target_observation_is_separated(target))

    def test_provider_capabilities_are_non_caller_mintable_through_contracts(self):
        with self.assertRaises(HostAuthoritySeparationError): hostsep.IndependentEvidenceProviderToken(CANONICAL_REPOSITORY_PROVIDER,"fake").validate()
        wrong=hostsep._mint_provider_token("caller-selected-provider","fake")
        with self.assertRaises(HostAuthoritySeparationError): derive_candidate_tree_evidence(wrong,(("x","100644",b"x"),))
        with self.assertRaises(HostAuthoritySeparationError): derive_schema_manifest_evidence(wrong,())

    def test_canonical_plan_derives_provenance_not_digest_arguments(self):
        p,repo,tree,pre=self.plan(); self.assertEqual(p.certified_repository_evidence_digest,repo.digest()); self.assertEqual(p.certified_source_manifest_sha256,tree.production_manifest_sha256); self.assertEqual(p.certified_pre_schema_manifest_digest,pre.digest()); self.assertEqual(p.certified_post_schema_digest,derive_expected_post_schema_evidence(pre).digest())
        params=set(inspect.signature(HostAuthoritySeparationBroker.canonical_plan).parameters)
        for forbidden in ("certified_synthetic_sha","certified_source_manifest_sha256","certified_post_schema_digest","baseline_sha","candidate_sha"): self.assertNotIn(forbidden,params)

    def test_candidate_tree_and_manifest_are_byte_derived(self):
        tree=self.tree_evidence(); self.assertTrue(tree.production_manifest_sha256); self.assertEqual(tree.production_entry_count,2)
        with self.assertRaises(HostAuthoritySeparationError): replace(tree,production_manifest_sha256=H5).validate()
        changed=derive_candidate_tree_evidence(self.tree_provider("changed"),((".github/workflows/x.yml","100644",b"name: y\n"),("README.md","100644",b"fixture\n"),("cyber_lion/enterprise/x.py","100644",b"VALUE=1\n"),("cyber_lion/tests/test_x.py","100644",b"pass\n")))
        p,repo,_,pre=self.plan()
        with self.assertRaises(HostAuthoritySeparationError): HostAuthoritySeparationBroker.canonical_plan(repository_evidence=repo,candidate_tree_evidence=changed,pre_schema_evidence=pre,trusted_runtime_reads=p.trusted_runtime_reads,generated_at=T)

    def test_repository_currentness_is_git_object_derived_and_provider_bound(self):
        repo=self.repo_evidence(); self.assertEqual(repo.synthetic_parents,(repo.base_sha,repo.head_sha)); self.assertEqual(repo.synthetic_tree,repo.head_tree)
        with self.assertRaises(HostAuthoritySeparationError): replace(repo,provider_id="caller").validate()
        with self.assertRaises(HostAuthoritySeparationError): replace(repo,synthetic_sha="f"*40).validate()

    def test_role_separation_and_test_authority_promotion_denied(self):
        p,repo,tree,_=self.plan(); r=self.deploy_req(p,repo,tree)
        with self.assertRaises(HostAuthorityContractError): self.authority(provenance_class="TEST_ONLY")
        for principal in (DEPLOYER_USER,MIGRATOR_USER,RUNTIME_USER,RUNNER_USER):
            with self.subTest(principal=principal),self.assertRaises(HostAuthoritySeparationError): BoundedDeploymentBroker.admit(r,**(self.deploy_args(p,repo,tree)|{"authority":self.authority(host_principal=principal)}))

    def test_candidate_builder_cannot_self_deploy_or_migrate(self):
        p,repo,tree,pre=self.plan(); before=self.before(pre); snap=self.snapshot(before)
        for principal in (DEPLOYER_USER,MIGRATOR_USER,RUNTIME_USER):
            with self.assertRaises(HostAuthorityContractError): self.deploy_req(p,repo,tree,requester_principal=principal)
            with self.assertRaises(HostAuthorityContractError): self.migration_req(p,repo,pre,snap,requester_principal=principal)

    def test_deployment_exact_provenance_and_currentness(self):
        p,repo,tree,_=self.plan(); r=self.deploy_req(p,repo,tree); args=self.deploy_args(p,repo,tree); permit=BoundedDeploymentBroker.admit(r,**args); self.assertEqual(permit.fixed_payload_digest,tree.production_manifest_sha256)
        with self.assertRaises(HostAuthoritySeparationError): BoundedDeploymentBroker.admit(replace(r,source_manifest_sha256=H5),**args)
        with self.assertRaises(HostAuthoritySeparationError): BoundedDeploymentBroker.admit(replace(r,synthetic_sha="f"*40),**args)
        with self.assertRaises(HostAuthoritySeparationError): BoundedDeploymentBroker.admit(r,**(args|{"current_deployed_manifest_sha256":H5}))
        reargs={k:v for k,v in args.items() if k not in {"authority","issued_at"}}; self.assertIs(BoundedDeploymentBroker.revalidate_before_effect(r,permit,**reargs),permit)
        with self.assertRaises(HostAuthoritySeparationError): BoundedDeploymentBroker.revalidate_before_effect(r,replace(permit,currentness_digest=H5),**reargs)

    def test_snapshot_digest_is_derived_from_actual_bytes_and_attester_bound(self):
        _,_,_,pre=self.plan(); before=self.before(pre); snap=self.snapshot(before); self.assertEqual(snap.attestation.snapshot_sha256,sha256(b"actual-consistent-snapshot-bytes").hexdigest()); self.assertEqual(snap.attestation.source_observation_digest,before.digest()); self.assertEqual(snap.attestation.snapshotter_identity,CANONICAL_SNAPSHOTTER_IDENTITY)
        fake_att=replace(snap.attestation,snapshot_sha256=H5,provenance_digest=H5)
        with self.assertRaises(HostAuthoritySeparationError): hostsep.SnapshotProvenanceEvidence(fake_att).validate()
        wrong=hostsep._mint_provider_token("caller-snapshotter","x")
        with self.assertRaises(HostAuthoritySeparationError): derive_snapshot_provenance(wrong,source_observation=before,snapshot_path=SNAPSHOT_DIR+"/x",snapshot_bytes=b"x",integrity_check="ok",created_at=T)

    def test_migration_derives_schema_sql_snapshot_and_post_schema(self):
        p,repo,_,pre=self.plan(); before=self.before(pre); snap=self.snapshot(before); r=self.migration_req(p,repo,pre,snap); permit=BoundedSchemaMigrationBroker.admit(r,plan=p,authority=self.authority(),repository_evidence=repo,before=before,pre_schema_evidence=pre,snapshot_evidence=snap,issued_at=T); self.assertEqual(permit.fixed_payload_digest,CANONICAL_SCHEMA_SQL_SHA256); self.assertEqual(schema_sql_digest(),CANONICAL_SCHEMA_SQL_SHA256)
        for rr in (replace(r,schema_sql_sha256=H5),replace(r,snapshot_sha256=H5),replace(r,expected_post_schema_digest=H5),replace(r,synthetic_sha="f"*40)):
            with self.assertRaises(HostAuthoritySeparationError): BoundedSchemaMigrationBroker.admit(rr,plan=p,authority=self.authority(),repository_evidence=repo,before=before,pre_schema_evidence=pre,snapshot_evidence=snap,issued_at=T)
        with self.assertRaises(HostAuthoritySeparationError): hostsep._validate_add_only_schema_sql("DROP TABLE pr_bootstrap;")

    def test_post_schema_is_derived_from_pre_manifest_not_caller_digest(self):
        p,repo,_,pre=self.plan(); before=self.before(pre); expected=derive_expected_post_schema_evidence(pre); after=SchemaObservation(database_sha256=H5,schema_digest=expected.digest(),pr_bootstrap_rows=0,authority_lineage_rows=2,objects=tuple(x[1] for x in expected.entries),integrity_check="ok",observed_at=T).validate(); self.assertIs(BoundedSchemaMigrationBroker.verify_postcondition(before,after,pre_schema_evidence=pre,after_schema_evidence=expected),after)
        fake=replace(expected,manifest_digest=H5)
        with self.assertRaises(HostAuthoritySeparationError): BoundedSchemaMigrationBroker.verify_postcondition(before,replace(after,schema_digest=H5),pre_schema_evidence=pre,after_schema_evidence=fake)

    def test_receipts_bind_permit_request_snapshot_and_schema(self):
        p,repo,tree,pre=self.plan(); dr=self.deploy_req(p,repo,tree); dp=BoundedDeploymentBroker.admit(dr,**self.deploy_args(p,repo,tree)); good=DeploymentReceipt("deploy-r",dr.digest(),dp.digest(),"DEPLOYED",H2,H5,repo.head_sha,repo.head_tree,T).validate(); self.assertIs(BoundedDeploymentBroker.verify_receipt(dr,dp,good),good)
        with self.assertRaises(HostAuthoritySeparationError): BoundedDeploymentBroker.verify_receipt(dr,dp,replace(good,permit_digest=H5))
        before=self.before(pre); snap=self.snapshot(before); mr=self.migration_req(p,repo,pre,snap); mp=BoundedSchemaMigrationBroker.admit(mr,plan=p,authority=self.authority(),repository_evidence=repo,before=before,pre_schema_evidence=pre,snapshot_evidence=snap,issued_at=T); post=derive_expected_post_schema_evidence(pre); after=SchemaObservation(H5,post.digest(),0,2,tuple(x[1] for x in post.entries),"ok",T).validate(); rec=MigrationReceipt("migrate-r",mr.digest(),mp.digest(),snap.attestation.snapshot_sha256,pre.digest(),post.digest(),0,2,"MIGRATED",T).validate(); self.assertIs(BoundedSchemaMigrationBroker.verify_receipt(mr,mp,before,pre,snap,after,post,rec),rec)

    def test_coherent_self_declared_evidence_cannot_be_resealed(self):
        p,repo,tree,pre=self.plan(); before=self.before(pre); snap=self.snapshot(before)
        fake_tree=replace(tree,production_manifest_sha256=H5,provenance_digest=H5)
        fake_repo=replace(repo,synthetic_sha="f"*40,synthetic_parents=(repo.base_sha,repo.head_sha),provenance_digest=H5)
        fake_pre=replace(pre,manifest_digest=H5,provenance_digest=H5)
        fake_snap=hostsep.SnapshotProvenanceEvidence(replace(snap.attestation,snapshot_sha256=H5,provenance_digest=H5))
        for evidence in (fake_tree,fake_repo,fake_pre,fake_snap):
            with self.subTest(type=type(evidence).__name__),self.assertRaises(HostAuthoritySeparationError): evidence.validate()
        # The public plan factory exposes no digest/synthetic inputs to coherently reseal.
        params=set(inspect.signature(HostAuthoritySeparationBroker.canonical_plan).parameters); self.assertEqual(params,{"repository_evidence","candidate_tree_evidence","pre_schema_evidence","trusted_runtime_reads","generated_at"})

    def test_no_caller_selected_provider_verifier_shell_or_destination(self):
        fields=set(DeploymentRequest.__dataclass_fields__)|set(SchemaMigrationRequest.__dataclass_fields__)
        for forbidden in ("provider","verifier","shell","command","destination","deployer","migrator","private_key","secret","token","ddl","sql"):
            self.assertNotIn(forbidden,fields)
        src=Path("cyber_lion/enterprise/host_authority_separation.py").read_text()
        for forbidden in ("subprocess","os.system","requests","urllib","signing_secret","os.environ","os.getenv","importlib","eval(","exec(","open(","read_text(","read_bytes(","write_bytes("):
            self.assertNotIn(forbidden,src)

    def test_complete_mediation_inventory_adds_no_surface(self):
        paths=("cyber_lion/contracts/host_authority_separation.py","cyber_lion/enterprise/host_authority_separation.py"); inv=EffectSurfaceScanner().scan(repository=CANONICAL_REPOSITORY,revision="1"*40,tree_digest="2"*40,sources={p:Path(p).read_text() for p in paths}); self.assertEqual(inv.unclassified_refs,()); self.assertEqual(inv.surfaces,())

    def test_external_read_binding_and_permit_are_bounded(self):
        with self.assertRaises(HostAuthorityContractError): TrustedRuntimeReadBinding(LIVE_DB_PATH,H).validate()
        p,repo,tree,_=self.plan(); permit=BoundedDeploymentBroker.admit(self.deploy_req(p,repo,tree),**self.deploy_args(p,repo,tree)); self.assertEqual(permit.fixed_executor_principal,"root"); self.assertFalse(hasattr(permit,"execute")); self.assertFalse(hasattr(permit,"authority_grant")); self.assertFalse(hasattr(permit,"credential"))

if __name__=="__main__": unittest.main()