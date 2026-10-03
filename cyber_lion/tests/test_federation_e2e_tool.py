from dataclasses import asdict,replace
from hashlib import sha256
import unittest
from tools.lion_federation_e2e_verify import FederationE2EError,verify_structure_bundle,verify_evidence_bundle
H=lambda x:sha256(x.encode()).hexdigest()
class FederationE2EVerifierTests(unittest.TestCase):
 def structure(self):
  data=b"graph"
  return {
   "process_spec":{"spec_digest":H("ps")},
   "delta_observation":{"observation_digest":H("delta"),"process_semantics_digest":H("ps")},
   "graph_projection":{"projection_digest":H("graph"),"upstream_digest":H("delta")},
   "artifact_identity":{"bytes_sha256":sha256(data).hexdigest(),"origin_repository":"DonkeyJJLove/mosaic_lab_pro.py","origin_head":"1"*40,"authority_effect":"NONE","publication_effect":"NONE"},
   "swarm_roundtrip":{"roundtrip_digest":H("swarm"),"authority_effect":"NONE","execution_effect":"NONE"},
  },data
 def evidence(self):
  data=b"result"
  return {
   "hypothesis":{"hypothesis_id":"hypothesis:1","digest":H("h"),"status":"TESTABLE"},
   "experiment":{"hypothesis_ref":"hypothesis:1","digest":H("e")},
   "simulation":{"result_digest":H("sim"),"epistemic_class":"SIMULATED"},
   "model_risk":{"result_digest":H("sim")},
   "artifact_identity":{"bytes_sha256":sha256(data).hexdigest(),"authority_effect":"NONE","publication_effect":"NONE"},
   "research_index":{"index_digest":H("idx"),"authority_effect":"NONE","execution_effect":"NONE"},
   "context_snapshot":{"snapshot_digest":H("ctx"),"epoch":1},
  },data
 def test_structure_chain_and_tamper(self):
  b,d=self.structure();r=verify_structure_bundle(b,d);self.assertEqual(r.authority_effect,"NONE")
  b["graph_projection"]["upstream_digest"]=H("wrong")
  with self.assertRaises(FederationE2EError):verify_structure_bundle(b,d)
 def test_evidence_chain_and_epistemic_promotion(self):
  b,d=self.evidence();r=verify_evidence_bundle(b,d);self.assertEqual(r.epistemic_class,"SIMULATED")
  b["simulation"]["epistemic_class"]="OBSERVED"
  with self.assertRaises(FederationE2EError):verify_evidence_bundle(b,d)
 def test_artifact_tamper_denied(self):
  b,d=self.evidence()
  with self.assertRaises(FederationE2EError):verify_evidence_bundle(b,b"tampered")
if __name__=="__main__":unittest.main()
