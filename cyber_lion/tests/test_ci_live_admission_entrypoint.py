from __future__ import annotations

import ast
import io
import json
import sys
import types
import unittest
from contextlib import redirect_stdout
from dataclasses import asdict
from pathlib import Path

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import (
    AuthorityLookupKey,
    canonical_pr_authority_resource,
    canonical_source_lineage_digest,
)
from cyber_lion.enterprise.ci_live_admission_entrypoint import (
    CILiveAdmissionEntrypointError,
    execute,
    load_bootstrap,
    load_issuer_key_bindings,
    load_pr_state,
    load_provider,
    main,
)

REPO = "DonkeyJJLove/ai_platform"
BASE = "a" * 40
HEAD = "b" * 40
POLICY = "sha256:" + "1" * 64
OBS = "sha256:" + "2" * 64


class CILiveAdmissionEntrypointTests(unittest.TestCase):
    def _fixture(self, suffix: str, *, records: int = 1, signature: str = "sig"):
        mission = f"ci-entry-{suffix}"
        grant_id = f"grant-{suffix}"
        key = AuthorityLookupKey(
            repository=REPO,
            pr_number=36,
            base_sha=BASE,
            head_sha=HEAD,
            mission_id=mission,
            grant_id=grant_id,
        ).validate()
        grant = AuthorityGrant(
            schema_version="1.1.0",
            grant_id=grant_id,
            issuer_subject_id="issuer",
            subject_id="merge-executor",
            tenant_id="tenant",
            organization_id="org",
            mission_id=mission,
            capability_id="github.merge",
            capability_version="1.0.0",
            actions=("merge_pull_request",),
            resource_scope=(canonical_pr_authority_resource(key),),
            authority_ceiling="external_write",
            constraints=("merge_method:merge",),
            parent_grant_id=None,
            issued_at="2026-08-20T00:00:00+00:00",
            expires_at="2026-08-21T00:00:00+00:00",
            epoch=9,
            policy_digest=POLICY,
            observability_contract_digest=OBS,
            signature=signature,
            delegation_allowed=False,
            delegation_depth_budget=0,
        ).validate()
        raw_grant = asdict(grant)
        raw_grant["actions"] = list(grant.actions)
        raw_grant["resource_scope"] = list(grant.resource_scope)
        raw_grant["constraints"] = list(grant.constraints)
        record = {
            "lookup_key": asdict(key),
            "lineage": [raw_grant],
            "lineage_digest": canonical_source_lineage_digest((grant,)),
            "provenance_id": f"control-plane:entry:{suffix}",
            "source_kind": "trusted-control-plane",
        }
        calls = []

        def lookup_exact(**kwargs):
            calls.append(kwargs)
            if records == 0:
                return ()
            if records == 2:
                return (record, dict(record))
            return (record,)

        def verifier(payload: bytes, presented_signature: str, key_id: str, algorithm: str) -> bool:
            return (
                presented_signature == "sig"
                and key_id == "key-1"
                and algorithm == "test"
            )

        env = {
            "CYBER_LION_REPOSITORY": REPO,
            "CYBER_LION_PR_NUMBER": "36",
            "CYBER_LION_BASE_SHA": BASE,
            "CYBER_LION_HEAD_SHA": HEAD,
            "CYBER_LION_MERGE_METHOD": "merge",
            "CYBER_LION_TRUST_DOMAIN": "github.test",
            "CYBER_LION_TENANT_ID": "tenant",
            "CYBER_LION_ORGANIZATION_ID": "org",
            "CYBER_LION_MISSION_ID": mission,
            "CYBER_LION_GRANT_ID": grant_id,
            "CYBER_LION_AUTHORITY_EPOCH": "9",
            "CYBER_LION_ROOT_GRANT_ID": grant.grant_id,
            "CYBER_LION_ROOT_GRANT_DIGEST": grant.digest(),
            "CYBER_LION_ADMISSION_ID": f"admission-{suffix}",
            "CYBER_LION_ISSUER_KEYS_JSON": json.dumps(
                [
                    {
                        "issuer_subject_id": "issuer",
                        "trust_domain": "github.test",
                        "key_id": "key-1",
                        "algorithm": "test",
                    }
                ]
            ),
        }
        return env, lookup_exact, verifier, calls

    def _run_execute(self, suffix: str, **fixture_kwargs):
        env, lookup_exact, verifier, calls = self._fixture(suffix, **fixture_kwargs)
        output = io.StringIO()
        with redirect_stdout(output):
            code = execute(env=env, lookup_exact=lookup_exact, verifier=verifier)
        payload = json.loads(output.getvalue())
        return code, payload, calls

    def test_exact_pr_and_bootstrap_inputs_are_loaded(self):
        env, *_ = self._fixture("inputs")
        state = load_pr_state(env)
        bootstrap = load_bootstrap(env)
        self.assertEqual(state.repository, REPO)
        self.assertEqual(state.pr_number, 36)
        self.assertEqual(state.base_sha, BASE)
        self.assertEqual(state.head_sha, HEAD)
        self.assertEqual(bootstrap.mission_id, env["CYBER_LION_MISSION_ID"])
        self.assertEqual(bootstrap.epoch, 9)

    def test_missing_or_partial_pr_input_fails_closed(self):
        env, *_ = self._fixture("bad-pr")
        del env["CYBER_LION_HEAD_SHA"]
        with self.assertRaises(CILiveAdmissionEntrypointError):
            load_pr_state(env)
        env, *_ = self._fixture("partial-sha")
        env["CYBER_LION_HEAD_SHA"] = "abc"
        with self.assertRaises(ValueError):
            load_pr_state(env)

    def test_issuer_key_shape_is_strict_and_has_no_key_material(self):
        env, *_ = self._fixture("keys")
        bindings = load_issuer_key_bindings(env)
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].key_id, "key-1")
        env["CYBER_LION_ISSUER_KEYS_JSON"] = json.dumps(
            [{"issuer_subject_id": "issuer", "trust_domain": "github.test", "key_id": "key-1", "algorithm": "test", "private_key": "secret"}]
        )
        with self.assertRaises(CILiveAdmissionEntrypointError):
            load_issuer_key_bindings(env)

    def test_provider_loader_requires_exact_module_callable(self):
        module_name = "cyber_lion_entrypoint_test_provider"
        module = types.ModuleType(module_name)
        module.lookup = lambda **kwargs: ()
        sys.modules[module_name] = module
        try:
            env = {"P": f"{module_name}:lookup"}
            self.assertIs(load_provider(env, "P"), module.lookup)
            with self.assertRaises(CILiveAdmissionEntrypointError):
                load_provider({"P": f"{module_name}:missing"}, "P")
            with self.assertRaises(CILiveAdmissionEntrypointError):
                load_provider({"P": "bad-spec"}, "P")
        finally:
            sys.modules.pop(module_name, None)

    def test_valid_exact_admission_outputs_one_json_and_exit_zero(self):
        code, payload, calls = self._run_execute("allow")
        self.assertEqual(code, 0)
        self.assertEqual(payload["decision"], "ALLOW")
        self.assertIsInstance(payload["evidence"], dict)
        self.assertNotIn("rationale", payload)
        self.assertEqual(len(calls), 1)

    def test_zero_and_ambiguous_authority_records_exit_one(self):
        code, payload, _ = self._run_execute("zero", records=0)
        self.assertEqual(code, 1)
        self.assertEqual(payload["decision"], "DENY")
        self.assertIsNone(payload["evidence"])
        code, payload, _ = self._run_execute("many", records=2)
        self.assertEqual(code, 1)
        self.assertEqual(payload["decision"], "DENY")

    def test_provider_exception_fails_closed_and_secret_is_not_printed(self):
        env, _, verifier, _ = self._fixture("provider-error")

        def failing_lookup(**kwargs):
            raise RuntimeError("Authorization: Bearer SUPER-SECRET")

        output = io.StringIO()
        with redirect_stdout(output):
            code = execute(env=env, lookup_exact=failing_lookup, verifier=verifier)
        self.assertEqual(code, 1)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["decision"], "DENY")
        self.assertNotIn("rationale", payload)
        self.assertNotIn("SUPER-SECRET", output.getvalue())
        self.assertNotIn("Authorization", output.getvalue())

    def test_invalid_signature_exits_one(self):
        code, payload, _ = self._run_execute("bad-signature", signature="forged")
        self.assertEqual(code, 1)
        self.assertEqual(payload["decision"], "DENY")

    def test_real_main_loads_environment_selected_providers(self):
        env, lookup_exact, verifier, calls = self._fixture("main")
        module_name = "cyber_lion_entrypoint_live_provider"
        module = types.ModuleType(module_name)
        module.lookup_exact = lookup_exact
        module.verify = verifier
        sys.modules[module_name] = module
        env["CYBER_LION_AUTHORITY_PROVIDER"] = f"{module_name}:lookup_exact"
        env["CYBER_LION_VERIFIER_PROVIDER"] = f"{module_name}:verify"
        try:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(env=env)
            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["decision"], "ALLOW")
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(output.getvalue().strip().splitlines()), 1)
        finally:
            sys.modules.pop(module_name, None)

    def test_main_provider_load_failure_is_sanitized_exit_two(self):
        env, *_ = self._fixture("load-fail")
        env["CYBER_LION_AUTHORITY_PROVIDER"] = "missing.module:lookup"
        env["CYBER_LION_VERIFIER_PROVIDER"] = "missing.module:verify"
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(env=env)
        self.assertEqual(code, 2)
        self.assertEqual(
            json.loads(output.getvalue()),
            {"status": "ERROR", "error": "CONFIGURATION_OR_RUNTIME_ERROR"},
        )

    def test_entrypoint_has_no_github_or_network_write_dependency(self):
        source_path = Path(__file__).parents[1] / "enterprise" / "ci_live_admission_entrypoint.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", 1)[0])
        self.assertTrue({"requests", "urllib", "httpx", "github"}.isdisjoint(roots))
        text = source_path.read_text(encoding="utf-8")
        self.assertNotIn("consumption_owner", text)
        self.assertNotIn("merge_pull_request(", text)


if __name__ == "__main__":
    unittest.main()
