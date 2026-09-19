import hashlib,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from tools.lion_operator_containment_helper import SCHEMA,contain,proc_identity

class OperatorContainmentHelperTests(unittest.TestCase):
    def test_exact_canary_process_is_contained_and_receipted_without_db(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);proc=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
            try:
                time.sleep(.05);identity=proc_identity(proc.pid)
                inv={'schema':SCHEMA,'mission_id':'CANARY-M','targets':[{'target_id':'canary-child','kind':'process',**identity}]}
                path=root/'inventory.json';path.write_text(json.dumps(inv),encoding='utf-8')
                out=contain(path,root/'receipts','CANARY-M','r1',1.5)
                proc.wait(timeout=2)
                self.assertEqual(out['status'],'PASS');self.assertTrue(out['results'][0]['stopped'])
                self.assertTrue((root/'receipts/r1.json').is_file())
                self.assertEqual(contain(path,root/'receipts','CANARY-M','r1',1.5)['receipt_digest'],out['receipt_digest'])
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
    def test_identity_drift_never_signals_reused_or_wrong_process(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);proc=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
            try:
                time.sleep(.05);identity=proc_identity(proc.pid);identity['cmdline_sha256']='0'*64
                inv={'schema':SCHEMA,'mission_id':'CANARY-M','targets':[{'target_id':'wrong','kind':'process',**identity}]}
                path=root/'inventory.json';path.write_text(json.dumps(inv),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'identity drift'):contain(path,root/'receipts','CANARY-M','r2',.2)
                self.assertIsNone(proc.poll())
            finally:proc.terminate();proc.wait(timeout=2)
if __name__=='__main__':unittest.main()
