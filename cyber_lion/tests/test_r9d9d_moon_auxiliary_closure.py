from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cyber_lion.enterprise.complete_mediation import CompleteMediationEngine, EffectSurfaceScanner
from cyber_lion.enterprise.moon_file_write_mediation import DurableMoonFileWriteFence, MoonFileWriteMediationError


class R9D9DMoonAuxiliaryClosureTests(unittest.TestCase):
    def test_missing_fence_parent_is_denied(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing" / "fence.sqlite3"
            with self.assertRaises(MoonFileWriteMediationError):
                DurableMoonFileWriteFence(str(missing))

    def test_existing_exact_parent_is_allowed_without_parent_creation(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "fence.sqlite3"
            fence = DurableMoonFileWriteFence(str(db))
            self.assertTrue(db.exists())
            self.assertEqual(Path(fence._path), db)

    def test_fence_constructor_contains_no_mkdir(self):
        source = Path("cyber_lion/enterprise/moon_file_write_mediation.py").read_text(encoding="utf-8")
        start = source.index("class DurableMoonFileWriteFence:")
        end = source.index("    def _connect", start)
        self.assertNotIn("mkdir(", source[start:end])
        self.assertIn("fence parent must already exist", source[start:end])
        self.assertIn("production fence parent must be exact bounded base", source[start:end])

    def test_authority_currentness_uses_observation_digest_not_synthetic_zero_epoch(self):
        source = Path("cyber_lion/enterprise/moon_file_write.py").read_text(encoding="utf-8")
        self.assertIn('provider_id: str = "github-collaborator-permission-pdp-v2"', source)
        self.assertIn('"control_issue": request.control_issue', source)
        self.assertIn('"source_event_digest": request.source_event_digest', source)
        self.assertIn("authority_epoch=None", source)
        self.assertNotIn("authority_epoch=0", source)

    def test_scanner_exposes_moon_runner_temp_bootstrap_writes(self):
        workflow = Path(".github/workflows/moon-file-write.yml").read_text(encoding="utf-8")
        inv = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources={".github/workflows/moon-file-write.yml": workflow},
        )
        classes = {s.effect_class for s in inv.surfaces}
        self.assertIn("filesystem.bootstrap.mkdir", classes)
        self.assertIn("filesystem.bootstrap.write", classes)

    def test_scanner_exposes_fence_persistent_state_and_authority_observation(self):
        mediation = Path("cyber_lion/enterprise/moon_file_write_mediation.py").read_text(encoding="utf-8")
        entry = Path("cyber_lion/enterprise/moon_file_write.py").read_text(encoding="utf-8")
        inv = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources={
                "cyber_lion/enterprise/moon_file_write_mediation.py": mediation,
                "cyber_lion/enterprise/moon_file_write.py": entry,
            },
        )
        classes = {s.effect_class for s in inv.surfaces}
        self.assertIn("persistent_state.write", classes)
        self.assertIn("external.network.authority_observation", classes)

    def test_global_assessment_remains_unknown_without_exact_bindings(self):
        workflow = Path(".github/workflows/moon-file-write.yml").read_text(encoding="utf-8")
        mediation = Path("cyber_lion/enterprise/moon_file_write_mediation.py").read_text(encoding="utf-8")
        inv = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources={
                ".github/workflows/moon-file-write.yml": workflow,
                "cyber_lion/enterprise/moon_file_write_mediation.py": mediation,
            },
        )
        assessment = CompleteMediationEngine().assess(
            inventory=inv,
            bindings=(),
            falsification_evidence_refs=("R9D-9D",),
            observation_evidence_refs=("R9D-9B2",),
        )
        self.assertEqual(assessment.global_status, "UNKNOWN")

    def test_workflow_bootstrap_never_materializes_under_home_d2j3(self):
        source = Path(".github/workflows/moon-file-write.yml").read_text(encoding="utf-8")
        for forbidden in ("> /home/d2j3", ">>/home/d2j3", "tee /home/d2j3", "cp /home/d2j3", "mv /home/d2j3"):
            self.assertNotIn(forbidden, source)
        self.assertIn('Path(os.environ["RUNNER_TEMP"]) / "moon-mediated-runtime"', source)

    def test_replace_remains_not_live_certified_by_this_phase(self):
        source = Path("cyber_lion/enterprise/moon_file_write.py").read_text(encoding="utf-8")
        self.assertIn('request.operation_mode == "CREATE_ONLY"', source)
        self.assertIn("REPLACE target drift before commit", source)
        # R9D-9D intentionally does not manufacture live evidence for REPLACE_EXPECTED_DIGEST.
        self.assertNotIn("R9D-9D REPLACE LIVE CANARY", source)


if __name__ == "__main__":
    unittest.main()
