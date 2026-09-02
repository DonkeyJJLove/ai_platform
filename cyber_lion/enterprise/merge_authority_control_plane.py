"""LAB-DEBIAN trusted control-plane extension for clock and consumption observation."""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json
import os
import sqlite3
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
_EPOCH_PATH = "/v1/authority-epoch-snapshot"
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
_EPOCH_FIELDS = frozenset(
    {"trust_domain", "tenant_id", "organization_id", "mission_id"}
)


class LABMergeAuthorityControlPlane(TrustedControlPlaneService):
    __slots__ = ("_consumption_store", "_clock_source_id", "_authority_database_path")

    def __init__(
        self,
        *,
        base: TrustedControlPlaneService,
        consumption_store,
        clock_source_id: str,
        authority_database_path: str | None = None,
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
        if authority_database_path is None:
            self._authority_database_path = ""
        else:
            path = _public_text(
                authority_database_path,
                field_name="authority database path",
                limit=4096,
            )
            if not path.startswith("/") or "\x00" in path:
                raise TrustedControlPlaneServiceError("authority database path invalid")
            self._authority_database_path = path

    def _authorized_runtime(self, authorization: object) -> bool:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            return False
        supplied = authorization[7:]
        return bool(supplied) and hmac.compare_digest(supplied, self._credential)

    @staticmethod
    def _query(raw: str, expected: frozenset[str]) -> dict[str, str]:
        try:
            decoded = urllib.parse.parse_qs(
                raw,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=len(expected),
            )
        except Exception as exc:
            raise TrustedControlPlaneServiceError("runtime query invalid") from exc
        if frozenset(decoded) != expected or any(
            len(v) != 1 for v in decoded.values()
        ):
            raise TrustedControlPlaneServiceError("runtime query invalid")
        return {k: v[0] for k, v in decoded.items()}

    def _epoch_snapshot(self, raw_query: str) -> ServiceResponse:
        if not self._authority_database_path:
            raise TrustedControlPlaneServiceError("authority database unavailable")
        q = self._query(raw_query, _EPOCH_FIELDS)
        context = tuple(
            _public_text(q[name], field_name=name)
            for name in ("trust_domain", "tenant_id", "organization_id", "mission_id")
        )
        uri = f"file:{self._authority_database_path}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True, timeout=5) as connection:
                rows = connection.execute(
                    """
                    SELECT epoch,revoked_json,version
                    FROM authority_epoch_state
                    WHERE trust_domain=? AND tenant_id=?
                      AND organization_id=? AND mission_id=?
                    """,
                    context,
                ).fetchall()
        except sqlite3.Error as exc:
            raise TrustedControlPlaneServiceError(
                "authority epoch state unavailable"
            ) from exc
        if len(rows) != 1:
            raise TrustedControlPlaneServiceError(
                "authority epoch state missing or ambiguous"
            )
        epoch, revoked_raw, state_version = rows[0]
        if (
            type(epoch) is not int
            or epoch < 0
            or type(state_version) is not int
            or state_version < 1
        ):
            raise TrustedControlPlaneServiceError("authority epoch state invalid")
        try:
            revoked = json.loads(revoked_raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise TrustedControlPlaneServiceError(
                "authority revocation state invalid"
            ) from exc
        if (
            type(revoked) is not list
            or len(set(revoked)) != len(revoked)
            or any(not isinstance(value, str) or not value for value in revoked)
        ):
            raise TrustedControlPlaneServiceError(
                "authority revocation state invalid"
            )
        trust_domain, tenant_id, organization_id, mission_id = context
        return ServiceResponse(
            200,
            {
                "provider_version": PROVIDER_VERSION,
                "trust_domain": trust_domain,
                "tenant_id": tenant_id,
                "organization_id": organization_id,
                "mission_id": mission_id,
                "epoch": epoch,
                "revoked_grant_ids": revoked,
                "state_version": state_version,
            },
        ).validate()

    def dispatch(
        self, *, method: str, target: str, headers, body: bytes = b""
    ) -> ServiceResponse:
        parsed = urllib.parse.urlsplit(target)
        if parsed.path not in {_CLOCK_PATH, _CONSUMPTION_PATH, _EPOCH_PATH}:
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
        if parsed.path == _EPOCH_PATH:
            try:
                return self._epoch_snapshot(parsed.query)
            except Exception:
                return ServiceResponse(
                    400, {"status": "ERROR", "error": "INVALID_REQUEST"}
                ).validate()
        try:
            q = self._query(parsed.query, _CONSUMPTION_FIELDS)
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
    authority_database_path = os.environ.get("LION_CP_DATABASE_PATH", "")
    return LABMergeAuthorityControlPlane(
        base=base,
        consumption_store=consumption_store,
        clock_source_id=clock_source_id,
        authority_database_path=authority_database_path,
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
