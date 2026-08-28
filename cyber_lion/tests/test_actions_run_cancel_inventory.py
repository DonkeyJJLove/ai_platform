import inspect
import unittest

import cyber_lion.enterprise.actions_run_cancel_github_effect as effect_module
import cyber_lion.enterprise.actions_run_cancel_runtime as runtime_module
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner


class ActionsRunCancelInventoryTests(unittest.TestCase):
    def test_single_raw_cancel_endpoint_owner_is_canonical_runtime(self):
        effect_source = inspect.getsource(effect_module)
        runtime_source = inspect.getsource(runtime_module)
        combined = effect_source + "\n" + runtime_source
        self.assertEqual(combined.count("/actions/runs/"), 1)
        self.assertEqual(combined.count("/cancel"), 1)
        self.assertEqual(combined.count('method="POST"'), 1)
        self.assertEqual(effect_source.count('method="POST"'), 0)
        self.assertEqual(runtime_source.count('method="POST"'), 1)
        self.assertNotIn('method="PUT"', combined)
        self.assertNotIn('method="PATCH"', combined)
        self.assertNotIn('method="DELETE"', combined)

    def test_scanner_keeps_exactly_one_raw_cancel_post_visible(self):
        runtime_path = "cyber_lion/enterprise/actions_run_cancel_runtime.py"
        sources = {
            "cyber_lion/enterprise/actions_run_cancel_github_effect.py": inspect.getsource(
                effect_module
            ),
            runtime_path: inspect.getsource(runtime_module),
        }
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources=sources,
        )
        posts = [
            surface
            for surface in inventory.surfaces
            if surface.effect_class == "external.network.post"
        ]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].implementation_refs, (runtime_path,))
        self.assertEqual(posts[0].mutation_kind, "urllib.request.Request")
        self.assertEqual(posts[0].target_class, "external")
        self.assertEqual(posts[0].authority_class, "external_write")
        self.assertEqual(sources[runtime_path].count("/cancel"), 1)

    def test_historical_effect_module_has_no_network_transport(self):
        source = inspect.getsource(effect_module)
        self.assertNotIn("urllib.request.Request", source)
        self.assertNotIn("build_opener", source)
        self.assertIn("direct actions-run-cancel effect provider disabled", source)


if __name__ == "__main__":
    unittest.main()
