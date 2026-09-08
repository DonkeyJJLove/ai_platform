"""Immutable TEST_ONLY contracts for the LION Local Swarm P0 Docker polygon."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

SCHEMA_VERSION = "1.0.0"
P0_ROLES = ("architecture", "security", "runtime", "provenance", "falsifier")
P0_OPERATIONS = frozenset({"ARCHITECTURE_DIGEST", "SECURITY_INVARIANTS", "RUNTIME_BINDINGS", "PROVENANCE_RELATIONSHIPS", "FALSIFY_CLAIM"})
RECONCILIATION_OUTCOMES = frozenset({"MATCHED", "MISMATCHED", "UNKNOWN"})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_CONTAINER = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")


class DockerFleetPolygonContractError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: Any, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise DockerFleetPolygonContractError(f"{name} invalid")
    return value


def _identifier(value: Any, name: str) -> str:
    value = _text(value, name, limit=128)
    if not _SAFE_ID.fullmatch(value):
        raise DockerFleetPolygonContractError(f"{name} invalid")
    return value


def _container_name(value: Any, name: str) -> str:
    value = _text(value, name, limit=128)
    if not _SAFE_CONTAINER.fullmatch(value):
        raise DockerFleetPolygonContractError(f"{name} invalid")
    return value


def _sha40(value: Any, name: str) -> str:
    value = _text(value, name, limit=40)
    if not _SHA40.fullmatch(value):
        raise DockerFleetPolygonContractError(f"{name} must be full lowercase git SHA")
    return value


def _sha256(value: Any, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise DockerFleetPolygonContractError(f"{name} must be sha256 hex")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DockerFleetPolygonContractError(f"{name} invalid")
    return value


def _iso8601(value: str, name: str) -> datetime:
    _text(value, name, limit=64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DockerFleetPolygonContractError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DockerFleetPolygonContractError(f"{name} must contain timezone")
    return parsed.astimezone(timezone.utc)


def digest_domain(domain: bytes, value: Any) -> str:
    return sha256(domain + b"\0" + canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class DroneRuntimeProfile:
    profile_id: str
    architecture: str = "linux/amd64"
    uid: int = 65532
    gid: int = 65532
    read_only_rootfs: bool = True
    no_new_privileges: bool = True
    cap_drop: Tuple[str, ...] = ("ALL",)
    pids_limit: int = 64
    memory_limit_bytes: int = 134217728
    cpu_limit_millis: int = 200
    tmpfs_limit_bytes: int = 16777216
    runtime_shell: bool = False
    package_manager: bool = False
    persistent_state: bool = False
    internet_egress: bool = False
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> "DroneRuntimeProfile":
        if self.schema_version != SCHEMA_VERSION:
            raise DockerFleetPolygonContractError("runtime profile schema mismatch")
        _identifier(self.profile_id, "profile_id")
        if self.architecture != "linux/amd64":
            raise DockerFleetPolygonContractError("P0 architecture must be linux/amd64")
        if (self.uid, self.gid) != (65532, 65532):
            raise DockerFleetPolygonContractError("P0 runtime must use uid/gid 65532")
        if (self.read_only_rootfs, self.no_new_privileges) != (True, True):
            raise DockerFleetPolygonContractError("runtime hardening missing")
        if self.cap_drop != ("ALL",):
            raise DockerFleetPolygonContractError("all Linux capabilities must be dropped")
        for name in ("pids_limit", "memory_limit_bytes", "cpu_limit_millis", "tmpfs_limit_bytes"):
            _positive_int(getattr(self, name), name)
        if self.runtime_shell or self.package_manager or self.persistent_state or self.internet_egress:
            raise DockerFleetPolygonContractError("P0 runtime must remain minimal and offline")
        return self

    def digest(self) -> str:
        self.validate()
        payload = asdict(self)
        payload["cap_drop"] = list(self.cap_drop)
        return digest_domain(b"LION/DOCKER-RUNTIME-PROFILE/P0", payload)


@dataclass(frozen=True)
class MissionCapsule:
    schema_version: str
    mission_id: str
    fleet_id: str
    drone_id: str
    role: str
    generation: int
    work_unit_id: str
    issued_at: str
    expires_at: str
    operation: str
    input_payload: Mapping[str, Any]
    input_digest: str
    policy_digest: str
    capsule_digest: str

    @classmethod
    def issue(cls, *, mission_id: str, fleet_id: str, drone_id: str, role: str, generation: int, work_unit_id: str, issued_at: str, expires_at: str, operation: str, input_payload: Mapping[str, Any], policy_digest: str) -> "MissionCapsule":
        input_digest = digest_domain(b"LION/MISSION-INPUT/P0", dict(input_payload))
        unsigned = {"schema_version": SCHEMA_VERSION, "mission_id": mission_id, "fleet_id": fleet_id, "drone_id": drone_id, "role": role, "generation": generation, "work_unit_id": work_unit_id, "issued_at": issued_at, "expires_at": expires_at, "operation": operation, "input_payload": dict(input_payload), "input_digest": input_digest, "policy_digest": policy_digest}
        capsule_digest = digest_domain(b"LION/MISSION-CAPSULE/P0", unsigned)
        return cls(**unsigned, capsule_digest=capsule_digest)

    def unsigned_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "mission_id": self.mission_id, "fleet_id": self.fleet_id, "drone_id": self.drone_id, "role": self.role, "generation": self.generation, "work_unit_id": self.work_unit_id, "issued_at": self.issued_at, "expires_at": self.expires_at, "operation": self.operation, "input_payload": dict(self.input_payload), "input_digest": self.input_digest, "policy_digest": self.policy_digest}

    def validate(self, *, now: datetime | None = None) -> "MissionCapsule":
        if self.schema_version != SCHEMA_VERSION:
            raise DockerFleetPolygonContractError("capsule schema mismatch")
        for name in ("mission_id", "fleet_id", "drone_id", "work_unit_id"):
            _identifier(getattr(self, name), name)
        if self.role not in P0_ROLES:
            raise DockerFleetPolygonContractError("unknown P0 role")
        _positive_int(self.generation, "generation")
        if self.operation not in P0_OPERATIONS:
            raise DockerFleetPolygonContractError("operation not allowed")
        _sha256(self.policy_digest, "policy_digest"); _sha256(self.input_digest, "input_digest"); _sha256(self.capsule_digest, "capsule_digest")
        issued = _iso8601(self.issued_at, "issued_at"); expires = _iso8601(self.expires_at, "expires_at")
        if expires <= issued:
            raise DockerFleetPolygonContractError("capsule expiry invalid")
        if now is not None and now.astimezone(timezone.utc) >= expires:
            raise DockerFleetPolygonContractError("capsule expired")
        if digest_domain(b"LION/MISSION-INPUT/P0", dict(self.input_payload)) != self.input_digest:
            raise DockerFleetPolygonContractError("input digest mismatch")
        if digest_domain(b"LION/MISSION-CAPSULE/P0", self.unsigned_dict()) != self.capsule_digest:
            raise DockerFleetPolygonContractError("capsule digest mismatch")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate(); value = self.unsigned_dict(); value["capsule_digest"] = self.capsule_digest; return value


@dataclass(frozen=True)
class DockerDroneBinding:
    drone_id: str
    role: str
    generation: int
    executor_id: str
    lease_id: str
    container_name: str
    image_digest: str
    capsule_digest: str

    def validate(self) -> "DockerDroneBinding":
        _identifier(self.drone_id, "drone_id")
        if self.role not in P0_ROLES: raise DockerFleetPolygonContractError("unknown P0 role")
        _positive_int(self.generation, "generation"); _identifier(self.executor_id, "executor_id"); _sha256(self.lease_id, "lease_id"); _container_name(self.container_name, "container_name"); _sha256(self.image_digest, "image_digest"); _sha256(self.capsule_digest, "capsule_digest")
        return self

    def canonical_dict(self) -> dict[str, Any]: self.validate(); return asdict(self)


@dataclass(frozen=True)
class DockerFleetPlan:
    mission_id: str
    fleet_id: str
    run_id: str
    repository: str
    source_head: str
    source_tree: str
    network_name: str
    image_reference: str
    image_digest: str
    runtime_profile_digest: str
    drones: Tuple[DockerDroneBinding, ...]
    trust_class: str = "TEST_ONLY"
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> "DockerFleetPlan":
        if self.schema_version != SCHEMA_VERSION or self.trust_class != "TEST_ONLY": raise DockerFleetPolygonContractError("fleet schema/trust invalid")
        for name in ("mission_id", "fleet_id", "run_id"): _identifier(getattr(self, name), name)
        if self.repository != "DonkeyJJLove/ai_platform": raise DockerFleetPolygonContractError("P0 repository mismatch")
        _sha40(self.source_head, "source_head"); _sha40(self.source_tree, "source_tree"); _container_name(self.network_name, "network_name"); _text(self.image_reference, "image_reference", limit=512); _sha256(self.image_digest, "image_digest"); _sha256(self.runtime_profile_digest, "runtime_profile_digest")
        if type(self.drones) is not tuple or len(self.drones) != 5: raise DockerFleetPolygonContractError("P0 requires exactly five drones")
        for drone in self.drones:
            drone.validate()
            if drone.image_digest != self.image_digest: raise DockerFleetPolygonContractError("drone image binding mismatch")
        if tuple(sorted(d.role for d in self.drones)) != tuple(sorted(P0_ROLES)): raise DockerFleetPolygonContractError("P0 roles incomplete")
        for attr in ("drone_id", "container_name", "lease_id"):
            values = [getattr(d, attr) for d in self.drones]
            if len(values) != len(set(values)): raise DockerFleetPolygonContractError(f"duplicate {attr}")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate(); value = asdict(self); value["drones"] = [d.canonical_dict() for d in self.drones]; return value

    def digest(self) -> str: return digest_domain(b"LION/DOCKER-FLEET-PLAN/P0", self.canonical_dict())


@dataclass(frozen=True)
class DroneResult:
    result_id: str
    mission_id: str
    fleet_id: str
    drone_id: str
    role: str
    generation: int
    work_unit_id: str
    status: str
    result: Mapping[str, Any]
    input_digest: str
    result_digest: str
    started_at: str
    completed_at: str
    evidence: Tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> "DroneResult":
        if self.schema_version != SCHEMA_VERSION: raise DockerFleetPolygonContractError("result schema mismatch")
        _sha256(self.result_id, "result_id")
        for name in ("mission_id", "fleet_id", "drone_id", "work_unit_id"): _identifier(getattr(self, name), name)
        if self.role not in P0_ROLES or self.status not in {"SUCCEEDED", "FAILED", "DENIED"}: raise DockerFleetPolygonContractError("result role/status invalid")
        _positive_int(self.generation, "generation"); _sha256(self.input_digest, "input_digest"); _sha256(self.result_digest, "result_digest"); _iso8601(self.started_at, "started_at"); _iso8601(self.completed_at, "completed_at")
        if type(self.evidence) is not tuple or len(set(self.evidence)) != len(self.evidence): raise DockerFleetPolygonContractError("result evidence invalid")
        if digest_domain(b"LION/DRONE-RESULT-BODY/P0", dict(self.result)) != self.result_digest: raise DockerFleetPolygonContractError("result digest mismatch")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate(); value = asdict(self); value["result"] = dict(self.result); value["evidence"] = list(self.evidence); return value


@dataclass(frozen=True)
class ObservedContainer:
    container_id: str
    container_name: str
    image_digest: str
    labels: Mapping[str, str]
    user: str
    read_only_rootfs: bool
    cap_drop: Tuple[str, ...]
    security_opt: Tuple[str, ...]
    pids_limit: int
    memory_limit_bytes: int
    nano_cpus: int
    network_name: str
    published_ports: Tuple[str, ...]
    docker_socket_mounted: bool
    exit_code: int
    restart_count: int

    def validate(self) -> "ObservedContainer":
        if not isinstance(self.container_id, str) or len(self.container_id) < 12 or not re.fullmatch(r"[0-9a-f]+", self.container_id): raise DockerFleetPolygonContractError("container_id invalid")
        _container_name(self.container_name, "container_name"); _sha256(self.image_digest, "image_digest")
        if not isinstance(self.labels, Mapping): raise DockerFleetPolygonContractError("labels invalid")
        if self.user != "65532:65532" or not self.read_only_rootfs: raise DockerFleetPolygonContractError("container hardening mismatch")
        if self.cap_drop != ("ALL",) or "no-new-privileges" not in self.security_opt: raise DockerFleetPolygonContractError("container privilege boundary mismatch")
        for name in ("pids_limit", "memory_limit_bytes", "nano_cpus"): _positive_int(getattr(self, name), name)
        _container_name(self.network_name, "network_name")
        if type(self.published_ports) is not tuple or self.published_ports: raise DockerFleetPolygonContractError("host ports are forbidden")
        if self.docker_socket_mounted: raise DockerFleetPolygonContractError("Docker socket mount forbidden")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int): raise DockerFleetPolygonContractError("exit_code invalid")
        if isinstance(self.restart_count, bool) or not isinstance(self.restart_count, int) or self.restart_count < 0: raise DockerFleetPolygonContractError("restart_count invalid")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate(); value = asdict(self); value["labels"] = dict(self.labels); value["cap_drop"] = list(self.cap_drop); value["security_opt"] = list(self.security_opt); value["published_ports"] = list(self.published_ports); return value


@dataclass(frozen=True)
class DockerFleetReconciliationReceipt:
    plan_digest: str
    observation_digest: str
    fleet_result_digest: str
    outcome: str
    mismatches: Tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> "DockerFleetReconciliationReceipt":
        if self.schema_version != SCHEMA_VERSION: raise DockerFleetPolygonContractError("reconciliation schema mismatch")
        for name in ("plan_digest", "observation_digest", "fleet_result_digest"): _sha256(getattr(self, name), name)
        if self.outcome not in RECONCILIATION_OUTCOMES: raise DockerFleetPolygonContractError("reconciliation outcome invalid")
        if type(self.mismatches) is not tuple or len(set(self.mismatches)) != len(self.mismatches): raise DockerFleetPolygonContractError("mismatches invalid")
        if self.outcome == "MATCHED" and self.mismatches: raise DockerFleetPolygonContractError("MATCHED cannot contain mismatches")
        if self.outcome == "MISMATCHED" and not self.mismatches: raise DockerFleetPolygonContractError("MISMATCHED requires evidence")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate(); value = asdict(self); value["mismatches"] = list(self.mismatches); return value
