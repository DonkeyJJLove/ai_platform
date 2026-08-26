from pathlib import Path
import unittest


class R2QF005WriteBypassGuards(unittest.TestCase):
    def test_effect_capable_f005_workflows_are_not_reachable_from_current_tree(self):
        for name in (
            'f005-branch-ref-cleanup.yml',
            'f005-runtime-fleet-convergence.yml',
        ):
            self.assertFalse(Path('.github/workflows', name).exists(), name)


if __name__ == '__main__':
    unittest.main()
