from __future__ import annotations

from dataclasses import fields
import inspect
import json
import os
from pathlib import Path
import unittest

from cyber_lion.contracts.repository_expansion import RepositoryPinObservation
from cyber_lion.enterprise.github_repository_read_source import (
    GitHubFleetPinSourceError,
    GitHubFleetRegistryPinReadSource,
    HttpResponse,
    _materialize_live_registry_pin_snapshot_with_source,
    materialize_live_registry_pin_snapshot,
)


REGISTRY_PATH = Path("cyber_lion/registry/repositories.json")


def registry_payload() -> bytes:
    return REGISTRY_PATH.read_bytes()


def registry_members() -> tuple[tuple[str, str], ...]:
    value = json.loads(registry_payload().decode("utf-8"))
    return tuple((item["id"], item["default_branch"]) for item in value["repositories"])


class FakeFleetSource:
    def __init__(
        self,
        *,
        manifest_false: frozenset[str] = frozenset({"DonkeyJJLove/writeups"}),
        drift_repository: str | None = None,
        drift_kind: str | None = None,
    ) -> None:
        self.members = registry_members()
        self.index = {repository: index for index, (repository, _) in enumerate(self.members, start=1)}
        self.manifest_false = manifest_false
        self.drift_repository = drift_repository
        self.drift_kind = drift_kind
        self.head_reads: dict[str, int] = {}
        self.head_calls: list[tuple[str, str]] = []
        self.manifest_calls: list[tuple[str, str]] = []

    def expected(self, repository: str) -> tuple[str, str]:
        index = self.index[repository]
        return f"{index:040x}", f"{index + 100:040x}"

    def read_default_head(self, repository: str, default_branch: str) -> tuple[str, str]:
        self.head_calls.append((repository, default_branch))
        expected_branch = dict(self.members)[repository]
        if default_branch != expected_branch:
            raise AssertionError("default branch substitution reached source")
        count = self.head_reads.get(repository, 0) + 1
        self.head_reads[repository] = count
        head, tree = self.expected(repository)
        if repository == self.drift_repository and count == 2:
            if self.drift_kind == "head":
                head = "f" * 40
            elif self.drift_kind == "tree":
                tree = "e" * 40
        return head, tree

    def manifest_present(self, repository: str, head: str) -> bool:
        self.manifest_calls.append((repository, head))
        expected_head, _ = self.expected(repository)
        if head != expected_head:
            raise AssertionError("manifest read not bound to first-pass head")
        return repository not in self.manifest_false


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def get(self, url: str, *, headers, timeout: float) -> HttpResponse:
        self.calls.append((url, dict(headers), timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP call")
        return self.responses.pop(0)


def response(value: object, status: int = 200) -> HttpResponse:
    return HttpResponse(status=status, headers={}, body=json.dumps(value).encode("utf-8"))


class FleetRegistryPinLiveSourceTests(unittest.TestCase):
    def snapshot(self, source: FakeFleetSource | None = None):
        return _materialize_live_registry_pin_snapshot_with_source(
            registry_payload(),
            source=source or FakeFleetSource(),
        )

    def test_canonical_entrypoint_accepts_registry_payload_only(self):
        signature = inspect.signature(materialize_live_registry_pin_snapshot)
        self.assertEqual(tuple(signature.parameters), ("registry_payload",))
        forbidden = {
            "repository", "default_branch", "head", "tree", "manifest_present",
            "source_ref", "api_origin", "url", "observations",
        }
        self.assertTrue(forbidden.isdisjoint(signature.parameters))

    def test_synthetic_pin_cannot_be_injected_through_canonical_signature(self):
        signature = inspect.signature(materialize_live_registry_pin_snapshot)
        self.assertNotIn("head", signature.parameters)
        self.assertNotIn("tree", signature.parameters)
        self.assertNotIn("observations", signature.parameters)

    def test_manifest_and_source_ref_are_source_derived(self):
        source = FakeFleetSource()
        snapshot = self.snapshot(source)
        by_repo = {item.repository: item for item in snapshot.observations}
        self.assertFalse(by_repo["DonkeyJJLove/writeups"].manifest_present)
        self.assertTrue(all(item.source_ref.startswith("github-live-v1:") for item in snapshot.observations))
        self.assertEqual(len(source.manifest_calls), len(snapshot.observations))
        for repository, head in source.manifest_calls:
            self.assertEqual(head, source.expected(repository)[0])

    def test_exact_registry_coverage_and_mixed_default_branches(self):
        source = FakeFleetSource()
        snapshot = self.snapshot(source)
        expected = registry_members()
        self.assertEqual(len(snapshot.members), 10)
        self.assertEqual(
            {(item.repository, item.default_branch) for item in snapshot.members},
            set(expected),
        )
        self.assertEqual({branch for _, branch in expected}, {"master", "main"})
        self.assertEqual(set(source.head_calls[:10]), set(expected))
        self.assertEqual(set(source.head_calls[10:]), set(expected))

    def test_noncanonical_registry_missing_member_is_denied_before_live_reads(self):
        raw = json.loads(registry_payload().decode("utf-8"))
        raw["repositories"] = raw["repositories"][:-1]
        source = FakeFleetSource()
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "registry substitution denied"):
            _materialize_live_registry_pin_snapshot_with_source(
                json.dumps(raw, separators=(",", ":")).encode("utf-8"),
                source=source,
            )
        self.assertEqual(source.head_calls, [])

    def test_noncanonical_registry_extra_member_is_denied_before_live_reads(self):
        raw = json.loads(registry_payload().decode("utf-8"))
        extra = dict(raw["repositories"][0])
        extra["id"] = "DonkeyJJLove/not-registered"
        raw["repositories"].append(extra)
        source = FakeFleetSource()
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "registry substitution denied"):
            _materialize_live_registry_pin_snapshot_with_source(
                json.dumps(raw, separators=(",", ":")).encode("utf-8"),
                source=source,
            )
        self.assertEqual(source.head_calls, [])

    def test_default_branch_substitution_in_registry_is_denied(self):
        raw = json.loads(registry_payload().decode("utf-8"))
        raw["repositories"][0]["default_branch"] = "main"
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "registry substitution denied"):
            _materialize_live_registry_pin_snapshot_with_source(
                json.dumps(raw, separators=(",", ":")).encode("utf-8"),
                source=FakeFleetSource(),
            )

    def test_head_drift_during_full_sweep_is_denied(self):
        repository = registry_members()[0][0]
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "fleet sweep drift denied"):
            self.snapshot(FakeFleetSource(drift_repository=repository, drift_kind="head"))

    def test_tree_drift_during_full_sweep_is_denied(self):
        repository = registry_members()[1][0]
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "fleet sweep drift denied"):
            self.snapshot(FakeFleetSource(drift_repository=repository, drift_kind="tree"))

    def test_output_cannot_claim_health_dependencies_or_authority(self):
        snapshot = self.snapshot()
        names = {field.name for field in fields(RepositoryPinObservation)}
        self.assertEqual(
            names,
            {"repository", "default_branch", "head", "tree", "manifest_present", "source_ref"},
        )
        self.assertTrue({
            "health", "build_result", "test_result", "failure_classification",
            "dependencies", "dependents", "authority", "gate0", "result",
            "credentials", "token",
        }.isdisjoint(names))
        self.assertNotIn("runtime-token", json.dumps(snapshot.canonical_dict()))

    def test_r2e2_snapshot_determinism_is_preserved(self):
        first = self.snapshot(FakeFleetSource())
        second = self.snapshot(FakeFleetSource())
        self.assertEqual(first.registry_digest, second.registry_digest)
        self.assertEqual(first.snapshot_digest(), second.snapshot_digest())
        self.assertEqual(first.canonical_dict(), second.canonical_dict())

    def test_http_source_binds_head_tree_and_manifest_to_exact_head(self):
        head, tree = "1" * 40, "2" * 40
        transport = FakeTransport([
            response({"commit": {"sha": head}}),
            response({"tree": {"sha": tree}}),
            response({"name": "cyber-lion.repository.json"}),
        ])
        source = GitHubFleetRegistryPinReadSource(token="runtime-token", transport=transport, timeout=3)
        self.assertEqual(source.read_default_head("DonkeyJJLove/example", "main"), (head, tree))
        self.assertTrue(source.manifest_present("DonkeyJJLove/example", head))
        self.assertEqual(
            transport.calls[0][0],
            "https://api.github.com/repos/DonkeyJJLove/example/branches/main",
        )
        self.assertEqual(
            transport.calls[1][0],
            f"https://api.github.com/repos/DonkeyJJLove/example/git/commits/{head}",
        )
        self.assertEqual(
            transport.calls[2][0],
            f"https://api.github.com/repos/DonkeyJJLove/example/contents/cyber-lion.repository.json?ref={head}",
        )
        for _, headers, _ in transport.calls:
            self.assertEqual(headers["Authorization"], "Bearer runtime-token")

    def test_manifest_404_is_false_and_other_failures_are_not_absence(self):
        head = "1" * 40
        source_404 = GitHubFleetRegistryPinReadSource(
            token="x", transport=FakeTransport([response({"message": "Not Found"}, status=404)])
        )
        self.assertFalse(source_404.manifest_present("DonkeyJJLove/example", head))
        for status in (302, 401, 403, 429, 500):
            with self.subTest(status=status):
                source = GitHubFleetRegistryPinReadSource(
                    token="x", transport=FakeTransport([response({"message": "error"}, status=status)])
                )
                with self.assertRaises(GitHubFleetPinSourceError):
                    source.manifest_present("DonkeyJJLove/example", head)

    def test_branch_and_commit_non_2xx_fail_closed(self):
        for status in (302, 401, 403, 404, 429, 500):
            with self.subTest(status=status):
                source = GitHubFleetRegistryPinReadSource(
                    token="x", transport=FakeTransport([response({"message": "error"}, status=status)])
                )
                with self.assertRaises(GitHubFleetPinSourceError):
                    source.read_default_head("DonkeyJJLove/example", "main")

    def test_concrete_source_has_no_api_origin_parameter_or_mutation_verbs(self):
        signature = inspect.signature(GitHubFleetRegistryPinReadSource)
        self.assertNotIn("api_base", signature.parameters)
        source = GitHubFleetRegistryPinReadSource(token="x", transport=FakeTransport([]))
        for name in ("post", "put", "patch", "delete"):
            self.assertFalse(hasattr(source, name))

    def test_environment_factory_requires_token_without_exposing_it(self):
        source = GitHubFleetRegistryPinReadSource.from_environment(
            environ={"GITHUB_TOKEN": "secret-token"},
            transport=FakeTransport([]),
        )
        self.assertIsInstance(source, GitHubFleetRegistryPinReadSource)
        self.assertNotIn("secret-token", repr(source))
        with self.assertRaises(GitHubFleetPinSourceError):
            GitHubFleetRegistryPinReadSource.from_environment(
                environ={}, transport=FakeTransport([])
            )

    @unittest.skipUnless(
        os.environ.get("R2E3_LIVE_FLEET_SWEEP") == "1",
        "R2E3 live GitHub sweep is CI-only",
    )
    def test_real_ten_repository_read_only_github_sweep(self):
        snapshot = materialize_live_registry_pin_snapshot(registry_payload())
        self.assertEqual(len(snapshot.members), 10)
        self.assertEqual(len(snapshot.observations), 10)
        self.assertEqual({item.default_branch for item in snapshot.members}, {"master", "main"})
        by_repo = {item.repository: item for item in snapshot.observations}
        self.assertFalse(by_repo["DonkeyJJLove/writeups"].manifest_present)
        self.assertTrue(all(len(item.head) == 40 and len(item.tree) == 40 for item in snapshot.observations))
        print("R2E3_LIVE_FLEET_SWEEP=PASS")
        print("R2E3_LIVE_MEMBER_COUNT=10")
        print(f"R2E3_REGISTRY_DIGEST={snapshot.registry_digest}")
        print(f"R2E3_SNAPSHOT_DIGEST={snapshot.snapshot_digest()}")
        print("R2E3_WRITEUPS_MANIFEST_PRESENT=FALSE")
        for item in snapshot.observations:
            print(
                "R2E3_MEMBER="
                + item.repository
                + "|"
                + item.default_branch
                + "|"
                + item.head
                + "|"
                + item.tree
                + "|"
                + ("MANIFEST" if item.manifest_present else "NO_MANIFEST")
            )


if __name__ == "__main__":
    unittest.main()
