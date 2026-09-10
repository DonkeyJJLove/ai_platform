import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'tools'/'lion_k3s_pod_provider_v2.py'
spec=importlib.util.spec_from_file_location('v2',P); v2=importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)

class ProviderV2Tests(unittest.TestCase):
    def test_manifest_is_digest_pinned_and_nonroot(self):
        payload=v2.transformed_manifest()
        workloads=[d for d in payload['documents'] if d.get('kind') in {'Deployment','StatefulSet'}]
        images={c['image'] for d in workloads for c in d['spec']['template']['spec']['containers']}
        self.assertEqual(images,{v2.RUNTIME_IMAGE})
        for d in [x for x in workloads if x.get('kind')=='StatefulSet']:
            c=d['spec']['template']['spec']['containers'][0]
            self.assertEqual(c['command'],v2.DRONE_COMMAND)
            self.assertTrue(c['securityContext']['runAsNonRoot'])
            self.assertEqual(c['securityContext']['runAsUser'],1000)
            self.assertEqual(c['securityContext']['capabilities']['drop'],['ALL'])

    def test_service_executes_v2_from_fixed_repo(self):
        unit=(ROOT/'deploy/k8s/vkt-r3/lion-k3s-pod-provider@.service').read_text()
        self.assertIn('/opt/lion/k3s-vkt-r3/repo/tools/lion_k3s_pod_provider_v2.py',unit)

if __name__=='__main__': unittest.main()
