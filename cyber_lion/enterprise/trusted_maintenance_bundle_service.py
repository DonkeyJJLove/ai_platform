"""Read-only HTTP exposure of one atomic trusted MaintenanceBundle.

Provisioning is deliberately absent from the HTTP surface. The service runs under a
separate control-plane identity and exposes only health/read operations.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from typing import Mapping
import urllib.parse

from .maintenance_bundle import (
    CAPABILITY_REPOSITORY_REF_DELETE,
    MaintenanceBundleError,
    SQLiteMaintenanceBundleRepository,
)
from .trusted_control_plane_runtime import build_store


class TrustedMaintenanceBundleServiceError(RuntimeError):
    pass


def _text(value: object, name: str, *, limit: int = 16384) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise TrustedMaintenanceBundleServiceError(f"{name} is invalid")
    return value


def _exact_query(raw: str) -> dict[str, str]:
    try:
        values = urllib.parse.parse_qs(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
    except (ValueError, UnicodeError) as exc:
        raise TrustedMaintenanceBundleServiceError("maintenance bundle query invalid") from exc
    if set(values) != {"repository", "capability"} or any(len(item) != 1 for item in values.values()):
        raise TrustedMaintenanceBundleServiceError("maintenance bundle query shape invalid")
    result = {key: item[0] for key, item in values.items()}
    _text(result["repository"], "repository", limit=512)
    _text(result["capability"], "capability", limit=128)
    if result["capability"] != CAPABILITY_REPOSITORY_REF_DELETE:
        raise TrustedMaintenanceBundleServiceError("maintenance capability unsupported")
    return result


class TrustedMaintenanceBundleService:
    def __init__(self, *, repository: SQLiteMaintenanceBundleRepository, credential: str) -> None:
        if type(repository) is not SQLiteMaintenanceBundleRepository:
            raise TrustedMaintenanceBundleServiceError("exact maintenance bundle repository required")
        _text(credential, "credential")
        if not credential.isascii():
            raise TrustedMaintenanceBundleServiceError("credential is invalid")
        self.repository = repository
        self.credential = credential

    def _authorized(self, headers: Mapping[str, str]) -> bool:
        raw = headers.get("Authorization")
        if not isinstance(raw, str) or not raw.startswith("Bearer "):
            return False
        supplied = raw[7:]
        return bool(supplied) and hmac.compare_digest(supplied, self.credential)

    def dispatch(self, *, method: str, target: str, headers: Mapping[str, str], body: bytes = b"") -> tuple[int, dict[str, object]]:
        if not self._authorized(headers):
            return 401, {"status": "ERROR", "error": "UNAUTHORIZED"}
        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            return 400, {"status": "ERROR", "error": "REQUEST_REJECTED"}
        if parsed.path == "/healthz":
            if method != "GET" or parsed.query or body:
                return 400, {"status": "ERROR", "error": "REQUEST_REJECTED"}
            return 200, {
                "status": "READY",
                "source_origin_id": self.repository.source_origin_id,
                "source_origin_digest": self.repository.source_origin_digest,
                "database_identity": self.repository.database_identity,
            }
        if parsed.path != "/v1/maintenance-bundle":
            return 404, {"status": "ERROR", "error": "NOT_FOUND"}
        if method != "GET" or body:
            return 405, {"status": "ERROR", "error": "METHOD_NOT_ALLOWED"}
        try:
            query = _exact_query(parsed.query)
            bundle = self.repository.resolve_exact(
                repository=query["repository"], capability=query["capability"]
            )
        except (MaintenanceBundleError, TrustedMaintenanceBundleServiceError):
            return 409, {"status": "ERROR", "error": "BUNDLE_NOT_EXACT"}
        return 200, bundle.to_wire()


class _Handler(BaseHTTPRequestHandler):
    server_version = "CyberLionMaintenanceBundle/1.0"
    sys_version = ""

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _run(self) -> None:
        service = getattr(self.server, "lion_service", None)
        if not isinstance(service, TrustedMaintenanceBundleService):
            self._write(503, {"status": "ERROR", "error": "SERVICE_UNAVAILABLE"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write(400, {"status": "ERROR", "error": "REQUEST_REJECTED"})
            return
        if content_length < 0 or content_length > 1024:
            self._write(413, {"status": "ERROR", "error": "REQUEST_TOO_LARGE"})
            return
        body = self.rfile.read(content_length) if content_length else b""
        status, payload = service.dispatch(
            method=self.command,
            target=self.path,
            headers={"Authorization": self.headers.get("Authorization", "")},
            body=body,
        )
        self._write(status, payload)

    def _write(self, status: int, payload: Mapping[str, object]) -> None:
        raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    do_GET = _run

    def _deny(self) -> None:
        self._write(405, {"status": "ERROR", "error": "METHOD_NOT_ALLOWED"})

    do_POST = _deny
    do_PUT = _deny
    do_PATCH = _deny
    do_DELETE = _deny
    do_HEAD = _deny
    do_OPTIONS = _deny
    do_TRACE = _deny
    do_CONNECT = _deny


def build_service_from_environment() -> TrustedMaintenanceBundleService:
    credential_env = _text(os.environ.get("LION_MAINTENANCE_BUNDLE_CREDENTIAL_ENV"), "credential env", limit=128)
    credential = _text(os.environ.get(credential_env), "credential")
    store = build_store()
    repository = SQLiteMaintenanceBundleRepository(store, initialize_schema=False)
    return TrustedMaintenanceBundleService(repository=repository, credential=credential)


def serve_from_environment() -> None:
    service = build_service_from_environment()
    host = os.environ.get("LION_MAINTENANCE_BUNDLE_HOST", "127.0.0.1")
    port_raw = os.environ.get("LION_MAINTENANCE_BUNDLE_PORT", "8765")
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise TrustedMaintenanceBundleServiceError("service port invalid") from exc
    if host not in {"127.0.0.1", "::1", "localhost"} or not (1 <= port <= 65535):
        raise TrustedMaintenanceBundleServiceError("service bind must remain loopback")
    server = ThreadingHTTPServer((host, port), _Handler)
    server.lion_service = service
    server.serve_forever()


if __name__ == "__main__":
    serve_from_environment()
