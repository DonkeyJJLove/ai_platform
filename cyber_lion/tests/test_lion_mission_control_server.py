import json, tempfile, threading, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from cyber_lion.mission_control.registry import AdapterRegistry
from cyber_lion.mission_control.server import MissionControl, make_handler
from cyber_lion.mission_control.storage import Store


class DummyReconciler:
    errors={}
    def poll_once(self): return []


class ServerTests(unittest.TestCase):
    def test_generic_read_only_api_and_method_denial(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'mc.db')
            store.upsert_run({'run_id':'r1','status':'PASS','verification_status':'VERIFIED','adapter_type':'TEST','process_class':'TEST'})
            mc=MissionControl(store,AdapterRegistry(),DummyReconciler())
            srv=ThreadingHTTPServer(('127.0.0.1',0),make_handler(mc)); port=srv.server_address[1]
            t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
            try:
                for path in ('/health','/api/summary','/api/adapters','/api/runs','/api/runs/r1','/api/runs/r1/events','/api/runs/r1/metrics','/api/runs/r1/participants','/api/runs/r1/artifacts','/api/runs/r1/receipts','/api/export','/api/export/r1'):
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=2) as r:
                        self.assertEqual(r.status,200); json.loads(r.read())
                req=urllib.request.Request(f'http://127.0.0.1:{port}/api/runs',data=b'{}',method='POST')
                with self.assertRaises(urllib.error.HTTPError) as ctx: urllib.request.urlopen(req,timeout=2)
                self.assertEqual(ctx.exception.code,405)
            finally:
                srv.shutdown(); srv.server_close()

if __name__=='__main__': unittest.main()
