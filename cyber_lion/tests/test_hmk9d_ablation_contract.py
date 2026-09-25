import unittest
from cyber_lion.contracts.hmk9d_ablation import *
Z="0"*64
class HMK9DAblationTests(unittest.TestCase):
    def test_matched_ablation(self):
        c=HMK9DMatchedAblation(Z,"release:1",Z,Z,Z,"DonkeyJJLove/chunk-chunk:HMK-9D",False,True).validate()
        self.assertFalse(c.variant_a_annotation);self.assertTrue(c.variant_b_annotation)
    def test_no_effect_semantics(self):
        c=HMK9DMatchedAblation(Z,"release:1",Z,Z,Z,"chunk",False,True).validate()
        self.assertEqual(c.authority_effect,"NONE");self.assertEqual(c.training_effect,"NONE")
if __name__=="__main__":unittest.main()
