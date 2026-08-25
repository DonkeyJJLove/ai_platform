from __future__ import annotations
import inspect,sqlite3,tempfile,threading,unittest
from pathlib import Path
from dataclasses import replace
from cyber_lion.enterprise.builder_process_launch import BuilderProcessLaunchBoundary
from cyber_lion.enterprise.persistent_authority_state import PersistentAuthorityStateError,PersistentAuthorityStoreOrigin,PersistentBuilderProcessHeldMaterialization,PersistentBuilderProcessLaunchReceipt,SQLiteAuthorityStateStore

D=lambda c:c*64
class BuilderProcessLaunchTests(unittest.TestCase):
    def test_boundary_requires_effect_clock_and_no_runtime_provider_argument(self):
        self.assertIn("effect_clock",inspect.signature(BuilderProcessLaunchBoundary).parameters)
        params=inspect.signature(BuilderProcessLaunchBoundary.launch).parameters
        self.assertNotIn("runtime_provider",params);self.assertNotIn("trusted_now",params)
        src=inspect.getsource(__import__("cyber_lion.enterprise.builder_process_launch",fromlist=["x"]))
        self.assertIn("observe_gate",src);self.assertIn("GATE_CLOSED",src);self.assertIn("GATE_OPENED_ONCE",src)
    def test_store_ready_requires_eleven_tables(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/"a.db");s=SQLiteAuthorityStateStore(p);self.assertEqual(len(s.REQUIRED_TABLES),11);self.assertTrue(s.ready())
            with sqlite3.connect(p) as c:
                cols={r[1] for r in c.execute("PRAGMA table_info(builder_process_held_materialization)")}
            self.assertIn("execution_gate_id",cols);self.assertIn("execution_gate_digest",cols)
    def test_persistent_held_and_receipt_reject_numeric_pid(self):
        origin=PersistentAuthorityStoreOrigin("aso:"+D("e"),D("e"),"1.0.0","/repo","/tmp/a.db").validate()
        held=PersistentBuilderProcessHeldMaterialization("launch:x","bplr:"+D("1"),D("2"),D("1"),"provider:x",D("3"),D("4"),D("5"),"runtime:x","env:x","pidfd:x","token:x",D("6"),"gate:x",D("7"),"CLOSED",D("8"),D("9"),"HELD_NOT_EXECUTING_BUILDER","2026-08-25T14:00:00Z","2026-08-25T14:00:01Z",origin.origin_id,origin.origin_digest).validate()
        with self.assertRaises(PersistentAuthorityStateError):replace(held,process_handle_reference="123").validate()
        rec=PersistentBuilderProcessLaunchReceipt("bplx:"+D("1"),D("2"),"bplr:"+D("1"),D("3"),D("1"),"bsa:"+D("4"),D("5"),"DonkeyJJLove/ai_platform","a"*40,"b"*40,D("6"),D("7"),"bpp:"+D("8"),D("8"),D("9"),"provider:x",D("a"),D("b"),D("c"),"runtime:x","launch:x","env:x","pidfd:x","token:x",D("d"),"gate:x",D("e"),D("f"),D("0"),"2026-08-25T14:00:00Z","2026-08-25T14:00:01Z","BUILDER_PROCESS_START","STARTED_OBSERVED","CLOSED_TO_OPENED_ONCE",origin.origin_id,origin.origin_digest).validate()
        with self.assertRaises(PersistentAuthorityStateError):replace(rec,process_handle_reference="77").validate()
        with self.assertRaises(PersistentAuthorityStateError):replace(rec,gate_transition="OPEN").validate()
    def test_concurrent_launch_replay_one_winner(self):
        with tempfile.TemporaryDirectory() as d:
            s=SQLiteAuthorityStateStore(str(Path(d)/"a.db"));b=threading.Barrier(6);out=[];lock=threading.Lock()
            def w():
                b.wait();v=s.consume_replay("builder-process-launch",D("1"),"2026-08-25T14:00:00Z")
                with lock:out.append(v)
            ts=[threading.Thread(target=w) for _ in range(6)];[t.start() for t in ts];[t.join() for t in ts]
            self.assertEqual(out.count(True),1)
if __name__=="__main__":unittest.main()
