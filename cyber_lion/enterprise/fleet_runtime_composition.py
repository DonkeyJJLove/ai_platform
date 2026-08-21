"""F005-H composition root for the existing durable LION fleet stores.

This module only creates/reopens the canonical persistence layers. It never inserts
mission, runtime, heartbeat, result, lease, reconciliation, effect, or authority
facts and never declares the fleet closable.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Callable, Mapping

from cyber_lion.contracts.fleet_reconciliation import ReconciliationTrustPins
from cyber_lion.contracts.fleet_runtime_composition import (
    COORDINATION_DB_PATH,
    RECONCILIATION_DB_PATH,
    RUNTIME_ROOT,
    STATUS_DB_PATH,
    RuntimeCompositionConfig,
    RuntimeCompositionReceipt,
    canonical_json,
)
from cyber_lion.contracts.fleet_status import VerificationTrustPins
from cyber_lion.enterprise.fleet_coordination_state import FleetCoordinationStore
from cyber_lion.enterprise.fleet_reconciliation import ReconciliationStore
from cyber_lion.enterprise.fleet_status_ingestion import FleetStatusIngestion
from cyber_lion.enterprise.fleet_status_projection import FleetStatusProjector
from cyber_lion.enterprise.fleet_status_state import FleetStatusStateError, FleetStatusStore


class FleetRuntimeCompositionError(RuntimeError):
    pass


_STATUS_SCHEMA = {
    "fleet_meta": {"singleton", "registry_instance_id", "revision", "event_head", "receipt_head"},
    "fleet_identity": {"mission_id", "executor_id", "repository", "baseline_sha", "baseline_tree_sha", "branch"},
    "fleet_mission": {"mission_id", "status"},
    "fleet_runtime": {"mission_id", "runtime_id"},
    "fleet_heartbeat": {"mission_id", "deadline_seconds", "observed_at"},
    "fleet_projection": {"mission_id", "kind", "state", "observed_at"},
    "fleet_verification": {"mission_id", "verification_state"},
    "fleet_lease": {"lease_id", "mission_id", "state"},
    "fleet_event": {"seq", "event_type", "mission_id", "payload_json", "previous_digest", "event_digest", "observed_at"},
    "fleet_receipt": {"seq", "receipt_id", "mission_id", "source_ref", "previous_digest", "receipt_digest", "observed_at"},
    "fleet_source_decision": {"seq", "mission_id", "dimension", "decision_type", "decision_json"},
}
_COORDINATION_SCHEMA = {
    "fleet_coordination_meta": {"singleton", "coordinator_id", "revision", "event_head"},
    "fleet_coordination_mission": {"mission_id", "state", "generation", "dispatch_id", "fencing_token", "branch", "updated_at"},
    "fleet_coordination_active_lease": {"repository", "lease_kind", "resource", "mission_id", "dispatch_id", "generation"},
    "fleet_coordination_event": {"seq", "event_id", "event_type", "mission_id", "payload_json", "previous_digest", "event_digest", "observed_at"},
}
_RECONCILIATION_SCHEMA = {
    "reconciliation_inventory_head": {"repository", "inventory_id", "inventory_revision", "inventory_digest", "default_head_sha", "observed_at"},
    "reconciliation_report": {"report_digest", "report_id", "repository", "inventory_id", "inventory_revision", "inventory_digest", "closure_preconditions_digest", "default_head_sha", "disposition", "observed_at"},
    "convergence_receipt": {"receipt_digest", "receipt_id", "report_digest", "repository", "inventory_id", "inventory_revision", "inventory_digest", "closure_preconditions_digest", "default_head_sha", "issued_at", "purpose", "consumed"},
}


class FailClosedVerificationSource:
    """No evidence source is invented by bootstrap; verification resolution stays denied."""

    def resolve(self, verification_id: str):
        raise FleetStatusStateError(f"trusted verification source unavailable for {verification_id}")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _verify_schema(path: Path, required: Mapping[str, set[str]]) -> None:
    conn = _ro(path)
    try:
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing_tables = sorted(set(required) - tables)
        if missing_tables:
            raise FleetRuntimeCompositionError("canonical runtime store schema incomplete: " + ",".join(missing_tables))
        for table, columns in required.items():
            actual = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
            missing_columns = sorted(columns - actual)
            if missing_columns:
                raise FleetRuntimeCompositionError(
                    f"canonical runtime store columns incomplete for {table}: " + ",".join(missing_columns)
                )
    finally:
        conn.close()


def _default_physical_paths(config: RuntimeCompositionConfig) -> dict[str, Path]:
    if os.name != "nt":
        raise FleetRuntimeCompositionError("F005-H runtime composition requires Windows lion-runtime")
    return {
        "root": Path(config.runtime_root),
        "status": Path(config.status_db_path),
        "coordination": Path(config.coordination_db_path),
        "reconciliation": Path(config.reconciliation_db_path),
    }


def _resolve_physical_paths(
    config: RuntimeCompositionConfig,
    physical_paths: Mapping[str, Path] | None,
) -> dict[str, Path]:
    if physical_paths is None:
        return _default_physical_paths(config)
    required = {"root", "status", "coordination", "reconciliation"}
    if set(physical_paths) != required:
        raise FleetRuntimeCompositionError("test/runtime physical path mapping is incomplete")
    value = {name: Path(path) for name, path in physical_paths.items()}
    if any(not path.is_absolute() for path in value.values()):
        raise FleetRuntimeCompositionError("physical runtime paths must be absolute")
    if any(value[name].parent != value["root"] for name in ("status", "coordination", "reconciliation")):
        raise FleetRuntimeCompositionError("physical runtime stores must be direct children of runtime root")
    return value


@dataclass
class RuntimeComposition:
    config: RuntimeCompositionConfig
    status: FleetStatusStore
    coordination: FleetCoordinationStore
    reconciliation: ReconciliationStore
    physical_paths: dict[str, Path]

    def close(self) -> None:
        errors = []
        for store in (self.status, self.coordination, self.reconciliation):
            try:
                store.close()
            except Exception as exc:  # pragma: no cover - defensive close aggregation
                errors.append(exc)
        if errors:
            raise FleetRuntimeCompositionError("runtime store close failed") from errors[0]

    def status_snapshot(self):
        return FleetStatusProjector(self.status).snapshot()

    def build_status_ingestion(self, *, adapters, trust_registry, reconciler, clock: Callable[[], datetime]):
        """Expose the existing canonical ingestion path without performing an ingestion."""
        return FleetStatusIngestion(
            self.status,
            adapters=adapters,
            trust_registry=trust_registry,
            reconciler=reconciler,
            clock=clock,
        )

    def semantic_fingerprint(self) -> dict[str, Any]:
        status_reader = self.status.open_query_reader()
        coordination_reader = self.coordination.open_query_reader()
        reconciliation_reader = _ro(self.physical_paths["reconciliation"])
        try:
            status_meta = dict(status_reader.execute(
                "SELECT registry_instance_id,revision,event_head,receipt_head FROM fleet_meta WHERE singleton=1"
            ).fetchone())
            coordination_meta = dict(coordination_reader.execute(
                "SELECT coordinator_id,revision,event_head FROM fleet_coordination_meta WHERE singleton=1"
            ).fetchone())
            reconciliation_heads = [dict(row) for row in reconciliation_reader.execute(
                "SELECT repository,inventory_id,inventory_revision,inventory_digest,default_head_sha,observed_at "
                "FROM reconciliation_inventory_head ORDER BY repository"
            )]
            return {
                "status_meta": status_meta,
                "coordination_meta": coordination_meta,
                "reconciliation_heads": reconciliation_heads,
                "status_mission_count": int(status_reader.execute("SELECT COUNT(*) FROM fleet_mission").fetchone()[0]),
                "status_runtime_count": int(status_reader.execute("SELECT COUNT(*) FROM fleet_runtime").fetchone()[0]),
                "status_verification_count": int(status_reader.execute("SELECT COUNT(*) FROM fleet_verification").fetchone()[0]),
                "coordination_mission_count": int(coordination_reader.execute(
                    "SELECT COUNT(*) FROM fleet_coordination_mission"
                ).fetchone()[0]),
                "reconciliation_inventory_count": int(reconciliation_reader.execute(
                    "SELECT COUNT(*) FROM reconciliation_inventory_head"
                ).fetchone()[0]),
            }
        finally:
            status_reader.close()
            coordination_reader.close()
            reconciliation_reader.close()


def _open_canonical_stores(
    config: RuntimeCompositionConfig,
    paths: dict[str, Path],
    *,
    verification_source,
    clock: Callable[[], datetime],
) -> RuntimeComposition:
    status = FleetStatusStore(
        paths["status"],
        registry_instance_id=config.registry_instance_id,
        clock=clock,
        verification_source=verification_source,
        verification_pins=config.verification_pins,
    )
    try:
        coordination = FleetCoordinationStore(
            paths["coordination"],
            coordinator_id=config.coordinator_instance_id,
            clock=clock,
        )
    except Exception:
        status.close()
        raise
    try:
        reconciliation = ReconciliationStore(
            paths["reconciliation"],
            trust_pins=config.reconciliation_pins,
            clock=clock,
        )
    except Exception:
        coordination.close()
        status.close()
        raise
    return RuntimeComposition(config, status, coordination, reconciliation, paths)


def _validate_all_schemas(paths: dict[str, Path]) -> None:
    _verify_schema(paths["status"], _STATUS_SCHEMA)
    _verify_schema(paths["coordination"], _COORDINATION_SCHEMA)
    _verify_schema(paths["reconciliation"], _RECONCILIATION_SCHEMA)


def _create_new_store_set(
    config: RuntimeCompositionConfig,
    paths: dict[str, Path],
    *,
    verification_source,
    clock: Callable[[], datetime],
) -> None:
    root = paths["root"]
    root.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=".f005-h-bootstrap-", dir=str(root)))
    stage = {
        "root": stage_dir,
        "status": stage_dir / paths["status"].name,
        "coordination": stage_dir / paths["coordination"].name,
        "reconciliation": stage_dir / paths["reconciliation"].name,
    }
    composition: RuntimeComposition | None = None
    moved: list[Path] = []
    try:
        composition = _open_canonical_stores(
            config,
            stage,
            verification_source=verification_source,
            clock=clock,
        )
        composition.close()
        composition = None
        _validate_all_schemas(stage)
        for name in ("status", "coordination", "reconciliation"):
            os.replace(stage[name], paths[name])
            moved.append(paths[name])
    except Exception:
        if composition is not None:
            try:
                composition.close()
            except Exception:
                pass
        for target in moved:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


def open_runtime_composition(
    config: RuntimeCompositionConfig,
    *,
    verification_source=None,
    clock: Callable[[], datetime] = _utc_now,
    physical_paths: Mapping[str, Path] | None = None,
) -> RuntimeComposition:
    config.validate()
    paths = _resolve_physical_paths(config, physical_paths)
    existing = {name: paths[name].is_file() for name in ("status", "coordination", "reconciliation")}
    if any(existing.values()) and not all(existing.values()):
        raise FleetRuntimeCompositionError("partial runtime store bootstrap denied")
    source = verification_source if verification_source is not None else FailClosedVerificationSource()
    if not any(existing.values()):
        _create_new_store_set(config, paths, verification_source=source, clock=clock)
    _validate_all_schemas(paths)
    return _open_canonical_stores(config, paths, verification_source=source, clock=clock)


def bootstrap_runtime_composition(
    config: RuntimeCompositionConfig,
    *,
    verification_source=None,
    clock: Callable[[], datetime] = _utc_now,
    physical_paths: Mapping[str, Path] | None = None,
) -> RuntimeCompositionReceipt:
    """Create/reopen canonical stores, prove reopen preservation, and never assert closure."""
    first = open_runtime_composition(
        config,
        verification_source=verification_source,
        clock=clock,
        physical_paths=physical_paths,
    )
    try:
        before = first.semantic_fingerprint()
        # Exercise the existing projection path; no status fact is written.
        first.status_snapshot()
    finally:
        first.close()

    second = open_runtime_composition(
        config,
        verification_source=verification_source,
        clock=clock,
        physical_paths=physical_paths,
    )
    try:
        after = second.semantic_fingerprint()
    finally:
        second.close()
    if before != after:
        raise FleetRuntimeCompositionError("canonical store reopen changed durable semantic state")

    empty = (
        after["status_mission_count"] == 0
        and after["coordination_mission_count"] == 0
        and after["reconciliation_inventory_count"] == 0
    )
    classification = "EMPTY_NOT_CLOSABLE" if empty else "STATE_PRESENT_REQUIRES_RUNTIME_CONVERGENCE"
    composition_digest = config.digest()
    composition_id = sha256(
        b"LION/F005-H-BOOTSTRAP/1\0" + canonical_json({
            "composition_digest": composition_digest,
            "fingerprint": after,
            "classification": classification,
        })
    ).hexdigest()
    return RuntimeCompositionReceipt(
        schema_version="1.0.0",
        composition_id=composition_id,
        repository=config.repository,
        current_master=config.current_master,
        current_master_tree=config.current_master_tree,
        composition_instance_id=config.composition_instance_id,
        runtime_root=RUNTIME_ROOT,
        status_db_path=STATUS_DB_PATH,
        coordination_db_path=COORDINATION_DB_PATH,
        reconciliation_db_path=RECONCILIATION_DB_PATH,
        status_mission_count=after["status_mission_count"],
        coordination_mission_count=after["coordination_mission_count"],
        reconciliation_inventory_count=after["reconciliation_inventory_count"],
        state_classification=classification,
        closable=False,
        composition_digest=composition_digest,
    ).validate()


def _pins_from_json(raw: str) -> tuple[VerificationTrustPins, ReconciliationTrustPins]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FleetRuntimeCompositionError("pins JSON invalid") from exc
    if not isinstance(value, dict):
        raise FleetRuntimeCompositionError("pins JSON must be an object")
    try:
        verification = VerificationTrustPins(**value["verification"]).validate()
        reconciliation = ReconciliationTrustPins(**value["reconciliation"]).validate()
    except (KeyError, TypeError, ValueError) as exc:
        raise FleetRuntimeCompositionError("pins JSON contract mismatch") from exc
    return verification, reconciliation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-master-tree", required=True)
    parser.add_argument("--composition-instance", required=True)
    parser.add_argument("--registry-instance", required=True)
    parser.add_argument("--coordinator-instance", required=True)
    parser.add_argument("--pins-json", required=True)
    args = parser.parse_args(argv)

    verification_pins, reconciliation_pins = _pins_from_json(args.pins_json)
    config = RuntimeCompositionConfig(
        repository=args.repository,
        current_master=args.expected_master,
        current_master_tree=args.expected_master_tree,
        composition_instance_id=args.composition_instance,
        registry_instance_id=args.registry_instance,
        coordinator_instance_id=args.coordinator_instance,
        verification_pins=verification_pins,
        reconciliation_pins=reconciliation_pins,
    ).validate()
    receipt = bootstrap_runtime_composition(config)
    print(json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
