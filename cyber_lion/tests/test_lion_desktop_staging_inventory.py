"""Read-only staging owner inventory tests with disposable trees."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from tools.lion_desktop_staging_inventory import snapshot, InventoryError

class InventoryTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="lion-staging-owner-test-")
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"staging"
        self.root.mkdir()
        (self.root/"Start-LION-Current-R24.vbs").write_text("historical",encoding="utf-8")
        (self.root/"Start-LION-Desktop-PR454-R11.ps1").write_text("current",encoding="utf-8")
        (self.root/"recovery-old").mkdir()
        (self.root/"suspicious.unknown").write_text("uncertain",encoding="utf-8")
    def test_exact_refs_preserved_with_no_retirement(self):
        value=snapshot(self.root,("Start-LION-Current-R24.vbs","Start-LION-Desktop-PR454-R11.ps1"))
        self.assertEqual(value["top_level_count"],4)
        self.assertEqual(value["file_count"],3)
        self.assertEqual(value["directory_count"],1)
        self.assertEqual(value["file_delete_count"],0)
        self.assertTrue(all(not f["deletion_authorized"] for f in value["items"].values()))
        self.assertEqual(value["items"]["suspicious.unknown"]["classification"],"UNCLASSIFIED_PRESERVE_REVIEW")
    def test_missing_exact_active_item_blocks_cleanup_admission(self):
        with self.assertRaisesRegex(InventoryError,"missing"):
            snapshot(self.root,("Start-LION-Current-UNKNOWN.vbs",))
    def test_no_subdirectory_traversal_or_inference(self):
        (self.root/"recovery-old"/"old.sqlite").write_text("do not read",encoding="utf-8")
        value=snapshot(self.root)
        self.assertEqual(value["items"]["recovery-old"]["kind"],"DIRECTORY")
        self.assertNotIn("old.sqlite",value["items"])
    def test_symlink_is_not_followed(self):
        outside=self.root.parent/"not-in-staging.txt"
        outside.write_text("secret",encoding="utf-8")
        link=self.root/"alias.txt"
        try:link.symlink_to(outside)
        except OSError:self.skipTest("Windows symlink privilege unavailable")
        value=snapshot(self.root)
        self.assertEqual(value["items"]["alias.txt"]["kind"],"SYMLINK_HOLD")
        self.assertIsNone(value["items"]["alias.txt"]["sha256"])
    def test_path_traversal_in_active_names_denied(self):
        for label in ("../history",".\\bad","x/y"):
            with self.assertRaises(InventoryError):
                snapshot(self.root,(label,))
if __name__=="__main__": unittest.main()
