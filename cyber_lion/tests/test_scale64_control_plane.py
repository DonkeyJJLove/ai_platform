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
 def _controller(self):
  import importlib.util
  path=ROOT/'tools/lion_scale64_controller.py'; spec=importlib.util.spec_from_file_location('lion_scale64_controller_r11',path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
 def _ping(self,prepared):
  return {'result':{'prepared_scale64':prepared}}
 def _pre(self,provider=True,containers=0,networks=0):
  return {'result':{'provider_current':provider,'container_count':containers if provider else None,'network_count':networks if provider else None}}
 def test_controller_prepares_when_prepared_null(self):
  c=self._controller(); r=c.readiness(self._ping(None),self._pre(), 'a'*40,'b'*40); self.assertTrue(r['needs_prepare']); self.assertFalse(r['prepared_scale64_current']); self.assertTrue(r['fleet_clean'])
 def test_controller_prepares_when_prepared_head_or_tree_stale(self):
  c=self._controller(); head='a'*40; tree='b'*40; base={'source_head':head,'source_tree':tree,'trust_class':'TEST_ONLY'}
  wrong=dict(base); wrong['source_head']='c'*40; self.assertTrue(c.readiness(self._ping(wrong),self._pre(),head,tree)['needs_prepare'])
  wrong=dict(base); wrong['source_tree']='d'*40; self.assertTrue(c.readiness(self._ping(wrong),self._pre(),head,tree)['needs_prepare'])
 def test_controller_prepares_when_provider_stale(self):
  c=self._controller(); head='a'*40; tree='b'*40; prepared={'source_head':head,'source_tree':tree,'trust_class':'TEST_ONLY'}; r=c.readiness(self._ping(prepared),self._pre(False),head,tree); self.assertTrue(r['needs_prepare']); self.assertFalse(r['fleet_clean'])
 def test_controller_skips_prepare_only_when_provider_and_prepared_current(self):
  c=self._controller(); head='a'*40; tree='b'*40; prepared={'source_head':head,'source_tree':tree,'trust_class':'TEST_ONLY'}; r=c.readiness(self._ping(prepared),self._pre(),head,tree); self.assertFalse(r['needs_prepare']); self.assertTrue(r['prepared_scale64_current']); self.assertTrue(r['fleet_clean']); c.require_ready(r)
 def test_controller_blocks_dirty_fleet_before_run(self):
  c=self._controller(); head='a'*40; tree='b'*40; prepared={'source_head':head,'source_tree':tree,'trust_class':'TEST_ONLY'}; r=c.readiness(self._ping(prepared),self._pre(True,1,0),head,tree); self.assertFalse(r['fleet_clean']);
  with self.assertRaises(RuntimeError): c.require_clean_if_observable(r)
 def test_controller_requires_all_three_after_prepare(self):
  c=self._controller(); head='a'*40; tree='b'*40; prepared={'source_head':head,'source_tree':tree,'trust_class':'TEST_ONLY'}
  for r in (c.readiness(self._ping(None),self._pre(),head,tree),c.readiness(self._ping(prepared),self._pre(False),head,tree),c.readiness(self._ping(prepared),self._pre(True,1,0),head,tree)):
   with self.assertRaises(RuntimeError): c.require_ready(r)
 def test_controller_command_failure_captures_bounded_stdout_and_stderr(self):
  s=self.text('tools/lion_scale64_controller.py'); self.assertIn('stdout_tail=',s); self.assertIn('stderr_tail=',s); self.assertIn('ERROR_TAIL = 4096',s); self.assertIn("write('readiness.json'",s); self.assertIn("write('readiness-after-prepare.json'",s)

 def test_r12_workspace_handoff_and_runner_diagnostics(self):
  b=self.text('tools/lion_effect_admission_broker.py'); r=self.text('tools/lion_runner_exec_provider.py'); self.assertIn('handoff_exact_workspace_to_runner(workspace)',b); self.assertIn('followlinks=False',b); self.assertIn('os.lchown',b); self.assertIn('stdout_tail = proc.stdout.decode',b); self.assertIn('stderr_tail = proc.stderr.decode',b); self.assertIn("repo-owner-mismatch",r); self.assertNotIn('safe.directory=*',b)
if __name__=='__main__': unittest.main()
