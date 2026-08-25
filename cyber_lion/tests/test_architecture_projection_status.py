import unittest

from cyber_lion.architecture_projection.status import ArchitectureStatus, IMPLEMENTATION_STATUSES, require_closed_status


class ArchitectureProjectionStatusTests(unittest.TestCase):
    def test_status_vocabulary_is_closed(self):
        self.assertEqual(len(IMPLEMENTATION_STATUSES), 8)
        for value in IMPLEMENTATION_STATUSES:
            self.assertEqual(require_closed_status(value), value)
        with self.assertRaises(ValueError):
            require_closed_status("OBSERVED_BUT_MAYBE")

    def test_target_only_cannot_claim_source_implementation(self):
        with self.assertRaises(ValueError):
            ArchitectureStatus("TARGET_ONLY", "LIVE_CODE", "bad", source_digest="a" * 64).validate()

    def test_unknown_cannot_be_promoted_by_documentation(self):
        with self.assertRaises(ValueError):
            ArchitectureStatus("UNKNOWN", "CANONICAL_DOCUMENTATION", "unsupported promotion").validate()

    def test_quarantined_requires_observed_state(self):
        ArchitectureStatus("QUARANTINED", "EXACT_GIT_STATE", "observed quarantine", source_digest="a" * 64).validate()


if __name__ == "__main__":
    unittest.main()
