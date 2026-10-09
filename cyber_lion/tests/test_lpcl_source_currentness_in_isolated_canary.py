"""R4 LPCL syntax must be observable when isolated MAT04 is absent.

Source currentness remains a mandatory, independent registration gate.
"""
from __future__ import annotations
import unittest

from tools.lion_local_intelligence_runtime import LpclControlBridge


SOURCE = """PROJECT=LION_EVOLUSION
MODE=AUTONOMOUS_EXECUTE
CONTROL_LANGUAGE=LPCL/1.2
MISSION_ID=CANARY-SOURCE-NOT-LIVE-R1
MISSION_TITLE=Deterministic canary syntax test
MISSION_OBJECTIVE=Compile source-only LPCL without material effects
MISSION_DESCRIPTION=No GitHub MAT04 worker is provisioned in canary
LOGICAL_DRONE_COUNT=8
MATERIAL_DRONE_COUNT=32
MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL
PROTOCOLS=LPCL,AUTHORITY,CURRENTNESS,EVIDENCE
PHASE_01=VALIDATE|Syntax only
PHASE_01_EXECUTION_CLASS=VERIFY
PHASE_01_CAPABILITY_CLASS=CONTROL_PLANE_RECONNAISSANCE
PHASE_01_EFFECT_CEILING=NONE
PHASE_01_BINDING_MODE=DYNAMIC
PHASE_01_ON_MISSING_CAPABILITY=WAIT_AND_DISCOVER
PHASE_01_AUTO_RESUME=FALSE
PHASE_01_VERIFY_BEFORE_MUTATE=TRUE
PHASE_01_CURRENTNESS=EXACT_SOURCE
PHASE_01_EVIDENCE=VERIFIED_DIGEST
PHASE_01_COMPLETION_01=SYNTAX=PASS
"""


class CurrentnessBroker:
    def __init__(self, *, mat04_live: bool, payload=None, failure=None):
        self.mat04_live = mat04_live
        self.payload = payload if payload is not None else {"head":"a"*40,"tree":"b"*40}
        self.failure = failure
        self.calls = []
    def fleet_state(self):
        return {"rows":[{"drone_id":"MAT04","live":self.mat04_live}]}
    def call(self, drone, operation, args):
        self.calls.append((drone,operation))
        if self.failure:
            raise self.failure
        return {"result":self.payload}


def bridge(broker):
    r=LpclControlBridge(broker)
    r._get=lambda *a,**kw: {
        "schema":"lion.capability.registry/v1",
        "capabilities":{},
        "registry_digest":"c"*64,
    }
    return r


class CanaryLpclCurrentnessTests(unittest.TestCase):
    def test_no_material_drone_compiles_syntax_without_dispatch(self):
        mat=CurrentnessBroker(mat04_live=False)
        c=bridge(mat)
        d=c.validate(SOURCE)
        self.assertTrue(d["valid"])
        self.assertEqual(len(d["spec"]["phases"]),1)
        self.assertEqual(d["source_currentness"]["verification"],"UNVERIFIED")
        self.assertIsNone(d["spec"]["source_head"])
        self.assertIsNone(d["spec"]["source_tree"])
        self.assertEqual(mat.calls, [])
        c._post=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("NO_REGISTER"))
        with self.assertRaisesRegex(ValueError,"LPCL_SOURCE_CURRENTNESS_REQUIRED"):
            c("register_lpcl",{"lpcl_text":SOURCE})

    def test_live_receipt_preserves_source_digest_and_supports_registration(self):
        mat=CurrentnessBroker(mat04_live=True)
        c=bridge(mat)
        result=c.validate(SOURCE)
        self.assertEqual(result["source_currentness"]["verification"],"VERIFIED")
        self.assertEqual(result["source_currentness"]["provider"],"MAT04")
        self.assertEqual(result["spec"]["source_head"],"a"*40)
        self.assertEqual(result["spec"]["source_tree"],"b"*40)
        self.assertEqual(mat.calls,[("MAT04","github_branch")])
        def post(path,spec,timeout=10):
            self.assertEqual(path,"/api/v3/missions/register-lpcl")
            self.assertEqual(spec["source_head"],"a"*40)
            return {"mission":{"mission_id":spec["mission_id"],"spec_digest":spec["lpcl_digest"]}}
        c._post=post
        out=c("register_lpcl",{"lpcl_text":SOURCE})
        self.assertEqual(out["registration_confirmation"]["mission_id"],"CANARY-SOURCE-NOT-LIVE-R1")

    def test_mat04_failed_or_malformed_denies_registration(self):
        for mat in (
            CurrentnessBroker(mat04_live=True,failure=TimeoutError("fixture timeout")),
            CurrentnessBroker(mat04_live=True,payload={"head":"0"*40,"tree":"WRONG"}),
        ):
            with self.subTest(mat=mat):
                c=bridge(mat)
                self.assertEqual(c.validate(SOURCE)["source_currentness"]["verification"],"UNVERIFIED")
                c._post=lambda *args,**kw: (_ for _ in ()).throw(AssertionError("WRITE_WITHOUT_VERIFIED_SOURCE"))
                with self.assertRaisesRegex(ValueError,"LPCL_SOURCE_CURRENTNESS_REQUIRED"):
                    c("register_lpcl",{"lpcl_text":SOURCE})


if __name__ == "__main__":
    unittest.main()
