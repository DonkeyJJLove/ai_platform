"""LAB-DEBIAN trusted control-plane extension for clock and consumption observation."""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import os
import urllib.parse

from .merge_authority_consumption import MergeAuthorityConsumptionKey
from .merge_authority_consumption_store import build_consumption_store_from_environment
from .trusted_control_plane_service import (
    PROVIDER_VERSION,
    ServiceResponse,
    TrustedControlPlaneService,
    TrustedControlPlaneServiceError,
    _public_text,
    build_service_from_environment,
    serve,
)

_CLOCK_PATH = "/v1/trusted-clock"
_CONSUMPTION_PATH = "/v1/merge-authority-consumption"
_CONSUMPTION_FIELDS = frozenset(
    {
        "repository",
        "pr_number",
        "base_sha",
        "head_sha",
        "grant_id",
        "grant_digest",
        "lineage_digest",
        "epoch",
        "merge_method",
    }
)


class LABMergeAuthorityControlPlane(TrustedControlPlaneService):
    __slots__ = ("_consumption_store", "_clock_source_id")

    def __init__(
        self,
        *,
        base: TrustedControlPlaneService,
        consumption_store,
        clock_source_id: str,
    ) -> None:
        super().__init__(
            store=base._store,
            verifier=base._verifier,
            credential=base._credential,
        )
        self._consumption_store = consumption_store
        self._clock_source_id = _public_text(
            clock_source_id, field_name="clock source id"
        )

    def _authorized_runtime(self, authorization: object) -> bool:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            return False
        supplied = authorization[7:]
        return bool(supplied) and hmac.compare_digest(supplied, self._credential)

    @staticmethod
    def _query(raw: str) -> dict[str, str]:
        try:
            decoded = urllib.parse.parse_qs(
                raw,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=len(_CONSUMPTION_FIELDS),
            )
        except Exception as exc:
            raise TrustedControlPlaneServiceError("consumption query invalid") from exc
        if frozenset(decoded) != _CONSUMPTION_FIELDS or any(
            len(v) != 1 for v in decoded.values()
        ):
            raise TrustedControlPlaneServiceError("consumption query invalid")
        return {k: v[0] for k, v in decoded.items()}

    def dispatch(
        self, *, method: str, target: str, headers, body: bytes = b""
    ) -> ServiceResponse:
        parsed = urllib.parse.urlsplit(target)
        if parsed.path not in {_CLOCK_PATH, _CONSUMPTION_PATH}:
            return super().dispatch(
                method=method, target=target, headers=headers, body=body
            )
        if not self._authorized_runtime(headers.get("Authorization")):
            return ServiceResponse(
                401, {"status": "ERROR", "error": "UNAUTHORIZED"}
            ).validate()
        if (
            method != "GET"
            or body
            or parsed.scheme
            or parsed.netloc
            or parsed.fragment
        ):
            return ServiceResponse(
                400, {"status": "ERROR", "error": "INVALID_REQUEST"}
            ).validate()
        if parsed.path == _CLOCK_PATH:
            if parsed.query:
                return ServiceResponse(
                    400, {"status": "ERROR", "error": "INVALID_REQUEST"}
                ).validate()
            observed_at = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
            return ServiceResponse(
                200,
                {
                    "provider_version": PROVIDER_VERSION,
                    "observed_at": observed_at,
                    "trusted_clock_source_id": self._clock_source_id,
                },
            ).validate()
        try:
            q = self._query(parsed.query)
            key = MergeAuthorityConsumptionKey(
                repository=q["repository"],
                pr_number=int(q["pr_number"]),
                base_sha=q["base_sha"],
                head_sha=q["head_sha"],
                grant_id=q["grant_id"],
                grant_digest=q["grant_digest"],
                lineage_digest=q["lineage_digest"],
                epoch=int(q["epoch"]),
                merge_method=q["merge_method"],
            ).validate()
            observation = self._consumption_store.observe_consumption_exact(key)
            return ServiceResponse(
                200,
                {
                    "provider_version": PROVIDER_VERSION,
                    "state": observation.state.value,
                    "state_version": observation.state_version,
                    "provenance_id": observation.provenance_id,
                },
            ).validate()
        except Exception:
            return ServiceResponse(
                400, {"status": "ERROR", "error": "INVALID_REQUEST"}
            ).validate()


def build_lab_service_from_environment() -> LABMergeAuthorityControlPlane:
    base = build_service_from_environment()
    consumption_store = build_consumption_store_from_environment()
    clock_source_id = os.environ.get("CYBER_LION_CP_CLOCK_SOURCE_ID", "")
    return LABMergeAuthorityControlPlane(
        base=base,
        consumption_store=consumption_store,
        clock_source_id=clock_source_id,
    )


def main() -> int:
    try:
        service = build_lab_service_from_environment()
        host = os.environ.get("CYBER_LION_CP_BIND_HOST", "")
        port_raw = os.environ.get("CYBER_LION_CP_BIND_PORT", "")
        if not port_raw.isascii() or not port_raw.isdigit():
            raise TrustedControlPlaneServiceError("bind port invalid")
        serve(service, host=host, port=int(port_raw))
        return 0
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
