from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.moon_file_write import MoonFileWriteRequest
from cyber_lion.enterprise.moon_file_write import ExactMoonFileWriteEffectProvider
from cyber_lion.enterprise.moon_file_write_mediation import (
    CanonicalMoonFileWriteAdmission, DurableMoonFileWriteFence, MoonFileWriteFenceRecord,
    MoonFileWriteMediationError, moon_file_write_effect_key,
)


def request():
    return MoonFileWriteRequest("1.0.0","effect-1","DonkeyJJLove/ai_platform",144,"DonkeyJJLove","lion-moon-r9d8-test",
        "/home/d2j3/effect-unit.txt","CREATE_ONLY","ABSENT",None,sha256(b"AAAA").hexdigest(),4,sha256(b"event").hexdigest()).sealed()


def admission(r):
    return CanonicalMoonFileWriteAdmission(r.request_digest,r.repository,r.control_issue,r.actor_login,r.runner_name,r.target_path,
        r.operation_mode,r.expected_previous_state,r.expected_previous_sha256,r.intended_content_sha256,r.intended_content_size,
        r.source_event_digest,sha256(b"auth").hexdigest(),sha256(b"pdp").hexdigest(),0,"provider").sealed()


class MoonFileWriteEffectTests(unittest.TestCase):
    def test_provider_requires_attempted_fence_before_any_host_effect(self):
        r=request(); a=admission(r); key=moon_file_write_effect_key(r,a)
        with tempfile.TemporaryDirectory() as td:
            f=DurableMoonFileWriteFence(str(Path(td)/"f.sqlite3"))
            f.prepare(MoonFileWriteFenceRecord(key,a.admission_digest,r.request_digest,r.repository,r.target_path,"PREPARED","t0",pre_observation_digest=sha256(b"pre").hexdigest()))
            p=ExactMoonFileWriteEffectProvider(content=b"AAAA",fence=f)
            with self.assertRaisesRegex(MoonFileWriteMediationError,"ATTEMPTED"):
                p.write_exact(r,a)

    def test_content_substitution_denied_before_filesystem(self):
        r=request(); a=admission(r)
        with tempfile.TemporaryDirectory() as td:
            f=DurableMoonFileWriteFence(str(Path(td)/"f.sqlite3")); p=ExactMoonFileWriteEffectProvider(content=b"BBBB",fence=f)
            with self.assertRaisesRegex(MoonFileWriteMediationError,"content substitution"):
                p.write_exact(r,a)

    def test_effect_public_surface_has_no_arbitrary_path_or_content_argument(self):
        import inspect
        params=list(inspect.signature(ExactMoonFileWriteEffectProvider.write_exact).parameters)
        self.assertEqual(params,["self","request","admission"])


if __name__ == "__main__": unittest.main()
