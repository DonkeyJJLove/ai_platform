"""Trusted read-only PR-to-authority bootstrap discovery.

This module resolves an exact pull-request identity to the immutable public bootstrap
needed by CI live authority admission. Discovery is evidence about which authority
context to evaluate; it never grants merge permission, consumes authority, reads the
PR tree, or exposes mutation capabilities.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Final

from .authority_verification import IssuerKeyBinding
from .ci_live_admission import CILiveAdmissionBootstrap

_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_PROVENANCE_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
_TRUSTED_SOURCE_KIND: Final = "trusted-control-plane"
_BOOTSTRAP_DOMAIN: Final = b"CYBER-LION/PR-AUTHORITY-BOOTSTRAP/1.0.0\x00"
_MERGE_METHODS: Final = frozenset({"merge", "squash", "rebase"})


class PRAuthorityBootstrapError(ValueError):
    """Raised when trusted PR bootstrap discovery cannot be proven canonical."""


def _text(value: object, *, field_name: str, limit: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise PRAuthorityBootstrapError(f"{field_name} is invalid")
    return value


def _sha(value: object, *, field_name: str) -> str:
    value = _text(value, field_name=field_name, limit=40)
    if not _SHA_RE.fullmatch(value):
        raise PRAuthorityBootstrapError(
            f"{field_name} must be a full lowercase git SHA"
        )
    return value


def _digest(value: object, *, field_name: str) -> str:
    value = _text(value, field_name=field_name, limit=64)
    if not _DIGEST_RE.fullmatch(value):
        raise PRAuthorityBootstrapError(
            f"{field_name} must be canonical sha256 hex"
        )
    return value


@dataclass(frozen=True)
class PRAuthorityBootstrapLookupKey:
    """Exact immutable PR identity used for bootstrap discovery."""

    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    merge_method: str

    def validate(self) -> "PRAuthorityBootstrapLookupKey":
        if type(self) is not PRAuthorityBootstrapLookupKey:
            raise PRAuthorityBootstrapError(
                "lookup key must be exact PRAuthorityBootstrapLookupKey"
            )
        _text(self.repository, field_name="repository")
        if (
            not isinstance(self.pr_number, int)
            or isinstance(self.pr_number, bool)
            or self.pr_number <= 0
        ):
            raise PRAuthorityBootstrapError(
                "pr_number must be a positive integer"
            )
        _sha(self.base_sha, field_name="base_sha")
        _sha(self.head_sha, field_name="head_sha")
        if self.merge_method not in _MERGE_METHODS:
            raise PRAuthorityBootstrapError("merge_method is unsupported")
        return self

    def binding(self) -> tuple[str, int, str, str, str]:
        self.validate()
        return (
            self.repository,
            self.pr_number,
            self.base_sha,
            self.head_sha,
            self.merge_method,
        )


@dataclass(frozen=True)
class PRAuthorityBootstrapRecord:
    """Immutable trusted discovery result; evidence, never merge permission."""

    lookup_key: PRAuthorityBootstrapLookupKey
    mission_id: str
    grant_id: str
    trust_domain: str
    tenant_id: str
    organization_id: str
    epoch: int
    root_grant_id: str
    root_grant_digest: str
    issuer_key_bindings: tuple[IssuerKeyBinding, ...]
    provenance_id: str
    bootstrap_digest: str
    source_kind: str = _TRUSTED_SOURCE_KIND

    def validate(self) -> "PRAuthorityBootstrapRecord":
        if type(self) is not PRAuthorityBootstrapRecord:
            raise PRAuthorityBootstrapError(
                "record must be exact PRAuthorityBootstrapRecord"
            )
        if type(self.lookup_key) is not PRAuthorityBootstrapLookupKey:
            raise PRAuthorityBootstrapError(
                "lookup_key must be exact PRAuthorityBootstrapLookupKey"
            )
        self.lookup_key.validate()
        for field_name in (
            "mission_id",
            "grant_id",
            "trust_domain",
            "tenant_id",
            "organization_id",
            "root_grant_id",
        ):
            _text(getattr(self, field_name), field_name=field_name)
        if (
            not isinstance(self.epoch, int)
            or isinstance(self.epoch, bool)
            or self.epoch < 0
        ):
            raise PRAuthorityBootstrapError(
                "epoch must be a non-negative integer"
            )
        _digest(self.root_grant_digest, field_name="root_grant_digest")
        if type(self.issuer_key_bindings) is not tuple or not self.issuer_key_bindings:
            raise PRAuthorityBootstrapError(
                "issuer_key_bindings must be a non-empty immutable tuple"
            )
        for binding in self.issuer_key_bindings:
            if type(binding) is not IssuerKeyBinding:
                raise PRAuthorityBootstrapError(
                    "issuer key binding must be exact IssuerKeyBinding"
                )
            binding.validate()
        if self.source_kind != _TRUSTED_SOURCE_KIND:
            raise PRAuthorityBootstrapError(
                "bootstrap source must be trusted-control-plane"
            )
        if (
            not isinstance(self.provenance_id, str)
            or not _PROVENANCE_RE.fullmatch(self.provenance_id)
        ):
            raise PRAuthorityBootstrapError("provenance_id is invalid")
        _digest(self.bootstrap_digest, field_name="bootstrap_digest")
        expected = canonical_pr_bootstrap_digest(self)
        if self.bootstrap_digest != expected:
            raise PRAuthorityBootstrapError(
                "bootstrap_digest does not match immutable bootstrap"
            )
        return self

    def to_live_admission_bootstrap(self) -> CILiveAdmissionBootstrap:
        self.validate()
        return CILiveAdmissionBootstrap(
            trust_domain=self.trust_domain,
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            mission_id=self.mission_id,
            grant_id=self.grant_id,
            epoch=self.epoch,
            root_grant_id=self.root_grant_id,
            root_grant_digest=self.root_grant_digest,
        ).validate()


def _binding_payload(binding: IssuerKeyBinding) -> dict[str, object]:
    binding.validate()
    return {
        "issuer_subject_id": binding.issuer_subject_id,
        "trust_domain": binding.trust_domain,
        "key_id": binding.key_id,
        "algorithm": binding.algorithm,
    }


def canonical_pr_bootstrap_digest(record: PRAuthorityBootstrapRecord) -> str:
    """Hash immutable public discovery evidence; this is not an authority proof."""
    if type(record) is not PRAuthorityBootstrapRecord:
        raise PRAuthorityBootstrapError(
            "record must be exact PRAuthorityBootstrapRecord"
        )
    key = record.lookup_key
    if type(key) is not PRAuthorityBootstrapLookupKey:
        raise PRAuthorityBootstrapError(
            "lookup_key must be exact PRAuthorityBootstrapLookupKey"
        )
    key.validate()
    payload = {
        "lookup_key": {
            "repository": key.repository,
            "pr_number": key.pr_number,
            "base_sha": key.base_sha,
            "head_sha": key.head_sha,
            "merge_method": key.merge_method,
        },
        "mission_id": record.mission_id,
        "grant_id": record.grant_id,
        "trust_domain": record.trust_domain,
        "tenant_id": record.tenant_id,
        "organization_id": record.organization_id,
        "epoch": record.epoch,
        "root_grant_id": record.root_grant_id,
        "root_grant_digest": record.root_grant_digest,
        "issuer_key_bindings": [
            _binding_payload(binding) for binding in record.issuer_key_bindings
        ],
        "provenance_id": record.provenance_id,
        "source_kind": record.source_kind,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(_BOOTSTRAP_DOMAIN + encoded).hexdigest()


class PRAuthorityBootstrapTransport(ABC):
    """Capability-reduced read-only transport for exact bootstrap lookup."""

    @abstractmethod
    def lookup_exact(
        self,
        *,
        repository: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        merge_method: str,
    ) -> tuple[Mapping[str, object], ...]:
        raise NotImplementedError


class PRAuthorityBootstrapSource(ABC):
    """Backend-independent deterministic source for trusted bootstrap records."""

    @abstractmethod
    def _lookup_exact(
        self, key: PRAuthorityBootstrapLookupKey
    ) -> tuple[PRAuthorityBootstrapRecord, ...]:
        raise NotImplementedError

    def resolve_exact(
        self, key: PRAuthorityBootstrapLookupKey
    ) -> PRAuthorityBootstrapRecord:
        if type(key) is not PRAuthorityBootstrapLookupKey:
            raise PRAuthorityBootstrapError(
                "key must be exact PRAuthorityBootstrapLookupKey"
            )
        key.validate()
        candidates = self._lookup_exact(key)
        if type(candidates) is not tuple:
            raise PRAuthorityBootstrapError(
                "bootstrap candidates must be an immutable tuple"
            )
        if len(candidates) == 0:
            raise PRAuthorityBootstrapError("authority bootstrap not found")
        if len(candidates) > 1:
            raise PRAuthorityBootstrapError(
                "authority bootstrap lookup is ambiguous"
            )
        record = candidates[0]
        if type(record) is not PRAuthorityBootstrapRecord:
            raise PRAuthorityBootstrapError("bootstrap record type is invalid")
        record.validate()
        if record.lookup_key.binding() != key.binding():
            raise PRAuthorityBootstrapError(
                "bootstrap record does not match exact PR lookup key"
            )
        return record


_LOOKUP_KEYS: Final = {
    "repository",
    "pr_number",
    "base_sha",
    "head_sha",
    "merge_method",
}
_ISSUER_KEYS: Final = {
    "issuer_subject_id",
    "trust_domain",
    "key_id",
    "algorithm",
}
_RECORD_KEYS: Final = {
    "lookup_key",
    "mission_id",
    "grant_id",
    "trust_domain",
    "tenant_id",
    "organization_id",
    "epoch",
    "root_grant_id",
    "root_grant_digest",
    "issuer_key_bindings",
    "provenance_id",
    "bootstrap_digest",
    "source_kind",
}


def _exact_mapping(
    value: object, *, expected: set[str], field_name: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise PRAuthorityBootstrapError(f"{field_name} shape is invalid")
    return value


def decode_pr_authority_bootstrap_record(
    raw: Mapping[str, object],
) -> PRAuthorityBootstrapRecord:
    """Strictly decode one trusted wire record; unknown/secret fields are rejected."""
    item = _exact_mapping(raw, expected=_RECORD_KEYS, field_name="record")
    raw_key = _exact_mapping(
        item["lookup_key"], expected=_LOOKUP_KEYS, field_name="lookup_key"
    )
    key = PRAuthorityBootstrapLookupKey(
        repository=raw_key["repository"],
        pr_number=raw_key["pr_number"],
        base_sha=raw_key["base_sha"],
        head_sha=raw_key["head_sha"],
        merge_method=raw_key["merge_method"],
    ).validate()

    raw_bindings = item["issuer_key_bindings"]
    if not isinstance(raw_bindings, list) or not raw_bindings:
        raise PRAuthorityBootstrapError(
            "issuer_key_bindings wire value must be a non-empty array"
        )
    bindings: list[IssuerKeyBinding] = []
    for raw_binding in raw_bindings:
        binding = _exact_mapping(
            raw_binding, expected=_ISSUER_KEYS, field_name="issuer_key_binding"
        )
        bindings.append(
            IssuerKeyBinding(
                issuer_subject_id=binding["issuer_subject_id"],
                trust_domain=binding["trust_domain"],
                key_id=binding["key_id"],
                algorithm=binding["algorithm"],
            ).validate()
        )

    return PRAuthorityBootstrapRecord(
        lookup_key=key,
        mission_id=item["mission_id"],
        grant_id=item["grant_id"],
        trust_domain=item["trust_domain"],
        tenant_id=item["tenant_id"],
        organization_id=item["organization_id"],
        epoch=item["epoch"],
        root_grant_id=item["root_grant_id"],
        root_grant_digest=item["root_grant_digest"],
        issuer_key_bindings=tuple(bindings),
        provenance_id=item["provenance_id"],
        bootstrap_digest=item["bootstrap_digest"],
        source_kind=item["source_kind"],
    ).validate()


class TrustedControlPlanePRAuthorityBootstrapSource(PRAuthorityBootstrapSource):
    """Decode bootstrap candidates from one read-only trusted-control-plane transport."""

    __slots__ = ("_transport",)

    def __init__(self, transport: PRAuthorityBootstrapTransport) -> None:
        if not isinstance(transport, PRAuthorityBootstrapTransport):
            raise PRAuthorityBootstrapError(
                "transport must implement PRAuthorityBootstrapTransport"
            )
        self._transport = transport

    def _lookup_exact(
        self, key: PRAuthorityBootstrapLookupKey
    ) -> tuple[PRAuthorityBootstrapRecord, ...]:
        key.validate()
        try:
            raw = self._transport.lookup_exact(
                repository=key.repository,
                pr_number=key.pr_number,
                base_sha=key.base_sha,
                head_sha=key.head_sha,
                merge_method=key.merge_method,
            )
        except Exception as exc:
            raise PRAuthorityBootstrapError(
                "trusted bootstrap transport failed"
            ) from exc
        if type(raw) is not tuple:
            raise PRAuthorityBootstrapError(
                "transport candidates must be an immutable tuple"
            )
        return tuple(decode_pr_authority_bootstrap_record(item) for item in raw)
