"""LION R11 — exact factory binding existing canonical R6.21/R6.16/R6.17.

Does NOT construct, forge or issue authority/admission/evidence and does NOT
provision a mission, worker or Docker resource. On production the outer R11
preactivation bootstrap independently pins this entire module's bytes. An
independently installed and source-pinned producer provides existing typed
owners. Production invocation is restricted to the canonical Mission Control
process on LION-AUTH-LAB, reading its original SQLite inode.

No default READY: failure in any observation aborts before binding.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import re
import socket
import stat
import sys
from typing import Any
from types import ModuleType

from cyber_lion.enterprise.cooperative_runtime_preparation_provider import (
    CooperativeRuntimePreparationProvider,
)
from cyber_lion.enterprise.cooperative_control_plane_materializer import (
    CooperativeControlPlaneMaterializer,
)
from cyber_lion.enterprise.cooperative_runtime_root import (
    CooperativeRuntimeCompositionRoot,
)
from cyber_lion.mission_control.cooperative_preactivation_bootstrap import (
    CooperativeSourceBoundPreactivation,
)

FACTORY_VERSION = "1.0.0"
BINDING_SCHEMA = "lion.r11.typed-existing-owners-factory/v1"
EXPECTED_HOST = "LION-AUTH-LAB"
EXPECTED_MC_SOURCE_ROOT = Path("/var/lib/sentinelx/uploads/lion-mission-control-v3")
EXPECTED_DB = EXPECTED_MC_SOURCE_ROOT / "mission-control-v3.db"
EXPECTED_WORKER = "MD001"
OWNER_FACTORY_SYMBOL = "build_current_owners"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
_PATH_ENV = "LION_R11_SOURCE_BOUND_OWNER_MODULE_PATH"
_SHA_ENV = "LION_R11_SOURCE_BOUND_OWNER_MODULE_SHA256"


class R11OwnerFactoryError(RuntimeError):
    pass


def _need(ok: bool, reason: str) -> None:
    if not ok:
        raise R11OwnerFactoryError(reason)


def _direct(path: str | Path, label: str, *, directory: bool = False) -> Path:
    p = Path(path)
    _need(p.is_absolute() and not p.is_symlink(), label + ": direct absolute path required")
    try:
        resolved = p.resolve(strict=True)
        s = p.lstat()
    except (OSError, ValueError) as exc:
        raise R11OwnerFactoryError(label + ": missing or unreadable") from exc
    _need(resolved == p, label + ": path indirection")
    _need(stat.S_ISDIR(s.st_mode) if directory else
          stat.S_ISREG(s.st_mode) and s.st_nlink == 1,
          label + ": unexpected object type")
    return p


def _identity(path: Path) -> tuple[int, int]:
    s = path.stat()
    return s.st_dev, s.st_ino


def _import_pinned_owner_source(module_path: Path, expected_sha: str):
    _need(HEX64.fullmatch(expected_sha) is not None, "owner source digest malformed")
    p = _direct(module_path, "owner source module")
    _need(EXPECTED_MC_SOURCE_ROOT not in p.parents and
          p != EXPECTED_MC_SOURCE_ROOT, "owner source may not impersonate MC repository")
    st = p.stat()
    _need(st.st_uid in {0, os.geteuid()} and not(st.st_mode & 0o022),
          "owner module owner/mode not trusted")
    original_inode = _identity(p)
    original_bytes = p.read_bytes()
    _need(sha256(original_bytes).hexdigest() == expected_sha,
          "owner source module digest mismatch")
    # Execute only the exact bytes already checked against the operator pin.
    # SourceFileLoader reopens the path after prehash verification, otherwise
    # an unverified transient replacement could execute and be restored.
    module_id = "_lion_r11_exact_source_" + expected_sha[:24]
    module = ModuleType(module_id)
    module.__file__ = str(p)
    module.__package__ = ""
    try:
        validated_code = compile(original_bytes, str(p), "exec", dont_inherit=True)
        sys.modules[module_id] = module
        exec(validated_code, module.__dict__)
    except Exception as exc:
        sys.modules.pop(module_id, None)
        raise R11OwnerFactoryError("owner source module failed closed") from exc
    try:
        _need(_identity(p) == original_inode and
              sha256(p.read_bytes()).hexdigest() == expected_sha,
              "owner source changed during import")
        maker = getattr(module, OWNER_FACTORY_SYMBOL, None)
        _need(callable(maker), "trusted current owner constructor unavailable")
    except Exception:
        sys.modules.pop(module_id, None)
        raise
    return maker


def compose_existing_owners(
    objects: tuple[Any, Any, Any, str],
    *,
    canonical_db: Path,
    expected_worker: str = EXPECTED_WORKER,
) -> CooperativeSourceBoundPreactivation:
    """Bind already-created real owner objects, never generate missing evidence."""
    _need(type(objects) is tuple and len(objects) == 4,
          "existing owner tuple must contain exactly three owners and one worker")
    prep, materializer, root, worker = objects
    _need(type(prep) is CooperativeRuntimePreparationProvider,
          "exact R6.21 owner required")
    _need(type(materializer) is CooperativeControlPlaneMaterializer,
          "exact R6.16 owner required")
    _need(type(root) is CooperativeRuntimeCompositionRoot,
          "exact R6.17 owner required")
    _need(type(worker) is str and worker == expected_worker == EXPECTED_WORKER,
          "one MD001 source-bound worker only")
    canonical = _direct(canonical_db, "canonical Mission Control SQLite")
    inode = _identity(canonical)
    for path in (prep.mission_db, materializer.mission_db, root.mission_db):
        _need(_identity(_direct(path, "owner Mission Control SQLite")) == inode,
              "separate, substituted or copied Mission Control DB denied")
    result = CooperativeSourceBoundPreactivation(
        prep, materializer, root, worker,
    ).validate()
    _need(_identity(canonical) == inode, "canonical MC database identity drift")
    _need(result.authority_effect == "NONE",
          "owner composition cannot issue authority")
    return result


def build() -> CooperativeSourceBoundPreactivation:
    """Factory entrypoint for the existing SHA-256-pinned R11 bootstrap.

    Requires a separately admitted and installed owner-source module. Neither
    the module digest nor this return value grants material effect authority.
    """
    _need(socket.gethostname().upper() == EXPECTED_HOST,
          "R11 owner factory may run only on canonical Mission Control host")
    _need(Path.cwd() == EXPECTED_MC_SOURCE_ROOT,
          "R11 factory requires active canonical MC working directory")
    _need(EXPECTED_MC_SOURCE_ROOT.is_dir(),
          "canonical Mission Control root unavailable")
    db = _direct(EXPECTED_DB, "canonical Mission Control SQLite")
    _need(db.stat().st_size > 4096, "canonical Mission Control SQLite not initialized")
    module = os.environ.get(_PATH_ENV, "")
    digest = os.environ.get(_SHA_ENV, "")
    _need(bool(module), "source-bound owner module not installed")
    _need(HEX64.fullmatch(digest) is not None,
          "source-bound owner module digest unavailable")
    owner_builder = _import_pinned_owner_source(Path(module), digest)
    try:
        owners = owner_builder()
    except Exception as exc:
        raise R11OwnerFactoryError("actual source-bound owners unavailable") from exc
    return compose_existing_owners(owners, canonical_db=db)
