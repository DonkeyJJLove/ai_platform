from __future__ import annotations

import dataclasses
import json
from pathlib import Path
import unittest

from cyber_lion.enterprise.authority_grant import (
    AuthorityGrant,
    AuthorityGrantError,
    validate_attenuation,
)

POLICY = "sha256:" + "1" * 64
OBS = "sha256:" + "2" * 64


def parent_grant() -> AuthorityGrant:
    return AuthorityGrant(
        schema_version="1.0.0",
        grant_id="grant:root",
        issuer_subject_id="root:governance",
        subject_id="workload:builder-parent",
        tenant_id="tenant:a",
        organization_id="org:a",
        mission_id="RCCM-1E-BF",
        capability_id="code.write",
        capability_version="1.0.0",
        actions=("read", "write", "test"),
        resource_scope=("repo:ai_platform", "path:cyber_lion"),
        authority_ceiling="local_write",
        constraints=("no-default-branch-write",),
        parent_grant_id=None,
        issued_at="2026-08-19T14:00:00Z",
        expires_at="2026-08-19T16:00:00Z",
        epoch=7,
        policy_digest=POLICY,
        observability_contract_digest=OBS,
        signature="test-signature-parent",
    )


def child_grant() -> AuthorityGrant:
    return AuthorityGrant(
        schema_version="1.0.0",
        grant_id="grant:child",
        issuer_subject_id="workload:builder-parent",
        subject_id="workload:builder-child",
        tenant_id="tenant:a",
        organization_id="org:a",
        mission_id="RCCM-1E-BF",
        capability_id="code.write",
        capability_version="1.0.0",
        actions=("read", "test"),
        resource_scope=("repo:ai_platform",),
        authority_ceiling="read",
        constraints=("no-default-branch-write", "read-only-child"),
        parent_grant_id="grant:root",
        issued_at="2026-08-19T14:15:00Z",
        expires_at="2026-08-19T15:00:00Z",
        epoch=7,
        policy_digest=POLICY,
        observability_contract_digest=OBS,
        signature="test-signature-child",
    )


class AuthorityGrantContractTests(unittest.TestCase):
    def test_valid_contract_and_canonical_digest(self):
        grant = parent_grant().validate()
        self.assertEqual(grant.digest(), grant.digest())
        payload = json.loads(grant.canonical_payload())
        self.assertEqual(payload["grant_id"], "grant:root")
        self.assertNotIn("signature", payload)

    def test_invalid_shape_fails_closed(self):
        invalid = (
            {"schema_version": "2.0.0"},
            {"actions": ()},
            {"actions": ("read", "read")},
            {"resource_scope": ()},
            {"constraints": ("x", "x")},
            {"epoch": -1},
            {"epoch": True},
            {"issued_at": "2026-08-19T14:00:00"},
            {"expires_at": "2026-08-19T13:00:00Z"},
            {"policy_digest": "sha256:not-canonical"},
            {"observability_contract_digest": "missing-prefix"},
        )
        for mutation in invalid:
            with self.subTest(mutation=mutation), self.assertRaises(AuthorityGrantError):
                dataclasses.replace(parent_grant(), **mutation).validate()

    def test_schema_required_fields_match_runtime_contract(self):
        schema_path = Path(__file__).parents[1] / "contracts" / "v1" / "authority_grant.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required"]), set(AuthorityGrant.__dataclass_fields__))
        self.assertFalse(schema["additionalProperties"])


class AuthorityAttenuationTests(unittest.TestCase):
    def test_narrower_child_is_valid(self):
        child = child_grant()
        self.assertIs(validate_attenuation(parent_grant(), child), child)

    def test_authority_actions_and_scope_cannot_expand(self):
        mutations = (
            {"authority_ceiling": "external_write"},
            {"actions": ("read", "test", "deploy")},
            {"resource_scope": ("repo:ai_platform", "repo:glitchlab")},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(AuthorityGrantError):
                validate_attenuation(parent_grant(), dataclasses.replace(child_grant(), **mutation))

    def test_parent_constraints_cannot_be_removed(self):
        with self.assertRaises(AuthorityGrantError):
            validate_attenuation(
                parent_grant(), dataclasses.replace(child_grant(), constraints=("read-only-child",))
            )

    def test_lineage_and_issuer_binding_are_exact(self):
        mutations = (
            {"parent_grant_id": "grant:other"},
            {"issuer_subject_id": "workload:other"},
            {"grant_id": "grant:root"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(AuthorityGrantError):
                validate_attenuation(parent_grant(), dataclasses.replace(child_grant(), **mutation))

    def test_domain_capability_epoch_and_policy_binding_cannot_drift(self):
        mutations = (
            {"tenant_id": "tenant:b"},
            {"organization_id": "org:b"},
            {"mission_id": "other-mission"},
            {"capability_id": "deploy"},
            {"capability_version": "2.0.0"},
            {"epoch": 8},
            {"policy_digest": "sha256:" + "3" * 64},
            {"observability_contract_digest": "sha256:" + "4" * 64},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(AuthorityGrantError):
                validate_attenuation(parent_grant(), dataclasses.replace(child_grant(), **mutation))

    def test_child_cannot_predate_or_outlive_parent(self):
        mutations = (
            {"issued_at": "2026-08-19T13:59:59Z"},
            {"expires_at": "2026-08-19T16:00:01Z"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(AuthorityGrantError):
                validate_attenuation(parent_grant(), dataclasses.replace(child_grant(), **mutation))


if __name__ == "__main__":
    unittest.main()
