from __future__ import annotations

import json
import unittest

from cyber_lion.enterprise.github_repository_read_source import (
    GitHubRESTReadSource,
    GitHubReadSourceError,
    HttpResponse,
    UrllibReadOnlyTransport,
)

REPO = "DonkeyJJLove/ai_platform"
MASTER = "1" * 40
TREE = "2" * 40
HEAD = "3" * 40


def response(value, status=200):
    return HttpResponse(status=status, headers={}, body=json.dumps(value).encode("utf-8"))


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, headers, timeout):
        self.calls.append((url, dict(headers), timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP call")
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


class GitHubRepositoryReadSourceTests(unittest.TestCase):
    def source(self, responses):
        transport = FakeTransport(responses)
        return GitHubRESTReadSource(
            token="runtime-token",
            transport=transport,
            api_base="https://api.github.test",
            timeout=3,
        ), transport

    def test_token_is_loaded_from_environment_only_factory(self):
        source = GitHubRESTReadSource.from_environment(
            environ={"GITHUB_TOKEN": "secret"},
            transport=FakeTransport([]),
            api_base="https://api.github.test",
        )
        self.assertIsInstance(source, GitHubRESTReadSource)
        with self.assertRaises(GitHubReadSourceError):
            GitHubRESTReadSource.from_environment(
                environ={},
                transport=FakeTransport([]),
                api_base="https://api.github.test",
            )

    def test_default_head_binds_exact_head_and_tree(self):
        source, transport = self.source([
            response({"commit": {"sha": MASTER}}),
            response({"tree": {"sha": TREE}}),
        ])
        self.assertEqual(source.default_head(REPO, "master"), (MASTER, TREE))
        self.assertEqual(len(transport.calls), 2)
        for _, headers, _ in transport.calls:
            self.assertEqual(headers["Authorization"], "Bearer runtime-token")

    def test_branch_pagination_uses_bounded_pages(self):
        first = [{"name": f"branch-{i}", "commit": {"sha": f"{i:040x}"[-40:]}} for i in range(100)]
        second = [{"name": "master", "commit": {"sha": MASTER}}]
        source, _ = self.source([response(first), response(second)])
        page1, cursor = source.list_branches_page(REPO, None)
        self.assertEqual(len(page1), 100)
        self.assertEqual(cursor, "2")
        page2, cursor2 = source.list_branches_page(REPO, cursor)
        self.assertEqual(len(page2), 1)
        self.assertIsNone(cursor2)

    def test_compare_statuses_map_exactly(self):
        cases = [
            ("identical", 0, 0, "IDENTICAL"),
            ("behind", 0, 4, "HEAD_ANCESTOR_OF_DEFAULT"),
            ("ahead", 3, 0, "DEFAULT_ANCESTOR_OF_HEAD"),
            ("diverged", 2, 5, "DIVERGED"),
        ]
        for status, ahead, behind, expected in cases:
            with self.subTest(status=status):
                source, _ = self.source([response({
                    "status": status,
                    "ahead_by": ahead,
                    "behind_by": behind,
                })])
                evidence = source.compare_to_default(REPO, MASTER, HEAD, "feature")
                self.assertEqual(evidence.ancestry_state, expected)
                self.assertEqual(evidence.ahead_by, ahead)
                self.assertEqual(evidence.behind_by, behind)

    def test_identical_heads_do_not_require_network(self):
        source, transport = self.source([])
        evidence = source.compare_to_default(REPO, MASTER, MASTER, "feature")
        self.assertEqual(evidence.ancestry_state, "IDENTICAL")
        self.assertEqual(transport.calls, [])

    def test_no_common_ancestor_is_explicit_404_only(self):
        source, _ = self.source([
            response({"message": "No common ancestor between the two commits"}, status=404)
        ])
        evidence = source.compare_to_default(REPO, MASTER, HEAD, "foreign")
        self.assertEqual(evidence.ancestry_state, "NO_COMMON_ANCESTOR")
        self.assertIsNone(evidence.ahead_by)
        self.assertIsNone(evidence.behind_by)

    def test_unknown_compare_status_is_denied(self):
        source, _ = self.source([response({
            "status": "mystery",
            "ahead_by": 1,
            "behind_by": 1,
        })])
        with self.assertRaises(GitHubReadSourceError):
            source.compare_to_default(REPO, MASTER, HEAD, "feature")

    def test_non_2xx_and_rate_limit_fail_closed(self):
        for status in (401, 403, 429, 500):
            with self.subTest(status=status):
                source, _ = self.source([response({"message": "error"}, status=status)])
                with self.assertRaises(GitHubReadSourceError):
                    source.default_head(REPO, "master")

    def test_malformed_json_and_schema_fail_closed(self):
        source, _ = self.source([HttpResponse(200, {}, b"{")])
        with self.assertRaises(GitHubReadSourceError):
            source.default_head(REPO, "master")

        source2, _ = self.source([response([])])
        with self.assertRaises(GitHubReadSourceError):
            source2.default_head(REPO, "master")

    def test_timeout_fails_closed(self):
        source, _ = self.source([TimeoutError("timeout")])
        with self.assertRaises(GitHubReadSourceError):
            source.default_head(REPO, "master")

    def test_repository_and_default_branch_substitution_denied(self):
        source, _ = self.source([])
        with self.assertRaises(GitHubReadSourceError):
            source.default_head("other/repo", "master")
        with self.assertRaises(GitHubReadSourceError):
            source.default_head(REPO, "main")

    def test_transport_exposes_get_only(self):
        transport = UrllibReadOnlyTransport()
        self.assertTrue(callable(getattr(transport, "get")))
        for name in ("post", "put", "patch", "delete"):
            self.assertFalse(hasattr(transport, name))


if __name__ == "__main__":
    unittest.main()
