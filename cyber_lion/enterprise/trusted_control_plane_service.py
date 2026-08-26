"""Read-only HTTP service core for Cyber-Lion trusted control-plane admission."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
import base64
import binascii
import hmac
import importlib
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Final
import urllib.parse

PROVIDER_VERSION: Final = "1.0.0"
_BOOTSTRAP_PATH: Final = "/v1/pr-authority-bootstrap"
_AUTHORITY_PATH: Final = "/v1/authority-lineage"
_BUILDER_SUBJECT_PATH: Final = "/v1/builder-subject"
_MAINTENANCE_POLICY_PATH: Final = "/v1/maintenance-policy"
_MAINTENANCE_MISSION_PATH: Final = "/v1/maintenance-mission"
_VERIFY_PATH: Final = "/v1/verify-signature"
_HEALTH_PATH: Final = "/healthz"

_MAX_REQUEST_BODY: Final = 128 * 1024
_MAX_RECORDS: Final = 16
_MAX_PUBLIC_TEXT: Final = 512
_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_ENV_REF_RE: Final = re.compile(r"^[A-Z][A-Z0-9_]{0,255}$")
_PROVIDER_RE: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*$")
_MERGE_METHODS: Final = frozenset({"merge", "squash", "rebase"})
_BUILDER_CAPABILITY: Final = "DETACHED_CANDIDATE_BUILD_ONLY"

_BOOTSTRAP_QUERY_FIELDS: Final = frozenset({"repository", "pr_number", "base_sha", "head_sha", "merge_method"})
_AUTHORITY_QUERY_FIELDS: Final = frozenset({"repository", "pr_number", "base_sha", "head_sha", "mission_id", "grant_id"})
_BUILDER_QUERY_FIELDS: Final = frozenset({"repository", "builder_subject_id", "builder_instance_id", "candidate_scope_digest", "resource_scope_digest", "capability_class"})
_MAINTENANCE_POLICY_QUERY_FIELDS: Final = frozenset({"repository", "mission_id", "policy_id"})
_MAINTENANCE_MISSION_QUERY_FIELDS: Final = frozenset({"repository", "mission_id"})
_VERIFY_BODY_FIELDS: Final = frozenset({"payload_base64", "signature", "key_id", "algorithm"})


class TrustedControlPlaneServiceError(RuntimeError):
    pass


class TrustedControlPlaneStore(ABC):
    @abstractmethod
    def lookup_pr_bootstrap_exact(self, *, repository: str, pr_number: int, base_sha: str, head_sha: str, merge_method: str) -> tuple[Mapping[str, object], ...]:
        raise NotImplementedError

    @abstractmethod
    def lookup_authority_exact(self, *, repository: str, pr_number: int, base_sha: str, head_sha: str, mission_id: str, grant_id: str) -> tuple[Mapping[str, object], ...]:
        raise NotImplementedError

    @abstractmethod
    def lookup_builder_subject_exact(self, *, repository: str, builder_subject_id: str, builder_instance_id: str, candidate_scope_digest: str, resource_scope_digest: str, capability_class: str) -> tuple[Mapping[str, object], ...]:
        raise NotImplementedError

    def lookup_maintenance_policy_exact(self, *, repository: str, mission_id: str, policy_id: str) -> tuple[Mapping[str, object], ...]:
        """Read-only optional capability; implementations must preserve zero/many cardinality."""
        raise NotImplementedError

    def lookup_maintenance_mission_exact(self, *, repository: str, mission_id: str) -> tuple[Mapping[str, object], ...]:
        """Read-only optional capability; implementations must preserve zero/many cardinality."""
        raise NotImplementedError

    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError


class TrustedSignatureVerifier(ABC):
    @abstractmethod
    def verify(self, payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class ServiceResponse:
    status: int
    payload: Mapping[str, object]

    def validate(self) -> "ServiceResponse":
        if type(self.status) is not int or not (100 <= self.status <= 599):
            raise TrustedControlPlaneServiceError("service response status is invalid")
        if not isinstance(self.payload, Mapping):
            raise TrustedControlPlaneServiceError("service response payload is invalid")
        return self


def _public_text(value: object, *, field_name: str, limit: int = _MAX_PUBLIC_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        raise TrustedControlPlaneServiceError(f"{field_name} is invalid")
    return value


def _sha(value: object, *, field_name: str) -> str:
    value = _public_text(value, field_name=field_name, limit=40)
    if not _SHA_RE.fullmatch(value):
        raise TrustedControlPlaneServiceError(f"{field_name} is invalid")
    return value


def _digest(value: object, *, field_name: str) -> str:
    value = _public_text(value, field_name=field_name, limit=64)
    if not _DIGEST_RE.fullmatch(value):
        raise TrustedControlPlaneServiceError(f"{field_name} is invalid")
    return value


def _positive_int_text(value: object, *, field_name: str) -> int:
    value = _public_text(value, field_name=field_name, limit=20)
    if not value.isascii() or not value.isdigit() or int(value) <= 0:
        raise TrustedControlPlaneServiceError(f"{field_name} is invalid")
    return int(value)


def _exact_query(query: str, expected: frozenset[str]) -> dict[str, str]:
    try:
        decoded = urllib.parse.parse_qs(query, keep_blank_values=True, strict_parsing=True, max_num_fields=len(expected))
    except (ValueError, UnicodeError) as exc:
        raise TrustedControlPlaneServiceError("request query is invalid") from exc
    if frozenset(decoded.keys()) != expected or any(type(v) is not list or len(v) != 1 for v in decoded.values()):
        raise TrustedControlPlaneServiceError("request query fields are not canonical")
    return {k: v[0] for k, v in decoded.items()}


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TrustedControlPlaneServiceError("request body fields are not canonical")
        result[key] = value
    return result


def _exact_json_body(raw_body: bytes) -> Mapping[str, object]:
    if type(raw_body) is not bytes or len(raw_body) > _MAX_REQUEST_BODY:
        raise TrustedControlPlaneServiceError("request body is invalid")
    try:
        decoded = json.loads(raw_body.decode("utf-8"), object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustedControlPlaneServiceError("request body is invalid") from exc
    if not isinstance(decoded, Mapping) or frozenset(decoded.keys()) != _VERIFY_BODY_FIELDS:
        raise TrustedControlPlaneServiceError("request body fields are not canonical")
    return decoded


def _canonical_record_tuple(records: object, *, expected_binding: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    if type(records) is not tuple or len(records) > _MAX_RECORDS:
        raise TrustedControlPlaneServiceError("trusted store result is invalid")
    expected_fields = frozenset(expected_binding.keys())
    result: list[Mapping[str, object]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise TrustedControlPlaneServiceError("trusted store result is invalid")
        lookup = record.get("lookup_key")
        if not isinstance(lookup, Mapping) or frozenset(lookup.keys()) != expected_fields:
            raise TrustedControlPlaneServiceError("trusted store binding is invalid")
        if any(lookup[key] != expected_binding[key] for key in expected_binding):
            raise TrustedControlPlaneServiceError("trusted store binding is invalid")
        result.append(dict(record))
    return tuple(result)


def validate_maintenance_policy_record(record: Mapping[str, object], *, expected_binding: Mapping[str, object]) -> Mapping[str, object]:
    """Strictly decode a trusted maintenance policy record without granting authority."""
    from cyber_lion.contracts.policy_gate import PolicyRevision

    fields = frozenset({"record_kind", "lookup_key", "revision", "content_digest", "lane", "active", "provenance_ref", "policy_payload"})
    payload_fields = frozenset({"policy_id", "revision", "content_digest", "lane", "active", "schema_version"})
    if not isinstance(record, Mapping) or frozenset(record.keys()) != fields or record.get("record_kind") != "maintenance-policy":
        raise TrustedControlPlaneServiceError("maintenance policy record is invalid")
    canonical = _canonical_record_tuple((record,), expected_binding=expected_binding)[0]
    payload = canonical.get("policy_payload")
    if not isinstance(payload, Mapping) or frozenset(payload.keys()) != payload_fields:
        raise TrustedControlPlaneServiceError("maintenance policy payload is invalid")
    try:
        policy = PolicyRevision(**dict(payload)).validate()
    except Exception as exc:
        raise TrustedControlPlaneServiceError("maintenance policy payload is invalid") from exc
    if policy.policy_id != expected_binding["policy_id"] or canonical["revision"] != policy.revision or canonical["content_digest"] != policy.content_digest or canonical["lane"] != policy.lane or canonical["active"] is not policy.active:
        raise TrustedControlPlaneServiceError("maintenance policy binding is invalid")
    _public_text(canonical["provenance_ref"], field_name="maintenance policy provenance")
    return canonical


def validate_maintenance_mission_record(record: Mapping[str, object], *, expected_binding: Mapping[str, object]) -> Mapping[str, object]:
    """Strictly decode a trusted maintenance mission record without granting authority."""
    from cyber_lion.enterprise.models import MissionSpec

    fields = frozenset({"record_kind", "lookup_key", "provenance_ref", "mission_payload"})
    payload_fields = frozenset({"mission_id", "purpose", "required_capabilities", "authority_ceiling", "risk_class", "max_agents", "observability_quorum", "require_independent_verifier", "max_total_cost_units"})
    if not isinstance(record, Mapping) or frozenset(record.keys()) != fields or record.get("record_kind") != "maintenance-mission":
        raise TrustedControlPlaneServiceError("maintenance mission record is invalid")
    canonical = _canonical_record_tuple((record,), expected_binding=expected_binding)[0]
    payload = canonical.get("mission_payload")
    if not isinstance(payload, Mapping) or frozenset(payload.keys()) != payload_fields:
        raise TrustedControlPlaneServiceError("maintenance mission payload is invalid")
    normalized = dict(payload)
    caps = normalized.get("required_capabilities")
    if type(caps) is not list:
        raise TrustedControlPlaneServiceError("maintenance mission capabilities are invalid")
    normalized["required_capabilities"] = tuple(caps)
    try:
        mission = MissionSpec(**normalized).validate()
    except Exception as exc:
        raise TrustedControlPlaneServiceError("maintenance mission payload is invalid") from exc
    if mission.mission_id != expected_binding["mission_id"]:
        raise TrustedControlPlaneServiceError("maintenance mission binding is invalid")
    _public_text(canonical["provenance_ref"], field_name="maintenance mission provenance")
    return canonical


class TrustedControlPlaneService:
    __slots__ = ("_store", "_verifier", "_credential")

    def __init__(self, *, store: TrustedControlPlaneStore, verifier: TrustedSignatureVerifier, credential: str) -> None:
        if not isinstance(store, TrustedControlPlaneStore):
            raise TrustedControlPlaneServiceError("store must implement TrustedControlPlaneStore")
        if not isinstance(verifier, TrustedSignatureVerifier):
            raise TrustedControlPlaneServiceError("verifier must implement TrustedSignatureVerifier")
        _public_text(credential, field_name="credential", limit=16384)
        if not credential.isascii():
            raise TrustedControlPlaneServiceError("credential is invalid")
        self._store = store
        self._verifier = verifier
        self._credential = credential

    def _authorized(self, authorization: object) -> bool:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            return False
        supplied = authorization[7:]
        return bool(supplied) and hmac.compare_digest(supplied, self._credential)

    def dispatch(self, *, method: str, target: str, headers: Mapping[str, str], body: bytes = b"") -> ServiceResponse:
        try:
            if not self._authorized(headers.get("Authorization")):
                return ServiceResponse(401, {"status": "ERROR", "error": "UNAUTHORIZED"}).validate()
            parsed = urllib.parse.urlsplit(target)
            if parsed.scheme or parsed.netloc or parsed.fragment:
                raise TrustedControlPlaneServiceError("request target is invalid")

            if parsed.path == _HEALTH_PATH:
                if method != "GET" or parsed.query or body:
                    raise TrustedControlPlaneServiceError("health request is invalid")
                ready = self._store.ready() is True and self._verifier.ready() is True
                return ServiceResponse(200 if ready else 503, {"status": "READY" if ready else "NOT_READY", "provider_version": PROVIDER_VERSION}).validate()

            if parsed.path == _BOOTSTRAP_PATH:
                if method != "GET" or body:
                    raise TrustedControlPlaneServiceError("bootstrap request is invalid")
                q = _exact_query(parsed.query, _BOOTSTRAP_QUERY_FIELDS)
                binding = {"repository": _public_text(q["repository"], field_name="repository"), "pr_number": _positive_int_text(q["pr_number"], field_name="pr_number"), "base_sha": _sha(q["base_sha"], field_name="base_sha"), "head_sha": _sha(q["head_sha"], field_name="head_sha"), "merge_method": _public_text(q["merge_method"], field_name="merge_method", limit=16)}
                if binding["merge_method"] not in _MERGE_METHODS:
                    raise TrustedControlPlaneServiceError("merge_method is invalid")
                canonical = _canonical_record_tuple(self._store.lookup_pr_bootstrap_exact(**binding), expected_binding=binding)
                return ServiceResponse(200, {"provider_version": PROVIDER_VERSION, "records": list(canonical)}).validate()

            if parsed.path == _AUTHORITY_PATH:
                if method != "GET" or body:
                    raise TrustedControlPlaneServiceError("authority request is invalid")
                q = _exact_query(parsed.query, _AUTHORITY_QUERY_FIELDS)
                binding = {"repository": _public_text(q["repository"], field_name="repository"), "pr_number": _positive_int_text(q["pr_number"], field_name="pr_number"), "base_sha": _sha(q["base_sha"], field_name="base_sha"), "head_sha": _sha(q["head_sha"], field_name="head_sha"), "mission_id": _public_text(q["mission_id"], field_name="mission_id"), "grant_id": _public_text(q["grant_id"], field_name="grant_id")}
                canonical = _canonical_record_tuple(self._store.lookup_authority_exact(**binding), expected_binding=binding)
                return ServiceResponse(200, {"provider_version": PROVIDER_VERSION, "records": list(canonical)}).validate()

            if parsed.path == _BUILDER_SUBJECT_PATH:
                if method != "GET" or body:
                    raise TrustedControlPlaneServiceError("builder subject request is invalid")
                q = _exact_query(parsed.query, _BUILDER_QUERY_FIELDS)
                binding = {
                    "repository": _public_text(q["repository"], field_name="repository"),
                    "builder_subject_id": _public_text(q["builder_subject_id"], field_name="builder_subject_id"),
                    "builder_instance_id": _public_text(q["builder_instance_id"], field_name="builder_instance_id"),
                    "candidate_scope_digest": _digest(q["candidate_scope_digest"], field_name="candidate_scope_digest"),
                    "resource_scope_digest": _digest(q["resource_scope_digest"], field_name="resource_scope_digest"),
                    "capability_class": _public_text(q["capability_class"], field_name="capability_class", limit=64),
                }
                if binding["capability_class"] != _BUILDER_CAPABILITY:
                    raise TrustedControlPlaneServiceError("builder capability invalid")
                if self._store.ready() is not True:
                    return ServiceResponse(503, {"status": "ERROR", "error": "NOT_READY", "provider_version": PROVIDER_VERSION}).validate()
                canonical = _canonical_record_tuple(self._store.lookup_builder_subject_exact(**binding), expected_binding=binding)
                return ServiceResponse(200, {"provider_version": PROVIDER_VERSION, "records": list(canonical)}).validate()

            if parsed.path == _MAINTENANCE_POLICY_PATH:
                if method != "GET" or body:
                    raise TrustedControlPlaneServiceError("maintenance policy request is invalid")
                q = _exact_query(parsed.query, _MAINTENANCE_POLICY_QUERY_FIELDS)
                binding = {
                    "repository": _public_text(q["repository"], field_name="repository"),
                    "mission_id": _public_text(q["mission_id"], field_name="mission_id"),
                    "policy_id": _public_text(q["policy_id"], field_name="policy_id"),
                }
                records = self._store.lookup_maintenance_policy_exact(**binding)
                canonical = _canonical_record_tuple(records, expected_binding=binding)
                validated = tuple(validate_maintenance_policy_record(record, expected_binding=binding) for record in canonical)
                return ServiceResponse(200, {"provider_version": PROVIDER_VERSION, "records": list(validated)}).validate()

            if parsed.path == _MAINTENANCE_MISSION_PATH:
                if method != "GET" or body:
                    raise TrustedControlPlaneServiceError("maintenance mission request is invalid")
                q = _exact_query(parsed.query, _MAINTENANCE_MISSION_QUERY_FIELDS)
                binding = {
                    "repository": _public_text(q["repository"], field_name="repository"),
                    "mission_id": _public_text(q["mission_id"], field_name="mission_id"),
                }
                records = self._store.lookup_maintenance_mission_exact(**binding)
                canonical = _canonical_record_tuple(records, expected_binding=binding)
                validated = tuple(validate_maintenance_mission_record(record, expected_binding=binding) for record in canonical)
                return ServiceResponse(200, {"provider_version": PROVIDER_VERSION, "records": list(validated)}).validate()

            if parsed.path == _VERIFY_PATH:
                if method != "POST" or parsed.query:
                    raise TrustedControlPlaneServiceError("verify request is invalid")
                if headers.get("Content-Type") != "application/json":
                    raise TrustedControlPlaneServiceError("verify content type is invalid")
                item = _exact_json_body(body)
                payload_b64 = _public_text(item["payload_base64"], field_name="payload_base64", limit=_MAX_REQUEST_BODY)
                try:
                    payload = base64.b64decode(payload_b64, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise TrustedControlPlaneServiceError("signature payload is invalid") from exc
                verified = self._verifier.verify(payload, _public_text(item["signature"], field_name="signature", limit=16384), _public_text(item["key_id"], field_name="key_id"), _public_text(item["algorithm"], field_name="algorithm", limit=128))
                if type(verified) is not bool:
                    raise TrustedControlPlaneServiceError("trusted verifier result is invalid")
                return ServiceResponse(200, {"provider_version": PROVIDER_VERSION, "verified": verified}).validate()

            return ServiceResponse(404, {"status": "ERROR", "error": "NOT_FOUND"}).validate()
        except TrustedControlPlaneServiceError:
            return ServiceResponse(400, {"status": "ERROR", "error": "REQUEST_REJECTED"}).validate()
        except Exception:
            return ServiceResponse(503, {"status": "ERROR", "error": "TRUSTED_BACKEND_UNAVAILABLE"}).validate()


class _Handler(BaseHTTPRequestHandler):
    server_version = "CyberLionTrustedControlPlane/1.0"
    sys_version = ""

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _run(self) -> None:
        service = getattr(self.server, "cyber_lion_service", None)
        if not isinstance(service, TrustedControlPlaneService):
            self._write(ServiceResponse(503, {"status": "ERROR", "error": "SERVICE_UNAVAILABLE"}))
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write(ServiceResponse(400, {"status": "ERROR", "error": "REQUEST_REJECTED"}))
            return
        if content_length < 0 or content_length > _MAX_REQUEST_BODY:
            self._write(ServiceResponse(413, {"status": "ERROR", "error": "REQUEST_TOO_LARGE"}))
            return
        body = self.rfile.read(content_length) if content_length else b""
        headers = {"Authorization": self.headers.get("Authorization", ""), "Content-Type": self.headers.get("Content-Type", "")}
        self._write(service.dispatch(method=self.command, target=self.path, headers=headers, body=body))

    def _write(self, response: ServiceResponse) -> None:
        response.validate()
        raw = json.dumps(dict(response.payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _reject_method(self) -> None:
        self._write(ServiceResponse(405, {"status": "ERROR", "error": "METHOD_NOT_ALLOWED"}))

    do_GET = _run
    do_POST = _run
    do_HEAD = _reject_method
    do_PUT = _reject_method
    do_DELETE = _reject_method
    do_PATCH = _reject_method
    do_OPTIONS = _reject_method
    do_TRACE = _reject_method
    do_CONNECT = _reject_method


def _required_env(name: str, *, limit: int = 4096) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        raise TrustedControlPlaneServiceError("trusted service configuration is invalid")
    return value


def _load_factory(variable: str) -> Callable[[], object]:
    spec = _required_env(variable, limit=512)
    if not _PROVIDER_RE.fullmatch(spec):
        raise TrustedControlPlaneServiceError("trusted provider specification is invalid")
    module_name, attribute_name = spec.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute_name)
    except (ImportError, AttributeError) as exc:
        raise TrustedControlPlaneServiceError("trusted provider is unavailable") from exc
    if not callable(factory):
        raise TrustedControlPlaneServiceError("trusted provider is invalid")
    return factory


def build_service_from_environment() -> TrustedControlPlaneService:
    if _required_env("CYBER_LION_CP_PROVIDER_VERSION", limit=64) != PROVIDER_VERSION:
        raise TrustedControlPlaneServiceError("trusted provider version mismatch")
    credential_env = _required_env("CYBER_LION_CP_CREDENTIAL_ENV", limit=256)
    if not _ENV_REF_RE.fullmatch(credential_env):
        raise TrustedControlPlaneServiceError("credential reference is invalid")
    credential = _required_env(credential_env, limit=16384)
    store = _load_factory("CYBER_LION_CP_STORE_PROVIDER")()
    verifier = _load_factory("CYBER_LION_CP_VERIFIER_PROVIDER")()
    if not isinstance(store, TrustedControlPlaneStore):
        raise TrustedControlPlaneServiceError("trusted store provider is invalid")
    if not isinstance(verifier, TrustedSignatureVerifier):
        raise TrustedControlPlaneServiceError("trusted verifier provider is invalid")
    return TrustedControlPlaneService(store=store, verifier=verifier, credential=credential)


def serve(service: TrustedControlPlaneService, *, host: str, port: int) -> None:
    if not isinstance(service, TrustedControlPlaneService):
        raise TrustedControlPlaneServiceError("service is invalid")
    _public_text(host, field_name="bind host", limit=255)
    if type(port) is not int or not (1 <= port <= 65535):
        raise TrustedControlPlaneServiceError("bind port is invalid")
    server = ThreadingHTTPServer((host, port), _Handler)
    server.cyber_lion_service = service
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> int:
    try:
        service = build_service_from_environment()
        host = _required_env("CYBER_LION_CP_BIND_HOST", limit=255)
        port_raw = _required_env("CYBER_LION_CP_BIND_PORT", limit=5)
        if not port_raw.isascii() or not port_raw.isdigit():
            raise TrustedControlPlaneServiceError("bind port is invalid")
        serve(service, host=host, port=int(port_raw))
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())