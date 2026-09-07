"""Bounded Docker materialization adapter for Local Swarm P0.

This module compiles immutable LION fleet intent into exact Docker CLI argv and
reconciles independent ``docker inspect`` observations.  It deliberately does
not invoke subprocess itself: the actual Docker effect remains the
responsibility of an explicitly authorized host-side provider.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from cyber_lion.contracts.docker_fleet_polygon import (
    DockerDroneBinding,
    DockerFleetPlan,
    DockerFleetPolygonContractError,
    DockerFleetReconciliationReceipt,
    DroneResult,
    DroneRuntimeProfile,
    MissionCapsule,
    ObservedContainer,
    canonical_json,
    digest_domain,
)

PROJECT_LABEL = "LION_EVOLUSION"
EXPERIMENT_LABEL = "LOCAL_SWARM_P0"
ARCH_EPOCH = "1.4"


class DockerFleetPolygonError(RuntimeError):
    pass


def _labels(plan: DockerFleetPlan, *, resource_class: str, drone: DockerDroneBinding | None = None) -> dict[str, str]:
    plan.validate()
    labels = {
        "lion.project": PROJECT_LABEL,
        "lion.architecture_epoch": ARCH_EPOCH,
        "lion.experiment_epoch": EXPERIMENT_LABEL,
        "lion.mission_id": plan.mission_id,
        "lion.fleet_id": plan.fleet_id,
        "lion.run_id": plan.run_id,
        "lion.resource_class": resource_class,
        "lion.trust_class": plan.trust_class,
        "lion.plan_digest": plan.digest(),
    }
    if drone is not None:
        drone.validate()
        labels.update(
            {
                "lion.drone_id": drone.drone_id,
                "lion.role": drone.role,
                "lion.generation": str(drone.generation),
                "lion.executor_id": drone.executor_id,
                "lion.lease_id": drone.lease_id,
                "lion.capsule_digest": drone.capsule_digest,
            }
        )
    return labels


def _label_args(labels: Mapping[str, str]) -> list[str]:
    args: list[str] = []
    for key in sorted(labels):
        args.extend(("--label", f"{key}={labels[key]}"))
    return args


def network_create_argv(plan: DockerFleetPlan) -> tuple[str, ...]:
    plan.validate()
    return tuple(
        ["docker", "network", "create", "--internal"]
        + _label_args(_labels(plan, resource_class="fleet-network"))
        + [plan.network_name]
    )


def network_remove_argv(plan: DockerFleetPlan) -> tuple[str, ...]:
    plan.validate()
    return ("docker", "network", "rm", plan.network_name)


def drone_run_argv(
    plan: DockerFleetPlan,
    profile: DroneRuntimeProfile,
    drone: DockerDroneBinding,
    capsule: MissionCapsule,
    capsule_host_path: str,
) -> tuple[str, ...]:
    plan.validate()
    profile.validate()
    drone.validate()
    capsule.validate()
    if drone not in plan.drones:
        raise DockerFleetPolygonError("drone is not present in fleet plan")
    if (
        capsule.mission_id,
        capsule.fleet_id,
        capsule.drone_id,
        capsule.role,
        capsule.generation,
        capsule.capsule_digest,
    ) != (
        plan.mission_id,
        plan.fleet_id,
        drone.drone_id,
        drone.role,
        drone.generation,
        drone.capsule_digest,
    ):
        raise DockerFleetPolygonError("capsule/drone/plan binding mismatch")
    path = Path(capsule_host_path)
    if not path.is_absolute() or "\x00" in capsule_host_path:
        raise DockerFleetPolygonError("capsule host path must be absolute")
    image_id = f"sha256:{plan.image_digest}"
    labels = _labels(plan, resource_class="drone", drone=drone)
    args = [
        "docker",
        "run",
        "--detach",
        "--name",
        drone.container_name,
        "--network",
        plan.network_name,
        "--read-only",
        "--user",
        f"{profile.uid}:{profile.gid}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(profile.pids_limit),
        "--memory",
        str(profile.memory_limit_bytes),
        "--cpus",
        f"{profile.cpu_limit_millis / 1000:.2f}",
        "--restart",
        "no",
        "--tmpfs",
        f"/tmp:rw,noexec,nosuid,nodev,size={profile.tmpfs_limit_bytes}",
        "--mount",
        f"type=bind,src={path},dst=/mission/capsule.json,readonly",
    ]
    args.extend(_label_args(labels))
    args.append(image_id)
    joined = " ".join(args)
    forbidden = ("/var/run/docker.sock", "--privileged", "--pid=host", "--network=host", "--ipc=host")
    if any(token in joined for token in forbidden):
        raise DockerFleetPolygonError("compiled Docker argv violates P0 boundary")
    return tuple(args)


def drone_inspect_argv(drone: DockerDroneBinding) -> tuple[str, ...]:
    drone.validate()
    return ("docker", "inspect", drone.container_name)


def drone_logs_argv(drone: DockerDroneBinding) -> tuple[str, ...]:
    drone.validate()
    return ("docker", "logs", drone.container_name)


def drone_remove_argv(drone: DockerDroneBinding) -> tuple[str, ...]:
    drone.validate()
    return ("docker", "rm", "--force", drone.container_name)


def observation_from_docker_inspect(value: Mapping[str, Any], *, network_name: str) -> ObservedContainer:
    try:
        host = value["HostConfig"]
        config = value["Config"]
        state = value["State"]
        network_settings = value["NetworkSettings"]
        mounts = value.get("Mounts", [])
        image = str(value["Image"])
        if image.startswith("sha256:"):
            image = image[7:]
        cap_drop = tuple(str(x).upper() for x in (host.get("CapDrop") or []))
        security_opt = tuple(
            "no-new-privileges" if str(x).startswith("no-new-privileges") else str(x)
            for x in (host.get("SecurityOpt") or [])
        )
        ports: list[str] = []
        for port, bindings in (network_settings.get("Ports") or {}).items():
            if bindings:
                ports.append(str(port))
        networks = network_settings.get("Networks") or {}
        if network_name not in networks:
            raise DockerFleetPolygonError("expected isolated network absent")
        socket_mounted = any(
            str(mount.get("Source", "")) in {"/var/run/docker.sock", "/run/docker.sock"}
            or str(mount.get("Destination", "")) in {"/var/run/docker.sock", "/run/docker.sock"}
            for mount in mounts
            if isinstance(mount, Mapping)
        )
        observed = ObservedContainer(
            container_id=str(value["Id"]),
            container_name=str(value["Name"]).lstrip("/"),
            image_digest=image,
            labels=dict(config.get("Labels") or {}),
            user=str(config.get("User") or ""),
            read_only_rootfs=bool(host.get("ReadonlyRootfs")),
            cap_drop=cap_drop,
            security_opt=security_opt,
            pids_limit=int(host.get("PidsLimit") or 0),
            memory_limit_bytes=int(host.get("Memory") or 0),
            nano_cpus=int(host.get("NanoCpus") or 0),
            network_name=network_name,
            published_ports=tuple(sorted(ports)),
            docker_socket_mounted=socket_mounted,
            exit_code=int(state.get("ExitCode", -1)),
            restart_count=int(value.get("RestartCount", 0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DockerFleetPolygonError("docker inspect payload malformed") from exc
    return observed.validate()


class FleetResultAggregator:
    def __init__(self, plan: DockerFleetPlan, capsules: Iterable[MissionCapsule]):
        self.plan = plan.validate()
        self.capsules = {c.drone_id: c.validate() for c in capsules}
        if set(self.capsules) != {d.drone_id for d in self.plan.drones}:
            raise DockerFleetPolygonError("capsule set does not match fleet")
        self._results: dict[str, DroneResult] = {}
        self._result_ids: set[str] = set()

    def accept(self, result: DroneResult) -> None:
        result.validate()
        if result.mission_id != self.plan.mission_id or result.fleet_id != self.plan.fleet_id:
            raise DockerFleetPolygonError("result mission/fleet mismatch")
        capsule = self.capsules.get(result.drone_id)
        if capsule is None:
            raise DockerFleetPolygonError("unknown drone result")
        if (
            result.role,
            result.generation,
            result.work_unit_id,
            result.input_digest,
        ) != (
            capsule.role,
            capsule.generation,
            capsule.work_unit_id,
            capsule.input_digest,
        ):
            raise DockerFleetPolygonError("result binding mismatch")
        if result.drone_id in self._results or result.result_id in self._result_ids:
            raise DockerFleetPolygonError("duplicate/replayed terminal result")
        self._results[result.drone_id] = result
        self._result_ids.add(result.result_id)

    def finalize(self) -> dict[str, Any]:
        expected = {d.drone_id for d in self.plan.drones}
        if set(self._results) != expected:
            raise DockerFleetPolygonError("fleet result incomplete")
        rows = [self._results[k].canonical_dict() for k in sorted(self._results)]
        if any(row["status"] != "SUCCEEDED" for row in rows):
            raise DockerFleetPolygonError("fleet contains unsuccessful work unit")
        body = {
            "schema_version": "1.0.0",
            "mission_id": self.plan.mission_id,
            "fleet_id": self.plan.fleet_id,
            "run_id": self.plan.run_id,
            "plan_digest": self.plan.digest(),
            "results": rows,
        }
        body["fleet_result_digest"] = digest_domain(b"LION/FLEET-RESULT/P0", body)
        return body


def reconcile(
    plan: DockerFleetPlan,
    profile: DroneRuntimeProfile,
    observations: Iterable[ObservedContainer],
    fleet_result: Mapping[str, Any],
) -> DockerFleetReconciliationReceipt:
    plan.validate()
    profile.validate()
    observed = list(observations)
    mismatches: list[str] = []
    by_name: dict[str, ObservedContainer] = {}
    for item in observed:
        try:
            item.validate()
        except DockerFleetPolygonContractError as exc:
            mismatches.append(f"invalid-observation:{type(exc).__name__}:{exc}")
            continue
        if item.container_name in by_name:
            mismatches.append(f"duplicate-container:{item.container_name}")
        by_name[item.container_name] = item
    if len(observed) != len(plan.drones):
        mismatches.append(f"container-count:{len(observed)}!=5")
    for drone in plan.drones:
        item = by_name.get(drone.container_name)
        if item is None:
            mismatches.append(f"missing-container:{drone.container_name}")
            continue
        expected_labels = _labels(plan, resource_class="drone", drone=drone)
        for key, expected in expected_labels.items():
            if item.labels.get(key) != expected:
                mismatches.append(f"label:{drone.container_name}:{key}")
        if item.image_digest != plan.image_digest:
            mismatches.append(f"image:{drone.container_name}")
        if item.network_name != plan.network_name:
            mismatches.append(f"network:{drone.container_name}")
        if item.pids_limit != profile.pids_limit:
            mismatches.append(f"pids:{drone.container_name}")
        if item.memory_limit_bytes != profile.memory_limit_bytes:
            mismatches.append(f"memory:{drone.container_name}")
        if item.nano_cpus != profile.cpu_limit_millis * 1_000_000:
            mismatches.append(f"cpu:{drone.container_name}")
        if item.exit_code != 0:
            mismatches.append(f"exit:{drone.container_name}:{item.exit_code}")
        if item.restart_count != 0:
            mismatches.append(f"restart:{drone.container_name}:{item.restart_count}")
    expected_result_digest = fleet_result.get("fleet_result_digest")
    if not isinstance(expected_result_digest, str) or len(expected_result_digest) != 64:
        mismatches.append("fleet-result-digest")
        fleet_result_digest = digest_domain(b"LION/INVALID-FLEET-RESULT/P0", dict(fleet_result))
    else:
        body = dict(fleet_result)
        body.pop("fleet_result_digest", None)
        recalculated = digest_domain(b"LION/FLEET-RESULT/P0", body)
        fleet_result_digest = expected_result_digest
        if recalculated != expected_result_digest:
            mismatches.append("fleet-result-digest")
    observation_rows = [x.canonical_dict() for x in sorted(observed, key=lambda x: x.container_name)]
    observation_digest = digest_domain(b"LION/FLEET-OBSERVATION/P0", observation_rows)
    outcome = "MATCHED" if not mismatches else "MISMATCHED"
    return DockerFleetReconciliationReceipt(
        plan_digest=plan.digest(),
        observation_digest=observation_digest,
        fleet_result_digest=fleet_result_digest,
        outcome=outcome,
        mismatches=tuple(sorted(set(mismatches))),
    ).validate()


def canonical_capsule_bytes(capsule: MissionCapsule) -> bytes:
    return canonical_json(capsule.canonical_dict()) + b"\n"
