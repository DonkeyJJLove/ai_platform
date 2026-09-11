import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


class MigrationTests(unittest.TestCase):
    def test_generic_service_is_primary_and_legacy_tool_is_wrapper(self):
        unit=(ROOT/'deploy/mission-control/lion-mission-control.service').read_text()
        install=(ROOT/'deploy/mission-control/install.sh').read_text()
        wrapper=(ROOT/'tools/vkt_r3_mission_control.py').read_text()
        self.assertIn('User=sentinelx',unit)
        self.assertIn('RuntimeDirectory=lion-mission-control lion-vkt-mission-control',unit)
        self.assertIn('/run/lion-mission-control/listen.json',unit)
        self.assertIn('systemctl stop lion-vkt-mission-control.service',install)
        self.assertIn('systemctl disable lion-vkt-mission-control.service',install)
        self.assertIn('from lion_mission_control import main',wrapper)

    def test_bootstrap_installs_generic_observer(self):
        text=(ROOT/'deploy/k8s/vkt-r3/bootstrap-authority.sh').read_text()
        self.assertIn('deploy/mission-control/install.sh',text)
        self.assertIn('lion-mission-control.service',text)
        self.assertNotIn('systemctl restart lion-vkt-mission-control.service',text)

    def test_read_proxy_is_separate_from_generic_http_process(self):
        unit=(ROOT/'deploy/mission-control/lion-mission-control.service').read_text()
        sock=(ROOT/'deploy/mission-control/lion-mission-control-read.socket').read_text()
        proxy=(ROOT/'deploy/mission-control/lion-mission-control-read@.service').read_text()
        self.assertIn('ListenStream=/run/lion-mission-control-read.sock',sock)
        self.assertIn('User=sentinelx',proxy)
        self.assertIn('lion_mission_control_read_proxy.py',proxy)
        self.assertIn('InaccessiblePaths=',unit)

    def test_legacy_vkt_package_is_preserved(self):
        self.assertTrue((ROOT/'cyber_lion/vkt_r3/mission_control/server.py').is_file())
        self.assertTrue((ROOT/'cyber_lion/vkt_r3/mission_control/models.py').is_file())

if __name__=='__main__': unittest.main()
