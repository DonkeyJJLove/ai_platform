from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha1, sha256
import inspect
import json
from pathlib import Path
import unittest

from cyber_lion.contracts.host_authority_separation import *
from cyber_lion.contracts.independent_evidence_origin import (
    IndependentEvidenceOriginReceipt,
    origin_receipt_digest,
)
from cyber_lion.enterprise.host_authority_separation import *
import cyber_lion.enterprise.host_authority_separation as hostsep
import cyber_lion.enterprise.independent_evidence_origin as originver
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

T = "2026-08-27T21:00:00Z"
H = "a" * 64
H2 = "b" * 64
H3 = "c" * 64
H5 = "e" * 64
BASE_REF = "mission/e006-r9d-9g3a1-authority-provisioning-plane"
HEAD_REF = "mission/e006-r9d-9g3a1-host-authority-separation-deployment-plane"

SIGNED_FIXTURES = {'5d6fb41e04bd8de4f5c15dcf260b8739a0fb71a9b9ca999f5d924d0e782e44b3': '1012d67aa62a6b212b21f80e29bacb0f069b7108dd6ec5db3a70e907c0f9733f068c8f68e0e8853309c963059c411bab02617c9a6d574f8d53abf9ab77891c96ecfd24e80dcf786f4029e065c94f105c5e29ff46f02f800bd05cee953c3ca6290763351ddf2876e1c6c15db511ff26949c7e741e7cf89d485eddf12c98fb0cc2a2f257e053e5a053c081ff052f0299025031ab0da9ac5a33773c7a987ac2e7d6499fce503f338c3ba46f6c7e480414111da70185e948802a709dc8def6d2079ca72eeb507d2290cb964334f5657446321acb0ad42cff57b6790f205ff170b8bee334a1982705be6106f28a843686be3dbeccca885db5c1119b0fd3b76f3bbce6', '76a836f9d10cc2ea1f9595cce2b2e0251efb1a1a8cff57e5deeb31582fbda5cc': '105ef9608e7bd99c5e6d981fa19fa261db4876bccc5f73bb4fecf03824882adfcdd5b551cda81e4089c361325950ab6a1f81eefab4a6e025bbf7427dfa9c63034bed05871b07ae9abfde18597c8638ef5326e6128421368c22b8a161d321b10bf944bea576a85c42a7bd4bf1c59f38f7a36ffc79b615840f2ca605931c00509b2482ea8e6d5561df7d909c022d84fdc8d49276a2453e0cdd95cef48aaff05dfa3d66ab99141fbd6a148625ecd8c37b7ad0002387c0963cd8d5bd06c25ac7cc693759a664471aac2a4000847c1909106a9baa6cd7d0e3dd708d36a071b4da0006b2af59b70a6c32ba5b91cad9de911ae63c7988e412e7d90590b998ae81fdd012', 'e20af613eda5719ad99ce249a6da2c59c71754d3b4115980f417879ed1a2030f': '155345e1bbc419b0b7390e422168622a96514f2ec0eacba4155c9085cc0ed5c3050105fdffadca303a352486a15b0c4528df5aa74b52d51622160b33bd4a43049ac3b7a51b5b06925050ac6947b90abcf6d62fbad5ad8e0ebedb3dff0dec784207d57d1e0ada90486575f6f49fd6021271fc2b3c9542694a05a9a138b535bb996d58f6275234e598d8f7c618a8c2c8b0c51bd59d6b2f7862e86a7eeb9e160b358e348894e161854cb16bb047fb1f7d55d989d540c940bb5901c1bafdd20772721a099dbc822708105c53a7dbfe02dd52dbab0b2b41bb8b0fce14a220c92d549c6d0ffdb0c4bec5a949f7d0bd9151f0c4b2c92c22a1bbc314bfb4429ea6a025c3', 'f5ad332494ec0b8f3056d8ccdde7fd9a9131440602363daa5b85ee7363182482': '525ab4583c15019a07a02f0bfe8d8a7450781b3d288eea263d43cda39ea346889d5ace1236cbbac6fab457e53628f935734c8d17df81754099ffa2b023257ffa40ffaf07c4a65eafd91d628e4ce54730ef8fb3f218a8b1c2393ee40d57eea71f971a8f7af72db0869c69e3e07f4e6080c465eddad47a468d269e6d077464988316cec8ef5df27418a760667d4452410314ecff7e828cc2ecca07ce4615b65d3ad83cb69f403a8af08bd44374a4ec889373f4dc1b9534ae8ec72989cf00966b3701d36cdd7e68b55f597699ecf237b8fb3c9cc87f75fbbf77d17cfeebe8293d098e783b9e6f6dba5b4ebf4fac1e627f4f31161afdbb0d8df608f147dfbe24b231', 'e3f5a1247d67b9966b31a15c907beb1b05d081e4011f4ca15ca0232d4c51182e': '6cf6003277e441c725578a45d0544d1dc623995b77e1d6a8e8c73cdb283eb7ad341c9fe727160da83166e5e3a985d15774bcb049c0d0795bc341c97c1987dbc17c9a2eb81b0742291b349cc003b6453748a683d34cc72728b0fc1c88226a26089e9b67ff3da589909b85912b8acccd2f8d7caab5ff3dc5cc7934dfe6557a98fb72f1d1662bcd8fc4708bde7e3d52a23c4e5d89c3ad11ca7b549fed220270f60bed1dbaa37ad3f681cfb55f03100a55296cc6c19a3d3396c835694da429ecee16834e6a36e344ad78da9a738a299dfbec089cac3db8dac10d62356baa4c5907513f7c011a2d9c4d9c93e2e5afc1125191beb06c78c3464944d1d6069b27d525b9'}


def commit_obj(tree: str, parents: tuple[str, ...] = (), message: str = "fixture") -> bytes:
    lines = [
        f"tree {tree}",
        *(f"parent {parent}" for parent in parents),
        "author Fixture <fixture@example> 1 +0000",
        "committer Fixture <fixture@example> 1 +0000",
        "",
        message,
        "",
    ]
    return "\n".join(lines).encode()


def oid(raw: bytes) -> str:
    return sha1(f"commit {len(raw)}\0".encode() + raw).hexdigest()


def _receipt(
    provider_id: str,
    provider_instance_id: str,
    observation_id: str,
    observation_kind: str,
    observed_object_identity: str,
    observed_object_digest: str,
    payload_digest: str,
    *,
    signed: bool = True,
    issued_at: str = T,
) -> IndependentEvidenceOriginReceipt:
    nonce = sha256(f"{observation_kind}:{observation_id}".encode()).hexdigest()
    digest = origin_receipt_digest(
        provider_id=provider_id,
        provider_instance_id=provider_instance_id,
        trust_anchor_id=originver.CANONICAL_ORIGIN_TRUST_ANCHOR_ID,
        algorithm=originver.CANONICAL_ORIGIN_ALGORITHM,
        observation_id=observation_id,
        observation_kind=observation_kind,
        observed_object_identity=observed_object_identity,
        observed_object_digest=observed_object_digest,
        payload_digest=payload_digest,
        issued_at=issued_at,
        nonce=nonce,
    )
    signature = SIGNED_FIXTURES.get(digest, "0" * 512) if signed else "0" * 512
    return IndependentEvidenceOriginReceipt(
        provider_id,
        provider_instance_id,
        originver.CANONICAL_ORIGIN_TRUST_ANCHOR_ID,
        originver.CANONICAL_ORIGIN_ALGORITHM,
        observation_id,
        observation_kind,
        observed_object_identity,
        observed_object_digest,
        payload_digest,
        issued_at,
        nonce,
        digest,
        signature,
    ).validate()


def _reseal(receipt: IndependentEvidenceOriginReceipt, **changes: object) -> IndependentEvidenceOriginReceipt:
    wire = receipt.unsigned_wire()
    wire.update(changes)
    digest = origin_receipt_digest(**wire)
    return IndependentEvidenceOriginReceipt(
        **wire,
        receipt_digest=digest,
        signature_hex=receipt.signature_hex,
    ).validate()


def _tree_material(files: tuple[tuple[str, str, bytes], ...]):
    rows = []
    git_entries = []
    production = []
    for path, mode, data in files:
        blob = hostsep._git_blob_sha(data)
        byte_sha = sha256(data).hexdigest()
        rows.append((path, mode, blob, byte_sha, len(data)))
        git_entries.append((path, mode, blob))
        if hostsep._production_path(path):
            production.append(
                {
                    "path": path,
                    "blob_sha": blob,
                    "byte_sha256": byte_sha,
                    "size": len(data),
                    "mode": mode,
                }
            )
    rows = tuple(sorted(rows, key=lambda row: row[0]))
    tree = hostsep._git_tree_sha(tuple(git_entries))
    manifest = sha256(
        b"LION/R9D8/EXACT-PRODUCTION-MANIFEST/1\0"
        + hostsep._canon(sorted(production, key=lambda row: row["path"]))
    ).hexdigest()
    payload = hostsep._candidate_tree_payload_digest(rows)
    object_digest = hostsep._candidate_tree_object_digest(
        tree, len(rows), manifest, len(production)
    )
    return rows, tree, manifest, payload, object_digest, len(production)


def _tree_receipt(files, observation_id="tree-fixture", *, signed=True):
    rows, tree, manifest, payload, object_digest, production_count = _tree_material(files)
    receipt = _receipt(
        hostsep.CANDIDATE_TREE_PROVIDER,
        "git-tree-observer:fixture-1",
        observation_id,
        originver.ORIGIN_CANDIDATE_TREE,
        tree,
        object_digest,
        payload,
        signed=signed,
    )
    return receipt, rows, tree, manifest, production_count


def _repository_material(tree_sha: str):
    base_raw = commit_obj("1" * 40, (), "base")
    base = oid(base_raw)
    head_raw = commit_obj(tree_sha, (base,), "head")
    head = oid(head_raw)
    synthetic_raw = commit_obj(tree_sha, (base, head), "merge")
    synthetic = oid(synthetic_raw)
    pr = {
        "number": 234,
        "base": {
            "ref": BASE_REF,
            "sha": base,
            "repo": {"full_name": CANONICAL_REPOSITORY},
        },
        "head": {
            "ref": HEAD_REF,
            "sha": head,
            "repo": {"full_name": CANONICAL_REPOSITORY},
        },
        "merge_commit_sha": synthetic,
    }
    pr_payload = json.dumps(pr, sort_keys=True, separators=(",", ":")).encode()
    payload = hostsep._bundle_digest(
        b"LION/REPOSITORY-CURRENTNESS-PRIMARY-PAYLOAD/1\0",
        pr_payload,
        base_raw,
        head_raw,
        synthetic_raw,
    )
    object_digest = hostsep._repository_object_digest(
        repository=CANONICAL_REPOSITORY,
        pr_number=234,
        base_ref=BASE_REF,
        base_sha=base,
        base_tree="1" * 40,
        head_ref=HEAD_REF,
        head_sha=head,
        head_tree=tree_sha,
        synthetic_sha=synthetic,
        synthetic_tree=tree_sha,
        synthetic_parents=(base, head),
    )
    return pr_payload, base_raw, head_raw, synthetic_raw, payload, object_digest


class HostAuthoritySeparationTests(unittest.TestCase):
    def files(self):
        return (
            (".github/workflows/x.yml", "100644", b"name: x\n"),
            ("README.md", "100644", b"fixture\n"),
            ("cyber_lion/enterprise/x.py", "100644", b"VALUE=1\n"),
            ("cyber_lion/tests/test_x.py", "100644", b"pass\n"),
        )

    def changed_files(self):
        return (
            (".github/workflows/x.yml", "100644", b"name: y\n"),
            ("README.md", "100644", b"fixture\n"),
            ("cyber_lion/enterprise/x.py", "100644", b"VALUE=1\n"),
            ("cyber_lion/tests/test_x.py", "100644", b"pass\n"),
        )

    def tree_evidence(self, *, changed=False):
        files = self.changed_files() if changed else self.files()
        receipt, _, _, _, _ = _tree_receipt(
            files, "tree-changed" if changed else "tree-fixture"
        )
        return derive_candidate_tree_evidence(receipt, files)

    def repo_evidence(self, tree=None):
        tree = tree or self.tree_evidence()
        pr_payload, base_raw, head_raw, synthetic_raw, payload, object_digest = _repository_material(
            tree.tree_sha
        )
        receipt = _receipt(
            CANONICAL_REPOSITORY_PROVIDER,
            "github-rest-observer:fixture-1",
            "repo-fixture",
            originver.ORIGIN_REPOSITORY_CURRENTNESS,
            f"{CANONICAL_REPOSITORY}#PR234",
            object_digest,
            payload,
        )
        return derive_repository_currentness_evidence(
            receipt,
            pr_payload=pr_payload,
            base_commit_object=base_raw,
            head_commit_object=head_raw,
            synthetic_commit_object=synthetic_raw,
        )

    def pre_schema(self):
        rows = (
            (
                "table",
                "pr_bootstrap",
                "pr_bootstrap",
                "CREATE TABLE pr_bootstrap(x TEXT)",
            ),
            (
                "table",
                "authority_lineage",
                "authority_lineage",
                "CREATE TABLE authority_lineage(x TEXT)",
            ),
        )
        entries = tuple(
            sorted(
                (
                    (typ, name, table, hostsep._normalize_sql(sql))
                    for typ, name, table, sql in rows
                ),
                key=lambda row: (row[0], row[1]),
            )
        )
        manifest = hostsep._schema_manifest_digest(entries)
        payload = hostsep._pre_schema_payload_digest(H, entries)
        object_digest = hostsep._pre_schema_object_digest(H, manifest)
        receipt = _receipt(
            hostsep.SCHEMA_MANIFEST_PROVIDER,
            "sqlite-schema-observer:fixture-1",
            "schema-fixture",
            originver.ORIGIN_PRE_SCHEMA,
            LIVE_DB_PATH,
            object_digest,
            payload,
        )
        return derive_schema_manifest_evidence(
            receipt, rows, source_database_sha256=H
        )

    def plan(self):
        tree = self.tree_evidence()
        repo = self.repo_evidence(tree)
        pre = self.pre_schema()
        plan = HostAuthoritySeparationBroker.canonical_plan(
            repository_evidence=repo,
            candidate_tree_evidence=tree,
            pre_schema_evidence=pre,
            trusted_runtime_reads=(
                TrustedRuntimeReadBinding(
                    "/opt/lion/trusted-runtime/workflow-dispatch-test/runtime_provider.py",
                    H,
                ),
            ),
            generated_at=T,
        )
        return plan, repo, tree, pre

    def authority(self, **changes):
        data = dict(
            issuer_subject_id="prod-issuer-1",
            trust_domain="prod.example",
            key_id="kms://issuer/1",
            algorithm="opaque-external",
            provenance_class="PRODUCTION_EXTERNAL",
            host_principal=None,
            private_key_on_host=False,
        )
        data.update(changes)
        return ExternalAuthorityIdentity(**data).validate()

    def host_obs(self, **changes):
        data = dict(
            hostname="MOON",
            runtime_user=RUNTIME_USER,
            runner_user=RUNNER_USER,
            runner_groups=(RUNNER_USER, CONTROL_PLANE_GROUP),
            runner_db_read=True,
            runner_db_write=True,
            runner_service_env_read=True,
            runtime_code_write=False,
            runner_actions_private_key_read=False,
            runner_authority_private_key_read=False,
            live_db_sha256=H,
            deployed_manifest_sha256=H2,
            service_unit_sha256=H3,
            observed_at=T,
        )
        data.update(changes)
        return HostAuthorityObservation(**data).validate()

    def deploy_req(self, plan, repo, tree, **changes):
        data = dict(
            request_id="deploy-1",
            repository=repo.repository,
            pr_number=repo.pr_number,
            baseline_ref=repo.base_ref,
            baseline_sha=repo.base_sha,
            baseline_tree=repo.base_tree,
            candidate_ref=repo.head_ref,
            candidate_sha=repo.head_sha,
            candidate_tree=repo.head_tree,
            synthetic_sha=repo.synthetic_sha,
            repository_evidence_digest=repo.digest(),
            source_manifest_sha256=tree.production_manifest_sha256,
            current_deployed_manifest_sha256=H2,
            service_unit_sha256=H3,
            separation_plan_digest=plan.digest(),
            requester_principal="candidate-builder",
            requested_at=T,
        )
        data.update(changes)
        return DeploymentRequest(**data).validate()

    def deploy_args(self, plan, repo, tree, **changes):
        data = dict(
            plan=plan,
            authority=self.authority(),
            repository_evidence=repo,
            candidate_tree_evidence=tree,
            current_deployed_manifest_sha256=H2,
            current_service_unit_sha256=H3,
            issued_at=T,
        )
        data.update(changes)
        return data

    def before(self, pre, **changes):
        data = dict(
            database_sha256=H,
            schema_digest=pre.digest(),
            pr_bootstrap_rows=0,
            authority_lineage_rows=2,
            objects=PRESERVED_TABLES,
            integrity_check="ok",
            observed_at=T,
        )
        data.update(changes)
        return SchemaObservation(**data).validate()

    def snapshot(self, before):
        snapshot_bytes = b"actual-consistent-snapshot-bytes"
        snapshot_sha = sha256(snapshot_bytes).hexdigest()
        path = SNAPSHOT_DIR + "/control-plane.pre.sqlite"
        object_digest = hostsep._snapshot_object_digest(
            snapshot_path=path,
            source_database_sha256=before.database_sha256,
            snapshot_sha256=snapshot_sha,
            snapshot_size=len(snapshot_bytes),
            source_observation_digest=before.digest(),
            integrity_check="ok",
            created_at=T,
        )
        receipt = _receipt(
            CANONICAL_SNAPSHOTTER_IDENTITY,
            "snapshot-observer:fixture-1",
            "snapshot-fixture",
            originver.ORIGIN_SNAPSHOT,
            path,
            object_digest,
            snapshot_sha,
        )
        return derive_snapshot_provenance(
            receipt,
            source_observation=before,
            snapshot_path=path,
            snapshot_bytes=snapshot_bytes,
            integrity_check="ok",
        )

    def migration_req(self, plan, repo, pre, snapshot, **changes):
        data = dict(
            request_id="migrate-1",
            repository=repo.repository,
            pr_number=repo.pr_number,
            candidate_ref=repo.head_ref,
            candidate_sha=repo.head_sha,
            candidate_tree=repo.head_tree,
            synthetic_sha=repo.synthetic_sha,
            repository_evidence_digest=repo.digest(),
            live_database_sha256=H,
            pre_schema_digest=pre.digest(),
            schema_sql_sha256=CANONICAL_SCHEMA_SQL_SHA256,
            snapshot_sha256=snapshot.attestation.snapshot_sha256,
            expected_post_schema_digest=derive_expected_post_schema_evidence(pre).digest(),
            separation_plan_digest=plan.digest(),
            requester_principal="candidate-builder",
            requested_at=T,
        )
        data.update(changes)
        return SchemaMigrationRequest(**data).validate()

    def test_independent_signed_origins_drive_canonical_plan(self):
        plan, repo, tree, pre = self.plan()
        self.assertEqual(plan.certified_repository_evidence_digest, repo.digest())
        self.assertEqual(plan.certified_source_manifest_sha256, tree.production_manifest_sha256)
        self.assertEqual(plan.certified_pre_schema_manifest_digest, pre.digest())
        self.assertTrue(repo.origin_digest())
        self.assertTrue(tree.origin_digest())
        self.assertTrue(pre.origin_digest())

    def test_observed_bypass_requires_transition_and_target_closes(self):
        plan, _, _, _ = self.plan()
        observation = self.host_obs()
        self.assertFalse(
            HostAuthoritySeparationBroker.target_observation_is_separated(observation)
        )
        kinds = {
            operation.kind
            for operation in HostAuthoritySeparationBroker.derive_transition(
                observation, plan, generated_at=T
            ).operations
        }
        self.assertIn("REMOVE_RUNNER_CONTROL_PLANE_GROUP", kinds)
        self.assertIn("DENY_RUNNER_DB_ACCESS", kinds)
        target = self.host_obs(
            runner_groups=(RUNNER_USER, TRUST_CLIENT_GROUP),
            runner_db_read=False,
            runner_db_write=False,
            runner_service_env_read=False,
        )
        self.assertTrue(
            HostAuthoritySeparationBroker.target_observation_is_separated(target)
        )

    def test_no_in_process_provider_capability_or_signer_exists(self):
        host_source = Path("cyber_lion/enterprise/host_authority_separation.py").read_text()
        verifier_source = Path("cyber_lion/enterprise/independent_evidence_origin.py").read_text()
        for forbidden in ("_EVIDENCE_CAP", "_mint_provider_token", "IndependentEvidenceProviderToken"):
            self.assertNotIn(forbidden, host_source)
        for forbidden in ("private_key", "signing_secret", "os.environ", "os.getenv", "subprocess", "requests", "urllib"):
            self.assertNotIn(forbidden, verifier_source)
        for callable_ in (
            derive_candidate_tree_evidence,
            derive_repository_currentness_evidence,
            derive_schema_manifest_evidence,
            derive_snapshot_provenance,
        ):
            params = set(inspect.signature(callable_).parameters)
            self.assertNotIn("provider", params)
            self.assertNotIn("verifier", params)
            self.assertNotIn("trust_anchor", params)

    def test_candidate_tree_and_manifest_are_byte_derived_and_origin_bound(self):
        tree = self.tree_evidence()
        self.assertEqual(tree.production_entry_count, 2)
        with self.assertRaises(HostAuthoritySeparationError):
            replace(tree, production_manifest_sha256=H5).validate()
        changed = self.tree_evidence(changed=True)
        plan, repo, _, pre = self.plan()
        with self.assertRaises(HostAuthoritySeparationError):
            HostAuthoritySeparationBroker.canonical_plan(
                repository_evidence=repo,
                candidate_tree_evidence=changed,
                pre_schema_evidence=pre,
                trusted_runtime_reads=plan.trusted_runtime_reads,
                generated_at=T,
            )

    def test_repository_currentness_is_git_object_derived_and_origin_bound(self):
        repo = self.repo_evidence()
        self.assertEqual(repo.synthetic_parents, (repo.base_sha, repo.head_sha))
        self.assertEqual(repo.synthetic_tree, repo.head_tree)
        with self.assertRaises(HostAuthoritySeparationError):
            replace(repo, provider_id="caller").validate()
        with self.assertRaises(HostAuthoritySeparationError):
            replace(repo, synthetic_sha="f" * 40).validate()

    def test_role_separation_and_test_authority_promotion_denied(self):
        plan, repo, tree, _ = self.plan()
        request = self.deploy_req(plan, repo, tree)
        with self.assertRaises(HostAuthorityContractError):
            self.authority(provenance_class="TEST_ONLY")
        for principal in (DEPLOYER_USER, MIGRATOR_USER, RUNTIME_USER, RUNNER_USER):
            with self.subTest(principal=principal), self.assertRaises(
                HostAuthoritySeparationError
            ):
                BoundedDeploymentBroker.admit(
                    request,
                    **(
                        self.deploy_args(plan, repo, tree)
                        | {"authority": self.authority(host_principal=principal)}
                    ),
                )

    def test_candidate_builder_cannot_self_deploy_or_migrate(self):
        plan, repo, tree, pre = self.plan()
        before = self.before(pre)
        snapshot = self.snapshot(before)
        for principal in (DEPLOYER_USER, MIGRATOR_USER, RUNTIME_USER):
            with self.assertRaises(HostAuthorityContractError):
                self.deploy_req(plan, repo, tree, requester_principal=principal)
            with self.assertRaises(HostAuthorityContractError):
                self.migration_req(
                    plan, repo, pre, snapshot, requester_principal=principal
                )

    def test_deployment_permit_binds_all_origin_digests(self):
        plan, repo, tree, _ = self.plan()
        request = self.deploy_req(plan, repo, tree)
        args = self.deploy_args(plan, repo, tree)
        permit = BoundedDeploymentBroker.admit(request, **args)
        expected = hostsep._deployment_currentness_digest(
            request, repo, tree, H2, H3
        )
        self.assertEqual(permit.currentness_digest, expected)
        self.assertEqual(permit.fixed_payload_digest, tree.production_manifest_sha256)
        with self.assertRaises(HostAuthoritySeparationError):
            BoundedDeploymentBroker.admit(
                replace(request, source_manifest_sha256=H5), **args
            )
        reargs = {key: value for key, value in args.items() if key not in {"authority", "issued_at"}}
        self.assertIs(
            BoundedDeploymentBroker.revalidate_before_effect(
                request, permit, **reargs
            ),
            permit,
        )
        with self.assertRaises(HostAuthoritySeparationError):
            BoundedDeploymentBroker.revalidate_before_effect(
                request, replace(permit, currentness_digest=H5), **reargs
            )

    def test_snapshot_digest_is_actual_byte_derived_and_signed_origin_bound(self):
        _, _, _, pre = self.plan()
        before = self.before(pre)
        snapshot = self.snapshot(before)
        self.assertEqual(
            snapshot.attestation.snapshot_sha256,
            sha256(b"actual-consistent-snapshot-bytes").hexdigest(),
        )
        self.assertEqual(snapshot.attestation.source_observation_digest, before.digest())
        self.assertEqual(
            snapshot.attestation.snapshotter_identity, CANONICAL_SNAPSHOTTER_IDENTITY
        )
        with self.assertRaises(HostAuthoritySeparationError):
            SnapshotProvenanceEvidence(
                replace(snapshot.attestation, snapshot_sha256=H5),
                snapshot.origin_receipt,
            ).validate()

    def test_migration_binds_schema_snapshot_and_derived_post_schema(self):
        plan, repo, _, pre = self.plan()
        before = self.before(pre)
        snapshot = self.snapshot(before)
        request = self.migration_req(plan, repo, pre, snapshot)
        permit = BoundedSchemaMigrationBroker.admit(
            request,
            plan=plan,
            authority=self.authority(),
            repository_evidence=repo,
            before=before,
            pre_schema_evidence=pre,
            snapshot_evidence=snapshot,
            issued_at=T,
        )
        self.assertEqual(permit.fixed_payload_digest, CANONICAL_SCHEMA_SQL_SHA256)
        self.assertEqual(schema_sql_digest(), CANONICAL_SCHEMA_SQL_SHA256)
        for bad_request in (
            replace(request, schema_sql_sha256=H5),
            replace(request, snapshot_sha256=H5),
            replace(request, expected_post_schema_digest=H5),
            replace(request, synthetic_sha="f" * 40),
        ):
            with self.assertRaises(HostAuthoritySeparationError):
                BoundedSchemaMigrationBroker.admit(
                    bad_request,
                    plan=plan,
                    authority=self.authority(),
                    repository_evidence=repo,
                    before=before,
                    pre_schema_evidence=pre,
                    snapshot_evidence=snapshot,
                    issued_at=T,
                )

    def test_post_schema_is_derived_not_caller_selected(self):
        _, _, _, pre = self.plan()
        before = self.before(pre)
        expected = derive_expected_post_schema_evidence(pre)
        after = SchemaObservation(
            H5,
            expected.digest(),
            0,
            2,
            tuple(row[1] for row in expected.entries),
            "ok",
            T,
        ).validate()
        self.assertIs(
            BoundedSchemaMigrationBroker.verify_postcondition(
                before,
                after,
                pre_schema_evidence=pre,
                after_schema_evidence=expected,
            ),
            after,
        )
        fake = replace(expected, provenance_digest=H5)
        with self.assertRaises(HostAuthoritySeparationError):
            BoundedSchemaMigrationBroker.verify_postcondition(
                before,
                after,
                pre_schema_evidence=pre,
                after_schema_evidence=fake,
            )

    def test_receipts_bind_permit_request_snapshot_and_schema(self):
        plan, repo, tree, pre = self.plan()
        deployment_request = self.deploy_req(plan, repo, tree)
        deployment_permit = BoundedDeploymentBroker.admit(
            deployment_request, **self.deploy_args(plan, repo, tree)
        )
        good = DeploymentReceipt(
            "deploy-r",
            deployment_request.digest(),
            deployment_permit.digest(),
            "DEPLOYED",
            H2,
            H5,
            repo.head_sha,
            repo.head_tree,
            T,
        ).validate()
        self.assertIs(
            BoundedDeploymentBroker.verify_receipt(
                deployment_request, deployment_permit, good
            ),
            good,
        )

        before = self.before(pre)
        snapshot = self.snapshot(before)
        migration_request = self.migration_req(plan, repo, pre, snapshot)
        migration_permit = BoundedSchemaMigrationBroker.admit(
            migration_request,
            plan=plan,
            authority=self.authority(),
            repository_evidence=repo,
            before=before,
            pre_schema_evidence=pre,
            snapshot_evidence=snapshot,
            issued_at=T,
        )
        post = derive_expected_post_schema_evidence(pre)
        after = SchemaObservation(
            H5, post.digest(), 0, 2, tuple(row[1] for row in post.entries), "ok", T
        ).validate()
        receipt = MigrationReceipt(
            "migrate-r",
            migration_request.digest(),
            migration_permit.digest(),
            snapshot.attestation.snapshot_sha256,
            pre.digest(),
            post.digest(),
            0,
            2,
            "MIGRATED",
            T,
        ).validate()
        self.assertIs(
            BoundedSchemaMigrationBroker.verify_receipt(
                migration_request,
                migration_permit,
                before,
                pre,
                snapshot,
                after,
                post,
                receipt,
            ),
            receipt,
        )

    def test_coherent_fake_world_a_repository_tree_manifest_is_denied_by_origin(self):
        fake_files = (
            ("cyber_lion/enterprise/evil.py", "100644", b"OWNED=True\n"),
            (".github/workflows/evil.yml", "100644", b"name: evil\n"),
        )
        _, fake_tree, _, payload, object_digest, _ = _tree_material(fake_files)
        fake_tree_receipt = _receipt(
            hostsep.CANDIDATE_TREE_PROVIDER,
            "attacker-tree:1",
            "attacker-tree-observation",
            originver.ORIGIN_CANDIDATE_TREE,
            fake_tree,
            object_digest,
            payload,
            signed=False,
        )
        with self.assertRaises(HostAuthoritySeparationError):
            derive_candidate_tree_evidence(fake_tree_receipt, fake_files)

        pr_payload, base_raw, head_raw, synthetic_raw, repo_payload, repo_object = _repository_material(
            fake_tree
        )
        fake_repo_receipt = _receipt(
            CANONICAL_REPOSITORY_PROVIDER,
            "attacker-github:1",
            "attacker-repo-observation",
            originver.ORIGIN_REPOSITORY_CURRENTNESS,
            f"{CANONICAL_REPOSITORY}#PR234",
            repo_object,
            repo_payload,
            signed=False,
        )
        with self.assertRaises(HostAuthoritySeparationError):
            derive_repository_currentness_evidence(
                fake_repo_receipt,
                pr_payload=pr_payload,
                base_commit_object=base_raw,
                head_commit_object=head_raw,
                synthetic_commit_object=synthetic_raw,
            )

    def test_coherent_fake_world_b_schema_snapshot_post_is_denied_by_origin(self):
        fake_rows = (
            ("table", "pr_bootstrap", "pr_bootstrap", "CREATE TABLE pr_bootstrap(evil TEXT)"),
            ("table", "authority_lineage", "authority_lineage", "CREATE TABLE authority_lineage(evil TEXT)"),
        )
        entries = tuple(
            sorted(
                (
                    (typ, name, table, hostsep._normalize_sql(sql))
                    for typ, name, table, sql in fake_rows
                ),
                key=lambda row: (row[0], row[1]),
            )
        )
        manifest = hostsep._schema_manifest_digest(entries)
        payload = hostsep._pre_schema_payload_digest(H5, entries)
        object_digest = hostsep._pre_schema_object_digest(H5, manifest)
        fake_schema_receipt = _receipt(
            hostsep.SCHEMA_MANIFEST_PROVIDER,
            "attacker-schema:1",
            "attacker-schema-observation",
            originver.ORIGIN_PRE_SCHEMA,
            LIVE_DB_PATH,
            object_digest,
            payload,
            signed=False,
        )
        with self.assertRaises(HostAuthoritySeparationError):
            derive_schema_manifest_evidence(
                fake_schema_receipt,
                fake_rows,
                source_database_sha256=H5,
            )

        valid_pre = self.pre_schema()
        before = self.before(valid_pre)
        fake_bytes = b"coherent-attacker-snapshot"
        fake_sha = sha256(fake_bytes).hexdigest()
        path = SNAPSHOT_DIR + "/attacker.sqlite"
        fake_object = hostsep._snapshot_object_digest(
            snapshot_path=path,
            source_database_sha256=before.database_sha256,
            snapshot_sha256=fake_sha,
            snapshot_size=len(fake_bytes),
            source_observation_digest=before.digest(),
            integrity_check="ok",
            created_at=T,
        )
        fake_snapshot_receipt = _receipt(
            CANONICAL_SNAPSHOTTER_IDENTITY,
            "attacker-snapshot:1",
            "attacker-snapshot-observation",
            originver.ORIGIN_SNAPSHOT,
            path,
            fake_object,
            fake_sha,
            signed=False,
        )
        with self.assertRaises(HostAuthoritySeparationError):
            derive_snapshot_provenance(
                fake_snapshot_receipt,
                source_observation=before,
                snapshot_path=path,
                snapshot_bytes=fake_bytes,
                integrity_check="ok",
            )

    def test_coherent_fake_world_c_cannot_reseal_public_certification_api(self):
        plan, repo, tree, pre = self.plan()

        forged_tree_receipt = _reseal(
            tree.origin_receipt,
            provider_instance_id="attacker-tree:resealed",
            observation_id="attacker-tree-resealed",
            nonce=sha256(b"attacker-tree-resealed").hexdigest(),
        )
        forged_tree_provenance = hostsep._digest(
            b"LION/CANDIDATE-TREE-EVIDENCE/2\0",
            {
                "tree_sha": tree.tree_sha,
                "tracked_file_count": tree.tracked_file_count,
                "production_manifest_sha256": tree.production_manifest_sha256,
                "production_entry_count": tree.production_entry_count,
                "provider_observation_id": forged_tree_receipt.observation_id,
                "provider_instance_id": forged_tree_receipt.provider_instance_id,
                "full_entries": tree.full_entries,
                "origin_receipt_digest": forged_tree_receipt.digest(),
            },
        )
        forged_tree = CandidateTreeEvidence(
            tree.tree_sha,
            tree.tracked_file_count,
            tree.production_manifest_sha256,
            tree.production_entry_count,
            forged_tree_receipt.observation_id,
            forged_tree_receipt.provider_instance_id,
            tree.full_entries,
            forged_tree_receipt,
            forged_tree_provenance,
        )

        forged_repo_receipt = _reseal(
            repo.origin_receipt,
            provider_instance_id="attacker-github:resealed",
            observation_id="attacker-repo-resealed",
            nonce=sha256(b"attacker-repo-resealed").hexdigest(),
        )
        forged_repo_provenance = hostsep._digest(
            b"LION/REPOSITORY-CURRENTNESS-EVIDENCE/2\0",
            {
                "provider_id": repo.provider_id,
                "provider_instance_id": forged_repo_receipt.provider_instance_id,
                "repository": repo.repository,
                "pr_number": repo.pr_number,
                "base_ref": repo.base_ref,
                "base_sha": repo.base_sha,
                "base_tree": repo.base_tree,
                "head_ref": repo.head_ref,
                "head_sha": repo.head_sha,
                "head_tree": repo.head_tree,
                "synthetic_sha": repo.synthetic_sha,
                "synthetic_tree": repo.synthetic_tree,
                "synthetic_parents": repo.synthetic_parents,
                "provider_payload_sha256": repo.provider_payload_sha256,
                "provider_observation_id": forged_repo_receipt.observation_id,
                "observed_at": repo.observed_at,
                "origin_receipt_digest": forged_repo_receipt.digest(),
            },
        )
        forged_repo = RepositoryCurrentnessEvidence(
            repo.provider_id,
            forged_repo_receipt.provider_instance_id,
            repo.repository,
            repo.pr_number,
            repo.base_ref,
            repo.base_sha,
            repo.base_tree,
            repo.head_ref,
            repo.head_sha,
            repo.head_tree,
            repo.synthetic_sha,
            repo.synthetic_tree,
            repo.synthetic_parents,
            repo.provider_payload_sha256,
            forged_repo_receipt.observation_id,
            repo.observed_at,
            forged_repo_receipt,
            forged_repo_provenance,
        )

        forged_pre_receipt = _reseal(
            pre.origin_receipt,
            provider_instance_id="attacker-schema:resealed",
            observation_id="attacker-schema-resealed",
            nonce=sha256(b"attacker-schema-resealed").hexdigest(),
        )
        forged_pre_provenance = hostsep._digest(
            b"LION/PRE-SCHEMA-EVIDENCE/2\0",
            {
                "entries": pre.entries,
                "manifest_digest": pre.manifest_digest,
                "source_database_sha256": pre.source_database_sha256,
                "provider_observation_id": forged_pre_receipt.observation_id,
                "provider_instance_id": forged_pre_receipt.provider_instance_id,
                "origin_receipt_digest": forged_pre_receipt.digest(),
            },
        )
        forged_pre = SchemaManifestEvidence(
            pre.entries,
            pre.manifest_digest,
            pre.source_database_sha256,
            forged_pre_receipt.observation_id,
            forged_pre_receipt.provider_instance_id,
            forged_pre_provenance,
            forged_pre_receipt,
            None,
        )

        with self.assertRaises(HostAuthoritySeparationError):
            HostAuthoritySeparationBroker.canonical_plan(
                repository_evidence=forged_repo,
                candidate_tree_evidence=forged_tree,
                pre_schema_evidence=forged_pre,
                trusted_runtime_reads=plan.trusted_runtime_reads,
                generated_at=T,
            )

        deployment_request = self.deploy_req(plan, repo, tree)
        with self.assertRaises(HostAuthoritySeparationError):
            BoundedDeploymentBroker.admit(
                deployment_request,
                plan=plan,
                authority=self.authority(),
                repository_evidence=forged_repo,
                candidate_tree_evidence=forged_tree,
                current_deployed_manifest_sha256=H2,
                current_service_unit_sha256=H3,
                issued_at=T,
            )

        before = self.before(pre)
        snapshot = self.snapshot(before)
        migration_request = self.migration_req(plan, repo, pre, snapshot)
        with self.assertRaises(HostAuthoritySeparationError):
            BoundedSchemaMigrationBroker.admit(
                migration_request,
                plan=plan,
                authority=self.authority(),
                repository_evidence=forged_repo,
                before=before,
                pre_schema_evidence=forged_pre,
                snapshot_evidence=snapshot,
                issued_at=T,
            )

    def test_provider_verifier_anchor_instance_observation_and_nonce_substitution_denied(self):
        tree = self.tree_evidence()
        mutations = (
            {"provider_id": "caller-selected-provider"},
            {"provider_instance_id": "caller-selected-instance"},
            {"observation_id": "caller-selected-observation"},
            {"trust_anchor_id": "caller-selected-anchor"},
            {"algorithm": "caller-selected-verifier"},
            {"nonce": sha256(b"caller-selected-nonce").hexdigest()},
        )
        for mutation in mutations:
            forged = _reseal(tree.origin_receipt, **mutation)
            forged_evidence = replace(
                tree,
                origin_receipt=forged,
                provider_observation_id=forged.observation_id,
                provider_instance_id=forged.provider_instance_id,
                provenance_digest=hostsep._digest(
                    b"LION/CANDIDATE-TREE-EVIDENCE/2\0",
                    {
                        "tree_sha": tree.tree_sha,
                        "tracked_file_count": tree.tracked_file_count,
                        "production_manifest_sha256": tree.production_manifest_sha256,
                        "production_entry_count": tree.production_entry_count,
                        "provider_observation_id": forged.observation_id,
                        "provider_instance_id": forged.provider_instance_id,
                        "full_entries": tree.full_entries,
                        "origin_receipt_digest": forged.digest(),
                    },
                ),
            )
            with self.subTest(mutation=mutation), self.assertRaises(
                HostAuthoritySeparationError
            ):
                forged_evidence.validate()

    def test_cross_origin_confusion_is_denied(self):
        tree_receipt, _, _, _, _ = _tree_receipt(self.files())
        rows = (
            ("table", "pr_bootstrap", "pr_bootstrap", "CREATE TABLE pr_bootstrap(x TEXT)"),
        )
        with self.assertRaises(HostAuthoritySeparationError):
            derive_schema_manifest_evidence(
                tree_receipt, rows, source_database_sha256=H
            )

    def test_stale_repository_tree_binding_is_denied(self):
        old_tree = self.tree_evidence()
        old_repo = self.repo_evidence(old_tree)
        current_tree = self.tree_evidence(changed=True)
        pre = self.pre_schema()
        with self.assertRaises(HostAuthoritySeparationError):
            HostAuthoritySeparationBroker.canonical_plan(
                repository_evidence=old_repo,
                candidate_tree_evidence=current_tree,
                pre_schema_evidence=pre,
                trusted_runtime_reads=(
                    TrustedRuntimeReadBinding(
                        "/opt/lion/trusted-runtime/workflow-dispatch-test/runtime_provider.py",
                        H,
                    ),
                ),
                generated_at=T,
            )

    def test_public_api_has_no_origin_mint_verifier_or_trust_anchor_selector(self):
        params = set(
            inspect.signature(HostAuthoritySeparationBroker.canonical_plan).parameters
        )
        self.assertEqual(
            params,
            {
                "repository_evidence",
                "candidate_tree_evidence",
                "pre_schema_evidence",
                "trusted_runtime_reads",
                "generated_at",
            },
        )
        for callable_ in (
            HostAuthoritySeparationBroker.canonical_plan,
            BoundedDeploymentBroker.admit,
            BoundedSchemaMigrationBroker.admit,
        ):
            names = set(inspect.signature(callable_).parameters)
            self.assertFalse(
                names
                & {
                    "provider",
                    "provider_id",
                    "provider_instance",
                    "verifier",
                    "trust_anchor",
                    "private_key",
                    "secret",
                }
            )

    def test_complete_mediation_inventory_adds_no_effect_surface(self):
        paths = (
            "cyber_lion/contracts/host_authority_separation.py",
            "cyber_lion/contracts/independent_evidence_origin.py",
            "cyber_lion/enterprise/host_authority_separation.py",
            "cyber_lion/enterprise/independent_evidence_origin.py",
        )
        inventory = EffectSurfaceScanner().scan(
            repository=CANONICAL_REPOSITORY,
            revision="1" * 40,
            tree_digest="2" * 40,
            sources={path: Path(path).read_text() for path in paths},
        )
        self.assertEqual(inventory.unclassified_refs, ())
        self.assertEqual(inventory.surfaces, ())

    def test_external_read_binding_and_permit_are_bounded(self):
        with self.assertRaises(HostAuthorityContractError):
            TrustedRuntimeReadBinding(LIVE_DB_PATH, H).validate()
        plan, repo, tree, _ = self.plan()
        permit = BoundedDeploymentBroker.admit(
            self.deploy_req(plan, repo, tree),
            **self.deploy_args(plan, repo, tree),
        )
        self.assertEqual(permit.fixed_executor_principal, "root")
        self.assertFalse(hasattr(permit, "execute"))
        self.assertFalse(hasattr(permit, "authority_grant"))
        self.assertFalse(hasattr(permit, "credential"))


if __name__ == "__main__":
    unittest.main()
