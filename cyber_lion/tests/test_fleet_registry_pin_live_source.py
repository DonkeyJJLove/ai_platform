from __future__ import annotations

import base64
import copy
from dataclasses import fields
from hashlib import sha1, sha256
import inspect
import json
import os
from pathlib import Path
import unittest

from cyber_lion.contracts.repository_expansion import (
    RepositoryManifestObservation,
    RepositoryPinObservation,
)
from cyber_lion.enterprise.conformance import (
    canonical_manifest_digest,
    evaluate_read_only_provider,
)
from cyber_lion.enterprise.federation import RepositoryManifest
from cyber_lion.enterprise.github_repository_read_source import (
    GitHubFleetPinSourceError,
    GitHubFleetRegistryPinReadSource,
    HttpResponse,
    _materialize_live_registry_manifest_observations_with_source,
    _materialize_live_registry_pin_snapshot_with_source,
    materialize_live_registry_manifest_observations,
    materialize_live_registry_pin_snapshot,
)
from cyber_lion.tests.test_enterprise_federation import GLITCHLAB


REGISTRY_PATH = Path("cyber_lion/registry/repositories.json")
R2E4_BASELINE_SNAPSHOT_DIGEST = "6a93f5c2d134306be446976efb10ca23f773b01967489959bc54eb1241de134e"
MANIFEST_PATH = "cyber-lion.repository.json"


def registry_payload() -> bytes:
    return REGISTRY_PATH.read_bytes()


def registry_members() -> tuple[tuple[str, str], ...]:
    value = json.loads(registry_payload().decode("utf-8"))
    return tuple((item["id"], item["default_branch"]) for item in value["repositories"])


def manifest_mapping(repository: str, default_branch: str) -> dict:
    value = copy.deepcopy(GLITCHLAB)
    value["repository"]["id"] = repository
    value["repository"]["url"] = f"https://github.com/{repository}"
    value["repository"]["owner"] = repository.split("/", 1)[0]
    value["repository"]["default_branch"] = default_branch
    value["cyber_lion"]["tile_id"] = "test." + repository.split("/", 1)[1].replace(".", "-")
    return value


def git_blob_sha(raw: bytes) -> str:
    return sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


class FakeFleetSource:
    def __init__(
        self,
        *,
        manifest_false: frozenset[str] = frozenset({"DonkeyJJLove/writeups"}),
        drift_repository: str | None = None,
        drift_kind: str | None = None,
        drift_read_number: int = 2,
        semantic_inject_present: frozenset[str] = frozenset(),
    ) -> None:
        self.members = registry_members()
        self.index = {repository: index for index, (repository, _) in enumerate(self.members, start=1)}
        self.manifest_false = manifest_false
        self.drift_repository = drift_repository
        self.drift_kind = drift_kind
        self.drift_read_number = drift_read_number
        self.semantic_inject_present = semantic_inject_present
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
        if repository == self.drift_repository and count == self.drift_read_number:
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

    def _read_manifest_at_pin(self, pin: RepositoryPinObservation):
        if not pin.manifest_present and pin.repository not in self.semantic_inject_present:
            observation = RepositoryManifestObservation(
                pin.repository,
                pin.default_branch,
                pin.head,
                pin.tree,
                "ABSENT",
                MANIFEST_PATH,
                None,
                None,
                None,
                f"fake-manifest:{pin.repository}:absent",
            ).validate()
            return observation, None, None

        mapping = manifest_mapping(pin.repository, pin.default_branch)
        raw = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        observation = RepositoryManifestObservation(
            pin.repository,
            pin.default_branch,
            pin.head,
            pin.tree,
            "PRESENT",
            MANIFEST_PATH,
            git_blob_sha(raw),
            sha256(raw).hexdigest(),
            canonical_manifest_digest(mapping),
            f"fake-manifest:{pin.repository}:present",
        ).validate()
        return observation, RepositoryManifest.from_mapping(mapping), mapping


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


def manifest_response(
    mapping: dict | None = None,
    *,
    raw: bytes | None = None,
    status: int = 200,
    path: str = MANIFEST_PATH,
    content_type: str = "file",
    encoding: str = "base64",
    blob_sha: str | None = None,
    size: int | None = None,
    content: str | None = None,
) -> HttpResponse:
    if status != 200:
        return response({"message": "error"}, status=status)
    if raw is None:
        raw = json.dumps(
            mapping if mapping is not None else GLITCHLAB,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    envelope = {
        "type": content_type,
        "path": path,
        "encoding": encoding,
        "content": content if content is not None else base64.b64encode(raw).decode("ascii"),
        "sha": blob_sha if blob_sha is not None else git_blob_sha(raw),
        "size": len(raw) if size is None else size,
    }
    return response(envelope)


class FleetRegistryPinLiveSourceTests(unittest.TestCase):
    def snapshot(self, source: FakeFleetSource | None = None):
        return _materialize_live_registry_pin_snapshot_with_source(
            registry_payload(),
            source=source or FakeFleetSource(),
        )

    def pin(self, *, manifest_present: bool = True) -> RepositoryPinObservation:
        return RepositoryPinObservation(
            repository="DonkeyJJLove/glitchlab",
            default_branch="master",
            head="1" * 40,
            tree="2" * 40,
            manifest_present=manifest_present,
            source_ref="test-pin",
        ).validate()

    def read_manifest(
        self,
        http_response: HttpResponse,
        *,
        pin: RepositoryPinObservation | None = None,
    ):
        transport = FakeTransport([http_response])
        source = GitHubFleetRegistryPinReadSource(token="x", transport=transport)
        result = source._read_manifest_at_pin(pin or self.pin())
        return result, transport

    def test_canonical_entrypoint_accepts_registry_payload_only(self):
        signature = inspect.signature(materialize_live_registry_pin_snapshot)
        self.assertEqual(tuple(signature.parameters), ("registry_payload",))
        forbidden = {
            "repository", "default_branch", "head", "tree", "manifest_present",
            "source_ref", "api_origin", "url", "observations",
        }
        self.assertTrue(forbidden.isdisjoint(signature.parameters))

    def test_r2e4_canonical_entrypoint_accepts_registry_payload_only(self):
        signature = inspect.signature(materialize_live_registry_manifest_observations)
        self.assertEqual(tuple(signature.parameters), ("registry_payload",))
        forbidden = {
            "manifest_bytes", "manifest_digest", "manifest_mapping", "repository",
            "head", "tree", "observations", "runtime_authority", "source_ref",
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

    def test_post_manifest_head_drift_is_denied(self):
        repository = registry_members()[0][0]
        source = FakeFleetSource(
            drift_repository=repository,
            drift_kind="head",
            drift_read_number=3,
        )
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "post-manifest drift denied"):
            _materialize_live_registry_manifest_observations_with_source(
                registry_payload(),
                source=source,
            )

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

    def test_manifest_observation_cannot_claim_health_dependencies_or_authority(self):
        names = {field.name for field in fields(RepositoryManifestObservation)}
        self.assertEqual(names, {
            "repository", "default_branch", "head", "tree", "manifest_state",
            "manifest_path", "git_blob_sha", "manifest_byte_sha256",
            "manifest_semantic_digest", "source_ref",
        })
        forbidden = {
            "build_result", "test_result", "failure_classification",
            "known_preexisting_failures", "dependencies", "dependents",
            "runtime_authority", "production_authority", "gate0", "result",
        }
        self.assertTrue(forbidden.isdisjoint(names))

    def test_r2e2_snapshot_determinism_is_preserved(self):
        first = self.snapshot(FakeFleetSource())
        second = self.snapshot(FakeFleetSource())
        self.assertEqual(first.registry_digest, second.registry_digest)
        self.assertEqual(first.snapshot_digest(), second.snapshot_digest())
        self.assertEqual(first.canonical_dict(), second.canonical_dict())

    def test_r2e3_pin_snapshot_is_unchanged_by_manifest_semantic_materialization(self):
        source = FakeFleetSource()
        pin_only = self.snapshot(FakeFleetSource())
        semantic_pin, observations = _materialize_live_registry_manifest_observations_with_source(
            registry_payload(), source=source
        )
        self.assertEqual(pin_only.canonical_dict(), semantic_pin.canonical_dict())
        self.assertEqual(pin_only.snapshot_digest(), semantic_pin.snapshot_digest())
        self.assertEqual(len(observations), 10)
        self.assertEqual(sum(item.manifest_state == "PRESENT" for item, _ in observations), 9)
        self.assertEqual(sum(item.manifest_state == "ABSENT" for item, _ in observations), 1)

    def test_http_source_binds_head_tree_and_manifest_to_exact_head(self):
        head, tree = "1" * 40, "2" * 40
        transport = FakeTransport([
            response({"commit": {"sha": head}}),
            response({"tree": {"sha": tree}}),
            response({"name": MANIFEST_PATH}),
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
            f"https://api.github.com/repos/DonkeyJJLove/example/contents/{MANIFEST_PATH}?ref={head}",
        )
        for _, headers, _ in transport.calls:
            self.assertEqual(headers["Authorization"], "Bearer runtime-token")

    def test_exact_manifest_content_binds_blob_bytes_semantics_and_head(self):
        mapping = copy.deepcopy(GLITCHLAB)
        (observation, manifest, parsed), transport = self.read_manifest(manifest_response(mapping))
        raw = json.dumps(mapping, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.assertEqual(observation.manifest_state, "PRESENT")
        self.assertEqual(observation.git_blob_sha, git_blob_sha(raw))
        self.assertEqual(observation.manifest_byte_sha256, sha256(raw).hexdigest())
        self.assertEqual(observation.manifest_semantic_digest, canonical_manifest_digest(mapping))
        self.assertTrue(observation.source_ref.startswith("github-manifest-live-v1:"))
        self.assertEqual(manifest.repository_id, "DonkeyJJLove/glitchlab")
        self.assertEqual(parsed, mapping)
        self.assertEqual(
            transport.calls[0][0],
            f"https://api.github.com/repos/DonkeyJJLove/glitchlab/contents/{MANIFEST_PATH}?ref={'1' * 40}",
        )

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

    def test_exact_manifest_404_materializes_explicit_absence(self):
        pin = self.pin(manifest_present=False)
        (observation, manifest, mapping), _ = self.read_manifest(
            response({"message": "Not Found"}, status=404), pin=pin
        )
        self.assertEqual(observation.manifest_state, "ABSENT")
        self.assertIsNone(observation.git_blob_sha)
        self.assertIsNone(observation.manifest_byte_sha256)
        self.assertIsNone(observation.manifest_semantic_digest)
        self.assertIsNone(manifest)
        self.assertIsNone(mapping)

    def test_manifest_semantic_state_must_match_r2e3_pin_boolean(self):
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "contradicts pinned presence"):
            self.read_manifest(response({"message": "Not Found"}, status=404), pin=self.pin())
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "contradicts pinned absence"):
            self.read_manifest(manifest_response(copy.deepcopy(GLITCHLAB)), pin=self.pin(manifest_present=False))

    def test_existing_conformance_accepts_observation_derived_bindings(self):
        (observation, _, mapping), _ = self.read_manifest(manifest_response(copy.deepcopy(GLITCHLAB)))
        snapshot, manifest = evaluate_read_only_provider(
            mapping,
            provider_id=observation.repository,
            provider_commit=observation.head,
            expected_commit=observation.head,
            capability="delta.normalize",
            expected_manifest_digest=observation.manifest_semantic_digest,
        )
        self.assertEqual(snapshot.runtime_authority, "read")
        self.assertEqual(snapshot.provider_commit, observation.head)
        self.assertEqual(snapshot.manifest_digest, observation.manifest_semantic_digest)
        self.assertEqual(manifest.repository_id, observation.repository)

    def test_r2e4_twenty_adversarial_manifest_mutations_fail_closed(self):
        def denied(http_response: HttpResponse, pin: RepositoryPinObservation | None = None) -> bool:
            try:
                self.read_manifest(http_response, pin=pin)
            except GitHubFleetPinSourceError:
                return True
            return False

        duplicate_raw = b'{"schema_version":"1.0.0","schema_version":"1.0.0"}'
        wrong_schema = copy.deepcopy(GLITCHLAB)
        wrong_schema["schema_version"] = "2.0.0"
        wrong_id = copy.deepcopy(GLITCHLAB)
        wrong_id["repository"]["id"] = "DonkeyJJLove/other"
        wrong_branch = copy.deepcopy(GLITCHLAB)
        wrong_branch["repository"]["default_branch"] = "main"
        unknown_root = copy.deepcopy(GLITCHLAB)
        unknown_root["unexpected"] = True
        missing_root = copy.deepcopy(GLITCHLAB)
        del missing_root["security"]
        bad_authority = copy.deepcopy(GLITCHLAB)
        bad_authority["authority"]["maximum_level"] = ["local_write"]
        bad_observability = copy.deepcopy(GLITCHLAB)
        bad_observability["observability"]["logs"] = "delta.analysis"
        bad_security = copy.deepcopy(GLITCHLAB)
        bad_security["security"]["trust_boundaries"] = "proposal != authority"

        def head_binding_probe() -> bool:
            mapping = copy.deepcopy(GLITCHLAB)
            (_, _, _), transport = self.read_manifest(manifest_response(mapping))
            return transport.calls[0][0].endswith(f"?ref={'1' * 40}")

        def synthetic_writeups_probe() -> bool:
            source = FakeFleetSource(semantic_inject_present=frozenset({"DonkeyJJLove/writeups"}))
            try:
                _materialize_live_registry_manifest_observations_with_source(
                    registry_payload(), source=source
                )
            except GitHubFleetPinSourceError:
                return True
            return False

        public_signature = inspect.signature(materialize_live_registry_manifest_observations)
        probes = (
            ("M01_DUPLICATE_JSON_KEY", lambda: denied(manifest_response(raw=duplicate_raw))),
            ("M02_SCHEMA_VERSION_SUBSTITUTION", lambda: denied(manifest_response(wrong_schema))),
            ("M03_REPOSITORY_ID_SUBSTITUTION", lambda: denied(manifest_response(wrong_id))),
            ("M04_DEFAULT_BRANCH_SUBSTITUTION", lambda: denied(manifest_response(wrong_branch))),
            ("M05_HEAD_UNBOUND_MANIFEST_CONTENT", head_binding_probe),
            ("M06_UNKNOWN_ROOT_FIELD", lambda: denied(manifest_response(unknown_root))),
            ("M07_MISSING_REQUIRED_ROOT_FIELD", lambda: denied(manifest_response(missing_root))),
            ("M08_AUTHORITY_LEVEL_SHAPE_SUBSTITUTION", lambda: denied(manifest_response(bad_authority))),
            ("M09_OBSERVABILITY_SHAPE_SUBSTITUTION", lambda: denied(manifest_response(bad_observability))),
            ("M10_SECURITY_BOUNDARY_SHAPE_SUBSTITUTION", lambda: denied(manifest_response(bad_security))),
            ("M11_INVALID_UTF8", lambda: denied(manifest_response(raw=b"\xff"))),
            ("M12_OVERSIZED_MANIFEST", lambda: denied(manifest_response(copy.deepcopy(GLITCHLAB), size=1_048_577))),
            ("M13_REDIRECT_RESPONSE", lambda: denied(manifest_response(status=302))),
            ("M14_401_RESPONSE", lambda: denied(manifest_response(status=401))),
            ("M15_403_RESPONSE", lambda: denied(manifest_response(status=403))),
            ("M16_429_RESPONSE", lambda: denied(manifest_response(status=429))),
            ("M17_500_RESPONSE", lambda: denied(manifest_response(status=500))),
            ("M18_WRITEUPS_SYNTHETIC_MANIFEST_INJECTION", synthetic_writeups_probe),
            ("M19_CALLER_SUPPLIED_MANIFEST_BYTES", lambda: "manifest_bytes" not in public_signature.parameters),
            ("M20_CALLER_SUPPLIED_MANIFEST_DIGEST", lambda: "manifest_digest" not in public_signature.parameters),
        )
        self.assertEqual(len(probes), 20)
        for name, probe in probes:
            with self.subTest(name=name):
                self.assertTrue(probe(), name)

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

    @unittest.skipUnless(
        os.environ.get("R2E4_LIVE_MANIFEST_SWEEP") == "1",
        "R2E4 live GitHub manifest sweep is CI-only",
    )
    def test_real_ten_repository_exact_head_manifest_semantic_sweep(self):
        snapshot, records = materialize_live_registry_manifest_observations(registry_payload())
        self.assertEqual(snapshot.snapshot_digest(), R2E4_BASELINE_SNAPSHOT_DIGEST)
        self.assertEqual(len(records), 10)
        present = [(observation, manifest) for observation, manifest in records if observation.manifest_state == "PRESENT"]
        absent = [(observation, manifest) for observation, manifest in records if observation.manifest_state == "ABSENT"]
        self.assertEqual(len(present), 9)
        self.assertEqual(len(absent), 1)
        self.assertEqual(absent[0][0].repository, "DonkeyJJLove/writeups")
        self.assertIsNone(absent[0][1])
        for observation, manifest in present:
            self.assertIsNotNone(manifest)
            self.assertEqual(manifest.repository_id, observation.repository)
            self.assertEqual(manifest.default_branch, observation.default_branch)
            self.assertRegex(observation.git_blob_sha or "", r"^[0-9a-f]{40}$")
            self.assertRegex(observation.manifest_byte_sha256 or "", r"^[0-9a-f]{64}$")
            self.assertRegex(observation.manifest_semantic_digest or "", r"^[0-9a-f]{64}$")
            self.assertTrue(observation.source_ref.startswith("github-manifest-live-v1:"))

        print("R2E4_LIVE_MANIFEST_SWEEP=PASS")
        print("R2E4_LIVE_MEMBER_COUNT=10")
        print("R2E4_MANIFEST_PRESENT_COUNT=9")
        print("R2E4_MANIFEST_ABSENT_COUNT=1")
        print("R2E4_WRITEUPS_MANIFEST_STATE=ABSENT")
        print(f"R2E4_REGISTRY_DIGEST={snapshot.registry_digest}")
        print(f"R2E4_PIN_SNAPSHOT_DIGEST={snapshot.snapshot_digest()}")
        for observation, _ in records:
            print(
                "R2E4_MANIFEST="
                + observation.repository
                + "|"
                + observation.default_branch
                + "|"
                + observation.head
                + "|"
                + observation.tree
                + "|"
                + observation.manifest_state
                + "|"
                + (observation.git_blob_sha or "NULL")
                + "|"
                + (observation.manifest_byte_sha256 or "NULL")
                + "|"
                + (observation.manifest_semantic_digest or "NULL")
            )


if __name__ == "__main__":
    unittest.main()
