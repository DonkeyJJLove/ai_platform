import unittest

from cyber_lion.registry import (
    CapabilityDescriptor,
    CapabilityRegistry,
    CapabilityValidationError,
)


class CapabilityRegistryTests(unittest.TestCase):
    def test_read_only_capability_can_be_gate_free(self):
        descriptor = CapabilityDescriptor(
            capability_id="structure.ast_graph.v1",
            provider_entity="repo:glitchlab",
            version="1.0.0",
            side_effects=("none",),
            required_authority="read",
            epistemic_status="FORMALISED",
        )
        descriptor.validate()

    def test_consequential_capability_requires_authority_and_gate(self):
        with self.assertRaises(CapabilityValidationError):
            CapabilityDescriptor(
                capability_id="execution.tool.v1",
                provider_entity="repo:swarm",
                version="1.0.0",
                side_effects=("execute",),
                required_authority="none",
            ).validate()

        with self.assertRaises(CapabilityValidationError):
            CapabilityDescriptor(
                capability_id="execution.tool.v1",
                provider_entity="repo:swarm",
                version="1.0.0",
                side_effects=("execute",),
                required_authority="execute",
                required_gates=(),
            ).validate()

    def test_registered_capability_cannot_silently_change(self):
        registry = CapabilityRegistry()
        first = CapabilityDescriptor(
            capability_id="simulation.scenario.v1",
            provider_entity="repo:cascade",
            version="1.0.0",
            side_effects=("none",),
            required_authority="read",
        )
        registry.register(first)
        with self.assertRaises(CapabilityValidationError):
            registry.register(
                CapabilityDescriptor(
                    capability_id="simulation.scenario.v1",
                    provider_entity="repo:other",
                    version="1.0.0",
                    side_effects=("none",),
                    required_authority="read",
                )
            )

    def test_provider_discovery_is_explicit(self):
        registry = CapabilityRegistry()
        registry.register(
            CapabilityDescriptor(
                capability_id="analysis.delta.v1",
                provider_entity="repo:glitchlab",
                version="1.0.0",
            )
        )
        self.assertEqual(
            [item.capability_id for item in registry.discover(provider_entity="repo:glitchlab")],
            ["analysis.delta.v1"],
        )


if __name__ == "__main__":
    unittest.main()
