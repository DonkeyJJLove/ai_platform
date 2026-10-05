"""Source-pinned worker injection seam for cooperative artifact assignments.

This module does not construct authority, RuntimeAdmission, provisioning or currentness.
It accepts only an exact CooperativeRuntimeCompositionRoot installed by the trusted
process composition. Without such a root, cooperative assignments are not claimed.
"""
from __future__ import annotations

from threading import RLock
import re
from typing import Any, Mapping

from cyber_lion.enterprise.cooperative_runtime_root import CooperativeRuntimeCompositionRoot
from cyber_lion.mission_control.cooperative_artifacts import WRITE_KIND, VERIFY_KIND
from tools.lion_cooperative_worker_adapter import assignment_input, cooperative_assignment_once

_WORKER = re.compile(r"^MD[0-9]{3}$")


class CooperativeWorkerRuntimeError(RuntimeError):
    pass


class CooperativeWorkerRuntime:
    def __init__(self, root: CooperativeRuntimeCompositionRoot, *, material_worker_id: str):
        if type(root) is not CooperativeRuntimeCompositionRoot:
            raise CooperativeWorkerRuntimeError("exact cooperative runtime root required")
        if type(material_worker_id) is not str or _WORKER.fullmatch(material_worker_id) is None:
            raise CooperativeWorkerRuntimeError("material worker identity")
        self.root = root
        self.material_worker_id = material_worker_id

    def status_marker(self) -> dict[str, Any]:
        marker = self.root.worker_status_marker()
        if type(marker) is not dict or marker != {
            "state": "READY",
            "provider_id": "COOPERATIVE_RUNTIME_WRITER_R5",
            "context_resolver": "PINNED_COOPERATIVE_CONTEXT_RESOLVER",
            "execution_engine": "RUNTIME_EXECUTION_ENGINE",
            "authority_effect": "NONE",
        }:
            raise CooperativeWorkerRuntimeError("cooperative provider marker mismatch")
        return dict(marker)

    def process_once(self, control, pending: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]):
        if not callable(control) or type(pending) not in {list, tuple}:
            raise CooperativeWorkerRuntimeError("worker control/pending")
        for row in pending:
            if not isinstance(row, Mapping) or row.get("material_drone_id") != self.material_worker_id:
                continue
            try:
                payload = assignment_input(row)
            except Exception:
                continue
            kind = payload.get("kind")
            if kind not in {WRITE_KIND, VERIFY_KIND}:
                continue
            assignment_id = row.get("assignment_id")
            if type(assignment_id) is not str or not assignment_id:
                continue
            if kind == WRITE_KIND:
                writer = self.root.writer_for_assignment(assignment_id)
                artifact_root = self.root.artifact_root
            else:
                writer = None
                artifact_root = self.root.verifier_workspace(assignment_id)
            return cooperative_assignment_once(
                control,
                material_drone_id=self.material_worker_id,
                artifact_root=artifact_root,
                pending=[row],
                admitted_writer=writer,
                now_fn=self.root.now_fn,
            )
        return None


class CooperativeWorkerRuntimeRegistry:
    """Exactly-once process binding. Registry state is not authority."""

    def __init__(self):
        self._lock = RLock()
        self._root: CooperativeRuntimeCompositionRoot | None = None

    def install(self, root: CooperativeRuntimeCompositionRoot) -> CooperativeRuntimeCompositionRoot:
        if type(root) is not CooperativeRuntimeCompositionRoot:
            raise CooperativeWorkerRuntimeError("exact cooperative runtime root required")
        with self._lock:
            if self._root is not None:
                raise CooperativeWorkerRuntimeError("cooperative runtime root already installed")
            self._root = root
        return root

    def current(self, material_worker_id: str) -> CooperativeWorkerRuntime | None:
        with self._lock:
            root = self._root
        if root is None:
            return None
        return CooperativeWorkerRuntime(root, material_worker_id=material_worker_id)

    def status(self) -> dict[str, Any]:
        with self._lock:
            root = self._root
        return {
            "state": "READY" if root is not None else "NOT_BOUND",
            "provider_id": "COOPERATIVE_RUNTIME_WRITER_R5",
            "authority_effect": "NONE",
        }


PROCESS_COOPERATIVE_RUNTIME = CooperativeWorkerRuntimeRegistry()
