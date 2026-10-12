"""R11 source-pinned build_current_owners() for an ORIGINAL trusted producer.

The first-party Mission Control R11 factory imports THIS module only from a
protected, SHA-256 pinned external release path. This module has no default
authority, no fixtures, no fallback providers, no worker launch and no DB copy.

The upstream source module MUST be independently admitted and pinned by its
own SHA-256. It must return exact CurrentOwnerSources containing already
existing canonical authority, PDP, runtime admission and currentness owners.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType

from cyber_lion.mission_control.cooperative_current_owner_wiring import (
    CurrentOwnerSources,
    assemble_original_owners,
)

SCHEMA = "lion.r11.external-current-owner-source/v1"
VERSION = "1.0.0"
_SOURCE_PATH = "LION_R11_CURRENT_OWNER_SOURCES_MODULE_PATH"
_SOURCE_HASH = "LION_R11_CURRENT_OWNER_SOURCES_MODULE_SHA256"
_SOURCE_VERSION = "LION_R11_CURRENT_OWNER_SOURCES_MODULE_VERSION"
_SOURCE_SYMBOL = "build_current_owner_sources"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class R11ExternalCurrentOwnerError(RuntimeError):
    pass


def _need(ok: bool, reason: str) -> None:
    if not ok:
        raise R11ExternalCurrentOwnerError(reason)


def _pinned_current_source():
    """Compile ONLY bytes verified against independent SHA pin (no importlib reopen)."""
    raw_path = os.environ.get(_SOURCE_PATH)
    expected = os.environ.get(_SOURCE_HASH)
    version = os.environ.get(_SOURCE_VERSION)
    _need(version == VERSION, "original owner-source version unavailable")
    _need(isinstance(raw_path, str) and raw_path, "original owner-source path unavailable")
    _need(isinstance(expected, str) and _SHA256.fullmatch(expected) is not None,
          "original owner-source digest unavailable")
    p = Path(raw_path)
    _need(p.is_absolute() and not p.is_symlink(), "original owner source must be direct")
    try:
        resolved = p.resolve(strict=True)
        s = p.lstat()
        parent = p.parent.lstat()
    except (OSError, ValueError) as exc:
        raise R11ExternalCurrentOwnerError("original owner source missing") from exc
    _need(resolved == p, "original owner-source path indirection denied")
    canonical_app_root = Path("/var/lib/sentinelx/uploads/lion-mission-control-v3")
    _need(p != canonical_app_root and canonical_app_root not in p.parents,
          "original owner source must be outside Mission Control repository")
    _need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "original owner-source file type")
    _need(stat.S_ISDIR(parent.st_mode) and not p.parent.is_symlink()
          and not (parent.st_mode & 0o022), "original owner-source parent mutable")
    _need(s.st_uid in {0, os.geteuid()} and not (s.st_mode & 0o022),
          "original owner-source owner/mode not trusted")
    original_identity = (s.st_dev, s.st_ino)
    original = p.read_bytes()
    _need(sha256(original).hexdigest() == expected,
          "original owner-source digest mismatch")
    name = "_lion_r11_current_owner_evidence_" + expected[:24]
    module = ModuleType(name)
    module.__file__ = str(p)
    module.__package__ = ""
    try:
        compiled = compile(original, str(p), "exec", dont_inherit=True)
        sys.modules[name] = module
        exec(compiled, module.__dict__)
        after = p.lstat()
        _need((after.st_dev, after.st_ino) == original_identity
              and sha256(p.read_bytes()).hexdigest() == expected,
              "original owner source changed during import")
        maker = getattr(module, _SOURCE_SYMBOL, None)
        _need(callable(maker), "original current owner source callable unavailable")
        return maker
    except Exception as exc:
        if isinstance(exc, R11ExternalCurrentOwnerError):
            raise
        raise R11ExternalCurrentOwnerError(
            "original current owner source import failed closed"
        ) from exc
    finally:
        sys.modules.pop(name, None)


def build_current_owners():
    """Return original three owners + MD001; NEVER fabricate source evidence."""
    maker = _pinned_current_source()
    try:
        sources = maker()
    except Exception as exc:
        raise R11ExternalCurrentOwnerError(
            "actual independent current owner sources unavailable"
        ) from exc
    _need(type(sources) is CurrentOwnerSources,
          "original owner provider did not return exact CurrentOwnerSources")
    # validate is no-effect; assemble initializes ONLY private provider stores.
    sources.validate()
    return assemble_original_owners(sources)
