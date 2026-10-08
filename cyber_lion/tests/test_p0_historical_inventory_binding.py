"""Fail-closed source identity checks for the historical P0 test epoch."""
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from cyber_lion.tests import p0_historical_inventory as historical


class P0HistoricalInventoryBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]

    def test_pinned_history_is_exact_and_not_current_checkout(self):
        inventory, taxonomy = historical.pinned_p0_inventory(self.root)
        self.assertEqual(inventory.revision, historical.HISTORICAL_HEAD)
        self.assertEqual(inventory.tree_digest, historical.HISTORICAL_TREE)
        self.assertEqual(inventory.scan_digest, historical.HISTORICAL_SCAN_DIGEST)
        self.assertFalse(inventory.unclassified_refs)
        self.assertFalse(taxonomy.unresolved_refs)

    def test_historical_commit_object_type_substitution_is_rejected(self):
        with patch.object(historical, "_git", return_value=b"blob\n"):
            with self.assertRaisesRegex(
                historical.HistoricalP0SourceError,
                "commit type mismatch",
            ):
                historical.pinned_p0_inventory(self.root)

    def test_historical_tree_substitution_is_rejected(self):
        original = historical._git
        def wrong_tree(root, *args):
            if args[0] == "rev-parse":
                return (b"0" * 40) + b"\n"
            return original(root, *args)
        with patch.object(historical, "_git", side_effect=wrong_tree):
            with self.assertRaisesRegex(
                historical.HistoricalP0SourceError,
                "source tree substitution",
            ):
                historical.pinned_p0_inventory(self.root)

    def test_history_checkout_is_detached_temporary_and_read_only_to_parent(self):
        before = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.root, text=True,
        ).strip()
        with historical.pinned_p0_checkout(self.root) as checkout:
            self.assertEqual(
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=checkout, text=True,
                ).strip(),
                historical.HISTORICAL_HEAD,
            )
            self.assertEqual(
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD^{tree}"],
                    cwd=checkout, text=True,
                ).strip(),
                historical.HISTORICAL_TREE,
            )
            self.assertTrue((checkout / ".git").exists())
        self.assertFalse(checkout.exists())
        self.assertEqual(
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=self.root, text=True,
            ).strip(),
            before,
        )


if __name__ == "__main__":
    unittest.main()
