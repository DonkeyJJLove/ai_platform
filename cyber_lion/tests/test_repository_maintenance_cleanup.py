import unittest

from cyber_lion.enterprise.repository_maintenance_cleanup import (
    SlashSafeGitHubRepositoryMaintenanceBackend,
)


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

    def test_delete_path_preserves_slash_and_is_exact(self):
        backend = self._backend()
        calls = []

        def request(method, path, body=None, *, allow_404=False):
            calls.append((method, path, allow_404))
            if method == "GET":
                return 200, {"object": {"sha": "b" * 40}}
            if method == "DELETE":
                return 204, None
            raise AssertionError("unexpected method")

        backend._request = request
        backend.delete_exact_branch_ref("mission/e003-r5-channel-replacement-projection", "b" * 40)
        self.assertEqual(
            calls[-1],
            (
                "DELETE",
                "/repos/DonkeyJJLove/ai_platform/git/refs/heads/mission/e003-r5-channel-replacement-projection",
                False,
            ),
        )


if __name__ == "__main__":
    unittest.main()
