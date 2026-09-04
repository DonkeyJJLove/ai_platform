from __future__ import annotations
from pathlib import Path
import subprocess,unittest
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler

REPO="DonkeyJJLove/ai_platform"

def production_sources():
    root=Path(__file__).resolve().parents[2];out={}
    for raw in subprocess.run(["git","ls-files"],check=True,stdout=subprocess.PIPE,text=True).stdout.splitlines():
        if (raw.startswith("cyber_lion/") and raw.endswith(".py") and "/tests/" not in f"/{raw}") or (raw.startswith(".github/workflows/") and raw.endswith((".yml",".yaml"))):
            out[raw]=(root/raw).read_text(encoding="utf-8")
    return out

def scan(sources):return EffectSurfaceScanner().scan(repository=REPO,revision="a"*40,tree_digest="b"*40,sources=sources)

class EffectTaxonomyReconciliationTests(unittest.TestCase):
    def test_current_checkout_resolves_six_without_hiding_surfaces(self):
        src=production_sources();raw=scan(src);self.assertEqual(len(raw.unclassified_refs),6)
        reconciled,report,resolutions=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=src)
        self.assertEqual(report.status,"PASS");self.assertEqual(reconciled.unclassified_refs,())
        self.assertEqual(len(reconciled.surfaces),len(raw.surfaces));self.assertEqual(len(resolutions),6)
        kinds=[r.resolution_kind for r in resolutions]
        self.assertEqual(kinds.count("NON_CONSEQUENTIAL_READ_ONLY"),4)
        self.assertEqual(kinds.count("MEDIATION_GATE_ALIAS"),1)
        self.assertEqual(kinds.count("EFFECT_ALIAS"),1)
        targets={r.source_ref:r for r in resolutions if r.target_surface_digest}
        delete=next(r for ref,r in targets.items() if "authorize_canonical_delete" in ref)
        budget=next(r for ref,r in targets.items() if "_budget_provider.release" in ref)
        self.assertIn("delete_exact_branch_ref",delete.target_entrypoint)
        self.assertIn("fleet_effect_budget.py",budget.target_entrypoint)
        self.assertTrue(any(s.digest()==delete.target_surface_digest and s.effect_class=="repository_ref.delete" for s in reconciled.surfaces))
        self.assertTrue(any(s.digest()==budget.target_surface_digest and s.effect_class=="persistent_state.write" for s in reconciled.surfaces))

    def test_dynamic_mutating_sql_is_never_reconciled_as_read_only(self):
        text="""import sqlite3
def _ro(p):
    uri=p+"?mode=ro"
    c=sqlite3.connect(uri,uri=True)
    c.execute("PRAGMA query_only=ON")
    return c
def f(p,q):
    c=_ro(p)
    c.execute(q)
"""
        src={"cyber_lion/x.py":text};raw=scan(src);self.assertTrue(raw.unclassified_refs)
        rec,report,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=src)
        self.assertEqual(report.status,"UNKNOWN");self.assertTrue(rec.unclassified_refs)

    def test_read_only_statement_without_mode_ro_or_query_only_remains_unknown(self):
        text="""import sqlite3
def f(p):
    c=sqlite3.connect(p)
    q=f"PRAGMA table_info({p})"
    c.execute(q)
"""
        src={"cyber_lion/x.py":text};raw=scan(src);self.assertTrue(raw.unclassified_refs)
        rec,report,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=src)
        self.assertEqual(report.status,"UNKNOWN");self.assertTrue(rec.unclassified_refs)

    def test_alias_resolution_fails_if_consequential_target_is_absent(self):
        text="""class B:
    def authorize_delete(self):
        raise RuntimeError()
    def authorize_canonical_delete(self):
        self.validate(); self.master_sha(); self.branch_sha(); self.master_tree(); self.compare_branch_to_master(); self.open_prs_for_branch(); self.ownership_observation(); self._pending_delete=(1,)
def f(backend):
    backend.authorize_canonical_delete()
"""
        src={"cyber_lion/enterprise/repository_maintenance_mediated_cleanup.py":text};raw=scan(src);self.assertTrue(raw.unclassified_refs)
        rec,report,_=EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=src)
        self.assertEqual(report.status,"UNKNOWN");self.assertTrue(rec.unclassified_refs)
