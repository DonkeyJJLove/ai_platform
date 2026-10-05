from pathlib import Path
import tempfile,unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cyber_lion.enterprise.edge_yoke.evidence import sign,public_hex
from cyber_lion.mission_control.edge_support import canonical,object_bytes,EdgeRejected
from cyber_lion.mission_control.edge_correction import project_event,deliver_once
class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name).resolve()
        self.key=Ed25519PrivateKey.generate();self.pub=public_hex(self.key)
        self.event=dict(schema='lion.edge.correction-request/v2',request_id='E1',host_id='H',observed_at=100,evidence_head='a'*64,authority_effect='NONE',type='REVIEW_REQUIRED')
        self.binding=dict(host_id='H',mission_id='M1',phase_id='BUILD',conversation_id='C1',binding_epoch=1,generation=1,lane='LOCAL',provider_session_ref='S1',correlation_id='R1',context_digest='b'*64,to_id='LD001')
    def raw(self):return canonical(sign(self.event,self.key))
    def project(self):return project_event(self.raw(),public_key=self.pub,binding=self.binding,now=101)
    def deliver(self,publish,readback):return deliver_once(self.raw(),public_key=self.pub,binding=self.binding,now=101,private_delivery_dir=self.root,publish=publish,readback=readback)
    def test_native_five_field_shape(self):self.assertEqual(set(self.project()),{'protocol','from_id','to_id','phase','payload'})
    def test_signed_data_and_coordinates_preserved(self):
        p=self.project()['payload'];self.assertEqual(p['route_binding'],self.binding);self.assertEqual(p['signed_observation']['payload'],self.event)
    def test_wrong_host(self):
        self.binding['host_id']='OTHER'
        with self.assertRaises(EdgeRejected):self.project()
    def test_stale(self):
        self.event['observed_at']=0
        with self.assertRaises(EdgeRejected):self.project()
    def test_authority_not_accepted(self):
        self.event['authority_effect']='ALLOW'
        with self.assertRaises(EdgeRejected):self.project()
    def test_actual_payload_readback(self):
        rows={}
        def send(mid,m):rows[mid,m['payload']['request_id']]=m['payload']
        r=self.deliver(send,lambda m,q:rows[m,q]);self.assertEqual(r['state'],'DELIVERY_OBSERVED')
    def test_ack_is_not_payload_delivery(self):
        with self.assertRaises(EdgeRejected):self.deliver(lambda *x:{'ok':True},lambda *x:{'ok':True})
    def test_send_unknown_not_replayed(self):
        calls=[]
        def fail(*a):calls.append(a);raise TimeoutError()
        with self.assertRaises(TimeoutError):self.deliver(fail,lambda *x:None)
        with self.assertRaises(EdgeRejected):self.deliver(fail,lambda *x:None)
        self.assertEqual(len(calls),1);self.assertEqual(object_bytes((self.root/'E1.json').read_bytes())['state'],'SEND_UNKNOWN')
    def test_missing_binding_not_inferred(self):
        self.binding.pop('conversation_id')
        with self.assertRaises(EdgeRejected):self.project()
if __name__=='__main__':unittest.main()
