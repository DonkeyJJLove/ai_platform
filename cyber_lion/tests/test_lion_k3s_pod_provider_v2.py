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

    def test_stuck_recycle_predicate_is_narrow_and_bounded(self):
        sample={"pods":[
            {"name":"lion-drone-101","ready":False,"restarts":0,"container_states":[{"waiting_reason":"ContainerCreating"}]},
            {"name":"tiger-drone-1","ready":True,"restarts":0,"container_states":[{"waiting_reason":None}]},
            {"name":"spectra-drone-2","ready":False,"restarts":1,"container_states":[{"waiting_reason":"CrashLoopBackOff"}]},
        ]}
        self.assertEqual(v2._stuck_zero_restart_names(sample),["lion-drone-101"])
        too_many={"pods":[{"name":f"lion-drone-{i}","ready":False,"restarts":0,"container_states":[{"waiting_reason":"ContainerCreating"}]} for i in range(17)]}
        with self.assertRaises(RuntimeError):
            v2._stuck_zero_restart_names(too_many)

    def test_cleanup_is_fixed_namespace_only(self):
        text=P.read_text()
        self.assertIn('["delete", "namespace", core.NAMESPACE', text)
        self.assertNotIn('core.kubectl(["exec"', text)

if __name__=='__main__': unittest.main()
