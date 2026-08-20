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
import base64
import json
import os
import re
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


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _request_json(
    *,
    path: str,
    method: str,
    payload: Mapping[str, object],
) -> Mapping[str, object]:
    origin, credential, trusted_base_sha = _runtime_config()
    if path not in {_BOOTSTRAP_PATH, _AUTHORITY_PATH, _VERIFY_PATH}:
        raise CILiveAdmissionProviderError("provider endpoint is not allowed")
    if method not in {"GET", "POST"}:
        raise CILiveAdmissionProviderError("provider method is not allowed")

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {credential}",
        "X-Cyber-Lion-Provider-Version": PROVIDER_VERSION,
        "X-Cyber-Lion-Trusted-Base-SHA": trusted_base_sha,
    }

    url = origin + path
    data: bytes | None = None
    if method == "GET":
        query = urllib.parse.urlencode(
            [(key, str(value)) for key, value in payload.items()],
            doseq=False,
            safe="",
        )
        url = f"{url}?{query}"
    else:
        headers["Content-Type"] = "application/json"
        data = _json_bytes(payload)

    request = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )
    opener = urllib.request.build_opener(_NoRedirect())

    try:
        with opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
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
    except CILiveAdmissionProviderError:
        raise
    except Exception as exc:
        raise CILiveAdmissionProviderError(
            "trusted control-plane request failed"
        ) from exc

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
    response = _request_json(
        path=_BOOTSTRAP_PATH,
        method="GET",
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
    response = _request_json(
        path=_AUTHORITY_PATH,
        method="GET",
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
    """Verify one authority signature through the trusted verifier service."""
    if not isinstance(payload, bytes):
        raise CILiveAdmissionProviderError("signature payload type is invalid")
    response = _request_json(
        path=_VERIFY_PATH,
        method="POST",
        payload={
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "signature": signature,
            "key_id": key_id,
            "algorithm": algorithm,
        },
    )
    if frozenset(response.keys()) != _VERIFY_RESPONSE_FIELDS:
        raise CILiveAdmissionProviderError("trusted response envelope is not canonical")
    if response["provider_version"] != PROVIDER_VERSION:
        raise CILiveAdmissionProviderError("trusted response provider version mismatch")
    verified = response["verified"]
    if type(verified) is not bool:
        raise CILiveAdmissionProviderError("trusted verifier result is invalid")
    return verified
