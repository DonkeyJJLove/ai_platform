import tempfile,unittest
from pathlib import Path
from tools.lion_workflow_homeostasis import audit,CRITICAL
ROOT=Path(__file__).resolve().parents[2]
GOOD="""permissions:\n  contents: read\nconcurrency:\n  group: x\njobs:\n  x:\n    timeout-minutes: 1\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          persist-credentials: false\n      - run: |\n          git rev-parse HEAD\n          git rev-parse HEAD^{tree}\n          echo X_SHA256=$(sha256sum x)\n      - uses: actions/upload-artifact@v4\n"""
class WorkflowHomeostasisTests(unittest.TestCase):
 def test_repository_critical_evidence_workflows_are_fail_closed(self):
  r=audit(ROOT);self.assertGreaterEqual(r['workflow_count'],24);self.assertEqual(r['blocking_defect_count'],0);self.assertEqual(len(r['audit_digest']),64)
 def test_advisory_findings_never_become_blocking_without_critical_rule(self):
  r=audit(ROOT)
  for row in r['workflows']:
   if row['advisory_findings'] and not row['critical_evidence']:
    self.assertEqual(row['blocking_defects'],[],row['name'])
 def test_critical_write_permission_is_detected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'.github/workflows';p.mkdir(parents=True)
   for name in CRITICAL:(p/name).write_text(GOOD)
   (p/'bandit-security.yml').write_text(GOOD.replace('contents: read','contents: write'))
   self.assertGreater(audit(root)['blocking_defect_count'],0)
 def test_classes_separate_runtime_write_observation_and_read_only_ci(self):
  r=audit(ROOT); by={w['name']:w for w in r['workflows']}
  self.assertEqual(by['lion-code-perception-observation.yml']['workflow_class'],'OBSERVATION')
  self.assertEqual(by['f009-live-runtime-proof.yml']['workflow_class'],'LIVE_PROOF')
  self.assertEqual(by['f005-runtime-composition.yml']['workflow_class'],'SELF_HOSTED_RUNTIME')
  self.assertEqual(by['lion-actions-dispatch-bridge.yml']['workflow_class'],'EXTERNAL_WRITE')
  self.assertEqual(by['f005-branch-ownership-registry-ci.yml']['workflow_class'],'READ_ONLY_CI')
  self.assertEqual(by['lion-rag32-validate.yml']['workflow_class'],'CRITICAL_EVIDENCE')
 def test_core_synthetic_merge_tree_binding_is_not_false_positive(self):
  r=audit(ROOT); by={w['name']:w for w in r['workflows']}
  self.assertTrue(by['cyber-lion-contracts.yml']['explicit_head_tree_binding'])
  self.assertNotIn('EXPLICIT_HEAD_TREE_BINDING_MISSING',by['cyber-lion-contracts.yml']['advisory_findings'])
 def test_f005_powershell_exact_binding_is_recognized(self):
  r=audit(ROOT);by={w['name']:w for w in r['workflows']}
  for name in ('f005-runtime-composition.yml','f005-runtime-reconciliation-ingestion.yml','f005-runtime-trust-provisioning.yml'):
   self.assertTrue(by[name]['explicit_head_tree_binding'],name);self.assertNotIn('EXPLICIT_HEAD_TREE_BINDING_MISSING',by[name]['advisory_findings'])
 def test_effect_family_hardening_reduces_findings_without_permission_widening(self):
  r=audit(ROOT);by={w['name']:w for w in r['workflows']}
  for name in ('f005-runtime-branch-ownership-registry-refresh.yml','f005-runtime-composition.yml','f005-runtime-reconciliation-execution.yml','f005-runtime-reconciliation-ingestion.yml','f005-runtime-reconciliation-preflight.yml','f005-runtime-repository-observation.yml','f005-runtime-trust-provisioning.yml','lion-moon-runner-attested-execution-bridge.yml'):
   self.assertTrue(by[name]['concurrency'],name);self.assertTrue(by[name]['explicit_head_tree_binding'],name)
  for name in ('f005-runtime-composition.yml','f005-runtime-reconciliation-ingestion.yml','f005-runtime-trust-provisioning.yml','fleet-attestation-n2.yml'):
   self.assertTrue(by[name]['persist_credentials_false'],name)
  self.assertEqual(by['lion-actions-dispatch-bridge.yml']['write_permissions'],['actions: write','issues: write'])
  self.assertEqual(by['fleet-attestation-n2.yml']['write_permissions'],['attestations: write','id-token: write'])
 def test_effect_workflow_policy_remains_family_review_even_when_current_findings_are_closed(self):
  r=audit(ROOT); by={w['name']:w for w in r['workflows']}
  self.assertEqual(by['lion-actions-dispatch-bridge.yml']['semantic_mutation_policy'],'FAMILY_REVIEW_REQUIRED')
  self.assertEqual(by['fleet-attestation-n2.yml']['semantic_mutation_policy'],'FAMILY_REVIEW_REQUIRED')
  self.assertEqual(r['family_review_workflow_count'],sum(1 for row in r['workflows'] if row['family_review_required']))

if __name__=='__main__':unittest.main()
