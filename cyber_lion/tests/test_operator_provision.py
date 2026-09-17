import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cyber_lion.mission_control import operator_control

ROOT=Path(__file__).resolve().parents[2]
TASK_ID='LION-OPERATOR-DRONE-SUPREMACY-AND-LIVE-MISSION-INTERVENTION-R1'

class OperatorProvisionTests(unittest.TestCase):
    def test_proxy_grant_is_expiring_and_primary_remains_nonexpiring(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);db=root/'mc.db';state=root/'state'
            c=sqlite3.connect(db);c.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT)');c.commit();c.close()
            cmd=[sys.executable,'tools/lion_operator_provision.py','--db',str(db),'--key-file',str(root/'primary.key'),'--proxy-key-file',str(root/'proxy.key'),'--panel-proxy-key-file',str(root/'panel.key'),'--pairing-key-file',str(root/'pair.key'),'--state-dir',str(state),'--proxy-grant-hours','2','--confirm',TASK_ID]
            env=dict(os.environ);env['PYTHONPATH']=str(ROOT)
            run=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stderr)
            receipt=json.loads(run.stdout)
            self.assertEqual(receipt['proxy_grant_hours'],2)
            self.assertIsInstance(receipt['proxy_grant_expires_at'],str)
            c=sqlite3.connect(db);c.row_factory=sqlite3.Row
            primary=c.execute("SELECT expires_at FROM operator_grants WHERE principal_id=? AND revoked_at IS NULL",(operator_control.PRIMARY_OPERATOR,)).fetchone()
            proxy=c.execute("SELECT actions_json,expires_at FROM operator_grants WHERE principal_id=? AND revoked_at IS NULL",(operator_control.SENTINELX_PROXY_PRINCIPAL,)).fetchone();c.close()
            self.assertIsNone(primary['expires_at'])
            self.assertEqual(proxy['expires_at'],receipt['proxy_grant_expires_at'])
            self.assertEqual(set(json.loads(proxy['actions_json'])),set(operator_control.DEFAULT_PROXY_ACTIONS))

    def test_invalid_proxy_grant_ttl_fails_before_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);db=root/'mc.db'
            c=sqlite3.connect(db);c.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT)');c.commit();c.close()
            cmd=[sys.executable,'tools/lion_operator_provision.py','--db',str(db),'--key-file',str(root/'primary.key'),'--proxy-key-file',str(root/'proxy.key'),'--panel-proxy-key-file',str(root/'panel.key'),'--pairing-key-file',str(root/'pair.key'),'--state-dir',str(root/'state'),'--proxy-grant-hours','0','--confirm',TASK_ID]
            env=dict(os.environ);env['PYTHONPATH']=str(ROOT)
            run=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('proxy grant hours must be 1..168',run.stderr+run.stdout)
            self.assertFalse((root/'primary.key').exists())

if __name__=='__main__':unittest.main()