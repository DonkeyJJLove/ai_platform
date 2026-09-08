from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
class TestNNPOverlay(unittest.TestCase):
 def text(self,p): return (ROOT/p).read_text()
 def test_canonical_entry(self):
  s=self.text('tools/lion_effect_admission_broker_entry.py'); self.assertNotIn('runuser',s); self.assertIn('lion-nnp-runner-exec.py',s); self.assertIn('PRECHECK_SCALE64',s)
 def test_runner_drop(self):
  s=self.text('tools/lion_nnp_runner_exec.py'); self.assertNotIn('runuser',s); self.assertIn('os.setgroups([provider_gid])',s); self.assertIn('os.setgid(runner.pw_gid)',s); self.assertIn('os.setuid(runner.pw_uid)',s); self.assertIn('/usr/bin/python3',s)
 def test_provider_adapter(self):
  s=self.text('deploy/docker/lion-p0-provider/install_nnp.sh'); self.assertIn('lion_nnp_runuser_compat.py',s); self.assertIn('PATH="$TMP:/usr/sbin:/usr/bin:/bin"',s)
  h=self.text('tools/lion_nnp_runuser_compat.py'); self.assertIn('RUNTIME_USER = "lion-container-runtime-lab"',h); self.assertIn('RUNNER_USER = "lion-maintenance-runner"',h); self.assertIn('PROVIDER_GROUP = "lion-docker-p0"',h); self.assertIn('os.setgroups(supplementary)',h); self.assertIn('os.setuid(pw.pw_uid)',h)
 def test_control_installer(self):
  s=self.text('deploy/docker/lion-scale64-control/install.sh'); self.assertIn('install_nnp.sh',s); self.assertIn('lion_effect_admission_broker_entry.py',s); self.assertIn('lion-effect-admission-broker-impl.py',s); self.assertNotIn('RESTART_RUNNER=0 bash "$R/deploy/docker/lion-p0-provider/install.sh"',s)
 def test_nnp_preserved(self):
  s=self.text('deploy/docker/lion-scale64-control/lion-effect-admission@.service'); self.assertIn('NoNewPrivileges=yes',s)
if __name__=='__main__': unittest.main()
