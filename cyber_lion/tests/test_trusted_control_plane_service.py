import base64
import inspect
import json
import os
import unittest
from unittest.mock import patch

from cyber_lion.enterprise import trusted_control_plane_service as service

BASE = "a" * 40
HEAD = "b" * 40
D1 = "c" * 64
D2 = "d" * 64
TOKEN = "TOP-SECRET"


def bootstrap_record(**overrides):
    key = {"repository": "DonkeyJJLove/ai_platform", "pr_number": 40, "base_sha": BASE, "head_sha": HEAD, "merge_method": "merge"}
    key.update(overrides)
    return {"lookup_key": key, "mission_id": "m", "grant_id": "g"}


def authority_record(**overrides):
    key = {"repository": "DonkeyJJLove/ai_platform", "pr_number": 40, "base_sha": BASE, "head_sha": HEAD, "mission_id": "m", "grant_id": "g"}
    key.update(overrides)
    return {"lookup_key": key, "lineage": [{"grant_id": "g"}]}


def builder_record(**overrides):
    key = {
        "repository": "DonkeyJJLove/ai_platform",
        "builder_subject_id": "builder-1",
        "builder_instance_id": "instance-1",
        "candidate_scope_digest": D1,
        "resource_scope_digest": D2,
        "capability_class": "DETACHED_CANDIDATE_BUILD_ONLY",
    }
    key.update(overrides)
    return {"record_kind": "builder-subject", "lookup_key": key, "subject": {"sealed": True}}


class Store(service.TrustedControlPlaneStore):
    def __init__(self):
        self.bootstrap = ()
        self.authority = ()
        self.builders = ()
        self.is_ready = True
        self.bootstrap_calls = []
        self.authority_calls = []
        self.builder_calls = []

    def lookup_pr_bootstrap_exact(self, **kwargs):
        self.bootstrap_calls.append(kwargs); return self.bootstrap

    def lookup_authority_exact(self, **kwargs):
        self.authority_calls.append(kwargs); return self.authority

    def lookup_builder_subject_exact(self, **kwargs):
        self.builder_calls.append(kwargs); return self.builders

    def ready(self): return self.is_ready


class Verifier(service.TrustedSignatureVerifier):
    def __init__(self): self.result = True; self.is_ready = True; self.calls = []
    def verify(self, payload, signature, key_id, algorithm): self.calls.append((payload, signature, key_id, algorithm)); return self.result
    def ready(self): return self.is_ready


class TrustedControlPlaneServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(); self.verifier = Verifier()
        self.app = service.TrustedControlPlaneService(store=self.store, verifier=self.verifier, credential=TOKEN)
        self.auth = {"Authorization": "Bearer " + TOKEN}

    def dispatch(self, method, target, *, body=b"", content_type=""):
        headers = dict(self.auth)
        if content_type: headers["Content-Type"] = content_type
        return self.app.dispatch(method=method, target=target, headers=headers, body=body)

    def test_read_only_interfaces_have_expected_surface(self):
        self.assertEqual(set(service.TrustedControlPlaneStore.__abstractmethods__), {"lookup_pr_bootstrap_exact", "lookup_authority_exact", "lookup_builder_subject_exact", "ready"})
        self.assertEqual(set(service.TrustedSignatureVerifier.__abstractmethods__), {"verify", "ready"})

    def test_builder_subject_endpoint_exact_authenticated_binding(self):
        record = builder_record(); self.store.builders = (record,)
        query = (
            "repository=DonkeyJJLove%2Fai_platform&builder_subject_id=builder-1&builder_instance_id=instance-1"
            f"&candidate_scope_digest={D1}&resource_scope_digest={D2}&capability_class=DETACHED_CANDIDATE_BUILD_ONLY"
        )
        response = self.dispatch("GET", "/v1/builder-subject?" + query)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.payload, {"provider_version": "1.0.0", "records": [record]})
        self.assertEqual(len(self.store.builder_calls), 1)

    def test_builder_subject_requires_auth_ready_store_exact_query_and_get_only(self):
        valid = (
            "repository=r&builder_subject_id=b&builder_instance_id=i"
            f"&candidate_scope_digest={D1}&resource_scope_digest={D2}&capability_class=DETACHED_CANDIDATE_BUILD_ONLY"
        )
        unauth = self.app.dispatch(method="GET", target="/v1/builder-subject?" + valid, headers={})
        self.assertEqual(unauth.status, 401)
        self.assertEqual(self.dispatch("POST", "/v1/builder-subject?" + valid).status, 400)
        self.assertEqual(self.dispatch("GET", "/v1/builder-subject?" + valid + "&extra=x").status, 400)
        self.assertEqual(self.dispatch("GET", "/v1/builder-subject?" + valid.replace(D1, "bad")).status, 400)
        self.assertEqual(self.dispatch("GET", "/v1/builder-subject?" + valid.replace("DETACHED_CANDIDATE_BUILD_ONLY", "MERGE")).status, 400)
        self.store.is_ready = False
        self.assertEqual(self.dispatch("GET", "/v1/builder-subject?" + valid).status, 503)

    def test_builder_store_mismatched_binding_is_rejected(self):
        self.store.builders = (builder_record(builder_instance_id="other"),)
        query = (
            "repository=DonkeyJJLove%2Fai_platform&builder_subject_id=builder-1&builder_instance_id=instance-1"
            f"&candidate_scope_digest={D1}&resource_scope_digest={D2}&capability_class=DETACHED_CANDIDATE_BUILD_ONLY"
        )
        self.assertEqual(self.dispatch("GET", "/v1/builder-subject?" + query).status, 400)

    def test_existing_bootstrap_authority_verify_and_health_semantics_preserved(self):
        self.store.bootstrap = (bootstrap_record(),)
        bq = f"repository=DonkeyJJLove%2Fai_platform&pr_number=40&base_sha={BASE}&head_sha={HEAD}&merge_method=merge"
        self.assertEqual(self.dispatch("GET", "/v1/pr-authority-bootstrap?" + bq).status, 200)
        self.store.authority = (authority_record(),)
        aq = f"repository=DonkeyJJLove%2Fai_platform&pr_number=40&base_sha={BASE}&head_sha={HEAD}&mission_id=m&grant_id=g"
        self.assertEqual(self.dispatch("GET", "/v1/authority-lineage?" + aq).status, 200)
        raw = json.dumps({"payload_base64": base64.b64encode(b"payload").decode(), "signature": "sig", "key_id": "key", "algorithm": "ed25519"}).encode()
        self.assertEqual(self.dispatch("POST", "/v1/verify-signature", body=raw, content_type="application/json").payload["verified"], True)
        self.assertEqual(self.dispatch("GET", "/healthz").payload, {"status": "READY", "provider_version": "1.0.0"})

    def test_backend_failure_is_sanitized(self):
        class Broken(Store):
            def lookup_builder_subject_exact(self, **kwargs): raise RuntimeError("SECRET")
        app = service.TrustedControlPlaneService(store=Broken(), verifier=self.verifier, credential=TOKEN)
        q = f"repository=r&builder_subject_id=b&builder_instance_id=i&candidate_scope_digest={D1}&resource_scope_digest={D2}&capability_class=DETACHED_CANDIDATE_BUILD_ONLY"
        response = app.dispatch(method="GET", target="/v1/builder-subject?" + q, headers=self.auth)
        self.assertEqual(response.status, 503)
        self.assertNotIn("SECRET", json.dumps(response.payload))

    def test_environment_builder_preserved(self):
        fake_module = type(os)("fake_cp_providers")
        fake_module.make_store = lambda: Store(); fake_module.make_verifier = lambda: Verifier()
        env = {"CYBER_LION_CP_PROVIDER_VERSION": "1.0.0", "CYBER_LION_CP_CREDENTIAL_ENV": "CYBER_LION_CP_TOKEN", "CYBER_LION_CP_TOKEN": TOKEN, "CYBER_LION_CP_STORE_PROVIDER": "fake_cp_providers:make_store", "CYBER_LION_CP_VERIFIER_PROVIDER": "fake_cp_providers:make_verifier"}
        with patch.dict(os.environ, env, clear=True), patch.dict("sys.modules", {"fake_cp_providers": fake_module}):
            built = service.build_service_from_environment()
        self.assertIsInstance(built, service.TrustedControlPlaneService)

    def test_no_authority_mutation_debug_or_subprocess_surface(self):
        source = inspect.getsource(service).lower()
        for token in ("github", "merge_pull_request", "advance_canonical", "register_canonical", "consume(", "subprocess", "os.system", "eval(", "exec(", "traceback", "print("):
            self.assertNotIn(token, source)
        self.assertIn("hmac.compare_digest", source)
        for name in ("do_HEAD", "do_PUT", "do_DELETE", "do_PATCH", "do_OPTIONS", "do_TRACE", "do_CONNECT"):
            self.assertIs(getattr(service._Handler, name), service._Handler._reject_method)


if __name__ == "__main__":
    unittest.main()