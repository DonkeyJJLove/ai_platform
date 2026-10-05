from pathlib import Path
from contextlib import closing
import sqlite3,tempfile,unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cyber_lion.enterprise.edge_yoke.evidence import sign,verify,public_hex,EvidenceJournal,verify_export
from cyber_lion.enterprise.edge_yoke.gate import YokeGate,VetoBoundResolver
from cyber_lion.enterprise.edge_yoke.observer import initialize,watch
from cyber_lion.mission_control.edge_support import canonical,object_bytes,EdgeRejected,exclusive_local_file

class GateTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name).resolve()
        self.key=Ed25519PrivateKey.generate();self.pub=public_hex(self.key);self.path=self.root/'snapshot.json'
        self.value=dict(schema='lion.edge.veto/v2',host_id='MOON',policy_sha256='a'*64,observed_at=100,expires_at=106,seq=1,state='NO_VETO',authority_effect='NONE')
        self.gate=YokeGate(snapshot=self.path,host_id='MOON',public_key=self.pub,policy_sha256='a'*64,clock=lambda:101)
    def emit(self,**kw):self.path.write_bytes(canonical(sign(dict(self.value,**kw),self.key)))
    def test_valid_signature(self):self.emit();self.assertEqual(self.gate.require_clear()['state'],'NO_VETO')
    def test_missing_snapshot(self):
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_wrong_key(self):
        self.emit();self.gate.public=public_hex(Ed25519PrivateKey.generate())
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_payload_substitution(self):
        e=sign(self.value,self.key);e['payload']['host_id']='OTHER';self.path.write_bytes(canonical(e))
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_wrong_host(self):
        self.emit(host_id='OTHER')
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_wrong_policy(self):
        self.emit(policy_sha256='b'*64)
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_expired(self):
        self.emit(expires_at=101)
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_future(self):
        self.emit(observed_at=102)
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_long_ttl(self):
        self.emit(expires_at=200)
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_hold(self):
        self.emit(state='HOLD')
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_boolean_sequence(self):
        self.emit(seq=True)
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_rollback(self):
        self.emit(seq=4);self.gate.require_clear();self.emit(seq=3)
        with self.assertRaises(EdgeRejected):self.gate.require_clear()
    def test_resolver_not_called_after_veto(self):
        self.emit(state='HOLD');calls=[]
        with self.assertRaises(EdgeRejected):VetoBoundResolver(lambda a:calls.append(a),self.gate)('A')
        self.assertEqual(calls,[])
    def test_context_preserved(self):
        self.emit();value=object();self.assertIs(VetoBoundResolver(lambda a:value,self.gate)('A'),value)
    def test_resolver_result_followed_by_new_check(self):
        self.emit()
        def inner(a):self.emit(state='HOLD');return object()
        with self.assertRaises(EdgeRejected):VetoBoundResolver(inner,self.gate)('A')
    def test_chain_and_export(self):
        j=EvidenceJournal(self.root/'e.db');j.append({'x':1},self.key);j.append({'x':2},self.key)
        self.assertEqual(verify_export(j.export(),self.pub),j.audit(self.pub))
    def test_tail_truncation_needs_external_anchor(self):
        j=EvidenceJournal(self.root/'e.db');j.append({'x':1},self.key);j.append({'x':2},self.key);h=j.audit(self.pub)
        with closing(sqlite3.connect(j.path)) as c:
            with c:c.execute('DELETE FROM events WHERE seq=2')
        with self.assertRaisesRegex(EdgeRejected,'checkpoint'):j.audit(self.pub,h)
    def test_internal_gap_detected(self):
        j=EvidenceJournal(self.root/'e.db');j.append({'x':1},self.key);j.append({'x':2},self.key)
        with closing(sqlite3.connect(j.path)) as c:
            with c:c.execute('DELETE FROM events WHERE seq=1')
        with self.assertRaises(EdgeRejected):j.audit(self.pub)
    def test_duplicate_json(self):
        with self.assertRaises(EdgeRejected):object_bytes(b'{"x":1,"x":2}')
    def test_nonfinite_json(self):
        with self.assertRaises(EdgeRejected):object_bytes(b'{"x":NaN}')
    def test_lock_second_writer_rejected(self):
        with exclusive_local_file(self.root/'lock'):
            with self.assertRaises(EdgeRejected):
                with exclusive_local_file(self.root/'lock'):pass
    def test_observer_signed_stop(self):
        h=self.root/'observer';cfg=initialize(h,'H');watch(h,seconds=0)
        frame=verify(object_bytes((h/'snapshot.json').read_bytes()),cfg['public_key'])
        self.assertEqual(frame['state'],'HOLD')
    def test_quarantine_persists_after_restart(self):
        h=self.root/'observer';cfg=initialize(h,'H')
        with patch('cyber_lion.enterprise.edge_yoke.observer.sample_host',return_value={'integrity':'MISMATCH'}):watch(h,seconds=.01,interval=.05)
        watch(h,seconds=0);frame=verify(object_bytes((h/'snapshot.json').read_bytes()),cfg['public_key']);self.assertEqual(frame['state'],'QUARANTINE')
    def test_observer_does_not_replace_keys(self):
        h=self.root/'observer';initialize(h,'H');before=(h/'observer.private.pem').read_bytes()
        with self.assertRaises(EdgeRejected):initialize(h,'H')
        self.assertEqual((h/'observer.private.pem').read_bytes(),before)
    def test_config_drift_rejected(self):
        h=self.root/'observer';initialize(h,'H');(h/'config.json').write_bytes(b'{}')
        with self.assertRaises(EdgeRejected):watch(h,seconds=0)
if __name__=='__main__':unittest.main()
