from __future__ import annotations

import copy
from dataclasses import fields
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
    MANIFEST_PATH,
    git_blob_sha,
    manifest_mapping,
    manifest_response,
    registry_payload,
    response,
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

F_IDENTITY_PROVENANCE = "R2E4_SPECTRA_IMPLEMENTATION_FALSIFICATION_R1_USER_LITERAL"


class ExactManifestAttackMatrixTests(unittest.TestCase):
    def pin(self, *, manifest_present: bool = True) -> RepositoryPinObservation:
        return RepositoryPinObservation(
            repository="DonkeyJJLove/glitchlab",
            default_branch="master",
            head="1" * 40,
            tree="2" * 40,
            manifest_present=manifest_present,
            source_ref="matrix-pin",
        ).validate()

    def read_manifest(self, http_response, *, pin: RepositoryPinObservation | None = None):
        source = GitHubFleetRegistryPinReadSource(
            token="matrix-token",
            transport=FakeTransport([http_response]),
        )
        return source._read_manifest_at_pin(pin or self.pin())

    def assert_manifest_denied(
        self,
        http_response,
        *,
        pin: RepositoryPinObservation | None = None,
        regex: str | None = None,
    ) -> None:
        context = (
            self.assertRaisesRegex(GitHubFleetPinSourceError, regex)
            if regex is not None
            else self.assertRaises(GitHubFleetPinSourceError)
        )
        with context:
            self.read_manifest(http_response, pin=pin)

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
        value = manifest_mapping("DonkeyJJLove/glitchlab", "master")
        value["repository"]["id"] = "DonkeyJJLove/other"
        raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sealed = manifest_response(
            raw=raw,
            blob_sha=git_blob_sha(raw),
            size=len(raw),
        )
        self.assert_manifest_denied(sealed, regex="repository identity mismatch")

    def test_matrix_identity_is_exact_and_complete(self):
        self.assertEqual(len(F_ATTACKS), 20)
        self.assertEqual(len(M_ATTACKS), 20)
        self.assertEqual(len(set(F_ATTACKS)), 20)
        self.assertEqual(len(set(M_ATTACKS)), 20)
        names = {name for name in dir(type(self)) if name.startswith("test_F") or name.startswith("test_M")}
        expected = {
            "test_" + attack.split("_", 1)[0] + "_" + attack.split("_", 1)[1].lower()
            for attack in F_ATTACKS + M_ATTACKS
        }
        self.assertTrue(expected.issubset(names))


if __name__ == "__main__":
    unittest.main()
