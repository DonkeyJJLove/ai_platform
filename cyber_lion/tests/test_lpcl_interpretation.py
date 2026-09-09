from __future__ import annotations

import unittest

from cyber_lion.process_language.canonical_run_examples import canonical_run_example
from cyber_lion.process_language.interpretation import (
    ProcessSourceInterpretationError,
    interpret_process_source,
)
from cyber_lion.process_language.lpcl import render_lpcl
from cyber_lion.process_language.reference_processes import reference_process


class LPCLInterpretationTests(unittest.TestCase):
    def test_strict_v1_remains_process_ir_compatibility_surface(self):
        source = render_lpcl(reference_process("read-only-live-reacquisition"))
        interpreted = interpret_process_source(source)
        self.assertEqual(interpreted.surface_class, "LPCL_1_0_STRICT")
        self.assertTrue(interpreted.process_candidate)
        self.assertIsNotNone(interpreted.process_ir)
        self.assertIsNone(interpreted.fleet_mission_ir)
        self.assertEqual(interpreted.authority_effect, "NONE")

    def test_canonical_v11_run_requires_fleet_mission_ir(self):
        for scenario in ("logical", "local", "hybrid"):
            with self.subTest(scenario=scenario):
                interpreted = interpret_process_source(canonical_run_example(scenario))
                self.assertEqual(interpreted.surface_class, "LPCL_1_1_CANONICAL_RUN")
                self.assertTrue(interpreted.process_candidate)
                self.assertIsNotNone(interpreted.process_ir)
                self.assertIsNotNone(interpreted.fleet_mission_ir)
                self.assertEqual(interpreted.authority_effect, "NONE")
                self.assertEqual(interpreted.runtime_effect, "NONE")
                self.assertEqual(interpreted.execution_effect, "NONE")

    def test_unversioned_run_stays_legacy_data(self):
        interpreted = interpret_process_source(
            "RUN=OLD-R1\n--repository=DonkeyJJLove/ai_platform\n"
        )
        self.assertEqual(interpreted.surface_class, "LEGACY_RUN_DATA")
        self.assertFalse(interpreted.process_candidate)
        self.assertIsNone(interpreted.process_ir)
        self.assertIsNone(interpreted.fleet_mission_ir)

    def test_numbered_unversioned_phase_does_not_become_v11(self):
        interpreted = interpret_process_source(
            "RUN=OLD-R2\nPHASE_0=READ\n--repository=DonkeyJJLove/ai_platform\n"
        )
        self.assertEqual(interpreted.surface_class, "LEGACY_RUN_DATA")
        self.assertEqual(interpreted.legacy.classification, "AMBIGUOUS")
        self.assertFalse(interpreted.process_candidate)

    def test_invalid_explicit_v11_fails_closed_not_legacy_fallback(self):
        source = "RUN=BAD-R1\nLPCL_VERSION=\n1.1\nEND\n"
        with self.assertRaises(ProcessSourceInterpretationError):
            interpret_process_source(source)


if __name__ == "__main__":
    unittest.main()
