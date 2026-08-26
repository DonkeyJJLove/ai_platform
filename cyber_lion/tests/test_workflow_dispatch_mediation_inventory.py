from __future__ import annotations

from pathlib import Path
import unittest

import cyber_lion.enterprise.actions_dispatch_bridge as bridge


class WorkflowDispatchInventoryTests(unittest.TestCase):
    def test_production_entrypoint_has_no_raw_dispatch_post(self):
        source = Path(bridge.__file__).read_text(encoding="utf-8")
        self.assertNotIn('method="POST"', source)
        self.assertIn("dispatch_mediated", source)
        self.assertIn("direct workflow dispatch disabled", source)

    def test_legacy_raw_effect_is_not_the_production_entrypoint(self):
        self.assertNotEqual(bridge.__file__, bridge._legacy.__file__)
        self.assertTrue(callable(bridge.GitHubApi.dispatch_mediated))


if __name__ == "__main__": unittest.main()
