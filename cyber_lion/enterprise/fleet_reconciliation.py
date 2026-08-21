"""Fail-closed observability reconciliation for F005-E.

The layer turns a pinned repository inventory and explicit closure preconditions into
deterministic reconciliation evidence. It emits a one-shot convergence receipt only
for an exact current inventory whose closure blockers are all absent. It performs no
GitHub write, merge, release, deploy, authority consumption, or mission close effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
from typing import Callable, Protocol

from cyber_lion.contracts.fleet_reconciliation import (
    BranchEvidence,
    BranchReconciliation,
    ClosurePreconditions,
    ConvergenceReceipt,
    CONVERGED_BRANCH_CLASSES,
    ReconciliationReport,
    ReconciliationTrustPins,
    RepositoryInventory,
)


class FleetReconciliationError(RuntimeError):
    """Fail-closed reconciliation state or evidence error."""


class RepositoryInventoryProvider(Protocol):
    def snapshot(self, repository: str) -> RepositoryInventory:
        ...


class ClosurePreconditionsProvider(Protocol):
    def snapshot(self, repository: str, inventory: RepositoryInventory) -> ClosurePreconditions:
        ...


def _utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise FleetReconciliationError("trusted clock must return timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FleetReconciliationError("stored observation time is invalid") from exc
    if parsed.tzinfo is None:
        raise FleetReconciliationError("stored observation time must be timezone-aware")
    return parsed.astimezone(timezone.utc)


class BranchReconciliationClassifier:
    """Pure deterministic classifier over trusted branch and closure evidence."""

    @staticmethod
    def _classify_one(inventory: RepositoryInventory, evidence: BranchEvidence) -> BranchReconciliation:
        evidence.validate()
        if evidence.epistemic_class not in {"OBSERVED", "ANCHORED"}:
            classification = "UNCLASSIFIED"
            rationale = "INSUFFICIENT_TRUSTED_EVIDENCE"
        elif evidence.ownership_state == "UNOWNED":
            classification = "UNCLASSIFIED"
            rationale = "UNOWNED_BRANCH"
        elif evidence.ownership_state == "UNKNOWN":
            classification = "UNCLASSIFIED"
            rationale = "UNKNOWN_BRANCH_OWNERSHIP"
        elif evidence.ownership_state == "ACTIVE":
            classification = "ACTIVE_MISSION"
            rationale = "ACTIVE_MISSION_OWNS_BRANCH"
        elif evidence.ancestry_state in {"IDENTICAL", "HEAD_ANCESTOR_OF_DEFAULT"}:
            classification = "ALREADY_INTEGRATED"
            rationale = "HEAD_ALREADY_IN_DEFAULT_HISTORY"
        elif (
            evidence.superseded_by_branch is not None
            and evidence.supersession_provenance_ref is not None
            and evidence.ownership_state == "TERMINAL"
        ):
            classification = "SUPERSEDED"
            rationale = "EXPLICIT_SUCCESSOR_SUPERSEDES_BRANCH"
        elif evidence.ancestry_state == "DEFAULT_ANCESTOR_OF_HEAD":
            classification = "MERGE_CANDIDATE"
            rationale = "BRANCH_AHEAD_OF_CURRENT_DEFAULT"
        elif evidence.ancestry_state == "DIVERGED":
            classification = "PORT_REQUIRED"
            rationale = "BRANCH_DIVERGED_FROM_CURRENT_DEFAULT"
        elif evidence.ancestry_state == "NO_COMMON_ANCESTOR":
            classification = "FOREIGN_HISTORY"
            rationale = "NO_COMMON_ANCESTOR"
        else:
            classification = "UNCLASSIFIED"
            rationale = "INSUFFICIENT_TRUSTED_EVIDENCE"

        return BranchReconciliation(
            repository=inventory.repository,
            inventory_digest=inventory.inventory_digest,
            branch=evidence.branch,
            branch_head_sha=evidence.branch_head_sha,
            mission_id=evidence.mission_id,
            baseline_sha=evidence.baseline_sha,
            classification=classification,
            rationale_code=rationale,
            evidence_digest=evidence.evidence_digest,
            observed_at=evidence.observed_at,
        ).validate()

    def classify(
        self,
        inventory: RepositoryInventory,
        closure_preconditions: ClosurePreconditions,
    ) -> ReconciliationReport:
        if type(inventory) is not RepositoryInventory:
            raise FleetReconciliationError("inventory must use exact RepositoryInventory contract")
        if type(closure_preconditions) is not ClosurePreconditions:
            raise FleetReconciliationError("closure_preconditions must use exact contract type")
        inventory.validate()
        closure_preconditions.validate()
        if (
            closure_preconditions.repository != inventory.repository
            or closure_preconditions.inventory_digest != inventory.inventory_digest
        ):
            raise FleetReconciliationError("closure preconditions do not bind exact inventory")
        if _parse_utc(closure_preconditions.observed_at) != _parse_utc(inventory.observed_at):
            raise FleetReconciliationError("closure preconditions must be observed atomically with inventory")

        results = tuple(self._classify_one(inventory, item) for item in inventory.branches)

        anomalies: set[str] = set(closure_preconditions.blocker_codes())
        for evidence, item in zip(inventory.branches, results):
            if evidence.ownership_state == "UNOWNED":
                anomalies.add("UNOWNED_BRANCH")
            elif evidence.ownership_state == "UNKNOWN":
                anomalies.add("UNKNOWN_BRANCH_OWNERSHIP")
            mapping = {
                "ACTIVE_MISSION": "ACTIVE_MISSION",
                "MERGE_CANDIDATE": "MERGE_CANDIDATE",
                "PORT_REQUIRED": "PORT_REQUIRED",
                "FOREIGN_HISTORY": "FOREIGN_HISTORY",
                "UNCLASSIFIED": "UNCLASSIFIED_BRANCH",
            }
            code = mapping.get(item.classification)
            if code:
                anomalies.add(code)
            if (
                item.classification in {"ACTIVE_MISSION", "MERGE_CANDIDATE", "PORT_REQUIRED"}
                and item.baseline_sha is not None
                and item.baseline_sha != inventory.default_head_sha
            ):
                anomalies.add("BASELINE_DRIFT")

        if not results:
            anomalies.add("EMPTY_INVENTORY")

        branch_converged = bool(results) and all(
            item.classification in CONVERGED_BRANCH_CLASSES for item in results
        )
        if "BASELINE_DRIFT" in anomalies:
            disposition = "STOP_REPLAN_REQUIRED"
        elif branch_converged and closure_preconditions.satisfied():
            disposition = "CONVERGED"
        else:
            disposition = "RECONCILIATION_REQUIRED"

        report_id = sha256(
            (
                f"fleet-reconciliation|{inventory.repository}|{inventory.inventory_digest}|"
                f"{closure_preconditions.preconditions_digest}"
            ).encode("utf-8")
        ).hexdigest()
        return ReconciliationReport.build(
            schema_version="1.0.0",
            report_id=report_id,
            repository=inventory.repository,
            inventory_id=inventory.inventory_id,
            inventory_revision=inventory.inventory_revision,
            inventory_digest=inventory.inventory_digest,
            default_head_sha=inventory.default_head_sha,
            closure_preconditions=closure_preconditions,
            closure_preconditions_digest=closure_preconditions.preconditions_digest,
            observed_at=inventory.observed_at,
            disposition=disposition,
            anomaly_codes=tuple(anomalies),
            branches=results,
        )


class ReconciliationStore:
    """SQLite-backed evidence store with monotonic inventories and one-shot receipts."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        trust_pins: ReconciliationTrustPins,
        clock: Callable[[], datetime],
    ) -> None:
        trust_pins.validate()
        self._db_path = str(Path(db_path))
        self._pins = trust_pins
        self._clock = clock
        self._conn = sqlite3.connect(self._db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reconciliation_inventory_head(
                repository TEXT PRIMARY KEY,
                inventory_id TEXT NOT NULL,
                inventory_revision INTEGER NOT NULL,
                inventory_digest TEXT NOT NULL UNIQUE,
                default_head_sha TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reconciliation_report(
                report_digest TEXT PRIMARY KEY,
                report_id TEXT NOT NULL UNIQUE,
                repository TEXT NOT NULL,
                inventory_id TEXT NOT NULL,
                inventory_revision INTEGER NOT NULL,
                inventory_digest TEXT NOT NULL,
                closure_preconditions_digest TEXT NOT NULL,
                default_head_sha TEXT NOT NULL,
                disposition TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS convergence_receipt(
                receipt_digest TEXT PRIMARY KEY,
                receipt_id TEXT NOT NULL UNIQUE,
                report_digest TEXT NOT NULL UNIQUE,
                repository TEXT NOT NULL,
                inventory_id TEXT NOT NULL,
                inventory_revision INTEGER NOT NULL,
                inventory_digest TEXT NOT NULL,
                closure_preconditions_digest TEXT NOT NULL,
                default_head_sha TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                purpose TEXT NOT NULL,
                consumed INTEGER NOT NULL CHECK(consumed IN (0,1))
            );
            """
        )

    def _current(self, repository: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM reconciliation_inventory_head WHERE repository=?", (repository,)
        ).fetchone()

    def _require_current_binding(
        self,
        *,
        repository: str,
        inventory_id: str,
        inventory_revision: int,
        inventory_digest: str,
        default_head_sha: str,
    ) -> sqlite3.Row:
        current = self._current(repository)
        if current is None:
            raise FleetReconciliationError("repository inventory has not been recorded")
        expected = (
            inventory_id,
            inventory_revision,
            inventory_digest,
            default_head_sha,
        )
        actual = (
            current["inventory_id"],
            int(current["inventory_revision"]),
            current["inventory_digest"],
            current["default_head_sha"],
        )
        if actual != expected:
            raise FleetReconciliationError("reconciliation evidence is stale relative to current inventory")
        return current

    def record_inventory(self, inventory: RepositoryInventory) -> None:
        if type(inventory) is not RepositoryInventory:
            raise FleetReconciliationError("inventory must use exact RepositoryInventory contract")
        inventory.validate()
        if inventory.source_pins().binding() != self._pins.binding():
            raise FleetReconciliationError("inventory source substitution denied")

        current = self._current(inventory.repository)
        if current is not None:
            if inventory.inventory_revision <= int(current["inventory_revision"]):
                raise FleetReconciliationError("stale or replayed inventory revision denied")
            if _parse_utc(inventory.observed_at) <= _parse_utc(current["observed_at"]):
                raise FleetReconciliationError("inventory observation time must advance monotonically")

        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                """INSERT INTO reconciliation_inventory_head(
                   repository,inventory_id,inventory_revision,inventory_digest,default_head_sha,observed_at
                   ) VALUES(?,?,?,?,?,?)
                   ON CONFLICT(repository) DO UPDATE SET
                   inventory_id=excluded.inventory_id,
                   inventory_revision=excluded.inventory_revision,
                   inventory_digest=excluded.inventory_digest,
                   default_head_sha=excluded.default_head_sha,
                   observed_at=excluded.observed_at""",
                (
                    inventory.repository,
                    inventory.inventory_id,
                    inventory.inventory_revision,
                    inventory.inventory_digest,
                    inventory.default_head_sha,
                    inventory.observed_at,
                ),
            )
            self._conn.execute("COMMIT")
        except Exception:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise

    def record_report(self, report: ReconciliationReport) -> None:
        if type(report) is not ReconciliationReport:
            raise FleetReconciliationError("report must use exact ReconciliationReport contract")
        report.validate()
        self._require_current_binding(
            repository=report.repository,
            inventory_id=report.inventory_id,
            inventory_revision=report.inventory_revision,
            inventory_digest=report.inventory_digest,
            default_head_sha=report.default_head_sha,
        )
        try:
            self._conn.execute(
                """INSERT INTO reconciliation_report(
                   report_digest,report_id,repository,inventory_id,inventory_revision,inventory_digest,
                   closure_preconditions_digest,default_head_sha,disposition,observed_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    report.report_digest,
                    report.report_id,
                    report.repository,
                    report.inventory_id,
                    report.inventory_revision,
                    report.inventory_digest,
                    report.closure_preconditions_digest,
                    report.default_head_sha,
                    report.disposition,
                    report.observed_at,
                ),
            )
        except sqlite3.IntegrityError as exc:
            existing = self._conn.execute(
                "SELECT report_digest FROM reconciliation_report WHERE report_id=?",
                (report.report_id,),
            ).fetchone()
            if existing is not None and existing["report_digest"] == report.report_digest:
                return
            raise FleetReconciliationError("reconciliation report identity collision or replay") from exc

    def has_report(self, report_digest: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM reconciliation_report WHERE report_digest=?", (report_digest,)
        ).fetchone() is not None

    def issue_convergence_receipt(self, report: ReconciliationReport) -> ConvergenceReceipt:
        if type(report) is not ReconciliationReport:
            raise FleetReconciliationError("report must use exact ReconciliationReport contract")
        report.validate()
        if report.disposition != "CONVERGED" or not report.closure_preconditions.satisfied():
            raise FleetReconciliationError(
                "convergence receipt requires CONVERGED report with satisfied closure preconditions"
            )
        self._require_current_binding(
            repository=report.repository,
            inventory_id=report.inventory_id,
            inventory_revision=report.inventory_revision,
            inventory_digest=report.inventory_digest,
            default_head_sha=report.default_head_sha,
        )
        stored = self._conn.execute(
            """SELECT report_digest,closure_preconditions_digest
               FROM reconciliation_report WHERE report_digest=?""",
            (report.report_digest,),
        ).fetchone()
        if stored is None:
            raise FleetReconciliationError("report must be persisted before receipt issuance")
        if stored["closure_preconditions_digest"] != report.closure_preconditions_digest:
            raise FleetReconciliationError("stored closure precondition binding mismatch")
        duplicate = self._conn.execute(
            "SELECT 1 FROM convergence_receipt WHERE report_digest=?", (report.report_digest,)
        ).fetchone()
        if duplicate is not None:
            raise FleetReconciliationError("convergence receipt replay denied")

        issued_at = _utc(self._clock())
        receipt_id = sha256(
            (
                f"convergence-receipt|{report.report_digest}|{report.inventory_revision}|"
                f"{report.closure_preconditions_digest}"
            ).encode("utf-8")
        ).hexdigest()
        receipt = ConvergenceReceipt.build(
            schema_version="1.0.0",
            receipt_id=receipt_id,
            repository=report.repository,
            inventory_id=report.inventory_id,
            inventory_revision=report.inventory_revision,
            inventory_digest=report.inventory_digest,
            report_id=report.report_id,
            report_digest=report.report_digest,
            closure_preconditions_digest=report.closure_preconditions_digest,
            default_head_sha=report.default_head_sha,
            issued_at=issued_at,
        )
        self._conn.execute(
            """INSERT INTO convergence_receipt(
               receipt_digest,receipt_id,report_digest,repository,inventory_id,inventory_revision,
               inventory_digest,closure_preconditions_digest,default_head_sha,issued_at,purpose,consumed
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,0)""",
            (
                receipt.receipt_digest,
                receipt.receipt_id,
                receipt.report_digest,
                receipt.repository,
                receipt.inventory_id,
                receipt.inventory_revision,
                receipt.inventory_digest,
                receipt.closure_preconditions_digest,
                receipt.default_head_sha,
                receipt.issued_at,
                receipt.purpose,
            ),
        )
        return receipt

    def claim_close_evidence_once(self, receipt: ConvergenceReceipt) -> str:
        """Consume evidence once; returned digest is not close or merge authority."""
        if type(receipt) is not ConvergenceReceipt:
            raise FleetReconciliationError("receipt must use exact ConvergenceReceipt contract")
        receipt.validate()
        self._require_current_binding(
            repository=receipt.repository,
            inventory_id=receipt.inventory_id,
            inventory_revision=receipt.inventory_revision,
            inventory_digest=receipt.inventory_digest,
            default_head_sha=receipt.default_head_sha,
        )
        row = self._conn.execute(
            "SELECT * FROM convergence_receipt WHERE receipt_digest=?", (receipt.receipt_digest,)
        ).fetchone()
        if row is None:
            raise FleetReconciliationError("unknown convergence receipt")
        exact = (
            row["receipt_id"], row["report_digest"], row["repository"], row["inventory_id"],
            int(row["inventory_revision"]), row["inventory_digest"],
            row["closure_preconditions_digest"], row["default_head_sha"],
            row["issued_at"], row["purpose"],
        )
        expected = (
            receipt.receipt_id, receipt.report_digest, receipt.repository, receipt.inventory_id,
            receipt.inventory_revision, receipt.inventory_digest,
            receipt.closure_preconditions_digest, receipt.default_head_sha,
            receipt.issued_at, receipt.purpose,
        )
        if exact != expected:
            raise FleetReconciliationError("convergence receipt binding mismatch")
        if int(row["consumed"]) != 0:
            raise FleetReconciliationError("convergence receipt replay denied")
        updated = self._conn.execute(
            "UPDATE convergence_receipt SET consumed=1 WHERE receipt_digest=? AND consumed=0",
            (receipt.receipt_digest,),
        )
        if updated.rowcount != 1:
            raise FleetReconciliationError("convergence receipt replay race denied")
        return receipt.receipt_digest

    def receipt_consumed(self, receipt_digest: str) -> bool:
        row = self._conn.execute(
            "SELECT consumed FROM convergence_receipt WHERE receipt_digest=?", (receipt_digest,)
        ).fetchone()
        if row is None:
            raise FleetReconciliationError("unknown convergence receipt")
        return bool(row["consumed"])


@dataclass(frozen=True)
class ReconciliationRun:
    inventory_digest: str
    closure_preconditions_digest: str
    report: ReconciliationReport
    convergence_receipt: ConvergenceReceipt | None


class RepositoryConvergenceGate:
    """Evidence-only close precondition gate; never performs the close effect."""

    def __init__(self, store: ReconciliationStore) -> None:
        self._store = store

    def observe_close_evidence_once(self, receipt: ConvergenceReceipt) -> str:
        return self._store.claim_close_evidence_once(receipt)


class FleetReconciler:
    """Read/compute/persist orchestration over trusted inventory and closure providers."""

    def __init__(
        self,
        *,
        provider: RepositoryInventoryProvider,
        closure_provider: ClosurePreconditionsProvider,
        classifier: BranchReconciliationClassifier,
        store: ReconciliationStore,
    ) -> None:
        self._provider = provider
        self._closure_provider = closure_provider
        self._classifier = classifier
        self._store = store

    def reconcile(self, repository: str) -> ReconciliationRun:
        if not isinstance(repository, str) or not repository.strip() or "\x00" in repository:
            raise FleetReconciliationError("repository is invalid")
        inventory = self._provider.snapshot(repository)
        if type(inventory) is not RepositoryInventory:
            raise FleetReconciliationError("inventory provider returned invalid contract type")
        if inventory.repository != repository:
            raise FleetReconciliationError("inventory provider repository substitution denied")
        closure = self._closure_provider.snapshot(repository, inventory)
        if type(closure) is not ClosurePreconditions:
            raise FleetReconciliationError("closure provider returned invalid contract type")
        if closure.repository != repository or closure.inventory_digest != inventory.inventory_digest:
            raise FleetReconciliationError("closure provider binding mismatch")
        self._store.record_inventory(inventory)
        report = self._classifier.classify(inventory, closure)
        self._store.record_report(report)
        receipt = None
        if report.disposition == "CONVERGED":
            receipt = self._store.issue_convergence_receipt(report)
        return ReconciliationRun(
            inventory.inventory_digest,
            closure.preconditions_digest,
            report,
            receipt,
        )
