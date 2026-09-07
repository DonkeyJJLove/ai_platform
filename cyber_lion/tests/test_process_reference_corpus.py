from __future__ import annotations

import unittest

from cyber_lion.process_language.lpcl import parse_lpcl, render_lpcl
from cyber_lion.process_language.reference_processes import SCENARIOS, all_reference_processes


class ProcessReferenceCorpusTests(unittest.TestCase):
    def test_all_required_scenarios_share_one_canonical_kernel(self):
        self.assertEqual(len(SCENARIOS),12); processes=all_reference_processes(); self.assertEqual(len({item.process_digest for item in processes}),12)
        for item in processes: self.assertEqual(parse_lpcl(render_lpcl(item)),item)


if __name__=="__main__": unittest.main()
