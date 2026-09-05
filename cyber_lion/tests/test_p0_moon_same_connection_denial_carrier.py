from __future__ import annotations
from pathlib import Path
import subprocess,tempfile,unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.moon_file_write_mediation import DurableMoonFileWriteFence
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_moon_same_connection_denial_carrier import (
    _attack_plans,_exercise_nonhost_denial,_same_connection_pragmas,materialize_same_connection_candidate,
)
from tools.p0_moon_same_connection_denial_contract import ATTACK_IDS,CREATE_TABLE_SURFACE,PRAGMA_SURFACE

REPO="DonkeyJJLove/ai_platform"
EXPECTED_SCAN="8ee66a2523a0b03784ecd283a7c502d928abd0a342b087b236f1c9c6de01c71c"

def inventory():
    root=Path(__file__).resolve().parents[2];sources={}
    for base in (root/"cyber_lion",root/".github/workflows"):
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in {".py",".yml",".yaml"}:sources[p.relative_to(root).as_posix()]=p.read_text(encoding="utf-8")
    rev=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip();tree=subprocess.check_output(["git","rev-parse","HEAD^{tree}"],cwd=root,text=True).strip()
    raw=EffectSurfaceScanner().scan(repository=REPO,revision=rev,tree_digest=tree,sources=sources)
    inv,_,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=sources);return inv

class SameConnectionDenialCarrierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.inv=inventory();cls.a=materialize_same_connection_candidate(inventory=cls.inv)

    def test_revision_bound_and_zero_live_evidence(self):
        self.assertEqual(self.inv.scan_digest,EXPECTED_SCAN)
        self.assertEqual((self.a.plan.observation_receipt_count,self.a.plan.denial_receipt_count,self.a.plan.bypass_result_count),(0,0,0))
        self.assertFalse(self.a.plan.live_execution);self.assertEqual(self.a.plan.global_status,"UNKNOWN")

    def test_observation_carrier_exact_two_surfaces_and_unattached(self):
        s=self.a.observation_spec
        self.assertEqual((s.create_table_surface,s.pragma_surface),(CREATE_TABLE_SURFACE,PRAGMA_SURFACE))
        self.assertFalse(s.live_execution);self.assertEqual(s.state,"CANDIDATE_UNATTACHED")

    def test_denial_carrier_exact_five_and_unattached(self):
        s=self.a.denial_spec
        self.assertEqual(s.attack_ids,ATTACK_IDS);self.assertFalse(s.live_execution)
        self.assertFalse(s.generic_shell);self.assertFalse(s.arbitrary_command);self.assertFalse(s.arbitrary_path);self.assertFalse(s.direct_database_write)

    def test_same_connection_helper_reads_values_from_canonical_connect(self):
        with tempfile.TemporaryDirectory() as td:
            f=DurableMoonFileWriteFence(str(Path(td)/"test.sqlite3"))
            journal,sync=_same_connection_pragmas(f)
            self.assertEqual(journal,"wal");self.assertEqual(sync,2)

    def test_nonhost_denials_are_exact_and_actor_hits_resolver(self):
        plans={p.attack_id:p for p in _attack_plans()}
        for aid in ("WRONG_EXPECTED_STATE","REPOSITORY_SUBSTITUTION","ACTOR_SUBSTITUTION","CONTROL_ISSUE_SUBSTITUTION"):
            with self.assertRaises(Exception) as cm:_exercise_nonhost_denial(aid)
            self.assertEqual(str(cm.exception),plans[aid].expected_denial)
        self.assertEqual(plans["ACTOR_SUBSTITUTION"].pep,"_PermissionAdmissionResolver.resolve")
        self.assertEqual(plans["ACTOR_SUBSTITUTION"].expected_denial,"authority subject substitution")

    def test_all_attack_plans_require_pre_post_equality_and_no_transition(self):
        plans=_attack_plans();self.assertEqual(tuple(p.attack_id for p in plans),ATTACK_IDS)
        for p in plans:
            self.assertTrue(p.denial_before_effect);self.assertTrue(p.canary_hash_capture);self.assertTrue(p.fence_state_capture)
            self.assertTrue(p.pre_post_equality_required);self.assertFalse(p.valid_transition_allowed);self.assertEqual(p.state,"CANDIDATE_UNEXECUTED")

    def test_no_live_method_is_called_by_materialization(self):
        self.assertEqual(self.a.plan.observation_receipt_count,0);self.assertEqual(self.a.plan.denial_receipt_count,0)

    def test_candidate_source_has_no_workflow_or_shell_execution_primitive(self):
        root=Path(__file__).resolve().parents[2];src=(root/"tools/p0_moon_same_connection_denial_carrier.py").read_text()
        for token in ("subprocess.run","os.system","shell=True","eval(","exec("):
            self.assertNotIn(token,src)
        self.assertIn("fence._connect()",src);self.assertIn("fence.prepare(_replay_record(existing))",src)

    def test_r9d9d1_shape_no_direct_sqlite_connect_in_moon_bound_file(self):
        root=Path(__file__).resolve().parents[2];src=(root/"tools/p0_moon_same_connection_denial_carrier.py").read_text()
        self.assertIn("/home/d2j3",src);self.assertNotIn("sqlite3.connect",src)

if __name__=="__main__":unittest.main()
