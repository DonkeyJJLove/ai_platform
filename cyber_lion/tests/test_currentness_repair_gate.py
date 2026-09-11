"""A stale remote baseline must not hide an invalid repair checkout."""
from contextlib import ExitStack
import copy
import json
import subprocess
import unittest
from unittest.mock import patch

from cyber_lion.tests import test_truth_plane_reconciliation as gate


class CurrentnessRepairGateTests(unittest.TestCase):
    def run_repair(self, *, ancestry=0, carriers=None, registry=None,
                   declared=None, invalid_remote=False, invalid_records=False):
        case = gate.TruthPlaneReconciliationTests()
        local = case.state()
        local["baseline"]["subject_digest"] = declared or "b" * 64
        live = copy.deepcopy(local)
        live["baseline"]["subject_digest"] = "a" * 64
        if invalid_remote:
            live["baseline"]["currentness_mode"] = "INVALID"
        if invalid_records:
            live["records"] = []

        def git_run(args, **kwargs):
            if args[1] == "show":
                return subprocess.CompletedProcess(args, 0, json.dumps(live))
            if args[1] == "merge-base":
                return subprocess.CompletedProcess(args, ancestry)
            if args[1] == "diff":
                paths = gate.CARRIER_PATHS if carriers is None else carriers
                return subprocess.CompletedProcess(args, 0, "\n".join(paths))
            raise AssertionError(f"Unexpected command: {args}")

        with ExitStack() as stack:
            for name, result in (("live_identity", ("1" * 40, "2" * 40)),
                                 ("_resolve_live_branch", ("1" * 40, "2" * 40)),
                                 ("state", local)):
                stack.enter_context(patch.object(case, name, return_value=result))
            stack.enter_context(patch.object(
                case, "checkout_subject_digest",
                side_effect=lambda ref: "c" * 64 if ref == "FETCH_HEAD" else "b" * 64))
            stack.enter_context(patch.object(gate.subprocess, "run", side_effect=git_run))
            stack.enter_context(patch.object(
                gate.Path, "read_text", return_value=json.dumps({
                    "generated_from": registry or "truth-subject-v1@" + "b" * 64})))
            case.test_live_master_truth_projection_is_current()

    def test_current_descendant_with_both_rebound_carriers_is_admitted(self):
        self.run_repair()

    def test_invalid_repairs_are_rejected(self):
        cases = (
            ({"ancestry": 1}, "MUST_DESCEND_FROM_LIVE_MASTER"),
            ({"ancestry": 128}, "MUST_DESCEND_FROM_LIVE_MASTER"),
            ({"carriers": {gate.STATE_PATH.as_posix()}}, "REQUIRES_BOTH_TRUTH_CARRIERS"),
            ({"registry": "truth-subject-v1@" + "a" * 64}, "REGISTRY_DRIFT"),
            ({"declared": "d" * 64,
              "registry": "truth-subject-v1@" + "d" * 64}, "CHECKOUT_SUBJECT_DIGEST_DRIFT"),
            ({"invalid_remote": True}, "LIVE_MASTER_FAILURE_IS_NOT_CURRENTNESS_DRIFT"),
            ({"invalid_records": True}, "records must be a non-empty array"),
        )
        for options, error in cases:
            with self.subTest(options=options):
                with self.assertRaisesRegex((AssertionError, gate.TruthProjectionError), error):
                    self.run_repair(**options)
