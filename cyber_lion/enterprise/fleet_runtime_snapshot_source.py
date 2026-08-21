"""Read-only F005-G producer for authoritative runtime convergence evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Callable, Iterable

from cyber_lion.contracts.fleet_runtime_snapshot_source import (
    ObservedRuntimeState,
    RuntimeSnapshotSourceConfig,
    build_convergence_snapshot,
    canonical_json,
)

TERMINAL_MISSIONS = frozenset({"DONE", "FAILED", "TERMINATED"})
COORDINATION_STATES = frozenset({"STARTING", "WAITING", "RUNNING", "DONE", "FAILED", "TERMINATED"})
TERMINAL_AUTHORITY = frozenset({"NONE", "REVOKED", "EXPIRED"})
TERMINAL_EFFECT = frozenset({"NONE", "APPLIED", "FAILED_NO_EFFECT"})
TERMINAL_RECONCILIATION = frozenset({"NOT_REQUIRED", "RESOLVED"})
CRITICAL_DECISION_DIMENSIONS = frozenset({
    "MISSION", "RUNTIME", "HEARTBEAT", "AUTHORITY", "LEASE", "SANDBOX",
    "VERIFICATION", "EFFECT", "RECONCILIATION", "REPOSITORY", "RECEIPT",
})


class RuntimeSnapshotSourceError(RuntimeError):
    pass


def _utc(clock: Callable[[], datetime]) -> str:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise RuntimeSnapshotSourceError("trusted clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RuntimeSnapshotSourceError("stored timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise RuntimeSnapshotSourceError("stored timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _ro_connect(path: str) -> sqlite3.Connection:
    file_path = Path(path)
    if not file_path.is_file():
        raise RuntimeSnapshotSourceError(f"authoritative runtime source unavailable: {path}")
    uri = file_path.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=5.0)
    except sqlite3.Error as exc:
        raise RuntimeSnapshotSourceError(f"cannot open authoritative runtime source: {path}") from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _require_tables(conn: sqlite3.Connection, names: Iterable[str]) -> None:
    actual = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = sorted(set(names) - actual)
    if missing:
        raise RuntimeSnapshotSourceError("runtime source schema incomplete: " + ",".join(missing))


def _rows(conn: sqlite3.Connection, sql: str, args: tuple[object, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, args).fetchall()]


def _one(conn: sqlite3.Connection, sql: str, args: tuple[object, ...] = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, args).fetchone()
    return None if row is None else dict(row)


def _status_event_digest(previous: str, row: dict[str, Any]) -> str:
    try:
        payload = json.loads(str(row["payload_json"]))
    except json.JSONDecodeError as exc:
        raise RuntimeSnapshotSourceError("status event payload corruption") from exc
    return sha256(canonical_json({
        "previous_digest": previous,
        "event_type": row["event_type"],
        "mission_id": row["mission_id"],
        "payload": payload,
        "observed_at": row["observed_at"],
    })).hexdigest()


def _status_receipt_digest(previous: str, row: dict[str, Any]) -> str:
    return sha256(canonical_json({
        "previous_digest": previous,
        "receipt_id": row["receipt_id"],
        "mission_id": row["mission_id"],
        "source_ref": row["source_ref"],
        "observed_at": row["observed_at"],
    })).hexdigest()


def _coord_event_digest(previous: str, row: dict[str, Any]) -> str:
    try:
        payload = json.loads(str(row["payload_json"]))
    except json.JSONDecodeError as exc:
        raise RuntimeSnapshotSourceError("coordination event payload corruption") from exc
    return sha256(canonical_json({
        "previous_digest": previous,
        "event_type": row["event_type"],
        "mission_id": row["mission_id"],
        "payload": payload,
        "observed_at": row["observed_at"],
    })).hexdigest()


def _verify_chain(rows: list[dict[str, Any]], head: str, digest_fn: Callable[[str, dict[str, Any]], str], *, id_field: str | None = None) -> bool:
    previous = "0" * 64
    previous_time: datetime | None = None
    try:
        for row in rows:
            current_time = _parse_time(str(row["observed_at"]))
            if previous_time is not None and current_time < previous_time:
                return False
            expected = digest_fn(previous, row)
            if row.get("previous_digest") != previous or row.get("event_digest", row.get("receipt_digest")) != expected:
                return False
            if id_field is not None and row.get(id_field) != expected:
                return False
            previous = expected
            previous_time = current_time
    except (KeyError, RuntimeSnapshotSourceError):
        return False
    return previous == head


def _latest_decisions(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        mission_id = row.get("mission_id")
        dimension = row.get("dimension")
        if isinstance(mission_id, str) and isinstance(dimension, str):
            latest[(mission_id, dimension)] = row
    return latest


def _decision_fact(row: dict[str, Any] | None) -> tuple[str, dict[str, str]] | None:
    if row is None or row.get("decision_type") != "FACT":
        return None
    try:
        payload = json.loads(str(row["decision_json"]))
        fact = payload["fact"]
        state = fact["state"]
        items = fact["value_items"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeSnapshotSourceError("status decision fact corruption") from exc
    if not isinstance(state, str) or not isinstance(items, list):
        raise RuntimeSnapshotSourceError("status decision fact invalid")
    values: dict[str, str] = {}
    for item in items:
        if not isinstance(item, list) or len(item) != 2 or not all(isinstance(x, str) for x in item):
            raise RuntimeSnapshotSourceError("status decision value invalid")
        if item[0] in values:
            raise RuntimeSnapshotSourceError("status decision value duplicate")
        values[item[0]] = item[1]
    return state, values


def _read_status(path: str) -> dict[str, Any]:
    conn = _ro_connect(path)
    try:
        _require_tables(conn, (
            "fleet_meta", "fleet_identity", "fleet_mission", "fleet_heartbeat",
            "fleet_projection", "fleet_lease", "fleet_event", "fleet_receipt",
            "fleet_source_decision",
        ))
        before = _one(conn, "SELECT registry_instance_id,revision,event_head,receipt_head FROM fleet_meta WHERE singleton=1")
        if before is None:
            raise RuntimeSnapshotSourceError("status registry meta missing")
        identities = _rows(conn, "SELECT * FROM fleet_identity ORDER BY mission_id")
        missions = _rows(conn, "SELECT * FROM fleet_mission ORDER BY mission_id")
        heartbeats = _rows(conn, "SELECT * FROM fleet_heartbeat ORDER BY mission_id")
        projections = _rows(conn, "SELECT * FROM fleet_projection ORDER BY mission_id,kind")
        leases = _rows(conn, "SELECT * FROM fleet_lease ORDER BY lease_id")
        events = _rows(conn, "SELECT * FROM fleet_event ORDER BY seq")
        receipts = _rows(conn, "SELECT * FROM fleet_receipt ORDER BY seq")
        decisions = _rows(conn, "SELECT * FROM fleet_source_decision ORDER BY seq")
        after = _one(conn, "SELECT registry_instance_id,revision,event_head,receipt_head FROM fleet_meta WHERE singleton=1")
        stable = before == after
        event_chain = _verify_chain(events, str(before["event_head"]), _status_event_digest)
        receipt_chain = _verify_chain(receipts, str(before["receipt_head"]), _status_receipt_digest)
        return {
            "meta": before, "stable": stable, "event_chain": event_chain,
            "receipt_chain": receipt_chain, "identities": identities, "missions": missions,
            "heartbeats": heartbeats, "projections": projections, "leases": leases,
            "receipts": receipts, "decisions": decisions,
        }
    finally:
        conn.close()


def _read_coordination(path: str) -> dict[str, Any]:
    conn = _ro_connect(path)
    try:
        _require_tables(conn, (
            "fleet_coordination_meta", "fleet_coordination_mission",
            "fleet_coordination_active_lease", "fleet_coordination_event",
        ))
        before = _one(conn, "SELECT coordinator_id,revision,event_head FROM fleet_coordination_meta WHERE singleton=1")
        if before is None:
            raise RuntimeSnapshotSourceError("coordination meta missing")
        missions = _rows(conn, "SELECT * FROM fleet_coordination_mission ORDER BY mission_id")
        leases = _rows(conn, "SELECT * FROM fleet_coordination_active_lease ORDER BY repository,lease_kind,resource")
        events = _rows(conn, "SELECT * FROM fleet_coordination_event ORDER BY seq")
        after = _one(conn, "SELECT coordinator_id,revision,event_head FROM fleet_coordination_meta WHERE singleton=1")
        stable = before == after
        event_chain = _verify_chain(events, str(before["event_head"]), _coord_event_digest, id_field="event_id")
        return {"meta": before, "stable": stable, "event_chain": event_chain, "missions": missions, "leases": leases}
    finally:
        conn.close()


def _read_reconciliation(path: str, repository: str, current_master: str) -> dict[str, Any]:
    conn = _ro_connect(path)
    try:
        _require_tables(conn, ("reconciliation_inventory_head", "reconciliation_report", "convergence_receipt"))
        before = _one(conn, "SELECT * FROM reconciliation_inventory_head WHERE repository=?", (repository,))
        if before is None:
            raise RuntimeSnapshotSourceError("repository reconciliation inventory missing")
        report = _one(
            conn,
            "SELECT * FROM reconciliation_report WHERE repository=? AND inventory_digest=? ORDER BY rowid DESC LIMIT 1",
            (repository, before["inventory_digest"]),
        )
        receipt = None
        if report is not None:
            receipt = _one(
                conn,
                "SELECT * FROM convergence_receipt WHERE repository=? AND report_digest=? ORDER BY rowid DESC LIMIT 1",
                (repository, report["report_digest"]),
            )
        after = _one(conn, "SELECT * FROM reconciliation_inventory_head WHERE repository=?", (repository,))
        stable = before == after
        exact_head = before.get("default_head_sha") == current_master
        report_bound = bool(report) and all(report.get(key) == before.get(key) for key in (
            "inventory_id", "inventory_revision", "inventory_digest", "default_head_sha",
        ))
        converged = bool(report_bound and report and report.get("disposition") == "CONVERGED")
        receipt_bound = bool(receipt) and all(receipt.get(key) == before.get(key) for key in (
            "inventory_id", "inventory_revision", "inventory_digest", "default_head_sha",
        ))
        return {
            "head": before, "stable": stable, "exact_head": exact_head,
            "report": report, "receipt": receipt, "report_bound": report_bound,
            "receipt_bound": receipt_bound, "converged": converged,
        }
    finally:
        conn.close()


def observe_runtime_state(config: RuntimeSnapshotSourceConfig, *, clock: Callable[[], datetime]) -> ObservedRuntimeState:
    config.validate()
    status = _read_status(config.status_db_path)
    coordination = _read_coordination(config.coordination_db_path)
    reconciliation = _read_reconciliation(config.reconciliation_db_path, config.repository, config.current_master)
    observed_at = _utc(clock)
    now = _parse_time(observed_at)

    coord_missions = {str(row["mission_id"]): row for row in coordination["missions"]}
    status_missions = {str(row["mission_id"]): row for row in status["missions"]}
    identities = {str(row["mission_id"]): row for row in status["identities"]}
    heartbeats = {str(row["mission_id"]): row for row in status["heartbeats"]}
    receipts_by_mission = {str(row["mission_id"]): row for row in status["receipts"]}
    projections = {(str(row["mission_id"]), str(row["kind"])): row for row in status["projections"]}
    decisions = _latest_decisions(status["decisions"])

    active_ids = {mid for mid, row in coord_missions.items() if row.get("state") not in TERMINAL_MISSIONS}
    unknown_ids = {mid for mid, row in coord_missions.items() if row.get("state") not in COORDINATION_STATES}

    mission_sets_equal = set(coord_missions) == set(status_missions) == set(identities)
    if not mission_sets_equal:
        unknown_ids.update(set(coord_missions) ^ set(status_missions))
        unknown_ids.update(set(coord_missions) ^ set(identities))

    critical_disagreements = 0
    for (mission_id, dimension), row in decisions.items():
        if dimension in CRITICAL_DECISION_DIMENSIONS and row.get("decision_type") in {"CONFLICT", "MISSING"}:
            unknown_ids.add(mission_id)
            critical_disagreements += 1

    terminality_consistent = True
    for mid in set(coord_missions).intersection(status_missions):
        c_state = str(coord_missions[mid]["state"])
        s_state = str(status_missions[mid]["status"])
        if c_state in TERMINAL_MISSIONS and s_state != c_state:
            terminality_consistent = False
            unknown_ids.add(mid)
        if c_state not in TERMINAL_MISSIONS and s_state in TERMINAL_MISSIONS:
            terminality_consistent = False
            unknown_ids.add(mid)

    active_authority = 0
    residual_authority = 0
    unresolved_effects = 0
    reconciliation_state_disagreements = 0
    unknown_results = 0
    late_unreconciled_results = 0
    missing_heartbeats = 0
    stale_heartbeats = 0

    for mid, c_row in coord_missions.items():
        authority = projections.get((mid, "authority"))
        effect = projections.get((mid, "effect"))
        recon = projections.get((mid, "reconciliation"))

        authority_fact = _decision_fact(decisions.get((mid, "AUTHORITY")))
        effect_fact = _decision_fact(decisions.get((mid, "EFFECT")))
        recon_fact = _decision_fact(decisions.get((mid, "RECONCILIATION")))
        heartbeat_fact = _decision_fact(decisions.get((mid, "HEARTBEAT")))

        authority_state = authority_fact[0] if authority_fact else (str(authority["state"]) if authority else "UNKNOWN")
        effect_state = effect_fact[0] if effect_fact else (str(effect["state"]) if effect else "UNKNOWN")
        recon_state = recon_fact[0] if recon_fact else (str(recon["state"]) if recon else "UNKNOWN")

        if authority_state == "ACTIVE":
            active_authority += 1
        if authority_state not in TERMINAL_AUTHORITY:
            residual_authority += 1

        if effect_state not in TERMINAL_EFFECT:
            unresolved_effects += 1
        if recon_state not in TERMINAL_RECONCILIATION:
            reconciliation_state_disagreements += 1

        if c_row.get("state") in TERMINAL_MISSIONS:
            if mid not in receipts_by_mission or effect_state == "UNKNOWN":
                unknown_results += 1
            if effect_state in {"PREPARED", "ATTEMPTED", "RECONCILE_REQUIRED"} or recon_state not in TERMINAL_RECONCILIATION:
                late_unreconciled_results += 1

        if mid in active_ids:
            hb = heartbeats.get(mid)
            if heartbeat_fact is not None:
                _, values = heartbeat_fact
                hb_time = values.get("heartbeat_observed_at")
                deadline_raw = values.get("deadline_seconds")
                try:
                    deadline = int(deadline_raw) if deadline_raw is not None else -1
                except ValueError:
                    deadline = -1
                if not hb_time or deadline < 1:
                    missing_heartbeats += 1
                else:
                    age = (now - _parse_time(hb_time)).total_seconds()
                    if age < 0 or age > deadline:
                        stale_heartbeats += 1
            elif hb is None:
                missing_heartbeats += 1
            else:
                deadline = int(hb["deadline_seconds"])
                age = (now - _parse_time(str(hb["observed_at"]))).total_seconds()
                if age < 0 or age > deadline:
                    stale_heartbeats += 1

    status_active_leases = {
        (str(row["mission_id"]), str(row["lease_id"]))
        for row in status["leases"] if row.get("state") in {"ACTIVE", "STALE_HELD"}
    }
    coordination_leases = {
        (str(row["mission_id"]), f"{row['repository']}:{row['lease_kind']}:{row['resource']}")
        for row in coordination["leases"]
    }
    unresolved_write_leases = len(status_active_leases) + len(coordination_leases)

    generation_fencing_consistency = True
    unowned_active_branches = 0
    unknown_branch_ownership = 0
    leases_by_mission: dict[str, list[dict[str, Any]]] = {}
    for lease in coordination["leases"]:
        mid = str(lease["mission_id"])
        leases_by_mission.setdefault(mid, []).append(lease)
        mission = coord_missions.get(mid)
        if lease.get("lease_kind") == "BRANCH":
            if mission is None or mission.get("state") != "RUNNING" or mission.get("branch") != lease.get("resource"):
                unowned_active_branches += 1

    branch_owners: dict[str, set[str]] = {}
    for mid, row in coord_missions.items():
        if row.get("state") not in TERMINAL_MISSIONS:
            branch_owners.setdefault(str(row["branch"]), set()).add(mid)
    unknown_branch_ownership += sum(len(owners) > 1 for owners in branch_owners.values())

    for mid, row in coord_missions.items():
        leases = leases_by_mission.get(mid, [])
        if row.get("state") == "RUNNING":
            matching = [
                lease for lease in leases
                if lease.get("dispatch_id") == row.get("dispatch_id")
                and int(lease.get("generation", -1)) == int(row.get("generation", -2))
            ]
            branch_matches = [lease for lease in matching if lease.get("lease_kind") == "BRANCH" and lease.get("resource") == row.get("branch")]
            if len(matching) != len(leases) or len(branch_matches) != 1 or not row.get("fencing_token"):
                generation_fencing_consistency = False
                unknown_branch_ownership += 1
        elif leases:
            generation_fencing_consistency = False

    reconciliation_disagreements = critical_disagreements + reconciliation_state_disagreements
    if not reconciliation["converged"] or not reconciliation["report_bound"] or not reconciliation["receipt_bound"]:
        reconciliation_disagreements += 1

    durable_state_consistency = bool(
        status["stable"] and coordination["stable"] and reconciliation["stable"]
        and mission_sets_equal and terminality_consistent
    )
    event_chain_consistency = bool(status["event_chain"] and status["receipt_chain"] and coordination["event_chain"])
    inventory_complete = bool(
        durable_state_consistency
        and reconciliation["exact_head"]
        and reconciliation["converged"]
        and reconciliation["report_bound"]
        and reconciliation["receipt_bound"]
        and not unknown_ids
    )

    evidence = {
        "repository": config.repository,
        "current_master": config.current_master,
        "current_master_tree": config.current_master_tree,
        "source_instance": config.source_instance,
        "status_meta": status["meta"],
        "coordination_meta": coordination["meta"],
        "reconciliation_head": reconciliation["head"],
        "reconciliation_report_digest": reconciliation["report"].get("report_digest") if reconciliation["report"] else None,
        "reconciliation_receipt_digest": reconciliation["receipt"].get("receipt_digest") if reconciliation["receipt"] else None,
        "coordination_missions": [
            {
                "mission_id": row["mission_id"], "state": row["state"], "generation": row["generation"],
                "dispatch_id": row["dispatch_id"], "branch": row["branch"], "updated_at": row["updated_at"],
            }
            for row in coordination["missions"]
        ],
        "coordination_leases": [
            {
                "mission_id": row["mission_id"], "lease_kind": row["lease_kind"], "resource": row["resource"],
                "dispatch_id": row["dispatch_id"], "generation": row["generation"],
            }
            for row in coordination["leases"]
        ],
        "status_projection": [
            {"mission_id": row["mission_id"], "kind": row["kind"], "state": row["state"], "observed_at": row["observed_at"]}
            for row in status["projections"]
        ],
        "status_receipts": [row["receipt_id"] for row in status["receipts"]],
        "unknown_mission_ids": sorted(unknown_ids),
    }
    source_digest = sha256(b"LION/F005-G-SOURCES/1\0" + canonical_json(evidence)).hexdigest()

    return ObservedRuntimeState(
        observed_at=observed_at,
        source_digest=source_digest,
        active_missions=len(active_ids),
        unknown_missions=len(unknown_ids),
        unresolved_write_leases=unresolved_write_leases,
        unknown_results=unknown_results,
        late_unreconciled_results=late_unreconciled_results,
        missing_heartbeats=missing_heartbeats,
        stale_heartbeats=stale_heartbeats,
        unknown_branch_ownership=unknown_branch_ownership,
        unowned_active_branches=unowned_active_branches,
        unreconciled_effects=unresolved_effects,
        reconciliation_disagreements=reconciliation_disagreements,
        active_authority=active_authority,
        residual_authority=residual_authority,
        durable_state_consistency=durable_state_consistency,
        event_chain_consistency=event_chain_consistency,
        generation_fencing_consistency=generation_fencing_consistency,
        inventory_complete=inventory_complete,
    ).validate()


def _atomic_write_json(path: str, value: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def materialize_snapshot(config: RuntimeSnapshotSourceConfig, *, clock: Callable[[], datetime]) -> dict[str, Any]:
    observed = observe_runtime_state(config, clock=clock)
    snapshot = build_convergence_snapshot(config, observed)
    value = snapshot.canonical_dict()
    _atomic_write_json(config.output_path, value)
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-master-tree", required=True)
    parser.add_argument("--source-instance", required=True)
    parser.add_argument("--status-db", required=True)
    parser.add_argument("--coordination-db", required=True)
    parser.add_argument("--reconciliation-db", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    config = RuntimeSnapshotSourceConfig(
        repository=args.repository,
        current_master=args.expected_master,
        current_master_tree=args.expected_master_tree,
        source_instance=args.source_instance,
        status_db_path=args.status_db,
        coordination_db_path=args.coordination_db,
        reconciliation_db_path=args.reconciliation_db,
        output_path=args.output,
    ).validate()
    value = materialize_snapshot(config, clock=lambda: datetime.now(timezone.utc))
    print(json.dumps({
        "status": "AUTHORITATIVE_RUNTIME_SNAPSHOT_MATERIALIZED",
        "snapshot_id": value["snapshot_id"],
        "source_digest": value["source_digest"],
        "observed_at": value["observed_at"],
        "output": config.output_path,
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
