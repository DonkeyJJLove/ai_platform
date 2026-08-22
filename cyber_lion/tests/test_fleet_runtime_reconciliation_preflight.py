from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.fleet_reconciliation import RECEIPT_PURPOSE, ReconciliationTrustPins
from cyber_lion.contracts.fleet_runtime_reconciliation_preflight import (
    REPOSITORY,
    RUNTIME_SOURCE_INSTANCE_ID,
    RuntimeReconciliationPreflightConfig,
)
from cyber_lion.enterprise import fleet_runtime_reconciliation_preflight as preflight
from cyber_lion.enterprise.fleet_runtime_reconciliation_ingestion import _build_inventory, _load_observation

MASTER = "a" * 40
TREE = "b" * 40
PINS = ReconciliationTrustPins(
    source_id="lion-runtime-reconciliation-source",
    source_instance_id=RUNTIME_SOURCE_INSTANCE_ID,
    source_implementation_digest="1" * 64,
    trust_anchor_id="lion-runtime-reconciliation-root-01",
).validate()


class RuntimeReconciliationPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.status = root / "status.sqlite"
        self.coordination = root / "coordination.sqlite"
        self.reconciliation = root / "reconciliation.sqlite"
        self.trust = root / "reconciliation-trust.json"
        self.inventory_file = root / "repository-inventory.json"
        self.execution_receipt = root / "reconciliation-execution-receipt.json"
        for path in (self.status, self.coordination, self.reconciliation):
            path.touch()
        self.trust.write_text(json.dumps({
            "source_id": PINS.source_id,
            "source_instance_id": PINS.source_instance_id,
            "source_implementation_digest": PINS.source_implementation_digest,
            "trust_anchor_id": PINS.trust_anchor_id,
        }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        self.observed_at = "2026-08-22T02:20:00+00:00"
        self.write_inventory(MASTER)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_inventory(self, master: str) -> None:
        value = {
            "schema_version": "1.0.0",
            "repository": REPOSITORY,
            "inventory_revision": 7,
            "default_branch": "master",
            "default_head_sha": master,
            "observed_at": self.observed_at,
            "branches": [{
                "branch": "mission/example",
                "branch_head_sha": "c" * 40,
                "mission_id": "MISSION-EXAMPLE",
                "baseline_sha": "d" * 40,
                "ownership_state": "TERMINAL",
                "ancestry_state": "HEAD_ANCESTOR_OF_DEFAULT",
                "ahead_by": 0,
                "behind_by": 1,
                "superseded_by_branch": None,
                "supersession_provenance_ref": None,
                "source_provenance_ref": "runtime-observation:test",
                "epistemic_class": "OBSERVED",
                "observed_at": self.observed_at,
            }],
        }
        self.inventory_file.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def config(self) -> RuntimeReconciliationPreflightConfig:
        return RuntimeReconciliationPreflightConfig(REPOSITORY, MASTER, TREE).validate()

    def paths(self):
        return {
            "status": self.status,
            "coordination": self.coordination,
            "reconciliation": self.reconciliation,
            "trust": self.trust,
            "inventory": self.inventory_file,
            "execution_receipt": self.execution_receipt,
        }

    def expected_inventory(self, master: str = MASTER):
        raw = self.inventory_file.read_bytes()
        observation = _load_observation(raw, repository=REPOSITORY, current_master=master)
        return _build_inventory(observation, PINS)

    def head_for(self, inv=None):
        inv = inv or self.expected_inventory()
        return {
            "repository": inv.repository,
            "inventory_id": inv.inventory_id,
            "inventory_revision": inv.inventory_revision,
            "inventory_digest": inv.inventory_digest,
            "default_head_sha": inv.default_head_sha,
            "observed_at": inv.observed_at,
        }

    def bounded_state(
        self,
        *,
        inv=None,
        head=None,
        report: bool = False,
        receipt: bool = False,
        consumed: int = 0,
    ):
        inv = inv or self.expected_inventory()
        if head is None:
            head = self.head_for(inv)
        reports = ()
        receipts = ()
        if report:
            reports = ({
                "report_digest": "2" * 64,
                "report_id": "report-preflight",
                "repository": inv.repository,
                "inventory_id": inv.inventory_id,
                "inventory_revision": inv.inventory_revision,
                "inventory_digest": inv.inventory_digest,
                "closure_preconditions_digest": "3" * 64,
                "default_head_sha": inv.default_head_sha,
                "disposition": "CONVERGED",
                "observed_at": inv.observed_at,
            },)
        if receipt:
            if not report:
                raise AssertionError("test receipt requires report")
            receipts = ({
                "receipt_digest": "4" * 64,
                "receipt_id": "receipt-preflight",
                "report_digest": "2" * 64,
                "repository": inv.repository,
                "inventory_id": inv.inventory_id,
                "inventory_revision": inv.inventory_revision,
                "inventory_digest": inv.inventory_digest,
                "closure_preconditions_digest": "3" * 64,
                "default_head_sha": inv.default_head_sha,
                "issued_at": inv.observed_at,
                "purpose": RECEIPT_PURPOSE,
                "consumed": consumed,
            },)
        return {
            "head": head,
            "reports": reports,
            "receipts": receipts,
            "report_count": len(reports),
            "receipt_count": len(receipts),
            "receipt_consumed_count": int(bool(receipts) and consumed != 0),
        }

    def canonical_view(self, state):
        reports = state["reports"]
        receipts = state["receipts"]
        report = None if not reports else dict(reports[0])
        receipt = None if not receipts else dict(receipts[0])
        consumed = 0 if receipt is None else int(receipt["consumed"])
        return {
            "head": deepcopy(state["head"]),
            "stable": True,
            "exact_head": True,
            "report": report,
            "receipt": receipt,
            "report_bound": report is not None,
            "receipt_bound": receipt is not None and consumed == 0,
            "converged": report is not None and report.get("disposition") == "CONVERGED",
        }

    def patches_for(
        self,
        state,
        *,
        after=None,
        status=None,
        coordination=None,
        canonical=None,
    ):
        after = deepcopy(state) if after is None else after
        status = status or {"stable": True, "event_chain": True, "receipt_chain": True}
        coordination = coordination or {"stable": True, "event_chain": True}
        canonical = self.canonical_view(state) if canonical is None and state.get("head") is not None else canonical
        return (
            mock.patch.object(preflight, "_read_status", return_value=status),
            mock.patch.object(preflight, "_read_coordination", return_value=coordination),
            mock.patch.object(preflight, "_bounded_reconciliation_state", side_effect=[state, after]),
            mock.patch.object(preflight, "_read_reconciliation", return_value=canonical),
        )

    def observe_with(
        self,
        state,
        *,
        after=None,
        status=None,
        coordination=None,
        canonical=None,
    ):
        patches = self.patches_for(
            state,
            after=after,
            status=status,
            coordination=coordination,
            canonical=canonical,
        )
        for item in patches:
            item.start()
        try:
            return preflight.observe_runtime_reconciliation_preflight(
                self.config(), physical_paths=self.paths()
            )
        finally:
            for item in reversed(patches):
                item.stop()

    def test_coherent_current_clean_state_remains_admissible(self) -> None:
        result = self.observe_with(self.bounded_state())
        self.assertEqual(result.inventory_state, "CURRENT")
        self.assertEqual(result.reconciliation_state, "CLEAN_PRE_EXECUTION")
        self.assertTrue(result.runtime_source_healthy)
        self.assertTrue(result.f005_q_admissible)
        self.assertEqual(result.next_step, "RUN_F005_Q")

    def test_coherent_stale_state_still_selects_f005_j_refresh(self) -> None:
        self.write_inventory("e" * 40)
        inv = self.expected_inventory(master="e" * 40)
        result = self.observe_with(self.bounded_state(inv=inv))
        self.assertEqual(result.inventory_state, "STALE")
        self.assertFalse(result.f005_q_admissible)
        self.assertEqual(result.next_step, "REFRESH_F005_J")

    def test_missing_inventory_selects_f005_j_refresh(self) -> None:
        self.inventory_file.unlink()
        state = self.bounded_state()
        state["head"] = None
        result = self.observe_with(state, canonical=None)
        self.assertEqual(result.inventory_state, "MISSING")
        self.assertEqual(result.next_step, "REFRESH_F005_J")
        self.assertFalse(result.f005_q_admissible)

    def test_stale_inventory_with_missing_recorded_head_is_missing(self) -> None:
        self.write_inventory("e" * 40)
        inv = self.expected_inventory(master="e" * 40)
        state = self.bounded_state(inv=inv)
        state["head"] = None
        result = self.observe_with(state, canonical=None)
        self.assertEqual(result.inventory_state, "MISSING")
        self.assertEqual(result.next_step, "REFRESH_F005_J")

    def test_inventory_head_conflict_denies(self) -> None:
        state = self.bounded_state()
        state["head"] = dict(state["head"])
        state["head"]["inventory_digest"] = "f" * 64
        canonical = self.canonical_view(state)
        result = self.observe_with(state, canonical=canonical)
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_existing_report_denies_execution(self) -> None:
        result = self.observe_with(self.bounded_state(report=True))
        self.assertEqual(result.reconciliation_state, "REPORT_ALREADY_PRESENT")
        self.assertFalse(result.f005_q_admissible)
        self.assertEqual(result.next_step, "DENY")

    def test_existing_receipt_denies_execution(self) -> None:
        result = self.observe_with(self.bounded_state(report=True, receipt=True))
        self.assertEqual(result.reconciliation_state, "RECEIPT_ALREADY_PRESENT")
        self.assertFalse(result.f005_q_admissible)

    def test_consumed_receipt_denies_execution_without_becoming_clean(self) -> None:
        result = self.observe_with(self.bounded_state(report=True, receipt=True, consumed=1))
        self.assertEqual(result.reconciliation_state, "RECEIPT_ALREADY_PRESENT")
        self.assertFalse(result.f005_q_admissible)

    def test_execution_receipt_denies_execution(self) -> None:
        self.execution_receipt.write_text("{}", encoding="utf-8")
        result = self.observe_with(self.bounded_state())
        self.assertEqual(result.reconciliation_state, "EXECUTION_ALREADY_RECORDED")
        self.assertFalse(result.f005_q_admissible)

    def test_stale_inventory_with_unstable_status_is_conflicting(self) -> None:
        self.write_inventory("e" * 40)
        inv = self.expected_inventory(master="e" * 40)
        result = self.observe_with(
            self.bounded_state(inv=inv),
            status={"stable": False, "event_chain": True, "receipt_chain": True},
        )
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_stale_inventory_with_broken_status_chain_is_conflicting(self) -> None:
        self.write_inventory("e" * 40)
        inv = self.expected_inventory(master="e" * 40)
        result = self.observe_with(
            self.bounded_state(inv=inv),
            status={"stable": True, "event_chain": False, "receipt_chain": True},
        )
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_stale_inventory_with_unstable_coordination_is_conflicting(self) -> None:
        self.write_inventory("e" * 40)
        inv = self.expected_inventory(master="e" * 40)
        result = self.observe_with(
            self.bounded_state(inv=inv),
            coordination={"stable": False, "event_chain": True},
        )
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_reconciliation_head_change_between_readers_denies(self) -> None:
        before = self.bounded_state()
        after = deepcopy(before)
        after["head"] = dict(after["head"])
        after["head"]["inventory_digest"] = "f" * 64
        result = self.observe_with(before, after=after)
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.reconciliation_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_f005_g_head_must_equal_bounded_preflight_head(self) -> None:
        state = self.bounded_state()
        canonical = self.canonical_view(state)
        canonical["head"] = dict(canonical["head"])
        canonical["head"]["inventory_digest"] = "f" * 64
        result = self.observe_with(state, canonical=canonical)
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_reconciliation_report_change_between_readers_denies(self) -> None:
        before = self.bounded_state()
        after = self.bounded_state(report=True)
        result = self.observe_with(before, after=after)
        self.assertEqual(result.reconciliation_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_reconciliation_receipt_change_between_readers_denies(self) -> None:
        before = self.bounded_state(report=True)
        after = self.bounded_state(report=True, receipt=True)
        result = self.observe_with(before, after=after)
        self.assertEqual(result.reconciliation_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_reconciliation_consumption_change_between_readers_denies(self) -> None:
        before = self.bounded_state(report=True, receipt=True, consumed=0)
        after = self.bounded_state(report=True, receipt=True, consumed=1)
        result = self.observe_with(before, after=after)
        self.assertEqual(result.reconciliation_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_multiple_reports_are_structurally_conflicting(self) -> None:
        state = self.bounded_state(report=True)
        duplicate = dict(state["reports"][0])
        duplicate["report_digest"] = "5" * 64
        duplicate["report_id"] = "report-duplicate"
        state["reports"] = (state["reports"][0], duplicate)
        state["report_count"] = 2
        canonical = self.canonical_view({**state, "reports": (state["reports"][0],)})
        result = self.observe_with(state, canonical=canonical)
        self.assertEqual(result.reconciliation_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_execution_receipt_disappearing_during_read_is_conflicting(self) -> None:
        with mock.patch.object(preflight, "_execution_receipt_state", return_value=(True, False)):
            result = self.observe_with(self.bounded_state())
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.reconciliation_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_execution_receipt_appearing_during_read_is_conflicting(self) -> None:
        with mock.patch.object(preflight, "_execution_receipt_state", return_value=(False, False)):
            result = self.observe_with(self.bounded_state())
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.reconciliation_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_execution_receipt_presence_helper_detects_appearance(self) -> None:
        with mock.patch.object(preflight, "_file_present", side_effect=[False, True]):
            present, stable = preflight._execution_receipt_state(self.execution_receipt)
        self.assertFalse(present)
        self.assertFalse(stable)

    def test_trust_file_race_is_conflicting(self) -> None:
        real = preflight._stable_bytes

        def race(path, name):
            if name == "reconciliation trust":
                raise preflight.RuntimeReconciliationPreflightError("race")
            return real(path, name)

        with mock.patch.object(preflight, "_stable_bytes", side_effect=race):
            result = self.observe_with(self.bounded_state())
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_inventory_file_race_is_conflicting(self) -> None:
        real = preflight._stable_bytes

        def race(path, name):
            if name == "repository inventory":
                raise preflight.RuntimeReconciliationPreflightError("race")
            return real(path, name)

        with mock.patch.object(preflight, "_stable_bytes", side_effect=race):
            result = self.observe_with(self.bounded_state())
        self.assertEqual(result.inventory_state, "CONFLICTING")
        self.assertEqual(result.next_step, "DENY")

    def test_result_digest_is_deterministic_for_same_observation(self) -> None:
        first = self.observe_with(self.bounded_state())
        second = self.observe_with(self.bounded_state())
        self.assertEqual(first.result_digest, second.result_digest)

    def test_bounded_query_helper_does_not_mutate_database(self) -> None:
        db = Path(self.tmp.name) / "counts.sqlite"
        conn = sqlite3.connect(db)
        try:
            conn.executescript("""
            CREATE TABLE reconciliation_inventory_head(
                repository TEXT PRIMARY KEY, inventory_id TEXT, inventory_revision INTEGER,
                inventory_digest TEXT, default_head_sha TEXT, observed_at TEXT
            );
            CREATE TABLE reconciliation_report(
                report_digest TEXT PRIMARY KEY, report_id TEXT, repository TEXT, inventory_id TEXT,
                inventory_revision INTEGER, inventory_digest TEXT, closure_preconditions_digest TEXT,
                default_head_sha TEXT, disposition TEXT, observed_at TEXT
            );
            CREATE TABLE convergence_receipt(
                receipt_digest TEXT PRIMARY KEY, receipt_id TEXT, report_digest TEXT, repository TEXT,
                inventory_id TEXT, inventory_revision INTEGER, inventory_digest TEXT,
                closure_preconditions_digest TEXT, default_head_sha TEXT, issued_at TEXT,
                purpose TEXT, consumed INTEGER
            );
            """)
            conn.execute(
                "INSERT INTO reconciliation_inventory_head VALUES(?,?,?,?,?,?)",
                (REPOSITORY, "inventory-1", 1, "1" * 64, MASTER, self.observed_at),
            )
            conn.commit()
        finally:
            conn.close()
        before = sha256(db.read_bytes()).hexdigest()
        state = preflight._bounded_reconciliation_state(db, REPOSITORY)
        after = sha256(db.read_bytes()).hexdigest()
        self.assertEqual(state["report_count"], 0)
        self.assertEqual(state["receipt_count"], 0)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
