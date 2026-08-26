from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.moon_file_write import MoonFileWriteRequest
from cyber_lion.enterprise.moon_file_write_mediation import (
    CanonicalMoonFileWriteAdmission, CanonicalMoonFileWriteMediator, DurableMoonFileWriteFence,
    MoonFileTargetObservation, MoonFileWriteMediationError, MoonFileWriteObserver,
)


def req(mode="CREATE_ONLY"):
    old=sha256(b"OLD").hexdigest() if mode!="CREATE_ONLY" else None
    return MoonFileWriteRequest("1.0.0","rec-"+mode,"DonkeyJJLove/ai_platform",144,"DonkeyJJLove","lion-moon-r9d8-test",
        "/home/d2j3/rec-unit.txt",mode,"ABSENT" if mode=="CREATE_ONLY" else "PRESENT_EXACT",old,
        sha256(b"NEW").hexdigest(),3,sha256(b"event").hexdigest()).sealed()


def adm(r):
    return CanonicalMoonFileWriteAdmission(r.request_digest,r.repository,r.control_issue,r.actor_login,r.runner_name,r.target_path,
        r.operation_mode,r.expected_previous_state,r.expected_previous_sha256,r.intended_content_sha256,r.intended_content_size,
        r.source_event_digest,sha256(b"auth").hexdigest(),sha256(b"pdp").hexdigest(),1,"resolver").sealed()


class Resolver:
    def __init__(self,a): self.a=a
    def resolve(self,r): return self.a


class Effect:
    def __init__(self): self.calls=0
    def write_exact(self,r,a): self.calls+=1


def absent(path):
    return MoonFileTargetObservation(path,False,False,False,None,None,None,None,1,2,"observer","2026-08-26T00:00:00+00:00").sealed()


def present(path,digest,size=3):
    return MoonFileTargetObservation(path,True,True,False,size,digest,3,4,1,2,"observer","2026-08-26T00:00:01+00:00").sealed()


class MoonFileWriteReconciliationTests(unittest.TestCase):
    def _run(self,r,pre,post):
        a=adm(r); effect=Effect()
        with tempfile.TemporaryDirectory() as td:
            fence=DurableMoonFileWriteFence(str(Path(td)/"f.sqlite3"))
            mediator=CanonicalMoonFileWriteMediator(admissions=Resolver(a),effect=effect,fence=fence,
                pre_observer=MoonFileWriteObserver(),post_observer=MoonFileWriteObserver())
            with mock.patch.object(MoonFileWriteObserver,"observe",side_effect=[pre,pre,post]):
                receipt=mediator.execute(r)
            return receipt,effect.calls,fence.get(receipt.effect_key).state

    def test_create_only_exact_observation_reconciles(self):
        r=req(); receipt,calls,state=self._run(r,absent(r.target_path),present(r.target_path,r.intended_content_sha256))
        self.assertEqual((receipt.result,calls,state),("MATCH",1,"RECONCILED"))
        self.assertFalse(receipt.authority_effect or receipt.repository_effect or receipt.external_network_effect)

    def test_replace_exact_observation_reconciles(self):
        r=req("REPLACE_EXPECTED_DIGEST")
        receipt,calls,state=self._run(r,present(r.target_path,r.expected_previous_sha256,size=3),present(r.target_path,r.intended_content_sha256,size=3))
        self.assertEqual((receipt.result,calls,state),("MATCH",1,"RECONCILED"))

    def test_post_effect_mismatch_never_reconciles_success(self):
        r=req(); a=adm(r); effect=Effect()
        with tempfile.TemporaryDirectory() as td:
            fence=DurableMoonFileWriteFence(str(Path(td)/"f.sqlite3"))
            mediator=CanonicalMoonFileWriteMediator(admissions=Resolver(a),effect=effect,fence=fence,
                pre_observer=MoonFileWriteObserver(),post_observer=MoonFileWriteObserver())
            with mock.patch.object(MoonFileWriteObserver,"observe",side_effect=[absent(r.target_path),absent(r.target_path),present(r.target_path,sha256(b"BAD").hexdigest())]):
                receipt=mediator.execute(r)
            self.assertEqual(receipt.result,"MISMATCH"); self.assertEqual(fence.get(receipt.effect_key).state,"UNKNOWN")

    def test_same_observer_instance_is_denied(self):
        r=req(); a=adm(r)
        with tempfile.TemporaryDirectory() as td:
            fence=DurableMoonFileWriteFence(str(Path(td)/"f.sqlite3")); observer=MoonFileWriteObserver()
            with self.assertRaisesRegex(MoonFileWriteMediationError,"independent observer"):
                CanonicalMoonFileWriteMediator(admissions=Resolver(a),effect=Effect(),fence=fence,pre_observer=observer,post_observer=observer)


if __name__ == "__main__": unittest.main()
