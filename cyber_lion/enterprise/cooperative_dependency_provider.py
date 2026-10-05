"""Concrete read-only dependency provider for the cooperative worker bootstrap.

The module composes existing authority/runtime contracts from external, read-only evidence.
It does not issue authority, RuntimeAdmission, provisioning, dispatch or currentness. Those
objects must already exist in the mounted provider/control-plane evidence surfaces.

The corresponding external provider shim is copied outside /src and SHA-256 pinned by the
R24 materializer. Missing/stale/ambiguous evidence fails closed.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import fields
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Any, Mapping

from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.authority_source_adapter import AuthoritySourceTransport, TrustedControlPlaneAuthoritySource
from cyber_lion.enterprise.authority_verification import AuthorityVerificationContext, IssuerKeyBinding
from cyber_lion.enterprise.cooperative_context_resolver import PinnedCooperativeContextResolver
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteContextPinSource,
    SQLiteEffectTimeCurrentnessSource,
    SQLiteEvidenceRuntimeAdmissionSource,
    SQLiteFleetDispatchSource,
    SQLiteProvisioningBindingSource,
    SQLiteRuntimeIdentitySource,
    SQLiteTransferBindingSource,
)
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.persistent_authority_state import (
    DurableReplayGuard,
    PersistentBindingFinalizer,
    PersistentEpochSnapshot,
    PersistentRootAnchor,
    SQLiteAuthorityStateStore,
)
from cyber_lion.enterprise.trusted_control_plane_providers import TrustedSignatureVerifierAdapter
from cyber_lion.mission_control.cooperative_worker_bootstrap import CooperativeRuntimeBootstrapDependencies

CONFIG_SCHEMA = "lion.cooperative-dependency-provider/v1"
PROVIDER_FACTORY_VERSION = "1.0.0"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_CALLABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


class CooperativeDependencyProviderError(RuntimeError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeDependencyProviderError(reason)


def _required(name: str, *, limit: int = 4096) -> str:
    value = os.environ.get(name)
    _require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit and "\x00" not in value,
             "provider configuration:" + name)
    return value


def _direct_file(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_file() and not path.is_symlink(), label)
    resolved = path.resolve(strict=True)
    _require(path == resolved, label + " symlink indirection")
    st = resolved.stat()
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, label + " private regular file")
    return resolved


def _direct_dir(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_dir() and not path.is_symlink(), label)
    resolved = path.resolve(strict=True)
    _require(path == resolved, label + " symlink indirection")
    return resolved


def _outside_repository(path: Path, repository_root: Path, label: str) -> Path:
    _require(path != repository_root and repository_root not in path.parents, label + " must be outside repository")
    return path


def _repository_root() -> Path:
    return _direct_dir(_required("LION_COOPERATIVE_REPOSITORY_ROOT"), "cooperative repository root")


def _identity(path: Path) -> tuple[int, int]:
    st = path.stat()
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "external DB private regular file")
    return st.st_dev, st.st_ino


def _strict_json(path: Path, expected: set[str], label: str) -> dict[str, Any]:
    def unique(pairs):
        out = {}
        for key, value in pairs:
            _require(key not in out, label + " duplicate JSON key")
            out[key] = value
        return out
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(CooperativeDependencyProviderError(label + " nonfinite JSON")),
        )
    except CooperativeDependencyProviderError:
        raise
    except Exception as exc:
        raise CooperativeDependencyProviderError(label + " JSON invalid") from exc
    _require(type(value) is dict and set(value) == expected, label + " fields")
    return value


def _contract(cls, value: Mapping[str, Any], label: str):
    _require(type(value) is dict and set(value) == {f.name for f in fields(cls)}, label + " fields")
    data = dict(value)
    for f in fields(cls):
        if str(f.type).startswith("tuple["):
            _require(type(data[f.name]) is list, label + ":" + f.name + " array")
            data[f.name] = tuple(data[f.name])
    try:
        return cls(**data).validate()
    except Exception as exc:
        raise CooperativeDependencyProviderError(label + " invalid") from exc


class _ReadOnlySQLite:
    def __init__(self, path: str | Path):
        self.path = _direct_file(path, "external SQLite evidence")
        self._identity = _identity(self.path)

    def connect(self):
        _require(not self.path.is_symlink() and _identity(self.path) == self._identity, "external SQLite identity drift")
        db = sqlite3.connect("file:" + self.path.as_posix() + "?mode=ro", uri=True, timeout=5)
        db.execute("PRAGMA query_only=ON")
        return db


class ReadOnlyAuthorityControlPlaneTransport(AuthoritySourceTransport):
    """Capability-reduced exact authority lookup over the existing control-plane schema."""

    def __init__(self, path: str | Path):
        self._db = _ReadOnlySQLite(path)

    def lookup_exact(self, *, repository, pr_number, base_sha, head_sha, mission_id, grant_id):
        try:
            with closing(self._db.connect()) as db:
                rows = db.execute(
                    "SELECT record_json FROM authority_lineage WHERE repository=? AND pr_number=? "
                    "AND base_sha=? AND head_sha=? AND mission_id=? AND grant_id=? ORDER BY record_json",
                    (repository, pr_number, base_sha, head_sha, mission_id, grant_id),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeDependencyProviderError("authority control plane unavailable") from exc
        out = []
        for (raw,) in rows:
            try:
                value = json.loads(raw)
            except Exception as exc:
                raise CooperativeDependencyProviderError("authority record corrupt") from exc
            _require(type(value) is dict, "authority record type")
            out.append(value)
        return tuple(out)


class ReadOnlyEpochProvider:
    def __init__(self, path: str | Path):
        self._db = _ReadOnlySQLite(path)

    def current(self, context):
        _require(type(context) is tuple and len(context) == 4, "authority context")
        try:
            with closing(self._db.connect()) as db:
                rows = db.execute(
                    "SELECT epoch,revoked_json,version FROM authority_epoch_state "
                    "WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",
                    context,
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeDependencyProviderError("authority epoch unavailable") from exc
        _require(len(rows) == 1, "authority epoch unavailable or ambiguous")
        epoch, revoked_raw, version = rows[0]
        try:
            revoked = json.loads(revoked_raw)
        except Exception as exc:
            raise CooperativeDependencyProviderError("revocation state corrupt") from exc
        _require(type(revoked) is list and all(type(x) is str and x for x in revoked), "revocation state invalid")
        return PersistentEpochSnapshot(*context, int(epoch), tuple(revoked), int(version))


class ReadOnlyRootProvider:
    def __init__(self, path: str | Path):
        self._db = _ReadOnlySQLite(path)

    def resolve(self, context, epoch):
        _require(type(context) is tuple and len(context) == 4 and type(epoch) is int, "root authority context")
        try:
            with closing(self._db.connect()) as db:
                rows = db.execute(
                    "SELECT root_grant_id,root_grant_digest FROM authority_root_anchor "
                    "WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=? AND epoch=?",
                    (*context, epoch),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CooperativeDependencyProviderError("authority root unavailable") from exc
        _require(len(rows) == 1, "authority root unavailable or ambiguous")
        return PersistentRootAnchor(*context, epoch, rows[0][0], rows[0][1])


def _load_verifier():
    path = _outside_repository(
        _direct_file(_required("LION_COOPERATIVE_VERIFIER_MODULE_PATH"), "cooperative verifier module"),
        _repository_root(),
        "cooperative verifier module",
    )
    expected = _required("LION_COOPERATIVE_VERIFIER_MODULE_SHA256", limit=64)
    _require(_SHA.fullmatch(expected) is not None and sha256(path.read_bytes()).hexdigest() == expected,
             "cooperative verifier module digest mismatch")
    name = _required("LION_COOPERATIVE_VERIFIER_CALLABLE", limit=128)
    _require(_CALLABLE.fullmatch(name) is not None, "cooperative verifier callable")
    ready_name = os.environ.get("LION_COOPERATIVE_VERIFIER_READY_CALLABLE")
    if ready_name is not None:
        _require(_CALLABLE.fullmatch(ready_name) is not None, "cooperative verifier ready callable")
    try:
        spec = importlib.util.spec_from_file_location("_lion_cooperative_verifier_" + expected[:20], path)
        _require(spec is not None and spec.loader is not None, "cooperative verifier module unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        verifier = getattr(module, name, None)
        ready = getattr(module, ready_name, None) if ready_name else None
        adapter = TrustedSignatureVerifierAdapter(verifier, ready=ready)
    except CooperativeDependencyProviderError:
        raise
    except Exception as exc:
        raise CooperativeDependencyProviderError("cooperative verifier failed closed") from exc
    _require(adapter.ready() is True, "cooperative verifier not ready")
    return adapter.verify


def _config():
    path = _outside_repository(
        _direct_file(_required("LION_COOPERATIVE_PROVIDER_CONFIG_PATH"), "cooperative provider config"),
        _repository_root(),
        "cooperative provider config",
    )
    value = _strict_json(
        path,
        {
            "schema", "factory_version", "authority_context", "issuer_keys",
            "upstream_admission_trust", "durable_admission_trust", "currentness_trust",
        },
        "cooperative provider config",
    )
    _require(value["schema"] == CONFIG_SCHEMA and value["factory_version"] == PROVIDER_FACTORY_VERSION,
             "cooperative provider config version")
    context = _contract(AuthorityVerificationContext, value["authority_context"], "authority context")
    _require(type(value["issuer_keys"]) is list and bool(value["issuer_keys"]), "issuer keys")
    keys = tuple(_contract(IssuerKeyBinding, item, "issuer key") for item in value["issuer_keys"])
    upstream = _contract(RuntimeAdmissionSourceTrustBinding, value["upstream_admission_trust"], "upstream admission trust")
    durable = _contract(RuntimeAdmissionSourceTrustBinding, value["durable_admission_trust"], "durable admission trust")
    current = _contract(CurrentnessSourceTrustBinding, value["currentness_trust"], "currentness trust")
    return context, keys, upstream, durable, current


def build_dependencies_from_environment() -> CooperativeRuntimeBootstrapDependencies:
    """Build exact worker dependencies from mounted read-only evidence.

    This function only assembles sources. It never publishes evidence or invokes a PDP.
    """
    if _required("LION_COOPERATIVE_PROVIDER_FACTORY_VERSION", limit=64) != PROVIDER_FACTORY_VERSION:
        raise CooperativeDependencyProviderError("cooperative provider factory version mismatch")

    repository_root = _repository_root()
    mission_db = _outside_repository(
        _direct_file(_required("LION_COOPERATIVE_MISSION_DB_PATH"), "Mission Control DB"),
        repository_root, "Mission Control DB",
    )
    evidence_db = _outside_repository(
        _direct_file(_required("LION_COOPERATIVE_PROVIDER_DB_PATH"), "runtime evidence DB"),
        repository_root, "runtime evidence DB",
    )
    context_root = _outside_repository(
        _direct_dir(_required("LION_COOPERATIVE_CONTEXT_CARRIER_ROOT"), "context carrier root"),
        repository_root, "context carrier root",
    )
    control_db = _outside_repository(
        _direct_file(_required("LION_COOPERATIVE_CONTROL_PLANE_DB_PATH"), "authority control-plane DB"),
        repository_root, "authority control-plane DB",
    )
    authority_state_db = _outside_repository(
        _direct_file(_required("LION_COOPERATIVE_AUTHORITY_STATE_DB_PATH"), "authority state DB"),
        repository_root, "authority state DB",
    )
    local_authority_state = Path(_required("LION_COOPERATIVE_LOCAL_AUTHORITY_STATE_PATH"))
    _require(local_authority_state.is_absolute() and local_authority_state.parent.resolve(strict=True).is_dir(),
             "local authority state path")
    _outside_repository(local_authority_state, repository_root, "local authority state")

    now_fn = lambda: datetime.now(timezone.utc)
    context, issuer_keys, upstream_trust, durable_trust, currentness_trust = _config()

    admission_source = SQLiteEvidenceRuntimeAdmissionSource(evidence_db, upstream_trust, now_fn=now_fn)
    dispatch_source = SQLiteFleetDispatchSource(evidence_db, now_fn=now_fn)
    identity_source = SQLiteRuntimeIdentitySource(evidence_db, now_fn=now_fn)
    provisioning_source = SQLiteProvisioningBindingSource(evidence_db, now_fn=now_fn)
    transfer_source = SQLiteTransferBindingSource(evidence_db, now_fn=now_fn)
    currentness_source = SQLiteEffectTimeCurrentnessSource(evidence_db, currentness_trust, now_fn=now_fn)
    pin_source = SQLiteContextPinSource(evidence_db, now_fn=now_fn)

    def context_source(assignment_id: str):
        pin = pin_source(assignment_id)
        return PinnedCooperativeContextResolver(
            mission_db=mission_db,
            context_directory=context_root,
            pins=(pin,),
            admission_source=admission_source,
            admission_trust=upstream_trust,
            dispatch_source=dispatch_source,
            runtime_identity_source=identity_source,
            now_fn=now_fn,
        )(assignment_id)

    transport = ReadOnlyAuthorityControlPlaneTransport(control_db)
    authority_source = TrustedControlPlaneAuthoritySource(transport)
    local_store = SQLiteAuthorityStateStore(str(local_authority_state))
    authority = LiveAuthorityAdmission(
        authority_source=authority_source,
        context=context,
        issuer_keys=issuer_keys,
        signature_verifier=_load_verifier(),
        epoch_provider=ReadOnlyEpochProvider(authority_state_db),
        root_provider=ReadOnlyRootProvider(authority_state_db),
        replay_guard=DurableReplayGuard(local_store, domain="cooperative-worker"),
        binding_finalizer=PersistentBindingFinalizer(local_store),
    )

    return CooperativeRuntimeBootstrapDependencies(
        context_source=context_source,
        upstream_admission_source=admission_source,
        upstream_admission_trust=upstream_trust,
        durable_admission_trust=durable_trust,
        authority_admission=authority,
        currentness_source=currentness_source,
        currentness_trust=currentness_trust,
        dispatch_source=dispatch_source,
        runtime_identity_source=identity_source,
        provisioning_binding_source=provisioning_source,
        transfer_binding_source=transfer_source,
        now_fn=now_fn,
        authority_effect="NONE",
    ).validate()
