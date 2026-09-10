from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

ALLOWED_ROOTS = (
    Path("/var/lib/sentinelx/uploads/vkt-r3-lpcl-v2-final"),
    Path("/var/lib/sentinelx/uploads/vkt-r3-validation"),
    Path("/var/lib/sentinelx/uploads/oss-repository-tests"),
    Path("/var/lib/sentinelx/uploads/lion-mission-control"),
)
DENIED_NAMES = {".env", "credentials", "credentials.json", "id_rsa", "id_ed25519", "secrets", "secrets.json"}
MAX_ARTIFACT_READ = 256 * 1024 * 1024


def safe_path(path: str | Path, roots: tuple[Path, ...] = ALLOWED_ROOTS) -> Path:
    candidate = Path(path)
    if candidate.name.lower() in DENIED_NAMES or candidate.name.lower().startswith(".env"):
        raise ValueError("secret-like artifact denied")
    resolved = candidate.resolve(strict=True)
    if resolved.is_symlink():
        raise ValueError("symlink artifact denied")
    allowed = False
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        raise ValueError("artifact path outside allowlist")
    if not resolved.is_file():
        raise ValueError("artifact is not file")
    if resolved.stat().st_size > MAX_ARTIFACT_READ:
        raise ValueError("artifact too large")
    return resolved


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def describe_artifact(run_id: str, path: str | Path, evidence_class: str = "ARTIFACT_HASH") -> dict[str, Any]:
    resolved = safe_path(path)
    digest = sha256_file(resolved)
    return {
        "artifact_id": f"{run_id}:{digest[:24]}",
        "path": str(resolved),
        "sha256": digest,
        "size": resolved.stat().st_size,
        "evidence_class": evidence_class,
    }
