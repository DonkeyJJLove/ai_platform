from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess,unittest
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_global_mediation_closure import GlobalMediationClosureCarrierBuilder,GlobalMediationClosureError
from tools.p0_global_mediation_contract import MEDIATION_CLOSURE_RECORD_DIGEST_DOMAIN,mediation_closure_record_digest
from cyber_lion.contracts.production_mediation import MediationClosureRecord,ProductionMediationContractError
from cyber_lion.enterprise.mediation_falsification import MediationBindingRegistry,MediationFalsificationError
from cyber_lion.contracts.mediation_falsification import MediationBindingCandidate
from cyber_lion.contracts.complete_mediation import MediationBinding

REPO="DonkeyJJLove/ai_platform";MOON_REPLACE="8c6d0020a0816d674a783504d2a8ccc25e3e75c0d446057ba3f4450bd768f687";MOON_LIVE_TRACE="53fbe8ccdae9a89d0177f01b555d3935b2290ba4975d733afebde2e68ced4e0e";H=lambda c:c*64

def current_inventory():
    root=Path(__file__).resolve().parents[2];sources={}
    for raw in subprocess.run(["git","ls-files"],check=True,stdout=subprocess.PIPE,text=True).stdout.splitlines():
        if (raw.startswith("cyber_lion/") and raw.endswith(".py") and "/tests/" not in f"/{raw}") or (raw.startswith(".github/workflows/") and raw.endswith((".yml",".yaml"))):sources[raw]=(root/raw).read_text(encoding="utf-8")
    revision=subprocess.run(["git","rev-parse","HEAD"],check=True,stdout=subprocess.PIPE,text=True).stdout.strip();tree=subprocess.run(["git","write-tree"],check=True,stdout=subprocess.PIPE,text=True).stdout.strip()
    raw=EffectSurfaceScanner().scan(repository=REPO,revision=revision,tree_digest=tree,sources=sources)
    return EffectTaxonomyReconciler().reconcile(raw_inventory=raw,sources=sources)

class GlobalMediationClosureCarrierTests(unittest.TestCase):
    def test_current_carrier_materializes_every_surface_and_keeps_moon_replace_unknown(self):
        inv,report,_=current_inventory();self.assertFalse(inv.unclassified_refs);self.assertIn(MOON_REPLACE,{s.digest() for s in inv.surfaces})
        carrier=GlobalMediationClosureCarrierBuilder().materialize(inventory=inv,taxonomy_report=report,explicit_unknown_surface_digests=(MOON_REPLACE,),evidence_refs=("P0-global-inventory-reconciliation",))
        self.assertEqual(len(carrier.surface_statuses),len(inv.surfaces));self.assertEqual(carrier.global_status,"UNKNOWN")
        self.assertEqual(next(x.status for x in carrier.surface_statuses if x.surface_digest==MOON_REPLACE),"UNKNOWN")
        print("P0_GLOBAL_MEDIATION_CLOSURE_CARRIER "+carrier.digest()+" inventory="+inv.digest()+" surfaces="+str(len(inv.surfaces))+" unknown="+str(sum(x.status=="UNKNOWN" for x in carrier.surface_statuses)))

    def test_stale_foreign_and_duplicate_closure_records_are_rejected(self):
        inv,report,_=current_inventory();sd=inv.surfaces[0].digest()
        foreign=MediationClosureRecord(H('f'),inv.digest(),"",H('1'),(),"UNKNOWN",()).validate()
        with self.assertRaises(GlobalMediationClosureError):GlobalMediationClosureCarrierBuilder().materialize(inventory=inv,taxonomy_report=report,closure_records=(foreign,))
        stale=MediationClosureRecord(sd,H('e'),"",H('1'),(),"UNKNOWN",()).validate()
        with self.assertRaises(GlobalMediationClosureError):GlobalMediationClosureCarrierBuilder().materialize(inventory=inv,taxonomy_report=report,closure_records=(stale,))
        good=MediationClosureRecord(sd,inv.digest(),"",H('1'),(),"UNKNOWN",()).validate()
        with self.assertRaises(GlobalMediationClosureError):GlobalMediationClosureCarrierBuilder().materialize(inventory=inv,taxonomy_report=report,closure_records=(good,good))

    def test_missing_closure_record_cannot_be_promoted_to_pass(self):
        inv,report,_=current_inventory();carrier=GlobalMediationClosureCarrierBuilder().materialize(inventory=inv,taxonomy_report=report,evidence_refs=("observation",))
        self.assertEqual(carrier.global_status,"UNKNOWN");self.assertTrue(all(x.status=="UNKNOWN" for x in carrier.surface_statuses))

    def test_cross_epoch_binding_is_rejected(self):
        inv,_,_=current_inventory();surface=inv.surfaces[0]
        candidate=MediationBindingCandidate(inv.digest(),surface.digest(),H('1'),H('2'),H('3'),H('4'),H('5'),H('6'),(H('7'),),H('8'),surface.effect_provider,surface.entrypoints[0],("e",),"E1").validate()
        binding=MediationBinding(surface.digest(),H('1'),H('2'),H('3'),H('4'),H('5'),(H('7'),),H('8'),("e",)).validate();registry=MediationBindingRegistry(inventory_digest=inv.digest(),epoch="E2")
        with self.assertRaises(MediationFalsificationError):registry.register(candidate,binding)

    def test_closure_record_digest_contract_vector(self):
        record=MediationClosureRecord(H('1'),H('2'),'',H('3'),(),"PARTIAL",("evidence:a","evidence:b")).validate()
        self.assertEqual(MEDIATION_CLOSURE_RECORD_DIGEST_DOMAIN,b"LION/GLOBAL-MEDIATION-CLOSURE-RECORD/1")
        self.assertEqual(mediation_closure_record_digest(record),"ff67a1705dd21b6ff748486faa80bae7606cf8d1b772c30dbc847dfa8e6c0168")

    def test_closure_record_digest_stability_and_field_order_independence(self):
        record=MediationClosureRecord(H('1'),H('2'),'',H('3'),(),"PARTIAL",("evidence:a","evidence:b")).validate()
        first=mediation_closure_record_digest(record);self.assertEqual(first,mediation_closure_record_digest(record))
        payload=asdict(record);reversed_payload=dict(reversed(tuple(payload.items())))
        raw=json.dumps(reversed_payload,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode("utf-8")
        manual=sha256(MEDIATION_CLOSURE_RECORD_DIGEST_DOMAIN+b"\0"+raw).hexdigest()
        self.assertEqual(first,manual)

    def test_single_valid_live_moon_partial_record_executes_and_global_stays_unknown(self):
        inv,report,_=current_inventory()
        record=MediationClosureRecord(MOON_REPLACE,inv.digest(),"",MOON_LIVE_TRACE,(),"PARTIAL",("github-actions-run:33911284689","github-actions-job:101148041371","moon-live-cert-r2",)).validate()
        carrier=GlobalMediationClosureCarrierBuilder().materialize(inventory=inv,taxonomy_report=report,closure_records=(record,),evidence_refs=("P0-global-inventory-reconciliation","moon-live-cert-r2"))
        moon=next(x for x in carrier.surface_statuses if x.surface_digest==MOON_REPLACE)
        self.assertEqual(moon.status,"PARTIAL");self.assertEqual(moon.closure_record_digest,mediation_closure_record_digest(record))
        self.assertEqual(sum(x.status=="PARTIAL" for x in carrier.surface_statuses),1)
        self.assertEqual(sum(x.status=="UNKNOWN" for x in carrier.surface_statuses),len(inv.surfaces)-1)
        self.assertEqual(carrier.global_status,"UNKNOWN")

    def test_single_valid_mediated_record_path_executes_but_global_stays_unknown(self):
        inv,report,_=current_inventory()
        record=MediationClosureRecord(MOON_REPLACE,inv.digest(),H('a'),H('b'),(H('c'),),"MEDIATED",("test:binding","test:bypass",)).validate()
        carrier=GlobalMediationClosureCarrierBuilder().materialize(inventory=inv,taxonomy_report=report,closure_records=(record,),evidence_refs=("test:positive-record-path",))
        moon=next(x for x in carrier.surface_statuses if x.surface_digest==MOON_REPLACE)
        self.assertEqual(moon.status,"MEDIATED");self.assertEqual(moon.closure_record_digest,mediation_closure_record_digest(record))
        self.assertEqual(sum(x.status=="MEDIATED" for x in carrier.surface_statuses),1)
        self.assertEqual(sum(x.status=="UNKNOWN" for x in carrier.surface_statuses),len(inv.surfaces)-1)
        self.assertEqual(carrier.global_status,"UNKNOWN")

    def test_missing_binding_and_bypass_cannot_promote_live_moon_to_mediated(self):
        inv,_,_=current_inventory()
        with self.assertRaises(ProductionMediationContractError):
            MediationClosureRecord(MOON_REPLACE,inv.digest(),"",MOON_LIVE_TRACE,(),"MEDIATED",("moon-live-cert-r2",)).validate()
