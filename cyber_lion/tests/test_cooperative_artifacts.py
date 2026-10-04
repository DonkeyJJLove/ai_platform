from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cyber_lion.mission_control.cooperative_artifacts import (
    CooperativeArtifactError,
    WRITE_KIND,
    VERIFY_KIND,
    artifact_path,
    materialize_text,
    verify_text,
)


class CooperativeArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mission = "LION-COOPERATIVE-PRODUCTION-PILOT-R1"
        self.assignment = "assignment-write-001"
        self.content = "cooperative production artifact\n"
        self.digest = sha256(self.content.encode("utf-8")).hexdigest()

    def write_payload(self, **kw):
        value = {
            "kind": WRITE_KIND,
            "mission_id": self.mission,
            "assignment_id": self.assignment,
            "generation": 1,
            "artifact_name": "pilot.txt",
            "content": self.content,
            "expected_sha256": self.digest,
            "producer_model_call_id": "modelcall-0123456789abcdef",
            "parent_response_digest": "a" * 64,
        }
        value.update(kw)
        return value

    def verify_payload(self, **kw):
        value = {
            "kind": VERIFY_KIND,
            "mission_id": self.mission,
            "source_assignment_id": self.assignment,
            "generation": 1,
            "artifact_name": "pilot.txt",
            "expected_sha256": self.digest,
            "expected_producer_worker_id": "MD001",
        }
        value.update(kw)
        return value

    def test_write_and_readback(self):
        out = materialize_text(self.root, self.write_payload(), worker_id="MD001")
        self.assertTrue(out["readback_match"])
        self.assertEqual(out["artifact_sha256"], self.digest)
        self.assertEqual(Path(out["artifact_path"]).read_text(encoding="utf-8"), self.content)

    def test_verify_by_different_worker(self):
        materialize_text(self.root, self.write_payload(), worker_id="MD001")
        out = verify_text(self.root, self.verify_payload(), worker_id="MD002")
        self.assertTrue(out["digest_match"])
        self.assertEqual(out["verifier_worker_id"], "MD002")

    def test_same_worker_cannot_self_verify(self):
        materialize_text(self.root, self.write_payload(), worker_id="MD001")
        with self.assertRaises(CooperativeArtifactError):
            verify_text(self.root, self.verify_payload(), worker_id="MD001")

    def test_wrong_write_digest_rejected_before_effect(self):
        with self.assertRaises(CooperativeArtifactError):
            materialize_text(self.root, self.write_payload(expected_sha256="b" * 64), worker_id="MD001")
        self.assertFalse(artifact_path(self.root, mission_id=self.mission, generation=1, artifact_name="pilot.txt").exists())

    def test_wrong_verify_digest_rejected(self):
        materialize_text(self.root, self.write_payload(), worker_id="MD001")
        with self.assertRaises(CooperativeArtifactError):
            verify_text(self.root, self.verify_payload(expected_sha256="b" * 64), worker_id="MD002")

    def test_second_write_does_not_overwrite(self):
        materialize_text(self.root, self.write_payload(), worker_id="MD001")
        with self.assertRaises(CooperativeArtifactError):
            materialize_text(self.root, self.write_payload(), worker_id="MD001")
        self.assertEqual(artifact_path(self.root, mission_id=self.mission, generation=1, artifact_name="pilot.txt").read_text(), self.content)

    def test_generation_isolated(self):
        materialize_text(self.root, self.write_payload(generation=1), worker_id="MD001")
        second = dict(self.write_payload(generation=2))
        materialize_text(self.root, second, worker_id="MD001")
        self.assertNotEqual(
            artifact_path(self.root, mission_id=self.mission, generation=1, artifact_name="pilot.txt"),
            artifact_path(self.root, mission_id=self.mission, generation=2, artifact_name="pilot.txt"),
        )

    def test_path_traversal_rejected(self):
        for name in ("../x", "a/b", "..", "."):
            with self.subTest(name=name), self.assertRaises(CooperativeArtifactError):
                materialize_text(self.root, self.write_payload(artifact_name=name), worker_id="MD001")

    def test_empty_content_rejected(self):
        with self.assertRaises(CooperativeArtifactError):
            materialize_text(
                self.root,
                self.write_payload(content="", expected_sha256=sha256(b"").hexdigest()),
                worker_id="MD001",
            )

    def test_oversize_rejected(self):
        content = "x" * 131073
        with self.assertRaises(CooperativeArtifactError):
            materialize_text(
                self.root,
                self.write_payload(content=content, expected_sha256=sha256(content.encode()).hexdigest()),
                worker_id="MD001",
            )

    def test_symlink_root_rejected(self):
        real = self.root / "real"
        real.mkdir()
        link = self.root / "link"
        link.symlink_to(real, target_is_directory=True)
        with self.assertRaises(CooperativeArtifactError):
            materialize_text(link, self.write_payload(), worker_id="MD001")


if __name__ == "__main__":
    unittest.main()
