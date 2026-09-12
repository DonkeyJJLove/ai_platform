from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'.github/workflows/lion-group-channel.yml'
class GroupChannelWorkflowHardeningTests(unittest.TestCase):
 def text(self):return P.read_text(encoding='utf-8')
 def test_exact_head_tree_binding(self):
  t=self.text();self.assertIn('actual_head="$(git rev-parse HEAD)"',t);self.assertIn("actual_tree=\"$(git rev-parse 'HEAD^{tree}')\"",t);self.assertIn('test "$actual_head" = "$GITHUB_SHA"',t)
 def test_receipt_is_digest_bound_before_upload(self):
  t=self.text();self.assertIn('GROUP_CHANNEL_RECEIPT_SHA256',t);self.assertIn('sha256sum "$receipt"',t);self.assertIn('actions/upload-artifact@',t)
 def test_effect_free_boundary_preserved(self):
  t=self.text();self.assertIn('value["authority_effect"] is False',t);self.assertIn('value["repository_effect"] is False',t);self.assertIn('"payload" not in value',t);self.assertIn('permissions:\n  contents: read',t)
 def test_trigger_and_pinned_actions_preserved(self):
  t=self.text();self.assertIn('workflow_dispatch:',t);self.assertIn('actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803',t);self.assertIn('actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1',t)
if __name__=='__main__':unittest.main()
