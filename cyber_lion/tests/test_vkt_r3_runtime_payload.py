import unittest
from cyber_lion.vkt_r3.runtime_payload import runtime_sources,DRONE_SOURCE,ROUTER_SOURCE

class VktR3RuntimePayloadTests(unittest.TestCase):
    def test_embedded_sources_compile(self):
        src=runtime_sources(); self.assertEqual(set(src),{'drone.py','router.py'})
        for name,text in src.items(): compile(text,name,'exec')
    def test_protocol_contract(self):
        for token in ['POD_UID','heartbeat_seq','messages_sent','messages_received','vendor_requests']:
            self.assertIn(token,DRONE_SOURCE)
        for token in ['TIGER_RELATION_ANALYSIS','SPECTRA_FALSIFIER','LION_LOCAL_EXECUTION','LION_RECEIPT','SPECTRA_PROOF_UPDATE','TIGER_ADJACENCY','VKT-R3-CASE-']:
            self.assertIn(token,ROUTER_SOURCE)
        self.assertIn("CASES=[f'VKT-R3-CASE-{i:02d}' for i in range(1,37)]",ROUTER_SOURCE)
        self.assertIn("if counts!=EXPECTED: return",ROUTER_SOURCE)
        self.assertIn("mission['duplicates']",ROUTER_SOURCE)
        self.assertIn("mission['orphans']",ROUTER_SOURCE)

    def test_network_policy_is_cluster_only(self):
        import importlib.util
        from pathlib import Path
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location("mat", root/"tools"/"lion_k3s_pod_materializer.py")
        mat=importlib.util.module_from_spec(spec); spec.loader.exec_module(mat)
        pol=next(d for d in mat.manifest()["documents"] if d.get("kind")=="NetworkPolicy")
        text=str(pol)
        self.assertIn("10.42.0.0/16", text)
        self.assertIn("10.43.0.0/16", text)
        self.assertNotIn("0.0.0.0/0", text)

if __name__=='__main__': unittest.main()
