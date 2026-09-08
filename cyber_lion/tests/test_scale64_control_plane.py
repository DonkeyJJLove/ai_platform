from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
class T(unittest.TestCase):
 def text(self,p): return (ROOT/p).read_text()
 def test_provider(self):
  s=self.text('tools/p0_rootless_docker_provider.py'); self.assertIn('"LIST_FLEET_RESOURCES"',s); self.assertNotIn('LIST_FLEET_RESOURCES',s.split('MUTATING = {',1)[1].split('}',1)[0]); b=s.split('if op == "LIST_FLEET_RESOURCES":',1)[1].split('raise Deny("unreachable operation")',1)[0]; self.assertIn('lion.fleet_id',b); self.assertNotIn('lion.run_id',b); old=s.split('if op == "LIST_MISSION_RESOURCES":',1)[1].split('if op == "LIST_FLEET_RESOURCES":',1)[0]; self.assertIn('lion.run_id',old)
 def test_broker(self):
  s=self.text('tools/lion_effect_admission_broker.py'); self.assertIn('PRECHECK_SCALE64',s); self.assertIn('LIST_FLEET_RESOURCES',s); self.assertIn('os.chmod(workspace, 0o750)',s); self.assertNotIn('0o777',s); self.assertIn('shell=False',s); self.assertNotIn('os.system(',s); self.assertNotIn('exec(',s.split('def _provider_call',1)[1].split('def precheck_scale64',1)[0])
 def test_client(self):
  s=self.text('tools/lion_effect_admission_client.py'); self.assertIn('precheck-scale64',s); self.assertNotIn('docker.sock',s); self.assertNotIn('provider.sock',s)
 def test_updater(self):
  s=self.text('tools/lion_broker_update_provider.py'); self.assertIn('lion-effect-admission-broker.py',s); self.assertIn('/usr/local/libexec/',s); self.assertIn('shell=False',s); self.assertIn('\"PRECHECK_SCALE64\"',s); code=s.split('FORBIDDEN_LITERALS =',1)[1].split('class Deny',1)[1]; self.assertNotIn('os.system(',code); self.assertNotIn('shell=True',code)
 def test_controller(self):
  s=self.text('tools/lion_scale64_controller.py'); self.assertNotIn('argparse',s); self.assertIn("BRANCH='experiment/local-swarm-p0-docker-polygon'",s); self.assertNotIn('docker.sock',s); self.assertNotIn('provider.sock',s)
 def test_service(self):
  s=self.text('deploy/docker/lion-scale64-control/lion-scale64-control.service'); self.assertIn('User=sentinelx',s); self.assertNotIn('User=root',s); self.assertIn('NoNewPrivileges=yes',s)
 def test_installer(self):
  s=self.text('deploy/docker/lion-scale64-control/install.sh'); self.assertIn('actions: [status, start, is-active, is-enabled]',s); self.assertNotIn('actions: [status, start, stop',s); self.assertIn('/opt/sentinelx-cloud-core/.venv/bin/python',s)
if __name__=='__main__': unittest.main()
