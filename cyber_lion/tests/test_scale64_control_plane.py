from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
class T(unittest.TestCase):
 def text(self,p): return (ROOT/p).read_text()
 def test_provider(self):
  s=self.text('tools/p0_rootless_docker_provider.py'); self.assertIn('"LIST_FLEET_RESOURCES"',s); self.assertNotIn('LIST_FLEET_RESOURCES',s.split('MUTATING = {',1)[1].split('}',1)[0]); b=s.split('if op == "LIST_FLEET_RESOURCES":',1)[1].split('raise Deny("unreachable operation")',1)[0]; self.assertIn('lion.fleet_id',b); self.assertNotIn('lion.run_id',b); old=s.split('if op == "LIST_MISSION_RESOURCES":',1)[1].split('if op == "LIST_FLEET_RESOURCES":',1)[0]; self.assertIn('lion.run_id',old)
 def test_broker(self):
  s=self.text('tools/lion_effect_admission_broker.py'); self.assertIn('PRECHECK_SCALE64',s); self.assertIn('LIST_FLEET_RESOURCES',s); self.assertIn('runner_exec_call(',s); self.assertNotIn('/usr/sbin/runuser',s); self.assertNotIn('os.setuid',s); self.assertNotIn('os.setgid',s); self.assertNotIn('os.setgroups',s); self.assertIn('shell=False',s)
 def test_client(self):
  s=self.text('tools/lion_effect_admission_client.py'); self.assertIn('precheck-scale64',s); self.assertNotIn('docker.sock',s); self.assertNotIn('provider.sock',s)
 def test_updater(self):
  s=self.text('tools/lion_broker_update_provider.py'); self.assertIn('lion-effect-admission-broker.py',s); self.assertIn('/usr/local/libexec/',s); self.assertIn('shell=False',s); self.assertIn('"PRECHECK_SCALE64"',s)
 def test_controller(self):
  s=self.text('tools/lion_scale64_controller.py'); self.assertNotIn('argparse',s); self.assertIn("BRANCH='experiment/local-swarm-p0-docker-polygon'",s); self.assertNotIn('docker.sock',s); self.assertNotIn('provider.sock',s)
 def test_service(self):
  s=self.text('deploy/docker/lion-scale64-control/lion-scale64-control.service'); self.assertIn('User=sentinelx',s); self.assertNotIn('User=root',s); self.assertIn('NoNewPrivileges=yes',s)
 def test_installer(self):
  s=self.text('deploy/docker/lion-scale64-control/install.sh'); self.assertIn('actions: [status, start, is-active, is-enabled]',s); self.assertNotIn('actions: [status, start, stop',s); self.assertIn('/opt/sentinelx-cloud-core/.venv/bin/python',s); self.assertNotIn('systemctl restart sentinelx-cloud-core',s); self.assertIn('/usr/sbin/visudo -cf',s); self.assertIn('/etc/sudoers.d/lion-scale64-control',s)
 def test_exact_service_sudoers(self):
  s=self.text('deploy/docker/lion-scale64-control/lion-scale64-control.sudoers'); self.assertIn('sentinelx LION_HOST = (root) NOPASSWD: LION_CTL',s); self.assertIn('/usr/bin/systemctl restart sentinelx-cloud-core',s); self.assertIn('/usr/bin/systemctl start lion-scale64-control.service',s); self.assertNotIn('/usr/bin/systemctl stop lion-scale64-control.service',s); self.assertNotIn('/usr/bin/systemctl restart lion-scale64-control.service',s); self.assertNotIn('*',s); self.assertNotIn(' NOPASSWD: ALL',s)
 def test_evidence_relay_hash_is_fail_closed(self):
  s=self.text('tools/lion_effect_admission_broker.py'); self.assertIn('relay_evidence_sha256=rr.get("source_evidence_sha256")',s); self.assertIn('require_hex64(relay_evidence_sha256,"relay_evidence_sha256")',s); self.assertIn('EVIDENCE_RELAY_HASH_MISMATCH',s); self.assertIn('broker_evidence_sha256 != relay_evidence_sha256',s); self.assertIn('"relay_evidence_sha256": relay_evidence_sha256',s); self.assertIn('"evidence_relay_match": True',s)
if __name__=='__main__': unittest.main()
