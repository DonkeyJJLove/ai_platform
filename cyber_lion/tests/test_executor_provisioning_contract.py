from __future__ import annotations

from dataclasses import fields, replace
import unittest

from cyber_lion.contracts.executor_provisioning import (
    CredentialHandle,
    ExecutorProvisioningContractError,
    ExecutorProvisioningRequest,
    ProviderTrustBinding,
    ProvisionedExecutor,
    ProvisioningMaterialization,
)

REPO = "DonkeyJJLove/ai_platform"
BASE = "1" * 40
TREE = "2" * 40
IMAGE = "a" * 64
SANDBOX = "b" * 64
RESOURCE = "c" * 64
IMPLEMENTATION = "d" * 64
ANCHOR = "e" * 64
ATTESTATION = "f" * 64


def handle(handle_id: str = "cred-gh-read") -> CredentialHandle:
    return CredentialHandle(handle_id, "broker-1", "repository-read")


def request(**overrides) -> ExecutorProvisioningRequest:
    values = dict(
        schema_version="1.0.0",
        request_id="provision-f005-d-001",
        idempotency_key="f005-d:executor-001",
        drone_id="drone-f005-d-001",
        executor_id="executor-f005-d-001",
        mission_id="F005-D-EXECUTOR-PROVISIONING-BUILD",
        parent_mission_id="F005",
        repository=REPO,
        baseline_sha=BASE,
        baseline_tree_sha=TREE,
        branch="mission/f005-d-executor-provisioning",
        read_scope=("cyber_lion",),
        write_scope=("cyber_lion/contracts/executor_provisioning.py",),
        runtime_class="python-3.11-linux",
        image_digest=IMAGE,
        sandbox_profile_digest=SANDBOX,
        resource_profile_digest=RESOURCE,
        credential_handles=(handle(),),
        requested_at="2026-08-21T13:50:00+00:00",
    )
    values.update(overrides)
    return ExecutorProvisioningRequest(**values)


def trust(**overrides) -> ProviderTrustBinding:
    values = dict(
        provider_id="executor-provider",
        provider_instance_id="provider-eu-1",
        implementation_digest=IMPLEMENTATION,
        trust_anchor_id="executor-provider-root",
        trust_anchor_digest=ANCHOR,
    )
    values.update(overrides)
    return ProviderTrustBinding(**values)


def materialization(req: ExecutorProvisioningRequest | None = None, **overrides) -> ProvisioningMaterialization:
    req = req or request()
    values = dict(
        request_digest=req.digest(),
        provider_id="executor-provider",
        provider_instance_id="provider-eu-1",
        runtime_instance_id="runtime-001",
        sandbox_id="sandbox-001",
        workspace_id="workspace-001",
        runtime_class=req.runtime_class,
        image_digest=req.image_digest,
        sandbox_profile_digest=req.sandbox_profile_digest,
        resource_profile_digest=req.resource_profile_digest,
        repository=req.repository,
        baseline_sha=req.baseline_sha,
        baseline_tree_sha=req.baseline_tree_sha,
        branch=req.branch,
        read_scope=req.read_scope,
        write_scope=req.write_scope,
        credential_handle_ids=req.credential_handle_ids(),
        state="READY",
        runtime_attestation_digest=ATTESTATION,
        evidence_ref="provider:evidence:001",
        failure_code=None,
        observed_at="2026-08-21T13:51:00+00:00",
    )
    values.update(overrides)
    return ProvisioningMaterialization(**values)


def receipt(req: ExecutorProvisioningRequest | None = None, **overrides) -> ProvisionedExecutor:
    req = req or request()
    binding = trust()
    values = dict(
        schema_version="1.0.0",
        receipt_id="executor-provisioning:receipt-001",
        request_id=req.request_id,
        request_digest=req.digest(),
        idempotency_key=req.idempotency_key,
        drone_id=req.drone_id,
        executor_id=req.executor_id,
        runtime_instance_id="runtime-001",
        sandbox_id="sandbox-001",
        workspace_id="workspace-001",
        mission_id=req.mission_id,
        parent_mission_id=req.parent_mission_id,
        repository=req.repository,
        baseline_sha=req.baseline_sha,
        baseline_tree_sha=req.baseline_tree_sha,
        branch=req.branch,
        read_scope=req.read_scope,
        write_scope=req.write_scope,
        runtime_class=req.runtime_class,
        image_digest=req.image_digest,
        sandbox_profile_digest=req.sandbox_profile_digest,
        resource_profile_digest=req.resource_profile_digest,
        credential_handle_ids=req.credential_handle_ids(),
        provider_id=binding.provider_id,
        provider_instance_id=binding.provider_instance_id,
        provider_implementation_digest=binding.implementation_digest,
        provider_trust_anchor_id=binding.trust_anchor_id,
        provider_trust_anchor_digest=binding.trust_anchor_digest,
        runtime_attestation_digest=ATTESTATION,
        provider_evidence_ref="provider:evidence:001",
        provisioned_at="2026-08-21T13:51:00+00:00",
    )
    values.update(overrides)
    return ProvisionedExecutor(**values)


class ExecutorProvisioningContractTests(unittest.TestCase):
    def test_request_is_deterministic_and_valid(self):
        first = request()
        second = request()
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(len(first.digest()), 64)
        self.assertEqual(first.credential_handle_ids(), ("cred-gh-read",))

    def test_request_requires_exact_schema_and_lowercase_full_git_ids(self):
        with self.assertRaises(ExecutorProvisioningContractError):
            request(schema_version="2.0.0").validate()
        with self.assertRaises(ExecutorProvisioningContractError):
            request(baseline_sha="A" * 40).validate()
        with self.assertRaises(ExecutorProvisioningContractError):
            request(baseline_tree_sha="2" * 39).validate()

    def test_request_rejects_unsafe_branch_and_scope(self):
        for branch in ("refs/heads/x", "../master", "feature//x", "feature x", "x.lock"):
            with self.subTest(branch=branch):
                with self.assertRaises(ExecutorProvisioningContractError):
                    request(branch=branch).validate()
        for scope in (("../secret",), ("/absolute",), ("cyber_lion\\x",)):
            with self.subTest(scope=scope):
                with self.assertRaises(ExecutorProvisioningContractError):
                    request(write_scope=scope).validate()

    def test_scopes_and_credentials_are_exact_tuples(self):
        with self.assertRaises(ExecutorProvisioningContractError):
            request(read_scope=["cyber_lion"]).validate()  # type: ignore[arg-type]
        with self.assertRaises(ExecutorProvisioningContractError):
            request(write_scope=()).validate()
        duplicate = (handle(), handle())
        with self.assertRaises(ExecutorProvisioningContractError):
            request(credential_handles=duplicate).validate()

    def test_credential_handle_has_no_material_field(self):
        names = {item.name.lower() for item in fields(CredentialHandle)}
        self.assertEqual(names, {"handle_id", "broker_id", "purpose"})
        forbidden = {"token", "password", "secret", "private_key", "credential_material"}
        self.assertTrue(names.isdisjoint(forbidden))

    def test_request_and_receipt_are_not_authority_grants(self):
        request_fields = {item.name for item in fields(ExecutorProvisioningRequest)}
        receipt_fields = {item.name for item in fields(ProvisionedExecutor)}
        forbidden = {
            "authority_grant", "grant_id", "authority_ceiling", "merge_authority",
            "signature", "access_token", "password", "secret", "private_key",
        }
        self.assertTrue(request_fields.isdisjoint(forbidden))
        self.assertTrue(receipt_fields.isdisjoint(forbidden))

    def test_ready_materialization_requires_attestation_and_no_failure(self):
        materialization().validate()
        with self.assertRaises(ExecutorProvisioningContractError):
            materialization(runtime_attestation_digest=None).validate()
        with self.assertRaises(ExecutorProvisioningContractError):
            materialization(failure_code="unexpected").validate()

    def test_failed_materialization_requires_failure_code(self):
        failed = materialization(state="FAILED", runtime_attestation_digest=None, failure_code="NO_CAPACITY")
        failed.validate()
        with self.assertRaises(ExecutorProvisioningContractError):
            replace(failed, failure_code=None).validate()

    def test_receipt_binds_exact_request_and_provider(self):
        req = request()
        value = receipt(req)
        self.assertIs(value.validate_for(req, trust()), value)
        self.assertEqual(len(value.digest()), 64)
        with self.assertRaises(ExecutorProvisioningContractError):
            replace(value, branch="mission/other").validate_for(req, trust())
        with self.assertRaises(ExecutorProvisioningContractError):
            value.validate_for(req, trust(implementation_digest="9" * 64))

    def test_provider_trust_binding_rejects_weak_digests(self):
        with self.assertRaises(ExecutorProvisioningContractError):
            trust(implementation_digest="d" * 63).validate()
        with self.assertRaises(ExecutorProvisioningContractError):
            trust(trust_anchor_digest="E" * 64).validate()

    def test_naive_timestamps_are_rejected(self):
        with self.assertRaises(ExecutorProvisioningContractError):
            request(requested_at="2026-08-21T13:50:00").validate()
        with self.assertRaises(ExecutorProvisioningContractError):
            materialization(observed_at="2026-08-21T13:51:00").validate()


if __name__ == "__main__":
    unittest.main()
