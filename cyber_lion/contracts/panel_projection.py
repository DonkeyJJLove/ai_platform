"""Bounded read-model projection contracts for LION control surfaces.

These objects are non-effectful UI/read-model carriers. They bind projection
currentness and source references without becoming a source of truth,
authority, scheduler state, or execution semantics.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, ClassVar, Mapping

SCHEMA_ID = "lion.control-read-projection/v1"
AUTHORITY_EFFECT = "NONE"
MAX_PAYLOAD_BYTES = 262_144
CURRENTNESS_STATES = frozenset({"CURRENT", "STALE", "UNKNOWN", "OBSERVATION_UNAVAILABLE"})
_SHA = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}$")


class ProjectionError(ValueError):
    pass


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProjectionError("strict JSON required") from exc


def _text(value: Any, name: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        raise ProjectionError(name)
    return value


def _canonical_utc(value: Any) -> str:
    value = _text(value, "observed_at", maximum=64)
    if not value.endswith("Z"):
        raise ProjectionError("observed_at")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProjectionError("observed_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ProjectionError("observed_at")
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise ProjectionError("observed_at")
    return value


def _sorted_unique(values: Any, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        raise ProjectionError(name)
    out = tuple(_text(x, name, maximum=512) for x in values)
    if not allow_empty and not out:
        raise ProjectionError(name)
    if len(out) != len(set(out)) or out != tuple(sorted(out)):
        raise ProjectionError(name)
    return out


@dataclass(frozen=True)
class ProjectionHeader:
    schema_id: str
    observed_at: str
    source_refs: tuple[str, ...]
    source_revision: str
    projection_version: str
    currentness: str
    gaps: tuple[str, ...]
    authority_effect: str = AUTHORITY_EFFECT

    def validate(self) -> "ProjectionHeader":
        if self.schema_id != SCHEMA_ID:
            raise ProjectionError("schema_id")
        _canonical_utc(self.observed_at)
        _sorted_unique(self.source_refs, "source_refs")
        revision = _text(self.source_revision, "source_revision", maximum=256)
        if _REVISION.fullmatch(revision) is None:
            raise ProjectionError("source_revision")
        _text(self.projection_version, "projection_version", maximum=64)
        if self.currentness not in CURRENTNESS_STATES:
            raise ProjectionError("currentness")
        _sorted_unique(self.gaps, "gaps", allow_empty=True)
        if self.authority_effect != AUTHORITY_EFFECT:
            raise ProjectionError("authority_effect")
        return self

    @classmethod
    def build(
        cls,
        *,
        observed_at: str,
        source_refs: list[str] | tuple[str, ...],
        source_revision: str,
        projection_version: str,
        currentness: str,
        gaps: list[str] | tuple[str, ...] = (),
    ) -> "ProjectionHeader":
        refs = tuple(sorted(source_refs))
        gap_values = tuple(sorted(gaps))
        return cls(
            SCHEMA_ID,
            observed_at,
            refs,
            source_revision,
            projection_version,
            currentness,
            gap_values,
        ).validate()


@dataclass(frozen=True)
class _ProjectionBase:
    header: ProjectionHeader
    payload_json: str
    projection_digest: str = ""

    KIND: ClassVar[str] = "BASE"
    DIGEST_DOMAIN: ClassVar[bytes] = b"LION/CONTROL-READ-PROJECTION/1\0"

    def payload(self) -> dict[str, Any]:
        try:
            value = json.loads(self.payload_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ProjectionError("payload_json") from exc
        if not isinstance(value, dict):
            raise ProjectionError("payload object required")
        canonical = _canonical(value).decode("utf-8")
        if canonical != self.payload_json:
            raise ProjectionError("payload_json not canonical")
        if len(canonical.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ProjectionError("payload too large")
        return value

    def digest_payload(self) -> dict[str, Any]:
        self.header.validate()
        return {
            "kind": self.KIND,
            "header": asdict(self.header),
            "payload": self.payload(),
        }

    def compute_digest(self) -> str:
        return sha256(self.DIGEST_DOMAIN + _canonical(self.digest_payload())).hexdigest()

    def validate(self, *, require_digest: bool = True):
        self.header.validate()
        self.payload()
        if self.KIND not in PROJECTION_TYPES:
            raise ProjectionError("projection kind")
        if require_digest:
            if not isinstance(self.projection_digest, str) or _SHA.fullmatch(self.projection_digest) is None:
                raise ProjectionError("projection_digest")
            if self.projection_digest != self.compute_digest():
                raise ProjectionError("projection digest mismatch")
        elif self.projection_digest and _SHA.fullmatch(self.projection_digest) is None:
            raise ProjectionError("projection_digest")
        return self

    def sealed(self):
        self.validate(require_digest=False)
        return replace(self, projection_digest=self.compute_digest()).validate()

    @classmethod
    def build(cls, header: ProjectionHeader, payload: Mapping[str, Any]):
        if not isinstance(header, ProjectionHeader):
            raise ProjectionError("header")
        if not isinstance(payload, Mapping):
            raise ProjectionError("payload")
        raw = _canonical(dict(payload))
        if len(raw) > MAX_PAYLOAD_BYTES:
            raise ProjectionError("payload too large")
        return cls(header=header.validate(), payload_json=raw.decode("utf-8")).sealed()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "kind": self.KIND,
            "header": asdict(self.header),
            "payload": self.payload(),
            "projection_digest": self.projection_digest,
        }


@dataclass(frozen=True)
class MissionProjection(_ProjectionBase):
    KIND: ClassVar[str] = "MISSION"


@dataclass(frozen=True)
class SwarmProjection(_ProjectionBase):
    KIND: ClassVar[str] = "SWARM"


@dataclass(frozen=True)
class ModelProjection(_ProjectionBase):
    KIND: ClassVar[str] = "MODEL"


@dataclass(frozen=True)
class FederationProjection(_ProjectionBase):
    KIND: ClassVar[str] = "FEDERATION"


@dataclass(frozen=True)
class RepositoryProjection(_ProjectionBase):
    KIND: ClassVar[str] = "REPOSITORY"


@dataclass(frozen=True)
class ArtifactProjection(_ProjectionBase):
    KIND: ClassVar[str] = "ARTIFACT"


@dataclass(frozen=True)
class TimelineProjection(_ProjectionBase):
    KIND: ClassVar[str] = "TIMELINE"


@dataclass(frozen=True)
class CommunicationProjection(_ProjectionBase):
    KIND: ClassVar[str] = "COMMUNICATION"


@dataclass(frozen=True)
class EvolutionProjection(_ProjectionBase):
    KIND: ClassVar[str] = "EVOLUTION"


PROJECTION_TYPES = {
    cls.KIND: cls
    for cls in (
        MissionProjection,
        SwarmProjection,
        ModelProjection,
        FederationProjection,
        RepositoryProjection,
        ArtifactProjection,
        TimelineProjection,
        CommunicationProjection,
        EvolutionProjection,
    )
}


def projection_from_mapping(value: Mapping[str, Any]) -> _ProjectionBase:
    if not isinstance(value, Mapping) or set(value) != {"kind", "header", "payload", "projection_digest"}:
        raise ProjectionError("projection fields")
    kind = value.get("kind")
    cls = PROJECTION_TYPES.get(kind)
    if cls is None:
        raise ProjectionError("projection kind")
    h = value.get("header")
    if not isinstance(h, Mapping) or set(h) != {
        "schema_id",
        "observed_at",
        "source_refs",
        "source_revision",
        "projection_version",
        "currentness",
        "gaps",
        "authority_effect",
    }:
        raise ProjectionError("header fields")
    header = ProjectionHeader(
        schema_id=h["schema_id"],
        observed_at=h["observed_at"],
        source_refs=tuple(h["source_refs"]) if isinstance(h["source_refs"], (list, tuple)) else h["source_refs"],
        source_revision=h["source_revision"],
        projection_version=h["projection_version"],
        currentness=h["currentness"],
        gaps=tuple(h["gaps"]) if isinstance(h["gaps"], (list, tuple)) else h["gaps"],
        authority_effect=h["authority_effect"],
    ).validate()
    payload = value.get("payload")
    if not isinstance(payload, Mapping):
        raise ProjectionError("payload")
    obj = cls(
        header=header,
        payload_json=_canonical(dict(payload)).decode("utf-8"),
        projection_digest=value.get("projection_digest"),
    )
    return obj.validate()
