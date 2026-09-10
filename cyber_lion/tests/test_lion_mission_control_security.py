import unittest
from pathlib import Path

from cyber_lion.mission_control.artifacts import safe_path
from cyber_lion.mission_control.schema import validate_event
from cyber_lion.mission_control.read_client import READ_OPERATIONS

ROOT=Path(__file__).resolve().parents[2]


class SecurityTests(unittest.TestCase):
    def test_generic_package_has_no_mutating_provider_operation(self):
        root=ROOT/'cyber_lion'/'mission_control'
        text='\n'.join(p.read_text() for p in root.rglob('*.py'))
        for denied in ('START_OSS_REPO_TEST','STOP_OSS_REPO_TEST','MATERIALIZE_VKT_PODS','PREPARE_LOCAL_K8S'):
            self.assertNotIn(denied,text)
        self.assertEqual(READ_OPERATIONS,{'PING','READ_POD_EVIDENCE','READ_OSS_REPO_TEST_EVIDENCE'})

    def test_read_proxy_operation_allowlist_is_exact(self):
        text=(ROOT/'tools/lion_mission_control_read_proxy.py').read_text()
        self.assertIn('READ_POD_EVIDENCE',text)
        self.assertIn('READ_OSS_REPO_TEST_EVIDENCE',text)
        for denied in ('START_OSS_REPO_TEST','STOP_OSS_REPO_TEST','MATERIALIZE_VKT_PODS','PREPARE_LOCAL_K8S'):
            self.assertNotIn(denied,text)

    def test_service_masks_mutating_and_control_sockets(self):
        text=(ROOT/'deploy/mission-control/lion-mission-control.service').read_text()
        self.assertIn('InaccessiblePaths=',text)
        for path in ('/run/lion-vkt-effect-admission.sock','/run/lion-k3s-vkt-r3/provider.sock','/run/lion-runner-exec.sock','/run/lion-effect-admission.sock'):
            self.assertIn(path,text)
        self.assertIn('/run/lion-mission-control-read.sock',text)

    def test_server_has_no_subprocess(self):
        text=(ROOT/'cyber_lion/mission_control/server.py').read_text()
        self.assertNotIn('subprocess',text)

    def test_control_like_event_payload_denied_recursively(self):
        base={'schema_version':'lion.observation-event/v1','event_id':'e1','run_id':'r1','timestamp':1.0,'event_type':'EVIDENCE'}
        with self.assertRaises(ValueError): validate_event({**base,'payload':{'command':'rm'}})
        with self.assertRaises(ValueError): validate_event({**base,'payload':{'nested':{'kubectl':'get pods'}}})

    def test_artifact_escape_denied(self):
        with self.assertRaises(ValueError): safe_path('/etc/passwd')

    def test_ui_escapes_run_fields_before_inner_html(self):
        text=(ROOT/'cyber_lion/mission_control/static/app.js').read_text()
        self.assertIn('const esc=',text)
        self.assertIn('${esc(r.run_id)}',text)
        self.assertIn('${esc(targetText(r))}',text)

if __name__=='__main__': unittest.main()
