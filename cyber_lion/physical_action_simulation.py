from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import re
from typing import Any


SCHEMA_VERSION = "lion.physical-action-spec/v1.3-candidate"
PROVIDER_CLASS = "DIGITAL_TWIN_ONLY"
SIMULATION_MODE = "SIMULATION_ONLY"
NO_EFFECT = "NONE"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,255}$")


class PhysicalSimulationError(ValueError):
    pass


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _digest(domain: bytes, value: Any) -> str:
    return sha256(domain + _canon(value)).hexdigest()


def _text(value: Any, name: str, *, limit: int = 512) -> str:
    if type(value) is not str or not value or value != value.strip() or len(value) > limit:
        raise PhysicalSimulationError(f"{name} invalid")
    if any(ord(ch) > 0x7F for ch in value):
        raise PhysicalSimulationError(f"{name} must be ASCII")
    return value


def _sha(value: Any, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise PhysicalSimulationError(f"{name} must be sha256 hex")
    return value


def _number(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PhysicalSimulationError(f"{name} must be numeric")
    result = float(value)
    if result != result or result in {float("inf"), float("-inf")}:
        raise PhysicalSimulationError(f"{name} non-finite")
    if minimum is not None and result < minimum:
        raise PhysicalSimulationError(f"{name} below minimum")
    return result


@dataclass(frozen=True)
class Pose6D:
    frame_id: str
    linear_unit: str
    angular_unit: str
    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float

    def validate(self) -> "Pose6D":
        _text(self.frame_id, "pose.frame_id")
        if self.linear_unit != "m" or self.angular_unit != "rad":
            raise PhysicalSimulationError("canonical pose units must be m/rad")
        for name in ("x", "y", "z", "roll", "pitch", "yaw"):
            _number(getattr(self, name), f"pose.{name}")
        return self


@dataclass(frozen=True)
class CalibrationBinding:
    calibration_id: str
    calibration_digest: str
    frame_id: str
    linear_unit: str
    angular_unit: str
    revision: int

    def validate(self) -> "CalibrationBinding":
        _text(self.calibration_id, "calibration_id")
        _sha(self.calibration_digest, "calibration_digest")
        _text(self.frame_id, "calibration.frame_id")
        if self.linear_unit != "m" or self.angular_unit != "rad":
            raise PhysicalSimulationError("calibration units must be m/rad")
        if type(self.revision) is not int or self.revision < 1:
            raise PhysicalSimulationError("calibration revision invalid")
        return self


@dataclass(frozen=True)
class PhysicalAuthorityEnvelope:
    domain: str
    capability: str
    mode: str
    target_scope: str
    spatial_frame: str
    not_before_ms: int
    not_after_ms: int
    max_displacement_m: float
    max_speed_m_s: float
    max_force_n: float
    max_energy_j: float
    hardware_effect_capability: str = NO_EFFECT

    def validate(self) -> "PhysicalAuthorityEnvelope":
        if (self.domain, self.capability, self.mode) != (
            "physical.simulation",
            "simulate_pose_transition",
            SIMULATION_MODE,
        ):
            raise PhysicalSimulationError("simulation authority envelope mismatch")
        _text(self.target_scope, "authority.target_scope")
        _text(self.spatial_frame, "authority.spatial_frame")
        if type(self.not_before_ms) is not int or type(self.not_after_ms) is not int:
            raise PhysicalSimulationError("authority temporal scope invalid")
        if self.not_before_ms < 0 or self.not_after_ms <= self.not_before_ms:
            raise PhysicalSimulationError("authority temporal scope invalid")
        for name in ("max_displacement_m", "max_speed_m_s", "max_force_n", "max_energy_j"):
            _number(getattr(self, name), f"authority.{name}", minimum=0.0)
        if self.hardware_effect_capability != NO_EFFECT:
            raise PhysicalSimulationError("simulation envelope cannot carry hardware effect authority")
        return self


@dataclass(frozen=True)
class SafetyPreconditions:
    emergency_stop_available: bool
    protected_zone_clear: bool
    safety_controller_state: str
    sensors_current: bool
    heartbeat_current: bool
    calibration_current: bool

    def validate(self) -> "SafetyPreconditions":
        if self.emergency_stop_available is not True:
            raise PhysicalSimulationError("emergency stop unavailable")
        if self.protected_zone_clear is not True:
            raise PhysicalSimulationError("protected zone occupied")
        if self.safety_controller_state != "READY":
            raise PhysicalSimulationError("safety controller not READY")
        if self.sensors_current is not True:
            raise PhysicalSimulationError("sensor state stale")
        if self.heartbeat_current is not True:
            raise PhysicalSimulationError("heartbeat stale")
        if self.calibration_current is not True:
            raise PhysicalSimulationError("calibration stale")
        return self


@dataclass(frozen=True)
class PhysicalActionSpec:
    action_id: str
    intent_ref: str
    object_id: str
    operation: str
    source_pose: Pose6D
    translation_m: tuple[float, float, float]
    requested_speed_m_s: float
    requested_force_n: float
    requested_energy_j: float
    calibration: CalibrationBinding
    authority: PhysicalAuthorityEnvelope
    safety: SafetyPreconditions
    expected_simulation_effects: tuple[str, ...]
    forbidden_physical_effects: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> "PhysicalActionSpec":
        if self.schema_version != SCHEMA_VERSION:
            raise PhysicalSimulationError("physical action schema mismatch")
        if not _ID.fullmatch(_text(self.action_id, "action_id", limit=256)):
            raise PhysicalSimulationError("action_id invalid")
        _text(self.intent_ref, "intent_ref")
        _text(self.object_id, "object_id")
        if self.operation != "pose.translate":
            raise PhysicalSimulationError("unsupported simulation operation")
        self.source_pose.validate()
        self.calibration.validate()
        self.authority.validate()
        self.safety.validate()
        if type(self.translation_m) is not tuple or len(self.translation_m) != 3:
            raise PhysicalSimulationError("translation_m must be xyz tuple")
        delta = tuple(_number(x, "translation component") for x in self.translation_m)
        displacement = sum(x * x for x in delta) ** 0.5
        if displacement > self.authority.max_displacement_m:
            raise PhysicalSimulationError("requested displacement exceeds authority")
        for value, ceiling, label in (
            (self.requested_speed_m_s, self.authority.max_speed_m_s, "speed"),
            (self.requested_force_n, self.authority.max_force_n, "force"),
            (self.requested_energy_j, self.authority.max_energy_j, "energy"),
        ):
            if _number(value, f"requested_{label}", minimum=0.0) > ceiling:
                raise PhysicalSimulationError(f"requested {label} exceeds authority")
        if self.source_pose.frame_id != self.calibration.frame_id:
            raise PhysicalSimulationError("source pose/calibration frame mismatch")
        if self.authority.spatial_frame != self.calibration.frame_id:
            raise PhysicalSimulationError("authority/calibration frame mismatch")
        if self.authority.target_scope != self.object_id:
            raise PhysicalSimulationError("authority target substitution")
        for name, values in (
            ("expected_simulation_effects", self.expected_simulation_effects),
            ("forbidden_physical_effects", self.forbidden_physical_effects),
        ):
            if type(values) is not tuple or not values or len(values) != len(set(values)):
                raise PhysicalSimulationError(f"{name} invalid")
            for item in values:
                _text(item, name)
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["translation_m"] = list(self.translation_m)
        value["expected_simulation_effects"] = list(self.expected_simulation_effects)
        value["forbidden_physical_effects"] = list(self.forbidden_physical_effects)
        return value

    def digest(self) -> str:
        return _digest(b"LION/PHYSICAL-ACTION-SPEC/1\0", self.canonical_dict())


@dataclass(frozen=True)
class DigitalTwinSnapshot:
    snapshot_id: str
    object_id: str
    observed_pose: Pose6D
    calibration_digest: str
    calibration_revision: int
    safety: SafetyPreconditions
    snapshot_digest: str = ""

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        self.validate(check_digest=False)
        value = asdict(self)
        if not include_digest:
            value.pop("snapshot_digest")
        return value

    def compute_digest(self) -> str:
        return _digest(b"LION/DIGITAL-TWIN-SNAPSHOT/1\0", self.canonical_dict(include_digest=False))

    def sealed(self) -> "DigitalTwinSnapshot":
        return replace(self, snapshot_digest=self.compute_digest()).validate()

    def validate(self, *, check_digest: bool = True) -> "DigitalTwinSnapshot":
        _text(self.snapshot_id, "snapshot_id")
        _text(self.object_id, "snapshot.object_id")
        self.observed_pose.validate()
        _sha(self.calibration_digest, "snapshot.calibration_digest")
        if type(self.calibration_revision) is not int or self.calibration_revision < 1:
            raise PhysicalSimulationError("snapshot calibration revision invalid")
        self.safety.validate()
        if check_digest:
            _sha(self.snapshot_digest, "snapshot_digest")
            if self.snapshot_digest != self.compute_digest():
                raise PhysicalSimulationError("snapshot digest mismatch")
        return self


@dataclass(frozen=True)
class DigitalTwinProviderIdentity:
    provider_id: str
    provider_class: str
    implementation_digest: str
    hardware_effect_capability: str
    authority_minting_capability: str
    external_effect_capability: str

    def validate(self) -> "DigitalTwinProviderIdentity":
        _text(self.provider_id, "provider_id")
        _sha(self.implementation_digest, "implementation_digest")
        if self.provider_class != PROVIDER_CLASS:
            raise PhysicalSimulationError("non-digital-twin provider denied")
        if (
            self.hardware_effect_capability,
            self.authority_minting_capability,
            self.external_effect_capability,
        ) != (NO_EFFECT, NO_EFFECT, NO_EFFECT):
            raise PhysicalSimulationError("simulation provider carries prohibited capability")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/DIGITAL-TWIN-PROVIDER/1\0", asdict(self))


@dataclass(frozen=True)
class PhysicalSimulationReceipt:
    receipt_id: str
    action_spec_digest: str
    snapshot_digest: str
    provider_digest: str
    source_pose: Pose6D
    simulated_pose: Pose6D
    safety_checks: tuple[str, ...]
    simulation_state: str
    physical_effect: str
    hardware_safety_proof: str
    receipt_digest: str = ""

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value = asdict(self)
        value["safety_checks"] = list(self.safety_checks)
        if not include_digest:
            value.pop("receipt_digest")
        return value

    def compute_digest(self) -> str:
        return _digest(b"LION/PHYSICAL-SIMULATION-RECEIPT/1\0", self.canonical_dict(include_digest=False))

    def sealed(self) -> "PhysicalSimulationReceipt":
        return replace(self, receipt_digest=self.compute_digest()).validate()

    def validate(self) -> "PhysicalSimulationReceipt":
        _text(self.receipt_id, "receipt_id")
        for name in ("action_spec_digest", "snapshot_digest", "provider_digest"):
            _sha(getattr(self, name), name)
        self.source_pose.validate()
        self.simulated_pose.validate()
        if type(self.safety_checks) is not tuple or not self.safety_checks:
            raise PhysicalSimulationError("simulation safety evidence missing")
        if self.simulation_state != "SIMULATED_VERIFIED":
            raise PhysicalSimulationError("simulation receipt state invalid")
        if self.physical_effect != NO_EFFECT:
            raise PhysicalSimulationError("simulation receipt cannot claim physical effect")
        if self.hardware_safety_proof != "NOT_PROVEN_BY_SIMULATION":
            raise PhysicalSimulationError("simulation cannot claim hardware safety proof")
        if self.receipt_digest:
            _sha(self.receipt_digest, "receipt_digest")
            if self.receipt_digest != self.compute_digest():
                raise PhysicalSimulationError("simulation receipt digest mismatch")
        return self


class DigitalTwinSimulator:
    """Pure deterministic provider. No actuator, process, network, or filesystem capability."""

    def __init__(self, identity: DigitalTwinProviderIdentity) -> None:
        if type(identity) is not DigitalTwinProviderIdentity:
            raise PhysicalSimulationError("exact digital-twin provider identity required")
        self.identity = identity.validate()

    def simulate(
        self,
        spec: PhysicalActionSpec,
        snapshot: DigitalTwinSnapshot,
        *,
        observed_at_ms: int,
    ) -> PhysicalSimulationReceipt:
        if type(spec) is not PhysicalActionSpec or type(snapshot) is not DigitalTwinSnapshot:
            raise PhysicalSimulationError("exact physical simulation inputs required")
        spec.validate()
        snapshot.validate()
        if type(observed_at_ms) is not int:
            raise PhysicalSimulationError("observation time invalid")
        if not (spec.authority.not_before_ms <= observed_at_ms <= spec.authority.not_after_ms):
            raise PhysicalSimulationError("simulation authority stale")
        if snapshot.object_id != spec.object_id:
            raise PhysicalSimulationError("digital-twin object substitution")
        if snapshot.observed_pose != spec.source_pose:
            raise PhysicalSimulationError("digital-twin pose currentness mismatch")
        if (
            snapshot.calibration_digest,
            snapshot.calibration_revision,
        ) != (
            spec.calibration.calibration_digest,
            spec.calibration.revision,
        ):
            raise PhysicalSimulationError("digital-twin calibration substitution")
        if snapshot.safety != spec.safety:
            raise PhysicalSimulationError("digital-twin safety-state substitution")

        dx, dy, dz = spec.translation_m
        p = spec.source_pose
        simulated = Pose6D(
            frame_id=p.frame_id,
            linear_unit=p.linear_unit,
            angular_unit=p.angular_unit,
            x=round(p.x + dx, 12),
            y=round(p.y + dy, 12),
            z=round(p.z + dz, 12),
            roll=p.roll,
            pitch=p.pitch,
            yaw=p.yaw,
        ).validate()
        checks = (
            "authority-simulation-only",
            "calibration-exact",
            "coordinate-frame-exact",
            "units-canonical-m-rad",
            "emergency-stop-available",
            "protected-zone-clear",
            "safety-controller-ready",
            "sensor-state-current",
            "heartbeat-current",
            "requested-limits-within-envelope",
            "digital-twin-currentness-exact",
            "hardware-effect-none",
        )
        spec_digest = spec.digest()
        snapshot_digest = snapshot.snapshot_digest
        provider_digest = self.identity.digest()
        receipt_id = "physical-sim:" + sha256((spec_digest + snapshot_digest + provider_digest).encode("ascii")).hexdigest()
        return PhysicalSimulationReceipt(
            receipt_id=receipt_id,
            action_spec_digest=spec_digest,
            snapshot_digest=snapshot_digest,
            provider_digest=provider_digest,
            source_pose=p,
            simulated_pose=simulated,
            safety_checks=checks,
            simulation_state="SIMULATED_VERIFIED",
            physical_effect=NO_EFFECT,
            hardware_safety_proof="NOT_PROVEN_BY_SIMULATION",
        ).sealed()
