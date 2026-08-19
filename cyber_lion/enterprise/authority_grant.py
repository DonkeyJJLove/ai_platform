"""Authority-grant contract and deterministic attenuation checks.

This module defines authority data and one-hop delegation invariants only. It does not
verify signatures, consult revocation state, or execute effects. Those remain separate
MAND/EXEC responsibilities.

AuthorityGrant 1.0.0 preserves its historical canonical signed bytes and cannot express
delegation. AuthorityGrant 1.1.0 adds explicit delegation authority, a semantic authority
partial order, and a remaining lineage-depth ceiling. The depth ceiling is not a global
or sibling issuance quota; enforcing cardinality across independently issued grants
requires separate authoritative state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Dict, FrozenSet, Tuple

from .models import EnterpriseModelError, authority_rank

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0.0", "1.1.0"})

# Explicit semantic containment relation. The two high-impact classes ``financial``
# and ``deploy`` are intentionally incomparable, while ``privileged`` dominates both.
_AUTHORITY_CONTAINS: Dict[str, FrozenSet[str]] = {
    "none": frozenset({"none"}),
    "read": frozenset({"none", "read"}),
    "local_write": frozenset({"none", "read", "local_write"}),
    "external_write": frozenset({"none", "read", "local_write", "external_write"}),
    "financial": frozenset(
        {"none", "read", "local_write", "external_write", "financial"}
    ),
    "deploy": frozenset(
        {"none", "read", "local_write", "external_write", "deploy"}
    ),
    "privileged": frozenset(
        {
            "none",
            "read",
            "local_write",
            "external_write",
            "financial",
            "deploy",
            "privileged",
        }
    ),
}


class AuthorityGrantError(EnterpriseModelError):
    """Raised when an authority grant or delegation violates a deterministic invariant."""


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise AuthorityGrantError("grant timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise AuthorityGrantError("grant timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _validate_unique(
    values: Tuple[str, ...], *, field_name: str, allow_empty: bool = False
) -> None:
    if not allow_empty and not values:
        raise AuthorityGrantError(f"{field_name} must not be empty")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise AuthorityGrantError(f"{field_name} must contain non-empty strings")
    if len(set(values)) != len(values):
        raise AuthorityGrantError(f"{field_name} must be unique")


def _validate_authority_attenuation(
    parent_authority: str, child_authority: str
) -> None:
    """Require semantic containment in the explicit authority partial order."""
    try:
        contained = _AUTHORITY_CONTAINS[parent_authority]
        _AUTHORITY_CONTAINS[child_authority]
    except KeyError as exc:
        raise AuthorityGrantError(f"unknown authority class: {exc.args[0]}") from exc
    if child_authority not in contained:
        raise AuthorityGrantError(
            "child authority must be semantically contained in parent authority"
        )


@dataclass(frozen=True)
class AuthorityGrant:
    """Mission-scoped authority envelope; presence of this object is not signature proof."""

    schema_version: str
    grant_id: str
    issuer_subject_id: str
    subject_id: str
    tenant_id: str
    organization_id: str
    mission_id: str
    capability_id: str
    capability_version: str
    actions: Tuple[str, ...]
    resource_scope: Tuple[str, ...]
    authority_ceiling: str
    constraints: Tuple[str, ...]
    parent_grant_id: str | None
    issued_at: str
    expires_at: str
    epoch: int
    policy_digest: str
    observability_contract_digest: str
    signature: str
    delegation_allowed: bool = False
    delegation_depth_budget: int = 0

    def validate(self) -> "AuthorityGrant":
        required = (
            self.grant_id,
            self.issuer_subject_id,
            self.subject_id,
            self.tenant_id,
            self.organization_id,
            self.mission_id,
            self.capability_id,
            self.capability_version,
            self.authority_ceiling,
            self.policy_digest,
            self.observability_contract_digest,
            self.signature,
        )
        if self.schema_version not in _SUPPORTED_SCHEMA_VERSIONS or any(
            not isinstance(value, str) or not value.strip() for value in required
        ):
            raise AuthorityGrantError("grant required fields/schema are invalid")
        if self.parent_grant_id is not None and (
            not isinstance(self.parent_grant_id, str)
            or not self.parent_grant_id.strip()
        ):
            raise AuthorityGrantError(
                "parent_grant_id must be null or a non-empty string"
            )
        _validate_unique(self.actions, field_name="actions")
        _validate_unique(self.resource_scope, field_name="resource_scope")
        _validate_unique(self.constraints, field_name="constraints", allow_empty=True)
        authority_rank(self.authority_ceiling)
        if (
            not isinstance(self.epoch, int)
            or isinstance(self.epoch, bool)
            or self.epoch < 0
        ):
            raise AuthorityGrantError("grant epoch must be a non-negative integer")
        if type(self.delegation_allowed) is not bool:
            raise AuthorityGrantError("delegation_allowed must be a boolean")
        if (
            not isinstance(self.delegation_depth_budget, int)
            or isinstance(self.delegation_depth_budget, bool)
            or self.delegation_depth_budget < 0
        ):
            raise AuthorityGrantError(
                "delegation_depth_budget must be a non-negative integer"
            )

        if self.schema_version == "1.0.0":
            if self.delegation_allowed or self.delegation_depth_budget != 0:
                raise AuthorityGrantError(
                    "AuthorityGrant 1.0.0 cannot express delegation"
                )
        else:
            if self.delegation_allowed and self.delegation_depth_budget == 0:
                raise AuthorityGrantError(
                    "delegation_allowed requires a positive delegation_depth_budget"
                )
            if (
                not self.delegation_allowed
                and self.delegation_depth_budget != 0
            ):
                raise AuthorityGrantError(
                    "delegation_depth_budget must be zero when delegation is not allowed"
                )

        if _utc(self.issued_at) >= _utc(self.expires_at):
            raise AuthorityGrantError("grant validity window is invalid")
        if not _DIGEST_RE.fullmatch(self.policy_digest):
            raise AuthorityGrantError("policy_digest must be canonical sha256")
        if not _DIGEST_RE.fullmatch(self.observability_contract_digest):
            raise AuthorityGrantError(
                "observability_contract_digest must be canonical sha256"
            )
        return self

    def canonical_payload(self) -> bytes:
        """Canonical unsigned payload, versioned without rewriting historical v1.0 bytes."""
        self.validate()
        value: Dict[str, Any] = asdict(self)
        value.pop("signature")
        if self.schema_version == "1.0.0":
            # These fields did not exist in the historical v1.0 signed contract.
            value.pop("delegation_allowed")
            value.pop("delegation_depth_budget")
        value["actions"] = list(self.actions)
        value["resource_scope"] = list(self.resource_scope)
        value["constraints"] = list(self.constraints)
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(
            self.canonical_payload() + b"." + self.signature.encode("utf-8")
        ).hexdigest()


def validate_attenuation(
    parent: AuthorityGrant, child: AuthorityGrant
) -> AuthorityGrant:
    """Validate one-hop delegation without inferring semantics absent from the contracts."""
    parent.validate()
    child.validate()

    if parent.schema_version != "1.1.0" or child.schema_version != "1.1.0":
        raise AuthorityGrantError(
            "delegation requires AuthorityGrant 1.1.0 on both parent and child"
        )
    if child.grant_id == parent.grant_id:
        raise AuthorityGrantError("child grant_id must differ from parent grant_id")
    if child.parent_grant_id != parent.grant_id:
        raise AuthorityGrantError("child must bind to the exact parent grant")
    if child.issuer_subject_id != parent.subject_id:
        raise AuthorityGrantError("child issuer must equal parent grant subject")
    if not parent.delegation_allowed:
        raise AuthorityGrantError("parent grant does not permit delegation")
    if child.delegation_depth_budget >= parent.delegation_depth_budget:
        raise AuthorityGrantError(
            "child delegation_depth_budget must be strictly smaller than parent budget"
        )

    exact_bindings = (
        ("schema_version", parent.schema_version, child.schema_version),
        ("tenant_id", parent.tenant_id, child.tenant_id),
        ("organization_id", parent.organization_id, child.organization_id),
        ("mission_id", parent.mission_id, child.mission_id),
        ("capability_id", parent.capability_id, child.capability_id),
        ("capability_version", parent.capability_version, child.capability_version),
        ("epoch", parent.epoch, child.epoch),
        ("policy_digest", parent.policy_digest, child.policy_digest),
        (
            "observability_contract_digest",
            parent.observability_contract_digest,
            child.observability_contract_digest,
        ),
    )
    for name, parent_value, child_value in exact_bindings:
        if parent_value != child_value:
            raise AuthorityGrantError(f"child {name} must equal parent {name}")

    _validate_authority_attenuation(
        parent.authority_ceiling, child.authority_ceiling
    )
    if not set(child.actions).issubset(parent.actions):
        raise AuthorityGrantError("child actions must be a subset of parent actions")
    if not set(child.resource_scope).issubset(parent.resource_scope):
        raise AuthorityGrantError(
            "child resource_scope must be a subset of parent scope"
        )
    if not set(parent.constraints).issubset(child.constraints):
        raise AuthorityGrantError("child cannot remove parent constraints")
    if _utc(child.issued_at) < _utc(parent.issued_at):
        raise AuthorityGrantError("child cannot predate parent grant")
    if _utc(child.expires_at) > _utc(parent.expires_at):
        raise AuthorityGrantError("child cannot outlive parent grant")

    return child
