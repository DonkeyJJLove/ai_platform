"""Concrete fail-closed providers for Cyber-Lion CI live admission.

This module is intentionally capability-reduced. It exposes only:
- exact read-only PR bootstrap lookup,
- exact read-only authority-lineage lookup,
- signature verification.

All control-plane configuration comes from trusted runtime environment. Credentials are
referenced by environment-variable name and are never accepted in provider call arguments,
URLs, response payloads, or persistent storage.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import base64
import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Final

PROVIDER_VERSION: Final = "1.0.0"
_BOOTSTRAP_PATH: Final = "/v1/pr-authority-bootstrap"
_AUTHORITY_PATH: Final = "/v1/authority-lineage"
_VERIFY_PATH: Final = "/v1/verify-signature"
_MAX_RESPONSE_BYTES: Final = 1024 * 1024
_MAX_RECORDS: Final = 16
_TIMEOUT_SECONDS: Final = 10
_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_RUN_ID_RE: Final = re.compile(r"^[1-9][0-9]{0,19}$")
_ATTEMPT_RE: Final = re.compile(r"^[1-9][0-9]{0,9}$")

_BOOTSTRAP_RESPONSE_FIELDS: Final = frozenset({"provider_version", "records"})
_VERIFY_RESPONSE_FIELDS: Final = frozenset({"provider_version", "verified"})


class CILiveAdmissionProviderError(RuntimeError):
    """Raised when trusted provider execution cannot be proven safe and canonical."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Reject every redirect so credentials never migrate to another origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise CILiveAdmissionProviderError("trusted control-plane redirect denied")


def _required_env(name: str, *, limit: int = 4096) -> str:
    value = os.environ.get(name)
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise CILiveAdmissionProviderError("trusted provider configuration is invalid")
    return value


def _runtime_config() -> tuple[str, str, str]:
    configured_version = _required_env("CYBER_LION_PROVIDER_VERSION", limit=64)
    if configured_version != PROVIDER_VERSION:
        raise CILiveAdmissionProviderError("trusted provider version mismatch")

    trusted_base_sha = _required_env("CYBER_LION_TRUSTED_BASE_SHA", limit=40)
    if not _SHA_RE.fullmatch(trusted_base_sha):
        raise CILiveAdmissionProviderError("trusted base SHA is invalid")

    origin = _required_env("CYBER_LION_CONTROL_PLANE_ORIGIN", limit=2048)
    parsed = urllib.parse.urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise CILiveAdmissionProviderError("trusted control-plane origin is invalid")
    canonical_origin = f"https://{parsed.netloc}"

    credential_env = _required_env("CYBER_LION_CONTROL_PLANE_CREDENTIAL_ENV", limit=256)
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,255}", credential_env):
        raise CILiveAdmissionProviderError("credential environment reference is invalid")
    credential = _required_env(credential_env, limit=16384)

    return canonical_origin, credential, trusted_base_sha


def _execution_epoch() -> str | None:
    """Bind production replay to the externally supplied GitHub Actions run epoch.

    Unit fixtures that are not running in Actions remain unbound and therefore do not
    share production replay state across calls.
    """
    run_id = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    if run_id is None and attempt is None:
        return None
    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
        raise CILiveAdmissionProviderError("trusted workflow run id is invalid")
    if not isinstance(attempt, str) or not _ATTEMPT_RE.fullmatch(attempt):
        raise CILiveAdmissionProviderError("trusted workflow run attempt is invalid")
    return f"{run_id}:{attempt}"


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _read_json_response(response) -> Mapping[str, object]:  # noqa: ANN001
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise CILiveAdmissionProviderError(
                "trusted control-plane response is invalid"
            ) from exc
        if declared < 0 or declared > _MAX_RESPONSE_BYTES:
            raise CILiveAdmissionProviderError(
                "trusted control-plane response is too large"
            )

    raw = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise CILiveAdmissionProviderError(
            "trusted control-plane response is too large"
        )
    status = getattr(response, "status", None)
    if status != 200:
        raise CILiveAdmissionProviderError(
            "trusted control-plane request failed"
        )
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise CILiveAdmissionProviderError(
            "trusted control-plane response is invalid"
        ) from exc
    if not isinstance(decoded, Mapping):
        raise CILiveAdmissionProviderError(
            "trusted control-plane response is invalid"
        )
    return decoded


def _get_json(*, path: str, payload: Mapping[str, object]) -> Mapping[str, object]:
    origin, credential, trusted_base_sha = _runtime_config()
    if path not in {_BOOTSTRAP_PATH, _AUTHORITY_PATH}:
        raise CILiveAdmissionProviderError("read provider endpoint is not allowed")
    query = urllib.parse.urlencode(
        [(key, str(value)) for key, value in payload.items()], doseq=False, safe=""
    )
    request = urllib.request.Request(
        url=f"{origin}{path}?{query}",
        data=None,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {credential}",
            "X-Cyber-Lion-Provider-Version": PROVIDER_VERSION,
            "X-Cyber-Lion-Trusted-Base-SHA": trusted_base_sha,
        },
        method="GET",
    )
    try:
        with urllib.request.build_opener(_NoRedirect()).open(
            request, timeout=_TIMEOUT_SECONDS
        ) as response:
            return _read_json_response(response)
    except CILiveAdmissionProviderError:
        raise
    except Exception as exc:
        raise CILiveAdmissionProviderError(
            "trusted control-plane request failed"
        ) from exc


@dataclass(frozen=True)
class SignatureVerificationAdmission:
    request_digest: str
    origin: str
    trusted_base_sha: str
    payload_digest: str
    execution_epoch: str | None


@dataclass(frozen=True)
class SignatureVerificationObservation:
    request_digest: str
    response_digest: str
    verified: bool


class SignatureVerificationNetworkBoundary:
    """Closed-world POST boundary for one signature-verification request.

    The boundary accepts no caller-selected URL/method/provider, rechecks trusted
    runtime configuration immediately before POST, and in production GitHub Actions
    binds replay to the externally supplied run-id/attempt. Exact repeated requests in
    one run return the already-observed result without a second network effect.
    """

    _lock = threading.RLock()
    _observed: dict[tuple[str, str], SignatureVerificationObservation] = {}

    @staticmethod
    def _payload(payload: bytes, signature: str, key_id: str, algorithm: str) -> dict[str, object]:
        if not isinstance(payload, bytes):
            raise CILiveAdmissionProviderError("signature payload type is invalid")
        for value, name, limit in (
            (signature, "signature", 32768),
            (key_id, "key id", 1024),
            (algorithm, "algorithm", 128),
        ):
            if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
                raise CILiveAdmissionProviderError(f"{name} is invalid")
        return {
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "signature": signature,
            "key_id": key_id,
            "algorithm": algorithm,
        }

    @staticmethod
    def _admit(body: Mapping[str, object]) -> SignatureVerificationAdmission:
        origin, _credential, trusted_base_sha = _runtime_config()
        execution_epoch = _execution_epoch()
        body_bytes = _json_bytes(body)
        payload_digest = sha256(body_bytes).hexdigest()
        request_digest = sha256(
            b"LION/CI-SIGNATURE-VERIFY-NETWORK/1\0"
            + origin.encode("utf-8")
            + b"\0"
            + trusted_base_sha.encode("ascii")
            + b"\0"
            + (execution_epoch or "UNBOUND").encode("ascii")
            + b"\0"
            + body_bytes
        ).hexdigest()
        return SignatureVerificationAdmission(
            request_digest=request_digest,
            origin=origin,
            trusted_base_sha=trusted_base_sha,
            payload_digest=payload_digest,
            execution_epoch=execution_epoch,
        )

    @classmethod
    def verify(cls, payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
        body = cls._payload(payload, signature, key_id, algorithm)
        admission = cls._admit(body)
        cache_key = (
            admission.execution_epoch or "",
            admission.request_digest,
        )
        with cls._lock:
            if admission.execution_epoch is not None:
                cached = cls._observed.get(cache_key)
                if cached is not None:
                    return cached.verified

            # Effect-time currentness: authoritative process configuration must still
            # equal admission immediately before network I/O.
            origin, credential, trusted_base_sha = _runtime_config()
            if (origin, trusted_base_sha) != (admission.origin, admission.trusted_base_sha):
                raise CILiveAdmissionProviderError(
                    "trusted verification configuration changed before effect"
                )
            if _execution_epoch() != admission.execution_epoch:
                raise CILiveAdmissionProviderError(
                    "trusted verification execution epoch changed before effect"
                )

            body_bytes = _json_bytes(body)
            if sha256(body_bytes).hexdigest() != admission.payload_digest:
                raise CILiveAdmissionProviderError("verification payload substitution denied")

            request = urllib.request.Request(
                url=origin + _VERIFY_PATH,
                data=body_bytes,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {credential}",
                    "Content-Type": "application/json",
                    "X-Cyber-Lion-Provider-Version": PROVIDER_VERSION,
                    "X-Cyber-Lion-Trusted-Base-SHA": trusted_base_sha,
                    "X-Cyber-Lion-Request-Digest": admission.request_digest,
                },
                method="POST",
            )
            try:
                with urllib.request.build_opener(_NoRedirect()).open(
                    request, timeout=_TIMEOUT_SECONDS
                ) as response:
                    decoded = _read_json_response(response)
            except CILiveAdmissionProviderError:
                raise
            except Exception as exc:
                raise CILiveAdmissionProviderError(
                    "trusted signature verification request failed"
                ) from exc

            if frozenset(decoded.keys()) != _VERIFY_RESPONSE_FIELDS:
                raise CILiveAdmissionProviderError("trusted response envelope is not canonical")
            if decoded["provider_version"] != PROVIDER_VERSION:
                raise CILiveAdmissionProviderError("trusted response provider version mismatch")
            verified = decoded["verified"]
            if type(verified) is not bool:
                raise CILiveAdmissionProviderError("trusted verifier result is invalid")

            observation = SignatureVerificationObservation(
                request_digest=admission.request_digest,
                response_digest=sha256(_json_bytes(decoded)).hexdigest(),
                verified=verified,
            )
            if admission.execution_epoch is not None:
                cls._observed[cache_key] = observation
            return observation.verified


def _records_response(response: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    if frozenset(response.keys()) != _BOOTSTRAP_RESPONSE_FIELDS:
        raise CILiveAdmissionProviderError("trusted response envelope is not canonical")
    if response["provider_version"] != PROVIDER_VERSION:
        raise CILiveAdmissionProviderError("trusted response provider version mismatch")
    records = response["records"]
    if not isinstance(records, list) or len(records) > _MAX_RECORDS:
        raise CILiveAdmissionProviderError("trusted response records are invalid")
    if any(not isinstance(record, Mapping) for record in records):
        raise CILiveAdmissionProviderError("trusted response records are invalid")
    return tuple(records)


def bootstrap_lookup_exact(
    *,
    repository: str,
    pr_number: int,
    base_sha: str,
    head_sha: str,
    merge_method: str,
) -> tuple[Mapping[str, object], ...]:
    """Read exact immutable PR bootstrap candidates from the trusted control plane."""
    response = _get_json(
        path=_BOOTSTRAP_PATH,
        payload={
            "repository": repository,
            "pr_number": pr_number,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "merge_method": merge_method,
        },
    )
    return _records_response(response)


def authority_lookup_exact(
    *,
    repository: str,
    pr_number: int,
    base_sha: str,
    head_sha: str,
    mission_id: str,
    grant_id: str,
) -> tuple[Mapping[str, object], ...]:
    """Read exact immutable authority-lineage candidates from the trusted control plane."""
    response = _get_json(
        path=_AUTHORITY_PATH,
        payload={
            "repository": repository,
            "pr_number": pr_number,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "mission_id": mission_id,
            "grant_id": grant_id,
        },
    )
    return _records_response(response)


def verify_signature(
    payload: bytes,
    signature: str,
    key_id: str,
    algorithm: str,
) -> bool:
    """Verify one authority signature through the fixed trusted verifier boundary."""
    return SignatureVerificationNetworkBoundary.verify(
        payload, signature, key_id, algorithm
    )
