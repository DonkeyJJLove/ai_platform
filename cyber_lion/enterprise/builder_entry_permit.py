"""Fail-closed non-effectful builder-entry permit issuer."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import ipaddress
import json
import os
import re
from typing import Any, Protocol
import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.contracts.builder_entry_permit import (
    BUILDER_CAPABILITY_CLASS,
    SCHEMA_VERSION,
    BuilderEntryPermit,
    TrustedBuilderSubject,
    compute_builder_entry_replay_digest,
)
from cyber_lion.contracts.build_authorization_consumption import BuildAuthorizationConsumptionPermit
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.enterprise.candidate_build_authorization import (
    LiveAdmittedResourceAuthority,
    LiveResourceAuthorityAdmission,
)


class BuilderEntryPermitError(RuntimeError):
    pass


_EFFECT_METHODS = frozenset({"execute", "write", "push", "merge", "deploy", "release", "create_branch", "create_pr", "run_test", "build_candidate", "consume_candidate", "start_builder", "issue_grant"})
_SCOPE_DIGEST_DOMAIN = b"LION/E004-BUILDER-SCOPE-LOOKUP/1\0"
_CLIENT_CONFIG_DOMAIN = b"LION/E004-TRUSTED-CONTROL-PLANE-BUILDER-CLIENT-CONFIG/1\0"
_CLIENT_CREDENTIAL_DOMAIN = b"LION/E004-TRUSTED-CONTROL-PLANE-BUILDER-CLIENT-CREDENTIAL/1\0"
PINNED_BUILDER_BACKEND_IDENTITY = "lion.trusted-control-plane.http-read/v1"
PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST = sha256(b"LION/E004-TRUSTED-CONTROL-PLANE-SERVICE-BUILDER-SOURCE/1").hexdigest()
_PROVIDER_VERSION = "1.0.0"
_BUILDER_PATH = "/v1/builder-subject"
_MAX_RESPONSE = 256 * 1024
_ENV_REF_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,255}$")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _scope_digest(scope: tuple[str, ...], *, label: str) -> str:
    if type(scope) is not tuple or not scope:
        raise BuilderEntryPermitError(f"{label} invalid")
    return sha256(_SCOPE_DIGEST_DOMAIN + label.encode("ascii") + b"\0" + _canonical_json(list(scope))).hexdigest()


def _utc(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise BuilderEntryPermitError(f"{name} invalid") from exc
    if parsed.tzinfo is None:
        raise BuilderEntryPermitError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _sealed_subject(value: object) -> TrustedBuilderSubject:
    if type(value) is not TrustedBuilderSubject:
        raise BuilderEntryPermitError("trusted builder subject type invalid")
    try:
        value.validate()
    except Exception as exc:
        raise BuilderEntryPermitError("trusted builder subject invalid") from exc
    if not value.subject_digest or value.subject_digest != value.compute_digest():
        raise BuilderEntryPermitError("trusted builder subject must be sealed")
    return value


def _wire_scope(value: object, *, name: str) -> tuple[str, ...]:
    if type(value) is not list or not value or any(type(item) is not str or not item for item in value):
        raise BuilderEntryPermitError(f"{name} wire value invalid")
    if len(set(value)) != len(value):
        raise BuilderEntryPermitError(f"{name} wire value invalid")
    return tuple(value)


def _subject_from_record(record: Mapping[str, object], *, expected_lookup: Mapping[str, object]) -> TrustedBuilderSubject:
    if not isinstance(record, Mapping) or frozenset(record.keys()) != frozenset({"record_kind", "lookup_key", "subject"}):
        raise BuilderEntryPermitError("builder subject record is not canonical")
    if record.get("record_kind") != "builder-subject":
        raise BuilderEntryPermitError("builder subject record kind invalid")
    lookup = record.get("lookup_key")
    if not isinstance(lookup, Mapping) or frozenset(lookup.keys()) != frozenset(expected_lookup.keys()) or any(lookup[k] != expected_lookup[k] for k in expected_lookup):
        raise BuilderEntryPermitError("builder subject lookup binding mismatch")
    raw = record.get("subject")
    if not isinstance(raw, Mapping) or frozenset(raw.keys()) != frozenset(TrustedBuilderSubject.__dataclass_fields__.keys()):
        raise BuilderEntryPermitError("builder subject payload invalid")
    decoded = dict(raw)
    decoded["candidate_scope"] = _wire_scope(decoded.get("candidate_scope"), name="candidate_scope")
    decoded["resource_scope"] = _wire_scope(decoded.get("resource_scope"), name="resource_scope")
    try:
        return _sealed_subject(TrustedBuilderSubject(**decoded))
    except (TypeError, ValueError) as exc:
        raise BuilderEntryPermitError("builder subject reconstruction failed") from exc


def _required_env(name: str, *, limit: int) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        raise BuilderEntryPermitError("trusted control-plane client configuration unavailable")
    return value


def _is_loopback_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _credential_digest(credential: str) -> str:
    if not isinstance(credential, str) or not credential or not credential.isascii():
        raise BuilderEntryPermitError("trusted control-plane credential invalid")
    return sha256(_CLIENT_CREDENTIAL_DOMAIN + credential.encode("ascii")).hexdigest()


def _observe_process_configuration() -> tuple[str, str, str, str, str]:
    """Observe and validate process configuration; values are request-local only."""
    provider_version = _required_env("CYBER_LION_CP_PROVIDER_VERSION", limit=64)
    if provider_version != _PROVIDER_VERSION:
        raise BuilderEntryPermitError("trusted control-plane provider version mismatch")
    endpoint = _required_env("CYBER_LION_CP_ENDPOINT", limit=2048).rstrip("/")
    parsed = urllib.parse.urlsplit(endpoint)
    if not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise BuilderEntryPermitError("trusted control-plane endpoint invalid")
    if parsed.scheme != "https":
        local_mode = os.environ.get("CYBER_LION_CP_ALLOW_LOCAL_HTTP") == "1"
        if parsed.scheme != "http" or not _is_loopback_host(parsed.hostname) or not local_mode:
            raise BuilderEntryPermitError("trusted control-plane endpoint must use https")
    credential_env = _required_env("CYBER_LION_CP_CREDENTIAL_ENV", limit=256)
    if not _ENV_REF_RE.fullmatch(credential_env):
        raise BuilderEntryPermitError("trusted control-plane credential reference invalid")
    credential = _required_env(credential_env, limit=16384)
    if not credential.isascii():
        raise BuilderEntryPermitError("trusted control-plane credential invalid")
    payload = {
        "provider_version": provider_version,
        "endpoint": endpoint,
        "credential_env": credential_env,
        "credential_digest": _credential_digest(credential),
    }
    digest = sha256(_CLIENT_CONFIG_DOMAIN + _canonical_json(payload)).hexdigest()
    return provider_version, endpoint, credential_env, credential, digest


def _make_configuration_anchor_registry():
    """Return one-way register/verify closures; there is no reseal operation."""
    registered: dict[int, tuple[object, str]] = {}

    def register_once(client: object, digest: str) -> None:
        key = id(client)
        if key in registered:
            raise BuilderEntryPermitError("trusted control-plane client configuration already registered")
        registered[key] = (client, digest)

    def verify_registered(client: object, digest: str) -> None:
        record = registered.get(id(client))
        if record is None or record[0] is not client or not hmac.compare_digest(record[1], digest):
            raise BuilderEntryPermitError("trusted control-plane client configuration anchor mismatch")

    return register_once, verify_registered


_register_initial_client_configuration, _verify_initial_client_configuration = _make_configuration_anchor_registry()
del _make_configuration_anchor_registry


class TrustedRepositoryBaselineSource(Protocol):
    def current(self, repository: str) -> TrustedRepositoryBaseline: ...


class F005StateSource(Protocol):
    def current(self) -> Mapping[str, Any]: ...


class BuilderEntryReplayGuard(Protocol):
    def consume(self, replay_digest: str, *, consumed_at: str) -> bool: ...


class PersistentBuilderEntryReplayGuard:
    DOMAIN = "candidate-builder-entry-consumption"

    def __init__(self, store: object):
        if not callable(getattr(store, "consume_replay", None)):
            raise BuilderEntryPermitError("persistent replay store unavailable")
        self._store = store

    def consume(self, replay_digest: str, *, consumed_at: str) -> bool:
        return self._store.consume_replay(self.DOMAIN, replay_digest, consumed_at)


class TrustedBuilderSubjectSource(ABC):
    source_kind = "untrusted-abstract-source"

    @abstractmethod
    def _lookup_exact(self, **kwargs: object) -> tuple[TrustedBuilderSubject, ...]:
        raise NotImplementedError


class TrustedControlPlaneBuilderClient:
    """Pinned authenticated HTTP reader anchored to one process-config observation."""

    __slots__ = ("_configuration_digest", "_sealed_configuration")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("TrustedControlPlaneBuilderClient is final")

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed_configuration", False) and name in {"_configuration_digest", "_sealed_configuration"}:
            raise BuilderEntryPermitError("trusted control-plane client configuration is immutable")
        object.__setattr__(self, name, value)

    def __init__(self) -> None:
        if type(self) is not TrustedControlPlaneBuilderClient:
            raise BuilderEntryPermitError("exact control-plane builder client required")
        object.__setattr__(self, "_sealed_configuration", False)
        _provider_version, _endpoint, _credential_env, _credential, digest = _observe_process_configuration()
        object.__setattr__(self, "_configuration_digest", digest)
        _register_initial_client_configuration(self, digest)
        object.__setattr__(self, "_sealed_configuration", True)
        self.verify_origin()

    def _validated_process_configuration(self) -> tuple[str, str, str, str]:
        if type(self) is not TrustedControlPlaneBuilderClient:
            raise BuilderEntryPermitError("exact control-plane builder client required")
        if getattr(self, "_sealed_configuration", None) is not True:
            raise BuilderEntryPermitError("trusted control-plane client configuration not sealed")
        digest = getattr(self, "_configuration_digest", None)
        if not isinstance(digest, str) or len(digest) != 64:
            raise BuilderEntryPermitError("trusted control-plane client configuration seal missing")
        _verify_initial_client_configuration(self, digest)
        provider_version, endpoint, credential_env, credential, observed_digest = _observe_process_configuration()
        if not hmac.compare_digest(digest, observed_digest):
            raise BuilderEntryPermitError("trusted control-plane process configuration drift")
        return provider_version, endpoint, credential_env, credential

    def verify_origin(self) -> None:
        self._validated_process_configuration()

    def lookup_builder_subject_exact(self, *, binding: Mapping[str, str]) -> tuple[Mapping[str, object], ...]:
        provider_version, endpoint, _credential_env, credential = self._validated_process_configuration()
        expected = frozenset({"repository", "builder_subject_id", "builder_instance_id", "candidate_scope_digest", "resource_scope_digest", "capability_class"})
        if not isinstance(binding, Mapping) or frozenset(binding.keys()) != expected or any(not isinstance(v, str) or not v for v in binding.values()):
            raise BuilderEntryPermitError("builder service lookup binding invalid")
        query = urllib.parse.urlencode([(k, binding[k]) for k in sorted(binding)])
        request = urllib.request.Request(
            endpoint + _BUILDER_PATH + "?" + query,
            headers={"Authorization": "Bearer " + credential, "Accept": "application/json"},
            method="GET",
        )
        provider_version_now, endpoint_now, _credential_env_now, credential_now = self._validated_process_configuration()
        if (provider_version_now, endpoint_now, credential_now) != (provider_version, endpoint, credential):
            raise BuilderEntryPermitError("trusted control-plane process configuration changed during request construction")
        opener = urllib.request.build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=5) as response:
                if getattr(response, "status", None) != 200:
                    raise BuilderEntryPermitError("trusted control-plane service denied request")
                raw = response.read(_MAX_RESPONSE + 1)
        except BuilderEntryPermitError:
            raise
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            raise BuilderEntryPermitError("trusted control-plane service unavailable") from exc
        if len(raw) > _MAX_RESPONSE:
            raise BuilderEntryPermitError("trusted control-plane response too large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BuilderEntryPermitError("trusted control-plane response malformed") from exc
        if not isinstance(payload, Mapping) or frozenset(payload.keys()) != frozenset({"provider_version", "records"}):
            raise BuilderEntryPermitError("trusted control-plane response noncanonical")
        if payload.get("provider_version") != provider_version:
            raise BuilderEntryPermitError("trusted control-plane provider version mismatch")
        records = payload.get("records")
        if type(records) is not list or len(records) > 16:
            raise BuilderEntryPermitError("trusted control-plane records invalid")
        return tuple(records)


class PinnedBuilderControlPlaneBackend:
    backend_identity = PINNED_BUILDER_BACKEND_IDENTITY
    __slots__ = ("_client",)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("PinnedBuilderControlPlaneBackend is final")

    def __init__(self) -> None:
        if type(self) is not PinnedBuilderControlPlaneBackend:
            raise BuilderEntryPermitError("exact trusted builder backend required")
        self._client = TrustedControlPlaneBuilderClient()
        self.verify_origin()

    def verify_origin(self) -> None:
        if type(self) is not PinnedBuilderControlPlaneBackend or type(self).backend_identity != PINNED_BUILDER_BACKEND_IDENTITY:
            raise BuilderEntryPermitError("trusted builder backend identity mismatch")
        if type(self._client) is not TrustedControlPlaneBuilderClient:
            raise BuilderEntryPermitError("trusted builder client type mismatch")
        self._client.verify_origin()

    def resolve_exact(self, *, builder_subject_id: str, builder_instance_id: str, repository: str, candidate_scope: tuple[str, ...], resource_scope: tuple[str, ...]) -> TrustedBuilderSubject:
        self.verify_origin()
        binding = {
            "repository": repository,
            "builder_subject_id": builder_subject_id,
            "builder_instance_id": builder_instance_id,
            "candidate_scope_digest": _scope_digest(candidate_scope, label="candidate_scope"),
            "resource_scope_digest": _scope_digest(resource_scope, label="resource_scope"),
            "capability_class": BUILDER_CAPABILITY_CLASS,
        }
        records = self._client.lookup_builder_subject_exact(binding=binding)
        if len(records) == 0:
            raise BuilderEntryPermitError("trusted builder subject not found")
        if len(records) > 1:
            raise BuilderEntryPermitError("trusted builder subject lookup ambiguous")
        subject = _subject_from_record(records[0], expected_lookup=binding)
        expected = (builder_subject_id, builder_instance_id, repository, candidate_scope, resource_scope, BUILDER_CAPABILITY_CLASS, "ADMITTED", "trusted-control-plane")
        actual = (subject.builder_subject_id, subject.builder_instance_id, subject.repository, subject.candidate_scope, subject.resource_scope, subject.capability_class, subject.state, subject.source_kind)
        if actual != expected:
            raise BuilderEntryPermitError("trusted builder subject request binding mismatch")
        return subject


class PinnedTrustedBuilderSubjectSource:
    source_kind = "trusted-control-plane"
    source_implementation_digest = PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST
    __slots__ = ("_backend",)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("PinnedTrustedBuilderSubjectSource is final")

    def __init__(self) -> None:
        if type(self) is not PinnedTrustedBuilderSubjectSource:
            raise BuilderEntryPermitError("exact pinned builder source required")
        self._backend = PinnedBuilderControlPlaneBackend()
        self.verify_origin()

    @property
    def backend(self) -> PinnedBuilderControlPlaneBackend:
        return self._backend

    def verify_origin(self) -> None:
        if type(self) is not PinnedTrustedBuilderSubjectSource or type(self).source_kind != "trusted-control-plane" or type(self).source_implementation_digest != PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST:
            raise BuilderEntryPermitError("builder source origin mismatch")
        if type(self._backend) is not PinnedBuilderControlPlaneBackend:
            raise BuilderEntryPermitError("builder source backend type mismatch")
        self._backend.verify_origin()

    def resolve_exact(self, **kwargs: object) -> TrustedBuilderSubject:
        self.verify_origin()
        return self._backend.resolve_exact(**kwargs)


class BuilderEntryPermitEngine:
    """Issue one entry permit; never consume it or start a builder."""

    def __init__(self, *, live_authority: LiveResourceAuthorityAdmission, baseline_source: TrustedRepositoryBaselineSource, f005_state_source: F005StateSource, builder_source: PinnedTrustedBuilderSubjectSource, replay_guard: BuilderEntryReplayGuard):
        if type(live_authority) is not LiveResourceAuthorityAdmission:
            raise BuilderEntryPermitError("live authority admission required")
        if type(builder_source) is not PinnedTrustedBuilderSubjectSource or type(builder_source.backend) is not PinnedBuilderControlPlaneBackend:
            raise BuilderEntryPermitError("exact pinned trusted builder source required")
        builder_source.verify_origin()
        for obj, method in ((baseline_source, "current"), (f005_state_source, "current"), (replay_guard, "consume")):
            if not callable(getattr(obj, method, None)):
                raise BuilderEntryPermitError("builder entry dependency unavailable")
        self._live, self._baseline, self._f005, self._builders, self._replay = live_authority, baseline_source, f005_state_source, builder_source, replay_guard

    @staticmethod
    def _permit(value: object) -> BuildAuthorizationConsumptionPermit:
        if type(value) is not BuildAuthorizationConsumptionPermit:
            raise BuilderEntryPermitError("exact consumption permit required")
        try:
            value.validate()
        except Exception as exc:
            raise BuilderEntryPermitError("consumption permit invalid") from exc
        if not value.consumption_permit_digest or value.consumption_permit_digest != value.compute_digest() or value.consumption_replay_digest != value.compute_consumption_replay_digest():
            raise BuilderEntryPermitError("consumption permit must be sealed and source-bound")
        if value.state != "CONSUMPTION_PERMIT_ISSUED" or value.action != "BUILD_CANDIDATE":
            raise BuilderEntryPermitError("source permit state/action invalid")
        return value

    @staticmethod
    def _live_receipt(value: object) -> LiveAdmittedResourceAuthority:
        if type(value) is not LiveAdmittedResourceAuthority:
            raise BuilderEntryPermitError("exact live authority receipt required")
        try:
            value.validate()
        except Exception as exc:
            raise BuilderEntryPermitError("live authority receipt invalid") from exc
        return value

    @staticmethod
    def _f005_ok(value: Mapping[str, Any]) -> None:
        if not isinstance(value, Mapping) or value.get("state") != "QUARANTINED" or value.get("effect_authority") != "DENY":
            raise BuilderEntryPermitError("F005 quarantine invariant failed")

    @staticmethod
    def _trusted_subject(value: object, *, builder_subject_id: str, builder_instance_id: str, repository: str, candidate_scope: tuple[str, ...], resource_scope: tuple[str, ...]) -> TrustedBuilderSubject:
        subject = _sealed_subject(value)
        expected = (builder_subject_id, builder_instance_id, repository, candidate_scope, resource_scope, BUILDER_CAPABILITY_CLASS, "ADMITTED", "trusted-control-plane")
        actual = (subject.builder_subject_id, subject.builder_instance_id, subject.repository, subject.candidate_scope, subject.resource_scope, subject.capability_class, subject.state, subject.source_kind)
        if actual != expected:
            raise BuilderEntryPermitError("trusted builder subject request binding mismatch")
        return subject

    def issue_permit(self, *, source_permit: BuildAuthorizationConsumptionPermit, admitted_authority: LiveAdmittedResourceAuthority, builder_subject_id: str, builder_instance_id: str, trusted_now: datetime) -> BuilderEntryPermit:
        permit = self._permit(source_permit)
        admitted = self._live_receipt(admitted_authority)
        if not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None:
            raise BuilderEntryPermitError("trusted_now must be timezone-aware")
        now = trusted_now.astimezone(timezone.utc)
        if now < _utc(permit.authorization_valid_from, "authorization valid_from") or now >= _utc(permit.authorization_expires_at, "authorization expires_at"):
            raise BuilderEntryPermitError("source authorization outside validity window")
        current = self._baseline.current(permit.repository)
        if type(current) is not TrustedRepositoryBaseline:
            raise BuilderEntryPermitError("trusted baseline type invalid")
        current.validate()
        if (current.repository, current.master_sha, current.master_tree_sha) != (permit.repository, permit.baseline_master_sha, permit.baseline_master_tree_sha):
            raise BuilderEntryPermitError("builder-entry baseline stale")
        try:
            authority = self._live.revalidate(admitted, now=now)
        except Exception as exc:
            raise BuilderEntryPermitError("current authority revalidation failed") from exc
        if type(authority) is not LiveAdmittedResourceAuthority:
            raise BuilderEntryPermitError("revalidated authority type invalid")
        authority.validate()
        expected_authority = (permit.repository, permit.grant_id, permit.leaf_grant_digest, permit.authority_lineage_digest, permit.authority_provenance_id, permit.authority_epoch, permit.authority_state_version, permit.root_grant_id, permit.root_grant_digest, permit.current_authority_digest, permit.resource_scope, "BUILD_CANDIDATE")
        actual_authority = (authority.repository, authority.grant_id, authority.leaf_grant_digest, authority.lineage_digest, authority.provenance_id, authority.epoch, authority.epoch_state_version, authority.root_grant_id, authority.root_grant_digest, authority.digest(), authority.resource_scope, authority.action)
        if actual_authority != expected_authority:
            raise BuilderEntryPermitError("source permit/current authority mismatch")
        self._f005_ok(self._f005.current())
        self._builders.verify_origin()
        subject = self._trusted_subject(
            self._builders.resolve_exact(builder_subject_id=builder_subject_id, builder_instance_id=builder_instance_id, repository=permit.repository, candidate_scope=permit.candidate_scope, resource_scope=permit.resource_scope),
            builder_subject_id=builder_subject_id, builder_instance_id=builder_instance_id, repository=permit.repository, candidate_scope=permit.candidate_scope, resource_scope=permit.resource_scope,
        )
        if now < _utc(subject.valid_from, "builder valid_from") or now >= _utc(subject.expires_at, "builder expires_at"):
            raise BuilderEntryPermitError("builder subject outside validity window")
        kwargs = dict(
            source_consumption_permit_id=permit.consumption_permit_id,
            source_consumption_permit_digest=permit.consumption_permit_digest,
            source_consumption_replay_digest=permit.consumption_replay_digest,
            repository=permit.repository,
            baseline_master_sha=permit.baseline_master_sha,
            baseline_master_tree_sha=permit.baseline_master_tree_sha,
            current_baseline_digest=current.digest(),
            action="BUILD_CANDIDATE",
            candidate_scope=permit.candidate_scope,
            resource_scope=permit.resource_scope,
            authority_epoch=permit.authority_epoch,
            authority_state_version=permit.authority_state_version,
            root_grant_id=permit.root_grant_id,
            root_grant_digest=permit.root_grant_digest,
            current_authority_digest=authority.digest(),
            builder_subject_id=subject.builder_subject_id,
            builder_instance_id=subject.builder_instance_id,
            builder_capability_class=subject.capability_class,
            builder_identity_digest=subject.identity_digest,
            builder_implementation_digest=subject.implementation_digest,
            builder_attestation_digest=subject.attestation_digest,
        )
        replay = compute_builder_entry_replay_digest(**kwargs)
        checked_at = now.isoformat()
        if self._replay.consume(replay, consumed_at=checked_at) is not True:
            raise BuilderEntryPermitError("builder entry replay denied")
        return BuilderEntryPermit(schema_version=SCHEMA_VERSION, builder_entry_permit_id=f"bep:{replay}", checked_at=checked_at, builder_entry_replay_digest=replay, **kwargs).sealed()

    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHODS:
            if hasattr(cls, name):
                raise BuilderEntryPermitError(f"effect surface present: {name}")
