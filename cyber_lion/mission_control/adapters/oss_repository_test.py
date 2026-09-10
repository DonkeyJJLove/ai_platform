from __future__ import annotations

import re
import uuid
from typing import Any

from ..read_client import SOCKET_PATH, call as read_call


class OssRepositoryTestAdapter:
    adapter_id = "OSS_REPOSITORY_TEST"
    supported_process_classes = ("AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST",)
    TARGET = "pallets/itsdangerous"
    COMMIT = "672971d66a2ef9f85151e53283113f33d642dabd"

    def __init__(self, source_head: str, source_tree: str, read_socket: str = SOCKET_PATH) -> None:
        self.source_head = source_head
        self.source_tree = source_tree
        self.read_socket = read_socket

    def _read(self) -> dict[str, Any]:
        return read_call(
            "READ_OSS_REPO_TEST_EVIDENCE", source_head=self.source_head, source_tree=self.source_tree,
            run_id="lion-mc-oss-read-" + uuid.uuid4().hex[:16], socket_path=self.read_socket,
        )

    @staticmethod
    def _exit_code(evidence: dict[str, Any], name: str) -> int | None:
        for pod in evidence.get("pods") or []:
            for state in pod.get("states") or []:
                if state.get("name") == name and state.get("exit_code") is not None:
                    return int(state["exit_code"])
        return None

    @staticmethod
    def _restarts(evidence: dict[str, Any]) -> int:
        return sum(int(state.get("restart_count") or 0) for pod in evidence.get("pods") or [] for state in pod.get("states") or [])

    def poll(self) -> list[dict[str, Any]]:
        evidence = self._read()
        raw_status = str(evidence.get("status") or "UNKNOWN").upper()
        if raw_status in {"ABSENT", "K3S_NOT_RUNNING"}:
            return []
        status = "RUNNING" if raw_status in {"PENDING", "RUNNING"} else raw_status
        if status not in {"RUNNING", "PASS", "FAIL"}:
            status = "UNKNOWN"
        clone_log = evidence.get("clone_log") or ""
        match = re.search(r"CLONED_HEAD=([0-9a-f]{40})", clone_log)
        cloned_head = match.group(1) if match else None
        pytest_exit = self._exit_code(evidence, "pytest")
        clone_exit = self._exit_code(evidence, "git-clone")
        restarts = self._restarts(evidence)
        pods = evidence.get("pods") or []
        pod_uid = pods[0].get("uid") if pods else None
        states = [state for pod in pods for state in (pod.get("states") or [])]
        image_ids = {state.get("name"): state.get("image_id") for state in states if state.get("name")}
        job_status = evidence.get("job_status") or {}
        verified = (
            status == "PASS" and cloned_head == self.COMMIT and pytest_exit == 0 and clone_exit == 0
            and int(job_status.get("succeeded") or 0) == 1 and int(job_status.get("failed") or 0) == 0
            and restarts == 0 and int(evidence.get("vendor_requests") or 0) == 0
            and bool(evidence.get("pytest_summary")) and bool(pod_uid)
            and bool(image_ids.get("git-clone")) and bool(image_ids.get("pytest"))
        )
        receipt = None
        if evidence.get("receipt_sha256") and evidence.get("receipt_path"):
            receipt = {
                "receipt_id": "oss-read:" + str(evidence["receipt_sha256"]),
                "path": evidence["receipt_path"],
                "sha256": evidence["receipt_sha256"],
                "operation": "READ_OSS_REPO_TEST_EVIDENCE",
                "status": "PASS",
                "timestamp": None,
            }
        return [{
            "run_id": "oss-test-itsdangerous",
            "process_language": "LPCL-1_0",
            "process_class": "AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST",
            "adapter_type": self.adapter_id,
            "status": status,
            "verification_status": "VERIFIED" if verified else "OBSERVED",
            "phase": "PYTEST" if status == "RUNNING" else status,
            "host": "LION-AUTH-LAB",
            "runtime": "K3S",
            "namespace": evidence.get("namespace") or "oss-test-itsdangerous",
            "source": {"repository": "DonkeyJJLove/ai_platform", "head": self.source_head, "tree": self.source_tree},
            "target": {"repository": self.TARGET, "commit": self.COMMIT, "cloned_head": cloned_head},
            "workload": {"kind": "KubernetesJob", "job": evidence.get("job"), "pod_uid": pod_uid, "image_ids": image_ids},
            "authority": {"class": "BOUNDED_PRIVILEGED_ADMISSION", "mission_control": "READ_ONLY"},
            "participants": {},
            "metrics": {
                "pytest_summary": evidence.get("pytest_summary"),
                "pytest_exit_code": pytest_exit,
                "clone_exit_code": clone_exit,
                "pod_restarts": restarts,
                "vendor_requests": int(evidence.get("vendor_requests") or 0),
            },
            "artifacts": [],
            "receipts": [receipt] if receipt else [],
            "cleanup": {},
            "evidence": {"class": "KUBERNETES_RUNTIME", "job_status": job_status, "image_ids": image_ids},
        }]
