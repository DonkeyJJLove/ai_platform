from __future__ import annotations

import ast
from dataclasses import replace
from hashlib import sha1, sha256
import inspect
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from cyber_lion.contracts.host_authority_separation import *
from cyber_lion.contracts.independent_evidence_origin import (
    IndependentEvidenceOriginReceipt,
    origin_receipt_digest,
)
from cyber_lion.enterprise.host_authority_separation import *
import cyber_lion.enterprise.host_authority_separation as hostsep
import cyber_lion.enterprise.independent_evidence_origin as originver
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

T="2026-08-27T21:00:00Z"; H="a"*64; H2="b"*64; H3="c"*64; H5="e"*64
BASE_REF="mission/e006-r9d-9g3a1-authority-provisioning-plane"
HEAD_REF="mission/e006-r9d-9g3a1-host-authority-separation-deployment-plane"

SELFTEST_RECEIPT=IndependentEvidenceOriginReceipt(
    "git-object-candidate-tree/v1",
    "verifier-selftest:non-production-observation",
    originver.CANONICAL_ORIGIN_TRUST_ANCHOR_ID,
    originver.CANONICAL_ORIGIN_ALGORITHM,
    "verifier-selftest-unmappable",
    originver.ORIGIN_CANDIDATE_TREE,
    "0"*40,
    "7b62994ca61331f9e99471efdf64e55bf96c423021dd21b4e9fb83e60a7b9d6b",
    "8dec013371a9acbd01b42b1eba30cc6e7b0a3c987956af92a4888fb6501a186c",
    T,
    "aaade059f4b1dfa2f756f68a56c99e5255ae93cacf2e7e3d56d8555124dd7fcf",
    "5fe1e2ea6656c9f28139afd69f4965eea2c31f287366e0282590e77aa42aaf03",
    "65304ca63b892fdfa68c616f8eb94afc6f31066808c63bdbc8d2f61e6a9770e99d88315782896006f6d1607d61eec7caae3fbd5091f28e78236bc7db2a0bb6954206cf4d1013ab40b875e6d6224091de71f6a250ad072a0d87237b47113afeca59b7d63f066c5e7b6e282ce39def4e94d3d6d5652234e80ad9c65797346ed20d0668b8d0696f503bcc5350ffc0a9fb4faaf1ed64391fd6e6ba0c9acfdf1a37a0e929a107f1fcb1923b8045cb4f3a12c944259c7045cbb60359c129f53c455decc67de63763d7be67d031904b5e38327e6487ecbd30587fc524f41c387d032eb2a46966a6d9692a194e5e04831a96ced865e73f4fd23def6f69e73016a55d11df",
).validate()


def commit_obj(tree:str,parents:tuple[str,...]=(),message:str="fixture")->bytes:
    lines=[f"tree {tree}",*(f"parent {p}" for p in parents),"author Fixture <fixture@example> 1 +0000","committer Fixture <fixture@example> 1 +0000","",message,""]
    return "\n".join(lines).encode()

def oid(raw:bytes)->str:
    return sha1(f"commit {len(raw)}\0".encode()+raw).hexdigest()

def fixture_receipt(provider_id:str,provider_instance_id:str,observation_id:str,kind:str,identity:str,object_digest:str,payload_digest:str)->IndependentEvidenceOriginReceipt:
    nonce=sha256(f"{kind}:{observation_id}".encode()).hexdigest()
    digest=origin_receipt_digest(
        provider_id=provider_id,provider_instance_id=provider_instance_id,
        trust_anchor_id=originver.CANONICAL_ORIGIN_TRUST_ANCHOR_ID,
        algorithm=originver.CANONICAL_ORIGIN_ALGORITHM,
        observation_id=observation_id,observation_kind=kind,
        observed_object_identity=identity,observed_object_digest=object_digest,
        payload_digest=payload_digest,issued_at=T,nonce=nonce,
    )
    return IndependentEvidenceOriginReceipt(
        provider_id,provider_instance_id,originver.CANONICAL_ORIGIN_TRUST_ANCHOR_ID,
        originver.CANONICAL_ORIGIN_ALGORITHM,observation_id,kind,identity,
        object_digest,payload_digest,T,nonce,digest,"0"*512,
    ).validate()

def reseal(receipt:IndependentEvidenceOriginReceipt,**changes)->IndependentEvidenceOriginReceipt:
    wire=receipt.unsigned_wire(); wire.update(changes)
    digest=origin_receipt_digest(**wire)
    return IndependentEvidenceOriginReceipt(**wire,receipt_digest=digest,signature_hex=receipt.signature_hex).validate()

def fixture_verify(receipt:IndependentEvidenceOriginReceipt,*,kind:str,identity:str,object_digest:str,payload_digest:str):
    receipt.validate()
    providers={
        originver.ORIGIN_REPOSITORY_CURRENTNESS:CANONICAL_REPOSITORY_PROVIDER,
        originver.ORIGIN_CANDIDATE_TREE:hostsep.CANDIDATE_TREE_PROVIDER,
        originver.ORIGIN_PRE_SCHEMA:hostsep.SCHEMA_MANIFEST_PROVIDER,
        originver.ORIGIN_SNAPSHOT:CANONICAL_SNAPSHOTTER_IDENTITY,
    }
    if providers.get(kind)!=receipt.provider_id: raise HostAuthoritySeparationError("provider substitution")
    if receipt.observation_kind!=kind: raise HostAuthoritySeparationError("cross-origin confusion")
    if receipt.trust_anchor_id!=originver.CANONICAL_ORIGIN_TRUST_ANCHOR_ID: raise HostAuthoritySeparationError("trust anchor substitution")
    if receipt.algorithm!=originver.CANONICAL_ORIGIN_ALGORITHM: raise HostAuthoritySeparationError("verifier substitution")
    if (receipt.observed_object_identity,receipt.observed_object_digest,receipt.payload_digest)!=(identity,object_digest,payload_digest):
        raise HostAuthoritySeparationError("origin binding mismatch")
    return receipt

def tree_material(files):
    rows=[]; git=[]; prod=[]
    for path,mode,data in files:
        blob=hostsep._git_blob_sha(data); bsha=sha256(data).hexdigest()
        rows.append((path,mode,blob,bsha,len(data))); git.append((path,mode,blob))
        if hostsep._production_path(path):
            prod.append({"path":path,"blob_sha":blob,"byte_sha256":bsha,"size":len(data),"mode":mode})
    rows=tuple(sorted(rows,key=lambda x:x[0]))
    tree=hostsep._git_tree_sha(tuple(git))
    manifest=sha256(b"LION/R9D8/EXACT-PRODUCTION-MANIFEST/1\0"+hostsep._canon(sorted(prod,key=lambda x:x["path"]))).hexdigest()
    payload=hostsep._candidate_tree_payload_digest(rows)
    obj=hostsep._candidate_tree_object_digest(tree,len(rows),manifest,len(prod))
    return rows,tree,manifest,payload,obj,len(prod)

def repository_material(tree_sha:str):
    base_raw=commit_obj("1"*40,(),"base"); base=oid(base_raw)
    head_raw=commit_obj(tree_sha,(base,),"head"); head=oid(head_raw)
    syn_raw=commit_obj(tree_sha,(base,head),"merge"); syn=oid(syn_raw)
    pr={"number":234,"base":{"ref":BASE_REF,"sha":base,"repo":{"full_name":CANONICAL_REPOSITORY}},
        "head":{"ref":HEAD_REF,"sha":head,"repo":{"full_name":CANONICAL_REPOSITORY}},"merge_commit_sha":syn}
    pp=json.dumps(pr,sort_keys=True,separators=(",",":")).encode()
    payload=hostsep._bundle_digest(b"LION/REPOSITORY-CURRENTNESS-PRIMARY-PAYLOAD/1\0",pp,base_raw,head_raw,syn_raw)
    obj=hostsep._repository_object_digest(
        repository=CANONICAL_REPOSITORY,pr_number=234,base_ref=BASE_REF,base_sha=base,
        base_tree="1"*40,head_ref=HEAD_REF,head_sha=head,head_tree=tree_sha,
        synthetic_sha=syn,synthetic_tree=tree_sha,synthetic_parents=(base,head))
    return pp,base_raw,head_raw,syn_raw,payload,obj


class HostAuthoritySeparationTests(unittest.TestCase):
    def setUp(self):
        self._p=patch.object(hostsep,"_verify_origin",side_effect=fixture_verify); self._p.start(); self._patched=True
    def tearDown(self):
        if self._patched: self._p.stop()
    def production_verifier(self):
        if self._patched: self._p.stop(); self._patched=False

    def files(self,changed=False):
        return (
            (".github/workflows/x.yml","100644",b"name: y\n" if changed else b"name: x\n"),
            ("README.md","100644",b"fixture\n"),
            ("cyber_lion/enterprise/x.py","100644",b"VALUE=1\n"),
            ("cyber_lion/tests/test_x.py","100644",b"pass\n"),
        )

    def tree(self,changed=False):
        files=self.files(changed); _,tree,_,payload,obj,_=tree_material(files)
        rec=fixture_receipt(hostsep.CANDIDATE_TREE_PROVIDER,"fixture-tree:1","tree-changed" if changed else "tree",originver.ORIGIN_CANDIDATE_TREE,tree,obj,payload)
        return derive_candidate_tree_evidence(rec,files)

    def repo(self,tree):
        pp,b,h,s,payload,obj=repository_material(tree.tree_sha)
        rec=fixture_receipt(CANONICAL_REPOSITORY_PROVIDER,"fixture-repo:1","repo",originver.ORIGIN_REPOSITORY_CURRENTNESS,f"{CANONICAL_REPOSITORY}#PR234",obj,payload)
        return derive_repository_currentness_evidence(rec,pr_payload=pp,base_commit_object=b,head_commit_object=h,synthetic_commit_object=s)

    def pre(self,dbsha=H):
        rows=(("table","pr_bootstrap","pr_bootstrap","CREATE TABLE pr_bootstrap(x TEXT)"),
              ("table","authority_lineage","authority_lineage","CREATE TABLE authority_lineage(x TEXT)"))
        entries=tuple(sorted(((a,b,c,hostsep._normalize_sql(d)) for a,b,c,d in rows),key=lambda x:(x[0],x[1])))
        md=hostsep._schema_manifest_digest(entries); payload=hostsep._pre_schema_payload_digest(dbsha,entries)
        obj=hostsep._pre_schema_object_digest(dbsha,md)
        rec=fixture_receipt(hostsep.SCHEMA_MANIFEST_PROVIDER,"fixture-schema:1","schema",originver.ORIGIN_PRE_SCHEMA,LIVE_DB_PATH,obj,payload)
        return derive_schema_manifest_evidence(rec,rows,source_database_sha256=dbsha)

    def plan(self):
        tree=self.tree(); repo=self.repo(tree); pre=self.pre()
        plan=HostAuthoritySeparationBroker.canonical_plan(
            repository_evidence=repo,candidate_tree_evidence=tree,pre_schema_evidence=pre,
            trusted_runtime_reads=(TrustedRuntimeReadBinding("/opt/lion/trusted-runtime/workflow-dispatch-test/runtime_provider.py",H),),
            generated_at=T)
        return plan,repo,tree,pre

    def authority(self,**kw):
        d=dict(issuer_subject_id="prod-issuer-1",trust_domain="prod.example",key_id="kms://issuer/1",
               algorithm="opaque-external",provenance_class="PRODUCTION_EXTERNAL",host_principal=None,private_key_on_host=False)
        d.update(kw); return ExternalAuthorityIdentity(**d).validate()

    def before(self,pre):
        return SchemaObservation(H,pre.digest(),0,2,PRESERVED_TABLES,"ok",T).validate()

    def snapshot(self,before):
        data=b"actual-consistent-snapshot-bytes"; s=sha256(data).hexdigest(); path=SNAPSHOT_DIR+"/control-plane.pre.sqlite"
        obj=hostsep._snapshot_object_digest(snapshot_path=path,source_database_sha256=before.database_sha256,
            snapshot_sha256=s,snapshot_size=len(data),source_observation_digest=before.digest(),integrity_check="ok",created_at=T)
        rec=fixture_receipt(CANONICAL_SNAPSHOTTER_IDENTITY,"fixture-snapshot:1","snapshot",originver.ORIGIN_SNAPSHOT,path,obj,s)
        return derive_snapshot_provenance(rec,source_observation=before,snapshot_path=path,snapshot_bytes=data,integrity_check="ok")

    def dreq(self,p,r,t,**kw):
        d=dict(request_id="deploy",repository=r.repository,pr_number=r.pr_number,baseline_ref=r.base_ref,
            baseline_sha=r.base_sha,baseline_tree=r.base_tree,candidate_ref=r.head_ref,candidate_sha=r.head_sha,
            candidate_tree=r.head_tree,synthetic_sha=r.synthetic_sha,repository_evidence_digest=r.digest(),
            source_manifest_sha256=t.production_manifest_sha256,current_deployed_manifest_sha256=H2,
            service_unit_sha256=H3,separation_plan_digest=p.digest(),requester_principal="candidate-builder",requested_at=T)
        d.update(kw); return DeploymentRequest(**d).validate()

    def mreq(self,p,r,pre,snap,**kw):
        d=dict(request_id="migrate",repository=r.repository,pr_number=r.pr_number,candidate_ref=r.head_ref,
            candidate_sha=r.head_sha,candidate_tree=r.head_tree,synthetic_sha=r.synthetic_sha,
            repository_evidence_digest=r.digest(),live_database_sha256=H,pre_schema_digest=pre.digest(),
            schema_sql_sha256=CANONICAL_SCHEMA_SQL_SHA256,snapshot_sha256=snap.attestation.snapshot_sha256,
            expected_post_schema_digest=derive_expected_post_schema_evidence(pre).digest(),
            separation_plan_digest=p.digest(),requester_principal="candidate-builder",requested_at=T)
        d.update(kw); return SchemaMigrationRequest(**d).validate()

    def test_pinned_production_verifier_selftest(self):
        self.assertIs(originver.verify_independent_evidence_origin(
            SELFTEST_RECEIPT,observation_kind=originver.ORIGIN_CANDIDATE_TREE,
            observed_object_identity=SELFTEST_RECEIPT.observed_object_identity,
            observed_object_digest=SELFTEST_RECEIPT.observed_object_digest,
            payload_digest=SELFTEST_RECEIPT.payload_digest),SELFTEST_RECEIPT)

    def test_plan_deploy_migration_and_postcondition_bind_origins(self):
        p,r,t,pre=self.plan(); dr=self.dreq(p,r,t)
        dp=BoundedDeploymentBroker.admit(dr,plan=p,authority=self.authority(),repository_evidence=r,
            candidate_tree_evidence=t,current_deployed_manifest_sha256=H2,current_service_unit_sha256=H3,issued_at=T)
        self.assertEqual(dp.fixed_payload_digest,t.production_manifest_sha256)
        before=self.before(pre); snap=self.snapshot(before); mr=self.mreq(p,r,pre,snap)
        mp=BoundedSchemaMigrationBroker.admit(mr,plan=p,authority=self.authority(),repository_evidence=r,before=before,
            pre_schema_evidence=pre,snapshot_evidence=snap,issued_at=T)
        self.assertEqual(mp.fixed_payload_digest,CANONICAL_SCHEMA_SQL_SHA256)
        post=derive_expected_post_schema_evidence(pre)
        after=SchemaObservation(H5,post.digest(),0,2,tuple(x[1] for x in post.entries),"ok",T).validate()
        self.assertIs(BoundedSchemaMigrationBroker.verify_postcondition(before,after,pre_schema_evidence=pre,after_schema_evidence=post),after)

    def test_host_separation_and_roles_regression(self):
        p,r,t,_=self.plan()
        obs=HostAuthorityObservation("MOON",RUNTIME_USER,RUNNER_USER,(RUNNER_USER,CONTROL_PLANE_GROUP),True,True,True,False,False,False,H,H2,H3,T).validate()
        kinds={x.kind for x in HostAuthoritySeparationBroker.derive_transition(obs,p,generated_at=T).operations}
        self.assertIn("REMOVE_RUNNER_CONTROL_PLANE_GROUP",kinds); self.assertIn("DENY_RUNNER_DB_ACCESS",kinds)
        with self.assertRaises(HostAuthorityContractError): self.authority(provenance_class="TEST_ONLY")
        for principal in (DEPLOYER_USER,MIGRATOR_USER,RUNTIME_USER):
            with self.assertRaises(HostAuthorityContractError): self.dreq(p,r,t,requester_principal=principal)

    def test_no_in_process_origin_mint_signer_or_selector(self):
        hs=Path("cyber_lion/enterprise/host_authority_separation.py").read_text()
        vs=Path("cyber_lion/enterprise/independent_evidence_origin.py").read_text()
        for x in ("_EVIDENCE_CAP","_mint_provider_token","IndependentEvidenceProviderToken"): self.assertNotIn(x,hs)
        for x in ("private_key","signing_secret","os.environ","os.getenv","subprocess","requests","urllib"): self.assertNotIn(x,vs)
        for fn in (HostAuthoritySeparationBroker.canonical_plan,BoundedDeploymentBroker.admit,BoundedSchemaMigrationBroker.admit):
            names=set(inspect.signature(fn).parameters)
            self.assertFalse(names & {"provider","provider_id","provider_instance","verifier","trust_anchor","private_key","secret"})

    def test_git_oid_sha1_is_explicitly_non_security(self):
        source=Path("cyber_lion/enterprise/host_authority_separation.py").read_text()
        parsed=ast.parse(source)
        calls=[node for node in ast.walk(parsed)
               if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=="sha1"]
        self.assertEqual(len(calls),3)
        for call in calls:
            keywords={kw.arg:kw.value for kw in call.keywords}
            self.assertIn("usedforsecurity",keywords)
            value=keywords["usedforsecurity"]
            self.assertIsInstance(value,ast.Constant)
            self.assertIs(value.value,False)

    def test_git_oid_sha1_regression_vectors(self):
        self.assertEqual(hostsep._git_blob_sha(b""),"e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        self.assertEqual(hostsep._git_blob_sha(b"hello\n"),"ce013625030ba8dba906f756967f9e9ca394464a")
        self.assertEqual(hostsep._git_blob_sha(b"test\n"),"9daeafb9864cf43055ae93beb0afd6c7d144bfa4")

    def test_coherent_fake_world_a_denied_by_real_origin(self):
        self.production_verifier()
        files=(("cyber_lion/enterprise/evil.py","100644",b"OWNED=True\n"),(".github/workflows/evil.yml","100644",b"name: evil\n"))
        _,tree,_,payload,obj,_=tree_material(files)
        rec=fixture_receipt(hostsep.CANDIDATE_TREE_PROVIDER,"attacker:tree","evil-tree",originver.ORIGIN_CANDIDATE_TREE,tree,obj,payload)
        with self.assertRaises(HostAuthoritySeparationError): derive_candidate_tree_evidence(rec,files)
        pp,b,h,s,rpayload,robj=repository_material(tree)
        rr=fixture_receipt(CANONICAL_REPOSITORY_PROVIDER,"attacker:repo","evil-repo",originver.ORIGIN_REPOSITORY_CURRENTNESS,f"{CANONICAL_REPOSITORY}#PR234",robj,rpayload)
        with self.assertRaises(HostAuthoritySeparationError):
            derive_repository_currentness_evidence(rr,pr_payload=pp,base_commit_object=b,head_commit_object=h,synthetic_commit_object=s)

    def test_coherent_fake_world_b_denied_by_real_origin(self):
        pre=self.pre(); before=self.before(pre); self.production_verifier()
        rows=(("table","pr_bootstrap","pr_bootstrap","CREATE TABLE pr_bootstrap(evil TEXT)"),)
        entries=((rows[0][0],rows[0][1],rows[0][2],hostsep._normalize_sql(rows[0][3])),)
        md=hostsep._schema_manifest_digest(entries); payload=hostsep._pre_schema_payload_digest(H5,entries); obj=hostsep._pre_schema_object_digest(H5,md)
        sr=fixture_receipt(hostsep.SCHEMA_MANIFEST_PROVIDER,"attacker:schema","evil-schema",originver.ORIGIN_PRE_SCHEMA,LIVE_DB_PATH,obj,payload)
        with self.assertRaises(HostAuthoritySeparationError): derive_schema_manifest_evidence(sr,rows,source_database_sha256=H5)
        data=b"coherent-fake-snapshot"; s=sha256(data).hexdigest(); path=SNAPSHOT_DIR+"/evil.sqlite"
        sobj=hostsep._snapshot_object_digest(snapshot_path=path,source_database_sha256=before.database_sha256,
            snapshot_sha256=s,snapshot_size=len(data),source_observation_digest=before.digest(),integrity_check="ok",created_at=T)
        rr=fixture_receipt(CANONICAL_SNAPSHOTTER_IDENTITY,"attacker:snapshot","evil-snapshot",originver.ORIGIN_SNAPSHOT,path,sobj,s)
        with self.assertRaises(HostAuthoritySeparationError):
            derive_snapshot_provenance(rr,source_observation=before,snapshot_path=path,snapshot_bytes=data,integrity_check="ok")

    def test_coherent_fake_world_c_resealed_all_internal_digests_denied(self):
        p,r,t,pre=self.plan(); dr=self.dreq(p,r,t); before=self.before(pre); snap=self.snapshot(before); mr=self.mreq(p,r,pre,snap)
        tr=reseal(t.origin_receipt,provider_instance_id="attacker-tree:resealed",observation_id="evil-tree-reseal",nonce=sha256(b"t").hexdigest())
        tp=hostsep._digest(b"LION/CANDIDATE-TREE-EVIDENCE/2\0",{"tree_sha":t.tree_sha,"tracked_file_count":t.tracked_file_count,
            "production_manifest_sha256":t.production_manifest_sha256,"production_entry_count":t.production_entry_count,
            "provider_observation_id":tr.observation_id,"provider_instance_id":tr.provider_instance_id,"full_entries":t.full_entries,"origin_receipt_digest":tr.digest()})
        ft=CandidateTreeEvidence(t.tree_sha,t.tracked_file_count,t.production_manifest_sha256,t.production_entry_count,tr.observation_id,tr.provider_instance_id,t.full_entries,tr,tp)
        rr=reseal(r.origin_receipt,provider_instance_id="attacker-repo:resealed",observation_id="evil-repo-reseal",nonce=sha256(b"r").hexdigest())
        rp=hostsep._digest(b"LION/REPOSITORY-CURRENTNESS-EVIDENCE/2\0",{"provider_id":r.provider_id,"provider_instance_id":rr.provider_instance_id,
            "repository":r.repository,"pr_number":r.pr_number,"base_ref":r.base_ref,"base_sha":r.base_sha,"base_tree":r.base_tree,
            "head_ref":r.head_ref,"head_sha":r.head_sha,"head_tree":r.head_tree,"synthetic_sha":r.synthetic_sha,"synthetic_tree":r.synthetic_tree,
            "synthetic_parents":r.synthetic_parents,"provider_payload_sha256":r.provider_payload_sha256,
            "provider_observation_id":rr.observation_id,"observed_at":r.observed_at,"origin_receipt_digest":rr.digest()})
        fr=RepositoryCurrentnessEvidence(r.provider_id,rr.provider_instance_id,r.repository,r.pr_number,r.base_ref,r.base_sha,r.base_tree,
            r.head_ref,r.head_sha,r.head_tree,r.synthetic_sha,r.synthetic_tree,r.synthetic_parents,r.provider_payload_sha256,
            rr.observation_id,r.observed_at,rr,rp)
        pr=reseal(pre.origin_receipt,provider_instance_id="attacker-schema:resealed",observation_id="evil-schema-reseal",nonce=sha256(b"p").hexdigest())
        pp=hostsep._digest(b"LION/PRE-SCHEMA-EVIDENCE/2\0",{"entries":pre.entries,"manifest_digest":pre.manifest_digest,
            "source_database_sha256":pre.source_database_sha256,"provider_observation_id":pr.observation_id,
            "provider_instance_id":pr.provider_instance_id,"origin_receipt_digest":pr.digest()})
        fp=SchemaManifestEvidence(pre.entries,pre.manifest_digest,pre.source_database_sha256,pr.observation_id,pr.provider_instance_id,pp,pr,None)
        self.production_verifier()
        with self.assertRaises(HostAuthoritySeparationError):
            HostAuthoritySeparationBroker.canonical_plan(repository_evidence=fr,candidate_tree_evidence=ft,pre_schema_evidence=fp,
                trusted_runtime_reads=p.trusted_runtime_reads,generated_at=T)
        with self.assertRaises(HostAuthoritySeparationError):
            BoundedDeploymentBroker.admit(dr,plan=p,authority=self.authority(),repository_evidence=fr,candidate_tree_evidence=ft,
                current_deployed_manifest_sha256=H2,current_service_unit_sha256=H3,issued_at=T)
        with self.assertRaises(HostAuthoritySeparationError):
            BoundedSchemaMigrationBroker.admit(mr,plan=p,authority=self.authority(),repository_evidence=fr,before=before,
                pre_schema_evidence=fp,snapshot_evidence=snap,issued_at=T)

    def test_provider_anchor_verifier_instance_observation_nonce_substitution_denied(self):
        for mutation in (
            {"provider_id":"caller-provider"},{"provider_instance_id":"caller-instance"},{"observation_id":"caller-observation"},
            {"trust_anchor_id":"caller-anchor"},{"algorithm":"caller-verifier"},{"nonce":sha256(b"caller-nonce").hexdigest()},
        ):
            forged=reseal(SELFTEST_RECEIPT,**mutation)
            with self.subTest(mutation=mutation),self.assertRaises(originver.IndependentEvidenceOriginError):
                originver.verify_independent_evidence_origin(forged,observation_kind=originver.ORIGIN_CANDIDATE_TREE,
                    observed_object_identity=SELFTEST_RECEIPT.observed_object_identity,
                    observed_object_digest=SELFTEST_RECEIPT.observed_object_digest,payload_digest=SELFTEST_RECEIPT.payload_digest)

    def test_cross_origin_and_stale_currentness_denied(self):
        files=self.files(); _,tree,_,payload,obj,_=tree_material(files)
        tr=fixture_receipt(hostsep.CANDIDATE_TREE_PROVIDER,"fixture-tree:1","tree",originver.ORIGIN_CANDIDATE_TREE,tree,obj,payload)
        rows=(("table","x","x","CREATE TABLE x(y TEXT)"),)
        with self.assertRaises(HostAuthoritySeparationError): derive_schema_manifest_evidence(tr,rows,source_database_sha256=H)
        old=self.tree(); repo=self.repo(old); new=self.tree(changed=True); pre=self.pre()
        with self.assertRaises(HostAuthoritySeparationError):
            HostAuthoritySeparationBroker.canonical_plan(repository_evidence=repo,candidate_tree_evidence=new,pre_schema_evidence=pre,
                trusted_runtime_reads=(TrustedRuntimeReadBinding("/opt/lion/trusted-runtime/workflow-dispatch-test/runtime_provider.py",H),),generated_at=T)

    def test_effect_surface_and_exact_terminal_inventory(self):
        changed=("cyber_lion/contracts/independent_evidence_origin.py","cyber_lion/enterprise/host_authority_separation.py","cyber_lion/enterprise/independent_evidence_origin.py")
        local=EffectSurfaceScanner().scan(repository=CANONICAL_REPOSITORY,revision="1"*40,tree_digest="2"*40,
            sources={p:Path(p).read_text() for p in changed})
        self.assertEqual(local.surfaces,()); self.assertEqual(local.unclassified_refs,())
        raw=subprocess.run(["git","ls-files","-z"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
        sources={}
        for p in raw.split(b"\0"):
            if p:
                path=p.decode()
                if hostsep._production_path(path): sources[path]=Path(path).read_text()
        revision=subprocess.run(["git","rev-parse","HEAD"],check=True,capture_output=True,text=True).stdout.strip()
        tree_digest=subprocess.run(["git","write-tree"],check=True,capture_output=True,text=True).stdout.strip()
        inv=EffectSurfaceScanner().scan(repository=CANONICAL_REPOSITORY,revision=revision,tree_digest=tree_digest,sources=sources)
        self.assertEqual((len(sources),len(inv.surfaces),len(inv.unclassified_refs)),(244,225,5))

    def test_p1_fake_world_harness_not_skipped(self):
        for name in ("test_coherent_fake_world_a_denied_by_real_origin","test_coherent_fake_world_b_denied_by_real_origin",
                     "test_coherent_fake_world_c_resealed_all_internal_digests_denied",
                     "test_git_oid_sha1_is_explicitly_non_security",
                     "test_git_oid_sha1_regression_vectors",
                     "test_effect_surface_and_exact_terminal_inventory"):
            self.assertFalse(getattr(getattr(type(self),name),"__unittest_skip__",False),name)


if __name__=="__main__":
    unittest.main()
