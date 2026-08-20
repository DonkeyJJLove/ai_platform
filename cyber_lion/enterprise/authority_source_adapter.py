"""Read-only adapter from a trusted external control plane to AuthoritySource.

The adapter deliberately exposes no mutation or secret-bearing configuration surface.
Concrete transports are responsible only for one exact read operation; transport
authentication/bootstrap belongs outside this contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Final

from .authority_grant import AuthorityGrant
from .authority_source import (
    AuthorityLineageRecord,
    AuthorityLookupKey,
    AuthoritySource,
    AuthoritySourceError,
)

_RECORD_FIELDS: Final = frozenset(
    {"lookup_key", "lineage", "lineage_digest", "provenance_id", "source_kind"}
)
_KEY_FIELDS: Final = frozenset(
    {"repository", "pr_number", "base_sha", "head_sha", "mission_id", "grant_id"}
)
_GRANT_FIELDS: Final = frozenset(
    {
        "schema_version",
        "grant_id",
        "issuer_subject_id",
        "subject_id",
        "tenant_id",
        "organization_id",
        "mission_id",
        "capability_id",
        "capability_version",
        "actions",
        "resource_scope",
        "authority_ceiling",
        "constraints",
        "parent_grant_id",
        "issued_at",
        "expires_at",
        "epoch",
        "policy_digest",
        "observability_contract_digest",
        "signature",
        "delegation_allowed",
        "delegation_depth_budget",
    }
)
_TUPLE_FIELDS: Final = frozenset({"actions", "resource_scope", "constraints"})


class AuthoritySourceTransport(ABC):
    """Capability-reduced transport: one exact read operation and no mutations."""

    @abstractmethod
    def lookup_exact(
        self,
        *,
        repository: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        mission_id: str,
        grant_id: str,
    ) -> tuple[Mapping[str, object], ...]:
        """Return raw records for exactly one lookup key as an immutable tuple."""
        raise NotImplementedError


def _exact_mapping(
    value: object, *, fields: frozenset[str], field_name: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AuthoritySourceError(f"{field_name} must be a mapping")
    keys = frozenset(value.keys())
    if keys != fields or any(not isinstance(key, str) for key in value.keys()):
        raise AuthoritySourceError(f"{field_name} fields are not canonical")
    return value


def _decode_key(value: object) -> AuthorityLookupKey:
    raw = _exact_mapping(value, fields=_KEY_FIELDS, field_name="lookup_key")
    try:
        key = AuthorityLookupKey(
            repository=raw["repository"],
            pr_number=raw["pr_number"],
            base_sha=raw["base_sha"],
            head_sha=raw["head_sha"],
            mission_id=raw["mission_id"],
            grant_id=raw["grant_id"],
        )
        return key.validate()
    except (KeyError, TypeError, AuthoritySourceError) as exc:
        if isinstance(exc, AuthoritySourceError):
            raise
        raise AuthoritySourceError("lookup_key wire record is invalid") from exc


def _wire_tuple(value: object, *, field_name: str) -> tuple[str, ...]:
    if type(value) not in {list, tuple}:
        raise AuthoritySourceError(f"grant {field_name} must be a list or tuple")
    if any(not isinstance(item, str) for item in value):
        raise AuthoritySourceError(f"grant {field_name} must contain strings")
    return tuple(value)


def _decode_grant(value: object) -> AuthorityGrant:
    raw = _exact_mapping(value, fields=_GRANT_FIELDS, field_name="grant")
    decoded = dict(raw)
    for field_name in _TUPLE_FIELDS:
        decoded[field_name] = _wire_tuple(decoded[field_name], field_name=field_name)
    try:
        grant = AuthorityGrant(**decoded)
        return grant.validate()
    except (TypeError, ValueError) as exc:
        raise AuthoritySourceError("authority grant wire record is invalid") from exc


def _decode_record(value: object) -> AuthorityLineageRecord:
    raw = _exact_mapping(value, fields=_RECORD_FIELDS, field_name="authority record")
    lineage_raw = raw["lineage"]
    if type(lineage_raw) not in {list, tuple} or not lineage_raw:
        raise AuthoritySourceError("authority record lineage must be a non-empty list or tuple")
    lineage = tuple(_decode_grant(item) for item in lineage_raw)
    record = AuthorityLineageRecord(
        lookup_key=_decode_key(raw["lookup_key"]),
        lineage=lineage,
        lineage_digest=raw["lineage_digest"],
        provenance_id=raw["provenance_id"],
        source_kind=raw["source_kind"],
    )
    return record.validate()


class TrustedControlPlaneAuthoritySource(AuthoritySource):
    """Fail-closed read-only adapter for a trusted external authority control plane."""

    __slots__ = ("_transport",)

    def __init__(self, transport: AuthoritySourceTransport) -> None:
        if not isinstance(transport, AuthoritySourceTransport):
            raise AuthoritySourceError("transport must implement AuthoritySourceTransport")
        self._transport = transport

    def _lookup_exact(
        self, key: AuthorityLookupKey
    ) -> tuple[AuthorityLineageRecord, ...]:
        if type(key) is not AuthorityLookupKey:
            raise AuthoritySourceError("key must be exact AuthorityLookupKey")
        key.validate()
        try:
            raw_records = self._transport.lookup_exact(
                repository=key.repository,
                pr_number=key.pr_number,
                base_sha=key.base_sha,
                head_sha=key.head_sha,
                mission_id=key.mission_id,
                grant_id=key.grant_id,
            )
        except Exception as exc:
            raise AuthoritySourceError("authority source unavailable") from exc
        if type(raw_records) is not tuple:
            raise AuthoritySourceError("authority transport result must be an immutable tuple")

        records = tuple(_decode_record(raw) for raw in raw_records)
        for record in records:
            if record.lookup_key.binding() != key.binding():
                raise AuthoritySourceError("authority transport returned a different exact lookup key")
        return records
