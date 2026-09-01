"""Read-only network providers for LAB-DEBIAN clock and consumption state."""
from __future__ import annotations

from collections.abc import Mapping
import json
import os
import re
import urllib.parse
import urllib.request

from .ci_live_admission_providers import (
    CILiveAdmissionProviderError,
    PROVIDER_VERSION,
    _NoRedirect,
)

_CLOCK_PATH = "/v1/trusted-clock"
_CONSUMPTION_PATH = "/v1/merge-authority-consumption"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _required(name: str, limit: int = 4096) -> str:
    value = os.environ.get(name)
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise CILiveAdmissionProviderError("trusted runtime configuration is invalid")
    return value


def _config() -> tuple[str, str, str]:
    if _required("CYBER_LION_PROVIDER_VERSION", 64) != PROVIDER_VERSION:
        raise CILiveAdmissionProviderError("trusted provider version mismatch")
    trusted_base = _required("CYBER_LION_TRUSTED_BASE_SHA", 40)
    if not _SHA_RE.fullmatch(trusted_base):
        raise CILiveAdmissionProviderError("trusted base SHA is invalid")
    origin_raw = _required("CYBER_LION_CONTROL_PLANE_ORIGIN", 2048)
    parsed = urllib.parse.urlsplit(origin_raw)
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
    credential_name = _required("CYBER_LION_CONTROL_PLANE_CREDENTIAL_ENV", 256)
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,255}", credential_name):
        raise CILiveAdmissionProviderError("credential environment reference is invalid")
    credential = _required(credential_name, 16384)
    return f"https://{parsed.netloc}", credential, trusted_base


def _get(
    path: str, query: list[tuple[str, object]] | None = None
) -> Mapping[str, object]:
    origin, credential, trusted_base = _config()
    suffix = "" if not query else "?" + urllib.parse.urlencode(query, doseq=False, safe="")
    request = urllib.request.Request(
        origin + path + suffix,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {credential}",
            "X-Cyber-Lion-Provider-Version": PROVIDER_VERSION,
            "X-Cyber-Lion-Trusted-Base-SHA": trusted_base,
        },
        method="GET",
    )
    try:
        with urllib.request.build_opener(_NoRedirect()).open(
            request, timeout=10
        ) as response:
            if getattr(response, "status", None) != 200:
                raise CILiveAdmissionProviderError("trusted runtime request failed")
            raw = response.read(1024 * 1024 + 1)
    except CILiveAdmissionProviderError:
        raise
    except Exception as exc:
        raise CILiveAdmissionProviderError("trusted runtime request failed") from exc
    if len(raw) > 1024 * 1024:
        raise CILiveAdmissionProviderError("trusted runtime response too large")
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise CILiveAdmissionProviderError("trusted runtime response invalid") from exc
    if not isinstance(decoded, Mapping) or decoded.get("provider_version") != PROVIDER_VERSION:
        raise CILiveAdmissionProviderError("trusted runtime response invalid")
    return decoded


def trusted_clock_observation() -> Mapping[str, object]:
    decoded = _get(_CLOCK_PATH)
    if set(decoded) != {
        "provider_version",
        "observed_at",
        "trusted_clock_source_id",
    }:
        raise CILiveAdmissionProviderError("trusted clock response is not canonical")
    return {
        "observed_at": decoded["observed_at"],
        "trusted_clock_source_id": decoded["trusted_clock_source_id"],
    }


def observe_consumption_exact(
    *,
    repository: str,
    pr_number: int,
    base_sha: str,
    head_sha: str,
    grant_id: str,
    grant_digest: str,
    lineage_digest: str,
    epoch: int,
    merge_method: str,
) -> Mapping[str, object]:
    decoded = _get(
        _CONSUMPTION_PATH,
        [
            ("repository", repository),
            ("pr_number", pr_number),
            ("base_sha", base_sha),
            ("head_sha", head_sha),
            ("grant_id", grant_id),
            ("grant_digest", grant_digest),
            ("lineage_digest", lineage_digest),
            ("epoch", epoch),
            ("merge_method", merge_method),
        ],
    )
    if set(decoded) != {
        "provider_version",
        "state",
        "state_version",
        "provenance_id",
    }:
        raise CILiveAdmissionProviderError("consumption response is not canonical")
    return {
        "state": decoded["state"],
        "state_version": decoded["state_version"],
        "provenance_id": decoded["provenance_id"],
    }
