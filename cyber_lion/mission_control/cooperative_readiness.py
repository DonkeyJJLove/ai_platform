"""Conservative readiness observation predicate and its generated data corpus.

READY here means recent reported reachability only. It is NOT a runtime
admission, verified source identity, available production capability or proof
that an assignment ran. Keep these other gates separate.
"""
from __future__ import annotations
import json
import math
from typing import Any, Mapping

SCHEMA = "lion.cooperative-readiness-corpus/v1"
MAX_AGE_SECONDS = 20
CASE_FIELDS = frozenset({"id", "state", "transport_state", "mission_control_reachability", "model_reachability", "age_seconds", "expected_ready"})


def observation_ready(value: Mapping[str, Any], *, max_age_seconds: int = MAX_AGE_SECONDS) -> bool:
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 300:
        raise ValueError("invalid freshness limit")
    if not isinstance(value, Mapping):
        return False
    age = value.get("age_seconds")
    return (type(age) in (int, float) and math.isfinite(age)
            and 0 <= age <= max_age_seconds
            and value.get("state") == "READY"
            and value.get("transport_state") == "READY"
            and value.get("mission_control_reachability") == "OK"
            and value.get("model_reachability") == "OK")


def validate_corpus(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not 1 <= len(raw) <= 16384:
        raise ValueError("corpus byte limit")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite number")))
    if type(value) is not dict or set(value) != {"schema", "cases"} or value["schema"] != SCHEMA:
        raise ValueError("corpus schema")
    cases = value["cases"]
    if type(cases) is not list or not 8 <= len(cases) <= 16:
        raise ValueError("corpus case count")
    ids = set()
    categories = set()
    passed = 0
    for case in cases:
        if type(case) is not dict or set(case) != CASE_FIELDS:
            raise ValueError("case fields")
        name = case["id"]
        if type(name) is not str or not 1 <= len(name) <= 80 or name in ids:
            raise ValueError("case id")
        ids.add(name)
        if type(case["expected_ready"]) is not bool:
            raise ValueError("expected_ready type")
        if case["state"] not in {"READY", "DEGRADED", "STOPPED"}:
            raise ValueError("worker state")
        if case["transport_state"] not in {"READY", "DEGRADED", "STALE"}:
            raise ValueError("transport state")
        if any(case[k] not in {"OK", "DOWN", "STALE"} for k in ("mission_control_reachability", "model_reachability")):
            raise ValueError("reachability state")
        age = case["age_seconds"]
        if type(age) not in (int, float) or not math.isfinite(age):
            raise ValueError("age type")
        actual = observation_ready(case)
        if actual is not case["expected_ready"]:
            raise ValueError("case expectation mismatch: " + name)
        passed += 1
        base = case["state"] == "READY" and case["transport_state"] == "READY" and case["mission_control_reachability"] == "OK" and case["model_reachability"] == "OK"
        if base and age == 0: categories.add("fresh")
        if base and age == 20: categories.add("boundary")
        if base and age == 21: categories.add("stale")
        if base and age == -1: categories.add("future")
        if age == 0:
            if case["state"] == "STOPPED" and case["transport_state"] == "READY" and case["mission_control_reachability"] == case["model_reachability"] == "OK": categories.add("stopped")
            if case["state"] == "READY" and case["transport_state"] == "DEGRADED" and case["mission_control_reachability"] == case["model_reachability"] == "OK": categories.add("transport")
            if case["state"] == case["transport_state"] == "READY" and case["mission_control_reachability"] == "DOWN" and case["model_reachability"] == "OK": categories.add("mission_control")
            if case["state"] == case["transport_state"] == "READY" and case["model_reachability"] == "DOWN" and case["mission_control_reachability"] == "OK": categories.add("model")
    required = {"fresh", "boundary", "stale", "future", "stopped", "transport", "mission_control", "model"}
    if categories != required:
        raise ValueError("missing boundary coverage: " + ",".join(sorted(required - categories)))
    return {"schema": SCHEMA, "case_count": passed, "categories": sorted(categories),
            "deterministic_validation": "PASS", "authority_effect": "NONE"}
