#!/usr/bin/env python3
"""Autonomous TEST_ONLY 64-drone Docker scale/soak polygon for LION 1.4.

Materializes exactly 64 logical drones on the bounded rootless Docker provider,
proves a full-fleet running barrier, holds the fleet for about three minutes,
observes it continuously, then dissolves only the resources bound to this run.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict
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
    DroneResult,
    DroneRuntimeProfile,
    MissionCapsule,
    canonical_json,
    digest_domain,
)
from tools.p0_docker_fleet_materializer import canonical_capsule_bytes
from tools.p0_rootless_docker_provider_client import send_request

MISSION_ID = "lion-local-swarm-scale64"
FLEET_ID = "lion-local-swarm-scale64"
EXECUTOR_ID = "rootless-docker-p0"
DRONE_COUNT = 64
SOAK_SECONDS = 180
POLL_SECONDS = 15
SAMPLE_SIZE = 8
ROLES = ("architecture", "security", "runtime", "provenance", "falsifier")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def request_id() -> str:
    return hashlib.sha256(os.urandom(32)).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LION 64-drone / 180-second rootless Docker soak polygon")
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--duration-seconds", type=int, default=SOAK_SECONDS)
    parser.add_argument("--poll-seconds", type=int, default=POLL_SECONDS)
    parser.add_argument("--evidence-out")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if len(args.source_head) != 40 or any(c not in "0123456789abcdef" for c in args.source_head):
        raise SystemExit("source head must be full lowercase SHA-1")
    if len(args.source_tree) != 40 or any(c not in "0123456789abcdef" for c in args.source_tree):
        raise SystemExit("source tree must be full lowercase SHA-1")
    if not 30 <= args.duration_seconds <= 300:
        raise SystemExit("duration must be in [30,300] seconds")
    if not 5 <= args.poll_seconds <= 30:
        raise SystemExit("poll interval must be in [5,30] seconds")


def workload(role: str, slot: int, image_digest: str | None = None) -> tuple[str, dict[str, Any]]:
    if role == "architecture":
        return "ARCHITECTURE_DIGEST", {"architecture_epoch": "1.4", "scale_slot": slot, "fleet_size": DRONE_COUNT}
    if role == "security":
        return "SECURITY_INVARIANTS", {"invariants": {"rootless": True, "bounded": True, "offline": True, "scale64": True}}
    if role == "runtime":
        return "RUNTIME_BINDINGS", {
            "expected": {"slot": slot, "uid": "65532", "memory": "134217728", "cpu": "0.20"},
            "observed": {"slot": slot, "uid": "65532", "memory": "134217728", "cpu": "0.20"},
        }
    if role == "provenance":
        objects = {"slot": slot, "fleet": DRONE_COUNT}
        if image_digest is not None:
            objects["image"] = image_digest
        return "PROVENANCE_RELATIONSHIPS", {
            "objects": objects,
            "relationships": [{"source": "slot", "target": "fleet"}],
        }
    if role == "falsifier":
        return "FALSIFY_CLAIM", {"claim": bool(slot % 2), "evidence": not bool(slot % 2)}
    raise ValueError(role)


def inspect_hardening(raw: dict[str, Any], *, network_name: str, expected_image: str) -> list[str]:
    errors: list[str] = []
    config = raw.get("Config") or {}
    host = raw.get("HostConfig") or {}
    state = raw.get("State") or {}
    network_settings = raw.get("NetworkSettings") or {}
    mounts = raw.get("Mounts") or []
    image = str(raw.get("Image") or "")
    if image.startswith("sha256:"):
        image = image[7:]
    if not state.get("Running"):
        errors.append("not-running")
    if image != expected_image:
        errors.append("image")
    if str(config.get("User") or "") != "65532:65532":
        errors.append("user")
    if not bool(host.get("ReadonlyRootfs")):
        errors.append("rootfs")
    if tuple(str(x).upper() for x in (host.get("CapDrop") or [])) != ("ALL",):
        errors.append("cap-drop")
    if not any(str(x).startswith("no-new-privileges") for x in (host.get("SecurityOpt") or [])):
        errors.append("nnp")
    if int(host.get("PidsLimit") or 0) != 64:
        errors.append("pids")
    if int(host.get("Memory") or 0) != 134217728:
        errors.append("memory")
    if int(host.get("NanoCpus") or 0) != 200_000_000:
        errors.append("cpu")
    if network_name not in (network_settings.get("Networks") or {}):
        errors.append("network")
    if any(bindings for bindings in (network_settings.get("Ports") or {}).values()):
        errors.append("host-ports")
    for mount in mounts:
        source = str(mount.get("Source", ""))
        destination = str(mount.get("Destination", ""))
        if source in {"/var/run/docker.sock", "/run/docker.sock"} or destination in {"/var/run/docker.sock", "/run/docker.sock"}:
            errors.append("docker-socket")
            break
    if int(raw.get("RestartCount") or 0) != 0:
        errors.append("restart")
    return errors


def main() -> int:
    args = parse_args()
    validate_args(args)
    source_head = args.source_head
    source_tree = args.source_tree
    nonce = secrets.token_hex(4)
    run_id = f"scale64-{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{nonce}"
    network_name = f"lion-p0-{nonce}-internal"
    hold_seconds = min(600, args.duration_seconds + 180)
    profile = DroneRuntimeProfile(profile_id="LION_DRONE_RUNTIME_P0").validate()
    policy_digest = profile.digest()
    issued = utc_now()
    issued_at = iso(issued)
    expires_at = iso(issued + timedelta(minutes=15))

    build_intent_digest = digest_domain(
        b"LION/SCALE64/BUILD-INTENT",
        {
            "mission_id": MISSION_ID,
            "fleet_id": FLEET_ID,
            "run_id": run_id,
            "source_head": source_head,
            "source_tree": source_tree,
            "runtime_profile_digest": policy_digest,
        },
    )

    def request(operation: str, payload: dict[str, Any], plan_digest: str) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "request_id": request_id(),
            "operation": operation,
            "mission_id": MISSION_ID,
            "fleet_id": FLEET_ID,
            "run_id": run_id,
            "source_head": source_head,
            "source_tree": source_tree,
            "plan_digest": plan_digest,
            "payload": payload,
        }

    def call(operation: str, payload: dict[str, Any], plan_digest: str) -> dict[str, Any]:
        response = send_request(request(operation, payload, plan_digest))
        if response.get("ok") is not True:
            raise RuntimeError(f"{operation} rejected: {json.dumps(response, sort_keys=True)}")
        return response["result"]

    print("===== LION SCALE64 AUTONOMOUS POLYGON =====")
    print(f"RUN_ID={run_id}")
    print(f"DRONES={DRONE_COUNT}")
    print(f"SOAK_SECONDS={args.duration_seconds}")
    print(f"POLL_SECONDS={args.poll_seconds}")
    print(f"INTERNAL_HOLD_SECONDS={hold_seconds}")

    created: list[DockerDroneBinding] = []
    capsules: list[MissionCapsule] = []
    bindings: list[DockerDroneBinding] = []
    container_ids: dict[str, str] = {}
    materialization_latency: dict[str, float] = {}
    snapshots: list[dict[str, Any]] = []
    work_results: list[dict[str, Any]] = []
    network_created = False
    network_id: str | None = None
    image_digest: str | None = None
    image_tag: str | None = None
    image_info: dict[str, Any] | None = None
    plan_digest: str | None = None
    failure: str | None = None
    cleanup_verified = False
    soak_started_at: str | None = None
    soak_completed_at: str | None = None

    try:
        ping = call("PING", {}, build_intent_digest)
        print(f"DOCKER_SERVER_VERSION={ping['docker_server_version']}")

        build = call("BUILD_P0_IMAGE", {}, build_intent_digest)
        image_digest = build["image_digest"]
        image_tag = build["image_tag"]
        image_info = call("INSPECT_P0_IMAGE", {"image_digest": image_digest}, build_intent_digest)
        print(f"IMAGE_DIGEST=sha256:{image_digest}")
        print(f"IMAGE_SIZE_MIB={image_info['size_bytes'] / 1048576:.2f}")

        for slot in range(DRONE_COUNT):
            role = ROLES[slot % len(ROLES)]
            operation, payload = workload(role, slot, image_digest)
            payload = dict(payload)
            payload["__lion_control__"] = {
                "mode": "hold_after_result",
                "hold_seconds": hold_seconds,
                "heartbeat_seconds": args.poll_seconds,
                "scale_run_id": run_id,
            }
            drone_id = f"drone-scale64-{slot:02d}"
            capsule = MissionCapsule.issue(
                mission_id=MISSION_ID,
                fleet_id=FLEET_ID,
                drone_id=drone_id,
                role=role,
                generation=1,
                work_unit_id=f"work-scale64-{slot:02d}",
                issued_at=issued_at,
                expires_at=expires_at,
                operation=operation,
                input_payload=payload,
                policy_digest=policy_digest,
            ).validate()
            lease_id = digest_domain(
                b"LION/SCALE64/LEASE",
                {"run_id": run_id, "drone_id": drone_id, "generation": 1, "slot": slot},
            )
            binding = DockerDroneBinding(
                drone_id=drone_id,
                role=role,
                generation=1,
                executor_id=EXECUTOR_ID,
                lease_id=lease_id,
                container_name=f"lion-p0-{nonce}-s{slot:02d}",
                image_digest=image_digest,
                capsule_digest=capsule.capsule_digest,
            ).validate()
            capsules.append(capsule)
            bindings.append(binding)

        plan_payload = {
            "schema_version": "1.0.0",
            "experiment": "LOCAL_SWARM_SCALE64",
            "mission_id": MISSION_ID,
            "fleet_id": FLEET_ID,
            "run_id": run_id,
            "source_head": source_head,
            "source_tree": source_tree,
            "image_digest": image_digest,
            "runtime_profile_digest": policy_digest,
            "network_name": network_name,
            "drone_count": DRONE_COUNT,
            "duration_seconds": args.duration_seconds,
            "drones": [asdict(item) for item in bindings],
        }
        plan_digest = digest_domain(b"LION/SCALE64/PLAN", plan_payload)
        print(f"SCALE64_PLAN_DIGEST={plan_digest}")

        network = call("CREATE_NETWORK", {"network_name": network_name}, plan_digest)
        network_created = True
        network_id = network["network_id"]
        print(f"NETWORK_ID={network_id}")

        print("===== MATERIALIZE 64 =====")
        for slot, (capsule, binding) in enumerate(zip(capsules, bindings), start=1):
            payload = {
                "container_name": binding.container_name,
                "network_name": network_name,
                "image_digest": image_digest,
                "drone_id": binding.drone_id,
                "role": binding.role,
                "generation": binding.generation,
                "executor_id": binding.executor_id,
                "lease_id": binding.lease_id,
                "capsule_digest": binding.capsule_digest,
                "capsule_b64": base64.b64encode(canonical_capsule_bytes(capsule)).decode("ascii"),
            }
            started = time.perf_counter()
            material = call("RUN_DRONE", payload, plan_digest)
            materialization_latency[binding.drone_id] = time.perf_counter() - started
            container_ids[binding.drone_id] = material["container_id"]
            created.append(binding)
            if slot % 8 == 0 or slot == DRONE_COUNT:
                print(f"MATERIALIZED={slot}/{DRONE_COUNT}")

        if len(created) != DRONE_COUNT:
            raise RuntimeError("scale64 materialization cardinality mismatch")

        print("===== FULL-FLEET BARRIER =====")
        inventory = call("LIST_MISSION_RESOURCES", {}, plan_digest)
        if len(inventory["containers"]) != DRONE_COUNT or len(inventory["networks"]) != 1:
            raise RuntimeError(f"barrier inventory mismatch: {inventory}")

        for capsule, binding in zip(capsules, bindings):
            inspect = call("INSPECT_DRONE", {"container_name": binding.container_name}, plan_digest)["inspect"]
            errors = inspect_hardening(inspect, network_name=network_name, expected_image=image_digest)
            if errors:
                raise RuntimeError(f"barrier hardening mismatch {binding.drone_id}: {errors}")
            logs = call("LOGS_DRONE", {"container_name": binding.container_name}, plan_digest)["logs"]
            lines = [line for line in logs.splitlines() if line.strip()]
            if not lines:
                raise RuntimeError(f"missing work result: {binding.drone_id}")
            first = json.loads(lines[0])
            if first.get("kind") != "WORK_RESULT" or first.get("status") != "SUCCEEDED":
                raise RuntimeError(f"invalid work result {binding.drone_id}: {first}")
            result_payload = dict(first)
            result_payload.pop("kind", None)
            result_payload["evidence"] = tuple(result_payload.get("evidence", []))
            DroneResult(**result_payload).validate()
            work_results.append(first)

        if len(work_results) != DRONE_COUNT:
            raise RuntimeError("scale64 distributed work incomplete")
        aggregate_digest = digest_domain(
            b"LION/SCALE64/RESULT",
            sorted(work_results, key=lambda item: item["drone_id"]),
        )
        print("FULL_FLEET_BARRIER=PASS")
        print("DISTRIBUTED_WORK_RESULTS=64")
        print(f"SCALE64_RESULT_DIGEST={aggregate_digest}")

        print("===== 180-SECOND SOAK =====")
        soak_started = time.monotonic()
        soak_started_at = iso(utc_now())
        poll_index = 0
        while True:
            elapsed = time.monotonic() - soak_started
            if elapsed >= args.duration_seconds:
                break
            inventory = call("LIST_MISSION_RESOURCES", {}, plan_digest)
            if len(inventory["containers"]) != DRONE_COUNT or len(inventory["networks"]) != 1:
                raise RuntimeError(f"soak inventory mismatch at {elapsed:.1f}s: {inventory}")

            sample_start = (poll_index * SAMPLE_SIZE) % DRONE_COUNT
            sample_slots = [(sample_start + offset) % DRONE_COUNT for offset in range(SAMPLE_SIZE)]
            sample_state: list[dict[str, Any]] = []
            for slot in sample_slots:
                binding = bindings[slot]
                raw = call("INSPECT_DRONE", {"container_name": binding.container_name}, plan_digest)["inspect"]
                errors = inspect_hardening(raw, network_name=network_name, expected_image=image_digest)
                if errors:
                    raise RuntimeError(f"soak sample mismatch {binding.drone_id}: {errors}")
                sample_state.append({"drone_id": binding.drone_id, "running": True, "restart_count": int(raw.get("RestartCount") or 0)})

            snapshot = {
                "elapsed_seconds": round(elapsed, 3),
                "observed_at": iso(utc_now()),
                "container_count": len(inventory["containers"]),
                "network_count": len(inventory["networks"]),
                "sample": sample_state,
            }
            snapshots.append(snapshot)
            print(f"T+{int(elapsed):03d}s CONTAINERS=64 SAMPLE_RUNNING={len(sample_state)}/{SAMPLE_SIZE}")
            poll_index += 1
            sleep_for = min(args.poll_seconds, max(0.0, args.duration_seconds - (time.monotonic() - soak_started)))
            if sleep_for > 0:
                time.sleep(sleep_for)

        print("===== FINAL 64/64 OBSERVATION =====")
        for binding in bindings:
            raw = call("INSPECT_DRONE", {"container_name": binding.container_name}, plan_digest)["inspect"]
            errors = inspect_hardening(raw, network_name=network_name, expected_image=image_digest)
            if errors:
                raise RuntimeError(f"final observation mismatch {binding.drone_id}: {errors}")
            logs = call("LOGS_DRONE", {"container_name": binding.container_name}, plan_digest)["logs"]
            heartbeats = [json.loads(line) for line in logs.splitlines() if line.strip() and json.loads(line).get("kind") == "HEARTBEAT"]
            if not heartbeats:
                raise RuntimeError(f"no heartbeat evidence for {binding.drone_id}")

        soak_completed_at = iso(utc_now())
        print("SOAK_WINDOW=PASS")
        print("FINAL_RUNNING=64/64")

    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        print(f"SCALE64_FAILURE={failure}")

    finally:
        print("===== DISSOLVE FLEET =====")
        if plan_digest is not None:
            for index, binding in enumerate(reversed(created), start=1):
                try:
                    response = send_request(request("REMOVE_DRONE", {"container_name": binding.container_name}, plan_digest))
                    if response.get("ok") is not True:
                        print(f"REMOVE_FAIL={binding.drone_id}:{json.dumps(response, sort_keys=True)}")
                except Exception as exc:
                    print(f"REMOVE_EXCEPTION={binding.drone_id}:{exc!r}")
                if index % 8 == 0 or index == len(created):
                    print(f"DISSOLVED={index}/{len(created)}")

            if network_created:
                try:
                    response = send_request(request("REMOVE_NETWORK", {"network_name": network_name}, plan_digest))
                    if response.get("ok") is not True:
                        print(f"REMOVE_NETWORK_FAIL={json.dumps(response, sort_keys=True)}")
                except Exception as exc:
                    print(f"REMOVE_NETWORK_EXCEPTION={exc!r}")

            try:
                inventory = call("LIST_MISSION_RESOURCES", {}, plan_digest)
                cleanup_verified = not inventory["containers"] and not inventory["networks"]
            except Exception as exc:
                print(f"CLEANUP_VERIFY_EXCEPTION={exc!r}")
                cleanup_verified = False
        print(f"CLEANUP_VERIFIED={cleanup_verified}")

    evidence = {
        "schema_version": "1.0.0",
        "experiment": "LOCAL_SWARM_SCALE64",
        "mission_id": MISSION_ID,
        "fleet_id": FLEET_ID,
        "run_id": run_id,
        "source_head": source_head,
        "source_tree": source_tree,
        "drone_count": DRONE_COUNT,
        "requested_soak_seconds": args.duration_seconds,
        "poll_seconds": args.poll_seconds,
        "internal_hold_seconds": hold_seconds,
        "soak_started_at": soak_started_at,
        "soak_completed_at": soak_completed_at,
        "image_digest": image_digest,
        "image_reference": image_tag,
        "image_info": image_info,
        "network_id": network_id,
        "scale_plan_digest": plan_digest,
        "container_ids": container_ids,
        "logical_bindings": [asdict(item) for item in bindings],
        "work_results": work_results,
        "materialization_latency_seconds": materialization_latency,
        "soak_snapshots": snapshots,
        "failure": failure,
        "cleanup_verified": cleanup_verified,
    }
    evidence_path = Path(args.evidence_out) if args.evidence_out else Path(f"/tmp/{run_id}-lion-scale64-evidence.json")
    evidence_path.write_bytes(canonical_json(evidence) + b"\n")
    os.chmod(evidence_path, 0o644)

    success = failure is None and cleanup_verified and len(created) == DRONE_COUNT and len(work_results) == DRONE_COUNT and soak_completed_at is not None
    print("===== SCALE64 FINAL =====")
    print(f"SCALE64_SUCCESS={success}")
    print(f"LOGICAL_DRONES={DRONE_COUNT}")
    print(f"MATERIALIZED={len(created)}")
    print(f"WORK_RESULTS={len(work_results)}")
    print(f"SOAK_SECONDS={args.duration_seconds}")
    print(f"CLEANUP_VERIFIED={cleanup_verified}")
    print(f"IMAGE_DIGEST={'sha256:' + image_digest if image_digest else 'UNKNOWN'}")
    print(f"SCALE64_PLAN_DIGEST={plan_digest or 'UNKNOWN'}")
    print(f"RUN_ID={run_id}")
    print(f"EVIDENCE={evidence_path}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
