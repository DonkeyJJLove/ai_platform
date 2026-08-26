"""Atomic externally provisioned maintenance bundle for repository effects.

The bundle is organizational/policy evidence only. It never grants authority and exposes
no repository effect capability. Administrative provisioning is local-store only; the
network service built on top of this module is read-only.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.contracts.policy_gate import PolicyRevision
from cyber_lion.enterprise.models import MissionSpec
from cyber_lion.enterprise.trusted_control_plane_providers import SQLiteTrustedControlPlaneStore
from cyber_lion.enterprise.trusted_control_plane_service import (
    TrustedControlPlaneServiceError,
    validate_maintenance_mission_record,
    validate_maintenance_policy_record,
)

BUNDLE_VERSION = "1.0.0"
CAPABILITY_REPOSITORY_REF_DELETE = "repository_ref.delete"
_SOURCE_DOMAIN = b"LION/E006-R9D8U-MAINTENANCE-BUNDLE-SOURCE/1\0"
_BINDING_DOMAIN = b"LION/E006-R9D8U-MAINTENANCE-BINDING/1\0"
_RECORD_DOMAIN = b"LION/E006-R9D8U-MAINTENANCE-RECORD/1\0"
_TRANSACTION_DOMAIN = b"LION/E006-R9D8U-MAINTENANCE-TRANSACTION/1\0"
_RECEIPT_DOMAIN = b"LION/E006-R9D8U-MAINTENANCE-ADMIN-RECEIPT/1\0"
_BUNDLE_DOMAIN = b"LION/E006-R9D8U-MAINTENANCE-BUNDLE/1\0"


class MaintenanceBundleError(RuntimeError):
    pass


def _text(value: object, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise MaintenanceBundleError(f"{name} is invalid")
    return value


def _hex64(value: object, name: str) -> str:
    value = _text(value, name, limit=64)
    if len(value) != 64 or value.lower() != value:
        raise MaintenanceBundleError(f"{name} is invalid")
    try:
        int(value, 16)
    except ValueError as exc:
        raise MaintenanceBundleError(f"{name} is invalid") from exc
    return value


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MaintenanceBundleError("value is not canonical JSON") from exc


def _digest(domain: bytes, value: object) -> str:
    return sha256(domain + _canonical(value)).hexdigest()


def _record_digest(record: Mapping[str, object]) -> str:
    if not isinstance(record, Mapping):
        raise MaintenanceBundleError("maintenance record must be a mapping")
    return _digest(_RECORD_DOMAIN, dict(record))


def source_attestation(database_identity: str) -> tuple[str, str]:
    database_identity = _hex64(database_identity, "database_identity")
    dg = sha256(_SOURCE_DOMAIN + database_identity.encode("ascii")).hexdigest()
    return f"maintenance-bundle:{dg}", dg


@dataclass(frozen=True)
class MaintenanceBinding:
    repository: str
    capability: str
    mission_id: str
    policy_id: str

    def validate(self) -> "MaintenanceBinding":
        for name in ("repository", "capability", "mission_id", "policy_id"):
            _text(getattr(self, name), name)
        if self.capability != CAPABILITY_REPOSITORY_REF_DELETE:
            raise MaintenanceBundleError("unsupported maintenance capability")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(_BINDING_DOMAIN, asdict(self))


@dataclass(frozen=True)
class MaintenanceAdministrativeReceipt:
    schema_version: str
    administrator_id: str
    operation_id: str
    source_system_id: str
    database_identity: str
    source_origin_id: str
    source_origin_digest: str
    binding_digest: str
    policy_record_digest: str
    mission_record_digest: str
    provisioned_at: str
    transaction_digest: str
    receipt_digest: str = ""

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("receipt_digest")
        return value

    def compute_transaction_digest(self) -> str:
        payload = self.canonical_payload()
        payload.pop("transaction_digest")
        return _digest(_TRANSACTION_DOMAIN, payload)

    def compute_receipt_digest(self) -> str:
        return _digest(_RECEIPT_DOMAIN, self.canonical_payload())

    def validate(self) -> "MaintenanceAdministrativeReceipt":
        if self.schema_version != BUNDLE_VERSION:
            raise MaintenanceBundleError("administrative receipt schema mismatch")
        for name in (
            "administrator_id",
            "operation_id",
            "source_system_id",
            "source_origin_id",
            "provisioned_at",
        ):
            _text(getattr(self, name), name)
        for name in (
            "database_identity",
            "source_origin_digest",
            "binding_digest",
            "policy_record_digest",
            "mission_record_digest",
            "transaction_digest",
        ):
            _hex64(getattr(self, name), name)
        expected_origin_id, expected_origin_digest = source_attestation(self.database_identity)
        if self.source_origin_id != expected_origin_id or self.source_origin_digest != expected_origin_digest:
            raise MaintenanceBundleError("administrative receipt source attestation mismatch")
        if self.transaction_digest != self.compute_transaction_digest():
            raise MaintenanceBundleError("administrative transaction digest mismatch")
        if self.receipt_digest:
            _hex64(self.receipt_digest, "receipt_digest")
            if self.receipt_digest != self.compute_receipt_digest():
                raise MaintenanceBundleError("administrative receipt digest mismatch")
        return self

    def sealed(self) -> "MaintenanceAdministrativeReceipt":
        self.validate()
        return MaintenanceAdministrativeReceipt(
            **{**asdict(self), "receipt_digest": self.compute_receipt_digest()}
        ).validate()


@dataclass(frozen=True)
class MaintenanceBundle:
    provider_version: str
    database_identity: str
    source_origin_id: str
    source_origin_digest: str
    binding: MaintenanceBinding
    maintenance_policy_record: Mapping[str, object]
    maintenance_mission_record: Mapping[str, object]
    administrative_receipt: MaintenanceAdministrativeReceipt
    bundle_digest: str = ""

    def canonical_payload(self) -> dict[str, object]:
        return {
            "provider_version": self.provider_version,
            "database_identity": self.database_identity,
            "source_origin_id": self.source_origin_id,
            "source_origin_digest": self.source_origin_digest,
            "binding": asdict(self.binding),
            "maintenance_policy_record": dict(self.maintenance_policy_record),
            "maintenance_mission_record": dict(self.maintenance_mission_record),
            "administrative_receipt": asdict(self.administrative_receipt),
        }

    def compute_digest(self) -> str:
        return _digest(_BUNDLE_DOMAIN, self.canonical_payload())

    def validate(self) -> "MaintenanceBundle":
        if self.provider_version != BUNDLE_VERSION:
            raise MaintenanceBundleError("maintenance bundle provider version mismatch")
        self.binding.validate()
        _hex64(self.database_identity, "database_identity")
        _hex64(self.source_origin_digest, "source_origin_digest")
        _text(self.source_origin_id, "source_origin_id")
        expected_origin_id, expected_origin_digest = source_attestation(self.database_identity)
        if self.source_origin_id != expected_origin_id or self.source_origin_digest != expected_origin_digest:
            raise MaintenanceBundleError("maintenance bundle source attestation mismatch")
        receipt = self.administrative_receipt.validate()
        if (
            receipt.database_identity != self.database_identity
            or receipt.source_origin_id != self.source_origin_id
            or receipt.source_origin_digest != self.source_origin_digest
            or receipt.binding_digest != self.binding.digest()
        ):
            raise MaintenanceBundleError("maintenance bundle receipt binding mismatch")
        policy_binding = {
            "repository": self.binding.repository,
            "mission_id": self.binding.mission_id,
            "policy_id": self.binding.policy_id,
        }
        mission_binding = {
            "repository": self.binding.repository,
            "mission_id": self.binding.mission_id,
        }
        try:
            policy_record = validate_maintenance_policy_record(
                self.maintenance_policy_record, expected_binding=policy_binding
            )
            mission_record = validate_maintenance_mission_record(
                self.maintenance_mission_record, expected_binding=mission_binding
            )
        except TrustedControlPlaneServiceError as exc:
            raise MaintenanceBundleError("maintenance bundle record validation failed") from exc
        if _record_digest(policy_record) != receipt.policy_record_digest:
            raise MaintenanceBundleError("maintenance policy record digest mismatch")
        if _record_digest(mission_record) != receipt.mission_record_digest:
            raise MaintenanceBundleError("maintenance mission record digest mismatch")
        mission_payload = dict(mission_record["mission_payload"])
        caps = mission_payload.get("required_capabilities")
        if type(caps) is not list or self.binding.capability not in caps:
            raise MaintenanceBundleError("maintenance bundle capability not required by mission")
        if self.bundle_digest:
            _hex64(self.bundle_digest, "bundle_digest")
            if self.bundle_digest != self.compute_digest():
                raise MaintenanceBundleError("maintenance bundle digest mismatch")
        return self

    def sealed(self) -> "MaintenanceBundle":
        self.validate()
        return MaintenanceBundle(
            provider_version=self.provider_version,
            database_identity=self.database_identity,
            source_origin_id=self.source_origin_id,
            source_origin_digest=self.source_origin_digest,
            binding=self.binding,
            maintenance_policy_record=dict(self.maintenance_policy_record),
            maintenance_mission_record=dict(self.maintenance_mission_record),
            administrative_receipt=self.administrative_receipt,
            bundle_digest=self.compute_digest(),
        ).validate()

    def policy(self) -> PolicyRevision:
        self.validate()
        return PolicyRevision(**dict(self.maintenance_policy_record["policy_payload"])).validate()

    def mission(self) -> MissionSpec:
        self.validate()
        raw = dict(self.maintenance_mission_record["mission_payload"])
        raw["required_capabilities"] = tuple(raw["required_capabilities"])
        return MissionSpec(**raw).validate()

    def to_wire(self) -> dict[str, object]:
        self.validate()
        value = self.canonical_payload()
        value["bundle_digest"] = self.bundle_digest
        return value


def decode_maintenance_bundle(value: Mapping[str, object]) -> MaintenanceBundle:
    fields = {
        "provider_version",
        "database_identity",
        "source_origin_id",
        "source_origin_digest",
        "binding",
        "maintenance_policy_record",
        "maintenance_mission_record",
        "administrative_receipt",
        "bundle_digest",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise MaintenanceBundleError("maintenance bundle wire shape invalid")
    binding_raw = value["binding"]
    receipt_raw = value["administrative_receipt"]
    if not isinstance(binding_raw, Mapping) or set(binding_raw) != {"repository", "capability", "mission_id", "policy_id"}:
        raise MaintenanceBundleError("maintenance bundle binding wire shape invalid")
    receipt_fields = {
        "schema_version",
        "administrator_id",
        "operation_id",
        "source_system_id",
        "database_identity",
        "source_origin_id",
        "source_origin_digest",
        "binding_digest",
        "policy_record_digest",
        "mission_record_digest",
        "provisioned_at",
        "transaction_digest",
        "receipt_digest",
    }
    if not isinstance(receipt_raw, Mapping) or set(receipt_raw) != receipt_fields:
        raise MaintenanceBundleError("maintenance receipt wire shape invalid")
    bundle = MaintenanceBundle(
        provider_version=value["provider_version"],
        database_identity=value["database_identity"],
        source_origin_id=value["source_origin_id"],
        source_origin_digest=value["source_origin_digest"],
        binding=MaintenanceBinding(**dict(binding_raw)).validate(),
        maintenance_policy_record=dict(value["maintenance_policy_record"]),
        maintenance_mission_record=dict(value["maintenance_mission_record"]),
        administrative_receipt=MaintenanceAdministrativeReceipt(**dict(receipt_raw)).validate(),
        bundle_digest=value["bundle_digest"],
    )
    return bundle.validate()


class SQLiteMaintenanceBundleRepository:
    """Atomic append-only maintenance bundle registry over the external control-plane DB."""

    def __init__(self, store: SQLiteTrustedControlPlaneStore, *, initialize_schema: bool = False) -> None:
        if type(store) is not SQLiteTrustedControlPlaneStore or store.ready() is not True:
            raise MaintenanceBundleError("exact trusted control-plane store required")
        raw_path = getattr(store, "_path", None)
        if not isinstance(raw_path, str) or not raw_path:
            raise MaintenanceBundleError("trusted control-plane database path unavailable")
        self._store = store
        self._path = str(Path(raw_path))
        self.database_identity = store.database_identity()
        self.source_origin_id, self.source_origin_digest = source_attestation(self.database_identity)
        if initialize_schema:
            self._initialize_schema()

    def _connect(self, *, read_only: bool = False) -> sqlite3.Connection:
        if read_only:
            uri = Path(self._path).resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
        else:
            connection = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS maintenance_binding(
                    repository TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    transaction_digest TEXT NOT NULL,
                    binding_digest TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK(active IN (0,1)),
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(repository,capability,mission_id,policy_id,transaction_digest,record_json)
                );
                CREATE TABLE IF NOT EXISTS maintenance_admin_receipt(
                    transaction_digest TEXT NOT NULL,
                    receipt_digest TEXT NOT NULL UNIQUE,
                    receipt_json TEXT NOT NULL,
                    PRIMARY KEY(transaction_digest,receipt_digest)
                );
                CREATE TRIGGER IF NOT EXISTS maintenance_binding_no_update
                  BEFORE UPDATE ON maintenance_binding BEGIN SELECT RAISE(ABORT,'maintenance binding append-only'); END;
                CREATE TRIGGER IF NOT EXISTS maintenance_binding_no_delete
                  BEFORE DELETE ON maintenance_binding BEGIN SELECT RAISE(ABORT,'maintenance binding append-only'); END;
                CREATE TRIGGER IF NOT EXISTS maintenance_admin_receipt_no_update
                  BEFORE UPDATE ON maintenance_admin_receipt BEGIN SELECT RAISE(ABORT,'maintenance receipt append-only'); END;
                CREATE TRIGGER IF NOT EXISTS maintenance_admin_receipt_no_delete
                  BEFORE DELETE ON maintenance_admin_receipt BEGIN SELECT RAISE(ABORT,'maintenance receipt append-only'); END;
                """
            )

    @staticmethod
    def _strict_json(value: object) -> str:
        return _canonical(value).decode("utf-8")

    def provision(
        self,
        *,
        binding: MaintenanceBinding,
        maintenance_policy_record: Mapping[str, object],
        maintenance_mission_record: Mapping[str, object],
        administrator_id: str,
        operation_id: str,
        source_system_id: str,
        provisioned_at: str,
    ) -> MaintenanceBundle:
        self._initialize_schema()
        binding.validate()
        policy_binding = {
            "repository": binding.repository,
            "mission_id": binding.mission_id,
            "policy_id": binding.policy_id,
        }
        mission_binding = {"repository": binding.repository, "mission_id": binding.mission_id}
        try:
            policy_record = dict(validate_maintenance_policy_record(maintenance_policy_record, expected_binding=policy_binding))
            mission_record = dict(validate_maintenance_mission_record(maintenance_mission_record, expected_binding=mission_binding))
        except TrustedControlPlaneServiceError as exc:
            raise MaintenanceBundleError("administrative bundle record invalid") from exc
        policy = PolicyRevision(**dict(policy_record["policy_payload"])).validate()
        mission_raw = dict(mission_record["mission_payload"])
        mission_raw["required_capabilities"] = tuple(mission_raw["required_capabilities"])
        mission = MissionSpec(**mission_raw).validate()
        if policy.policy_id != binding.policy_id or mission.mission_id != binding.mission_id:
            raise MaintenanceBundleError("administrative bundle identity mismatch")
        if binding.capability not in mission.required_capabilities:
            raise MaintenanceBundleError("administrative bundle capability mismatch")
        if not policy.active:
            raise MaintenanceBundleError("administrative bundle policy must be active")
        _text(administrator_id, "administrator_id")
        _text(operation_id, "operation_id")
        _text(source_system_id, "source_system_id")
        _text(provisioned_at, "provisioned_at")
        binding_digest = binding.digest()
        policy_dg = _record_digest(policy_record)
        mission_dg = _record_digest(mission_record)
        provisional_receipt = MaintenanceAdministrativeReceipt(
            schema_version=BUNDLE_VERSION,
            administrator_id=administrator_id,
            operation_id=operation_id,
            source_system_id=source_system_id,
            database_identity=self.database_identity,
            source_origin_id=self.source_origin_id,
            source_origin_digest=self.source_origin_digest,
            binding_digest=binding_digest,
            policy_record_digest=policy_dg,
            mission_record_digest=mission_dg,
            provisioned_at=provisioned_at,
            transaction_digest="0" * 64,
            receipt_digest="",
        )
        transaction_digest = provisional_receipt.compute_transaction_digest()
        receipt = MaintenanceAdministrativeReceipt(
            **{**asdict(provisional_receipt), "transaction_digest": transaction_digest}
        ).sealed()
        binding_record = {
            "repository": binding.repository,
            "capability": binding.capability,
            "mission_id": binding.mission_id,
            "policy_id": binding.policy_id,
            "transaction_digest": transaction_digest,
            "binding_digest": binding_digest,
            "active": True,
        }
        policy_raw = self._strict_json(policy_record)
        mission_raw_json = self._strict_json(mission_record)
        binding_raw = self._strict_json(binding_record)
        receipt_raw = self._strict_json(asdict(receipt))
        with self._connect() as connection:
            try:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT COUNT(*) FROM maintenance_binding WHERE repository=? AND capability=? AND active=1",
                    (binding.repository, binding.capability),
                ).fetchone()[0] != 0:
                    raise MaintenanceBundleError("current maintenance binding already exists")
                if connection.execute(
                    "SELECT COUNT(*) FROM maintenance_policy WHERE repository=? AND mission_id=? AND policy_id=? AND active=1",
                    (binding.repository, binding.mission_id, binding.policy_id),
                ).fetchone()[0] != 0:
                    raise MaintenanceBundleError("current maintenance policy already exists")
                if connection.execute(
                    "SELECT COUNT(*) FROM maintenance_mission WHERE repository=? AND mission_id=?",
                    (binding.repository, binding.mission_id),
                ).fetchone()[0] != 0:
                    raise MaintenanceBundleError("current maintenance mission already exists")
                connection.execute(
                    "INSERT INTO maintenance_policy(repository,mission_id,policy_id,revision,active,record_json) VALUES(?,?,?,?,?,?)",
                    (binding.repository, binding.mission_id, binding.policy_id, policy.revision, 1, policy_raw),
                )
                connection.execute(
                    "INSERT INTO maintenance_mission(repository,mission_id,record_json) VALUES(?,?,?)",
                    (binding.repository, binding.mission_id, mission_raw_json),
                )
                connection.execute(
                    "INSERT INTO maintenance_binding(repository,capability,mission_id,policy_id,transaction_digest,binding_digest,active,record_json) VALUES(?,?,?,?,?,?,1,?)",
                    (binding.repository, binding.capability, binding.mission_id, binding.policy_id, transaction_digest, binding_digest, binding_raw),
                )
                connection.execute(
                    "INSERT INTO maintenance_admin_receipt(transaction_digest,receipt_digest,receipt_json) VALUES(?,?,?)",
                    (transaction_digest, receipt.receipt_digest, receipt_raw),
                )
                counts = (
                    connection.execute(
                        "SELECT COUNT(*) FROM maintenance_binding WHERE repository=? AND capability=? AND active=1",
                        (binding.repository, binding.capability),
                    ).fetchone()[0],
                    connection.execute(
                        "SELECT COUNT(*) FROM maintenance_policy WHERE repository=? AND mission_id=? AND policy_id=? AND active=1",
                        (binding.repository, binding.mission_id, binding.policy_id),
                    ).fetchone()[0],
                    connection.execute(
                        "SELECT COUNT(*) FROM maintenance_mission WHERE repository=? AND mission_id=?",
                        (binding.repository, binding.mission_id),
                    ).fetchone()[0],
                    connection.execute(
                        "SELECT COUNT(*) FROM maintenance_admin_receipt WHERE transaction_digest=?",
                        (transaction_digest,),
                    ).fetchone()[0],
                )
                if counts != (1, 1, 1, 1):
                    raise MaintenanceBundleError("atomic maintenance provisioning cardinality mismatch")
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        bundle = self.resolve_exact(repository=binding.repository, capability=binding.capability)
        if bundle.administrative_receipt.transaction_digest != transaction_digest:
            raise MaintenanceBundleError("administrative provisioning readback mismatch")
        return bundle

    def resolve_exact(self, *, repository: str, capability: str) -> MaintenanceBundle:
        _text(repository, "repository")
        _text(capability, "capability")
        with self._connect(read_only=True) as connection:
            bindings = connection.execute(
                "SELECT mission_id,policy_id,transaction_digest,binding_digest,record_json FROM maintenance_binding WHERE repository=? AND capability=? AND active=1 ORDER BY record_json",
                (repository, capability),
            ).fetchall()
            if len(bindings) != 1:
                raise MaintenanceBundleError("maintenance binding missing or ambiguous")
            row = bindings[0]
            try:
                binding_record = json.loads(row["record_json"])
            except json.JSONDecodeError as exc:
                raise MaintenanceBundleError("maintenance binding record corrupt") from exc
            binding = MaintenanceBinding(
                repository=repository,
                capability=capability,
                mission_id=row["mission_id"],
                policy_id=row["policy_id"],
            ).validate()
            expected_binding_record = {
                "repository": binding.repository,
                "capability": binding.capability,
                "mission_id": binding.mission_id,
                "policy_id": binding.policy_id,
                "transaction_digest": row["transaction_digest"],
                "binding_digest": row["binding_digest"],
                "active": True,
            }
            if binding_record != expected_binding_record or row["binding_digest"] != binding.digest():
                raise MaintenanceBundleError("maintenance binding record mismatch")
            policy_rows = connection.execute(
                "SELECT record_json FROM maintenance_policy WHERE repository=? AND mission_id=? AND policy_id=? AND active=1 ORDER BY revision,record_json",
                (repository, binding.mission_id, binding.policy_id),
            ).fetchall()
            mission_rows = connection.execute(
                "SELECT record_json FROM maintenance_mission WHERE repository=? AND mission_id=? ORDER BY record_json",
                (repository, binding.mission_id),
            ).fetchall()
            receipt_rows = connection.execute(
                "SELECT receipt_json FROM maintenance_admin_receipt WHERE transaction_digest=? ORDER BY receipt_json",
                (row["transaction_digest"],),
            ).fetchall()
        if len(policy_rows) != 1 or len(mission_rows) != 1 or len(receipt_rows) != 1:
            raise MaintenanceBundleError("maintenance bundle component missing or ambiguous")
        try:
            policy_record = json.loads(policy_rows[0]["record_json"])
            mission_record = json.loads(mission_rows[0]["record_json"])
            receipt = MaintenanceAdministrativeReceipt(**json.loads(receipt_rows[0]["receipt_json"])).validate()
        except (json.JSONDecodeError, TypeError) as exc:
            raise MaintenanceBundleError("maintenance bundle component corrupt") from exc
        bundle = MaintenanceBundle(
            provider_version=BUNDLE_VERSION,
            database_identity=self.database_identity,
            source_origin_id=self.source_origin_id,
            source_origin_digest=self.source_origin_digest,
            binding=binding,
            maintenance_policy_record=policy_record,
            maintenance_mission_record=mission_record,
            administrative_receipt=receipt,
        ).sealed()
        return bundle


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpMaintenanceBundleSource:
    """Capability-reduced read-only client for exactly one trusted bundle lookup."""

    def __init__(self, *, base_url: str, credential: str) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
            raise MaintenanceBundleError("maintenance bundle service URL invalid")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise MaintenanceBundleError("plaintext maintenance bundle service must be loopback")
        _text(credential, "maintenance bundle credential", limit=16384)
        self.base_url = base_url.rstrip("/")
        self.credential = credential

    def resolve_exact(self, *, repository: str, capability: str) -> MaintenanceBundle:
        query = urllib.parse.urlencode({"repository": repository, "capability": capability})
        url = f"{self.base_url}/v1/maintenance-bundle?{query}"
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.credential}",
                "Accept": "application/json",
                "User-Agent": "lion-maintenance-bundle-client/1",
            },
        )
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=15) as response:
                raw = response.read()
                if response.status != 200:
                    raise MaintenanceBundleError("trusted maintenance bundle service rejected lookup")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            raise MaintenanceBundleError("trusted maintenance bundle service unavailable") from exc
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MaintenanceBundleError("trusted maintenance bundle response invalid") from exc
        if not isinstance(value, Mapping):
            raise MaintenanceBundleError("trusted maintenance bundle response invalid")
        bundle = decode_maintenance_bundle(value)
        if bundle.binding.repository != repository or bundle.binding.capability != capability:
            raise MaintenanceBundleError("trusted maintenance bundle lookup substitution denied")
        return bundle
