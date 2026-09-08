from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
class RunnerExecTests(unittest.TestCase):
 def t(self,p): return (ROOT/p).read_text()
 def test_socket_root_only(self):
  s=self.t('deploy/docker/lion-runner-exec/lion-runner-exec.socket'); self.assertIn('SocketUser=root',s); self.assertIn('SocketGroup=root',s); self.assertIn('SocketMode=0600',s); self.assertIn('Accept=yes',s)
 def test_service_identity_and_nnp(self):
  s=self.t('deploy/docker/lion-runner-exec/lion-runner-exec@.service'); self.assertIn('User=lion-maintenance-runner',s); self.assertIn('Group=lion-maintenance-runner',s); self.assertIn('SupplementaryGroups=lion-docker-p0',s); self.assertIn('NoNewPrivileges=yes',s); self.assertIn('PrivateTmp=no',s)
 def test_provider_is_declarative(self):
  s=self.t('tools/lion_runner_exec_provider.py'); self.assertIn("if peer_uid()!=EXPECTED_ROOT_UID",s); self.assertIn("op=='IDENTITY'",s); self.assertIn("op in {'STATIC_UNITTEST','STATIC_PYCOMPILE'}",s); self.assertIn("op=='PROVIDER_CALL'",s); self.assertIn("op=='SCALE64_RUN'",s); self.assertNotIn('ARBITRARY_EXEC',s); self.assertIn("'180'",s); self.assertIn("'15'",s); self.assertIn("FIXED_REPO=Path('/opt/lion/effect-admission/scale64-repo')",s)
 def test_client_has_fixed_operations(self):
  s=self.t('tools/lion_runner_exec_client.py'); self.assertIn("sub.add_parser('identity')",s); self.assertIn("choices=['PING','LIST_FLEET_RESOURCES']",s); self.assertNotIn('docker.sock',s); self.assertNotIn('provider.sock',s)
 def test_broker_has_no_identity_drop(self):
  s=self.t('tools/lion_effect_admission_broker.py'); self.assertNotIn('/usr/sbin/runuser',s); self.assertNotIn('runner_prefix()',s); self.assertNotIn('os.setuid',s); self.assertNotIn('os.setgid',s); self.assertNotIn('os.setgroups',s); self.assertIn('runner_exec_call(',s); self.assertIn('WORKSPACE_ROOT = INSTALL_ROOT / "workspaces"',s)
 def test_provider_installer_uses_runner_exec(self):
  s=self.t('deploy/docker/lion-p0-provider/install.sh'); self.assertNotIn('runuser ',s); self.assertNotIn('os.setuid',s); self.assertIn('lion-runner-exec-client.py provider-call',s)
 def test_top_installer_no_sentinel_restart(self):
  s=self.t('deploy/docker/lion-scale64-control/install.sh'); self.assertIn('lion-runner-exec.socket',s); self.assertIn('SENTINELX_RESTART_REQUIRED=YES',s); self.assertNotIn('systemctl restart sentinelx-cloud-core',s)
 def test_runner_returns_source_evidence_hash_and_cleans_state(self):
  s=self.t('tools/lion_runner_exec_provider.py'); self.assertIn('source_evidence_sha256',s); self.assertIn('shutil.rmtree(run_dir,ignore_errors=True)',s)
if __name__=='__main__': unittest.main()
