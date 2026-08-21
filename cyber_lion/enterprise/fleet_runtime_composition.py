"""F005-H composition root for the existing durable LION fleet stores.

The composition root only creates or reopens canonical persistence layers. It never
inserts mission, runtime, heartbeat, result, lease, reconciliation, effect, authority,
or closure facts. Existing stores are schema-verified read-only against fresh schema
fingerprints produced by the canonical store constructors before those constructors
are allowed to reopen the target databases.
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


class FailClosedVerificationSource:
    """Bootstrap never invents verification evidence."""

    def resolve(self, verification_id: str):
        raise FleetStatusStateError(
            f"trusted verification source unavailable for {verification_id}"
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FleetRuntimeCompositionError(f"runtime store missing: {path}")
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=5.0)
    except sqlite3.Error as exc:
        raise FleetRuntimeCompositionError(f"cannot open runtime store read-only: {path}") from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _normalize_sql(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FleetRuntimeCompositionError("canonical sqlite schema object has no SQL")
    return " ".join(value.split())


def _quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _schema_fingerprint(path: Path) -> dict[str, Any]:
    """Read the complete user table/column/trigger schema without mutating the store."""
    conn = _ro(path)
    try:
        objects: list[dict[str, Any]] = []
        rows = conn.execute(
            """
            SELECT type,name,tbl_name,sql
            FROM sqlite_master
            WHERE type IN ('table','trigger') AND name NOT LIKE 'sqlite_%'
            ORDER BY type,name
            """
        ).fetchall()
        for row in rows:
            item: dict[str, Any] = {
                "type": str(row["type"]),
                "name": str(row["name"]),
                "table": str(row["tbl_name"]),
                "sql": _normalize_sql(row["sql"]),
            }
            if row["type"] == "table":
                table_name = str(row["name"])
                pragma = f"PRAGMA table_xinfo({_quoted_identifier(table_name)})"
                item["columns"] = [
                    {
                        "cid": int(column[0]),
                        "name": str(column[1]),
                        "type": str(column[2]),
                        "notnull": int(column[3]),
                        "default": column[4],
                        "pk": int(column[5]),
                        "hidden": int(column[6]),
                    }
                    for column in conn.execute(pragma).fetchall()
                ]
            objects.append(item)
        payload = {"objects": objects}
        return {
            "digest": sha256(
                b"LION/F005-H-SQLITE-SCHEMA/1\0" + canonical_json(payload)
            ).hexdigest(),
            "objects": objects,
        }
    finally:
        conn.close()


def _default_physical_paths(config: RuntimeCompositionConfig) -> dict[str, Path]:
    if os.name != "nt":
        raise FleetRuntimeCompositionError(
            "F005-H runtime composition requires Windows lion-runtime"
        )
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
        raise FleetRuntimeCompositionError(
            "test/runtime physical path mapping is incomplete"
        )
    value = {name: Path(path) for name, path in physical_paths.items()}
    if any(not path.is_absolute() for path in value.values()):
        raise FleetRuntimeCompositionError("physical runtime paths must be absolute")
    if any(
        value[name].parent != value["root"]
        for name in ("status", "coordination", "reconciliation")
    ):
        raise FleetRuntimeCompositionError(
            "physical runtime stores must be direct children of runtime root"
        )
    return value


@dataclass
class RuntimeComposition:
    config: RuntimeCompositionConfig
    status: FleetStatusStore
    coordination: FleetCoordinationStore
    reconciliation: ReconciliationStore
    physical_paths: dict[str, Path]

    def close(self) -> None:
        errors: list[Exception] = []
        for store in (self.status, self.coordination, self.reconciliation):
            try:
                store.close()
            except Exception as exc:  # pragma: no cover
                errors.append(exc)
        if errors:
            raise FleetRuntimeCompositionError("runtime store close failed") from errors[0]

    def status_snapshot(self):
        return FleetStatusProjector(self.status).snapshot()

    def build_status_ingestion(
        self,
        *,
        adapters,
        trust_registry,
        reconciler,
        clock: Callable[[], datetime],
    ):
        """Expose the existing canonical ingestion path without performing ingestion."""
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
            status_meta_row = status_reader.execute(
                "SELECT registry_instance_id,revision,event_head,receipt_head "
                "FROM fleet_meta WHERE singleton=1"
            ).fetchone()
            coordination_meta_row = coordination_reader.execute(
                "SELECT coordinator_id,revision,event_head "
                "FROM fleet_coordination_meta WHERE singleton=1"
            ).fetchone()
            if status_meta_row is None or coordination_meta_row is None:
                raise FleetRuntimeCompositionError("canonical runtime binding metadata missing")
            reconciliation_heads = [
                dict(row)
                for row in reconciliation_reader.execute(
                    "SELECT repository,inventory_id,inventory_revision,inventory_digest,"
                    "default_head_sha,observed_at FROM reconciliation_inventory_head "
                    "ORDER BY repository"
                )
            ]
            return {
                "status_meta": dict(status_meta_row),
                "coordination_meta": dict(coordination_meta_row),
                "reconciliation_heads": reconciliation_heads,
                "status_mission_count": int(
                    status_reader.execute("SELECT COUNT(*) FROM fleet_mission").fetchone()[0]
                ),
                "status_runtime_count": int(
                    status_reader.execute("SELECT COUNT(*) FROM fleet_runtime").fetchone()[0]
                ),
                "status_verification_count": int(
                    status_reader.execute("SELECT COUNT(*) FROM fleet_verification").fetchone()[0]
                ),
                "coordination_mission_count": int(
                    coordination_reader.execute(
                        "SELECT COUNT(*) FROM fleet_coordination_mission"
                    ).fetchone()[0]
                ),
                "reconciliation_inventory_count": int(
                    reconciliation_reader.execute(
                        "SELECT COUNT(*) FROM reconciliation_inventory_head"
                    ).fetchone()[0]
                ),
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


def _reference_paths(root: Path) -> dict[str, Path]:
    return {
        "root": root,
        "status": root / "status.sqlite",
        "coordination": root / "coordination.sqlite",
        "reconciliation": root / "reconciliation.sqlite",
    }


def _derive_canonical_schema_fingerprints(
    config: RuntimeCompositionConfig,
    *,
    verification_source,
    clock: Callable[[], datetime],
) -> dict[str, dict[str, Any]]:
    """Derive schema truth from fresh canonical store constructors, never copied DDL."""
    with tempfile.TemporaryDirectory(prefix="f005-h-schema-reference-") as temp:
        paths = _reference_paths(Path(temp))
        reference = _open_canonical_stores(
            config,
            paths,
            verification_source=verification_source,
            clock=clock,
        )
        reference.close()
        return {
            name: _schema_fingerprint(paths[name])
            for name in ("status", "coordination", "reconciliation")
        }


def _validate_existing_schema_before_open(
    paths: dict[str, Path],
    canonical: Mapping[str, dict[str, Any]],
) -> None:
    for name in ("status", "coordination", "reconciliation"):
        actual = _schema_fingerprint(paths[name])
        if actual != canonical[name]:
            raise FleetRuntimeCompositionError(
                f"canonical {name} store schema fingerprint mismatch"
            )


def _validate_existing_instance_bindings_before_open(
    config: RuntimeCompositionConfig,
    paths: dict[str, Path],
) -> None:
    status = _ro(paths["status"])
    coordination = _ro(paths["coordination"])
    try:
        status_meta = status.execute(
            "SELECT registry_instance_id FROM fleet_meta WHERE singleton=1"
        ).fetchone()
        if status_meta is None:
            raise FleetRuntimeCompositionError("status registry binding metadata missing")
        if status_meta["registry_instance_id"] != config.registry_instance_id:
            raise FleetRuntimeCompositionError("status registry instance substitution denied")

        coordination_meta = coordination.execute(
            "SELECT coordinator_id FROM fleet_coordination_meta WHERE singleton=1"
        ).fetchone()
        if coordination_meta is None:
            raise FleetRuntimeCompositionError("coordination binding metadata missing")
        if coordination_meta["coordinator_id"] != config.coordinator_instance_id:
            raise FleetRuntimeCompositionError("coordinator instance substitution denied")
    finally:
        status.close()
        coordination.close()


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
    existing = {
        name: paths[name].is_file()
        for name in ("status", "coordination", "reconciliation")
    }
    if any(existing.values()) and not all(existing.values()):
        raise FleetRuntimeCompositionError("partial runtime store bootstrap denied")

    source = (
        verification_source
        if verification_source is not None
        else FailClosedVerificationSource()
    )
    canonical_schema = _derive_canonical_schema_fingerprints(
        config,
        verification_source=source,
        clock=clock,
    )

    if not any(existing.values()):
        _create_new_store_set(
            config,
            paths,
            verification_source=source,
            clock=clock,
        )

    # Critical ordering: all target validation is read-only and occurs before a
    # canonical constructor can execute CREATE ... IF NOT EXISTS against the target.
    _validate_existing_schema_before_open(paths, canonical_schema)
    _validate_existing_instance_bindings_before_open(config, paths)

    return _open_canonical_stores(
        config,
        paths,
        verification_source=source,
        clock=clock,
    )


def bootstrap_runtime_composition(
    config: RuntimeCompositionConfig,
    *,
    verification_source=None,
    clock: Callable[[], datetime] = _utc_now,
    physical_paths: Mapping[str, Path] | None = None,
) -> RuntimeCompositionReceipt:
    """Create/reopen canonical stores, prove preservation, and never assert closure."""
    first = open_runtime_composition(
        config,
        verification_source=verification_source,
        clock=clock,
        physical_paths=physical_paths,
    )
    try:
        before = first.semantic_fingerprint()
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
        raise FleetRuntimeCompositionError(
            "canonical store reopen changed durable semantic state"
        )

    empty = (
        after["status_mission_count"] == 0
        and after["coordination_mission_count"] == 0
        and after["reconciliation_inventory_count"] == 0
    )
    classification = (
        "EMPTY_NOT_CLOSABLE"
        if empty
        else "STATE_PRESENT_REQUIRES_RUNTIME_CONVERGENCE"
    )
    composition_digest = config.digest()
    composition_id = sha256(
        b"LION/F005-H-BOOTSTRAP/1\0"
        + canonical_json(
            {
                "composition_digest": composition_digest,
                "fingerprint": after,
                "classification": classification,
            }
        )
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


def _pins_from_json(
    raw: str,
) -> tuple[VerificationTrustPins, ReconciliationTrustPins]:
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