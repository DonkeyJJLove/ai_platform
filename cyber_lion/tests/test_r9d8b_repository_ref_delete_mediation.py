from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.repository_maintenance_cleanup import (
    RepositoryDeleteAuthorityEvidence,
    SlashSafeGitHubRepositoryMaintenanceBackend,
    load_repository_delete_authority,
)
from cyber_lion.enterprise.repository_maintenance_sandbox import (
    GitHubRepositoryMaintenanceBackend,
    RepositoryMaintenanceError,
)


class R9D8BRepositoryRefDeleteMediationTests(unittest.TestCase):
    def _event(self, *, actor: str = "DonkeyJJLove", owner: str = "DonkeyJJLove", body: str = "LION-BRANCH-CLEANUP v1") -> dict:
        return {
            "action": "created",
            "issue": {"number": 144},
            "comment": {"id": 123456, "body": body, "user": {"login": actor}},
            "repository": {"full_name": "DonkeyJJLove/ai_platform", "owner": {"login": owner}},
        }

    def _load(self, event: dict) -> RepositoryDeleteAuthorityEvidence:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "event.json"
            path.write_text(json.dumps(event), encoding="utf-8")
            return load_repository_delete_authority(
                event_path=path,
                repository="DonkeyJJLove/ai_platform",
                workflow_run_id=42,
                workflow_run_attempt=1,
                checked_out_sha="a" * 40,
            )

    def test_owner_control_event_is_external_evidence_and_digest_bound(self):
        evidence = self._load(self._event())
        self.assertEqual(evidence.actor_login, "DonkeyJJLove")
        self.assertEqual(evidence.owner_login, "DonkeyJJLove")
        self.assertEqual(evidence.checked_out_sha, "a" * 40)
        self.assertRegex(evidence.digest(), r"^[0-9a-f]{64}$")

    def test_actor_issue_command_repository_and_sha_substitution_are_denied(self):
        cases = [
            self._event(actor="attacker"),
            self._event(body="LION-BRANCH-CLEANUP v2"),
            {**self._event(), "issue": {"number": 145}},
            {**self._event(), "repository": {"full_name": "other/repo", "owner": {"login": "DonkeyJJLove"}}},
        ]
        for event in cases:
            with self.subTest(event=event):
                with self.assertRaises(RepositoryMaintenanceError):
                    self._load(event)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "event.json"
            path.write_text(json.dumps(self._event()), encoding="utf-8")
            with self.assertRaises(RepositoryMaintenanceError):
                load_repository_delete_authority(
                    event_path=path,
                    repository="DonkeyJJLove/ai_platform",
                    workflow_run_id=42,
                    workflow_run_attempt=1,
                    checked_out_sha="not-a-sha",
                )

    def test_direct_mediated_backend_delete_is_unrepresentable_without_exact_admission(self):
        backend = SlashSafeGitHubRepositoryMaintenanceBackend("DonkeyJJLove/ai_platform", "token")
        backend._request = lambda *args, **kwargs: self.fail("network effect reached")
        with self.assertRaisesRegex(RepositoryMaintenanceError, "exact admission required"):
            backend.delete_exact_branch_ref("mission/example", "b" * 40)

    def test_historical_base_backend_cannot_delete_or_reach_network(self):
        backend = GitHubRepositoryMaintenanceBackend("DonkeyJJLove/ai_platform", "token")
        backend._request = lambda *args, **kwargs: self.fail("network effect reached")
        with self.assertRaisesRegex(RepositoryMaintenanceError, "mediated boundary required"):
            backend.delete_exact_branch_ref("mission/example", "b" * 40)

    def test_scanner_classifies_selected_primitive_as_external_repository_ref_delete(self):
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources={
                "cyber_lion/enterprise/repository_maintenance_sandbox.py":
                    "def f(self):\n    self.backend.delete_exact_branch_ref('mission/x', 'a' * 40)\n"
            },
        )
        self.assertEqual(len(inventory.surfaces), 1)
        surface = inventory.surfaces[0]
        self.assertEqual(surface.effect_class, "repository_ref.delete")
        self.assertEqual(surface.authority_class, "external_write")
        self.assertEqual(surface.target_class, "external")
        self.assertFalse(inventory.unclassified_refs)

    def test_delete_route_remains_closed_to_default_and_release_refs(self):
        backend = SlashSafeGitHubRepositoryMaintenanceBackend("DonkeyJJLove/ai_platform", "token")
        for branch in ("master", "main", "release/prod"):
            with self.subTest(branch=branch):
                with self.assertRaises(RepositoryMaintenanceError):
                    backend._validate_api_path(
                        "DELETE",
                        f"/repos/DonkeyJJLove/ai_platform/git/refs/heads/{branch}",
                    )


if __name__ == "__main__":
    unittest.main()
