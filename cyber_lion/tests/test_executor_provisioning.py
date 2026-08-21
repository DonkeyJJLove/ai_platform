from __future__ import annotations

from dataclasses import replace
import inspect
import unittest

from cyber_lion.contracts.executor_provisioning import (
    CredentialHandle,
    ExecutorProvisioningRequest,
    ProviderTrustBinding,
    ProvisioningMaterialization,
)
from cyber_lion.enterprise.executor_provisioning import (
    ExecutorProvisioner,
    ExecutorProvisioningError,
    ExecutorProvisioningLedger,
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


def request(slot: str = "1", **overrides) -> ExecutorProvisioningRequest:
    values = dict(
        schema_version="1.0.0",
        request_id=f"provision-{slot}",
        idempotency_key=f"idem-{slot}",
        drone_id=f"drone-{slot}",
        executor_id=f"executor-{slot}",
        mission_id=f"mission-{slot}",
        parent_mission_id="F005",
        repository=REPO,
        baseline_sha=BASE,
        baseline_tree_sha=TREE,
        branch=f"mission/f005-d-{slot}",
        read_scope=("cyber_lion",),
        write_scope=(f"cyber_lion/generated-{slot}.py",),
        runtime_class="python-3.11-linux",
        image_digest=IMAGE,
        sandbox_profile_digest=SANDBOX,
        resource_profile_digest=RESOURCE,
        credential_handles=(CredentialHandle(f"cred-{slot}", "broker-1", "repository-read"),),
        requested_at="2026-08-21T13:50:00+00:00",
    )
    values.update(overrides)
    return ExecutorProvisioningRequest(**values)


def trust(**overrides) -> ProviderTrustBinding:
    values = dict(
        provider_id="executor-provider",
        provider_instance_id="provider-eu-1",
        implementation_digest=IMPLEMENTATION,
        trust_anchor_id="provider-root",
        trust_anchor_digest=ANCHOR,
    )
    values.update(overrides)
    return ProviderTrustBinding(**values)


def ready(req: ExecutorProvisioningRequest, *, slot: str | None = None, **overrides) -> ProvisioningMaterialization:
    suffix = slot or req.executor_id.rsplit("-", 1)[-1]
    values = dict(
        request_digest=req.digest(),
        provider_id="executor-provider",
        provider_instance_id="provider-eu-1",
        runtime_instance_id=f"runtime-{suffix}",
        sandbox_id=f"sandbox-{suffix}",
        workspace_id=f"workspace-{suffix}",
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
        evidence_ref=f"provider:evidence:{suffix}",
        failure_code=None,
        observed_at="2026-08-21T13:51:00+00:00",
    )
    values.update(overrides)
    return ProvisioningMaterialization(**values)


class FakeProvider:
    provider_id = "executor-provider"
    provider_instance_id = "provider-eu-1"
    implementation_digest = IMPLEMENTATION

    def __init__(self, callback=None):
        self.callback = callback
        self.calls = 0
        self.seen = []

    def provision(self, req):
        self.calls += 1
        self.seen.append(req)
        if self.callback is not None:
            return self.callback(req, self.calls)
        return ready(req)


class ExecutorProvisioningTests(unittest.TestCase):
    def make_subject(self, provider=None, ledger=None):
        provider = provider or FakeProvider()
        return ExecutorProvisioner(provider=provider, trust=trust(), ledger=ledger), provider

    def test_successful_provisioning_binds_exact_context(self):
        subject, provider = self.make_subject()
        req = request()
        result = subject.provision(req)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result.request_digest, req.digest())
        self.assertEqual(result.executor_id, req.executor_id)
        self.assertEqual(result.runtime_instance_id, "runtime-1")
        self.assertEqual(result.sandbox_id, "sandbox-1")
        self.assertEqual(result.write_scope, req.write_scope)
        self.assertEqual(result.credential_handle_ids, ("cred-1",))
        self.assertEqual(result.provider_implementation_digest, IMPLEMENTATION)
        self.assertEqual(result.provider_trust_anchor_digest, ANCHOR)
        self.assertEqual(len(result.digest()), 64)
        self.assertIs(subject.lookup(req), result)

    def test_replay_is_idempotent_and_does_not_call_provider_twice(self):
        subject, provider = self.make_subject()
        req = request()
        first = subject.provision(req)
        second = subject.provision(req)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(first.digest(), second.digest())

    def test_same_idempotency_key_cannot_change_request(self):
        subject, provider = self.make_subject()
        subject.provision(request("1"))
        divergent = request("2", idempotency_key="idem-1")
        with self.assertRaises(ExecutorProvisioningError):
            subject.provision(divergent)
        self.assertEqual(provider.calls, 1)

    def test_same_executor_or_drone_cannot_be_rebound(self):
        for field_name, value in (("executor_id", "executor-1"), ("drone_id", "drone-1")):
            with self.subTest(field=field_name):
                subject, provider = self.make_subject()
                subject.provision(request("1"))
                with self.assertRaises(ExecutorProvisioningError):
                    subject.provision(request("2", **{field_name: value}))
                self.assertEqual(provider.calls, 1)

    def test_provider_identity_is_pinned_at_composition_root(self):
        provider = FakeProvider()
        provider.provider_instance_id = "rogue-provider"
        with self.assertRaises(ExecutorProvisioningError):
            ExecutorProvisioner(provider=provider, trust=trust())

    def test_provider_request_digest_mismatch_fails_closed_and_can_retry(self):
        state = {"bad": True}

        def callback(req, _calls):
            if state["bad"]:
                return ready(req, request_digest="0" * 64)
            return ready(req)

        provider = FakeProvider(callback)
        subject, _ = self.make_subject(provider)
        req = request()
        with self.assertRaises(ExecutorProvisioningError):
            subject.provision(req)
        self.assertIsNone(subject.lookup(req))
        state["bad"] = False
        result = subject.provision(req)
        self.assertEqual(result.runtime_instance_id, "runtime-1")
        self.assertEqual(provider.calls, 2)

    def test_provider_cannot_widen_scope_or_change_branch_image_or_profiles(self):
        mutations = (
            {"write_scope": ("cyber_lion",)},
            {"branch": "mission/other"},
            {"image_digest": "9" * 64},
            {"sandbox_profile_digest": "8" * 64},
            {"resource_profile_digest": "7" * 64},
            {"credential_handle_ids": ("cred-1", "extra-handle")},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                provider = FakeProvider(lambda req, _calls, mutation=mutation: ready(req, **mutation))
                subject, _ = self.make_subject(provider)
                with self.assertRaises(ExecutorProvisioningError):
                    subject.provision(request())

    def test_failed_provider_materialization_does_not_commit(self):
        state = {"failed": True}

        def callback(req, _calls):
            if state["failed"]:
                return ready(
                    req,
                    state="FAILED",
                    runtime_attestation_digest=None,
                    failure_code="NO_CAPACITY",
                )
            return ready(req)

        provider = FakeProvider(callback)
        subject, _ = self.make_subject(provider)
        req = request()
        with self.assertRaises(ExecutorProvisioningError):
            subject.provision(req)
        self.assertIsNone(subject.lookup(req))
        state["failed"] = False
        self.assertEqual(subject.provision(req).executor_id, "executor-1")

    def test_provider_exception_releases_request_reservation(self):
        state = {"boom": True}

        def callback(req, _calls):
            if state["boom"]:
                raise RuntimeError("provider unavailable")
            return ready(req)

        provider = FakeProvider(callback)
        subject, _ = self.make_subject(provider)
        req = request()
        with self.assertRaises(ExecutorProvisioningError):
            subject.provision(req)
        state["boom"] = False
        self.assertEqual(subject.provision(req).runtime_instance_id, "runtime-1")

    def test_runtime_sandbox_and_workspace_reuse_are_denied(self):
        for field_name in ("runtime_instance_id", "sandbox_id", "workspace_id"):
            with self.subTest(field=field_name):
                def normalized(req, calls, field_name=field_name):
                    value = ready(req)
                    if req.executor_id != "executor-2":
                        return value
                    duplicate = {
                        "runtime_instance_id": "runtime-1",
                        "sandbox_id": "sandbox-1",
                        "workspace_id": "workspace-1",
                    }[field_name]
                    return replace(value, **{field_name: duplicate})

                provider = FakeProvider(normalized)
                subject, _ = self.make_subject(provider)
                subject.provision(request("1"))
                with self.assertRaises(ExecutorProvisioningError):
                    subject.provision(request("2"))

    def test_duplicate_runtime_failure_does_not_poison_other_unique_retry(self):
        state = {"duplicate": True}

        def callback(req, _calls):
            value = ready(req)
            if req.executor_id == "executor-2" and state["duplicate"]:
                return replace(value, runtime_instance_id="runtime-1")
            return value

        provider = FakeProvider(callback)
        subject, _ = self.make_subject(provider)
        subject.provision(request("1"))
        with self.assertRaises(ExecutorProvisioningError):
            subject.provision(request("2"))
        state["duplicate"] = False
        result = subject.provision(request("2"))
        self.assertEqual(result.runtime_instance_id, "runtime-2")

    def test_provider_evidence_cannot_predate_request(self):
        provider = FakeProvider(lambda req, _calls: ready(req, observed_at="2026-08-21T13:49:59+00:00"))
        subject, _ = self.make_subject(provider)
        with self.assertRaises(ExecutorProvisioningError):
            subject.provision(request())

    def test_in_progress_duplicate_fails_closed(self):
        ledger = ExecutorProvisioningLedger()
        req = request()
        self.assertIsNone(ledger.begin(req))
        with self.assertRaises(ExecutorProvisioningError):
            ledger.begin(req)
        ledger.abort(req)
        self.assertIsNone(ledger.begin(req))
        ledger.abort(req)

    def test_provider_sees_no_authority_or_credential_material(self):
        subject, provider = self.make_subject()
        subject.provision(request())
        seen = provider.seen[0]
        parameter_names = set(inspect.signature(ExecutorProvisioner.provision).parameters)
        self.assertEqual(parameter_names, {"self", "request"})
        self.assertFalse(hasattr(seen, "grant_id"))
        self.assertFalse(hasattr(seen, "authority_ceiling"))
        self.assertFalse(hasattr(seen, "token"))
        self.assertFalse(hasattr(seen, "password"))
        self.assertEqual(seen.credential_handles[0].handle_id, "cred-1")


if __name__ == "__main__":
    unittest.main()
