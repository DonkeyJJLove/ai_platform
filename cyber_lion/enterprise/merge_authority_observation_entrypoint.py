"""Evidence-only process entrypoint for trusted merge-authority observation.

The entrypoint loads only trusted runtime-selected read/verification capabilities. It
never loads a consumption write capability and never executes a merge effect.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping

from .ci_live_admission_entrypoint import CILiveAdmissionEntrypointError, load_pr_state, load_provider
from .merge_authority_observation import (
    MergeAuthorityObservationError,
    observe_trusted_merge_authority,
    provider_identity,
)


_REQUIRED_PROVIDER_SELECTORS = (
    ("BOOTSTRAP", "CYBER_LION_BOOTSTRAP_PROVIDER"),
    ("AUTHORITY", "CYBER_LION_AUTHORITY_PROVIDER"),
    ("VERIFIER", "CYBER_LION_VERIFIER_PROVIDER"),
    ("CLOCK", "CYBER_LION_CLOCK_PROVIDER"),
    ("CONSUMPTION_STATE", "CYBER_LION_CONSUMPTION_READ_PROVIDER"),
)


def _required(env: Mapping[str, str], name: str, *, limit: int = 4096) -> str:
    value = env.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise CILiveAdmissionEntrypointError(f"{name} is missing or invalid")
    return value


def _identity(env: Mapping[str, str], role: str, selector: str):
    spec = _required(env, selector, limit=512)
    version = _required(env, "CYBER_LION_PROVIDER_VERSION", limit=64)
    trusted_base_sha = _required(env, "CYBER_LION_TRUSTED_BASE_SHA", limit=40)
    origin = _required(env, "CYBER_LION_CONTROL_PLANE_ORIGIN", limit=2048)
    return provider_identity(
        role=role,
        provider_version=version,
        implementation_identity=spec,
        trusted_base_sha=trusted_base_sha,
        public_configuration={
            "selector": selector,
            "implementation": spec,
            "origin": origin,
            "trusted_base_sha": trusted_base_sha,
            "provider_version": version,
        },
        source_kind="trusted-runtime",
    )


def _emit(payload: Mapping[str, object]) -> None:
    print(json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def execute(*, env: Mapping[str, str]) -> int:
    pr_state = load_pr_state(env)
    observation_id = _required(env, "CYBER_LION_OBSERVATION_ID", limit=512)
    providers = {
        role: load_provider(env, selector)
        for role, selector in _REQUIRED_PROVIDER_SELECTORS
    }
    identities = {
        role: _identity(env, role, selector)
        for role, selector in _REQUIRED_PROVIDER_SELECTORS
    }
    observation = observe_trusted_merge_authority(
        pr_state=pr_state,
        observation_id=observation_id,
        bootstrap_lookup_exact=providers["BOOTSTRAP"],
        authority_lookup_exact=providers["AUTHORITY"],
        verifier=providers["VERIFIER"],
        clock_provider=providers["CLOCK"],
        consumption_read_provider=providers["CONSUMPTION_STATE"],
        bootstrap_provider_identity=identities["BOOTSTRAP"],
        authority_provider_identity=identities["AUTHORITY"],
        verifier_provider_identity=identities["VERIFIER"],
        clock_provider_identity=identities["CLOCK"],
        consumption_provider_identity=identities["CONSUMPTION_STATE"],
    )
    _emit(observation.to_public_dict())
    return 0


def main(argv: list[str] | None = None, *, env: Mapping[str, str] | None = None) -> int:
    del argv
    source = os.environ if env is None else env
    try:
        code = execute(env=source)
        print("MERGE_AUTHORITY_OBSERVATION_TERMINAL=OK")
        print("AUTHORITY_EFFECT=NO")
        print("MERGE_AUTHORIZATION_INFERRED=NO")
        return code
    except Exception:
        _emit({
            "status": "ERROR",
            "error": "CONFIGURATION_OR_RUNTIME_ERROR",
            "authority_effect": "NO",
            "merge_authorization_inferred": "NO",
        })
        print("MERGE_AUTHORITY_OBSERVATION_TERMINAL=FAIL")
        print("AUTHORITY_EFFECT=NO")
        print("MERGE_AUTHORIZATION_INFERRED=NO")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
