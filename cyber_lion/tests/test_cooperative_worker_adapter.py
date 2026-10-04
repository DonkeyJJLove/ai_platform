from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from tools.lion_cooperative_worker_adapter import cooperative_assignment_once as consume_assignment
from cyber_lion.mission_control.cooperative_artifacts import materialize_text


def fixture_admitted_writer(*, claimed, payload, artifact_root, worker_id):
    """Isolated transport fixture, NOT a real runtime admission or receipt."""
    return {**materialize_text(artifact_root, payload, worker_id=worker_id),
            "effect_receipt_digest": "f" * 64}


def cooperative_assignment_once(*args, **kwargs):
    return consume_assignment(*args, admitted_writer=fixture_admitted_writer, **kwargs)
from cyber_lion.mission_control.cooperative_artifacts import WRITE_KIND, VERIFY_KIND


class Control:
    def __init__(self, rows):
        self.rows = {r["assignment_id"]: dict(r) for r in rows}
        self.calls = []
        self.receipts = []

    def __call__(self, op, args):
        self.calls.append((op, dict(args)))
        if op == "local_assignment_claim":
            row = dict(self.rows[args["assignment_id"]])
            row["lease_generation"] = row.get("lease_generation", 1)
            row["state"] = "CLAIMED"
            row["lease_expires_at"] = "2099-01-01T00:00:00Z"
            return row
        if op == "local_assignment_receipt":
            self.receipts.append(dict(args))
            return {"receipt_id": "receipt-" + args["assignment_id"], **args}
        raise AssertionError(op)


class CooperativeWorkerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mission = "LION-COOPERATIVE-PRODUCTION-PILOT-R1"
        self.content = "artifact from local model\n"
        self.digest = sha256(self.content.encode()).hexdigest()

    def write_row(self):
        payload = {
            "kind": WRITE_KIND,
            "mission_id": self.mission,
            "assignment_id": "assignment-write-1",
            "generation": 1,
            "artifact_name": "pilot.txt",
            "content": self.content,
            "expected_sha256": self.digest,
            "producer_model_call_id": "modelcall-0123456789abcdef",
            "parent_response_digest": "a" * 64,
        }
        return {
            "assignment_id": "assignment-write-1",
            "mission_id": self.mission,
            "material_drone_id": "MD001",
            "lease_generation": 1,
            "input": payload,
        }

    def verify_row(self):
        payload = {
            "kind": VERIFY_KIND,
            "mission_id": self.mission,
            "source_assignment_id": "assignment-write-1",
            "generation": 1,
            "artifact_name": "pilot.txt",
            "expected_sha256": self.digest,
            "expected_producer_worker_id": "MD001",
        }
        return {
            "assignment_id": "assignment-verify-1",
            "mission_id": self.mission,
            "material_drone_id": "MD002",
            "lease_generation": 1,
            "input": payload,
        }

    def test_write_assignment_claims_and_receipts(self):
        row = self.write_row()
        control = Control([row])
        out = cooperative_assignment_once(control, material_drone_id="MD001", artifact_root=self.root, pending=[row])
        self.assertEqual(out["status"], "PASS")
        self.assertTrue((self.root / self.mission / "g00000001" / "pilot.txt").is_file())
        self.assertEqual(control.receipts[0]["result"]["artifact_sha256"], self.digest)

    def test_verify_assignment_by_second_worker(self):
        write = self.write_row()
        c1 = Control([write])
        cooperative_assignment_once(c1, material_drone_id="MD001", artifact_root=self.root, pending=[write])
        verify = self.verify_row()
        c2 = Control([verify])
        out = cooperative_assignment_once(c2, material_drone_id="MD002", artifact_root=self.root, pending=[verify])
        self.assertEqual(out["status"], "PASS")
        self.assertTrue(c2.receipts[0]["result"]["digest_match"])

    def test_other_worker_does_not_claim(self):
        row = self.write_row()
        control = Control([row])
        self.assertIsNone(cooperative_assignment_once(control, material_drone_id="MD002", artifact_root=self.root, pending=[row]))
        self.assertEqual(control.calls, [])

    def test_wrong_digest_returns_fail_receipt(self):
        row = self.write_row()
        row["input"]["expected_sha256"] = "b" * 64
        control = Control([row])
        out = cooperative_assignment_once(control, material_drone_id="MD001", artifact_root=self.root, pending=[row])
        self.assertEqual(out["status"], "FAIL")
        self.assertIn("payload digest mismatch", out["result"]["error"])

    def test_unrelated_assignment_ignored(self):
        row = self.write_row()
        row["input"]["kind"] = "LOCAL_MODEL_INFERENCE"
        control = Control([row])
        self.assertIsNone(cooperative_assignment_once(control, material_drone_id="MD001", artifact_root=self.root, pending=[row]))


if __name__ == "__main__":
    unittest.main()
