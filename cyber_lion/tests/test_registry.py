import unittest
from cyber_lion.registry import CapabilityDescriptor,CapabilityRegistry,CapabilityValidationError

class RegistryTests(unittest.TestCase):
    def test_read_only_can_be_gate_free(self):
        CapabilityDescriptor("structure.ast_graph.v1","repo:glitchlab","1.0.0",side_effects=("none",),required_authority="read",epistemic_status="FORMALISED").validate()
    def test_consequential_requires_authority_and_gate(self):
        with self.assertRaises(CapabilityValidationError): CapabilityDescriptor("execution.tool.v1","repo:swarm","1.0.0",side_effects=("execute",),required_authority="none").validate()
        with self.assertRaises(CapabilityValidationError): CapabilityDescriptor("execution.tool.v1","repo:swarm","1.0.0",side_effects=("execute",),required_authority="execute").validate()
    def test_same_id_cannot_silently_change(self):
        r=CapabilityRegistry(); r.register(CapabilityDescriptor("simulation.scenario.v1","repo:cascade","1.0.0"))
        with self.assertRaises(CapabilityValidationError): r.register(CapabilityDescriptor("simulation.scenario.v1","repo:other","1.0.0"))
    def test_provider_discovery(self):
        r=CapabilityRegistry(); r.register(CapabilityDescriptor("analysis.delta.v1","repo:glitchlab","1.0.0"))
        self.assertEqual([x.capability_id for x in r.discover("repo:glitchlab")],["analysis.delta.v1"])

if __name__=="__main__": unittest.main()
