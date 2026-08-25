from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from cyber_lion.enterprise import ci_live_admission_providers as providers

BASE = "a" * 40


class _Response:
    status = 200
    headers = {}

    def __init__(self, verified: bool = True):
        self.raw = json.dumps(
            {"provider_version": providers.PROVIDER_VERSION, "verified": verified},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def read(self, size: int = -1) -> bytes:
        return self.raw if size < 0 else self.raw[:size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Opener:
    def __init__(self, response=None):
        self.response = response or _Response()
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        return self.response


class SignatureVerificationBoundaryTests(unittest.TestCase):
    def setUp(self):
        providers.SignatureVerificationNetworkBoundary._observed.clear()
        self.env = {
            "CYBER_LION_PROVIDER_VERSION": providers.PROVIDER_VERSION,
            "CYBER_LION_TRUSTED_BASE_SHA": BASE,
            "CYBER_LION_CONTROL_PLANE_ORIGIN": "https://control.example",
            "CYBER_LION_CONTROL_PLANE_CREDENTIAL_ENV": "CYBER_LION_CP_TOKEN",
            "CYBER_LION_CP_TOKEN": "secret",
            "GITHUB_RUN_ID": "32999990001",
            "GITHUB_RUN_ATTEMPT": "1",
        }

    def test_exact_replay_in_same_ci_epoch_causes_one_network_effect(self):
        opener = _Opener(_Response(True))
        with patch.dict(os.environ, self.env, clear=True), patch(
            "urllib.request.build_opener", return_value=opener
        ):
            self.assertTrue(providers.verify_signature(b"payload", "sig", "key", "ed25519"))
            self.assertTrue(providers.verify_signature(b"payload", "sig", "key", "ed25519"))
        self.assertEqual(len(opener.calls), 1)
        request, timeout = opener.calls[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, "https://control.example/v1/verify-signature")
        self.assertEqual(timeout, 10)
        self.assertRegex(request.headers["X-cyber-lion-request-digest"], r"^[0-9a-f]{64}$")

    def test_cross_epoch_replay_is_a_distinct_effect_binding(self):
        opener = _Opener(_Response(True))
        with patch.dict(os.environ, self.env, clear=True), patch(
            "urllib.request.build_opener", return_value=opener
        ):
            self.assertTrue(providers.verify_signature(b"payload", "sig", "key", "ed25519"))
            os.environ["GITHUB_RUN_ATTEMPT"] = "2"
            self.assertTrue(providers.verify_signature(b"payload", "sig", "key", "ed25519"))
        self.assertEqual(len(opener.calls), 2)
        digests = [call[0].headers["X-cyber-lion-request-digest"] for call in opener.calls]
        self.assertNotEqual(digests[0], digests[1])

    def test_effect_time_configuration_drift_is_denied_before_post(self):
        opener = _Opener(_Response(True))
        stable = ("https://control.example", "secret", BASE)
        drifted = ("https://other.example", "secret", BASE)
        with patch.dict(os.environ, self.env, clear=True), patch(
            "urllib.request.build_opener", return_value=opener
        ), patch.object(providers, "_runtime_config", side_effect=[stable, drifted]):
            with self.assertRaisesRegex(
                providers.CILiveAdmissionProviderError,
                "configuration changed before effect",
            ):
                providers.verify_signature(b"payload", "sig", "key", "ed25519")
        self.assertEqual(opener.calls, [])

    def test_run_identity_must_be_complete_and_canonical(self):
        for run_id, attempt in (("0", "1"), ("abc", "1"), ("123", "0"), ("123", "x")):
            env = dict(self.env, GITHUB_RUN_ID=run_id, GITHUB_RUN_ATTEMPT=attempt)
            with self.subTest(run_id=run_id, attempt=attempt), patch.dict(
                os.environ, env, clear=True
            ), self.assertRaises(providers.CILiveAdmissionProviderError):
                providers.verify_signature(b"payload", "sig", "key", "ed25519")

    def test_no_generic_caller_selected_post_surface_remains(self):
        import inspect

        source = inspect.getsource(providers)
        self.assertNotIn("def _request_json", source)
        self.assertNotIn("method: str", source)
        self.assertEqual(source.count('method="POST"'), 1)
        self.assertIn("SignatureVerificationNetworkBoundary.verify", source)
        self.assertNotIn("/dispatches", source)
        self.assertNotIn("git/refs", source)


if __name__ == "__main__":
    unittest.main()
