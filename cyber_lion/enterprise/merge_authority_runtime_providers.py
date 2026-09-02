"""Read-only network providers for LAB-DEBIAN clock and consumption state."""
from __future__ import annotations

from collections.abc import Mapping
import json
import os
import re
import urllib.parse
import urllib.request

from .authority_revocation import (
    AuthorityEpochState,
    observe_canonical_authority_epoch_state,
    register_canonical_authority_epoch_state,
)
from .ci_live_admission_providers import (
    CILiveAdmissionProviderError,
    PROVIDER_VERSION,
    _NoRedirect,
)
from .pr_authority_bootstrap import decode_pr_authority_bootstrap_record

_CLOCK_PATH = "/v1/trusted-clock"
_CONSUMPTION_PATH = "/v1/merge-authority-consumption"
_EPOCH_PATH = "/v1/authority-epoch-snapshot"
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


def bind_epoch_state_from_bootstrap_records(
    records: tuple[Mapping[str, object], ...],
) -> tuple[Mapping[str, object], ...]:
    """Bind the CI process-local epoch reader to an independent persistent LAB snapshot.

    Cardinality remains the bootstrap provider's evidence. A zero/many bootstrap result is
    returned unchanged so the observer can report it literally. Only an exact bootstrap
    record is allowed to select the independently read authority context.
    """
    if type(records) is not tuple:
        raise CILiveAdmissionProviderError("bootstrap result must be immutable tuple")
    if len(records) != 1:
        return records
    try:
        bootstrap = decode_pr_authority_bootstrap_record(records[0])
        context = bootstrap.to_live_admission_bootstrap().verification_context()
    except Exception as exc:
        raise CILiveAdmissionProviderError("bootstrap context is invalid") from exc

    decoded = _get(
        _EPOCH_PATH,
        [
            ("trust_domain", context.trust_domain),
            ("tenant_id", context.tenant_id),
            ("organization_id", context.organization_id),
            ("mission_id", context.mission_id),
        ],
    )
    expected_fields = {
        "provider_version",
        "trust_domain",
        "tenant_id",
        "organization_id",
        "mission_id",
        "epoch",
        "revoked_grant_ids",
        "state_version",
    }
    if set(decoded) != expected_fields:
        raise CILiveAdmissionProviderError("authority epoch response is not canonical")
    if (
        decoded["trust_domain"],
        decoded["tenant_id"],
        decoded["organization_id"],
        decoded["mission_id"],
    ) != (
        context.trust_domain,
        context.tenant_id,
        context.organization_id,
        context.mission_id,
    ):
        raise CILiveAdmissionProviderError("authority epoch context mismatch")
    epoch = decoded["epoch"]
    state_version = decoded["state_version"]
    revoked = decoded["revoked_grant_ids"]
    if (
        type(epoch) is not int
        or epoch < 0
        or type(state_version) is not int
        or state_version < 1
        or type(revoked) is not list
        or len(set(revoked)) != len(revoked)
        or any(not isinstance(value, str) or not value for value in revoked)
    ):
        raise CILiveAdmissionProviderError("authority epoch response is invalid")
    state = AuthorityEpochState(
        context.trust_domain,
        context.tenant_id,
        context.organization_id,
        context.mission_id,
        epoch,
        tuple(revoked),
    ).validate()
    try:
        register_canonical_authority_epoch_state(state)
    except Exception:
        try:
            existing = observe_canonical_authority_epoch_state(context)
        except Exception as exc:
            raise CILiveAdmissionProviderError(
                "authority epoch registration failed"
            ) from exc
        if (
            existing.trust_domain,
            existing.tenant_id,
            existing.organization_id,
            existing.mission_id,
            existing.epoch,
            existing.revoked_grant_ids,
        ) != (
            state.trust_domain,
            state.tenant_id,
            state.organization_id,
            state.mission_id,
            state.epoch,
            state.revoked_grant_ids,
        ):
            raise CILiveAdmissionProviderError("authority epoch state drift")
    return records
