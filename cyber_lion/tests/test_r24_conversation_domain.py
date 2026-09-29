from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from cyber_lion.app_coordination.conversation_domain import ConversationConflict
from cyber_lion.app_coordination.local_intelligence_gateway import make_handler
from tools.lion_local_intelligence_runtime import ThreadStore


class R24ConversationDomainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "threads.db"
        self.store = ThreadStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def op(self, op, args=None):
        return self.store("conversation_" + op, args or {})

    def test_create_unbound_and_mission_bound_list_get(self):
        a = self.op("create", {"title": "A", "idempotency_key": "create-a"})
        b = self.op("create", {"title": "B", "mission_id": "M1", "idempotency_key": "create-b"})
        self.assertEqual(a["state"], "UNBOUND")
        self.assertIsNone(a["current_binding"]["mission_id"])
        self.assertEqual(a["current_binding"]["binding_epoch"], 1)
        self.assertEqual(b["state"], "BOUND")
        self.assertEqual(b["current_binding"]["mission_id"], "M1")
        listed = self.op("list")
        self.assertEqual(
            {x["conversation_id"] for x in listed["conversations"]},
            {a["conversation_id"], b["conversation_id"]},
        )
        got = self.op("get", {"conversation_id": b["conversation_id"]})
        self.assertEqual(got["conversation_id"], b["conversation_id"])
        self.assertEqual(got["authority_effect"], "NONE")

    def test_bind_and_detach_create_successors_and_freeze_predecessors(self):
        root = self.op("create", {"title": "A", "idempotency_key": "root"})
        bound = self.op("bind", {
            "conversation_id": root["conversation_id"],
            "transition": {"mission_id": "M1", "operation_id": "bind-1"},
        })
        root_after = self.op("get", {"conversation_id": root["conversation_id"]})
        self.assertEqual(root_after["state"], "FROZEN")
        self.assertEqual(root_after["current_binding"]["state"], "FROZEN")
        self.assertEqual(bound["state"], "BOUND")
        self.assertEqual(bound["current_binding"]["binding_epoch"], 2)
        self.assertEqual(bound["current_binding"]["mission_id"], "M1")
        detached = self.op("detach", {
            "conversation_id": bound["conversation_id"],
            "transition": {"operation_id": "detach-1"},
        })
        self.assertEqual(detached["state"], "UNBOUND")
        self.assertEqual(detached["current_binding"]["binding_epoch"], 3)
        self.assertIsNone(detached["current_binding"]["mission_id"])
        self.assertNotEqual(root["conversation_id"], bound["conversation_id"])
        self.assertNotEqual(bound["conversation_id"], detached["conversation_id"])
        chain = self.op("lineage", {"conversation_id": detached["conversation_id"]})
        self.assertEqual(
            [x["transition"] for x in chain["ancestors"]],
            ["DETACH", "BIND", "CREATE"],
        )

    def test_transition_idempotency_is_exact_and_conflicting_reuse_is_denied(self):
        root = self.op("create", {"idempotency_key": "root-idem"})
        args = {
            "conversation_id": root["conversation_id"],
            "transition": {"mission_id": "M1", "operation_id": "same-op"},
        }
        first = self.op("bind", args)
        second = self.op("bind", args)
        self.assertEqual(first["conversation_id"], second["conversation_id"])
        self.assertTrue(second["idempotent_replay"])
        with self.assertRaises(ConversationConflict):
            self.op("bind", {
                "conversation_id": root["conversation_id"],
                "transition": {"mission_id": "M2", "operation_id": "different-op"},
            })

    def test_create_idempotency_conflict_does_not_duplicate(self):
        first = self.op("create", {"title": "A", "idempotency_key": "create-same"})
        second = self.op("create", {"title": "A", "idempotency_key": "create-same"})
        self.assertEqual(first["conversation_id"], second["conversation_id"])
        self.assertTrue(second["idempotent_replay"])
        with self.assertRaises(ConversationConflict):
            self.op("create", {"title": "DIFFERENT", "idempotency_key": "create-same"})
        self.assertEqual(len(self.op("list")["conversations"]), 1)

    def test_lane_and_external_bridge_are_explicit_and_idempotent(self):
        conv = self.op("create", {"mission_id": "M1", "idempotency_key": "lane-root"})
        digest = conv["current_binding"]["context_digest"]
        lane = {
            "lane_id": "saas-primary",
            "provider": "SAAS",
            "provider_session_ref": "provider-session-saas-1",
            "state": "ACTIVE",
            "context_digest": digest,
        }
        first_lane = self.op("lane_create", {"conversation_id": conv["conversation_id"], "lane": lane})
        second_lane = self.op("lane_create", {"conversation_id": conv["conversation_id"], "lane": lane})
        self.assertFalse(first_lane["idempotent_replay"])
        self.assertTrue(second_lane["idempotent_replay"])
        bridge = {
            "external_thread_ref": "native-saas-thread-1",
            "external_system": "CHATGPT_SAAS",
            "context_snapshot_digest": digest,
            "provenance": {"source": "explicit-test"},
        }
        first_bridge = self.op("bridge_create", {"conversation_id": conv["conversation_id"], "bridge": bridge})
        second_bridge = self.op("bridge_create", {"conversation_id": conv["conversation_id"], "bridge": bridge})
        self.assertEqual(first_bridge["bridge_id"], second_bridge["bridge_id"])
        self.assertEqual(first_bridge["authority_effect"], "NONE")
        self.assertEqual(len(self.op("lanes", {"conversation_id": conv["conversation_id"]})["lanes"]), 1)
        self.assertEqual(len(self.op("bridges", {"conversation_id": conv["conversation_id"]})["external_bridges"]), 1)

    def test_simultaneous_same_mission_conversations_remain_distinct(self):
        a = self.op("create", {"mission_id": "M1", "idempotency_key": "same-mission-a"})
        b = self.op("create", {"mission_id": "M1", "idempotency_key": "same-mission-b"})
        self.assertNotEqual(a["conversation_id"], b["conversation_id"])
        self.assertEqual(a["current_binding"]["mission_id"], b["current_binding"]["mission_id"])

    def test_concurrent_same_create_request_materializes_one_conversation(self):
        def create(_):
            return self.op(
                "create",
                {"title": "C", "idempotency_key": "concurrent-create"},
            )["conversation_id"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            ids = list(pool.map(create, range(40)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(len(self.op("list")["conversations"]), 1)

    def test_frozen_predecessor_cannot_fork_through_different_transition(self):
        root = self.op("create", {"idempotency_key": "fork-root"})
        self.op("bind", {
            "conversation_id": root["conversation_id"],
            "transition": {"mission_id": "M1", "operation_id": "first"},
        })
        with self.assertRaises(ConversationConflict):
            self.op("bind", {
                "conversation_id": root["conversation_id"],
                "transition": {"mission_id": "M1", "operation_id": "second"},
            })


    def test_mission_view_lists_all_canonical_conversations_for_exact_mission(self):
        a = self.op("create", {"mission_id": "M1", "idempotency_key": "m1-a"})
        b = self.op("create", {"mission_id": "M1", "idempotency_key": "m1-b"})
        self.op("create", {"mission_id": "M2", "idempotency_key": "m2-a"})
        rows = self.store("conversation_list", {"mission_id": "M1"})["conversations"]
        self.assertEqual(
            {x["conversation_id"] for x in rows},
            {a["conversation_id"], b["conversation_id"]},
        )
        self.assertTrue(all(x["current_binding"]["mission_id"] == "M1" for x in rows))

class R24ConversationApiTests(unittest.TestCase):
    def test_http_api_exposes_domain_without_switching_legacy_thread_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ThreadStore(Path(directory) / "threads.db")

            class FakeGateway:
                thread_provider = store
                control_provider = None
                operator_provider = None

                def state(self):
                    return {"authority_effect": "NONE"}

            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(FakeGateway()))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"

            def req(path, body=None):
                data = None
                headers = {}
                method = "GET"
                if body is not None:
                    data = json.dumps(body).encode()
                    headers["Content-Type"] = "application/json"
                    method = "POST"
                request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
                try:
                    response = urllib.request.urlopen(request, timeout=5)
                    return response.status, json.loads(response.read())
                except urllib.error.HTTPError as error:
                    return error.code, json.loads(error.read())

            try:
                status, created = req("/api/conversations", {
                    "title": "API",
                    "idempotency_key": "api-create",
                })
                self.assertEqual(status, 201)
                cid = created["conversation_id"]
                status, got = req("/api/conversations/" + cid)
                self.assertEqual(status, 200)
                self.assertEqual(got["conversation_id"], cid)
                status, bound = req("/api/conversations/" + cid + "/bind", {
                    "mission_id": "M1",
                    "operation_id": "api-bind",
                })
                self.assertEqual(status, 201)
                self.assertNotEqual(bound["conversation_id"], cid)
                status, lineage = req("/api/conversations/" + bound["conversation_id"] + "/lineage")
                self.assertEqual(status, 200)
                self.assertEqual(
                    [x["transition"] for x in lineage["ancestors"]],
                    ["BIND", "CREATE"],
                )
                status, legacy = req("/api/threads", {})
                self.assertEqual(status, 410)
                self.assertTrue(legacy["archival_read_only"])
                self.assertEqual(legacy["canonical_surface"], "/api/conversations")
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
