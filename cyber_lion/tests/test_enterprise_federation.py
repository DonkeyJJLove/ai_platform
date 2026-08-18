from __future__ import annotations

import unittest

from cyber_lion.enterprise import EnterpriseModelError, RepositoryFederationRegistry


GLITCHLAB = {
    "schema_version": "1.0.0",
    "repository": {
        "id": "DonkeyJJLove/glitchlab",
        "url": "https://github.com/DonkeyJJLove/glitchlab",
        "owner": "DonkeyJJLove",
        "default_branch": "master",
        "vcs_ref": None,
    },
    "cyber_lion": {
        "tile_id": "evolution-compiler.glitchlab",
        "roles": ["EvolutionCompiler"],
        "layers": ["SEM", "MAND"],
        "disposition": ["KEEP", "INTEGRATE"],
    },
    "capabilities": ["delta.normalize", "invariant.evaluate"],
    "authority": {
        "maximum_level": "local_write",
        "required_gates": ["glitchlab.invariants", "cyber-lion.mand"],
    },
    "observability": {
        "logs": ["delta.analysis"],
        "metrics": ["invariant.failures"],
        "traces": ["source→delta→decision"],
    },
    "security": {"trust_boundaries": ["proposal != authority"]},
    "epistemic": {"status": "ENGINEERING_CANDIDATE", "confidence": 0.86},
}

SBOM = {
    "schema_version": "1.0.0",
    "repository": {
        "id": "DonkeyJJLove/sbom",
        "url": "https://github.com/DonkeyJJLove/sbom",
        "owner": "DonkeyJJLove",
        "default_branch": "main",
        "vcs_ref": None,
    },
    "cyber_lion": {
        "tile_id": "provenance.sbom",
        "roles": ["SupplyChainEvidenceProvider"],
        "layers": ["INF", "SEM"],
        "disposition": ["KEEP", "INTEGRATE"],
    },
    "capabilities": ["artifact.identify", "provenance.emit"],
    "authority": {"maximum_level": "read", "required_gates": []},
    "observability": {
        "logs": ["sbom.event"],
        "metrics": ["provenance.coverage"],
        "traces": ["source→AID→evidence"],
    },
    "security": {"trust_boundaries": ["measurement != authority"]},
    "epistemic": {"status": "OBSERVED", "confidence": 0.9},
}


class RepositoryFederationTests(unittest.TestCase):
    def test_register_and_discover_capability(self):
        registry = RepositoryFederationRegistry()
        registry.register_mapping(GLITCHLAB)
        registry.register_mapping(SBOM)
        providers = registry.discover_capability("provenance.emit")
        self.assertEqual([p.repository_id for p in providers], ["DonkeyJJLove/sbom"])
        self.assertEqual([p.repository_id for p in registry.discover_layer("MAND")], ["DonkeyJJLove/glitchlab"])

    def test_registration_does_not_infer_or_expand_authority(self):
        manifest = RepositoryFederationRegistry().register_mapping(SBOM)
        self.assertEqual(manifest.maximum_authority, "read")
        self.assertEqual(manifest.required_gates, ())

    def test_consequential_repository_requires_gate(self):
        broken = {**GLITCHLAB, "authority": {"maximum_level": "external_write", "required_gates": []}}
        with self.assertRaises(EnterpriseModelError):
            RepositoryFederationRegistry().register_mapping(broken)

    def test_duplicate_tile_id_fails_closed(self):
        registry = RepositoryFederationRegistry()
        registry.register_mapping(GLITCHLAB)
        collision = {
            **SBOM,
            "cyber_lion": {**SBOM["cyber_lion"], "tile_id": "evolution-compiler.glitchlab"},
        }
        with self.assertRaises(EnterpriseModelError):
            registry.register_mapping(collision)

    def test_manifest_change_under_same_repository_id_requires_new_identity_or_update_protocol(self):
        registry = RepositoryFederationRegistry()
        registry.register_mapping(SBOM)
        changed = {**SBOM, "capabilities": ["artifact.identify", "provenance.emit", "artifact.delta"]}
        with self.assertRaises(EnterpriseModelError):
            registry.register_mapping(changed)

    def test_invalid_epistemic_confidence_is_rejected(self):
        broken = {**SBOM, "epistemic": {"status": "OBSERVED", "confidence": 1.5}}
        with self.assertRaises(EnterpriseModelError):
            RepositoryFederationRegistry().register_mapping(broken)


if __name__ == "__main__":
    unittest.main()
