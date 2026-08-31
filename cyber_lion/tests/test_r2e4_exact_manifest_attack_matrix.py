from __future__ import annotations

import copy
from dataclasses import fields
from hashlib import sha1
import inspect
import json
import unittest

from cyber_lion.contracts.repository_expansion import (
    FleetRegistryPinSnapshot,
    RepositoryManifestObservation,
    RepositoryPinObservation,
)
from cyber_lion.enterprise.federation import RepositoryManifest
from cyber_lion.enterprise.models import EnterpriseModelError
from cyber_lion.enterprise.github_repository_read_source import (
    GitHubFleetPinSourceError,
    GitHubFleetRegistryPinReadSource,
    _materialize_live_registry_manifest_observations_with_source,
    _materialize_live_registry_pin_snapshot_with_source,
    materialize_live_registry_manifest_observations,
)
from cyber_lion.tests.test_enterprise_federation import GLITCHLAB
from cyber_lion.tests.test_fleet_registry_pin_live_source import (
    FakeFleetSource,
    FakeTransport,
    git_blob_sha,
    git_tree_sha,
    manifest_mapping,
    manifest_response,
    manifest_tree_entry,
    registry_payload,
    response,
    tree_entries_for_manifest_response,
    tree_response,
)


F_ATTACKS = (
    "F01_HEAD_SUBSTITUTION",
    "F02_TREE_SUBSTITUTION",
    "F03_MANIFEST_BLOB_SUBSTITUTION",
    "F04_MANIFEST_BYTES_SUBSTITUTION",
    "F05_MANIFEST_PATH_SUBSTITUTION",
    "F06_POST_HEAD_READ_DRIFT",
    "F07_POST_TREE_READ_DRIFT",
    "F08_POST_MANIFEST_READ_HEAD_DRIFT",
    "F09_WRONG_BLOB_REBIND",
    "F10_BYTE_SHA256_SUBSTITUTION",
    "F11_SOURCE_REF_SUBSTITUTION",
    "F12_SYNTHETIC_OBSERVATION_INJECTION",
    "F13_REGISTRY_MEMBER_SUBSTITUTION",
    "F14_REGISTRY_EXTRA_MEMBER",
    "F15_REGISTRY_MISSING_MEMBER",
    "F16_MANIFEST_404_PROMOTION",
    "F17_NON_404_AS_ABSENCE",
    "F18_STALE_HEAD_ACCEPTANCE",
    "F19_TREE_ONLY_AUTHORITY",
    "F20_SNAPSHOT_ONLY_AUTHORITY",
)

M_ATTACKS = (
    "M01_DUPLICATE_JSON_KEY",
    "M02_UNKNOWN_ROOT_FIELD",
    "M03_UNKNOWN_MANIFEST_FIELD",
    "M04_MISSING_REQUIRED_FIELD",
    "M05_WRONG_NATIVE_STRING_TYPE",
    "M06_BOOL_AS_INTEGER_CONFUSION",
    "M07_INTEGER_AS_STRING_COERCION",
    "M08_LIST_AS_TUPLE_COERCION",
    "M09_NULL_SUBSTITUTION",
    "M10_TRAILING_NON_JSON_CONTENT",
    "M11_INVALID_UTF8",
    "M12_NON_OBJECT_ROOT",
    "M13_NESTED_UNKNOWN_FIELD",
    "M14_AUTHORITY_FIELD_INJECTION",
    "M15_HEALTH_FIELD_INJECTION",
    "M16_DEPENDENCY_FIELD_INJECTION",
    "M17_REPOSITORY_ID_SUBSTITUTION",
    "M18_SCHEMA_VERSION_SUBSTITUTION",
    "M19_CAPABILITY_TYPE_SUBSTITUTION",
    "M20_SEMANTIC_RESEAL_AFTER_MUTATION",
)

T_ATTACKS = (
    "T01_TREE_RESPONSE_SHA_SUBSTITUTION",
    "T02_TREE_ENTRY_MANIFEST_BLOB_SHA_SUBSTITUTION",
    "T03_TREE_ENTRY_MANIFEST_PATH_SUBSTITUTION",
    "T04_DUPLICATE_MANIFEST_PATH_ENTRY",
    "T05_MANIFEST_ENTRY_TYPE_TREE",
    "T06_MANIFEST_ENTRY_TYPE_COMMIT",
    "T07_MANIFEST_ENTRY_MISSING_WHEN_PIN_PRESENT",
    "T08_MANIFEST_ENTRY_PRESENT_WHEN_PIN_ABSENT",
    "T09_TREE_OBJECT_RESEAL_WITH_MUTATED_ENTRY",
    "T10_TREE_ENTRY_ORDER_SUBSTITUTION",
    "T11_TREE_ENTRY_MODE_SUBSTITUTION",
    "T12_TREE_RESPONSE_TRUNCATED",
    "T13_TREE_HTTP_301",
    "T14_TREE_HTTP_401",
    "T15_TREE_HTTP_403",
    "T16_TREE_HTTP_404",
    "T17_TREE_HTTP_429",
    "T18_TREE_HTTP_500",
    "T19_TREE_RESPONSE_MALFORMED_OBJECT",
    "T20_CONTENTS_AND_TREE_COLLUSIVE_BLOB_SUBSTITUTION_WITHOUT_VALID_PIN_TREE_SHA",
)

F_IDENTITY_PROVENANCE = "R2E4_SPECTRA_IMPLEMENTATION_FALSIFICATION_R1_USER_LITERAL"

AI_PLATFORM_GOLDEN_TREE = (
    {"path": ".github", "mode": "040000", "type": "tree", "sha": "143d34e68844589680b64f30518f0166b6e9eee5"},
    {"path": ".gitignore", "mode": "100644", "type": "blob", "sha": "397f0dafa83fce8c2eb92db224d2ebbfc6fc0afd"},
    {"path": ".lion", "mode": "040000", "type": "tree", "sha": "9f3797d487034e234f38e20f4a9fa0424e8353aa"},
    {"path": "AI_NATIVE_ROADMAP.md", "mode": "100644", "type": "blob", "sha": "c9dfebf5fb80dc4dd3ecdcfaba9c996c87db070c"},
    {"path": "LAT_GLX_PROJECT_MOSAIC.MD", "mode": "100644", "type": "blob", "sha": "d226594bdc3591b3197f2d56b2bb80f46b39db88"},
    {"path": "LION", "mode": "040000", "type": "tree", "sha": "0bc812a55a85f92bd6d381b5656914ad48a4eb09"},
    {"path": "OPEN_SOURCE_LICENSES.md", "mode": "100644", "type": "blob", "sha": "d53c12e5d4c9a932f32b4438acd7b3df79531839"},
    {"path": "README.md", "mode": "100644", "type": "blob", "sha": "26243db6fa21fa7697759ef72161602c6ab55ad0"},
    {"path": "cyber-lion.repository.json", "mode": "100644", "type": "blob", "sha": "4eb2b3b6ae1929c58ca381b5b41e1b8c1808b63a"},
    {"path": "cyber_lion", "mode": "040000", "type": "tree", "sha": "7569672d48d0cd4d4a514b311ffb7be875f45321"},
    {"path": "docs", "mode": "040000", "type": "tree", "sha": "a862f88916e441d213c05d40fe3fe323c05df4f3"},
    {"path": "examples", "mode": "040000", "type": "tree", "sha": "895f28f9c353018bc054bb58ff9be23165cef0c0"},
    {"path": "platform.md", "mode": "100644", "type": "blob", "sha": "de354909e568e766a0c0cebc6ee0a0d7db8a90b4"},
    {"path": "tests", "mode": "040000", "type": "tree", "sha": "fe0a90a6cfa77cab8033ce9e55411dde76717727"},
    {"path": "tools", "mode": "040000", "type": "tree", "sha": "7880ac01341df54155c992db22e2632c14628793"},
    {"path": "writeups", "mode": "040000", "type": "tree", "sha": "a9a0a781c50f8487ef6eab5ae9d6f0b4d55cf2c9"},
)

SBOM_GOLDEN_TREE = (
    {"path": ".dockerignore", "mode": "100644", "type": "blob", "sha": "6b8710a711f3b689885aa5c26c6c06bde348e82b"},
    {"path": ".github", "mode": "040000", "type": "tree", "sha": "5f6e49a7eb6d9971be8e63ff02352250d84c5240"},
    {"path": ".gitignore", "mode": "100644", "type": "blob", "sha": "c49f0b2aefe1ec18784c5e7f670d7b28ca5e5ddd"},
    {"path": "AID_CONTRACT.md", "mode": "100644", "type": "blob", "sha": "5c1b2fb3020282bba283bc51a6bf39252c9a83b1"},
    {"path": "AI_NATIVE_ROADMAP.md", "mode": "100644", "type": "blob", "sha": "764577d682fc1462906dafc88b4fa24428e7956f"},
    {"path": "Dockerfile", "mode": "100644", "type": "blob", "sha": "ac416da8b088590a7ea29641a3261af569a14dc7"},
    {"path": "PROCESS_GUARD.md", "mode": "100644", "type": "blob", "sha": "686a92ea76e3ef06da27006080e2593d6eb5856d"},
    {"path": "README.md", "mode": "100644", "type": "blob", "sha": "b6797698cd6c6e29ab2eeab69f3def6997ee6746"},
    {"path": "cyber-lion.repository.json", "mode": "100644", "type": "blob", "sha": "b12be2426db78004a5b9c358aff55dbfbc6a8b53"},
    {"path": "docs", "mode": "040000", "type": "tree", "sha": "ffdc102c7c6a0051690056db6a851fe0bdfa8a96"},
    {"path": "img", "mode": "040000", "type": "tree", "sha": "72736056b7761d6e307f82aa2fd40761bee27fb4"},
    {"path": "kryptologia-informacyjna-sbom.md", "mode": "100644", "type": "blob", "sha": "2b6e7d200e030c558d7f26cd27b8e9fc634dc23f"},
    {"path": "lab", "mode": "040000", "type": "tree", "sha": "b5ece0e8693fc10302c3cd7cff4b55b6a2fffbef"},
    {"path": "sbom_arkusz_jenkins_elastic_lab.xlsx", "mode": "100644", "type": "blob", "sha": "1bfd9adba489ed5f189fefd6a6cabc81e4c03c1d"},
    {"path": "środowiska-testowe", "mode": "040000", "type": "tree", "sha": "70c7d117d72943d090becb380068e380b1af8642"},
)


class ExactManifestAttackMatrixTests(unittest.TestCase):
    def pin(
        self,
        *,
        manifest_present: bool = True,
        tree: str | None = None,
    ) -> RepositoryPinObservation:
        if tree is None:
            tree = git_tree_sha([]) if not manifest_present else "2" * 40
        return RepositoryPinObservation(
            repository="DonkeyJJLove/glitchlab",
            default_branch="master",
            head="1" * 40,
            tree=tree,
            manifest_present=manifest_present,
            source_ref="matrix-pin",
        ).validate()

    def read_manifest(
        self,
        http_response,
        *,
        pin: RepositoryPinObservation | None = None,
        tree_http_response=None,
    ):
        entries = tree_entries_for_manifest_response(http_response)
        if pin is None:
            pin = self.pin(
                manifest_present=http_response.status == 200,
                tree=git_tree_sha(entries),
            )
        if tree_http_response is None:
            tree_http_response = tree_response(entries, response_sha=pin.tree)
        source = GitHubFleetRegistryPinReadSource(
            token="matrix-token",
            transport=FakeTransport([http_response, tree_http_response]),
        )
        return source._read_manifest_at_pin(pin)

    def assert_manifest_denied(
        self,
        http_response,
        *,
        pin: RepositoryPinObservation | None = None,
        tree_http_response=None,
        regex: str | None = None,
    ) -> None:
        context = (
            self.assertRaisesRegex(GitHubFleetPinSourceError, regex)
            if regex is not None
            else self.assertRaises(GitHubFleetPinSourceError)
        )
        with context:
            self.read_manifest(
                http_response,
                pin=pin,
                tree_http_response=tree_http_response,
            )

    def valid_manifest_case(self):
        raw = json.dumps(GLITCHLAB, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        content_response = manifest_response(raw=raw)
        blob_sha = git_blob_sha(raw)
        entries = [manifest_tree_entry(blob_sha)]
        pin = self.pin(tree=git_tree_sha(entries))
        return raw, content_response, blob_sha, entries, pin

    def test_F01_head_substitution(self):
        with self.assertRaises(TypeError):
            materialize_live_registry_manifest_observations(
                registry_payload(), head="f" * 40  # type: ignore[call-arg]
            )

    def test_F02_tree_substitution(self):
        with self.assertRaises(TypeError):
            materialize_live_registry_manifest_observations(
                registry_payload(), tree="e" * 40  # type: ignore[call-arg]
            )

    def test_F03_manifest_blob_substitution(self):
        raw = json.dumps(GLITCHLAB, separators=(",", ":")).encode("utf-8")
        other = raw + b"\n"
        self.assert_manifest_denied(
            manifest_response(raw=raw, blob_sha=git_blob_sha(other)),
            regex="Git blob identity mismatch",
        )

    def test_F04_manifest_bytes_substitution(self):
        original = copy.deepcopy(GLITCHLAB)
        original_raw = json.dumps(original, separators=(",", ":")).encode("utf-8")
        mutated = copy.deepcopy(original)
        mutated["cyber_lion"]["tile_id"] = "mutated.tile"
        mutated_raw = json.dumps(mutated, separators=(",", ":")).encode("utf-8")
        self.assert_manifest_denied(
            manifest_response(raw=mutated_raw, blob_sha=git_blob_sha(original_raw)),
            regex="Git blob identity mismatch",
        )

    def test_F05_manifest_path_substitution(self):
        self.assert_manifest_denied(
            manifest_response(copy.deepcopy(GLITCHLAB), path="other.repository.json"),
            regex="path substitution denied",
        )

    def test_F06_post_head_read_drift(self):
        repository = "DonkeyJJLove/HA2D"
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "fleet sweep drift denied"):
            _materialize_live_registry_pin_snapshot_with_source(
                registry_payload(),
                source=FakeFleetSource(
                    drift_repository=repository,
                    drift_kind="head",
                    drift_read_number=2,
                ),
            )

    def test_F07_post_tree_read_drift(self):
        repository = "DonkeyJJLove/SymulacjaKaskadySieciowej"
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "fleet sweep drift denied"):
            _materialize_live_registry_pin_snapshot_with_source(
                registry_payload(),
                source=FakeFleetSource(
                    drift_repository=repository,
                    drift_kind="tree",
                    drift_read_number=2,
                ),
            )

    def test_F08_post_manifest_read_head_drift(self):
        repository = "DonkeyJJLove/HA2D"
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "post-manifest drift denied"):
            _materialize_live_registry_manifest_observations_with_source(
                registry_payload(),
                source=FakeFleetSource(
                    drift_repository=repository,
                    drift_kind="head",
                    drift_read_number=3,
                ),
            )

    def test_F09_wrong_blob_rebind(self):
        self.assert_manifest_denied(
            manifest_response(copy.deepcopy(GLITCHLAB), blob_sha="0" * 40),
            regex="Git blob identity mismatch",
        )

    def test_F10_byte_sha256_substitution(self):
        signature = inspect.signature(materialize_live_registry_manifest_observations)
        self.assertNotIn("manifest_byte_sha256", signature.parameters)
        self.assertNotIn("manifest_digest", signature.parameters)
        with self.assertRaises(TypeError):
            materialize_live_registry_manifest_observations(
                registry_payload(), manifest_digest="0" * 64  # type: ignore[call-arg]
            )

    def test_F11_source_ref_substitution(self):
        signature = inspect.signature(materialize_live_registry_manifest_observations)
        self.assertNotIn("source_ref", signature.parameters)
        with self.assertRaises(TypeError):
            materialize_live_registry_manifest_observations(
                registry_payload(), source_ref="attacker"  # type: ignore[call-arg]
            )

    def test_F12_synthetic_observation_injection(self):
        signature = inspect.signature(materialize_live_registry_manifest_observations)
        self.assertNotIn("observations", signature.parameters)
        with self.assertRaises(TypeError):
            materialize_live_registry_manifest_observations(
                registry_payload(), observations=()  # type: ignore[call-arg]
            )

    def test_F13_registry_member_substitution(self):
        value = json.loads(registry_payload().decode("utf-8"))
        value["repositories"][0]["id"] = "DonkeyJJLove/substituted"
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "registry substitution denied"):
            _materialize_live_registry_pin_snapshot_with_source(
                json.dumps(value, separators=(",", ":")).encode("utf-8"),
                source=FakeFleetSource(),
            )

    def test_F14_registry_extra_member(self):
        value = json.loads(registry_payload().decode("utf-8"))
        extra = copy.deepcopy(value["repositories"][0])
        extra["id"] = "DonkeyJJLove/extra-member"
        value["repositories"].append(extra)
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "registry substitution denied"):
            _materialize_live_registry_pin_snapshot_with_source(
                json.dumps(value, separators=(",", ":")).encode("utf-8"),
                source=FakeFleetSource(),
            )

    def test_F15_registry_missing_member(self):
        value = json.loads(registry_payload().decode("utf-8"))
        value["repositories"] = value["repositories"][:-1]
        with self.assertRaisesRegex(GitHubFleetPinSourceError, "registry substitution denied"):
            _materialize_live_registry_pin_snapshot_with_source(
                json.dumps(value, separators=(",", ":")).encode("utf-8"),
                source=FakeFleetSource(),
            )

    def test_F16_manifest_404_promotion(self):
        self.assert_manifest_denied(
            response({"message": "Not Found"}, status=404),
            pin=self.pin(manifest_present=True),
            regex="contradicts pinned presence",
        )

    def test_F17_non_404_as_absence(self):
        self.assert_manifest_denied(
            response({"message": "error"}, status=500),
            pin=self.pin(manifest_present=False),
            regex="HTTP status denied: 500",
        )

    def test_F18_stale_head_acceptance(self):
        target = "DonkeyJJLove/HA2D"

        class StaleObservationSource(FakeFleetSource):
            def _read_manifest_at_pin(self, pin):
                observation, manifest, mapping = super()._read_manifest_at_pin(pin)
                if pin.repository != target or observation.manifest_state != "PRESENT":
                    return observation, manifest, mapping
                stale = RepositoryManifestObservation(
                    repository=observation.repository,
                    default_branch=observation.default_branch,
                    head="f" * 40,
                    tree=observation.tree,
                    manifest_state=observation.manifest_state,
                    manifest_path=observation.manifest_path,
                    git_blob_sha=observation.git_blob_sha,
                    manifest_byte_sha256=observation.manifest_byte_sha256,
                    manifest_semantic_digest=observation.manifest_semantic_digest,
                    source_ref=observation.source_ref,
                ).validate()
                return stale, manifest, mapping

        with self.assertRaisesRegex(GitHubFleetPinSourceError, "identity differs from pin"):
            _materialize_live_registry_manifest_observations_with_source(
                registry_payload(), source=StaleObservationSource()
            )

    def test_F19_tree_only_authority(self):
        names = {item.name for item in fields(RepositoryManifestObservation)}
        self.assertNotIn("runtime_authority", names)
        self.assertNotIn("production_authority", names)
        self.assertNotIn("authority", names)
        self.assertIn("tree", names)

    def test_F20_snapshot_only_authority(self):
        snapshot = _materialize_live_registry_pin_snapshot_with_source(
            registry_payload(), source=FakeFleetSource()
        )
        snapshot_names = {item.name for item in fields(FleetRegistryPinSnapshot)}
        self.assertNotIn("runtime_authority", snapshot_names)
        self.assertNotIn("production_authority", snapshot_names)
        for observation in snapshot.observations:
            self.assertFalse(hasattr(observation, "runtime_authority"))
            self.assertFalse(hasattr(observation, "production_authority"))

    def test_M01_duplicate_json_key(self):
        self.assert_manifest_denied(
            manifest_response(raw=b'{"schema_version":"1.0.0","schema_version":"1.0.0"}'),
            regex="content JSON invalid",
        )

    def test_M02_unknown_root_field(self):
        value = copy.deepcopy(GLITCHLAB)
        value["unexpected"] = True
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M03_unknown_manifest_field(self):
        value = copy.deepcopy(GLITCHLAB)
        value["repository"]["unexpected"] = "value"
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M04_missing_required_field(self):
        value = copy.deepcopy(GLITCHLAB)
        del value["security"]
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M05_wrong_native_string_type(self):
        value = copy.deepcopy(GLITCHLAB)
        value["repository"]["owner"] = ["DonkeyJJLove"]
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M06_bool_as_integer_confusion(self):
        value = copy.deepcopy(GLITCHLAB)
        value["epistemic"]["confidence"] = True
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M07_integer_as_string_coercion(self):
        value = copy.deepcopy(GLITCHLAB)
        value["authority"]["maximum_level"] = 1
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M08_list_as_tuple_coercion(self):
        value = copy.deepcopy(GLITCHLAB)
        value["capabilities"] = tuple(value["capabilities"])
        with self.assertRaisesRegex(EnterpriseModelError, "array of strings"):
            RepositoryManifest.from_mapping(value)

    def test_M09_null_substitution(self):
        value = copy.deepcopy(GLITCHLAB)
        value["repository"]["id"] = None
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M10_trailing_non_json_content(self):
        raw = json.dumps(GLITCHLAB, separators=(",", ":")).encode("utf-8") + b" trailing"
        self.assert_manifest_denied(manifest_response(raw=raw), regex="content JSON invalid")

    def test_M11_invalid_utf8(self):
        self.assert_manifest_denied(manifest_response(raw=b"\xff"), regex="content JSON invalid")

    def test_M12_non_object_root(self):
        self.assert_manifest_denied(manifest_response(raw=b"[]"), regex="content JSON invalid")

    def test_M13_nested_unknown_field(self):
        value = copy.deepcopy(GLITCHLAB)
        value["authority"]["unexpected"] = "write"
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M14_authority_field_injection(self):
        value = copy.deepcopy(GLITCHLAB)
        value["authority"]["runtime_credentials"] = "attacker-token"
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M15_health_field_injection(self):
        value = copy.deepcopy(GLITCHLAB)
        value["health"] = {"status": "green"}
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M16_dependency_field_injection(self):
        value = copy.deepcopy(GLITCHLAB)
        value["dependencies"] = ["DonkeyJJLove/other"]
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M17_repository_id_substitution(self):
        value = copy.deepcopy(GLITCHLAB)
        value["repository"]["id"] = "DonkeyJJLove/other"
        self.assert_manifest_denied(manifest_response(value), regex="repository identity mismatch")

    def test_M18_schema_version_substitution(self):
        value = copy.deepcopy(GLITCHLAB)
        value["schema_version"] = "2.0.0"
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M19_capability_type_substitution(self):
        value = copy.deepcopy(GLITCHLAB)
        value["capabilities"] = ["delta.normalize", 7]
        self.assert_manifest_denied(manifest_response(value), regex="typed validation failed")

    def test_M20_semantic_reseal_after_mutation(self):
        mutations = {
            "repository_id": lambda value: value["repository"].__setitem__("id", "DonkeyJJLove/other"),
            "default_branch": lambda value: value["repository"].__setitem__("default_branch", "main"),
            "schema_version": lambda value: value.__setitem__("schema_version", "2.0.0"),
            "capability_type": lambda value: value.__setitem__("capabilities", ["delta.normalize", 7]),
            "authority_shape": lambda value: value["authority"].__setitem__("runtime_credentials", "attacker"),
            "health_injection": lambda value: value.__setitem__("health", {"status": "green"}),
            "dependency_injection": lambda value: value.__setitem__("dependencies", ["DonkeyJJLove/other"]),
            "manifest_bytes": lambda value: value["cyber_lion"].__setitem__("tile_id", "mutated.tile"),
        }
        baseline = manifest_mapping("DonkeyJJLove/glitchlab", "master")
        baseline_raw = json.dumps(baseline, sort_keys=True, separators=(",", ":")).encode("utf-8")
        baseline_entry = manifest_tree_entry(git_blob_sha(baseline_raw))
        pin = self.pin(tree=git_tree_sha([baseline_entry]))
        for mutation_name, mutate in mutations.items():
            with self.subTest(mutation=mutation_name):
                value = manifest_mapping("DonkeyJJLove/glitchlab", "master")
                mutate(value)
                raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
                sealed = manifest_response(raw=raw, blob_sha=git_blob_sha(raw), size=len(raw))
                mutated_entry = manifest_tree_entry(git_blob_sha(raw))
                collusive_tree = tree_response([mutated_entry], response_sha=pin.tree)
                with self.assertRaises(GitHubFleetPinSourceError):
                    self.read_manifest(
                        sealed,
                        pin=pin,
                        tree_http_response=collusive_tree,
                    )

    def test_T01_tree_response_sha_substitution(self):
        _, content, _, entries, pin = self.valid_manifest_case()
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(entries, response_sha="f" * 40),
            regex="response sha mismatch",
        )

    def test_T02_tree_entry_manifest_blob_sha_substitution(self):
        _, content, _, _, _ = self.valid_manifest_case()
        entries = [manifest_tree_entry("0" * 40)]
        pin = self.pin(tree=git_tree_sha(entries))
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(entries),
            regex="pinned tree blob mismatch",
        )

    def test_T03_tree_entry_manifest_path_substitution(self):
        _, content, blob_sha, _, _ = self.valid_manifest_case()
        entries = [manifest_tree_entry(blob_sha, path="other.repository.json")]
        pin = self.pin(tree=git_tree_sha(entries))
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(entries),
            regex="missing from pinned root tree",
        )

    def test_T04_duplicate_manifest_path_entry(self):
        _, content, blob_sha, _, _ = self.valid_manifest_case()
        entries = [
            manifest_tree_entry(blob_sha),
            manifest_tree_entry("0" * 40),
        ]
        pin = self.pin(tree=git_tree_sha(entries))
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(entries),
            regex="duplicate fleet root tree path denied",
        )

    def test_T05_manifest_entry_type_tree(self):
        _, content, blob_sha, _, _ = self.valid_manifest_case()
        entries = [manifest_tree_entry(blob_sha, mode="040000", entry_type="tree")]
        pin = self.pin(tree=git_tree_sha(entries))
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(entries),
            regex="entry type/mode invalid",
        )

    def test_T06_manifest_entry_type_commit(self):
        _, content, blob_sha, _, _ = self.valid_manifest_case()
        entries = [manifest_tree_entry(blob_sha, mode="160000", entry_type="commit")]
        pin = self.pin(tree=git_tree_sha(entries))
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(entries),
            regex="entry type/mode invalid",
        )

    def test_T07_manifest_entry_missing_when_pin_present(self):
        _, content, _, _, _ = self.valid_manifest_case()
        entries: list[dict] = []
        pin = self.pin(tree=git_tree_sha(entries))
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(entries),
            regex="missing from pinned root tree",
        )

    def test_T08_manifest_entry_present_when_pin_absent(self):
        raw = json.dumps(GLITCHLAB, separators=(",", ":")).encode("utf-8")
        entries = [manifest_tree_entry(git_blob_sha(raw))]
        pin = self.pin(manifest_present=False, tree=git_tree_sha(entries))
        self.assert_manifest_denied(
            response({"message": "Not Found"}, status=404),
            pin=pin,
            tree_http_response=tree_response(entries),
            regex="tree presence contradicts contents absence",
        )

    def test_T09_tree_object_reseal_with_mutated_entry(self):
        _, content, blob_sha, entries, pin = self.valid_manifest_case()
        mutated = [manifest_tree_entry("0" * 40 if blob_sha != "0" * 40 else "1" * 40)]
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(mutated),
            regex="response sha mismatch",
        )
        self.assertNotEqual(git_tree_sha(entries), git_tree_sha(mutated))

    def test_T10_tree_entry_order_substitution(self):
        _, content, blob_sha, _, _ = self.valid_manifest_case()
        extra = {"path": ".github", "mode": "040000", "type": "tree", "sha": "a" * 40}
        entries = [extra, manifest_tree_entry(blob_sha)]
        pin = self.pin(tree=git_tree_sha(entries))
        reordered = list(reversed(entries))
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(reordered, response_sha=pin.tree),
            regex="Git object identity mismatch",
        )

    def test_T11_tree_entry_mode_substitution(self):
        _, content, blob_sha, entries, _ = self.valid_manifest_case()
        pin = self.pin(tree=git_tree_sha(entries))
        mutated = [manifest_tree_entry(blob_sha, mode="100755")]
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(mutated, response_sha=pin.tree),
            regex="Git object identity mismatch",
        )

    def test_T12_tree_response_truncated(self):
        _, content, _, entries, pin = self.valid_manifest_case()
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(entries, response_sha=pin.tree, truncated=True),
            regex="truncated or incomplete",
        )

    def _assert_tree_http_denied(self, status: int) -> None:
        _, content, _, entries, pin = self.valid_manifest_case()
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=tree_response(entries, status=status),
            regex=f"tree HTTP status denied: {status}",
        )

    def test_T13_tree_http_301(self):
        self._assert_tree_http_denied(301)

    def test_T14_tree_http_401(self):
        self._assert_tree_http_denied(401)

    def test_T15_tree_http_403(self):
        self._assert_tree_http_denied(403)

    def test_T16_tree_http_404(self):
        self._assert_tree_http_denied(404)

    def test_T17_tree_http_429(self):
        self._assert_tree_http_denied(429)

    def test_T18_tree_http_500(self):
        self._assert_tree_http_denied(500)

    def test_T19_tree_response_malformed_object(self):
        _, content, _, _, pin = self.valid_manifest_case()
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=response([], status=200),
            regex="root tree response invalid",
        )

    def test_T20_contents_and_tree_collusive_blob_substitution_without_valid_pin_tree_sha(self):
        baseline = copy.deepcopy(GLITCHLAB)
        baseline_raw = json.dumps(baseline, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        baseline_entry = manifest_tree_entry(git_blob_sha(baseline_raw))
        pin = self.pin(tree=git_tree_sha([baseline_entry]))

        mutated = copy.deepcopy(baseline)
        mutated["cyber_lion"]["tile_id"] = "collusive.mutated.tile"
        mutated_raw = json.dumps(mutated, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        mutated_blob_sha = git_blob_sha(mutated_raw)
        content = manifest_response(raw=mutated_raw, blob_sha=mutated_blob_sha)
        collusive_tree = tree_response(
            [manifest_tree_entry(mutated_blob_sha)],
            response_sha=pin.tree,
        )
        self.assert_manifest_denied(
            content,
            pin=pin,
            tree_http_response=collusive_tree,
            regex="Git object identity mismatch",
        )

    def test_tree_reconstruction_golden_ai_platform(self):
        expected = "3c9705f85301e73f268228f3c36f6ae82a641633"
        self.assertEqual(git_tree_sha(AI_PLATFORM_GOLDEN_TREE), expected)
        pin = RepositoryPinObservation(
            repository="DonkeyJJLove/ai_platform",
            default_branch="master",
            head="1" * 40,
            tree=expected,
            manifest_present=True,
            source_ref="golden-ai-platform",
        ).validate()
        source = GitHubFleetRegistryPinReadSource(
            token="matrix-token",
            transport=FakeTransport([tree_response(AI_PLATFORM_GOLDEN_TREE, response_sha=expected)]),
        )
        entries = source._read_root_tree_at_pin(pin)
        self.assertEqual(len(entries), len(AI_PLATFORM_GOLDEN_TREE))

        body = b""
        for entry in AI_PLATFORM_GOLDEN_TREE:
            body += (
                entry["mode"].encode("ascii")
                + b" "
                + entry["path"].encode("utf-8")
                + b"\0"
                + bytes.fromhex(entry["sha"])
            )
        wrong = sha1(b"tree " + str(len(body)).encode("ascii") + b"\0" + body).hexdigest()
        self.assertEqual(wrong, "c4e0bf8774b3e24915197c95a16129dd5bd7dac7")
        self.assertNotEqual(wrong, expected)
        print("TREE_MODE_040000_TO_40000_NORMALIZATION=PASS")
        print("TREE_OBJECT_SHA_RECONSTRUCTION=PASS")

    def test_tree_reconstruction_golden_sbom_unicode(self):
        expected = "8d7cc0e5b5025899d0889c4a5c17ac230681c4fb"
        self.assertIn("środowiska-testowe", {entry["path"] for entry in SBOM_GOLDEN_TREE})
        self.assertEqual(git_tree_sha(SBOM_GOLDEN_TREE), expected)
        pin = RepositoryPinObservation(
            repository="DonkeyJJLove/sbom",
            default_branch="main",
            head="1" * 40,
            tree=expected,
            manifest_present=True,
            source_ref="golden-sbom",
        ).validate()
        source = GitHubFleetRegistryPinReadSource(
            token="matrix-token",
            transport=FakeTransport([tree_response(SBOM_GOLDEN_TREE, response_sha=expected)]),
        )
        entries = source._read_root_tree_at_pin(pin)
        self.assertEqual(len(entries), len(SBOM_GOLDEN_TREE))

    def test_matrix_identity_is_exact_and_complete(self):
        self.assertEqual(len(F_ATTACKS), 20)
        self.assertEqual(len(M_ATTACKS), 20)
        self.assertEqual(len(T_ATTACKS), 20)
        self.assertEqual(len(set(F_ATTACKS)), 20)
        self.assertEqual(len(set(M_ATTACKS)), 20)
        self.assertEqual(len(set(T_ATTACKS)), 20)
        names = {
            name
            for name in dir(type(self))
            if name.startswith("test_F") or name.startswith("test_M") or name.startswith("test_T")
        }
        expected = {
            "test_" + attack.split("_", 1)[0] + "_" + attack.split("_", 1)[1].lower()
            for attack in F_ATTACKS + M_ATTACKS + T_ATTACKS
        }
        self.assertTrue(expected.issubset(names))


if __name__ == "__main__":
    unittest.main()