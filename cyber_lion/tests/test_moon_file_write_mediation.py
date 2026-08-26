from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.moon_file_write import MoonFileWriteRequest
from cyber_lion.enterprise.moon_file_write_mediation import (
    CanonicalMoonFileWriteAdmission, DurableMoonFileWriteFence, MoonFileWriteFenceRecord,
    MoonFileWriteMediationError, moon_file_write_effect_key,
)


def _request():
    return MoonFileWriteRequest(
        "1.0.0","r9d9a-mediation","DonkeyJJLove/ai_platform",144,"DonkeyJJLove","lion-moon-r9d8-test",
        "/home/d2j3/r9d9a-unit.txt","CREATE_ONLY","ABSENT",None,sha256(b"A").hexdigest(),1,
        sha256(b"event").hexdigest(),
    ).sealed()


def _admission(request):
    return CanonicalMoonFileWriteAdmission(
        request.request_digest,request.repository,request.control_issue,request.actor_login,request.runner_name,
        request.target_path,request.operation_mode,request.expected_previous_state,request.expected_previous_sha256,
        request.intended_content_sha256,request.intended_content_size,request.source_event_digest,
        sha256(b"authority").hexdigest(),sha256(b"pdp").hexdigest(),7,"test-provider",
    ).sealed()


class MoonFileWriteMediationTests(unittest.TestCase):
    def test_admission_exactly_binds_request(self):
        request=_request(); admission=_admission(request)
        admission.binds(request)
        with self.assertRaises(MoonFileWriteMediationError):
            replace(admission,target_path="/home/d2j3/other.txt",admission_digest="").sealed().binds(request)

    def test_effect_key_is_deterministic_and_authority_bound(self):
        request=_request(); admission=_admission(request)
        self.assertEqual(moon_file_write_effect_key(request,admission),moon_file_write_effect_key(request,admission))
        changed=replace(admission,authority_epoch=8,admission_digest="").sealed()
        self.assertNotEqual(moon_file_write_effect_key(request,admission),moon_file_write_effect_key(request,changed))

    def test_durable_fence_restart_and_replay_denial(self):
        request=_request(); admission=_admission(request); key=moon_file_write_effect_key(request,admission)
        with tempfile.TemporaryDirectory() as td:
            db=str(Path(td)/"fence.sqlite3")
            fence=DurableMoonFileWriteFence(db)
            record=MoonFileWriteFenceRecord(key,admission.admission_digest,request.request_digest,request.repository,
                request.target_path,"PREPARED","t0",pre_observation_digest=sha256(b"pre").hexdigest())
            fence.prepare(record)
            self.assertEqual(fence.get(key).state,"PREPARED")
            self.assertEqual(DurableMoonFileWriteFence(db).get(key).state,"PREPARED")
            with self.assertRaises(MoonFileWriteMediationError): DurableMoonFileWriteFence(db).prepare(record)

    def test_fence_forward_only_and_unknown_terminal(self):
        request=_request(); admission=_admission(request); key=moon_file_write_effect_key(request,admission)
        with tempfile.TemporaryDirectory() as td:
            fence=DurableMoonFileWriteFence(str(Path(td)/"f.sqlite3"))
            fence.prepare(MoonFileWriteFenceRecord(key,admission.admission_digest,request.request_digest,request.repository,
                request.target_path,"PREPARED","t0",pre_observation_digest=sha256(b"pre").hexdigest()))
            fence.mark_attempted(key,"t1"); fence.mark_unknown(key)
            self.assertEqual(fence.get(key).state,"UNKNOWN")
            with self.assertRaises(MoonFileWriteMediationError): fence.mark_attempted(key,"t2")


if __name__ == "__main__": unittest.main()
