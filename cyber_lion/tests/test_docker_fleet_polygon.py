from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import unittest

from cyber_lion.contracts.docker_fleet_polygon import (
    DockerDroneBinding,
    DockerFleetPlan,
    DockerFleetPolygonContractError,
    DroneRuntimeProfile,
    MissionCapsule,
    ObservedContainer,
)
from cyber_lion.drone_p0 import execute_capsule
from cyber_lion.enterprise.docker_fleet_polygon import (
    DockerFleetPolygonError,
    FleetResultAggregator,
    drone_run_argv,
    network_create_argv,
    observation_from_docker_inspect,
    reconcile,
)

D = lambda value: sha256(value.encode()).hexdigest()
HEAD = "1" * 40
TREE = "2" * 40
MISSION = "lion-local-swarm-p0"
FLEET = "lion-local-swarm-p0"
RUN = "run-p0-static"
ROLES = ("architecture", "security", "runtime", "provenance", "falsifier")
OPS = {
    "architecture": ("ARCHITECTURE_DIGEST", {"contracts": 7, "epoch": "1.4"}),
    "security": ("SECURITY_INVARIANTS", {"invariants": {"nonroot": True, "no_socket": True}}),
    "runtime": ("RUNTIME_BINDINGS", {"expected": {"generation": 1}, "observed": {"generation": 1}}),
    "provenance": (
        "PROVENANCE_RELATIONSHIPS",
        {"objects": {"source": {"sha": HEAD}, "plan": {"version": 1}}, "relationships": [{"source": "source", "target": "plan"}]},
    ),
    "falsifier": ("FALSIFY_CLAIM", {"claim": True, "evidence": False}),
}


def profile(**overrides):
    base = DroneRuntimeProfile("lion-drone-runtime-p0")
    return replace(base, **overrides)


def capsule(role: str, **overrides):
    op, payload = OPS[role]
    base = MissionCapsule.issue(
        mission_id=MISSION,
        fleet_id=FLEET,
        drone_id=f"drone-{role}",
        role=role,
        generation=1,
        work_unit_id=f"work-{role}",
        issued_at="2099-01-01T00:00:00Z",
        expires_at="2099-01-01T01:00:00Z",
        operation=op,
        input_payload=payload,
        policy_digest=D("policy"),
    )
    return replace(base, **overrides)


def binding(role: str, image_digest: str = D("image"), **overrides):
    c = capsule(role)
    base = DockerDroneBinding(
        drone_id=c.drone_id,
        role=role,
        generation=1,
        executor_id=f"executor-{role}",
        lease_id=D(f"lease-{role}"),
        container_name=f"lion-p0-{role}",
        image_digest=image_digest,
        capsule_digest=c.capsule_digest,
    )
    return replace(base, **overrides)


def plan(**overrides):
    image = D("image")
    base = DockerFleetPlan(
        mission_id=MISSION,
        fleet_id=FLEET,
        run_id=RUN,
        repository="DonkeyJJLove/ai_platform",
        source_head=HEAD,
        source_tree=TREE,
        network_name="lion-p0-run-p0-static-internal",
        image_reference="lion-drone-p0",
        image_digest=image,
        runtime_profile_digest=profile().digest(),
        drones=tuple(binding(role, image) for role in ROLES),
    )
    return replace(base, **overrides)


def expected_labels(p: DockerFleetPlan, d: DockerDroneBinding) -> dict[str, str]:
    return {
        "lion.project": "LION_EVOLUSION",
        "lion.architecture_epoch": "1.4",
        "lion.experiment_epoch": "LOCAL_SWARM_P0",
        "lion.mission_id": p.mission_id,
        "lion.fleet_id": p.fleet_id,
        "lion.run_id": p.run_id,
        "lion.resource_class": "drone",
        "lion.trust_class": "TEST_ONLY",
        "lion.plan_digest": p.digest(),
        "lion.drone_id": d.drone_id,
        "lion.role": d.role,
        "lion.generation": str(d.generation),
        "lion.executor_id": d.executor_id,
        "lion.lease_id": d.lease_id,
        "lion.capsule_digest": d.capsule_digest,
    }


def observed(p: DockerFleetPlan, d: DockerDroneBinding, **overrides):
    base = ObservedContainer(
        container_id=D(f"container-{d.drone_id}"),
        container_name=d.container_name,
        image_digest=p.image_digest,
        labels=expected_labels(p, d),
        user="65532:65532",
        read_only_rootfs=True,
        cap_drop=("ALL",),
        security_opt=("no-new-privileges",),
        pids_limit=64,
        memory_limit_bytes=134217728,
        nano_cpus=200_000_000,
        network_name=p.network_name,
        published_ports=(),
        docker_socket_mounted=False,
        exit_code=0,
        restart_count=0,
    )
    return replace(base, **overrides)


class DockerFleetPolygonTests(unittest.TestCase):
    def test_runtime_profile_is_fail_closed(self):
        profile().validate()
        for bad in (
            profile(uid=0),
            profile(read_only_rootfs=False),
            profile(no_new_privileges=False),
            profile(cap_drop=()),
            profile(runtime_shell=True),
            profile(package_manager=True),
            profile(persistent_state=True),
            profile(internet_egress=True),
        ):
            with self.assertRaises(DockerFleetPolygonContractError):
                bad.validate()

    def test_capsule_detects_mutation_and_binding_substitution(self):
        c = capsule("architecture")
        c.validate()
        with self.assertRaises(DockerFleetPolygonContractError):
            replace(c, input_payload={"contracts": 8, "epoch": "1.4"}).validate()
        with self.assertRaises(DockerFleetPolygonContractError):
            replace(c, mission_id="other-mission").validate()
        with self.assertRaises(DockerFleetPolygonContractError):
            replace(c, drone_id="drone-security").validate()

    def test_plan_requires_exact_five_role_complete_bound_drones(self):
        p = plan()
        p.validate()
        with self.assertRaises(DockerFleetPolygonContractError):
            replace(p, drones=p.drones[:-1]).validate()
        duplicate = (p.drones[0],) + p.drones[1:-1] + (replace(p.drones[0], container_name="other-name"),)
        with self.assertRaises(DockerFleetPolygonContractError):
            replace(p, drones=duplicate).validate()

    def test_network_is_internal_and_mission_labelled(self):
        argv = network_create_argv(plan())
        self.assertEqual(argv[:4], ("docker", "network", "create", "--internal"))
        text = " ".join(argv)
        self.assertIn("lion.project=LION_EVOLUSION", text)
        self.assertIn("lion.experiment_epoch=LOCAL_SWARM_P0", text)
        self.assertIn("lion.resource_class=fleet-network", text)

    def test_drone_argv_enforces_hardening_without_docker_control(self):
        p = plan()
        d = p.drones[0]
        c = capsule(d.role)
        argv = drone_run_argv(p, profile(), d, c, "/tmp/lion-p0/capsule.json")
        text = " ".join(argv)
        for required in (
            "--read-only",
            "--user 65532:65532",
            "--cap-drop ALL",
            "--security-opt no-new-privileges",
            "--pids-limit 64",
            "--memory 134217728",
            "--cpus 0.20",
            "--restart no",
            "--network lion-p0-run-p0-static-internal",
            "readonly",
            f"sha256:{p.image_digest}",
        ):
            self.assertIn(required, text)
        for forbidden in ("docker.sock", "--privileged", "--pid=host", "--network=host", "--ipc=host"):
            self.assertNotIn(forbidden, text)

    def test_materializer_rejects_wrong_capsule_binding(self):
        p = plan()
        d = p.drones[0]
        with self.assertRaises(DockerFleetPolygonError):
            drone_run_argv(p, profile(), d, capsule("security"), "/tmp/lion-p0/capsule.json")

    def test_all_five_d0_operations_are_deterministic_and_terminal(self):
        for role in ROLES:
            c = capsule(role)
            a = execute_capsule(c)
            b = execute_capsule(c)
            self.assertEqual(a.result_digest, b.result_digest)
            self.assertEqual(a.result, b.result)
            self.assertEqual(a.status, "SUCCEEDED")

    def test_aggregator_rejects_unknown_stale_and_replayed_results(self):
        p = plan()
        capsules = tuple(capsule(role) for role in ROLES)
        agg = FleetResultAggregator(p, capsules)
        result = execute_capsule(capsules[0])
        agg.accept(result)
        with self.assertRaises(DockerFleetPolygonError):
            agg.accept(result)
        with self.assertRaises(DockerFleetPolygonError):
            FleetResultAggregator(p, capsules).accept(replace(result, mission_id="other-mission"))
        with self.assertRaises(DockerFleetPolygonError):
            FleetResultAggregator(p, capsules).accept(replace(result, generation=2))

    def test_full_result_and_reconciliation_match(self):
        p = plan()
        capsules = tuple(capsule(role) for role in ROLES)
        agg = FleetResultAggregator(p, capsules)
        for c in capsules:
            agg.accept(execute_capsule(c))
        fleet_result = agg.finalize()
        receipt = reconcile(p, profile(), [observed(p, d) for d in p.drones], fleet_result)
        self.assertEqual(receipt.outcome, "MATCHED")
        self.assertEqual(receipt.mismatches, ())

    def test_reconciliation_falsifies_image_substitution(self):
        p = plan()
        capsules = tuple(capsule(role) for role in ROLES)
        agg = FleetResultAggregator(p, capsules)
        for c in capsules:
            agg.accept(execute_capsule(c))
        observations = [observed(p, d) for d in p.drones]
        observations[0] = replace(observations[0], image_digest=D("substituted-image"))
        receipt = reconcile(p, profile(), observations, agg.finalize())
        self.assertEqual(receipt.outcome, "MISMATCHED")
        self.assertTrue(any(x.startswith("image:") for x in receipt.mismatches))

    def test_docker_inspect_is_independent_runtime_evidence(self):
        p = plan()
        d = p.drones[0]
        raw = {
            "Id": D("container"),
            "Name": f"/{d.container_name}",
            "Image": f"sha256:{p.image_digest}",
            "Config": {"User": "65532:65532", "Labels": expected_labels(p, d)},
            "HostConfig": {
                "ReadonlyRootfs": True,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges"],
                "PidsLimit": 64,
                "Memory": 134217728,
                "NanoCpus": 200_000_000,
            },
            "State": {"ExitCode": 0},
            "NetworkSettings": {"Networks": {p.network_name: {}}, "Ports": {}},
            "Mounts": [{"Source": "/tmp/capsule.json", "Destination": "/mission/capsule.json"}],
            "RestartCount": 0,
        }
        item = observation_from_docker_inspect(raw, network_name=p.network_name)
        self.assertEqual(item.container_name, d.container_name)
        self.assertFalse(item.docker_socket_mounted)

    def test_final_image_definition_has_no_runtime_install_or_shell_step(self):
        dockerfile = Path("deploy/docker/lion-drone-p0/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM dhi.io/python@sha256:", dockerfile)
        self.assertIn("USER 65532:65532", dockerfile)
        self.assertIn('["python3", "-m", "cyber_lion.drone_p0"]', dockerfile)
        self.assertNotIn("\nRUN ", dockerfile)
        self.assertNotIn("apt ", dockerfile.lower())
        self.assertNotIn("pip install", dockerfile.lower())
        self.assertNotIn("/bin/sh", dockerfile)
        self.assertNotIn("/bin/bash", dockerfile)


if __name__ == "__main__":
    unittest.main()
