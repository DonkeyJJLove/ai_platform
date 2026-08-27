from __future__ import annotations

import ast
from pathlib import Path
import unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.repository_maintenance_cleanup import (
    SlashSafeGitHubRepositoryMaintenanceBackend,
    run_cleanup,
)
from cyber_lion.enterprise.repository_maintenance_mediated_cleanup import (
    CanonicalSlashSafeGitHubRepositoryMaintenanceBackend,
)
from cyber_lion.enterprise.repository_maintenance_sandbox import (
    GitHubRepositoryMaintenanceBackend,
    RepositoryMaintenanceError,
)


class R9D9ERepositoryMaintenanceDynamicHttpClosureTests(unittest.TestCase):
    def test_legacy_execute_cleanup_is_structurally_disabled(self):
        with self.assertRaisesRegex(
            RepositoryMaintenanceError,
            "legacy execute-cleanup route disabled",
        ):
            run_cleanup(
                token="token",
                expected_master="a" * 40,
                event_path=Path("/nonexistent/event.json"),
                repository="DonkeyJJLove/ai_platform",
                workflow_run_id=1,
                workflow_run_attempt=1,
                checked_out_sha="a" * 40,
            )

    def test_historical_sandbox_transport_is_get_only_before_network(self):
        backend = GitHubRepositoryMaintenanceBackend("DonkeyJJLove/ai_platform", "token")
        backend._request_get_exact = lambda *args, **kwargs: self.fail("network reached")
        with self.assertRaisesRegex(RepositoryMaintenanceError, "GET-only"):
            backend._request(
                "DELETE",
                "/repos/DonkeyJJLove/ai_platform/git/refs/heads/mission/example",
            )

    def test_slash_safe_generic_transport_is_get_only_before_network(self):
        backend = SlashSafeGitHubRepositoryMaintenanceBackend("DonkeyJJLove/ai_platform", "token")
        backend._request_get_exact = lambda *args, **kwargs: self.fail("network reached")
        with self.assertRaisesRegex(RepositoryMaintenanceError, "GET-only"):
            backend._request(
                "DELETE",
                "/repos/DonkeyJJLove/ai_platform/git/refs/heads/mission/example",
            )

    def test_legacy_delete_admission_is_disabled(self):
        backend = SlashSafeGitHubRepositoryMaintenanceBackend("DonkeyJJLove/ai_platform", "token")
        with self.assertRaisesRegex(RepositoryMaintenanceError, "legacy repository delete admission disabled"):
            backend.authorize_delete()

    def test_raw_delete_requires_exact_pending_canonical_admission(self):
        backend = CanonicalSlashSafeGitHubRepositoryMaintenanceBackend(
            "DonkeyJJLove/ai_platform", "token"
        )
        backend._delete_exact_branch_ref_http = lambda *args, **kwargs: self.fail("network reached")
        with self.assertRaisesRegex(RepositoryMaintenanceError, "exact admission required"):
            backend.delete_exact_branch_ref("mission/example", "b" * 40)

    def test_raw_http_delete_owner_is_fixed_literal_and_unique(self):
        root = Path(__file__).resolve().parents[2]
        cleanup = (root / "cyber_lion/enterprise/repository_maintenance_cleanup.py").read_text(encoding="utf-8")
        sandbox = (root / "cyber_lion/enterprise/repository_maintenance_sandbox.py").read_text(encoding="utf-8")
        delete_requests = []
        for path, source in (("cleanup", cleanup), ("sandbox", sandbox)):
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if not (
                    isinstance(fn, ast.Attribute)
                    and fn.attr == "Request"
                ):
                    continue
                method = None
                for kw in node.keywords:
                    if kw.arg == "method" and isinstance(kw.value, ast.Constant):
                        method = kw.value.value
                if method == "DELETE":
                    delete_requests.append((path, node.lineno))
        self.assertEqual(delete_requests, [("cleanup", delete_requests[0][1])])

    def test_scanner_closes_selected_dynamic_http_ambiguities(self):
        root = Path(__file__).resolve().parents[2]
        paths = (
            "cyber_lion/enterprise/repository_maintenance_cleanup.py",
            "cyber_lion/enterprise/repository_maintenance_sandbox.py",
            "cyber_lion/enterprise/repository_maintenance_mediated_cleanup.py",
        )
        sources = {path: (root / path).read_text(encoding="utf-8") for path in paths}
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources=sources,
        )
        refs = set(inventory.unclassified_refs)
        self.assertFalse(
            any(
                ref.startswith("cyber_lion/enterprise/repository_maintenance_cleanup.py:")
                and ref.endswith("urllib.request.Request:dynamic-http-method")
                for ref in refs
            )
        )
        self.assertFalse(
            any(
                ref.startswith("cyber_lion/enterprise/repository_maintenance_sandbox.py:")
                and ref.endswith("urllib.request.Request:dynamic-http-method")
                for ref in refs
            )
        )
        delete_surfaces = [s for s in inventory.surfaces if s.effect_class == "external.network.delete"]
        self.assertEqual(len(delete_surfaces), 1)
        self.assertEqual(
            delete_surfaces[0].implementation_refs,
            ("cyber_lion/enterprise/repository_maintenance_cleanup.py",),
        )


if __name__ == "__main__":
    unittest.main()
