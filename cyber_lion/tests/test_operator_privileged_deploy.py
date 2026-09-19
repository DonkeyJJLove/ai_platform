import hashlib
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import lion_effect_admission_broker as broker

HEAD='1'*40
TREE='2'*40
RID='3'*64
TASK='LION-OPERATOR-DRONE-SUPREMACY-AND-LIVE-MISSION-INTERVENTION-R1'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class OperatorPrivilegedDeployTests(unittest.TestCase):
    def envelope(self,**extra):
        value={'schema_version':'1.0.0','request_id':RID,'operation':'OPERATOR_INTERVENTION_DEPLOY','task_id':TASK,'source_head':HEAD,'source_tree':TREE}
        value.update(extra);return value

    def test_envelope_is_fixed_to_operator_branch_currentness(self):
        with patch.object(broker,'operator_intervention_git_identity',return_value=(HEAD,TREE)):
            self.assertEqual(broker.operator_intervention_require_envelope(self.envelope()),(HEAD,TREE))
            with self.assertRaisesRegex(broker.Deny,'OPERATOR_INTERVENTION_TASK_ID'):
                broker.operator_intervention_require_envelope(self.envelope(task_id='other'))
            with self.assertRaisesRegex(broker.Deny,'OPERATOR_INTERVENTION_FIELD_SET'):
                broker.operator_intervention_require_envelope({**self.envelope(),'branch':'master'})
        with patch.object(broker,'operator_intervention_git_identity',return_value=('4'*40,TREE)):
            with self.assertRaisesRegex(broker.Deny,'OPERATOR_INTERVENTION_LIVE_SOURCE_DRIFT'):
                broker.operator_intervention_require_envelope(self.envelope())

    def fixture(self,root):
        root=Path(root);stage=root/'stage';live=root/'live';state=root/'state';etc=root/'etc';stage.mkdir();live.mkdir();etc.mkdir()
        (stage/'mission_control_v3.py').write_text('NEW_MC\n')
        (stage/'systemd').mkdir();(stage/'systemd/lion-operator-control.service').write_text('NEW_UNIT\n')
        (live/'mission_control_v3.py').write_text('OLD_MC\n')
        for name in ('operator-gateway.key','operator-sentinelx-proxy.key','operator-panel-proxy.key','operator-pairing.key'):(live/name).write_text('k'*64+'\n')
        db=live/'mission-control-v3.db';c=sqlite3.connect(db);c.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT)');c.commit();c.close()
        drop=etc/'99-v3-control.conf';drop.write_text('OLD_DROPIN\n')
        unit=etc/'lion-operator-control.service';locator=root/'listen.json';locator.write_text(json.dumps({'port':8766,'generation':'MISSION_CONTROL_V3'}))
        expected={'mission_control_v3.py':sha(stage/'mission_control_v3.py'),'systemd/lion-operator-control.service':sha(stage/'systemd/lion-operator-control.service')}
        return stage,live,state,drop,unit,db,locator,expected

    def patches(self,stage,live,state,drop,unit,db,locator,expected,systemctl):
        return [
            patch.object(broker,'MISSION_CONTROL_V3_REQUIRED_SHA256',expected),
            patch.object(broker,'MISSION_CONTROL_V3_ROOT',live),
            patch.object(broker,'OPERATOR_INTERVENTION_STAGE_ROOT',stage),
            patch.object(broker,'OPERATOR_INTERVENTION_STATE_ROOT',state),
            patch.object(broker,'MISSION_CONTROL_V3_DROPIN',drop),
            patch.object(broker,'OPERATOR_CONTROL_UNIT_PATH',unit),
            patch.object(broker,'OPERATOR_PROXY_KEY_PATH',live/'operator-sentinelx-proxy.key'),
            patch.object(broker,'OPERATOR_DB_PATH',db),
            patch.object(broker,'MISSION_CONTROL_V3_LOCATOR',locator),
            patch.object(broker,'operator_intervention_require_envelope',return_value=(HEAD,TREE)),
            patch.object(broker,'_systemctl_exact',side_effect=systemctl),
        ]

    def test_success_copies_exact_package_installs_both_services_and_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            stage,live,state,drop,unit,db,locator,expected=self.fixture(td);calls=[]
            def systemctl(*args,check=True):calls.append(args);return subprocess.CompletedProcess(args,0,b'',b'')
            managers=self.patches(stage,live,state,drop,unit,db,locator,expected,systemctl)
            for m in managers:m.start()
            try:
                with patch.object(broker,'_operator_control_health',return_value={'status':'ok','authenticated_principal':'OPERATOR_SENTINX_PROXY'}),patch.object(broker,'_mission_control_health',return_value={'status':'ok'}):
                    out=broker.operator_intervention_deploy(self.envelope())
            finally:
                for m in reversed(managers):m.stop()
            self.assertTrue(out['installed']);self.assertEqual(out['db_integrity'],'ok')
            self.assertEqual((live/'mission_control_v3.py').read_text(),'NEW_MC\n')
            self.assertEqual(unit.read_text(),'NEW_UNIT\n')
            self.assertEqual((live/'systemd').stat().st_mode & 0o777,0o755)
            self.assertIn(('enable',broker.OPERATOR_CONTROL_UNIT),calls)
            self.assertIn(('restart',broker.OPERATOR_CONTROL_UNIT),calls)
            self.assertIn(('restart',broker.MISSION_CONTROL_V3_UNIT),calls)
            self.assertTrue((state/'receipts'/f'{RID}.json').is_file())

    def test_failed_operator_start_restores_previous_package_and_unit_state(self):
        with tempfile.TemporaryDirectory() as td:
            stage,live,state,drop,unit,db,locator,expected=self.fixture(td);calls=[]
            def systemctl(*args,check=True):calls.append(args);return subprocess.CompletedProcess(args,0,b'',b'')
            managers=self.patches(stage,live,state,drop,unit,db,locator,expected,systemctl)
            for m in managers:m.start()
            try:
                with patch.object(broker,'_wait_health',side_effect=broker.Deny('forced-readback-failure')):
                    with self.assertRaisesRegex(broker.Deny,'OPERATOR_INTERVENTION_DEPLOY_FAILED'):
                        broker.operator_intervention_deploy(self.envelope())
            finally:
                for m in reversed(managers):m.stop()
            self.assertEqual((live/'mission_control_v3.py').read_text(),'OLD_MC\n')
            self.assertFalse((live/'systemd/lion-operator-control.service').exists())
            self.assertEqual(drop.read_text(),'OLD_DROPIN\n')
            self.assertFalse(unit.exists())
            self.assertTrue((state/'deploy-backups'/RID/'rollback.json').is_file())
            self.assertIn(('restart',broker.MISSION_CONTROL_V3_UNIT),calls)

if __name__=='__main__':unittest.main()
