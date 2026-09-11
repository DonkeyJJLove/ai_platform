from __future__ import annotations

import json
from pathlib import Path
import unittest

from cyber_lion.process_language.canonical_run_examples import canonical_run_example
from cyber_lion.process_language.interpretation import (
    ProcessSourceInterpretationError,
    interpret_process_source,
)


_CORPUS = Path(__file__).parents[1] / "process_language" / "canonical_run_negative_corpus.json"


class LPCLCanonicalRunNegativeCorpusTests(unittest.TestCase):
    def test_corpus(self):
        entries = json.loads(_CORPUS.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(entries), 12)
        seen = set()
        for case in entries:
            with self.subTest(case=case["id"]):
                self.assertNotIn(case["id"], seen)
                seen.add(case["id"])
                source = canonical_run_example(case["scenario"])
                for old, new in case["replacements"]:
                    self.assertIn(old, source)
                    source = source.replace(old, new, 1)
                if case["expected"] == "DATA_ONLY":
                    interpreted = interpret_process_source(source)
                    self.assertFalse(interpreted.process_candidate)
                    self.assertIn(interpreted.surface_class, {"LEGACY_RUN_DATA", "UNREPRESENTABLE"})
                    continue
                self.assertEqual(case["expected"], "ERROR")
                with self.assertRaises(ProcessSourceInterpretationError) as caught:
                    interpret_process_source(source)
                self.assertIn(case["error_contains"], str(caught.exception))


if __name__ == "__main__":
    unittest.main()
