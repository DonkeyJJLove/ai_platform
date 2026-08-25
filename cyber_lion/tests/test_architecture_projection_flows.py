import unittest

from cyber_lion.architecture_projection.flows import ARCHITECTURE_LAYERS, FLOW_SPECS, ArchitectureFlow, canonical_flows


class ArchitectureProjectionFlowTests(unittest.TestCase):
    def test_all_15_layers_are_declared(self):
        self.assertEqual(len(ARCHITECTURE_LAYERS), 15)
        self.assertEqual(len(set(ARCHITECTURE_LAYERS)), 15)

    def test_all_9_named_flows_resolve(self):
        flows = canonical_flows()
        self.assertEqual(len(flows), 9)
        self.assertEqual({flow.flow_id for flow in flows}, set(FLOW_SPECS))

    def test_flow_order_is_exact_and_closed(self):
        flow = canonical_flows()[0]
        self.assertEqual(flow.steps, FLOW_SPECS[flow.flow_id])
        with self.assertRaises(ValueError):
            ArchitectureFlow(flow.flow_id, tuple(reversed(flow.steps))).validate()


if __name__ == "__main__":
    unittest.main()
