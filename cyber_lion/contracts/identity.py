"""Cyber-Lion entity identity v1.

This module deliberately does not replace the SBOM AID contract. It wraps an
existing AID observation in a more general entity envelope and preserves the
original AID values for round-trip compatibility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, Mapping, Optional

_ENTITY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")

ENTITY_TYPES = {
    "application",
    "repository",
    "service",
    "agent",
    "model",
    "tool",
    "artifact",
    "experiment",
    "execution",
    "dataset",
    "workload",
    "other",
}

ENVIRONMENTS = {"lab", "dev", "test", "stage", "prod", "local", "unknown"}

_REQUIRED_AID_FIELDS = {
    "app_id",
    "owner_team",
    "env",
    "vcs_ref",
    "app_version",
}


class IdentityValidationError(ValueError):
    """Raised when an identity or compatibility envelope is invalid."""


@dataclass(frozen=True)
class EntityIdentity:
    schema_version: str
    entity_id: str
    entity_type: str
    owner: str
    environment: str
    repo: Optional[str] = None
    version: Optional[str] = None
    vcs_ref: Optional[str] = None
    runtime: Optional[str] = None
    parent_entity: Optional[str] = None
    created_at: Optional[str] = None
    compat: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "EntityIdentity":
        if self.schema_version != "1.0.0":
            raise IdentityValidationError("unsupported schema_version")
        if not self.entity_id or not _ENTITY_ID_RE.fullmatch(self.entity_id):
            raise IdentityValidationError("invalid entity_id")
        if self.entity_type not in ENTITY_TYPES:
            raise IdentityValidationError("invalid entity_type")
        if not self.owner.strip():
            raise IdentityValidationError("owner must be explicit")
        if self.environment not in ENVIRONMENTS:
            raise IdentityValidationError("invalid environment")
        if self.repo is not None and not _REPO_RE.fullmatch(self.repo):
            raise IdentityValidationError("repo must use owner/name form")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)


def entity_from_aid(aid: Mapping[str, Any]) -> EntityIdentity:
    """Wrap an existing SBOM AID object without changing its semantics.

    AID remains the compatibility source of truth for its original fields. The
    generalized entity identifier is namespaced as ``aid:application:<app_id>``
    so that it cannot be confused with a network address or VCS reference.
    """

    missing = sorted(_REQUIRED_AID_FIELDS - set(aid))
    if missing:
        raise IdentityValidationError(f"missing AID fields: {missing}")

    app_id = str(aid["app_id"]).strip()
    owner = str(aid["owner_team"]).strip()
    environment = str(aid["env"]).strip().lower()
    vcs_ref = str(aid["vcs_ref"]).strip()
    version = str(aid["app_version"]).strip()
    repo_value = aid.get("repo")
    repo = str(repo_value).strip() if repo_value not in (None, "") else None

    entity = EntityIdentity(
        schema_version="1.0.0",
        entity_id=f"aid:application:{app_id}",
        entity_type="application",
        owner=owner,
        environment=environment if environment in ENVIRONMENTS else "unknown",
        repo=repo,
        version=version,
        vcs_ref=vcs_ref,
        compat={"aid": dict(aid)},
    )
    return entity.validate()


def aid_from_entity(entity: EntityIdentity) -> Dict[str, Any]:
    """Recover the exact wrapped AID values.

    This is intentionally not a lossy reconstruction from generalized fields.
    Migration requires the original AID object to survive in ``compat.aid``.
    """

    entity.validate()
    aid = entity.compat.get("aid")
    if not isinstance(aid, dict):
        raise IdentityValidationError("entity has no compatible AID payload")
    missing = sorted(_REQUIRED_AID_FIELDS - set(aid))
    if missing:
        raise IdentityValidationError(f"wrapped AID is incomplete: {missing}")
    return dict(aid)
