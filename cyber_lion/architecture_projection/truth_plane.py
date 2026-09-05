from __future__ import annotations

import re
from typing import Any, Mapping

from .gap import classify_projection_currentness

SCHEMA_VERSION = "lion.truth-projection/v1.3-a0-candidate"
PLANES = frozenset({"AS_IS", "CANDIDATE", "TARGET", "UNKNOWN"})
CANDIDATE_STATUSES = frozenset({"CURRENT_MASTER_BASE_CANDIDATE", "CURRENT_STACKED_CANDIDATE", "STALE_BASE_CANDIDATE"})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
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


def validate_truth_projection(
    payload: Mapping[str, Any],
    *,
    current_head: str,
    current_tree: str,
) -> Mapping[str, Any]:
    """Validate an exact AS-IS/CANDIDATE/TARGET truth projection.

    The projection is descriptive only. It grants no authority and cannot promote
    a candidate into AS-IS. CURRENT is valid only for the exact supplied Git head
    and tree. Historical projections self-degrade to STALE on material drift.
    """
    if not isinstance(payload, Mapping):
        raise TruthProjectionError("truth projection must be an object")
    _exact_keys(payload, {"schema_version", "baseline", "records", "historical_projections"}, "root")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise TruthProjectionError("truth projection schema_version mismatch")

    _sha40(current_head, "current_head")
    _sha40(current_tree, "current_tree")

    baseline = payload["baseline"]
    if not isinstance(baseline, Mapping):
        raise TruthProjectionError("baseline must be an object")
    _exact_keys(baseline, {"repository", "branch", "head", "tree", "currentness"}, "baseline")
    _text(baseline["repository"], "baseline.repository")
    _text(baseline["branch"], "baseline.branch")
    baseline_head = _sha40(baseline["head"], "baseline.head")
    baseline_tree = _sha40(baseline["tree"], "baseline.tree")
    expected_currentness = classify_projection_currentness(
        observed_commit=baseline_head,
        observed_tree=baseline_tree,
        current_commit=current_head,
        current_tree=current_tree,
    )
    if baseline["currentness"] != expected_currentness:
        raise TruthProjectionError(
            f"baseline currentness contradiction: declared={baseline['currentness']} expected={expected_currentness}"
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
