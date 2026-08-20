"""Fail-closed process entrypoint for Cyber-Lion CI live merge admission.

The production composition path starts from exact trusted PR identity, resolves exactly
one immutable authority bootstrap through a read-only trusted-control-plane provider,
then evaluates live non-consuming admission with separately selected authority and
signature-verifier providers. Provider selection is trusted runtime configuration,
never PR-tree authority.

The module emits one sanitized JSON object, exits zero only for a validated ALLOW,
does not consume authority, persist credentials, call GitHub, or expose mutation
operations.
"""
from __future__ import annotations

import importlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict
from typing import Any

from .authority_verification import IssuerKeyBinding
from .ci_live_admission import (
    CILiveAdmissionBootstrap,
    ReadOnlyAuthorityControlPlaneTransport,
    admission_exit_code,
    run_live_admission,
)
from .merge_admission import TrustedPullRequestState
from .pr_authority_bootstrap import (
    PRAuthorityBootstrapLookupKey,
    PRAuthorityBootstrapTransport,
    TrustedControlPlanePRAuthorityBootstrapSource,
)


class CILiveAdmissionEntrypointError(ValueError):
    """Raised when trusted process configuration is incomplete or malformed."""


def _required_env(env: Mapping[str, str], name: str, *, limit: int = 4096) -> str:
    value = env.get(name)
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise CILiveAdmissionEntrypointError(f"{name} is missing or invalid")
    return value


def _positive_int(value: str, *, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CILiveAdmissionEntrypointError(f"{field_name} must be an integer") from exc
    if parsed <= 0:
        raise CILiveAdmissionEntrypointError(f"{field_name} must be positive")
    return parsed


def _non_negative_int(value: str, *, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CILiveAdmissionEntrypointError(f"{field_name} must be an integer") from exc
    if parsed < 0:
        raise CILiveAdmissionEntrypointError(f"{field_name} must be non-negative")
    return parsed


def load_pr_state(env: Mapping[str, str]) -> TrustedPullRequestState:
    """Load exact GitHub PR state supplied by the trusted CI bootstrap layer."""
    return TrustedPullRequestState(
        repository=_required_env(env, "CYBER_LION_REPOSITORY", limit=512),
        pr_number=_positive_int(
            _required_env(env, "CYBER_LION_PR_NUMBER", limit=32),
            field_name="CYBER_LION_PR_NUMBER",
        ),
        base_sha=_required_env(env, "CYBER_LION_BASE_SHA", limit=64),
        head_sha=_required_env(env, "CYBER_LION_HEAD_SHA", limit=64),
        merge_method=_required_env(env, "CYBER_LION_MERGE_METHOD", limit=32),
    ).validate()


def load_bootstrap(env: Mapping[str, str]) -> CILiveAdmissionBootstrap:
    """Legacy library helper; production ``main`` does not use env bootstrap fields."""
    return CILiveAdmissionBootstrap(
        trust_domain=_required_env(env, "CYBER_LION_TRUST_DOMAIN", limit=256),
        tenant_id=_required_env(env, "CYBER_LION_TENANT_ID", limit=256),
        organization_id=_required_env(env, "CYBER_LION_ORGANIZATION_ID", limit=256),
        mission_id=_required_env(env, "CYBER_LION_MISSION_ID", limit=256),
        grant_id=_required_env(env, "CYBER_LION_GRANT_ID", limit=256),
        epoch=_non_negative_int(
            _required_env(env, "CYBER_LION_AUTHORITY_EPOCH", limit=32),
            field_name="CYBER_LION_AUTHORITY_EPOCH",
        ),
        root_grant_id=_required_env(env, "CYBER_LION_ROOT_GRANT_ID", limit=256),
        root_grant_digest=_required_env(
            env, "CYBER_LION_ROOT_GRANT_DIGEST", limit=64
        ),
    ).validate()


def load_issuer_key_bindings(env: Mapping[str, str]) -> tuple[IssuerKeyBinding, ...]:
    """Legacy library helper; production ``main`` uses discovered issuer bindings."""
    raw = _required_env(env, "CYBER_LION_ISSUER_KEYS_JSON", limit=65536)
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CILiveAdmissionEntrypointError(
            "CYBER_LION_ISSUER_KEYS_JSON is invalid"
        ) from exc
    if not isinstance(decoded, list) or not decoded:
        raise CILiveAdmissionEntrypointError(
            "CYBER_LION_ISSUER_KEYS_JSON must be a non-empty array"
        )

    allowed = {"issuer_subject_id", "trust_domain", "key_id", "algorithm"}
    result: list[IssuerKeyBinding] = []
    for item in decoded:
        if not isinstance(item, dict) or set(item) != allowed:
            raise CILiveAdmissionEntrypointError("issuer key binding shape is invalid")
        result.append(
            IssuerKeyBinding(
                issuer_subject_id=item["issuer_subject_id"],
                trust_domain=item["trust_domain"],
                key_id=item["key_id"],
                algorithm=item["algorithm"],
            ).validate()
        )
    return tuple(result)


def _provider_spec(env: Mapping[str, str], variable: str) -> tuple[str, str]:
    spec = _required_env(env, variable, limit=512)
    if spec.count(":") != 1:
        raise CILiveAdmissionEntrypointError(f"{variable} must use module:callable form")
    module_name, attribute_name = spec.split(":", 1)
    module_parts = module_name.split(".")
    if (
        not module_parts
        or any(not part.isidentifier() for part in module_parts)
        or not attribute_name.isidentifier()
    ):
        raise CILiveAdmissionEntrypointError(f"{variable} provider name is invalid")
    return module_name, attribute_name


def load_provider(env: Mapping[str, str], variable: str) -> Callable[..., Any]:
    """Load one callable selected exclusively by trusted runtime configuration."""
    module_name, attribute_name = _provider_spec(env, variable)
    try:
        module = importlib.import_module(module_name)
        provider = getattr(module, attribute_name)
    except (ImportError, AttributeError) as exc:
        raise CILiveAdmissionEntrypointError(f"{variable} provider unavailable") from exc
    if not callable(provider):
        raise CILiveAdmissionEntrypointError(f"{variable} provider is not callable")
    return provider


class ReadOnlyPRAuthorityBootstrapTransport(PRAuthorityBootstrapTransport):
    """Capability-reduced adapter around one injected exact bootstrap lookup."""

    __slots__ = ("_lookup",)

    def __init__(
        self,
        lookup: Callable[..., tuple[Mapping[str, object], ...]],
    ) -> None:
        if not callable(lookup):
            raise CILiveAdmissionEntrypointError("bootstrap lookup must be callable")
        self._lookup = lookup

    def lookup_exact(
        self,
        *,
        repository: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        merge_method: str,
    ) -> tuple[Mapping[str, object], ...]:
        return self._lookup(
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            merge_method=merge_method,
        )


def _public_receipt(receipt: object) -> dict[str, object]:
    """Project a receipt to public CI evidence without provider-controlled rationale."""
    decision = getattr(receipt, "decision", None)
    payload: dict[str, object] = {
        "runtime_version": getattr(receipt, "runtime_version", None),
        "admission_id": getattr(receipt, "admission_id", None),
        "decision": decision,
        "repository": getattr(receipt, "repository", None),
        "pr_number": getattr(receipt, "pr_number", None),
        "base_sha": getattr(receipt, "base_sha", None),
        "head_sha": getattr(receipt, "head_sha", None),
        "merge_method": getattr(receipt, "merge_method", None),
        "mission_id": getattr(receipt, "mission_id", None),
        "grant_id": getattr(receipt, "grant_id", None),
        "evidence": None,
    }
    evidence = getattr(receipt, "evidence", None)
    if decision == "ALLOW" and evidence is not None:
        payload["evidence"] = asdict(evidence)
    return payload


def _emit(payload: Mapping[str, object]) -> None:
    print(
        json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )


def execute(
    *,
    env: Mapping[str, str],
    lookup_exact: Callable[..., tuple[Mapping[str, object], ...]],
    verifier: Callable[[bytes, str, str, str], bool],
) -> int:
    """Legacy library composition using explicit trusted bootstrap env fields."""
    pr_state = load_pr_state(env)
    bootstrap = load_bootstrap(env)
    issuer_keys = load_issuer_key_bindings(env)
    admission_id = _required_env(env, "CYBER_LION_ADMISSION_ID", limit=512)

    receipt = run_live_admission(
        pr_state=pr_state,
        bootstrap=bootstrap,
        authority_transport=ReadOnlyAuthorityControlPlaneTransport(lookup_exact),
        issuer_keys=issuer_keys,
        verifier=verifier,
        admission_id=admission_id,
    )
    _emit(_public_receipt(receipt))
    return admission_exit_code(receipt)


def execute_composed(
    *,
    env: Mapping[str, str],
    bootstrap_lookup_exact: Callable[..., tuple[Mapping[str, object], ...]],
    authority_lookup_exact: Callable[..., tuple[Mapping[str, object], ...]],
    verifier: Callable[[bytes, str, str, str], bool],
) -> int:
    """Resolve trusted PR bootstrap exactly, then run one live admission evaluation."""
    pr_state = load_pr_state(env)
    admission_id = _required_env(env, "CYBER_LION_ADMISSION_ID", limit=512)

    discovery_key = PRAuthorityBootstrapLookupKey(
        repository=pr_state.repository,
        pr_number=pr_state.pr_number,
        base_sha=pr_state.base_sha,
        head_sha=pr_state.head_sha,
        merge_method=pr_state.merge_method,
    ).validate()

    bootstrap_source = TrustedControlPlanePRAuthorityBootstrapSource(
        ReadOnlyPRAuthorityBootstrapTransport(bootstrap_lookup_exact)
    )
    record = bootstrap_source.resolve_exact(discovery_key)

    receipt = run_live_admission(
        pr_state=pr_state,
        bootstrap=record.to_live_admission_bootstrap(),
        authority_transport=ReadOnlyAuthorityControlPlaneTransport(
            authority_lookup_exact
        ),
        issuer_keys=record.issuer_key_bindings,
        verifier=verifier,
        admission_id=admission_id,
    )
    _emit(_public_receipt(receipt))
    return admission_exit_code(receipt)


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> int:
    """Run the production composed path and fail closed on discovery/config errors."""
    del argv
    source = os.environ if env is None else env
    try:
        bootstrap_lookup = load_provider(
            source, "CYBER_LION_BOOTSTRAP_PROVIDER"
        )
        authority_lookup = load_provider(
            source, "CYBER_LION_AUTHORITY_PROVIDER"
        )
        verifier = load_provider(source, "CYBER_LION_VERIFIER_PROVIDER")
        return execute_composed(
            env=source,
            bootstrap_lookup_exact=bootstrap_lookup,
            authority_lookup_exact=authority_lookup,
            verifier=verifier,
        )
    except Exception:
        _emit({"status": "ERROR", "error": "CONFIGURATION_OR_RUNTIME_ERROR"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
