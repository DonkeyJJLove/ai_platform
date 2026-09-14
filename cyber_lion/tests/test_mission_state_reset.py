import importlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from contextlib import closing
from unittest.mock import patch

from tools.lion_mission_state_reset import reset_offline


class MissionResetTests(unittest.TestCase):
    def test_dynamic_descendants_archive_and_restart_remain_empty(self):
        tools=Path(__file__).resolve().parents[2]/'tools'
        with patch.object(sys,'path',[str(tools),*sys.path]):
            compat=importlib.import_module('lion_mission_control_compat')
            with patch.dict(sys.modules,{'mission_control_compat':compat}):
                mc=importlib.import_module('lion_mission_control_v3')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);database=root/'runtime.db'
            with patch.object(mc,'DB',database),patch.object(mc,'LEGACY_DB',root/'absent.db'),patch.object(compat,'V3_DB',database):
                mc.migrate()
                with closing(sqlite3.connect(database)) as conn:
                    conn.execute("INSERT INTO mission_meta VALUES('mission_dispatch_paused','1','2026-09-15T00:00:00Z')")
                    conn.execute('CREATE TABLE future_mission_data(id INTEGER PRIMARY KEY,root_mission_id TEXT,payload TEXT)')
                    conn.execute('CREATE TABLE future_child(id INTEGER PRIMARY KEY,parent_id INTEGER REFERENCES future_mission_data(id),payload TEXT)')
                    conn.execute("INSERT INTO future_mission_data VALUES(1,?,'archive this')",(mc.MISSION,))
                    conn.execute("INSERT INTO future_child VALUES(1,1,'child evidence')")
                    conn.commit()
                receipt=reset_offline(database,root/'archive','2026-09-15T00:00:01Z')
                self.assertGreater(receipt['missions_before'],0)
                self.assertEqual(receipt['deleted_rows']['future_child'],1)
                document=json.loads(Path(receipt['archive_path']).read_text(encoding='utf-8'))
                self.assertEqual(document['mission_state']['future_child'][0]['payload'],'child evidence')
                with closing(sqlite3.connect(receipt['backup_path'])) as backup:
                    self.assertGreater(backup.execute('SELECT count(*) FROM missions').fetchone()[0],0)
                mc.migrate()
                self.assertEqual(mc.mission_summaries(),[])
                self.assertIsNone(mc.focus_mission_id())
                self.assertEqual(mc.snapshot()['state'],'NO_ACTIVE_MISSIONS')
                self.assertEqual(compat.all_runs(mc.snapshot()),[])
                with patch.object(mc,'broker',side_effect=AssertionError('empty registry must not query executor')):
                    mc.observe_once()
                with patch.object(mc.global_sched,'next_dispatch',side_effect=AssertionError('dispatch must remain paused')):
                    mc.global_scheduler_once()
                # Exercise the real HTTP ingress on an ephemeral test listener.
                (root/'saas-mediator.key').write_text('unit-test-only-'*8,encoding='utf-8')
                server=ThreadingHTTPServer(('127.0.0.1',0),mc.H)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                base='http://127.0.0.1:'+str(server.server_port)
                def request(path,body=None,authenticated=False):
                    headers={'Content-Type':'application/json'}
                    if authenticated:headers['X-LION-Mediator-Key']='unit-test-only-'*8
                    data=json.dumps(body).encode() if body is not None else None
                    with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=5) as response:
                        return json.load(response)
                try:
                    self.assertEqual(request('/health')['mission_count'],0)
                    created=request('/api/v3/saas-broker/requests',{'scope_type':'CONTROL_PLANE','question':'Connectivity?','authority_effect':'NONE'})
                    prefix='/api/v3/saas-broker/requests/'+created['request_id']
                    with self.assertRaises(urllib.error.HTTPError) as denied:request(prefix+'/claim',{})
                    self.assertEqual(denied.exception.code,403)
                    claim=request(prefix+'/claim',{},True)
                    self.assertNotIn('response_token',request(prefix))
                    answer={k:claim[k] for k in ('response_token','claim_generation')}
                    answer.update(answer='Connected',model_identity='UNIT_TEST_MEDIATOR',transport=mc.saas_broker.TRANSPORT,attestation_class=mc.saas_broker.ATTESTATION_CLASS)
                    self.assertEqual(request(prefix+'/respond',answer,True)['status'],'RESPONDED')
                    with self.assertRaises(urllib.error.HTTPError) as duplicate:request(prefix+'/respond',answer,True)
                    self.assertEqual(duplicate.exception.code,409)
                    self.assertEqual(request('/api/v3/saas-broker/status')['pending_count'],0)
                finally:
                    server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    unittest.main()
