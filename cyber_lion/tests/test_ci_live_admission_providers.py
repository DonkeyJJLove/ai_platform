import io
import inspect
import json
import os
import types
import unittest
import urllib.error
from contextlib import contextmanager
from unittest.mock import patch

from cyber_lion.enterprise import ci_live_admission_providers as providers


BASE = "a" * 40
HEAD = "b" * 40


class _Response:
    def __init__(self, payload: object, *, status: int = 200, content_length: str | None = None):
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def read(self, size: int = -1) -> bytes:
        return self._raw[:size] if size >= 0 else self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Opener:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


class CILiveAdmissionProvidersTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "CYBER_LION_PROVIDER_VERSION": providers.PROVIDER_VERSION,
            "CYBER_LION_TRUSTED_BASE_SHA": BASE,
            "CYBER_LION_CONTROL_PLANE_ORIGIN": "https://control.example",
            "CYBER_LION_CONTROL_PLANE_CREDENTIAL_ENV": "CYBER_LION_CP_TOKEN",
            "CYBER_LION_CP_TOKEN": "SUPER-SECRET",
        }

    @contextmanager
    def runtime(self, opener: _Opener):
        with patch.dict(os.environ, self.env, clear=True), patch(
            "urllib.request.build_opener", return_value=opener
        ):
            yield opener

    def test_public_callables_have_exact_signatures(self):
        self.assertEqual(
            tuple(inspect.signature(providers.bootstrap_lookup_exact).parameters),
            ("repository", "pr_number", "base_sha", "head_sha", "merge_method"),
        )
        self.assertEqual(
            tuple(inspect.signature(providers.authority_lookup_exact).parameters),
            (
                "repository",
                "pr_number",
                "base_sha",
                "head_sha",
                "mission_id",
                "grant_id",
            ),
        )
        self.assertEqual(
            tuple(inspect.signature(providers.verify_signature).parameters),
            ("payload", "signature", "key_id", "algorithm"),
        )

    def test_bootstrap_exact_get_request_and_tuple_response(self):
        record = {"lookup_key": {"x": "y"}}
        opener = _Opener(
            _Response({"provider_version": providers.PROVIDER_VERSION, "records": [record]})
        )
        with self.runtime(opener):
            result = providers.bootstrap_lookup_exact(
                repository="DonkeyJJLove/ai_platform",
                pr_number=39,
                base_sha=BASE,
                head_sha=HEAD,
                merge_method="merge",
            )
        self.assertEqual(result, (record,))
        request, timeout = opener.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 10)
        self.assertTrue(request.full_url.startswith("https://control.example/v1/pr-authority-bootstrap?"))
        self.assertIn("repository=DonkeyJJLove%2Fai_platform", request.full_url)
        self.assertIn("pr_number=39", request.full_url)
        self.assertIn("base_sha=" + BASE, request.full_url)
        self.assertIn("head_sha=" + HEAD, request.full_url)
        self.assertIn("merge_method=merge", request.full_url)
        self.assertNotIn("SUPER-SECRET", request.full_url)
        self.assertEqual(request.headers["Authorization"], "Bearer SUPER-SECRET")
        self.assertEqual(request.headers["X-cyber-lion-provider-version"], providers.PROVIDER_VERSION)
        self.assertEqual(request.headers["X-cyber-lion-trusted-base-sha"], BASE)

    def test_authority_exact_get_request(self):
        opener = _Opener(
            _Response({"provider_version": providers.PROVIDER_VERSION, "records": []})
        )
        with self.runtime(opener):
            result = providers.authority_lookup_exact(
                repository="DonkeyJJLove/ai_platform",
                pr_number=39,
                base_sha=BASE,
                head_sha=HEAD,
                mission_id="mission-1",
                grant_id="grant-1",
            )
        self.assertEqual(result, ())
        request, _ = opener.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("/v1/authority-lineage?", request.full_url)
        self.assertIn("mission_id=mission-1", request.full_url)
        self.assertIn("grant_id=grant-1", request.full_url)

    def test_verifier_post_and_boolean_semantics(self):
        opener = _Opener(
            _Response({"provider_version": providers.PROVIDER_VERSION, "verified": True})
        )
        with self.runtime(opener):
            self.assertTrue(providers.verify_signature(b"abc", "sig", "key-1", "ed25519"))
        request, _ = opener.calls[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, "https://control.example/v1/verify-signature")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            body,
            {
                "algorithm": "ed25519",
                "key_id": "key-1",
                "payload_base64": "YWJj",
                "signature": "sig",
            },
        )

        opener = _Opener(
            _Response({"provider_version": providers.PROVIDER_VERSION, "verified": False})
        )
        with self.runtime(opener):
            self.assertFalse(providers.verify_signature(b"abc", "sig", "key-1", "ed25519"))

    def test_https_origin_is_strict(self):
        invalid = [
            "http://control.example",
            "https://control.example/path",
            "https://control.example/?q=1",
            "https://control.example/#frag",
            "https://user:pass@control.example",
            "file:///tmp/x",
        ]
        for origin in invalid:
            with self.subTest(origin=origin):
                self.env["CYBER_LION_CONTROL_PLANE_ORIGIN"] = origin
                opener = _Opener(
                    _Response({"provider_version": providers.PROVIDER_VERSION, "records": []})
                )
                with self.runtime(opener), self.assertRaises(providers.CILiveAdmissionProviderError):
                    providers.bootstrap_lookup_exact(
                        repository="r", pr_number=1, base_sha=BASE, head_sha=HEAD, merge_method="merge"
                    )
                self.assertEqual(opener.calls, [])
        self.env["CYBER_LION_CONTROL_PLANE_ORIGIN"] = "https://control.example"

    def test_credential_reference_and_missing_secret_fail_closed(self):
        self.env["CYBER_LION_CONTROL_PLANE_CREDENTIAL_ENV"] = "bad-name"
        with self.runtime(_Opener()), self.assertRaises(providers.CILiveAdmissionProviderError):
            providers.bootstrap_lookup_exact(
                repository="r", pr_number=1, base_sha=BASE, head_sha=HEAD, merge_method="merge"
            )
        self.env["CYBER_LION_CONTROL_PLANE_CREDENTIAL_ENV"] = "CYBER_LION_CP_TOKEN"
        del self.env["CYBER_LION_CP_TOKEN"]
        with self.runtime(_Opener()), self.assertRaises(providers.CILiveAdmissionProviderError):
            providers.bootstrap_lookup_exact(
                repository="r", pr_number=1, base_sha=BASE, head_sha=HEAD, merge_method="merge"
            )

    def test_provider_version_and_base_sha_bindings_are_required(self):
        self.env["CYBER_LION_PROVIDER_VERSION"] = "9.9.9"
        with self.runtime(_Opener()), self.assertRaises(providers.CILiveAdmissionProviderError):
            providers.bootstrap_lookup_exact(
                repository="r", pr_number=1, base_sha=BASE, head_sha=HEAD, merge_method="merge"
            )
        self.env["CYBER_LION_PROVIDER_VERSION"] = providers.PROVIDER_VERSION
        self.env["CYBER_LION_TRUSTED_BASE_SHA"] = "short"
        with self.runtime(_Opener()), self.assertRaises(providers.CILiveAdmissionProviderError):
            providers.bootstrap_lookup_exact(
                repository="r", pr_number=1, base_sha=BASE, head_sha=HEAD, merge_method="merge"
            )

    def test_response_envelope_is_exact_and_version_bound(self):
        cases = [
            {"provider_version": providers.PROVIDER_VERSION, "records": [], "extra": 1},
            {"provider_version": "9.9.9", "records": []},
            {"provider_version": providers.PROVIDER_VERSION, "records": "bad"},
            {"provider_version": providers.PROVIDER_VERSION, "records": [1]},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.runtime(_Opener(_Response(payload))), self.assertRaises(
                    providers.CILiveAdmissionProviderError
                ):
                    providers.bootstrap_lookup_exact(
                        repository="r", pr_number=1, base_sha=BASE, head_sha=HEAD, merge_method="merge"
                    )

    def test_verifier_envelope_is_exact(self):
        cases = [
            {"provider_version": providers.PROVIDER_VERSION, "verified": True, "extra": 1},
            {"provider_version": "2.0.0", "verified": True},
            {"provider_version": providers.PROVIDER_VERSION, "verified": 1},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.runtime(_Opener(_Response(payload))), self.assertRaises(
                    providers.CILiveAdmissionProviderError
                ):
                    providers.verify_signature(b"x", "s", "k", "a")

    def test_transport_failure_is_sanitized_and_secret_not_exposed(self):
        opener = _Opener(error=RuntimeError("Authorization: Bearer SUPER-SECRET"))
        with self.runtime(opener):
            with self.assertRaises(providers.CILiveAdmissionProviderError) as cm:
                providers.bootstrap_lookup_exact(
                    repository="r", pr_number=1, base_sha=BASE, head_sha=HEAD, merge_method="merge"
                )
        self.assertNotIn("SUPER-SECRET", str(cm.exception))
        self.assertEqual(str(cm.exception), "trusted control-plane request failed")

    def test_oversized_and_malformed_responses_fail_closed(self):
        opener = _Opener(
            _Response(
                {"provider_version": providers.PROVIDER_VERSION, "records": []},
                content_length=str(1024 * 1024 + 1),
            )
        )
        with self.runtime(opener), self.assertRaises(providers.CILiveAdmissionProviderError):
            providers.bootstrap_lookup_exact(
                repository="r", pr_number=1, base_sha=BASE, head_sha=HEAD, merge_method="merge"
            )

        class BadResponse(_Response):
            def __init__(self):
                self.status = 200
                self.headers = {}
                self._raw = b"not-json"

        with self.runtime(_Opener(BadResponse())), self.assertRaises(
            providers.CILiveAdmissionProviderError
        ):
            providers.bootstrap_lookup_exact(
                repository="r", pr_number=1, base_sha=BASE, head_sha=HEAD, merge_method="merge"
            )

    def test_redirect_handler_always_denies(self):
        handler = providers._NoRedirect()
        with self.assertRaises(providers.CILiveAdmissionProviderError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://other.example")

    def test_module_has_no_mutation_or_pr_head_execution_surface(self):
        source = inspect.getsource(providers)
        forbidden = [
            "subprocess",
            "os.system",
            "eval(",
            "exec(",
            "github",
            "merge_pull_request",
            "create_",
            "update_",
            "delete_",
            "checkout",
            "pull_request.head",
            "requests",
            "httpx",
        ]
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source.lower())

        public = {
            name
            for name, value in vars(providers).items()
            if callable(value) and not name.startswith("_")
        }
        self.assertTrue(
            {"bootstrap_lookup_exact", "authority_lookup_exact", "verify_signature"}
            <= public
        )


if __name__ == "__main__":
    unittest.main()
