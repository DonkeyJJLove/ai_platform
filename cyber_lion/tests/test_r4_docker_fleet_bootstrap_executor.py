from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import copy
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.contracts.runtime_enforcement import (
    RequestedRuntimeEffect, RuntimeIdentityBinding, RuntimeAdmission,
)
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.live_authority_admission import (
    LiveAdmittedAuthority, LiveAuthorityAdmission,
)
from cyber_lion.enterprise.runtime_execution import (
    SQLiteRuntimeAdmissionSource, SQLiteAdmissionConsumptionGuard,
)
from cyber_lion.mission_control.docker_local_fleet_plan import deterministic_fleet_plan
from cyber_lion.mission_control.docker_fleet_bootstrap_executor import (
    ACTION, EXECUTOR_ID, RESOURCE, DockerFleetBootstrapError,
    DockerFleetBootstrapExecutor, MoonDockerComposeRuntime,
)


def filled(char):
    return char * 64


def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


class RuntimeFixture:
    def __init__(self, plan, compose):
        self.plan = plan
        self.compose = compose
        self.inventory = []
        self.started = 0
        self.saved = []
        self.fail_launch = False
        self.identity = {
            "schema": "lion.material-worker-source-identity/v1",
            "source_head": plan["source_head"],
            "source_tree": plan["source_tree"],
            "identity_digest": filled("3"),
            "compose_sha256": filled("4"),
        }
        self.receipt = {
            **self.identity,
            "schema": "lion.r24-material-fleet-materialization/v1",
        }

    def compose_config(self):
        return self.compose

    def identity_and_receipt(self):
        return self.identity, self.receipt

    def runtime_attestation(self):
        return {
            "schema": "lion.r24-docker-fleet-attestation/v1",
            "host": "MOON", "docker_engine": "docker-desktop",
            "image_id": "sha256:" + "d" * 64,
            "source_head": self.plan["source_head"],
            "source_tree": self.plan["source_tree"],
            "compose_sha256": filled("4"),
            "worker_source_sha256": filled("e"),
            "runtime_contract_sha256": filled("f"),
        }

    def container_inventory(self):
        return copy.deepcopy(self.inventory)

    def start_exact_compose(self):
        self.started += 1
        if self.fail_launch:
            raise RuntimeError("simulated transport loss after effect")

    def observe_currentness(self):
        workers = [
            {
                "material_worker_id": row["material_worker_id"],
                "container_name": row["container_name"],
                "container_id": "source-bound-id-" + row["material_worker_id"],
                "ready": True,
                "worker_profile": "LION_MATERIAL_EXECUTOR_V2",
            }
            for row in self.plan["workers"]
        ]
        d = {
            "schema": "lion.docker-local-model-fleet-currentness/v1",
            "physical_host": "MOON", "state": "READY",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "materialized": 32, "ready": 32,
            "source_head": self.plan["source_head"],
            "source_tree": self.plan["source_tree"],
            "worker_profile": "LION_MATERIAL_EXECUTOR_V2",
            "workers": workers,
        }
        d["currentness_digest"] = sha256(canonical(d)).hexdigest()
        return d

    def persist_receipt(self, value):
        self.saved.append(copy.deepcopy(value))
        return sha256(canonical(value) + b"\n").hexdigest()


class BoundedDockerBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.source = (
            "PROJECT=LION_EVOLUSION\n"
            "MODE=AUTONOMOUS_EXECUTE\n"
            "CONTROL_LANGUAGE=LPCL/1.2\n"
            "MISSION_ID=LION-TEST-8L32M\n"
            "LOGICAL_DRONE_COUNT=8\n"
            "MATERIAL_DRONE_COUNT=32\n"
            "MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL\n"
            "PHASE_01=PREPARE|Controlled bootstrap\n"
        )
        self.mission = {
            "mission_id": "LION-TEST-8L32M",
            "source_head": "a" * 40, "source_tree": "b" * 40,
            "spec_digest": sha256(self.source.encode("utf-8")).hexdigest(),
            "state": "AUTHORIZED", "adapter": "LPCL_MISSION",
            "logical_count": 8, "material_target": 32,
            "process": {
                "authority_state": "EXPLICIT_USER_ACTIVATION",
                "lpcl_text": self.source,
            },
            "operator_control": {"autonomy_allowed": True},
        }
        self.compose = {"services": {
            f"worker-{i:02d}": {
                "container_name": f"lion-r24-md{i:03d}", "read_only": True,
                "labels": {
                    "LION_WORKER_PROFILE": "LION_MATERIAL_EXECUTOR_V2",
                    "LION_MATERIAL_WORKER_ID": f"MD{i:03d}",
                },
            }
            for i in range(1, 33)
        }}
        self.plan = deterministic_fleet_plan(self.mission, self.compose)
        self.runtime = RuntimeFixture(self.plan, self.compose)
        attestation_digest = sha256(canonical(self.runtime.runtime_attestation())).hexdigest()
        self.identity = RuntimeIdentityBinding(
            workload_identity=EXECUTOR_ID, execution_subject=EXECUTOR_ID,
            runtime_instance_id="MOON_DOCKER_DESKTOP_R24",
            sandbox_id="LION_R24_MATERIAL_SANDBOX",
            workspace_id="/srv/lion-e4-candidate-r1/r20-mission/r24-autonomy",
            runtime_attestation_digest=attestation_digest,
            provisioned_executor_digest=filled("6"),
        )
        self.live = LiveAdmittedAuthority(
            repository="DonkeyJJLove/ai_platform", pr_number=999,
            base_sha="a"*40, head_sha="b"*40,
            mission_id=self.plan["mission_id"],
            grant_id="test-grant", lineage_digest=filled("7"),
            provenance_id="test-provenance", epoch=1,
            epoch_state_version=1, authority_ceiling="bounded_material",
            root_grant_id="test-root", root_grant_digest=filled("8"),
            authenticated_grant_digests=(filled("9"),),
            leaf_key_id="test-key", leaf_algorithm="ed25519",
            replay_digest=filled("0"),
            admitted_at=datetime.now(timezone.utc).isoformat(),
        ).validate()
        self.effect = RequestedRuntimeEffect(
            effect_id="docker-effect-001",
            proposal_id="operator-lpcl-effect-001",
            mission_id=self.plan["mission_id"],
            policy_binding="operator-scope",
            authority_lineage_digest=self.live.lineage_digest,
            requested_authority="bounded_material",
            action_class=ACTION, resource=RESOURCE,
            payload_digest=self.plan["plan_digest"],
            observability_state="HEALTHY",
            runtime_identity_digest=self.identity.digest(),
        ).validate()
        self.admission = RuntimeAdmission(
            admission_id="issued-by-original-runtime-engine",
            request_id="control-001", gate_event_id="gate-event-001",
            proposal_id=self.effect.proposal_id,
            gate_decision_digest=filled("a"),
            pdp_receipt_digest=filled("b"),
            pdp_evidence_digest=filled("c"),
            live_authority_digest=self.live.digest(),
            authority_lineage_digest=self.live.lineage_digest,
            policy_binding=self.effect.policy_binding,
            effective_authority=self.effect.requested_authority,
            requested_effect_digest=self.effect.digest(),
            runtime_identity_digest=self.identity.digest(),
            provisioned_executor_digest=self.identity.provisioned_executor_digest,
            observability_state=self.effect.observability_state,
            replay_key=filled("d"),
        ).sealed()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trust = RuntimeAdmissionSourceTrustBinding(
            source_id="original-published-runtime-admissions",
            source_instance_id="test-source-1",
            source_implementation_digest=filled("1"),
            trust_anchor_id="trusted-owner",
            trust_anchor_digest=filled("2"),
        )
        root = Path(self.tmp.name)
        self.source_f = SQLiteRuntimeAdmissionSource(root / "admissions.db", self.trust)
        self.source_f.publish(
            self.admission, provenance_digest=filled("f"),
            published_at=datetime.now(timezone.utc),
        )
        self.guard = SQLiteAdmissionConsumptionGuard(root / "consumption.db")
        # The test replaces ONLY the live authority lookup. RuntimeAdmission
        # is a synthetic fixture, not a real permission for Docker.
        self.verifier = object.__new__(LiveAuthorityAdmission)
        self.executor = DockerFleetBootstrapExecutor(
            admission_source=self.source_f, admission_source_trust=self.trust,
            consumption_guard=self.guard,
            mission_source=lambda _: self.mission, fleet_runtime=self.runtime,
            authority_verifier=self.verifier,
        )

    def guard_count(self):
        with sqlite3.connect(self.guard.path) as conn:
            return conn.execute("SELECT COUNT(*) FROM runtime_admission_consumption").fetchone()[0]

    def execute(self, **replacements):
        kwargs = dict(plan=self.plan, admission=self.admission,
                      effect=self.effect, runtime_identity=self.identity,
                      admitted_authority=self.live,
                      execution_id="e2e-test-1")
        kwargs.update(replacements)
        with patch.object(LiveAuthorityAdmission, "revalidate",
                          return_value=self.live):
            return self.executor.execute(**kwargs)

    def test_one_admission_starts_one_prepared_absent_fleet(self):
        result = self.execute()
        self.assertEqual(result["result"], "OBSERVED")
        self.assertEqual(self.runtime.started, 1)
        self.assertEqual(len(self.runtime.saved), 1)
        self.assertEqual(result["source_head"], self.plan["source_head"])
        self.assertFalse(result["retries_permitted"])
        self.assertEqual(self.guard_count(), 1)

    def test_second_execution_is_denied_before_second_start(self):
        self.execute()
        with self.assertRaisesRegex(DockerFleetBootstrapError,
                                    "DUPLICATE_DOCKER_BOOTSTRAP_ADMISSION"):
            self.execute(execution_id="second-execution")
        self.assertEqual(self.runtime.started, 1)

    def test_effect_failure_is_unknown_not_retryable(self):
        self.runtime.fail_launch = True
        result = self.execute()
        self.assertEqual(result["result"], "EFFECT_UNKNOWN_RECONCILE")
        self.assertEqual(result["reported_error_class"], "RuntimeError")
        self.assertEqual(self.guard_count(), 1)
        with self.assertRaisesRegex(DockerFleetBootstrapError, "DUPLICATE"):
            self.execute(execution_id="retry")
        self.assertEqual(self.runtime.started, 1)

    def test_wrong_mission_activation_blocks_before_admission_consumption(self):
        self.mission["state"] = "REGISTERED"
        with self.assertRaisesRegex(DockerFleetBootstrapError,
                                    "EXPLICIT_OPERATOR_LPCL_ACTIVATION_REQUIRED"):
            self.execute()
        self.assertEqual(self.runtime.started, 0)
        self.assertEqual(self.guard_count(), 0)

    def test_stale_admission_and_wrong_effect_are_denied(self):
        with patch.object(SQLiteRuntimeAdmissionSource, "is_current", return_value=False):
            with self.assertRaisesRegex(DockerFleetBootstrapError,
                                        "STALE_OR_SUBSTITUTED_ADMISSION"):
                self.execute()
        changed = copy.copy(self.effect)
        object.__setattr__(changed, "resource", "docker://MOON/untrusted")
        with self.assertRaisesRegex(DockerFleetBootstrapError,
                                    "EFFECT_CLASS_OR_RESOURCE_DENIED"):
            self.execute(effect=changed)
        self.assertEqual(self.runtime.started, 0)

    def test_identity_substitution_is_denied(self):
        altered = copy.copy(self.identity)
        object.__setattr__(altered, "execution_subject", "MODEL_ASSISTANT")
        with self.assertRaisesRegex(DockerFleetBootstrapError,
                                    "FLEET_EFFECT_IDENTITY_DRIFT"):
            self.execute(runtime_identity=altered)
        self.assertEqual(self.runtime.started, 0)

    def test_historical_stopped_cohort_source_drift_blocks_launch(self):
        self.runtime.inventory = [{
            "name": f"/lion-r24-md{i:03d}", "container_id": f"cid-{i}",
            "state": "exited",
            "labels": {
                "LION_MATERIAL_WORKER_ID": f"MD{i:03d}",
                "LION_WORKER_PROFILE": "LION_MATERIAL_EXECUTOR_V2",
                "com.docker.compose.project": "lion-r24-autonomy",
            }
        } for i in range(1, 33)]
        self.runtime.receipt["source_head"] = "f" * 40
        with self.assertRaisesRegex(DockerFleetBootstrapError,
                                    "DOCKER_PRE_EFFECT_BLOCKED"):
            self.execute()
        self.assertEqual(self.runtime.started, 0)
        self.assertEqual(self.guard_count(), 0)

    def test_prepared_runtime_source_drift_blocks_absent_fleet(self):
        self.runtime.identity["source_tree"] = "f"*40
        with self.assertRaisesRegex(DockerFleetBootstrapError,
                                    "MATERIALIZED_RUNTIME_NOT_FOR_THIS_SOURCE"):
            self.execute()
        self.assertEqual(self.guard_count(), 0)

    def test_running_ready_fleet_returns_readonly_reconciliation(self):
        self.runtime.inventory = [{
            "name": f"/lion-r24-md{i:03d}", "container_id": f"cid-{i}",
            "state": "running",
            "labels": {
                "LION_MATERIAL_WORKER_ID": f"MD{i:03d}",
                "LION_WORKER_PROFILE": "LION_MATERIAL_EXECUTOR_V2",
                "com.docker.compose.project": "lion-r24-autonomy",
            }
        } for i in range(1, 33)]
        result = self.execute()
        self.assertEqual(result["result"], "ALREADY_SOURCE_BOUND_READY")
        self.assertFalse(result["effect_applied"])
        self.assertEqual(self.runtime.started, 0)
        self.assertEqual(self.guard_count(), 0)

    def test_live_authority_revalidation_failure_blocks_pre_effect(self):
        with patch.object(LiveAuthorityAdmission, "revalidate",
                          side_effect=RuntimeError("expired authority")):
            with self.assertRaisesRegex(DockerFleetBootstrapError,
                                        "LIVE_AUTHORITY_REVALIDATION_FAILED"):
                self.executor.execute(
                    plan=self.plan, admission=self.admission,
                    effect=self.effect, runtime_identity=self.identity,
                    admitted_authority=self.live, execution_id="e2e-test-1",
                )
        self.assertEqual(self.runtime.started, 0)
        self.assertEqual(self.guard_count(), 0)

    def test_image_attestation_drift_denied_before_effect(self):
        previous = self.runtime.runtime_attestation
        self.runtime.runtime_attestation = lambda: {
            **previous(), "image_id": "sha256:" + "0" * 64,
        }
        with self.assertRaisesRegex(DockerFleetBootstrapError,
                                    "DOCKER_IMAGE_AND_SOURCE_ATTESTATION_DRIFT"):
            self.execute()
        self.assertEqual(self.runtime.started, 0)
        self.assertEqual(self.guard_count(), 0)

    def test_readiness_poll_does_not_repeat_compose_up(self):
        probes = []
        original = self.runtime.observe_currentness
        def observe():
            probes.append(len(probes))
            if len(probes) == 1:
                return {"schema":"lion.docker-local-model-fleet-currentness/v1",
                        "physical_host":"MOON","workers":[]}
            return original()
        self.runtime.observe_currentness = observe
        self.executor.readiness_checks = 3
        self.executor.sleep = lambda _: None
        result = self.execute()
        self.assertEqual(result["result"], "OBSERVED")
        self.assertEqual(len(probes), 2)
        self.assertEqual(self.runtime.started, 1)

    def test_missing_fleet_readiness_is_unknown_not_success(self):
        self.runtime.observe_currentness = lambda: {
            "schema":"lion.docker-local-model-fleet-currentness/v1",
            "physical_host":"MOON","workers":[],
        }
        self.executor.readiness_checks = 2
        self.executor.sleep = lambda _: None
        result = self.execute()
        self.assertEqual(result["result"], "EFFECT_UNKNOWN_RECONCILE")
        self.assertEqual(result["reported_error_class"], "DockerFleetBootstrapError")
        self.assertEqual(self.runtime.started, 1)
        self.assertEqual(self.guard_count(), 1)
        self.assertEqual(len(self.runtime.saved), 1)

    def test_compose_security_scope_rejects_host_socket_or_privilege(self):
        root = "/srv/lion-e4-candidate-r1/r20-mission/r24-autonomy"
        ro = [
            "/src", "/runtime/worker.py", "/identity/current.json",
            "/cooperative-provider-artifact", "/cooperative-provider",
            "/cooperative-control", "/mission-control",
        ]
        rw = ["/status", "/gate", "/cooperative"]
        services = {}
        for i in range(1, 33):
            volumes = [
                {"type": "bind", "target": target,
                 "source": root + target, "read_only": True}
                for target in ro
            ]
            volumes += [
                {"type": "bind", "target": target,
                 "source": root + ("/private/MD%03d" % i if target == "/cooperative" else target)}
                for target in rw
            ]
            services[f"worker-{i:02d}"] = {
                "image": "lion-r20-worker:r1",
                "entrypoint": ["python3", "/runtime/worker.py"],
                "read_only": True, "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "pids_limit": 128, "mem_limit": "536870912",
                "cpus": 0.5, "volumes": volumes,
            }
        valid = {"services": services}
        MoonDockerComposeRuntime.validate_compose_security(valid)
        excessive = copy.deepcopy(valid)
        excessive["services"]["worker-02"]["cap_add"] = ["SYS_ADMIN"]
        with self.assertRaisesRegex(DockerFleetBootstrapError, "SECURITY_DRIFT"):
            MoonDockerComposeRuntime.validate_compose_security(excessive)
        excessive = copy.deepcopy(valid)
        excessive["services"]["worker-01"]["volumes"][-2]["source"] = "/var/run/docker.sock"
        with self.assertRaisesRegex(DockerFleetBootstrapError, "MOUNT_OUTSIDE_RUNTIME"):
            MoonDockerComposeRuntime.validate_compose_security(excessive)

    def test_docker_up_argv_is_fixed_and_no_shell(self):
        runtime = object.__new__(MoonDockerComposeRuntime)
        runtime.runtime = Path("/srv/lion-e4-candidate-r1/r20-mission/r24-autonomy")
        invoked = []
        runtime._run = lambda argv, **kwargs: invoked.append((argv, kwargs))
        runtime.start_exact_compose()
        self.assertEqual(len(invoked), 1)
        self.assertEqual(invoked[0][0][:5], [
            "docker", "compose", "-p", "lion-r24-autonomy", "-f",
        ])
        self.assertEqual(invoked[0][0][-3:],
                         ["up", "-d", "--no-recreate"])
        self.assertFalse(any(x in invoked[0][0] for x in ("sh", "-c", "--force-recreate")))


if __name__ == "__main__":
    unittest.main()
