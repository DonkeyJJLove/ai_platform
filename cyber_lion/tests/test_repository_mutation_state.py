from __future__ import annotations
import inspect,tempfile,threading,unittest
from unittest.mock import patch
import cyber_lion.enterprise.repository_mutation_state as m
from cyber_lion.enterprise.repository_mutation_state import *
def args(effect="e1",akey="a"*64,adm="a1"):
    return dict(effect_id=effect,authority_effect_key=akey,admission_id=adm,admission_digest=("b" if adm=="a1" else "c")*64,intent_digest="d"*64,candidate_digest="e"*64,repository="r",branch="b",expected_head_sha="1"*40,expected_parent_sha="1"*40,candidate_commit_sha="2"*40,candidate_tree_sha="3"*40,verification_digest="4"*64,runtime_binding_digest="7"*64,live_admission_digest="5"*64,grant_id="g",grant_digest="6"*64,authority_epoch=1,prepared_at="t")
class Tests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.p=patch.object(m,"CANONICAL_REPOSITORY_ATTACH_JOURNAL_PATH",self.t.name+"/j.db"); self.p.start()
    def tearDown(self): self.p.stop(); self.t.cleanup()
    def test_scope(self):
        j=RepositoryAttachJournal(); self.assertEqual(j.scope_class,"SINGLE_RUNTIME_ATTACH_ONLY")
        self.assertEqual(tuple(inspect.signature(RepositoryAttachJournal).parameters),())
    def test_restart_single_use(self):
        a=RepositoryAttachJournal(); b=RepositoryAttachJournal(); a.prepare(**args())
        with self.assertRaises(RepositoryMutationStateError): b.prepare(**args(effect="e2",adm="a2"))
    def test_terminal_observation(self):
        j=RepositoryAttachJournal(); j.prepare(**args()); j.mark_attempted("e1",attempted_at="x")
        with self.assertRaises(RepositoryMutationStateError): j.mark_failed_no_effect("e1",observed_head_sha="9"*40,finalized_at="f")
        st=j.mark_failed_no_effect("e1",observed_head_sha="1"*40,finalized_at="f"); self.assertEqual(st.status,"FAILED_NO_EFFECT")
    def test_concurrent_prepare_single_winner(self):
        results=[]; lock=threading.Lock()
        def run(i):
            j=RepositoryAttachJournal()
            try: j.prepare(**args(effect=f"e{i}",akey="f"*64,adm=f"a{i}")); out="PASS"
            except RepositoryMutationStateError: out="DENY"
            with lock: results.append(out)
        th=[threading.Thread(target=run,args=(i,)) for i in range(8)]
        [x.start() for x in th]; [x.join() for x in th]
        self.assertEqual(results.count("PASS"),1)
    def test_wrong_observed_head_cannot_mark_applied(self):
        j=RepositoryAttachJournal(); j.prepare(**args()); j.mark_attempted("e1",attempted_at="x")
        with self.assertRaises(RepositoryMutationStateError): j.mark_applied("e1",observed_head_sha="9"*40,finalized_at="f")
    def test_attempted_can_enter_reconcile(self):
        j=RepositoryAttachJournal(); j.prepare(**args()); j.mark_attempted("e1",attempted_at="x")
        st=j.mark_reconcile_required("e1",observed_head_sha=None,finalized_at="f"); self.assertEqual(st.status,"RECONCILE_REQUIRED")
if __name__=="__main__": unittest.main()
