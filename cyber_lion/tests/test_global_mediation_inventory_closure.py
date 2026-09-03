from __future__ import annotations
from pathlib import Path
import subprocess
import unittest
from cyber_lion.enterprise.complete_mediation import CompleteMediationEngine,EffectSurfaceScanner
from cyber_lion.enterprise.host_authority_separation import _production_path
ROOT=Path(__file__).resolve().parents[2]

def exact_inventory():
    raw=subprocess.run(['git','ls-files','-z'],check=True,stdout=subprocess.PIPE).stdout
    sources={}
    for item in raw.split(b'\0'):
        if item:
            p=item.decode()
            if _production_path(p): sources[p]=(ROOT/p).read_text()
    head=subprocess.run(['git','rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
    tree=subprocess.run(['git','write-tree'],check=True,capture_output=True,text=True).stdout.strip()
    return sources,EffectSurfaceScanner().scan(repository='DonkeyJJLove/ai_platform',revision=head,tree_digest=tree,sources=sources)

class GlobalMediationInventoryClosureTests(unittest.TestCase):
    def test_exact_inventory_has_zero_unclassified_refs(self):
        sources,inv=exact_inventory()
        self.assertEqual((len(sources),len(inv.surfaces),len(inv.unclassified_refs)),(255,241,0))
    def test_control_effects_are_explicit_surfaces(self):
        paths=('cyber_lion/enterprise/repository_maintenance_mediated_cleanup.py','cyber_lion/enterprise/repository_mutation_pep.py')
        inv=EffectSurfaceScanner().scan(repository='DonkeyJJLove/ai_platform',revision='1'*40,tree_digest='2'*40,sources={p:(ROOT/p).read_text() for p in paths})
        classes={s.effect_class for s in inv.surfaces}
        self.assertIn('repository_ref.delete.authorization',classes)
        self.assertIn('fleet_budget.release',classes)
        self.assertEqual(inv.unclassified_refs,())
    def test_zero_unclassified_does_not_fake_global_pass(self):
        _,inv=exact_inventory()
        a=CompleteMediationEngine().assess(inventory=inv,bindings=(),falsification_evidence_refs=('inventory-closure',),observation_evidence_refs=('exact-candidate',))
        self.assertEqual(a.global_status,'UNKNOWN')
        self.assertEqual(len(a.matrix),241)
        self.assertTrue(all(row.status=='UNKNOWN' for row in a.matrix))
if __name__=='__main__': unittest.main()
