from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.bounded_task_profile import (
    BoundedTaskProfile,
    BoundedTaskProfileError,
    TASK_CLASSES,
    catalog_payload,
    default_catalog,
    load_catalog,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "cyber_lion/contracts/bounded_task_profiles.json"


class BoundedTaskProfileTests(unittest.TestCase):
    def test_default_catalog_is_complete_unique_and_non_effectful(self):
        profiles = default_catalog()
        self.assertEqual(tuple(p.task_class for p in profiles), TASK_CLASSES)
        self.assertEqual(len({p.profile_id for p in profiles}), len(TASK_CLASSES))
        self.assertEqual(len({p.profile_digest for p in profiles}), len(TASK_CLASSES))
        for profile in profiles:
            self.assertEqual(
                (profile.authority_effect, profile.execution_effect, profile.external_effect),
                ("NONE", "NONE", "NONE"),
            )
            self.assertGreater(profile.max_context_bytes, 0)
            self.assertGreater(profile.max_files, 0)
            self.assertGreater(profile.max_input_tokens, 0)
            self.assertGreater(profile.max_output_tokens, 0)

    def test_stored_catalog_exactly_matches_generated_catalog(self):
        raw = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(raw, catalog_payload())
        loaded = load_catalog(CATALOG)
        self.assertEqual(tuple(p.to_dict() for p in loaded), tuple(p.to_dict() for p in default_catalog()))

    def test_profile_reference_does_not_carry_authority_or_effect(self):
        profile = default_catalog()[0]
        self.assertTrue(profile.tool_profile_ref)
        self.assertTrue(profile.resource_profile_ref)
        self.assertTrue(profile.workspace_profile_ref)
        with self.assertRaisesRegex(BoundedTaskProfileError, "authority or effect"):
            replace(profile, authority_effect="ALLOW", profile_digest="").sealed()
        with self.assertRaisesRegex(BoundedTaskProfileError, "authority or effect"):
            replace(profile, execution_effect="EXECUTE", profile_digest="").sealed()

    def test_limits_are_finite_and_bool_is_not_integer(self):
        profile = default_catalog()[0]
        for field, value in (
            ("max_files", 0),
            ("max_context_bytes", 16 * 1024 * 1024 + 1),
            ("max_input_tokens", True),
            ("max_output_tokens", 65_537),
            ("timeout_seconds", 3_601),
            ("retry_budget", 9),
        ):
            with self.subTest(field=field):
                with self.assertRaises(BoundedTaskProfileError):
                    replace(profile, **{field: value, "profile_digest": ""}).sealed()

    def test_unknown_task_class_and_unknown_field_fail_closed(self):
        profile = default_catalog()[0]
        with self.assertRaisesRegex(BoundedTaskProfileError, "task_class"):
            replace(profile, task_class="DO_ANYTHING", profile_digest="").sealed()
        value = profile.to_dict()
        value["grant_tools"] = True
        with self.assertRaisesRegex(BoundedTaskProfileError, "fields"):
            BoundedTaskProfile.from_mapping(value)

    def test_tampered_profile_and_catalog_digest_are_rejected(self):
        profile = default_catalog()[0]
        tampered = profile.to_dict()
        tampered["timeout_seconds"] += 1
        with self.assertRaisesRegex(BoundedTaskProfileError, "digest mismatch"):
            BoundedTaskProfile.from_mapping(tampered)

        raw = json.loads(CATALOG.read_text(encoding="utf-8"))
        raw["profiles"][0]["max_files"] += 1
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "catalog.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(BoundedTaskProfileError, "catalog digest"):
                load_catalog(path)

    def test_catalog_requires_exact_task_class_coverage(self):
        profiles = list(default_catalog())
        with self.assertRaisesRegex(BoundedTaskProfileError, "duplication"):
            catalog_payload(profiles + [profiles[0]])
        incomplete = profiles[:-1]
        payload = catalog_payload(incomplete)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "catalog.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(BoundedTaskProfileError, "coverage"):
                load_catalog(path)


if __name__ == "__main__":
    unittest.main()
