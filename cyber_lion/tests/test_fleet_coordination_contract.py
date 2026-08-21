from __future__ import annotations

import dataclasses
import unittest

from cyber_lion.contracts.fleet_coordination import (
    FleetCoordinationContractError,
    FleetCoordinationSpec,
    FleetDispatch,
    FleetPlanRequest,
)

BASE="a"*40; TREE="b"*40

def spec(**overrides):
    v=dict(mission_id="mission-a",drone_id="drone-a",repository="DonkeyJJLove/ai_platform",baseline_sha=BASE,baseline_tree_sha=TREE,branch="mission/f005-b-a",write_scope=("cyber_lion/example.py",),dependencies=(),evidence_refs=("authority:F005-B",)); v.update(overrides); return FleetCoordinationSpec(**v)

def request(**overrides):
    v=dict(request_id="plan-1",coordinator_id="coordinator-1",current_heads=(("DonkeyJJLove/ai_platform",BASE),),max_parallel=2); v.update(overrides); return FleetPlanRequest(**v)

class FleetCoordinationContractTests(unittest.TestCase):
    def test_spec_immutable_and_digest_deterministic(self):
        x=spec().validate(); self.assertEqual(x.digest(),spec().digest()); self.assertEqual(len(x.digest()),64)
        with self.assertRaises(dataclasses.FrozenInstanceError): x.mission_id="other"  # type: ignore[misc]
    def test_write_scope_canonical(self):
        for bad in (("../escape",),("/absolute",),("cyber_lion//x.py",),("cyber_lion/./x.py",),("cyber_lion/**",),("cyber_lion\\x.py",)):
            with self.subTest(bad=bad), self.assertRaises(FleetCoordinationContractError): spec(write_scope=bad).validate()
    def test_dependency_and_git_identity_validation(self):
        with self.assertRaises(FleetCoordinationContractError): spec(dependencies=("dep","dep")).validate()
        with self.assertRaises(FleetCoordinationContractError): spec(dependencies=("mission-a",)).validate()
        with self.assertRaises(FleetCoordinationContractError): spec(baseline_sha="A"*40).validate()
        with self.assertRaises(FleetCoordinationContractError): spec(branch="refs/heads/a").validate()
    def test_plan_request_constraints(self):
        self.assertEqual(request().head_map(),{"DonkeyJJLove/ai_platform":BASE})
        with self.assertRaises(FleetCoordinationContractError): request(current_heads=(("DonkeyJJLove/ai_platform",BASE),("DonkeyJJLove/ai_platform",BASE))).validate()
        with self.assertRaises(FleetCoordinationContractError): request(max_parallel=101).validate()
    def test_dispatch_exact_binding(self):
        s=spec().validate(); p=request().validate(); d=FleetDispatch("1"*64,"2"*64,p.request_id,p.coordinator_id,s.mission_id,s.drone_id,1,s.repository,s.baseline_sha,s.baseline_tree_sha,s.branch,s.write_scope,"2026-08-21T14:00:00+00:00")
        d.validate_for(s,p)
        with self.assertRaises(FleetCoordinationContractError): dataclasses.replace(d,baseline_tree_sha="c"*40).validate_for(s,p)

if __name__=="__main__": unittest.main()
