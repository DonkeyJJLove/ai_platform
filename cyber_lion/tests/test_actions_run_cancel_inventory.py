import inspect
import unittest

import cyber_lion.enterprise.actions_run_cancel_github_effect as effect_module


class ActionsRunCancelInventoryTests(unittest.TestCase):
    def test_single_raw_cancel_endpoint_owner(self):
        source = inspect.getsource(effect_module)
        self.assertEqual(source.count('/actions/runs/{request.run_id}/cancel'), 1)
        self.assertEqual(source.count('method="POST"'), 1)
        self.assertIn('class ExactActionsRunCancelEffectProvider', source)
        self.assertNotIn('method="PUT"', source)
        self.assertNotIn('method="PATCH"', source)
        self.assertNotIn('method="DELETE"', source)

    def test_no_caller_supplied_url_or_method(self):
        source = inspect.getsource(effect_module.ExactActionsRunCancelEffectProvider.cancel_exact)
        self.assertNotIn('request.url', source)
        self.assertNotIn('request.method', source)
        self.assertIn('API_ORIGIN', inspect.getsource(effect_module.ExactActionsRunCancelEffectProvider))


if __name__ == "__main__":
    unittest.main()
