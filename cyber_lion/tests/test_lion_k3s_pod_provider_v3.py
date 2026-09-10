import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'tools'/'lion_k3s_pod_provider_v3.py'
spec=importlib.util.spec_from_file_location('v3',P); v3=importlib.util.module_from_spec(spec); spec.loader.exec_module(v3)
class V3Tests(unittest.TestCase):
    def test_manifest_direct_service_and_hash(self):
        p=v3.transformed_manifest_v3(); cfg=next(d for d in p['documents'] if d.get('kind')=='ConfigMap')
        self.assertIn('VKT_FLEET_ROUTER_SERVICE_HOST',cfg['data']['drone.py'])
        self.assertNotIn('http://vkt-fleet-router:8080',cfg['data']['drone.py'])
        ws=[d for d in p['documents'] if d.get('kind') in {'Deployment','StatefulSet'}]
        self.assertEqual(len({d['spec']['template']['metadata']['annotations']['vkt-runtime-sha256'] for d in ws}),1)
    def test_service_uses_v4_that_wraps_v3(self):
        s=(ROOT/'deploy/k8s/vkt-r3/lion-k3s-pod-provider@.service').read_text()
        self.assertIn('lion_k3s_pod_provider_v4.py',s)
        v4=(ROOT/'tools'/'lion_k3s_pod_provider_v4.py').read_text()
        self.assertRegex(v4, r'V3_PATH\s*=\s*HERE\s*/\s*["\']lion_k3s_pod_provider_v3\.py["\']')
        self.assertIn('V3_PATH)',v4)
        self.assertIn('v3 = _load(',v4)
if __name__=='__main__': unittest.main()
