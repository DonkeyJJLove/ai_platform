from __future__ import annotations

import unittest

from cyber_lion.process_language.legacy_run import LegacyRunAdapter, LegacyRunError
from cyber_lion.process_language.lpcl import LPCLParseError, parse_lpcl, render_lpcl
from cyber_lion.process_language.reference_processes import reference_process


class LPCLTests(unittest.TestCase):
    def test_round_trip_preserves_canonical_process_ir(self):
        ir=reference_process("candidate-preparation"); self.assertEqual(parse_lpcl(render_lpcl(ir)),ir)

    def test_unknown_and_duplicate_statements_fail_closed(self):
        text=render_lpcl(reference_process("scientific-experiment"))
        with self.assertRaisesRegex(LPCLParseError,"unknown"): parse_lpcl(text.replace("END\n","RAW_SHELL \"x\"\nEND\n"))
        lines=text.splitlines(); duplicate="\n".join(lines[:2]+[lines[1]]+lines[2:])+"\n"
        with self.assertRaisesRegex(LPCLParseError,"duplicate LPCL statement"): parse_lpcl(duplicate)

    def test_historical_run_is_data_not_execution(self):
        adapter=LegacyRunAdapter(); result=adapter.parse("RUN=TEST-R1\n--repository=owner/repo\n"); self.assertEqual(result.run_id,"TEST-R1"); self.assertEqual(result.classification,"LOSSY_BUT_SAFE"); candidate=adapter.semantic_candidate("RUN=TEST-R1\n--repository=owner/repo\n"); self.assertEqual(candidate["authority_effect"],"NONE"); self.assertEqual(candidate["execution_effect"],"NONE")

    def test_then_encoded_mode_is_ambiguous_and_not_promotable(self):
        source="RUN=TEST-R2\n--mode=READ_THEN_WRITE_THEN_MERGE\n"; result=LegacyRunAdapter().parse(source); self.assertEqual(result.classification,"AMBIGUOUS")
        with self.assertRaisesRegex(LegacyRunError,"cannot be promoted"): LegacyRunAdapter().semantic_candidate(source)

    def test_missing_run_is_unrepresentable(self):
        self.assertEqual(LegacyRunAdapter().parse("--mode=READ_ONLY\n").classification,"UNREPRESENTABLE")


if __name__=="__main__": unittest.main()
