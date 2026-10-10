"""Versioned, non-authorizing LION service-continuation ledger.

The tracked document captures future work and evidence pointers. It is not Mission
Control's event log, an authority issuer, a scheduler, or a current runtime truth
source. Updates are immutable events proposed through Git; model proposals can
never grant an effect. Independently read the target before consequential action.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA = "lion.service-continuation-ledger/v1"
EVENT_DOMAIN = b"LION/SERVICE-CONTINUATION-EVENT/1\0"
GENESIS = "0" * 64
STATES = frozenset({"WAITING", "READY", "BLOCKED", "IN_PROGRESS", "VERIFIED", "COMPLETE", "SUPERSEDED"})
EFFECTS = frozenset({"NONE", "REPOSITORY_WRITE", "AUTHORITY_WRITE", "MERGE", "DEPLOY", "LPCL_ACTIVATE", "TRUST_CHANGE"})
APPROVALS = frozenset({"NONE_READ_ONLY", "SEPARATE_EXACT_OPERATOR_APPROVAL", "EXPLICIT_EXACT_LPCL_OPERATOR_LAUNCH"})
TRANSITIONS = {
    "WAITING": frozenset({"READY", "BLOCKED", "SUPERSEDED"}),
    "BLOCKED": frozenset({"READY", "SUPERSEDED"}),
    "READY": frozenset({"IN_PROGRESS", "BLOCKED", "SUPERSEDED"}),
    "IN_PROGRESS": frozenset({"VERIFIED", "BLOCKED", "SUPERSEDED"}),
    "VERIFIED": frozenset({"COMPLETE", "BLOCKED", "SUPERSEDED"}),
    "COMPLETE": frozenset(),
    "SUPERSEDED": frozenset(),
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TASK_ID = re.compile(r"^SVC-[0-9]{4}$")
EVIDENCE_PREFIXES = frozenset({"SOURCE", "GITHUB", "CI", "TEST", "RUNTIME", "OPERATOR", "SIGNED", "CHECKPOINT", "UNKNOWN"})


class ServiceContinuationLedgerError(ValueError):
    pass


def _fail(message: str) -> None:
    raise ServiceContinuationLedgerError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _record(value: object, fields: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        _fail(f"{label} fields invalid")
    return value


def _text(value: object, label: str, maximum: int = 1024) -> str:
    if type(value) is not str or not value.strip() or "\x00" in value or len(value) > maximum:
        _fail(f"{label} invalid")
    return value


def _list(value: object, label: str) -> list:
    if type(value) is not list:
        _fail(f"{label} invalid")
    return value


def _timestamp(value: object) -> str:
    _text(value, "timestamp", 64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail("timestamp malformed")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("timestamp must be timezone aware")
    return value


def _evidence_ref(value: object) -> str:
    value = _text(value, "evidence reference")
    if ":" not in value or value.split(":", 1)[0] not in EVIDENCE_PREFIXES:
        _fail("evidence reference must carry a known evidence class")
    if not value.split(":", 1)[1]:
        _fail("evidence reference locator missing")
    return value


def _unique_text_list(value: object, label: str, *, evidence: bool = False) -> list[str]:
    items = _list(value, label)
    if len(items) != len(set(x for x in items if type(x) is str)):
        _fail(f"{label} duplicate")
    for x in items:
        if evidence:
            _evidence_ref(x)
        else:
            _text(x, label)
    return items


def _task(value: object) -> dict:
    fields = {
        "task_id", "title", "intent", "owner", "scope", "initial_state",
        "dependencies", "effect_class", "authorization_gate",
        "source_refs", "acceptance", "first_action",
    }
    t = _record(value, fields, "task")
    if not TASK_ID.fullmatch(_text(t["task_id"], "task id")):
        _fail("task id not canonical")
    for name in ("title", "intent", "owner", "scope", "first_action"):
        _text(t[name], name, maximum=2048)
    if t["initial_state"] not in {"WAITING", "READY", "BLOCKED"}:
        _fail("initial state cannot assert completed or executing work")
    deps = _unique_text_list(t["dependencies"], "dependencies")
    if t["task_id"] in deps or any(not TASK_ID.fullmatch(x) for x in deps):
        _fail("invalid task dependency")
    if t["effect_class"] not in EFFECTS or t["authorization_gate"] not in APPROVALS:
        _fail("unknown effect or gate")
    if t["effect_class"] == "NONE" and t["authorization_gate"] != "NONE_READ_ONLY":
        _fail("read-only task cannot require execution authority")
    if t["effect_class"] != "NONE" and t["authorization_gate"] == "NONE_READ_ONLY":
        _fail("effectful task requires separate authority")
    if t["effect_class"] == "LPCL_ACTIVATE" and t["authorization_gate"] != "EXPLICIT_EXACT_LPCL_OPERATOR_LAUNCH":
        _fail("LPCL requires explicit operator launch")
    refs = _unique_text_list(t["source_refs"], "source refs", evidence=True)
    if not refs:
        _fail("task must carry source references")
    acceptance = _unique_text_list(t["acceptance"], "acceptance")
    if not acceptance:
        _fail("task must declare acceptance criteria")
    return t


def _dependencies_acyclic(tasks: Mapping[str, dict]) -> None:
    seen: set[str] = set()
    in_path: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in in_path:
            _fail("task dependency cycle")
        if task_id in seen:
            return
        in_path.add(task_id)
        for dependency in tasks[task_id]["dependencies"]:
            if dependency not in tasks:
                _fail("unknown task dependency")
            visit(dependency)
        in_path.remove(task_id)
        seen.add(task_id)

    for task_id in tasks:
        visit(task_id)


def _event_digest(event: dict) -> str:
    without_digest = {key: value for key, value in event.items() if key != "digest"}
    return sha256(EVENT_DOMAIN + canonical_bytes(without_digest)).hexdigest()


def _replay(ledger: Mapping[str, Any]) -> tuple[dict[str, dict], dict[str, str]]:
    tasks: dict[str, dict] = {}
    states: dict[str, str] = {}
    for raw in _list(ledger["tasks"], "tasks"):
        t = _task(raw)
        task_id = t["task_id"]
        if task_id in tasks:
            _fail("duplicate task")
        tasks[task_id] = t
        states[task_id] = t["initial_state"]
    _dependencies_acyclic(tasks)
    prev = GENESIS
    last_at = datetime.fromisoformat(ledger["recorded_at"].replace("Z", "+00:00"))
    for seq, raw in enumerate(_list(ledger["events"], "events"), start=1):
        common = {"sequence", "previous_digest", "digest", "kind", "task_id", "actor", "observed_at", "evidence_refs"}
        if type(raw) is not dict or raw.get("kind") not in ("REGISTER_TASK", "TRANSITION"):
            _fail("unknown event kind")
        extra = {"task"} if raw["kind"] == "REGISTER_TASK" else {"from_state", "to_state"}
        ev = _record(raw, common | extra, "event")
        if type(ev["sequence"]) is not int or ev["sequence"] != seq:
            _fail("event sequence mismatch")
        if ev["previous_digest"] != prev or not HEX64.fullmatch(str(ev["digest"])):
            _fail("event previous digest mismatch")
        if ev["digest"] != _event_digest(ev):
            _fail("event digest mismatch")
        _timestamp(ev["observed_at"])
        observed = datetime.fromisoformat(ev["observed_at"].replace("Z", "+00:00"))
        if observed < last_at:
            _fail("event chronology regressed")
        last_at = observed
        _text(ev["actor"], "event actor")
        refs = _unique_text_list(ev["evidence_refs"], "event evidence", evidence=True)
        task_id = _text(ev["task_id"], "event task id")
        if raw["kind"] == "REGISTER_TASK":
            t = _task(ev["task"])
            if task_id != t["task_id"] or task_id in tasks:
                _fail("event registration invalid")
            if int(task_id[-4:]) <= max(int(existing[-4:]) for existing in tasks):
                _fail("registered task id must advance monotonically")
            if not refs:
                _fail("task registration needs source evidence")
            tasks[task_id] = t
            states[task_id] = t["initial_state"]
            _dependencies_acyclic(tasks)
        else:
            if task_id not in tasks:
                _fail("event refers to unknown task")
            previous_state = states[task_id]
            new_state = ev["to_state"]
            if ev["from_state"] != previous_state or new_state not in TRANSITIONS[previous_state]:
                _fail("invalid state transition")
            if new_state in {"READY", "IN_PROGRESS", "VERIFIED", "COMPLETE"}:
                if any(states[dep] != "COMPLETE" for dep in tasks[task_id]["dependencies"]):
                    _fail("unsatisfied dependencies")
            if new_state in {"VERIFIED", "COMPLETE"} and not refs:
                _fail("verification and completion require evidence")
            if new_state == "COMPLETE":
                classes = {ref.split(":", 1)[0] for ref in refs}
                if not classes.intersection({"RUNTIME", "GITHUB", "CI", "TEST"}):
                    _fail("completion needs independent observation or test reference")
                if tasks[task_id]["effect_class"] != "NONE" and "OPERATOR" not in classes:
                    _fail("effectful completion needs operator approval reference")
            states[task_id] = new_state
        prev = ev["digest"]
    if ledger["event_chain_head"] != prev:
        _fail("event chain head mismatch")
    if type(ledger["revision"]) is not int or ledger["revision"] != len(ledger["events"]) + 1:
        _fail("ledger revision mismatch")
    return tasks, states


def validate_ledger(value: object) -> dict[str, str]:
    top = {
        "schema", "ledger_id", "owner_repository", "revision", "recorded_at",
        "authority_effect", "runtime_effect", "baseline", "tasks", "events", "event_chain_head",
    }
    doc = _record(value, top, "ledger")
    if doc["schema"] != SCHEMA:
        _fail("unsupported schema")
    _text(doc["ledger_id"], "ledger id")
    if doc["owner_repository"] != "DonkeyJJLove/ai_platform":
        _fail("ledger owner mismatch")
    if doc["authority_effect"] != "NONE" or doc["runtime_effect"] != "NONE":
        _fail("ledger cannot assert effect")
    _timestamp(doc["recorded_at"])
    base = _record(doc["baseline"], {"source_head", "source_tree", "evidence_refs", "limitations"}, "baseline")
    if not HEX40.fullmatch(str(base["source_head"])) or not HEX40.fullmatch(str(base["source_tree"])):
        _fail("source baseline invalid")
    if not _unique_text_list(base["evidence_refs"], "baseline evidence", evidence=True):
        _fail("baseline evidence missing")
    _unique_text_list(base["limitations"], "baseline limitations")
    tasks, states = _replay(doc)
    if not tasks:
        _fail("empty ledger")
    return states


def assert_append_only(prior: Mapping[str, Any], successor: Mapping[str, Any]) -> dict[str, str]:
    old = validate_ledger(prior)
    new = validate_ledger(successor)
    immutable = set(prior) - {"events", "revision", "event_chain_head"}
    if any(prior[k] != successor[k] for k in immutable):
        _fail("ledger baseline or task definitions rewritten")
    if successor["events"][:len(prior["events"])] != prior["events"] or len(successor["events"]) <= len(prior["events"]):
        _fail("history replaced or not advanced")
    return new


def propose_event(
    ledger: Mapping[str, Any],
    *,
    kind: str,
    task_id: str,
    actor: str,
    observed_at: str,
    evidence_refs: list[str],
    to_state: str | None = None,
    task: dict | None = None,
) -> dict:
    states = validate_ledger(ledger)
    _timestamp(observed_at)
    _text(actor, "actor")
    _unique_text_list(evidence_refs, "evidence_refs", evidence=True)
    common = {
        "sequence": len(ledger["events"]) + 1,
        "previous_digest": ledger["event_chain_head"],
        "kind": kind, "task_id": task_id, "actor": actor,
        "observed_at": observed_at, "evidence_refs": list(evidence_refs),
    }
    if kind == "REGISTER_TASK":
        if task is None or task_id in states:
            _fail("registration not new")
        event = {**common, "task": deepcopy(task)}
    elif kind == "TRANSITION":
        if task_id not in states or to_state is None:
            _fail("transition target invalid")
        event = {**common, "from_state": states[task_id], "to_state": to_state}
    else:
        _fail("unsupported event")
    event["digest"] = _event_digest(event)
    proposal = deepcopy(dict(ledger))
    proposal["events"].append(event)
    proposal["revision"] += 1
    proposal["event_chain_head"] = event["digest"]
    assert_append_only(ledger, proposal)
    return proposal


def next_ready_tasks(ledger: Mapping[str, Any]) -> list[dict]:
    states = validate_ledger(ledger)
    tasks = list(ledger["tasks"]) + [ev["task"] for ev in ledger["events"] if ev["kind"] == "REGISTER_TASK"]
    return [
        {"task_id": task["task_id"], "title": task["title"], "first_action": task["first_action"],
         "authorization_gate": task["authorization_gate"]}
        for task in tasks if states[task["task_id"]] == "READY"
        and all(states[dep] == "COMPLETE" for dep in task["dependencies"])
    ]
