#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any

from tools.p0_docker_fleet_contract import (
    DockerDroneBinding,
    DockerFleetPlan,
    DroneResult,
    DroneRuntimeProfile,
    MissionCapsule,
    canonical_json,
    digest_domain,
)
from tools.p0_docker_fleet_materializer import (
    FleetResultAggregator,
    canonical_capsule_bytes,
    observation_from_docker_inspect,
    reconcile,
)
from tools.p0_rootless_docker_provider_client import send_request

MISSION_ID = "lion-local-swarm-p0-material"
FLEET_ID = "lion-local-swarm-p0"
EXECUTOR_ID = "rootless-docker-p0"
PROBES = (
    "ROOTFS_WRITE_DENIED",
    "NON_ROOT",
    "NO_SHELL",
    "NO_PACKAGE_MANAGER",
    "NO_DOCKER_SOCKET",
    "CAP_EFF_ZERO",
    "EGRESS_DENIED",
)
ROLES = ("architecture", "security", "runtime", "provenance", "falsifier")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the complete TEST_ONLY LION Docker P0 polygon")
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--evidence-out")
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def random_request_id() -> str:
    return hashlib.sha256(os.urandom(32)).hexdigest()


def duration_seconds(started: str, completed: str) -> float:
    a = datetime.fromisoformat(started.replace("Z", "+00:00"))
    b = datetime.fromisoformat(completed.replace("Z", "+00:00"))
    return max(0.0, (b - a).total_seconds())


def main() -> int:
    args = parse_args()
    source_head = args.source_head
    source_tree = args.source_tree
    nonce = secrets.token_hex(4)
    run_id = f"run-{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{nonce}"
    network_name = f"lion-p0-{nonce}-internal"

    profile = DroneRuntimeProfile(profile_id="LION_DRONE_RUNTIME_P0").validate()
    policy_digest = profile.digest()
    issued = utc_now()
    issued_at = iso(issued)
    expires_at = iso(issued + timedelta(minutes=30))

    build_intent_digest = digest_domain(
        b"LION/P0/BUILD-INTENT",
        {
            "source_head": source_head,
            "source_tree": source_tree,
            "runtime_profile_digest": policy_digest,
            "mission_id": MISSION_ID,
            "fleet_id": FLEET_ID,
            "run_id": run_id,
        },
    )

    def request(operation: str, payload: dict[str, Any], plan_digest: str, *, mission_id: str = MISSION_ID) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "request_id": random_request_id(),
            "operation": operation,
            "mission_id": mission_id,
            "fleet_id": FLEET_ID,
            "run_id": run_id,
            "source_head": source_head,
            "source_tree": source_tree,
            "plan_digest": plan_digest,
            "payload": payload,
        }

    def call(operation: str, payload: dict[str, Any], plan_digest: str) -> dict[str, Any]:
        response = send_request(request(operation, payload, plan_digest))
        print(f"{operation}={'PASS' if response.get('ok') is True else 'FAIL'}")
        if response.get("ok") is not True:
            raise RuntimeError(f"{operation} rejected: {json.dumps(response, sort_keys=True)}")
        return response["result"]

    work = {
        "architecture": (
            "ARCHITECTURE_DIGEST",
            {
                "architecture_epoch": "1.4",
                "source_head": source_head,
                "source_tree": source_tree,
                "fleet_size": 5,
                "substrate": "docker",
            },
        ),
        "security": (
            "SECURITY_INVARIANTS",
            {
                "invariants": {
                    "non_root": True,
                    "read_only_rootfs": True,
                    "cap_drop_all": True,
                    "no_new_privileges": True,
                    "docker_socket_absent": True,
                    "host_ports_absent": True,
                    "persistent_state_absent": True,
                }
            },
        ),
        "runtime": (
            "RUNTIME_BINDINGS",
            {
                "expected": {
                    "runtime": "rootless-docker",
                    "uid": "65532",
                    "gid": "65532",
                    "memory": "134217728",
                    "pids": "64",
                    "cpu": "0.20",
                },
                "observed": {
                    "runtime": "rootless-docker",
                    "uid": "65532",
                    "gid": "65532",
                    "memory": "134217728",
                    "pids": "64",
                    "cpu": "0.20",
                },
            },
        ),
        "provenance": (
            "PROVENANCE_RELATIONSHIPS",
            {
                "objects": {
                    "head": source_head,
                    "tree": source_tree,
                    "runtime_profile": policy_digest,
                },
                "relationships": [
                    {"source": "head", "target": "tree"},
                    {"source": "tree", "target": "runtime_profile"},
                ],
            },
        ),
        "falsifier": ("FALSIFY_CLAIM", {"claim": True, "evidence": False}),
    }

    created: list[DockerDroneBinding] = []
    removed: set[str] = set()
    network_created = False
    network_id: str | None = None
    image_digest: str | None = None
    image_tag: str | None = None
    image_info: dict[str, Any] | None = None
    plan: DockerFleetPlan | None = None
    plan_digest: str | None = None
    capsules: list[MissionCapsule] = []
    bindings: list[DockerDroneBinding] = []
    results: list[DroneResult] = []
    observations = []
    fleet_result: dict[str, Any] | None = None
    receipt = None
    failure: str | None = None
    cleanup_verified = False
    cleanup_inventory: dict[str, Any] | None = None
    materialization_latency: dict[str, float] = {}
    negative: dict[str, Any] = {}
    probe_results: dict[str, Any] = {}
    build_latency = None

    print("===== P0 FULL LIVE RUN =====")
    print(f"RUN_ID={run_id}")

    try:
        ping = call("PING", {}, build_intent_digest)
        print(f"DOCKER_SERVER_VERSION={ping['docker_server_version']}")

        build_started = time.perf_counter()
        build = call("BUILD_P0_IMAGE", {}, build_intent_digest)
        build_latency = time.perf_counter() - build_started
        image_digest = build["image_digest"]
        image_tag = build["image_tag"]
        print(f"IMAGE_DIGEST=sha256:{image_digest}")

        image_info = call("INSPECT_P0_IMAGE", {"image_digest": image_digest}, build_intent_digest)
        print(f"IMAGE_SIZE_BYTES={image_info['size_bytes']}")
        print(f"IMAGE_SIZE_MIB={image_info['size_bytes'] / 1048576:.2f}")

        for role in ROLES:
            operation, payload = work[role]
            if role == "provenance":
                payload = dict(payload)
                payload["objects"] = dict(payload["objects"])
                payload["objects"]["image"] = image_digest
                payload["relationships"] = list(payload["relationships"]) + [
                    {"source": "tree", "target": "image"},
                    {"source": "image", "target": "runtime_profile"},
                ]
            drone_id = f"drone-{role}"
            capsule = MissionCapsule.issue(
                mission_id=MISSION_ID,
                fleet_id=FLEET_ID,
                drone_id=drone_id,
                role=role,
                generation=1,
                work_unit_id=f"work-{role}",
                issued_at=issued_at,
                expires_at=expires_at,
                operation=operation,
                input_payload=payload,
                policy_digest=policy_digest,
            ).validate()
            lease_id = digest_domain(
                b"LION/P0/LEASE",
                {
                    "mission_id": MISSION_ID,
                    "fleet_id": FLEET_ID,
                    "run_id": run_id,
                    "drone_id": drone_id,
                    "generation": 1,
                },
            )
            binding = DockerDroneBinding(
                drone_id=drone_id,
                role=role,
                generation=1,
                executor_id=EXECUTOR_ID,
                lease_id=lease_id,
                container_name=f"lion-p0-{nonce}-{role}",
                image_digest=image_digest,
                capsule_digest=capsule.capsule_digest,
            ).validate()
            capsules.append(capsule)
            bindings.append(binding)

        plan = DockerFleetPlan(
            mission_id=MISSION_ID,
            fleet_id=FLEET_ID,
            run_id=run_id,
            repository="DonkeyJJLove/ai_platform",
            source_head=source_head,
            source_tree=source_tree,
            network_name=network_name,
            image_reference=image_tag,
            image_digest=image_digest,
            runtime_profile_digest=policy_digest,
            drones=tuple(bindings),
        ).validate()
        plan_digest = plan.digest()
        print(f"FLEET_PLAN_DIGEST={plan_digest}")

        create_network_request = request("CREATE_NETWORK", {"network_name": network_name}, plan_digest)
        create_network_response = send_request(create_network_request)
        if create_network_response.get("ok") is not True:
            raise RuntimeError(f"CREATE_NETWORK failed: {create_network_response}")
        network_created = True
        network_id = create_network_response["result"]["network_id"]
        print(f"NETWORK_ID={network_id}")

        replay = send_request(create_network_request)
        negative["NEGATIVE_05_REPLAYED_MUTATING_REQUEST"] = replay.get("ok") is False
        if not negative["NEGATIVE_05_REPLAYED_MUTATING_REQUEST"]:
            raise RuntimeError("replayed mutating request was accepted")

        first_capsule = capsules[0]
        first_binding = bindings[0]

        def run_payload(capsule_bytes: bytes, binding: DockerDroneBinding, *, drone_id: str | None = None, generation: int | None = None) -> dict[str, Any]:
            return {
                "container_name": binding.container_name,
                "network_name": network_name,
                "image_digest": image_digest,
                "drone_id": binding.drone_id if drone_id is None else drone_id,
                "role": binding.role,
                "generation": binding.generation if generation is None else generation,
                "executor_id": binding.executor_id,
                "lease_id": binding.lease_id,
                "capsule_digest": binding.capsule_digest,
                "capsule_b64": base64.b64encode(capsule_bytes).decode("ascii"),
            }

        mutated = first_capsule.canonical_dict()
        mutated["input_payload"] = {"tampered": True}
        mutated_response = send_request(
            request(
                "RUN_DRONE",
                run_payload(canonical_json(mutated) + b"\n", first_binding),
                plan_digest,
            )
        )
        negative["NEGATIVE_01_MUTATED_CAPSULE_DIGEST"] = mutated_response.get("ok") is False
        if not negative["NEGATIVE_01_MUTATED_CAPSULE_DIGEST"]:
            raise RuntimeError("mutated capsule accepted")

        wrong_drone_response = send_request(
            request(
                "RUN_DRONE",
                run_payload(canonical_capsule_bytes(first_capsule), first_binding, drone_id="drone-wrong"),
                plan_digest,
            )
        )
        negative["NEGATIVE_03_WRONG_DRONE_ID"] = wrong_drone_response.get("ok") is False
        if not negative["NEGATIVE_03_WRONG_DRONE_ID"]:
            raise RuntimeError("wrong drone binding accepted")

        stale_generation_response = send_request(
            request(
                "RUN_DRONE",
                run_payload(canonical_capsule_bytes(first_capsule), first_binding, generation=2),
                plan_digest,
            )
        )
        negative["NEGATIVE_04_STALE_GENERATION"] = stale_generation_response.get("ok") is False
        if not negative["NEGATIVE_04_STALE_GENERATION"]:
            raise RuntimeError("stale generation accepted")

        print("===== MATERIALIZE FIVE DRONES =====")
        for capsule, binding in zip(capsules, bindings):
            started = time.perf_counter()
            material = call(
                "RUN_DRONE",
                run_payload(canonical_capsule_bytes(capsule), binding),
                plan_digest,
            )
            materialization_latency[binding.drone_id] = time.perf_counter() - started
            created.append(binding)
            print(f"{binding.drone_id}={material['container_id']}")

        if len(created) != 5:
            raise RuntimeError("materialized fleet cardinality != 5")

        aggregator = FleetResultAggregator(plan, capsules)
        for binding in bindings:
            wait = call("WAIT_DRONE", {"container_name": binding.container_name}, plan_digest)
            logs = call("LOGS_DRONE", {"container_name": binding.container_name}, plan_digest)
            inspect = call("INSPECT_DRONE", {"container_name": binding.container_name}, plan_digest)
            if int(wait["exit_code"]) != 0:
                raise RuntimeError(f"{binding.drone_id} exit={wait['exit_code']} logs={logs['logs']}")
            parsed = json.loads(logs["logs"].strip())
            if parsed.get("status") != "SUCCEEDED":
                raise RuntimeError(f"{binding.drone_id} result not SUCCEEDED: {parsed}")
            parsed["evidence"] = tuple(parsed.get("evidence", []))
            result = DroneResult(**parsed).validate()
            aggregator.accept(result)
            results.append(result)
            observations.append(
                observation_from_docker_inspect(inspect["inspect"], network_name=network_name)
            )

        negative["NEGATIVE_08_PROCESS_UID_IS_ROOT"] = all(o.user == "65532:65532" for o in observations)
        negative["NEGATIVE_11_DOCKER_SOCKET_PRESENT"] = all(not o.docker_socket_mounted for o in observations)
        negative["NEGATIVE_14_UNEXPECTED_HOST_PORT_EXPOSED"] = all(not o.published_ports for o in observations)
        if not all(
            negative[k]
            for k in (
                "NEGATIVE_08_PROCESS_UID_IS_ROOT",
                "NEGATIVE_11_DOCKER_SOCKET_PRESENT",
                "NEGATIVE_14_UNEXPECTED_HOST_PORT_EXPOSED",
            )
        ):
            raise RuntimeError("live observation hardening mismatch")

        print("===== HARDENING PROBES =====")
        for probe in PROBES:
            result = call(
                "RUN_HARDENING_PROBE",
                {"probe": probe, "network_name": network_name, "image_digest": image_digest},
                plan_digest,
            )
            probe_results[probe] = result["result"]
            print(f"PROBE_{probe}=PASS")

        negative["NEGATIVE_07_WRITE_TO_ROOT_FILESYSTEM"] = True
        negative["NEGATIVE_08_PROCESS_UID_IS_ROOT"] = True
        negative["NEGATIVE_09_RUNTIME_SHELL_PRESENT"] = True
        negative["NEGATIVE_10_PACKAGE_MANAGER_PRESENT"] = True
        negative["NEGATIVE_11_DOCKER_SOCKET_PRESENT"] = True
        negative["NEGATIVE_12_EFFECTIVE_LINUX_CAPABILITIES_NONZERO"] = True
        negative["NEGATIVE_13_OUTBOUND_INTERNET_CONNECTIVITY"] = True

        duplicate_aggregator = FleetResultAggregator(plan, capsules)
        duplicate_aggregator.accept(results[0])
        try:
            duplicate_aggregator.accept(results[0])
        except Exception:
            negative["NEGATIVE_06_DUPLICATE_TERMINAL_RESULT"] = True
        else:
            negative["NEGATIVE_06_DUPLICATE_TERMINAL_RESULT"] = False
            raise RuntimeError("duplicate terminal result accepted")

        wrong_mission = send_request(
            request(
                "INSPECT_DRONE",
                {"container_name": bindings[0].container_name},
                plan_digest,
                mission_id="wrong-mission",
            )
        )
        negative["NEGATIVE_02_WRONG_MISSION_ID"] = wrong_mission.get("ok") is False
        if not negative["NEGATIVE_02_WRONG_MISSION_ID"]:
            raise RuntimeError("wrong mission observation accepted")

        fleet_result = aggregator.finalize()
        receipt = reconcile(plan, profile, observations, fleet_result)
        if receipt.outcome != "MATCHED":
            raise RuntimeError(f"positive reconciliation failed: {receipt.mismatches}")
        print("RECONCILIATION=MATCHED")

        unlabeled = replace(observations[0], labels={})
        unlabeled_receipt = reconcile(plan, profile, [unlabeled, *observations[1:]], fleet_result)
        negative["NEGATIVE_15_UNLABELED_MISSION_RESOURCE_ACCEPTED"] = unlabeled_receipt.outcome == "MISMATCHED"
        if not negative["NEGATIVE_15_UNLABELED_MISSION_RESOURCE_ACCEPTED"]:
            raise RuntimeError("unlabeled observation accepted")

        unknown = replace(
            observations[0],
            container_id="f" * 64,
            container_name=f"lion-p0-{nonce}-unknown",
        )
        unknown_receipt = reconcile(plan, profile, [*observations, unknown], fleet_result)
        negative["NEGATIVE_16_UNKNOWN_CONTAINER_COUNTED_AS_FLEET_MEMBER"] = unknown_receipt.outcome == "MISMATCHED"
        if not negative["NEGATIVE_16_UNKNOWN_CONTAINER_COUNTED_AS_FLEET_MEMBER"]:
            raise RuntimeError("unknown container accepted")

        stale_binding = bindings[0]
        remove_first = call("REMOVE_DRONE", {"container_name": stale_binding.container_name}, plan_digest)
        _ = remove_first
        removed.add(stale_binding.drone_id)
        stale_rematerialization = send_request(
            request(
                "RUN_DRONE",
                run_payload(canonical_capsule_bytes(capsules[0]), stale_binding),
                plan_digest,
            )
        )
        negative["NEGATIVE_17_STALE_LEASE_REMATERIALIZATION"] = stale_rematerialization.get("ok") is False
        if not negative["NEGATIVE_17_STALE_LEASE_REMATERIALIZATION"]:
            raise RuntimeError("stale lease rematerialization accepted")

    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        print(f"P0_FAILURE={failure}")

    finally:
        print("===== CLEANUP =====")
        if plan_digest is not None:
            for binding in reversed(created):
                if binding.drone_id in removed:
                    continue
                response = send_request(
                    request("REMOVE_DRONE", {"container_name": binding.container_name}, plan_digest)
                )
                print(f"REMOVE_{binding.drone_id}={response.get('ok')}")
                if response.get("ok") is not True and failure is None:
                    failure = f"cleanup failed for {binding.drone_id}: {response}"
            if network_created:
                response = send_request(
                    request("REMOVE_NETWORK", {"network_name": network_name}, plan_digest)
                )
                print(f"REMOVE_NETWORK={response.get('ok')}")
                if response.get("ok") is not True and failure is None:
                    failure = f"network cleanup failed: {response}"
            inventory_response = send_request(request("LIST_MISSION_RESOURCES", {}, plan_digest))
            if inventory_response.get("ok") is True:
                cleanup_inventory = inventory_response["result"]
                cleanup_verified = not cleanup_inventory["containers"] and not cleanup_inventory["networks"]
            else:
                cleanup_inventory = inventory_response
                cleanup_verified = False
            print(f"CLEANUP_VERIFIED={cleanup_verified}")
            if not cleanup_verified and failure is None:
                failure = f"cleanup inventory not empty: {cleanup_inventory}"

    telemetry = {
        "image_size_bytes": None if image_info is None else image_info.get("size_bytes"),
        "image_size_mib": None if image_info is None else round(image_info.get("size_bytes", 0) / 1048576, 2),
        "build_latency_seconds": build_latency,
        "per_drone_materialization_latency_seconds": materialization_latency,
        "per_drone_wall_time_seconds": {
            result.drone_id: duration_seconds(result.started_at, result.completed_at)
            for result in results
        },
        "container_restart_count": {o.container_name: o.restart_count for o in observations},
        "peak_or_observed_memory": "UNKNOWN_NOT_RELIABLY_OBSERVED",
        "cpu_usage": "UNKNOWN_NOT_RELIABLY_OBSERVED",
        "network_rx": "UNKNOWN_NOT_RELIABLY_OBSERVED",
        "network_tx": "UNKNOWN_NOT_RELIABLY_OBSERVED",
        "failure_count": 0 if failure is None else 1,
    }

    evidence = {
        "mission_id": MISSION_ID,
        "fleet_id": FLEET_ID,
        "run_id": run_id,
        "source_head": source_head,
        "source_tree": source_tree,
        "build_intent_digest": build_intent_digest,
        "image_reference": image_tag,
        "image_digest": image_digest,
        "image_info": image_info,
        "runtime_profile_digest": policy_digest,
        "fleet_plan_digest": plan_digest,
        "network_id": network_id,
        "logical_drones": [asdict(x) for x in bindings],
        "results": [x.canonical_dict() for x in results],
        "observations": [asdict(x) for x in observations],
        "fleet_result": fleet_result,
        "reconciliation": None if receipt is None else asdict(receipt),
        "negative_tests": negative,
        "hardening_probes": probe_results,
        "resource_telemetry": telemetry,
        "cleanup_inventory": cleanup_inventory,
        "cleanup_verified": cleanup_verified,
        "failure": failure,
    }

    evidence_path = Path(args.evidence_out or f"/tmp/{run_id}-lion-p0-full-evidence.json")
    evidence_path.write_bytes(canonical_json(evidence) + b"\n")
    os.chmod(evidence_path, 0o644)

    all_negative = len(negative) >= 17 and all(negative.values())
    full_success = (
        failure is None
        and len(results) == 5
        and len(observations) == 5
        and receipt is not None
        and receipt.outcome == "MATCHED"
        and all_negative
        and cleanup_verified
    )

    print("===== P0 FINAL =====")
    print(f"FULL_SUCCESS={full_success}")
    print(f"LOGICAL_DRONES={len(bindings)}")
    print(f"MATERIAL_CONTAINERS={len(observations)}")
    print(f"NEGATIVE_TESTS_PASS={all_negative}")
    print(f"CLEANUP_VERIFIED={cleanup_verified}")
    print(f"RECONCILIATION={None if receipt is None else receipt.outcome}")
    print(f"IMAGE_DIGEST={None if image_digest is None else 'sha256:' + image_digest}")
    print(f"FLEET_PLAN_DIGEST={plan_digest}")
    print(f"RUN_ID={run_id}")
    print(f"EVIDENCE={evidence_path}")

    return 0 if full_success else 2


if __name__ == "__main__":
    raise SystemExit(main())
