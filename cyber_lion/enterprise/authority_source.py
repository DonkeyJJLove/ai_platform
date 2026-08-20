"""Abstract canonical authority-lineage source contract.

This module defines deterministic lookup and provenance invariants for trusted authority
lineage records consumed by live admission and merge execution. It deliberately does not
implement a backend, verify signatures, admit epochs/revocation state, consume authority,
or execute effects.

Authoritative lineage records must come from a trusted control-plane source independent
of a pull-request tree. Repository/PR branch content is never accepted as authority.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import re
from typing import Final

from .authority_grant import AuthorityGrant

_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_PROVENANCE_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
_LINEAGE_DOMAIN: Final = b"CYBER-LION/AUTHORITY-SOURCE-LINEAGE/1.0.0\x00"
_TRUSTED_SOURCE_KIND: Final = "trusted-control-plane"


class AuthoritySourceError(ValueError):
    """Raised when canonical authority lookup cannot be proven safely."""


def _text(value: object, *, field_name: str, limit: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise AuthoritySourceError(f"{field_name} is invalid")
    return value


def _sha(value: object, *, field_name: str) -> str:
    value = _text(value, field_name=field_name, limit=40)
    if not _SHA_RE.fullmatch(value):
        raise AuthoritySourceError(f"{field_name} must be a full lowercase git SHA")
    return value


@dataclass(frozen=True)
class AuthorityLookupKey:
    """Exact immutable lookup identity for one PR-bound authority lineage."""

    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    mission_id: str
    grant_id: str

    def validate(self) -> "AuthorityLookupKey":
        _text(self.repository, field_name="repository")
        if (
            not isinstance(self.pr_number, int)
            or isinstance(self.pr_number, bool)
            or self.pr_number <= 0
        ):
            raise AuthoritySourceError("pr_number must be a positive integer")
        _sha(self.base_sha, field_name="base_sha")
        _sha(self.head_sha, field_name="head_sha")
        _text(self.mission_id, field_name="mission_id")
        _text(self.grant_id, field_name="grant_id")
        return self

    def binding(self) -> tuple[str, int, str, str, str, str]:
        self.validate()
        return (
            self.repository,
            self.pr_number,
            self.base_sha,
            self.head_sha,
            self.mission_id,
            self.grant_id,
        )


def canonical_pr_authority_resource(key: AuthorityLookupKey) -> str:
    """Canonical exact PR resource that the authority leaf must contain."""
    if type(key) is not AuthorityLookupKey:
        raise AuthoritySourceError("key must be exact AuthorityLookupKey")
    key.validate()
    return (
        f"github:repo:{key.repository}:pr:{key.pr_number}:"
        f"base:{key.base_sha}:head:{key.head_sha}"
    )


def canonical_source_lineage_digest(lineage: tuple[AuthorityGrant, ...]) -> str:
    """Hash one immutable root-to-leaf lineage without treating it as admission proof."""
    if type(lineage) is not tuple or not lineage:
        raise AuthoritySourceError("authority lineage must be a non-empty immutable tuple")
    payload = bytearray(_LINEAGE_DOMAIN)
    for grant in lineage:
        if type(grant) is not AuthorityGrant:
            raise AuthoritySourceError("lineage entries must be exact AuthorityGrant")
        grant.validate()
        digest = grant.digest()
        payload.extend(digest.encode("ascii"))
        payload.extend(b"\x00")
    return hashlib.sha256(bytes(payload)).hexdigest()


@dataclass(frozen=True)
class AuthorityLineageRecord:
    """Immutable source record; provenance is evidence, never execution permission."""

    lookup_key: AuthorityLookupKey
    lineage: tuple[AuthorityGrant, ...]
    lineage_digest: str
    provenance_id: str
    source_kind: str = _TRUSTED_SOURCE_KIND

    def validate(self) -> "AuthorityLineageRecord":
        if type(self.lookup_key) is not AuthorityLookupKey:
            raise AuthoritySourceError("lookup_key must be exact AuthorityLookupKey")
        self.lookup_key.validate()
        if type(self.lineage) is not tuple or not self.lineage:
            raise AuthoritySourceError("lineage must be a non-empty immutable tuple")
        if self.source_kind != _TRUSTED_SOURCE_KIND:
            raise AuthoritySourceError("authority source must be trusted-control-plane")
        if not isinstance(self.provenance_id, str) or not _PROVENANCE_RE.fullmatch(
            self.provenance_id
        ):
            raise AuthoritySourceError("provenance_id is invalid")
        if not isinstance(self.lineage_digest, str) or not _DIGEST_RE.fullmatch(
            self.lineage_digest
        ):
            raise AuthoritySourceError("lineage_digest must be canonical sha256 hex")

        previous: AuthorityGrant | None = None
        for grant in self.lineage:
            if type(grant) is not AuthorityGrant:
                raise AuthoritySourceError("lineage entries must be exact AuthorityGrant")
            grant.validate()
            if grant.mission_id != self.lookup_key.mission_id:
                raise AuthoritySourceError("lineage mission_id does not match lookup key")
            if previous is None:
                if grant.parent_grant_id is not None:
                    raise AuthoritySourceError("lineage root must not declare a parent grant")
            elif grant.parent_grant_id != previous.grant_id:
                raise AuthoritySourceError("lineage parent chain is not contiguous")
            previous = grant

        leaf = self.lineage[-1]
        if leaf.grant_id != self.lookup_key.grant_id:
            raise AuthoritySourceError("lineage leaf does not match lookup grant_id")
        expected_resource = canonical_pr_authority_resource(self.lookup_key)
        if expected_resource not in leaf.resource_scope:
            raise AuthoritySourceError("lineage leaf does not bind exact PR resource")
        expected_digest = canonical_source_lineage_digest(self.lineage)
        if self.lineage_digest != expected_digest:
            raise AuthoritySourceError("lineage_digest does not match immutable lineage")
        return self


class AuthoritySource(ABC):
    """Backend-independent fail-closed canonical authority source.

    Implementations may query an external trusted control plane, but callers receive only
    records that pass exact binding, provenance, and zero/one/many determinism checks.
    """

    @abstractmethod
    def _lookup_exact(self, key: AuthorityLookupKey) -> tuple[AuthorityLineageRecord, ...]:
        """Return every backend candidate for the exact key as an immutable tuple."""
        raise NotImplementedError

    def resolve_exact(self, key: AuthorityLookupKey) -> AuthorityLineageRecord:
        if type(key) is not AuthorityLookupKey:
            raise AuthoritySourceError("key must be exact AuthorityLookupKey")
        key.validate()
        candidates = self._lookup_exact(key)
        if type(candidates) is not tuple:
            raise AuthoritySourceError("authority source candidates must be an immutable tuple")
        if len(candidates) == 0:
            raise AuthoritySourceError("authority lineage not found")
        if len(candidates) > 1:
            raise AuthoritySourceError("authority lineage lookup is ambiguous")

        record = candidates[0]
        if type(record) is not AuthorityLineageRecord:
            raise AuthoritySourceError("authority source record has invalid type")
        record.validate()
        if record.lookup_key.binding() != key.binding():
            raise AuthoritySourceError("authority source record does not match exact lookup key")
        return record
