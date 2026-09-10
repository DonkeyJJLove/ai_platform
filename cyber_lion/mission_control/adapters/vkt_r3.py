from __future__ import annotations

import uuid
from typing import Any

from ..read_client import SOCKET_PATH, call as read_call


class VktR3Adapter:
    adapter_id = "VKT_R3"
    supported_process_classes = ("LOCAL_SUPERVISED_RUNTIME_TEST", "VKT_R3_384_DRONE_TEST")

    def __init__(self, source_head: str, source_tree: str, read_socket: str = SOCKET_PATH) -> None:
        self.source_head = source_head
        self.source_tree = source_tree
        self.read_socket = read_socket

    def _read(self) -> dict[str, Any]:
        return read_call(
            "READ_POD_EVIDENCE", source_head=self.source_head, source_tree=self.source_tree,
            run_id="lion-mc-vkt-read-" + uuid.uuid4().hex[:16], socket_path=self.read_socket,
        )

    def poll(self) -> list[dict[str, Any]]:
        evidence = self._read()
        router = evidence.get("router_state") or {}
        mission = router.get("mission") or {}
        materialized = int(evidence.get("materialized") or 0)
        if materialized == 0 and not mission:
            return []
        complete = bool(mission.get("completed")) or str(mission.get("phase") or "").upper() == "COMPLETE"
        metrics = {
            "pods": materialized,
            "ready": int(evidence.get("ready") or 0),
            "uids": int(evidence.get("unique_uid_count") or 0),
            "restarts": int(evidence.get("restart_count_total") or 0),
            "fresh_drones": int(router.get("fresh_count") or 0),
            "cases": int(router.get("cases_seen") or 0),
            "proven": int(router.get("cases_proven") or 0),
            "messages": int(router.get("messages_total") or 0),
            "ack_rate": float(router.get("ack_rate") or 0.0),
            "orphans": int(router.get("orphans") or 0),
            "duplicates": int(router.get("duplicates") or 0),
            "vendor_requests": int(evidence.get("vendor_requests") or 0),
        }
        verified = (
            complete and materialized == 384 and metrics["ready"] == 384 and metrics["uids"] == 384
            and metrics["restarts"] == 0 and metrics["fresh_drones"] == 384 and metrics["proven"] == 36
            and metrics["messages"] == 768 and metrics["ack_rate"] == 1.0 and metrics["orphans"] == 0
            and metrics["duplicates"] == 0 and metrics["vendor_requests"] == 0
        )
        status = "PASS" if verified else "RUNNING"
        verification = "VERIFIED" if verified else "OBSERVED"
        receipt = None
        if evidence.get("receipt_sha256") and evidence.get("receipt_path"):
            receipt = {
                "receipt_id": "vkt-read:" + str(evidence["receipt_sha256"]),
                "path": evidence["receipt_path"],
                "sha256": evidence["receipt_sha256"],
                "operation": "READ_POD_EVIDENCE",
                "status": "PASS",
                "timestamp": None,
            }
        return [{
            "run_id": "vkt-r3-live",
            "process_language": "LPCL-1_0",
            "process_class": "VKT_R3_384_DRONE_TEST",
            "adapter_type": self.adapter_id,
            "status": status,
            "verification_status": verification,
            "phase": mission.get("phase") or "RUNTIME",
            "host": "LION-AUTH-LAB",
            "runtime": "K3S",
            "namespace": "vkt-r3",
            "source": {"repository": "DonkeyJJLove/ai_platform", "head": self.source_head, "tree": self.source_tree},
            "target": {"kind": "VKT_R3_384_DRONE_FLEET"},
            "workload": {"kind": "KubernetesFleet", "pods": materialized},
            "authority": {"class": "BOUNDED_PRIVILEGED_ADMISSION", "mission_control": "READ_ONLY"},
            "participants": router.get("participants") or {},
            "metrics": metrics,
            "artifacts": [],
            "receipts": [receipt] if receipt else [],
            "cleanup": {},
            "evidence": {"class": "KUBERNETES_RUNTIME", "uid_set": evidence.get("pod_uid_set_sha256")},
        }]
