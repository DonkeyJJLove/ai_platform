from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping

from .gap import classify_projection_currentness

SCHEMA_VERSION = "lion.truth-projection/v1.4-a0-candidate"
PLANES = frozenset({"AS_IS", "CANDIDATE", "TARGET", "UNKNOWN"})
CANDIDATE_STATUSES = frozenset({"CURRENT_MASTER_BASE_CANDIDATE", "CURRENT_STACKED_CANDIDATE", "STALE_BASE_CANDIDATE"})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
SUBJECT_DIGEST_DOMAIN = "LION/TRUTH-SUBJECT/1"
SUBJECT_DIGEST_PREFIX = b"LION/TRUTH-SUBJECT/1\0"
CURRENTNESS_MODE = "DERIVED_SUBJECT_DIGEST"
CARRIER_PATHS = frozenset({
    "LION/architecture/canonical-state-v1-3-candidate.json",
    "cyber_lion/registry/repositories.json",
})
_ALLOWED_MODE_TYPES = frozenset({
    ("100644", "blob"),
    ("100755", "blob"),
    ("120000", "blob"),
    ("160000", "commit"),
})
_RECORD_KEYS = frozenset({
    "id",
    "plane",
    "status",
    "evidence_refs",
    "integrated",
    "pr",
    "head",
    "tree",
    "base_head",
})


class TruthProjectionError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class SubjectEntry:
    path: str
    mode: str
    object_type: str
    object_sha: str

    def validate(self) -> "SubjectEntry":
        _canonical_subject_path(self.path)
        if (self.mode, self.object_type) not in _ALLOWED_MODE_TYPES:
            raise TruthProjectionError(f"unsupported Git leaf mode/type: {self.mode} {self.object_type}")
        if not _SHA40.fullmatch(self.object_sha):
            raise TruthProjectionError("Git leaf object SHA must be exact lowercase SHA-1")
        return self


def _canonical_subject_path(path: str) -> str:
    if not isinstance(path, str) or not path or "\x00" in path or "\\" in path or path.startswith("/"):
        raise TruthProjectionError("subject path is not canonical")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise TruthProjectionError("subject path is not canonical")
    path.encode("utf-8", "strict")
    return path


def _carrier_paths(carrier_paths: Iterable[str]) -> frozenset[str]:
    paths = frozenset(_canonical_subject_path(path) for path in carrier_paths)
    if not paths:
        raise TruthProjectionError("carrier path set cannot be empty")
    return paths


def canonical_subject_entries(
    entries: Iterable[SubjectEntry],
    *,
    carrier_paths: Iterable[str] = CARRIER_PATHS,
) -> tuple[SubjectEntry, ...]:
    carriers = _carrier_paths(carrier_paths)
    by_path: dict[str, SubjectEntry] = {}
    for raw in entries:
        if not isinstance(raw, SubjectEntry):
            raise TruthProjectionError("subject entry must be SubjectEntry")
        entry = raw.validate()
        if entry.path in by_path:
            raise TruthProjectionError(f"duplicate subject path: {entry.path}")
        by_path[entry.path] = entry
    missing = sorted(carriers - set(by_path), key=lambda item: item.encode("utf-8"))
    if missing:
        raise TruthProjectionError(f"truth carrier missing from Git tree: {missing[0]}")
    for carrier in carriers:
        entry = by_path[carrier]
        if entry.mode != "100644" or entry.object_type != "blob":
            raise TruthProjectionError(f"truth carrier must be regular non-executable blob: {carrier}")
    return tuple(
        sorted(
            (entry for path, entry in by_path.items() if path not in carriers),
            key=lambda entry: entry.path.encode("utf-8"),
        )
    )


def canonical_subject_payload(
    entries: Iterable[SubjectEntry],
    *,
    carrier_paths: Iterable[str] = CARRIER_PATHS,
) -> bytes:
    value = [
        {
            "path": entry.path,
            "mode": entry.mode,
            "git_object_type": entry.object_type,
            "git_object_sha": entry.object_sha,
        }
        for entry in canonical_subject_entries(entries, carrier_paths=carrier_paths)
    ]
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def subject_digest(
    entries: Iterable[SubjectEntry],
    *,
    carrier_paths: Iterable[str] = CARRIER_PATHS,
) -> str:
    return sha256(
        SUBJECT_DIGEST_PREFIX + canonical_subject_payload(entries, carrier_paths=carrier_paths)
    ).hexdigest()


def derive_subject_currentness(declared_subject_digest: str, observed_subject_digest: str) -> str:
    declared = _sha256(declared_subject_digest, "declared_subject_digest")
    observed = _sha256(observed_subject_digest, "observed_subject_digest")
    return "CURRENT" if declared == observed else "STALE"


def _exact_keys(value: Mapping[str, Any], expected: set[str] | frozenset[str], label: str) -> None:
    actual = set(value)
    if actual != set(expected):
        raise TruthProjectionError(f"{label} keys are not canonical")


def _sha40(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not _SHA40.fullmatch(value):
        raise TruthProjectionError(f"{label} must be exact lowercase SHA-1")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise TruthProjectionError(f"{label} is invalid")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise TruthProjectionError(f"{label} must be exact lowercase SHA-256")
    return value


def validate_truth_projection(
    payload: Mapping[str, Any],
    *,
    current_head: str,
    current_tree: str,
    current_subject_digest: str,
) -> Mapping[str, Any]:
    """Validate an exact AS-IS/CANDIDATE/TARGET truth projection.

    The projection is descriptive only. It grants no authority and cannot promote
    a candidate into AS-IS. Baseline currentness is derived from a non-self-referential
    semantic subject digest. Exact Git head/tree remain external revision evidence.
    Historical projections still self-degrade to STALE on material drift.
    """
    if not isinstance(payload, Mapping):
        raise TruthProjectionError("truth projection must be an object")
    _exact_keys(payload, {"schema_version", "baseline", "records", "historical_projections"}, "root")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise TruthProjectionError("truth projection schema_version mismatch")

    _sha40(current_head, "current_head")
    _sha40(current_tree, "current_tree")
    observed_subject_digest = _sha256(current_subject_digest, "current_subject_digest")

    baseline = payload["baseline"]
    if not isinstance(baseline, Mapping):
        raise TruthProjectionError("baseline must be an object")
    _exact_keys(
        baseline,
        {"repository", "branch", "subject_digest_domain", "subject_digest", "currentness_mode"},
        "baseline",
    )
    _text(baseline["repository"], "baseline.repository")
    _text(baseline["branch"], "baseline.branch")
    if baseline["subject_digest_domain"] != SUBJECT_DIGEST_DOMAIN:
        raise TruthProjectionError("baseline subject_digest_domain mismatch")
    if baseline["currentness_mode"] != CURRENTNESS_MODE:
        raise TruthProjectionError("baseline currentness_mode mismatch")
    declared_subject_digest = _sha256(baseline["subject_digest"], "baseline.subject_digest")
    if derive_subject_currentness(declared_subject_digest, observed_subject_digest) != "CURRENT":
        raise TruthProjectionError(
            "baseline subject digest contradiction: "
            f"declared={declared_subject_digest} observed={observed_subject_digest} expected=STALE"
        )

    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise TruthProjectionError("records must be a non-empty array")
    seen: set[str] = set()
    for index, record in enumerate(records):
        label = f"records[{index}]"
        if not isinstance(record, Mapping):
            raise TruthProjectionError(f"{label} must be an object")
        _exact_keys(record, _RECORD_KEYS, label)
        record_id = _text(record["id"], f"{label}.id")
        if record_id in seen:
            raise TruthProjectionError(f"duplicate truth record: {record_id}")
        seen.add(record_id)
        plane = record["plane"]
        if plane not in PLANES:
            raise TruthProjectionError(f"unknown truth plane: {plane}")
        status = _text(record["status"], f"{label}.status")
        evidence_refs = record["evidence_refs"]
        if not isinstance(evidence_refs, list) or any(not isinstance(item, str) or not item.strip() for item in evidence_refs):
            raise TruthProjectionError(f"{label}.evidence_refs must be strings")
        if len(set(evidence_refs)) != len(evidence_refs):
            raise TruthProjectionError(f"{label}.evidence_refs must be unique")
        if not isinstance(record["integrated"], bool):
            raise TruthProjectionError(f"{label}.integrated must be boolean")

        if plane == "AS_IS":
            if not record["integrated"]:
                raise TruthProjectionError(f"AS_IS record is not integrated: {record_id}")
            if not evidence_refs:
                raise TruthProjectionError(f"AS_IS record lacks implementation evidence: {record_id}")
            if any(record[field] is not None for field in ("pr", "head", "tree", "base_head")):
                raise TruthProjectionError(f"AS_IS record cannot be represented by PR candidate identity: {record_id}")
        elif plane == "CANDIDATE":
            if record["integrated"]:
                raise TruthProjectionError(f"candidate silently promoted to integrated: {record_id}")
            if not isinstance(record["pr"], int) or isinstance(record["pr"], bool) or record["pr"] <= 0:
                raise TruthProjectionError(f"candidate requires exact PR number: {record_id}")
            _sha40(record["head"], f"{label}.head")
            _sha40(record["tree"], f"{label}.tree")
            base_head = _sha40(record["base_head"], f"{label}.base_head")
            if status not in CANDIDATE_STATUSES:
                raise TruthProjectionError(f"candidate currentness status is not canonical: {record_id}")
            if status == "CURRENT_MASTER_BASE_CANDIDATE" and base_head != current_head:
                raise TruthProjectionError(f"current master-base candidate is stale: {record_id}")
            if status in {"CURRENT_STACKED_CANDIDATE", "STALE_BASE_CANDIDATE"} and base_head == current_head:
                raise TruthProjectionError(f"candidate base currentness contradiction: {record_id}")
            if not evidence_refs:
                raise TruthProjectionError(f"candidate lacks exact evidence: {record_id}")
        elif plane == "TARGET":
            if record["integrated"]:
                raise TruthProjectionError(f"TARGET cannot be integrated: {record_id}")
            if evidence_refs:
                raise TruthProjectionError(f"TARGET cannot carry live implementation evidence: {record_id}")
            if any(record[field] is not None for field in ("pr", "head", "tree", "base_head")):
                raise TruthProjectionError(f"TARGET cannot carry candidate Git identity: {record_id}")
        else:
            if record["integrated"]:
                raise TruthProjectionError(f"UNKNOWN cannot be integrated by declaration: {record_id}")
            if any(record[field] is not None for field in ("pr", "head", "tree", "base_head")):
                raise TruthProjectionError(f"UNKNOWN cannot carry candidate Git identity: {record_id}")

    history = payload["historical_projections"]
    if not isinstance(history, list):
        raise TruthProjectionError("historical_projections must be an array")
    for index, item in enumerate(history):
        label = f"historical_projections[{index}]"
        if not isinstance(item, Mapping):
            raise TruthProjectionError(f"{label} must be an object")
        _exact_keys(item, {"path", "observed_head", "observed_tree", "currentness"}, label)
        _text(item["path"], f"{label}.path")
        observed_head = _sha40(item["observed_head"], f"{label}.observed_head")
        observed_tree = _sha40(item["observed_tree"], f"{label}.observed_tree")
        expected = classify_projection_currentness(
            observed_commit=observed_head,
            observed_tree=observed_tree,
            current_commit=current_head,
            current_tree=current_tree,
        )
        if item["currentness"] != expected:
            raise TruthProjectionError(
                f"historical currentness contradiction for {item['path']}: declared={item['currentness']} expected={expected}"
            )

    return payload
