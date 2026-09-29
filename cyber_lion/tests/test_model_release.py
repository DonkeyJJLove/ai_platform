import unittest
from dataclasses import replace
from cyber_lion.contracts.model_release import *
Z="0"*64
class ModelReleaseTests(unittest.TestCase):
    def release(self):
        return ModelRelease("release:1",Z,None,Z,Z,Z,Z,Z,Z).sealed()
    def test_release_is_immutable_digest_identity(self):
        r=self.release(); self.assertEqual(r.release_digest,r.compute_digest())
        with self.assertRaises(ModelReleaseError):
            replace(r,prompt_profile_digest="1"*64).validate()
    def test_lifecycle_is_separate_from_identity(self):
        r=self.release()
        a=ModelReleaseLifecycle(r.release_id,"TRAINING_CANDIDATE",("eval:0",)).validate()
        b=ModelReleaseLifecycle(r.release_id,"EVALUATED_CANDIDATE",("eval:1",)).validate()
        self.assertEqual(a.release_ref,b.release_ref); self.assertNotEqual(a.state,b.state)
    def test_lifecycle_cannot_mint_authority(self):
        with self.assertRaises(ModelReleaseError):
            ModelReleaseLifecycle("release:1","SHADOW_CANDIDATE",(),authority_effect="PROMOTE").validate()
    def test_model_plane_identity_adapter_is_unresolved(self):
        from cyber_lion.contracts.model_plane_adapter import ModelPlaneIdentity
        ident=ModelPlaneIdentity("provider:test","model:test",Z).validate()
        ref=model_plane_identity_to_release_ref(ident)
        self.assertEqual(ref.resolution_state,"IDENTITY_ONLY_UNRESOLVED")
        self.assertEqual(ref.authority_effect,"NONE")
if __name__=="__main__":unittest.main()
