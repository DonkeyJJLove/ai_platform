from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.contracts.authority_provisioning import (
    AuthorityEpochBootstrap,
    AuthorityIssuerBinding,
    AuthorityProvisioningDecision,
    AuthorityRootBootstrap,
    RepositoryRefAuthorityProvisioningRequest,
    RepositoryRefAuthorityProvisioningTransaction,
)
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_provisioning import (
    AuthorityProvisioningError,
    SQLiteAuthorityProvisioningStore,
    authority_provisioning_schema_sql,
)
from cyber_lion.enterprise.authority_source import (
    AuthoritySource,
    AuthoritySourceError,
    RepositoryRefAuthorityLineageRecord,
    RepositoryRefAuthorityLookupKey,
    canonical_repository_ref_authority_resource,
    canonical_source_lineage_digest,
)
from cyber_lion.enterprise.authority_source_adapter import (
    AuthoritySourceTransport,
    TrustedControlPlaneAuthoritySource,
)
from cyber_lion.enterprise.authority_verification import AuthorityVerificationContext, IssuerKeyBinding
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.persistent_authority_state import (
    DurableReplayGuard,
    PersistentBindingFinalizer,
    PersistentEpochStateProvider,
    PersistentRootAnchorProvider,
    SQLiteAuthorityStateStore,
)
from cyber_lion.enterprise.trusted_control_plane_providers import SQLiteTrustedControlPlaneStore

REPO = "DonkeyJJLove/ai_platform"
BRANCH = "docs/lion-v1.4-r20-documentation-homeostasis-ai-platform"
HEAD = "1" * 40
MASTER = "2" * 40
MISSION = "repository-maintenance-prod"
POLICY = "sha256:" + "a" * 64
OBS = "sha256:" + "b" * 64
DOMAIN = "lion.prod.repository-maintenance"
TENANT = "tenant-prod"
ORG = "org-prod"
ADMIN = "repository-maintenance-authority-admin"
ROOT_ISSUER = "repository-maintenance-root-issuer"
DELEGATOR = "repository-maintenance-delegator"
EXECUTOR = "repository-maintenance-runner"
REQUESTER = "repository-maintenance-controller"
NOW = "2026-09-09T01:00:00+00:00"


def sig(key: str, alg: str = "TEST-ALG") -> str:
    return f"sig:{key}:{alg}"


def verifier(_payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    return signature == sig(key_id, algorithm)


def key(**overrides) -> RepositoryRefAuthorityLookupKey:
    values = dict(
        repository=REPO,
        branch=BRANCH,
        expected_head=HEAD,
        protected_master_sha=MASTER,
        mission_id=MISSION,
        grant_id="leaf-grant",
    )
    values.update(overrides)
    return RepositoryRefAuthorityLookupKey(**values).validate()


def raw_grant(grant: AuthorityGrant) -> dict[str, object]:
    value = asdict(grant)
    value["actions"] = list(grant.actions)
    value["resource_scope"] = list(grant.resource_scope)
    value["constraints"] = list(grant.constraints)
    return value


def raw_record(record: RepositoryRefAuthorityLineageRecord) -> dict[str, object]:
    return {
        "lookup_key": asdict(record.lookup_key),
        "lineage": [raw_grant(g) for g in record.lineage],
        "lineage_digest": record.lineage_digest,
        "provenance_id": record.provenance_id,
        "source_kind": record.source_kind,
    }


class StaticSource(AuthoritySource):
    def __init__(self, record):
        self.record = record

    def _lookup_exact(self, _key):
        return ()

    def _lookup_repository_ref_exact(self, requested):
        return (self.record,) if requested.binding() == self.record.lookup_key.binding() else ()


class StaticTransport(AuthoritySourceTransport):
    def __init__(self, records):
        self.records = records
        self.calls = []

    def lookup_exact(self, **_kwargs):
        return ()

    def lookup_repository_ref_exact(self, **kwargs):
        self.calls.append(kwargs)
        return self.records


class RepositoryRefAuthorityProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.TemporaryDirectory()
        self.data = tempfile.TemporaryDirectory()
        self.db = Path(self.data.name) / "authority.sqlite"
        sqlite3.connect(self.db).close()
        with sqlite3.connect(self.db) as connection:
            connection.executescript(authority_provisioning_schema_sql())
        self.store = SQLiteAuthorityProvisioningStore(str(self.db), repository_root=self.repo.name)

    def tearDown(self):
        self.repo.cleanup()
        self.data.cleanup()

    def reset(self):
        self.tearDown()
        self.setUp()

    def binding(self, subject, role, key_id):
        return AuthorityIssuerBinding(
            subject, DOMAIN, key_id, "TEST-ALG", role, f"control-plane:{subject}"
        ).validate()

    def build(self, *, request_changes=None, leaf_changes=None, root_changes=None, requester=REQUESTER):
        admin_key = "admin-key"
        root_key = "root-key"
        leaf_key = "leaf-key"
        request = RepositoryRefAuthorityProvisioningRequest(
            "repo-delete-req-1", REPO, BRANCH, HEAD, MASTER, MISSION,
            "delete_exact_branch_ref", "repository_ref.delete", POLICY,
            requester, EXECUTOR, "2026-09-09T00:50:00+00:00",
        ).validate()
        if request_changes:
            request = replace(request, **request_changes)
        epoch = AuthorityEpochBootstrap(
            DOMAIN, TENANT, ORG, MISSION, 9, (), ADMIN, admin_key, "TEST-ALG",
            "2026-09-09T00:00:00+00:00", "control-plane:repo-delete:epoch", sig(admin_key),
        ).validate()
        exact_key = RepositoryRefAuthorityLookupKey(
            request.repository, request.branch, request.expected_head,
            request.protected_master_sha, request.mission_id, "leaf-grant",
        ).validate()
        resource = canonical_repository_ref_authority_resource(exact_key)
        root = AuthorityGrant(
            "1.1.0", "root-grant", ROOT_ISSUER, DELEGATOR, TENANT, ORG, MISSION,
            "repository_ref.delete", "1", ("delete_exact_branch_ref",), (resource,),
            "external_write", (), None,
            "2026-09-09T00:00:00+00:00", "2026-09-10T00:00:00+00:00", 9,
            POLICY, OBS, sig(root_key), True, 1,
        ).validate()
        leaf = AuthorityGrant(
            "1.1.0", "leaf-grant", DELEGATOR, EXECUTOR, TENANT, ORG, MISSION,
            "repository_ref.delete", "1", ("delete_exact_branch_ref",), (resource,),
            "external_write", (), "root-grant",
            "2026-09-09T00:10:00+00:00", "2026-09-09T23:00:00+00:00", 9,
            POLICY, OBS, sig(leaf_key), False, 0,
        ).validate()
        if root_changes:
            root = replace(root, **root_changes)
        if leaf_changes:
            leaf = replace(leaf, **leaf_changes)
        rootb = AuthorityRootBootstrap(
            epoch.digest(), root.grant_id, root.digest(), ADMIN, admin_key, "TEST-ALG",
            "2026-09-09T00:01:00+00:00", "control-plane:repo-delete:root", sig(admin_key),
        ).validate()
        bindings = (
            self.binding(ADMIN, "provisioning-administrator", admin_key),
            self.binding(ROOT_ISSUER, "authority-issuer", root_key),
            self.binding(DELEGATOR, "authority-issuer", leaf_key),
        )
        tx = RepositoryRefAuthorityProvisioningTransaction(
            "repo-delete-tx-1", request, epoch, rootb, bindings,
            canonical_source_lineage_digest((root, leaf)), leaf.grant_id,
            "control-plane:repo-delete:tx",
        ).validate()
        decision = AuthorityProvisioningDecision(
            "repo-delete-decision-1", tx.digest(), "ALLOW", ADMIN, admin_key, "TEST-ALG",
            "2026-09-09T00:55:00+00:00", sig(admin_key),
        ).validate()
        return tx, decision, (root, leaf)

    def bootstrap(self, tx, lineage):
        return self.store.bootstrap_authority_context(
            epoch_bootstrap=tx.epoch_bootstrap,
            root_bootstrap=tx.root_bootstrap,
            root_grant=lineage[0],
            issuer_bindings=tx.issuer_bindings,
            administrator_verifier=verifier,
            authority_verifier=verifier,
            provisioned_at=NOW,
        )

    def provision(self, tx, decision, lineage):
        return self.store.provision_repository_ref_authority(
            transaction=tx,
            decision=decision,
            lineage=lineage,
            administrator_verifier=verifier,
            authority_verifier=verifier,
            provisioned_at=NOW,
        )

    def test_key_and_resource_bind_branch_head_and_master_exactly(self):
        k = key()
        self.assertEqual(
            canonical_repository_ref_authority_resource(k),
            f"github:repo:{REPO}:ref:heads/{BRANCH}:head:{HEAD}:protected-master:{MASTER}",
        )
        for changes in (
            {"branch": "master"},
            {"branch": "feature/not-allowed"},
            {"expected_head": "abc"},
            {"protected_master_sha": "def"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(Exception):
                    key(**changes)

    def test_lineage_record_rejects_resource_substitution(self):
        k = key()
        resource = canonical_repository_ref_authority_resource(k)
        grant = AuthorityGrant(
            "1.1.0", k.grant_id, "issuer", "runner", TENANT, ORG, MISSION,
            "repository_ref.delete", "1", ("delete_exact_branch_ref",), (resource,),
            "external_write", (), None,
            "2026-09-09T00:00:00+00:00", "2026-09-10T00:00:00+00:00", 9,
            POLICY, OBS, "sig",
        ).validate()
        record = RepositoryRefAuthorityLineageRecord(
            k, (grant,), canonical_source_lineage_digest((grant,)), "control-plane:record:repo-delete"
        ).validate()
        self.assertEqual(record.lookup_key, k)
        wrong = replace(grant, resource_scope=(resource + ":tampered",))
        with self.assertRaisesRegex(AuthoritySourceError, "exact repository-ref resource"):
            RepositoryRefAuthorityLineageRecord(
                k, (wrong,), canonical_source_lineage_digest((wrong,)), "control-plane:record:repo-delete"
            ).validate()

    def test_adapter_forwards_only_exact_repository_ref_lookup(self):
        tx, _, lineage = self.build()
        k = RepositoryRefAuthorityLookupKey(
            REPO, BRANCH, HEAD, MASTER, MISSION, lineage[-1].grant_id
        ).validate()
        record = RepositoryRefAuthorityLineageRecord(
            k, lineage, canonical_source_lineage_digest(lineage), "control-plane:repo-delete:lineage"
        ).validate()
        transport = StaticTransport((raw_record(record),))
        resolved = TrustedControlPlaneAuthoritySource(transport).resolve_repository_ref_exact(k)
        self.assertEqual(resolved.lookup_key.binding(), k.binding())
        self.assertEqual(transport.calls, [{
            "repository": REPO,
            "branch": BRANCH,
            "expected_head": HEAD,
            "protected_master_sha": MASTER,
            "mission_id": MISSION,
            "grant_id": "leaf-grant",
        }])

    def test_positive_signed_external_repository_ref_provisioning(self):
        tx, decision, lineage = self.build()
        self.bootstrap(tx, lineage)
        receipt = self.provision(tx, decision, lineage)
        self.assertEqual(receipt.repository, REPO)
        self.assertEqual(receipt.branch, BRANCH)
        self.assertEqual(receipt.expected_head, HEAD)
        self.assertEqual(receipt.protected_master_sha, MASTER)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM repository_ref_authority_lineage").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM authority_provisioning_receipt").fetchone()[0], 2)

    def test_post_binding_request_substitutions_are_denied(self):
        cases = (
            {"repository": "Other/repo"},
            {"branch": "mission/other"},
            {"expected_head": "3" * 40},
            {"protected_master_sha": "4" * 40},
            {"mission_id": "other-mission"},
            {"policy_digest": "sha256:" + "f" * 64},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self.reset()
                tx, _, lineage = self.build()
                self.bootstrap(tx, lineage)
                with self.assertRaises(Exception):
                    changed_request = replace(tx.request, **changes)
                    changed_tx = replace(tx, request=changed_request)
                    changed_decision = AuthorityProvisioningDecision(
                        "repo-delete-decision-tampered", changed_tx.digest(), "ALLOW", ADMIN,
                        "admin-key", "TEST-ALG", "2026-09-09T00:55:00+00:00", sig("admin-key"),
                    ).validate()
                    self.provision(changed_tx, changed_decision, lineage)

    def test_invalid_action_or_capability_is_denied_by_contract(self):
        for changes in ({"action": "merge_pull_request"}, {"capability_id": "github-merge"}):
            with self.subTest(changes=changes):
                with self.assertRaises(Exception):
                    self.build(request_changes=changes)

    def test_fresh_separately_signed_exact_target_is_not_confused_with_tampering(self):
        tx, decision, lineage = self.build(request_changes={"branch": "mission/fresh-exact-target"})
        self.bootstrap(tx, lineage)
        receipt = self.provision(tx, decision, lineage)
        self.assertEqual(receipt.branch, "mission/fresh-exact-target")

    def test_leaf_resource_action_capability_and_policy_substitutions_are_denied(self):
        modifications = (
            {"actions": ("merge_pull_request",)},
            {"capability_id": "github-merge"},
            {"resource_scope": ("github:repo:Other/repo:ref:heads/docs/x:head:" + HEAD + ":protected-master:" + MASTER,)},
            {"policy_digest": "sha256:" + "f" * 64},
        )
        for changes in modifications:
            with self.subTest(changes=changes):
                self.reset()
                tx, decision, lineage = self.build(leaf_changes=changes)
                self.bootstrap(tx, lineage[:1])
                with self.assertRaises(Exception):
                    self.provision(tx, decision, lineage)

    def test_role_overlap_self_signed_denied_and_decision_deny(self):
        tx, decision, lineage = self.build(requester=DELEGATOR)
        self.bootstrap(tx, lineage)
        with self.assertRaises(AuthorityProvisioningError):
            self.provision(tx, decision, lineage)
        self.reset()
        tx, decision, lineage = self.build(leaf_changes={"issuer_subject_id": EXECUTOR})
        self.bootstrap(tx, lineage[:1])
        with self.assertRaises(AuthorityProvisioningError):
            self.provision(tx, decision, lineage)
        self.reset()
        tx, decision, lineage = self.build()
        self.bootstrap(tx, lineage)
        denied = replace(decision, decision="DENY")
        with self.assertRaises(AuthorityProvisioningError):
            self.provision(tx, denied, lineage)

    def test_stale_revoked_and_replay_are_denied(self):
        tx, decision, lineage = self.build()
        self.bootstrap(tx, lineage)
        with sqlite3.connect(self.db) as connection:
            connection.execute("UPDATE authority_epoch_state SET epoch=10")
        with self.assertRaises(AuthorityProvisioningError):
            self.provision(tx, decision, lineage)
        self.reset()
        tx, decision, lineage = self.build()
        self.bootstrap(tx, lineage)
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                "UPDATE authority_epoch_state SET revoked_json=?",
                (json.dumps([lineage[-1].grant_id]),),
            )
        with self.assertRaises(AuthorityProvisioningError):
            self.provision(tx, decision, lineage)
        self.reset()
        tx, decision, lineage = self.build()
        self.bootstrap(tx, lineage)
        self.provision(tx, decision, lineage)
        with self.assertRaises(AuthorityProvisioningError):
            self.provision(tx, decision, lineage)

    def test_atomic_rollback_on_repository_ref_lineage_insert_failure(self):
        tx, decision, lineage = self.build()
        self.bootstrap(tx, lineage)
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                "CREATE TRIGGER fail_repo_ref_lineage BEFORE INSERT ON repository_ref_authority_lineage "
                "BEGIN SELECT RAISE(ABORT,'fail'); END;"
            )
        with self.assertRaises(sqlite3.DatabaseError):
            self.provision(tx, decision, lineage)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM repository_ref_authority_lineage").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM authority_provisioning_receipt").fetchone()[0], 1)

    def test_live_admission_uses_same_epoch_root_signature_and_replay_planes(self):
        tx, _, lineage = self.build()
        k = RepositoryRefAuthorityLookupKey(REPO, BRANCH, HEAD, MASTER, MISSION, "leaf-grant").validate()
        record = RepositoryRefAuthorityLineageRecord(
            k, lineage, canonical_source_lineage_digest(lineage), "control-plane:repo-delete:lineage"
        ).validate()
        with tempfile.TemporaryDirectory() as td:
            state = SQLiteAuthorityStateStore(str(Path(td) / "state.sqlite"))
            context_key = (DOMAIN, TENANT, ORG, MISSION)
            state.bootstrap_context(context_key, epoch=9)
            state.register_root(
                context_key, epoch=9, root_grant_id=lineage[0].grant_id,
                root_grant_digest=lineage[0].digest(),
            )
            admission = LiveAuthorityAdmission(
                authority_source=StaticSource(record),
                context=AuthorityVerificationContext(DOMAIN, TENANT, ORG, MISSION),
                issuer_keys=(
                    IssuerKeyBinding(ROOT_ISSUER, DOMAIN, "root-key", "TEST-ALG"),
                    IssuerKeyBinding(DELEGATOR, DOMAIN, "leaf-key", "TEST-ALG"),
                ),
                signature_verifier=verifier,
                epoch_provider=PersistentEpochStateProvider(state),
                root_provider=PersistentRootAnchorProvider(state),
                replay_guard=DurableReplayGuard(state, domain="repo-ref-live-test"),
                binding_finalizer=PersistentBindingFinalizer(state),
            )
            admitted = admission.admit_repository_ref(
                key=k, now=datetime.fromisoformat(NOW), replay_nonce="nonce-1"
            )
            self.assertEqual(admitted.branch, BRANCH)
            self.assertEqual(admitted.protected_master_sha, MASTER)
            self.assertEqual(admitted.lineage_digest, record.lineage_digest)
            self.assertIs(admission.revalidate_repository_ref(admitted, now=datetime.fromisoformat(NOW)), admitted)
            with self.assertRaises(Exception):
                admission.admit_repository_ref(key=k, now=datetime.fromisoformat(NOW), replay_nonce="nonce-1")

    def test_trusted_control_plane_store_separates_pr_and_repository_ref_namespaces(self):
        tx, _, lineage = self.build()
        k = RepositoryRefAuthorityLookupKey(REPO, BRANCH, HEAD, MASTER, MISSION, "leaf-grant").validate()
        record = RepositoryRefAuthorityLineageRecord(
            k, lineage, canonical_source_lineage_digest(lineage), "control-plane:repo-delete:lineage"
        ).validate()
        with tempfile.TemporaryDirectory() as td:
            store = SQLiteTrustedControlPlaneStore(str(Path(td) / "control.sqlite"))
            store.put_repository_ref_authority_record(raw_record(record))
            rows = store.lookup_repository_ref_authority_exact(
                repository=REPO, branch=BRANCH, expected_head=HEAD,
                protected_master_sha=MASTER, mission_id=MISSION, grant_id="leaf-grant",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                store.lookup_authority_exact(
                    repository=REPO, pr_number=216, base_sha=HEAD, head_sha=HEAD,
                    mission_id=MISSION, grant_id="leaf-grant",
                ),
                (),
            )

    def test_provisioning_has_no_signing_secret_network_or_effect_surface(self):
        import cyber_lion.enterprise.authority_provisioning as module
        source = inspect.getsource(module)
        for forbidden in (
            "private_key", "PRIVATE KEY", "os.environ", "importlib", "urllib.request",
            "requests.", "subprocess.", "git push", "github.",
        ):
            self.assertNotIn(forbidden, source)
        inventory = EffectSurfaceScanner().scan(
            repository=REPO,
            revision="a" * 40,
            tree_digest="b" * 40,
            sources={"cyber_lion/enterprise/authority_provisioning.py": source},
        )
        self.assertEqual(len(inventory.unclassified_refs), 0)
        self.assertTrue(inventory.surfaces)
        self.assertTrue(all(s.effect_class == "persistent_state.write" for s in inventory.surfaces))
        self.assertTrue(all(s.target_class == "runtime" for s in inventory.surfaces))


if __name__ == "__main__":
    unittest.main()
