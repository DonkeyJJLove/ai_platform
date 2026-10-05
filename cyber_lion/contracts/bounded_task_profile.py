"""Bounded, non-effectful task profiles for LOCAL cognitive work.

A BoundedTaskProfile shapes a future work order. References to tool, resource
or workspace profiles are requirements only: they do not grant a capability,
select an executor, create RuntimeAdmission or authorize an effect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_ID = "lion.bounded-task-profile/v1"
PROFILE_VERSION = "1.0.0"

TASK_CLASSES = (
    "ARTIFACT_VERIFICATION",
    "BUILD_AND_TEST_SMALL",
    "CODE_GENERATION_SMALL",
    "CODE_REPAIR_BOUNDED",
    "DATA_TRANSFORMATION",
    "DEPENDENCY_INSPECTION",
    "DOCUMENT_UPDATE",
    "HYPOTHESIS_CHECK",
    "REPOSITORY_DELTA_ANALYSIS",
    "SEMANTIC_EXTRACTION",
    "STATIC_ANALYSIS",
    "TEST_AUTHORING",
)

_MAX_CONTEXT_BYTES = 16 * 1024 * 1024
_MAX_FILES = 128
_MAX_INPUT_TOKENS = 262_144
_MAX_OUTPUT_TOKENS = 65_536
_MAX_TIMEOUT_SECONDS = 3_600
_MAX_RETRY_BUDGET = 8

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")


class BoundedTaskProfileError(ValueError):
    pass


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise BoundedTaskProfileError(f"{name} invalid")
    return value


def _bounded_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BoundedTaskProfileError(f"{name} must be int")
    if not minimum <= value <= maximum:
        raise BoundedTaskProfileError(f"{name} outside bound")
    return value


def _canon(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BoundedTaskProfileError("canonical JSON required") from exc


@dataclass(frozen=True)
class BoundedTaskProfile:
    profile_id: str
    task_class: str
    input_schema_ref: str
    output_schema_ref: str
    max_context_bytes: int
    max_files: int
    max_input_tokens: int
    max_output_tokens: int
    tool_profile_ref: str
    resource_profile_ref: str
    workspace_profile_ref: str
    timeout_seconds: int
    retry_budget: int
    test_ref: str
    falsifier_ref: str
    profile_version: str = PROFILE_VERSION
    schema_id: str = SCHEMA_ID
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    external_effect: str = "NONE"
    profile_digest: str = ""

    def payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("profile_digest", None)
        return value

    def compute_digest(self) -> str:
        return sha256(b"LION/BOUNDED-TASK-PROFILE/1\0" + _canon(self.payload())).hexdigest()

    def validate(self, require_digest: bool = True) -> "BoundedTaskProfile":
        _id(self.profile_id, "profile_id")
        if self.task_class not in TASK_CLASSES:
            raise BoundedTaskProfileError("task_class invalid")
        for name in (
            "input_schema_ref",
            "output_schema_ref",
            "tool_profile_ref",
            "resource_profile_ref",
            "workspace_profile_ref",
            "test_ref",
            "falsifier_ref",
        ):
            _id(getattr(self, name), name)
        _bounded_int(self.max_context_bytes, "max_context_bytes", 1, _MAX_CONTEXT_BYTES)
        _bounded_int(self.max_files, "max_files", 1, _MAX_FILES)
        _bounded_int(self.max_input_tokens, "max_input_tokens", 1, _MAX_INPUT_TOKENS)
        _bounded_int(self.max_output_tokens, "max_output_tokens", 1, _MAX_OUTPUT_TOKENS)
        _bounded_int(self.timeout_seconds, "timeout_seconds", 1, _MAX_TIMEOUT_SECONDS)
        _bounded_int(self.retry_budget, "retry_budget", 0, _MAX_RETRY_BUDGET)
        if self.profile_version != PROFILE_VERSION or self.schema_id != SCHEMA_ID:
            raise BoundedTaskProfileError("profile schema/version mismatch")
        if (
            self.authority_effect != "NONE"
            or self.execution_effect != "NONE"
            or self.external_effect != "NONE"
        ):
            raise BoundedTaskProfileError("task profile cannot carry authority or effect")
        if require_digest:
            if not isinstance(self.profile_digest, str) or _HEX.fullmatch(self.profile_digest) is None:
                raise BoundedTaskProfileError("profile_digest invalid")
            if self.profile_digest != self.compute_digest():
                raise BoundedTaskProfileError("profile_digest mismatch")
        return self

    def sealed(self) -> "BoundedTaskProfile":
        return replace(self, profile_digest=self.compute_digest()).validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BoundedTaskProfile":
        if not isinstance(value, Mapping):
            raise BoundedTaskProfileError("profile mapping required")
        expected = frozenset(cls.__dataclass_fields__)
        if set(value) != expected:
            raise BoundedTaskProfileError("profile fields mismatch")
        try:
            return cls(**dict(value)).validate()
        except TypeError as exc:
            raise BoundedTaskProfileError("profile types invalid") from exc


def _profile(
    task_class: str,
    *,
    max_context_bytes: int,
    max_files: int,
    max_input_tokens: int,
    max_output_tokens: int,
    tool: str,
    resource: str,
    workspace: str,
    timeout: int,
    retries: int,
    input_schema: str = "schema:local-task-input/v1",
    output_schema: str = "schema:local-task-output/v1",
    test: str = "test-profile:bounded-result",
    falsifier: str = "falsifier-profile:contract-or-test-failure",
) -> BoundedTaskProfile:
    slug = task_class.lower().replace("_", "-")
    return BoundedTaskProfile(
        profile_id=f"local-task-profile:{slug}:v1",
        task_class=task_class,
        input_schema_ref=input_schema,
        output_schema_ref=output_schema,
        max_context_bytes=max_context_bytes,
        max_files=max_files,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        tool_profile_ref=tool,
        resource_profile_ref=resource,
        workspace_profile_ref=workspace,
        timeout_seconds=timeout,
        retry_budget=retries,
        test_ref=test,
        falsifier_ref=falsifier,
    ).sealed()


def default_catalog() -> tuple[BoundedTaskProfile, ...]:
    """Conservative source candidate catalog; refs remain requirements, not grants."""
    profiles = (
        _profile("CODE_GENERATION_SMALL", max_context_bytes=524_288, max_files=16,
                 max_input_tokens=12_000, max_output_tokens=4_096,
                 tool="tool-profile:bounded-python-build", resource="resource-profile:local-medium",
                 workspace="workspace-profile:ephemeral-source-rw", timeout=300, retries=2,
                 output_schema="schema:source-artifact/v1", test="test-profile:compile-and-unit"),
        _profile("CODE_REPAIR_BOUNDED", max_context_bytes=786_432, max_files=24,
                 max_input_tokens=16_000, max_output_tokens=4_096,
                 tool="tool-profile:bounded-python-build", resource="resource-profile:local-medium",
                 workspace="workspace-profile:ephemeral-source-rw", timeout=300, retries=2,
                 output_schema="schema:source-patch/v1", test="test-profile:targeted-regression"),
        _profile("TEST_AUTHORING", max_context_bytes=524_288, max_files=20,
                 max_input_tokens=12_000, max_output_tokens=4_096,
                 tool="tool-profile:source-read-test-write", resource="resource-profile:local-light",
                 workspace="workspace-profile:ephemeral-source-rw", timeout=240, retries=2,
                 output_schema="schema:test-artifact/v1", test="test-profile:test-discovery"),
        _profile("STATIC_ANALYSIS", max_context_bytes=1_048_576, max_files=48,
                 max_input_tokens=20_000, max_output_tokens=3_072,
                 tool="tool-profile:source-read-only", resource="resource-profile:local-light",
                 workspace="workspace-profile:ephemeral-readonly", timeout=180, retries=1,
                 output_schema="schema:analysis-findings/v1", test="test-profile:schema-validation"),
        _profile("SEMANTIC_EXTRACTION", max_context_bytes=1_048_576, max_files=32,
                 max_input_tokens=20_000, max_output_tokens=4_096,
                 tool="tool-profile:source-read-only", resource="resource-profile:local-light",
                 workspace="workspace-profile:ephemeral-readonly", timeout=180, retries=1,
                 output_schema="schema:semantic-extraction/v1", test="test-profile:schema-validation"),
        _profile("REPOSITORY_DELTA_ANALYSIS", max_context_bytes=2_097_152, max_files=64,
                 max_input_tokens=24_000, max_output_tokens=4_096,
                 tool="tool-profile:git-read-only", resource="resource-profile:local-medium",
                 workspace="workspace-profile:ephemeral-readonly", timeout=300, retries=1,
                 output_schema="schema:repository-delta-analysis/v1", test="test-profile:source-bound-delta"),
        _profile("DOCUMENT_UPDATE", max_context_bytes=1_048_576, max_files=24,
                 max_input_tokens=18_000, max_output_tokens=6_144,
                 tool="tool-profile:document-source-write", resource="resource-profile:local-light",
                 workspace="workspace-profile:ephemeral-source-rw", timeout=240, retries=2,
                 output_schema="schema:document-candidate/v1", test="test-profile:document-validation"),
        _profile("ARTIFACT_VERIFICATION", max_context_bytes=1_048_576, max_files=32,
                 max_input_tokens=16_000, max_output_tokens=3_072,
                 tool="tool-profile:artifact-read-test", resource="resource-profile:local-light",
                 workspace="workspace-profile:ephemeral-verifier", timeout=240, retries=1,
                 output_schema="schema:verification-result/v1", test="test-profile:independent-readback"),
        _profile("HYPOTHESIS_CHECK", max_context_bytes=1_048_576, max_files=32,
                 max_input_tokens=20_000, max_output_tokens=4_096,
                 tool="tool-profile:evidence-read-only", resource="resource-profile:local-light",
                 workspace="workspace-profile:ephemeral-readonly", timeout=240, retries=1,
                 output_schema="schema:hypothesis-check/v1", test="test-profile:falsifier-required"),
        _profile("DATA_TRANSFORMATION", max_context_bytes=2_097_152, max_files=32,
                 max_input_tokens=20_000, max_output_tokens=4_096,
                 tool="tool-profile:bounded-data-transform", resource="resource-profile:local-medium",
                 workspace="workspace-profile:ephemeral-data-rw", timeout=300, retries=2,
                 output_schema="schema:data-transform-result/v1", test="test-profile:deterministic-fixture"),
        _profile("BUILD_AND_TEST_SMALL", max_context_bytes=1_048_576, max_files=32,
                 max_input_tokens=20_000, max_output_tokens=4_096,
                 tool="tool-profile:bounded-python-build", resource="resource-profile:local-medium",
                 workspace="workspace-profile:ephemeral-source-rw", timeout=600, retries=2,
                 output_schema="schema:build-test-result/v1", test="test-profile:build-and-unit"),
        _profile("DEPENDENCY_INSPECTION", max_context_bytes=1_048_576, max_files=64,
                 max_input_tokens=18_000, max_output_tokens=3_072,
                 tool="tool-profile:source-and-manifest-read", resource="resource-profile:local-light",
                 workspace="workspace-profile:ephemeral-readonly", timeout=180, retries=1,
                 output_schema="schema:dependency-inspection/v1", test="test-profile:source-bound-dependency"),
    )
    by_class = {profile.task_class: profile for profile in profiles}
    if len(by_class) != len(profiles) or tuple(sorted(by_class)) != TASK_CLASSES:
        raise BoundedTaskProfileError("default catalog task-class coverage")
    return tuple(sorted(profiles, key=lambda profile: profile.task_class))


def catalog_payload(profiles: Sequence[BoundedTaskProfile] | None = None) -> dict[str, Any]:
    rows = tuple(profiles or default_catalog())
    if not rows:
        raise BoundedTaskProfileError("catalog cannot be empty")
    seen_ids: set[str] = set()
    seen_classes: set[str] = set()
    for profile in rows:
        profile.validate()
        if profile.profile_id in seen_ids or profile.task_class in seen_classes:
            raise BoundedTaskProfileError("catalog profile duplication")
        seen_ids.add(profile.profile_id)
        seen_classes.add(profile.task_class)
    value = {
        "schema": "lion.bounded-task-profile-catalog/v1",
        "profile_version": PROFILE_VERSION,
        "profiles": [profile.to_dict() for profile in sorted(rows, key=lambda p: p.task_class)],
        "authority_effect": "NONE",
        "execution_effect": "NONE",
    }
    value["catalog_digest"] = sha256(
        b"LION/BOUNDED-TASK-PROFILE-CATALOG/1\0" + _canon(value)
    ).hexdigest()
    return value


def load_catalog(path: str | Path) -> tuple[BoundedTaskProfile, ...]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundedTaskProfileError("catalog unavailable") from exc
    if not isinstance(raw, dict) or set(raw) != {
        "schema", "profile_version", "profiles", "authority_effect",
        "execution_effect", "catalog_digest",
    }:
        raise BoundedTaskProfileError("catalog fields mismatch")
    digest = raw.get("catalog_digest")
    payload = dict(raw)
    payload.pop("catalog_digest")
    expected = sha256(
        b"LION/BOUNDED-TASK-PROFILE-CATALOG/1\0" + _canon(payload)
    ).hexdigest()
    if not isinstance(digest, str) or digest != expected:
        raise BoundedTaskProfileError("catalog digest mismatch")
    if raw.get("schema") != "lion.bounded-task-profile-catalog/v1":
        raise BoundedTaskProfileError("catalog schema mismatch")
    if raw.get("profile_version") != PROFILE_VERSION:
        raise BoundedTaskProfileError("catalog version mismatch")
    if raw.get("authority_effect") != "NONE" or raw.get("execution_effect") != "NONE":
        raise BoundedTaskProfileError("catalog cannot carry effects")
    if not isinstance(raw.get("profiles"), list):
        raise BoundedTaskProfileError("profiles list required")
    profiles = tuple(BoundedTaskProfile.from_mapping(row) for row in raw["profiles"])
    current = catalog_payload(profiles)
    if current["catalog_digest"] != digest:
        raise BoundedTaskProfileError("catalog canonicalization mismatch")
    if tuple(profile.task_class for profile in profiles) != TASK_CLASSES:
        raise BoundedTaskProfileError("catalog task-class coverage mismatch")
    return profiles
