import base64
import inspect
import json
import os
import unittest
from unittest.mock import patch

from cyber_lion.enterprise import trusted_control_plane_service as service


BASE = "a" * 40
HEAD = "b" * 40
TOKEN = "TOP-SECRET"


def bootstrap_record(**overrides):
    key = {
        "repository": "DonkeyJJLove/ai_platform",
        "pr_number": 40,
        "base_sha": BASE,
        "head_sha": HEAD,
        "merge_method": "merge",
    }
    key.update(overrides)
    return {"lookup_key": key, "mission_id": "m", "grant_id": "g"}


def authority_record(**overrides):
    key = {
        "repository": "DonkeyJJLove/ai_platform",
        "pr_number": 40,
        "base_sha": BASE,
        "head_sha": HEAD,
        "mission_id": "m",
        "grant_id": "g",
    }
    key.update(overrides)
    return {"lookup_key": key, "lineage": [{"grant_id": "g"}]}


class Store(service.TrustedControlPlaneStore):
    def __init__(self):
        self.bootstrap = ()
        self.authority = ()
        self.is_ready = True
        self.bootstrap_calls = []
        self.authority_calls = []

    def lookup_pr_bootstrap_exact(self, **kwargs):
        self.bootstrap_calls.append(kwargs)
        return self.bootstrap

    def lookup_authority_exact(self, **kwargs):
        self.authority_calls.append(kwargs)
        return self.authority

    def ready(self):
        return self.is_ready


class Verifier(service.TrustedSignatureVerifier):
    def __init__(self):
        self.result = True
        self.is_ready = True
        self.calls = []

    def verify(self, payload, signature, key_id, algorithm):
        self.calls.append((payload, signature, key_id, algorithm))
        return self.result

    def ready(self):
        return self.is_ready


class TrustedControlPlaneServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.verifier = Verifier()
        self.app = service.TrustedControlPlaneService(
            store=self.store,
            verifier=self.verifier,
            credential=TOKEN,
        )
        self.auth = {"Authorization": "Bearer " + TOKEN}

    def dispatch(self, method, target, *, body=b"", content_type=""):
        headers = dict(self.auth)
        if content_type:
            headers["Content-Type"] = content_type
        return self.app.dispatch(
            method=method,
            target=target,
            headers=headers,
            body=body,
        )

    def test_read_only_interfaces_have_only_expected_abstract_surface(self):
        store_abstract = set(service.TrustedControlPlaneStore.__abstractmethods__)
        verifier_abstract = set(service.TrustedSignatureVerifier.__abstractmethods__)
        self.assertEqual(
            store_abstract,
            {"lookup_pr_bootstrap_exact", "lookup_authority_exact", "ready"},
        )
        self.assertEqual(verifier_abstract, {"verify", "ready"})

    def test_bootstrap_endpoint_exact_binding_and_response(self):
        record = bootstrap_record()
        self.store.bootstrap = (record,)
        query = (
            "repository=DonkeyJJLove%2Fai_platform&pr_number=40"
            f"&base_sha={BASE}&head_sha={HEAD}&merge_method=merge"
        )
        response = self.dispatch(
            "GET", "/v1/pr-authority-bootstrap?" + query
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(
            response.payload,
            {"provider_version": "1.0.0", "records": [record]},
        )
        self.assertEqual(
            self.store.bootstrap_calls,
            [{
                "repository": "DonkeyJJLove/ai_platform",
                "pr_number": 40,
                "base_sha": BASE,
                "head_sha": HEAD,
                "merge_method": "merge",
            }],
        )

    def test_authority_endpoint_exact_binding_and_response(self):
        record = authority_record()
        self.store.authority = (record,)
        query = (
            "repository=DonkeyJJLove%2Fai_platform&pr_number=40"
            f"&base_sha={BASE}&head_sha={HEAD}&mission_id=m&grant_id=g"
        )
        response = self.dispatch("GET", "/v1/authority-lineage?" + query)
        self.assertEqual(response.status, 200)
        self.assertEqual(
            response.payload,
            {"provider_version": "1.0.0", "records": [record]},
        )
        self.assertEqual(len(self.store.authority_calls), 1)

    def test_verifier_endpoint_exact_body_and_boolean_result(self):
        raw = json.dumps({
            "payload_base64": base64.b64encode(b"payload").decode("ascii"),
            "signature": "sig",
            "key_id": "key-1",
            "algorithm": "ed25519",
        }).encode()
        response = self.dispatch(
            "POST",
            "/v1/verify-signature",
            body=raw,
            content_type="application/json",
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(
            response.payload,
            {"provider_version": "1.0.0", "verified": True},
        )
        self.assertEqual(
            self.verifier.calls,
            [(b"payload", "sig", "key-1", "ed25519")],
        )
        self.verifier.result = False
        response = self.dispatch(
            "POST",
            "/v1/verify-signature",
            body=raw,
            content_type="application/json",
        )
        self.assertEqual(response.payload["verified"], False)

    def test_health_requires_auth_and_reports_readiness(self):
        response = self.dispatch("GET", "/healthz")
        self.assertEqual(
            (response.status, response.payload),
            (200, {"status": "READY", "provider_version": "1.0.0"}),
        )
        self.store.is_ready = False
        response = self.dispatch("GET", "/healthz")
        self.assertEqual(response.status, 503)
        self.assertEqual(response.payload["status"], "NOT_READY")

        unauthorized = self.app.dispatch(
            method="GET", target="/healthz", headers={}, body=b""
        )
        self.assertEqual(unauthorized.status, 401)
        self.assertEqual(
            unauthorized.payload,
            {"status": "ERROR", "error": "UNAUTHORIZED"},
        )

    def test_authentication_is_bearer_exact_and_secret_not_returned(self):
        cases = [
            {},
            {"Authorization": TOKEN},
            {"Authorization": "Bearer wrong"},
            {"Authorization": "bearer " + TOKEN},
        ]
        for headers in cases:
            with self.subTest(headers=headers):
                response = self.app.dispatch(
                    method="GET", target="/healthz", headers=headers
                )
                self.assertEqual(response.status, 401)
                self.assertNotIn(TOKEN, json.dumps(response.payload))

    def test_bootstrap_query_rejects_missing_unknown_duplicate_and_bad_values(self):
        valid = (
            "repository=r&pr_number=1"
            f"&base_sha={BASE}&head_sha={HEAD}&merge_method=merge"
        )
        cases = [
            valid + "&extra=1",
            valid.replace("&merge_method=merge", ""),
            valid + "&pr_number=2",
            valid.replace("pr_number=1", "pr_number=0"),
            valid.replace("base_sha=" + BASE, "base_sha=short"),
            valid.replace("merge_method=merge", "merge_method=octopus"),
        ]
        for query in cases:
            with self.subTest(query=query):
                response = self.dispatch(
                    "GET", "/v1/pr-authority-bootstrap?" + query
                )
                self.assertEqual(response.status, 400)
        self.assertEqual(self.store.bootstrap_calls, [])

    def test_authority_store_cannot_return_mismatched_binding(self):
        self.store.authority = (authority_record(head_sha="c" * 40),)
        query = (
            "repository=DonkeyJJLove%2Fai_platform&pr_number=40"
            f"&base_sha={BASE}&head_sha={HEAD}&mission_id=m&grant_id=g"
        )
        response = self.dispatch("GET", "/v1/authority-lineage?" + query)
        self.assertEqual(response.status, 400)
        self.assertEqual(response.payload["error"], "REQUEST_REJECTED")

    def test_bootstrap_store_cannot_return_mismatched_or_mutable_result_type(self):
        query = (
            "repository=DonkeyJJLove%2Fai_platform&pr_number=40"
            f"&base_sha={BASE}&head_sha={HEAD}&merge_method=merge"
        )
        self.store.bootstrap = (bootstrap_record(head_sha="c" * 40),)
        response = self.dispatch(
            "GET", "/v1/pr-authority-bootstrap?" + query
        )
        self.assertEqual(response.status, 400)

        self.store.bootstrap = [bootstrap_record()]  # type: ignore[assignment]
        response = self.dispatch(
            "GET", "/v1/pr-authority-bootstrap?" + query
        )
        self.assertEqual(response.status, 400)

    def test_verify_requires_exact_json_content_type_and_fields(self):
        base = {
            "payload_base64": "eA==",
            "signature": "sig",
            "key_id": "key",
            "algorithm": "ed25519",
        }
        cases = [
            (base, ""),
            ({**base, "extra": 1}, "application/json"),
            ({k: v for k, v in base.items() if k != "key_id"}, "application/json"),
            ({**base, "payload_base64": "%%%bad%%%"}, "application/json"),
        ]
        for payload, content_type in cases:
            with self.subTest(payload=payload, content_type=content_type):
                response = self.dispatch(
                    "POST",
                    "/v1/verify-signature",
                    body=json.dumps(payload).encode(),
                    content_type=content_type,
                )
                self.assertEqual(response.status, 400)
        self.assertEqual(self.verifier.calls, [])

    def test_backend_exceptions_and_invalid_verifier_results_fail_closed(self):
        class BrokenStore(Store):
            def ready(self):
                raise RuntimeError("TOP-SECRET backend details")

        app = service.TrustedControlPlaneService(
            store=BrokenStore(), verifier=self.verifier, credential=TOKEN
        )
        response = app.dispatch(
            method="GET", target="/healthz", headers=self.auth
        )
        self.assertEqual(response.status, 503)
        self.assertEqual(
            response.payload,
            {"status": "ERROR", "error": "TRUSTED_BACKEND_UNAVAILABLE"},
        )
        self.assertNotIn("TOP-SECRET", json.dumps(response.payload))

        self.verifier.result = 1
        raw = json.dumps({
            "payload_base64": "eA==",
            "signature": "s",
            "key_id": "k",
            "algorithm": "a",
        }).encode()
        response = self.dispatch(
            "POST",
            "/v1/verify-signature",
            body=raw,
            content_type="application/json",
        )
        self.assertEqual(response.status, 400)

    def test_unknown_routes_and_methods_never_reach_store(self):
        response = self.dispatch("GET", "/admin")
        self.assertEqual(response.status, 404)
        response = self.dispatch("POST", "/v1/authority-lineage")
        self.assertEqual(response.status, 400)
        self.assertEqual(self.store.authority_calls, [])

    def test_request_body_bound_is_enforced_by_parser_and_handler_constant(self):
        oversized = b"x" * (service._MAX_REQUEST_BODY + 1)
        response = self.dispatch(
            "POST",
            "/v1/verify-signature",
            body=oversized,
            content_type="application/json",
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(service._MAX_REQUEST_BODY, 128 * 1024)

    def test_environment_builder_uses_credential_reference_and_trusted_factories(self):
        class LocalStore(Store):
            pass

        class LocalVerifier(Verifier):
            pass

        fake_module = type(os)("fake_cp_providers")
        fake_module.make_store = lambda: LocalStore()
        fake_module.make_verifier = lambda: LocalVerifier()

        env = {
            "CYBER_LION_CP_PROVIDER_VERSION": "1.0.0",
            "CYBER_LION_CP_CREDENTIAL_ENV": "CYBER_LION_CP_TOKEN",
            "CYBER_LION_CP_TOKEN": TOKEN,
            "CYBER_LION_CP_STORE_PROVIDER": "fake_cp_providers:make_store",
            "CYBER_LION_CP_VERIFIER_PROVIDER": "fake_cp_providers:make_verifier",
        }
        with patch.dict(os.environ, env, clear=True), patch.dict(
            "sys.modules", {"fake_cp_providers": fake_module}
        ):
            built = service.build_service_from_environment()
        self.assertIsInstance(built, service.TrustedControlPlaneService)

    def test_environment_builder_rejects_version_bad_reference_and_bad_provider(self):
        good = {
            "CYBER_LION_CP_PROVIDER_VERSION": "1.0.0",
            "CYBER_LION_CP_CREDENTIAL_ENV": "CYBER_LION_CP_TOKEN",
            "CYBER_LION_CP_TOKEN": TOKEN,
            "CYBER_LION_CP_STORE_PROVIDER": "x:y",
            "CYBER_LION_CP_VERIFIER_PROVIDER": "x:z",
        }
        cases = [
            {**good, "CYBER_LION_CP_PROVIDER_VERSION": "2.0.0"},
            {**good, "CYBER_LION_CP_CREDENTIAL_ENV": "bad-name"},
            {k: v for k, v in good.items() if k != "CYBER_LION_CP_TOKEN"},
        ]
        for env in cases:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(service.TrustedControlPlaneServiceError):
                    service.build_service_from_environment()

    def test_deployable_entrypoint_exists_and_main_sanitizes_failure(self):
        self.assertTrue(callable(service.main))
        self.assertTrue(callable(service.serve))
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(service.main(), 2)

    def test_module_has_no_github_authority_mutation_debug_or_subprocess_surface(self):
        source = inspect.getsource(service).lower()
        forbidden = [
            "github",
            "merge_pull_request",
            "advance_canonical",
            "register_canonical",
            "consume(",
            "subprocess",
            "os.system",
            "eval(",
            "exec(",
            "traceback",
            "print(",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

        self.assertIn("hmac.compare_digest", source)
        self.assertIn("max_request_body", source)
        self.assertIn('if __name__ == "__main__"', source)
        for name in (
            "do_HEAD",
            "do_PUT",
            "do_DELETE",
            "do_PATCH",
            "do_OPTIONS",
            "do_TRACE",
            "do_CONNECT",
        ):
            self.assertIs(
                getattr(service._Handler, name),
                service._Handler._reject_method,
            )


if __name__ == "__main__":
    unittest.main()
