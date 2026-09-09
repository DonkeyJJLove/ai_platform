import unittest
from unittest.mock import patch

from cyber_lion.enterprise.repository_maintenance_cleanup import (
    SlashSafeGitHubRepositoryMaintenanceBackend,
)
from cyber_lion.enterprise.repository_maintenance_sandbox import RepositoryMaintenanceError


class SlashSafeRepositoryMaintenanceBackendTests(unittest.TestCase):
    def _backend(self):
        return SlashSafeGitHubRepositoryMaintenanceBackend(
            "DonkeyJJLove/ai_platform", "test-token"
        )

    def test_branch_ref_path_preserves_slash(self):
        backend = self._backend()
        calls = []

        def request(method, path, body=None, *, allow_404=False):
            calls.append((method, path, allow_404))
            return 200, {"object": {"sha": "a" * 40}}

        backend._request = request
        self.assertEqual(backend.branch_sha("mission/example"), "a" * 40)
        self.assertEqual(
            calls,
            [("GET", "/repos/DonkeyJJLove/ai_platform/git/ref/heads/mission/example", True)],
        )

    def test_compare_path_preserves_slash(self):
        backend = self._backend()
        calls = []

        def request(method, path, body=None, *, allow_404=False):
            calls.append((method, path))
            return 200, {"status": "ahead", "ahead_by": 3, "behind_by": 0}

        backend._request = request
        result = backend.compare_branch_to_master("docs/polish-documentation")
        self.assertEqual(result["behind_by"], 0)
        self.assertEqual(
            calls,
            [("GET", "/repos/DonkeyJJLove/ai_platform/compare/docs/polish-documentation...master")],
        )

    def test_direct_delete_without_exact_admission_is_denied_before_network(self):
        backend = self._backend()
        calls = []

        def request(method, path, body=None, *, allow_404=False):
            calls.append((method, path, allow_404))
            raise AssertionError("network must not be reached")

        backend._request = request
        with self.assertRaisesRegex(RepositoryMaintenanceError, "exact admission required"):
            backend.delete_exact_branch_ref(
                "mission/e003-r5-channel-replacement-projection", "b" * 40
            )
        self.assertEqual(calls, [])

    def test_canonical_compare_routes_are_allowed(self):
        backend = self._backend()
        backend._validate_api_path(
            "GET",
            "/repos/DonkeyJJLove/ai_platform/compare/mission/foo...master",
        )
        backend._validate_api_path(
            "GET",
            "/repos/DonkeyJJLove/ai_platform/compare/docs/foo...master",
        )

    def test_real_traversal_segments_are_denied(self):
        backend = self._backend()
        for path in (
            "/repos/DonkeyJJLove/ai_platform/../issues",
            "/repos/DonkeyJJLove/ai_platform/foo/../bar",
            "/repos/DonkeyJJLove/ai_platform/%2e%2e/issues",
            "/repos/DonkeyJJLove/ai_platform/foo/%2E%2E/bar",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(RepositoryMaintenanceError, "unsafe GitHub API path"):
                    backend._validate_api_path("GET", path)

    def test_arbitrary_read_and_delete_routes_are_denied(self):
        backend = self._backend()
        with self.assertRaisesRegex(RepositoryMaintenanceError, "read route not allowlisted"):
            backend._validate_api_path("GET", "/repos/DonkeyJJLove/ai_platform/issues")
        with self.assertRaisesRegex(RepositoryMaintenanceError, "delete route not allowlisted"):
            backend._validate_api_path("DELETE", "/repos/DonkeyJJLove/ai_platform/issues/1")
        with self.assertRaisesRegex(RepositoryMaintenanceError, "outside mission allowlist"):
            backend._validate_api_path(
                "DELETE", "/repos/DonkeyJJLove/ai_platform/git/refs/heads/release/prod"
            )


    def test_delete_route_accepts_every_canonical_cleanup_family(self):
        backend = self._backend()
        branches = (
            "cyber-lion/evidence",
            "docs/evidence",
            "experiment/evidence",
            "integration/evidence",
            "mission/evidence",
            "reconcile/evidence",
            "verification/evidence",
            "__invalid_never_create",
            "tmp-r3-upload-staging",
        )
        for branch in branches:
            with self.subTest(branch=branch):
                backend._validate_api_path(
                    "DELETE", f"/repos/DonkeyJJLove/ai_platform/git/refs/heads/{branch}"
                )

    def test_delete_waits_for_bounded_ref_visibility_without_second_delete(self):
        backend = self._backend()
        branch = "reconcile/example"
        head = "b" * 40
        master = "a" * 40
        admission = "d" * 64
        backend._pending_delete = (branch, head, master, admission, "e" * 64)
        backend.master_sha = lambda: master
        observations = iter((head, head, head, None))
        backend.branch_sha = lambda _branch: next(observations)
        delete_calls = []
        backend._delete_exact_branch_ref_http = lambda path: delete_calls.append(path) or 204
        with patch("cyber_lion.enterprise.repository_maintenance_cleanup.time.sleep", lambda _seconds: None):
            backend.delete_exact_branch_ref(branch, head)
        self.assertEqual(len(delete_calls), 1)
        self.assertIn("reconcile/example", delete_calls[0])
        self.assertIn(admission, backend._consumed_delete_admissions)

    def test_noncanonical_origin_remains_denied(self):
        with self.assertRaisesRegex(RepositoryMaintenanceError, "canonical HTTPS"):
            SlashSafeGitHubRepositoryMaintenanceBackend(
                "DonkeyJJLove/ai_platform",
                "test-token",
                api_url="https://evil.example",
            )


if __name__ == "__main__":
    unittest.main()
