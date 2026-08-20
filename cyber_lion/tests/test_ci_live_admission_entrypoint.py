from __future__ import annotations

import ast
import io
import json
import sys
import types
import unittest
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from pathlib import Path

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import (
    AuthorityLookupKey,
    canonical_pr_authority_resource,
    canonical_source_lineage_digest,
)
from cyber_lion.enterprise.authority_verification import IssuerKeyBinding
from cyber_lion.enterprise.ci_live_admission_entrypoint import (
    CILiveAdmissionEntrypointError,
    execute_composed,
    load_pr_state,
    load_provider,
    main,
)
from cyber_lion.enterprise.pr_authority_bootstrap import (
    PRAuthorityBootstrapLookupKey,
    PRAuthorityBootstrapRecord,
    canonical_pr_bootstrap_digest,
)

REPO = "DonkeyJJLove/ai_platform"
BASE = "a" * 40
HEAD = "b" * 40
POLICY = "sha256:" + "1" * 64
OBS = "sha256:" + "2" * 64


class CILiveAdmissionCompositionTests(unittest.TestCase):
    def _fixture(
        self,
        suffix: str,
        *,
        bootstrap_records: int = 1,
        authority_records: int = 1,
        signature: str = "sig",
    ):
        mission = f"ci-composed-{suffix}"
        grant_id = f"grant-{suffix}"
        authority_key = AuthorityLookupKey(
            repository=REPO,
            pr_number=38,
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
            resource_scope=(canonical_pr_authority_resource(authority_key),),
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
        authority_wire = {
            "lookup_key": asdict(authority_key),
            "lineage": [raw_grant],
            "lineage_digest": canonical_source_lineage_digest((grant,)),
            "provenance_id": f"control-plane:authority:{suffix}",
            "source_kind": "trusted-control-plane",
        }

        pr_key = PRAuthorityBootstrapLookupKey(
            repository=REPO,
            pr_number=38,
            base_sha=BASE,
            head_sha=HEAD,
            merge_method="merge",
        ).validate()
        issuer_binding = IssuerKeyBinding(
            issuer_subject_id="issuer",
            trust_domain="github.test",
            key_id="key-1",
            algorithm="test",
        ).validate()
        bootstrap_record = PRAuthorityBootstrapRecord(
            lookup_key=pr_key,
            mission_id=mission,
            grant_id=grant_id,
            trust_domain="github.test",
            tenant_id="tenant",
            organization_id="org",
            epoch=9,
            root_grant_id=grant.grant_id,
            root_grant_digest=grant.digest(),
            issuer_key_bindings=(issuer_binding,),
            provenance_id=f"control-plane:bootstrap:{suffix}",
            bootstrap_digest="0" * 64,
        )
        bootstrap_record = replace(
            bootstrap_record,
            bootstrap_digest=canonical_pr_bootstrap_digest(bootstrap_record),
        ).validate()
        bootstrap_wire = asdict(bootstrap_record)
        bootstrap_wire["issuer_key_bindings"] = [asdict(issuer_binding)]

        bootstrap_calls: list[dict[str, object]] = []
        authority_calls: list[dict[str, object]] = []

        def bootstrap_lookup(**kwargs):
            bootstrap_calls.append(kwargs)
            if bootstrap_records == 0:
                return ()
            if bootstrap_records == 2:
                return (bootstrap_wire, dict(bootstrap_wire))
            return (bootstrap_wire,)

        def authority_lookup(**kwargs):
            authority_calls.append(kwargs)
            if authority_records == 0:
                return ()
            if authority_records == 2:
                return (authority_wire, dict(authority_wire))
            return (authority_wire,)

        def verifier(
            payload: bytes,
            presented_signature: str,
            key_id: str,
            algorithm: str,
        ) -> bool:
            return (
                presented_signature == "sig"
                and key_id == "key-1"
                and algorithm == "test"
            )

        env = {
            "CYBER_LION_REPOSITORY": REPO,
            "CYBER_LION_PR_NUMBER": "38",
            "CYBER_LION_BASE_SHA": BASE,
            "CYBER_LION_HEAD_SHA": HEAD,
            "CYBER_LION_MERGE_METHOD": "merge",
            "CYBER_LION_ADMISSION_ID": f"admission-{suffix}",
        }
        return (
            env,
            bootstrap_lookup,
            authority_lookup,
            verifier,
            bootstrap_calls,
            authority_calls,
            bootstrap_wire,
        )

    def _run_composed(self, suffix: str, **kwargs):
        (
            env,
            bootstrap_lookup,
            authority_lookup,
            verifier,
            bootstrap_calls,
            authority_calls,
            _,
        ) = self._fixture(suffix, **kwargs)
        output = io.StringIO()
        with redirect_stdout(output):
            code = execute_composed(
                env=env,
                bootstrap_lookup_exact=bootstrap_lookup,
                authority_lookup_exact=authority_lookup,
                verifier=verifier,
            )
        return (
            code,
            json.loads(output.getvalue()),
            bootstrap_calls,
            authority_calls,
        )

    def test_exact_pr_state_is_only_discovery_input(self):
        env, *_ = self._fixture("pr-state")
        state = load_pr_state(env)
        self.assertEqual(
            (
                state.repository,
                state.pr_number,
                state.base_sha,
                state.head_sha,
                state.merge_method,
            ),
            (REPO, 38, BASE, HEAD, "merge"),
        )

    def test_provider_loader_requires_exact_module_callable(self):
        module_name = "cyber_lion_composition_provider_loader"
        module = types.ModuleType(module_name)
        module.lookup = lambda **kwargs: ()
        sys.modules[module_name] = module
        try:
            self.assertIs(
                load_provider({"P": f"{module_name}:lookup"}, "P"),
                module.lookup,
            )
            with self.assertRaises(CILiveAdmissionEntrypointError):
                load_provider({"P": "bad-spec"}, "P")
            with self.assertRaises(CILiveAdmissionEntrypointError):
                load_provider({"P": f"{module_name}:missing"}, "P")
        finally:
            sys.modules.pop(module_name, None)

    def test_valid_chain_resolves_bootstrap_then_authority_and_allows(self):
        code, payload, bootstrap_calls, authority_calls = self._run_composed("allow")
        self.assertEqual(code, 0)
        self.assertEqual(payload["decision"], "ALLOW")
        self.assertIsInstance(payload["evidence"], dict)
        self.assertNotIn("rationale", payload)
        self.assertEqual(len(bootstrap_calls), 1)
        self.assertEqual(
            bootstrap_calls[0],
            {
                "repository": REPO,
                "pr_number": 38,
                "base_sha": BASE,
                "head_sha": HEAD,
                "merge_method": "merge",
            },
        )
        self.assertEqual(len(authority_calls), 1)
        self.assertEqual(authority_calls[0]["mission_id"], payload["mission_id"])
        self.assertEqual(authority_calls[0]["grant_id"], payload["grant_id"])

    def test_bootstrap_zero_and_many_fail_before_authority(self):
        for count in (0, 2):
            (
                env,
                bootstrap_lookup,
                authority_lookup,
                verifier,
                _,
                authority_calls,
                _,
            ) = self._fixture(f"bootstrap-{count}", bootstrap_records=count)
            with self.assertRaises(Exception):
                execute_composed(
                    env=env,
                    bootstrap_lookup_exact=bootstrap_lookup,
                    authority_lookup_exact=authority_lookup,
                    verifier=verifier,
                )
            self.assertEqual(authority_calls, [])

    def test_bootstrap_binding_mismatch_fails_before_authority(self):
        (
            env,
            _,
            authority_lookup,
            verifier,
            _,
            authority_calls,
            bootstrap_wire,
        ) = self._fixture("mismatch")
        bad = dict(bootstrap_wire)
        bad["lookup_key"] = dict(bootstrap_wire["lookup_key"])
        bad["lookup_key"]["head_sha"] = "c" * 40

        def wrong_bootstrap(**kwargs):
            return (bad,)

        with self.assertRaises(Exception):
            execute_composed(
                env=env,
                bootstrap_lookup_exact=wrong_bootstrap,
                authority_lookup_exact=authority_lookup,
                verifier=verifier,
            )
        self.assertEqual(authority_calls, [])

    def test_bootstrap_unknown_secret_field_fails_closed(self):
        env, _, authority_lookup, verifier, _, authority_calls, bootstrap_wire = self._fixture(
            "secret-field"
        )
        bad = dict(bootstrap_wire)
        bad["token"] = "SUPER-SECRET"

        def secret_bootstrap(**kwargs):
            return (bad,)

        with self.assertRaises(Exception):
            execute_composed(
                env=env,
                bootstrap_lookup_exact=secret_bootstrap,
                authority_lookup_exact=authority_lookup,
                verifier=verifier,
            )
        self.assertEqual(authority_calls, [])

    def test_no_bootstrap_environment_fallback(self):
        env, bootstrap_lookup, authority_lookup, verifier, _, authority_calls, _ = self._fixture(
            "no-fallback", bootstrap_records=0
        )
        env.update(
            {
                "CYBER_LION_MISSION_ID": "attacker-mission",
                "CYBER_LION_GRANT_ID": "attacker-grant",
                "CYBER_LION_TRUST_DOMAIN": "attacker",
                "CYBER_LION_TENANT_ID": "attacker",
                "CYBER_LION_ORGANIZATION_ID": "attacker",
                "CYBER_LION_AUTHORITY_EPOCH": "999",
                "CYBER_LION_ROOT_GRANT_ID": "attacker-root",
                "CYBER_LION_ROOT_GRANT_DIGEST": "f" * 64,
                "CYBER_LION_ISSUER_KEYS_JSON": "[]",
            }
        )
        with self.assertRaises(Exception):
            execute_composed(
                env=env,
                bootstrap_lookup_exact=bootstrap_lookup,
                authority_lookup_exact=authority_lookup,
                verifier=verifier,
            )
        self.assertEqual(authority_calls, [])

    def test_missing_authority_and_bad_signature_are_deny_exit_one(self):
        code, payload, _, authority_calls = self._run_composed(
            "no-authority", authority_records=0
        )
        self.assertEqual(code, 1)
        self.assertEqual(payload["decision"], "DENY")
        self.assertEqual(len(authority_calls), 1)
        self.assertIsNone(payload["evidence"])

        code, payload, _, _ = self._run_composed(
            "bad-signature", signature="forged"
        )
        self.assertEqual(code, 1)
        self.assertEqual(payload["decision"], "DENY")

    def test_real_main_loads_three_providers_and_emits_one_json(self):
        (
            env,
            bootstrap_lookup,
            authority_lookup,
            verifier,
            bootstrap_calls,
            authority_calls,
            _,
        ) = self._fixture("main")
        module_name = "cyber_lion_composed_live_provider"
        module = types.ModuleType(module_name)
        module.bootstrap = bootstrap_lookup
        module.authority = authority_lookup
        module.verify = verifier
        sys.modules[module_name] = module
        env["CYBER_LION_BOOTSTRAP_PROVIDER"] = f"{module_name}:bootstrap"
        env["CYBER_LION_AUTHORITY_PROVIDER"] = f"{module_name}:authority"
        env["CYBER_LION_VERIFIER_PROVIDER"] = f"{module_name}:verify"
        try:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(env=env)
            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["decision"], "ALLOW")
            self.assertEqual(len(bootstrap_calls), 1)
            self.assertEqual(len(authority_calls), 1)
            self.assertEqual(len(output.getvalue().strip().splitlines()), 1)
        finally:
            sys.modules.pop(module_name, None)

    def test_bootstrap_provider_exception_is_sanitized_exit_two(self):
        env, _, authority_lookup, verifier, _, _, _ = self._fixture("provider-error")

        def failing_bootstrap(**kwargs):
            raise RuntimeError("Authorization: Bearer BOOTSTRAP-SUPER-SECRET")

        module_name = "cyber_lion_composed_error_provider"
        module = types.ModuleType(module_name)
        module.bootstrap = failing_bootstrap
        module.authority = authority_lookup
        module.verify = verifier
        sys.modules[module_name] = module
        env["CYBER_LION_BOOTSTRAP_PROVIDER"] = f"{module_name}:bootstrap"
        env["CYBER_LION_AUTHORITY_PROVIDER"] = f"{module_name}:authority"
        env["CYBER_LION_VERIFIER_PROVIDER"] = f"{module_name}:verify"
        try:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(env=env)
            self.assertEqual(code, 2)
            self.assertEqual(
                json.loads(output.getvalue()),
                {"status": "ERROR", "error": "CONFIGURATION_OR_RUNTIME_ERROR"},
            )
            self.assertNotIn("BOOTSTRAP-SUPER-SECRET", output.getvalue())
            self.assertNotIn("Authorization", output.getvalue())
        finally:
            sys.modules.pop(module_name, None)

    def test_entrypoint_has_no_github_network_or_consumption_surface(self):
        source_path = Path(__file__).parents[1] / "enterprise" / "ci_live_admission_entrypoint.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", 1)[0])
        self.assertTrue({"requests", "urllib", "httpx", "github"}.isdisjoint(roots))
        self.assertNotIn("consumption_owner", source)
        self.assertNotIn("merge_pull_request(", source)
        main_source = source.split("def main(", 1)[1]
        self.assertNotIn("CYBER_LION_MISSION_ID", main_source)
        self.assertNotIn("CYBER_LION_GRANT_ID", main_source)
        self.assertNotIn("CYBER_LION_ISSUER_KEYS_JSON", main_source)


if __name__ == "__main__":
    unittest.main()
