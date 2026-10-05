from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.cooperative_runtime_root import CooperativeRuntimeCompositionRoot
from cyber_lion.mission_control.cooperative_artifacts import WRITE_KIND, VERIFY_KIND
from cyber_lion.mission_control.cooperative_worker_runtime import (
    CooperativeWorkerRuntime,
    CooperativeWorkerRuntimeError,
    CooperativeWorkerRuntimeRegistry,
)


MARKER = {
    "state": "READY",
    "provider_id": "COOPERATIVE_RUNTIME_WRITER_R5",
    "context_resolver": "PINNED_COOPERATIVE_CONTEXT_RESOLVER",
    "execution_engine": "RUNTIME_EXECUTION_ENGINE",
    "authority_effect": "NONE",
}


class CooperativeWorkerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.artifacts = self.base / "artifacts"
        self.verifier = self.base / "verifier"
        self.artifacts.mkdir()
        self.verifier.mkdir()
        self.writer = object()
        self.root = object.__new__(CooperativeRuntimeCompositionRoot)
        self.root.artifact_root = self.artifacts
        self.root.now_fn = lambda: __import__("datetime").datetime(
            2026, 10, 5, 12, 0, tzinfo=__import__("datetime").timezone.utc
        )
        self.root.worker_status_marker = lambda: dict(MARKER)
        self.root.writer_for_assignment = lambda aid: self.writer
        self.root.verifier_workspace = lambda aid: self.verifier
        self.runtime = CooperativeWorkerRuntime(self.root, material_worker_id="MD001")

    @staticmethod
    def row(kind, aid="assignment-1"):
        return {
            "assignment_id": aid,
            "material_drone_id": "MD001",
            "input": {"kind": kind},
        }

    def test_status_marker_is_exact_and_non_authorizing(self):
        self.assertEqual(self.runtime.status_marker(), MARKER)

    def test_write_assignment_routes_to_bound_writer_and_artifact_root(self):
        with patch(
            "cyber_lion.mission_control.cooperative_worker_runtime.cooperative_assignment_once",
            return_value={"receipt_id": "r1"},
        ) as call:
            out = self.runtime.process_once(lambda *_: {}, [self.row(WRITE_KIND)])
        self.assertEqual(out, {"receipt_id": "r1"})
        kwargs = call.call_args.kwargs
        self.assertEqual(kwargs["material_drone_id"], "MD001")
        self.assertEqual(kwargs["artifact_root"], self.artifacts)
        self.assertIs(kwargs["admitted_writer"], self.writer)
        self.assertEqual(kwargs["pending"], [self.row(WRITE_KIND)])

    def test_verify_assignment_routes_to_private_verifier_workspace(self):
        row = self.row(VERIFY_KIND, "verify-assignment-1")
        with patch(
            "cyber_lion.mission_control.cooperative_worker_runtime.cooperative_assignment_once",
            return_value={"receipt_id": "r2"},
        ) as call:
            out = self.runtime.process_once(lambda *_: {}, [row])
        self.assertEqual(out, {"receipt_id": "r2"})
        kwargs = call.call_args.kwargs
        self.assertEqual(kwargs["artifact_root"], self.verifier)
        self.assertIsNone(kwargs["admitted_writer"])
        self.assertEqual(kwargs["pending"], [row])

    def test_other_worker_or_other_kind_is_not_claimed(self):
        self.assertIsNone(self.runtime.process_once(lambda *_: (_ for _ in ()).throw(AssertionError()), [
            {"assignment_id": "a", "material_drone_id": "MD002", "input": {"kind": WRITE_KIND}},
            {"assignment_id": "b", "material_drone_id": "MD001", "input": {"kind": "LOCAL_MODEL_INFERENCE"}},
        ]))

    def test_registry_is_exactly_once_and_unbound_is_explicit(self):
        registry = CooperativeWorkerRuntimeRegistry()
        self.assertIsNone(registry.current("MD001"))
        self.assertEqual(registry.status()["state"], "NOT_BOUND")
        registry.install(self.root)
        self.assertIsInstance(registry.current("MD001"), CooperativeWorkerRuntime)
        self.assertEqual(registry.status()["state"], "READY")
        with self.assertRaisesRegex(CooperativeWorkerRuntimeError, "already installed"):
            registry.install(self.root)

    def test_worker_source_checks_registry_before_cooperative_assignment(self):
        worker = (
            Path(__file__).resolve().parents[2]
            / "LION/runtime_compat/r24/docker-autonomy/worker.py"
        ).read_text(encoding="utf-8")
        self.assertIn("PROCESS_COOPERATIVE_RUNTIME.current(WORKER_ID)", worker)
        self.assertIn('operation="COOPERATIVE_ASSIGNMENT"', worker)
        self.assertIn("cooperative_runtime.process_once(", worker)
        self.assertIn('"cooperative_runtime_provider": (', worker)


if __name__ == "__main__":
    unittest.main()
