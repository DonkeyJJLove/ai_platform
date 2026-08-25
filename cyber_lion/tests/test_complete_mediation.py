from dataclasses import replace
from pathlib import Path
import unittest

from cyber_lion.contracts.complete_mediation import MediationBinding
from cyber_lion.enterprise.complete_mediation import CompleteMediationEngine,CompleteMediationError,EffectSurfaceScanner

class CompleteMediationTests(unittest.TestCase):
    def scan(self,sources):
        return EffectSurfaceScanner().scan(repository="DonkeyJJLove/ai_platform",revision="a"*40,tree_digest="b"*40,sources=sources)

    def binding(self,surface):
        return MediationBinding(surface_digest=surface.digest(),effect_contract_digest="1"*64,pep_identity_digest="2"*64,
            authority_source_digest="3"*64,currentness_source_digest="4"*64,execution_boundary_digest="5"*64,
            observer_identity_digests=("6"*64,),reconciliation_boundary_digest="7"*64,evidence_refs=("observed-binding",)).validate()

    def test_deterministic_inventory_and_source_change_changes_scan_digest(self):
        a=self.scan({"cyber_lion/x.py":"from pathlib import Path\nPath('x').write_text('a')\n","README.md":"ignored"})
        b=self.scan({"README.md":"ignored","cyber_lion/x.py":"from pathlib import Path\nPath('x').write_text('a')\n"})
        self.assertEqual(a.digest(),b.digest())
        c=self.scan({"cyber_lion/x.py":"from pathlib import Path\nPath('x').write_text('b')\n"})
        self.assertNotEqual(a.scan_digest,c.scan_digest)

    def test_hidden_effect_entrypoint_is_detected(self):
        inv=self.scan({"cyber_lion/hidden.py":"import subprocess\ndef hidden():\n    subprocess.run(['tool'])\n"})
        self.assertEqual(len(inv.surfaces),1);self.assertEqual(inv.surfaces[0].effect_class,"runtime.tool_execution")

    def test_filesystem_and_mutating_sql_are_discovered(self):
        inv=self.scan({"cyber_lion/x.py":"def f(conn):\n    open('x','w').write('a')\n    conn.execute('UPDATE t SET x=1')\n"})
        self.assertEqual({s.effect_class for s in inv.surfaces},{"filesystem.write","persistent_state.write"})

    def test_dynamic_sql_is_unclassified_and_keeps_global_unknown(self):
        inv=self.scan({"cyber_lion/x.py":"def f(conn,sql):\n    conn.execute(sql)\n"})
        self.assertTrue(inv.unclassified_refs)
        out=CompleteMediationEngine().assess(inventory=inv,bindings=(),falsification_evidence_refs=("f",),observation_evidence_refs=("o",))
        self.assertEqual(out.global_status,"UNKNOWN")

    def test_missing_binding_is_unknown_not_success(self):
        inv=self.scan({"cyber_lion/x.py":"import subprocess\nsubprocess.run(['x'])\n"})
        out=CompleteMediationEngine().assess(inventory=inv,bindings=(),falsification_evidence_refs=("f",),observation_evidence_refs=("o",))
        self.assertEqual(out.global_status,"UNKNOWN");self.assertEqual(out.matrix[0].status,"UNKNOWN")

    def test_exact_binding_can_mark_one_surface_mediated_but_requires_global_evidence(self):
        inv=self.scan({"cyber_lion/x.py":"import subprocess\nsubprocess.run(['x'])\n"});b=self.binding(inv.surfaces[0])
        out=CompleteMediationEngine().assess(inventory=inv,bindings=(b,),falsification_evidence_refs=("f",),observation_evidence_refs=("o",))
        self.assertEqual(out.global_status,"PASS");self.assertEqual(out.matrix[0].status,"MEDIATED")
        out2=CompleteMediationEngine().assess(inventory=inv,bindings=(b,),falsification_evidence_refs=(),observation_evidence_refs=("o",))
        self.assertEqual(out2.global_status,"UNKNOWN")

    def test_binding_for_surface_outside_inventory_is_denied(self):
        a=self.scan({"cyber_lion/a.py":"import subprocess\nsubprocess.run(['a'])\n"});b=self.scan({"cyber_lion/b.py":"import subprocess\nsubprocess.run(['b'])\n"})
        with self.assertRaises(CompleteMediationError):CompleteMediationEngine().assess(inventory=a,bindings=(self.binding(b.surfaces[0]),),falsification_evidence_refs=("f",),observation_evidence_refs=("o",))

    def test_test_files_and_documentation_do_not_inflate_runtime_inventory(self):
        inv=self.scan({"cyber_lion/tests/test_fake.py":"import subprocess\nsubprocess.run(['x'])\n","cyber_lion/README.md":"subprocess.run"})
        self.assertFalse(inv.surfaces)

    def test_real_checkout_scan_is_observed_and_fail_closed(self):
        root=Path(__file__).resolve().parents[2]
        sources={}
        for p in root.rglob("*"):
            if p.is_file() and (p.suffix==".py" or (p.suffix in {".yml",".yaml"} and ".github/workflows" in p.as_posix())):
                try:sources[p.relative_to(root).as_posix()]=p.read_text(encoding="utf-8")
                except UnicodeDecodeError:pass
        inv=EffectSurfaceScanner().scan(repository="DonkeyJJLove/ai_platform",revision="CI-CHECKOUT",tree_digest="CI-TREE",sources=sources)
        self.assertTrue(inv.evidence_refs);self.assertTrue(any(x.startswith("source-count:") for x in inv.evidence_refs))
        # R9 must not self-certify all discovered surfaces merely because the scanner found them.
        assessment=CompleteMediationEngine().assess(inventory=inv,bindings=(),falsification_evidence_refs=("r9-adversarial-scan",),observation_evidence_refs=("ci-checkout",))
        self.assertEqual(assessment.global_status,"UNKNOWN")

    def test_contract_has_no_effect_or_authority_minting_surface(self):
        inv=self.scan({"cyber_lion/x.py":"import subprocess\nsubprocess.run(['x'])\n"})
        for name in ("execute","authorize","grant","attach","deploy","release"):
            self.assertFalse(hasattr(inv,name))

if __name__=="__main__":unittest.main()
