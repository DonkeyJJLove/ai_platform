"""Durable single-use admission/receipt substrate for bounded LION mutations.

This module is deliberately executor-agnostic. Concrete repository, PR, mission,
database and runtime adapters are bound by exact effect class and executor id.
Unbound effects fail closed before nonce consumption. Consumption is committed
before the effect call so a crash can never silently authorize a replay.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Callable, Mapping

from cyber_lion.contracts.bounded_mutation import (
    MutationAdmission, MutationContractError, MutationReceipt, canonical, digest,
    parse_expiration,
)

SCHEMA_ID = "lion.bounded-mutation-substrate/v1"

DDL = """
CREATE TABLE IF NOT EXISTS bounded_mutation_admissions(
  mutation_admission_id TEXT PRIMARY KEY,
  admission_digest TEXT NOT NULL UNIQUE,
  single_use_nonce TEXT NOT NULL UNIQUE,
  parent_mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  allowed_effect_class TEXT NOT NULL,
  effect_ceiling TEXT NOT NULL,
  expiration TEXT NOT NULL,
  admission_json TEXT NOT NULL,
  issued_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bounded_mutation_consumptions(
  mutation_admission_id TEXT PRIMARY KEY,
  single_use_nonce TEXT NOT NULL UNIQUE,
  admission_digest TEXT NOT NULL UNIQUE,
  executor_id TEXT NOT NULL,
  observed_pre_state TEXT NOT NULL,
  consumed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bounded_mutation_receipts(
  receipt_id TEXT PRIMARY KEY,
  mutation_admission_id TEXT NOT NULL UNIQUE,
  receipt_digest TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  receipt_json TEXT NOT NULL,
  observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bounded_mutation_migrations(
  version INTEGER PRIMARY KEY,
  schema_id TEXT NOT NULL,
  applied_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS bounded_mutation_admission_immutable
BEFORE UPDATE ON bounded_mutation_admissions BEGIN
  SELECT RAISE(ABORT,'immutable bounded mutation admission');
END;
CREATE TRIGGER IF NOT EXISTS bounded_mutation_consumption_immutable
BEFORE UPDATE ON bounded_mutation_consumptions BEGIN
  SELECT RAISE(ABORT,'immutable bounded mutation consumption');
END;
CREATE TRIGGER IF NOT EXISTS bounded_mutation_receipt_immutable
BEFORE UPDATE ON bounded_mutation_receipts BEGIN
  SELECT RAISE(ABORT,'immutable bounded mutation receipt');
END;
"""


class MutationSubstrateError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso(value: str) -> datetime:
    return parse_expiration(value)


def migrate(conn: sqlite3.Connection, now_fn: Callable[[], str] = utc_now) -> None:
    conn.executescript(DDL)
    conn.execute(
        "INSERT OR IGNORE INTO bounded_mutation_migrations VALUES(?,?,?)",
        (1, SCHEMA_ID, now_fn()),
    )
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        conn.rollback()
        raise MutationSubstrateError("database integrity failed")
    conn.commit()


class BoundedMutationSubstrate:
    def __init__(
        self,
        conn: sqlite3.Connection,
        executors: Mapping[str, tuple[str, Callable[[MutationAdmission], Any]]],
        *,
        now_fn: Callable[[], str] = utc_now,
    ) -> None:
        self.conn = conn
        self.executors = dict(executors)
        self.now_fn = now_fn
        migrate(conn, now_fn)

    def issue(self, value: Mapping[str, Any]) -> dict[str, Any]:
        admission = MutationAdmission.from_mapping(value)
        raw = canonical({"schema": "lion.bounded-mutation-admission/v1", **admission.as_dict()})
        stamp = self.now_fn()
        existing = self.conn.execute(
            "SELECT admission_digest FROM bounded_mutation_admissions WHERE mutation_admission_id=?",
            (admission.mutation_admission_id,),
        ).fetchone()
        if existing:
            if existing[0] != admission.admission_digest:
                raise MutationSubstrateError("mutation admission id conflict")
            return self.admission(admission.mutation_admission_id)
        try:
            self.conn.execute(
                """INSERT INTO bounded_mutation_admissions
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    admission.mutation_admission_id, admission.admission_digest,
                    admission.single_use_nonce, admission.parent_mission_id,
                    admission.phase_id, admission.allowed_effect_class,
                    admission.effect_ceiling, admission.expiration, raw, stamp,
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            raise MutationSubstrateError("admission replay/nonce reuse denied") from exc
        return self.admission(admission.mutation_admission_id)

    def admission(self, admission_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM bounded_mutation_admissions WHERE mutation_admission_id=?",
            (admission_id,),
        ).fetchone()
        if row is None:
            raise MutationSubstrateError("mutation admission not found")
        cols = [d[0] for d in self.conn.execute(
            "SELECT * FROM bounded_mutation_admissions LIMIT 0"
        ).description]
        return dict(zip(cols, row))

    def _load(self, admission_id: str) -> MutationAdmission:
        row = self.conn.execute(
            "SELECT admission_json FROM bounded_mutation_admissions WHERE mutation_admission_id=?",
            (admission_id,),
        ).fetchone()
        if row is None:
            raise MutationSubstrateError("mutation admission not found")
        value = json.loads(row[0])
        value.pop("schema", None)
        try:
            return MutationAdmission.from_mapping(value)
        except MutationContractError as exc:
            raise MutationSubstrateError("persisted admission invalid") from exc

    def execute(
        self,
        admission_id: str,
        *,
        observed_pre_state: str,
        readback: Callable[[MutationAdmission], str],
        test: Callable[[MutationAdmission], Mapping[str, Any]],
        rollback: Callable[[MutationAdmission], Any],
    ) -> dict[str, Any]:
        admission = self._load(admission_id)
        binding = self.executors.get(admission.allowed_effect_class)
        if not binding or len(binding) != 2 or not callable(binding[1]):
            raise MutationSubstrateError("effect class has no bound executor")
        executor_id, executor = binding
        if not isinstance(executor_id, str) or not executor_id:
            raise MutationSubstrateError("executor id invalid")
        now_value = self.now_fn()
        if _iso(now_value) >= _iso(admission.expiration):
            raise MutationSubstrateError("mutation admission expired")
        if observed_pre_state != admission.expected_pre_state:
            raise MutationSubstrateError("pre-state currentness mismatch")
        if self.conn.execute(
            "SELECT 1 FROM bounded_mutation_consumptions WHERE mutation_admission_id=? OR single_use_nonce=?",
            (admission_id, admission.single_use_nonce),
        ).fetchone():
            raise MutationSubstrateError("mutation admission replay denied")

        # Fencing point: durable nonce consumption precedes external effect.
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute(
                "INSERT INTO bounded_mutation_consumptions VALUES(?,?,?,?,?,?)",
                (
                    admission_id, admission.single_use_nonce,
                    admission.admission_digest, executor_id,
                    observed_pre_state, now_value,
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            raise MutationSubstrateError("mutation admission replay denied") from exc

        effect_result: Any = {"status": "NOT_EXECUTED"}
        test_result: Mapping[str, Any] = {"status": "NOT_RUN"}
        rollback_result: Any = None
        post = observed_pre_state
        status = "FAILED_UNRECONCILED"
        try:
            effect_result = executor(admission)
            post = readback(admission)
            if post != admission.expected_post_state:
                raise MutationSubstrateError("post-state readback mismatch")
            test_result = test(admission)
            if not isinstance(test_result, Mapping) or str(test_result.get("status")).upper() != "PASS":
                raise MutationSubstrateError("test procedure did not PASS")
            status = "RECONCILED"
        except Exception as effect_error:
            try:
                rollback_result = rollback(admission)
                rollback_readback = readback(admission)
                status = "ROLLED_BACK" if rollback_readback == admission.expected_pre_state else "FAILED_UNRECONCILED"
                post = rollback_readback
            except Exception as rollback_error:
                rollback_result = {
                    "rollback_error": type(rollback_error).__name__,
                    "effect_error": type(effect_error).__name__,
                }
                status = "FAILED_UNRECONCILED"

        receipt = MutationReceipt(
            receipt_id="mutation-receipt:" + admission.admission_digest,
            mutation_admission_id=admission_id,
            admission_digest=admission.admission_digest,
            allowed_effect_class=admission.allowed_effect_class,
            executor_id=executor_id,
            target_object_digest=digest(admission.target_object),
            observed_pre_state=observed_pre_state,
            observed_post_state=post,
            effect_result_digest=digest(effect_result),
            test_result_digest=digest(dict(test_result)),
            rollback_result_digest=digest(rollback_result) if rollback_result is not None else None,
            status=status,
            observed_at=self.now_fn(),
        ).as_dict()
        try:
            self.conn.execute(
                "INSERT INTO bounded_mutation_receipts VALUES(?,?,?,?,?,?)",
                (
                    receipt["receipt_id"], admission_id, receipt["receipt_digest"],
                    status, canonical(receipt), receipt["observed_at"],
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            raise MutationSubstrateError("mutation receipt already exists") from exc
        return receipt

    def snapshot(self) -> dict[str, Any]:
        counts = {}
        for table in (
            "bounded_mutation_admissions",
            "bounded_mutation_consumptions",
            "bounded_mutation_receipts",
        ):
            counts[table] = int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        bindings = {
            effect: executor_id
            for effect, (executor_id, _executor) in sorted(self.executors.items())
        }
        value = {
            "schema": SCHEMA_ID,
            "counts": counts,
            "executor_bindings": bindings,
            "authority_effect": "NONE",
        }
        value["snapshot_digest"] = digest(value)
        return value
