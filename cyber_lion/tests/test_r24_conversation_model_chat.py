from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from cyber_lion.app_coordination.conversation_chat import (
    deliver_saas_once,
    submit_chat,
)
from cyber_lion.app_coordination.local_intelligence_gateway import make_handler
from cyber_lion.app_coordination.conversation_domain import ConversationConflict
from tools.lion_local_intelligence_runtime import ThreadStore


class FakeControl:
    def __init__(self):
        self.counter = 0
        self.requests = {}
        self.order = []

    def __call__(self, op, args):
        if op == "saas_request":
            self.counter += 1
            request_id = f"saas-request-{self.counter}"
            self.order.append(("SAAS_REQUEST", request_id, args["question"]))
            self.requests[request_id] = {
                "status": "PENDING",
                "request_id": request_id,
                "question_digest": sha256(args["question"].encode("utf-8")).hexdigest(),
                "thread_id": None,
                "receipt_digest": None,
                "response_text": None,
                "response_meta_json": "{}",
            }
            return {
                "request_id": request_id,
                "request_code": f"CODE-{self.counter}",
                "transport": args.get("transport") or "CHATGPT_SENTINELX_MCP",
                "authority_effect": "NONE",
            }
        if op == "saas_request_status":
            return dict(self.requests[args["request_id"]])
        raise AssertionError((op, args))

    def respond(self, request_id, text, model="FAKE_REAL_SAAS"):
        row = self.requests[request_id]
        row.update({
            "status": "RESPONDED",
            "receipt_digest": ("d" if request_id.endswith("1") else "e") * 64,
            "response_text": text,
            "response_digest": sha256(text.encode("utf-8")).hexdigest(),
            "binding_id": "binding-" + request_id,
            "claim_generation": 1,
            "response_meta_json": json.dumps({
                "model_identity": model,
                "transport": "CHATGPT_FIREFOX_PROJECT_MEDIATED",
                "authority_effect": "NONE",
            }),
        })


class FakeGateway:
    def __init__(self, store, control):
        self.thread_provider = store
        self.control_provider = control
        self.operator_provider = None
        self.control = control
        self.local_calls = []
        self.order = control.order
        self.ctx = type("Ctx", (), {"digest": "a" * 64})()

    def chat(self, message, use_web=False, history=None, output_language="auto", provider_binding=None):
        self.order.append(("LOCAL_CHAT", message, list(history or [])))
        self.local_calls.append({
            "message": message,
            "history": list(history or []),
            "output_language": output_language,
            "provider_binding": dict(provider_binding or {}),
        })
        answer = "LOCAL-SECRET-OUTPUT:" + message
        return {
            "route": "LOCAL_MODEL",
            "answer": answer,
            "authority_boundary": False,
            "authority_effect": "NONE",
            "provider_provenance": {
                "shared_context_digest": self.ctx.digest,
                "projection_digest": "b" * 64,
                "actual_payload_bytes_digest": "c" * 64,
                "response_digest": sha256(answer.encode("utf-8")).hexdigest(),
                "provider": "LOCAL",
                "provider_session_ref": (provider_binding or {}).get("provider_session_ref"),
                "provider_session_ref_class": (
                    "LION_LANE_REF_NOT_PROVIDER_ATTESTATION"
                    if (provider_binding or {}).get("provider_session_ref")
                    else "UNKNOWN_NOT_PROVIDER_ATTESTED"
                ),
                "authority_effect": "NONE",
            },
        }

    def state(self):
        return {"authority_effect": "NONE"}


class ThreadStoreConnectionSafetyTests(unittest.TestCase):
    class FakeConnection:
        def __init__(self, fail_on=None):
            self.fail_on=fail_on
            self.statements=[]
            self.closed=False
            self.row_factory=None
        def execute(self, statement):
            self.statements.append(statement)
            if statement==self.fail_on:
                raise sqlite3.OperationalError("simulated pragma failure")
            return self
        def close(self):
            self.closed=True

    def store_without_init(self):
        store=ThreadStore.__new__(ThreadStore)
        store.path=Path("synthetic-thread-store.db")
        return store

    def test_connection_setup_does_not_renegotiate_journal_mode_per_request(self):
        fake=self.FakeConnection()
        with patch("tools.lion_local_intelligence_runtime.sqlite3.connect",return_value=fake):
            result=self.store_without_init()._conn()
        self.assertIs(result,fake)
        self.assertEqual(fake.statements,["PRAGMA busy_timeout=10000","PRAGMA foreign_keys=ON"])
        self.assertFalse(fake.closed)

    def test_connection_setup_closes_descriptor_if_pragma_fails(self):
        fake=self.FakeConnection(fail_on="PRAGMA foreign_keys=ON")
        with patch("tools.lion_local_intelligence_runtime.sqlite3.connect",return_value=fake):
            with self.assertRaises(sqlite3.OperationalError):
                self.store_without_init()._conn()
        self.assertTrue(fake.closed)


class R24ConversationModelChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ThreadStore(Path(self.tmp.name) / "threads.db")
        self.control = FakeControl()
        self.gateway = FakeGateway(self.store, self.control)

    def tearDown(self):
        self.tmp.cleanup()

    def create(self, key):
        return self.store("conversation_create", {
            "title": key,
            "idempotency_key": key,
        })

    def transcript(self, cid):
        return self.store("conversation_chat_transcript", {"conversation_id": cid})

    def events(self, cid, consumer="panel-r24", **extra):
        return self.store("conversation_chat_events", {
            "conversation_id": cid,
            "consumer_id": consumer,
            **extra,
        })

    def test_local_request_has_complete_identity_and_independent_provider_session(self):
        conv = self.create("local-root")
        out = submit_chat(self.store, self.gateway, conv["conversation_id"], {
            "message": "alpha",
            "route": "LOCAL",
            "client_request_id": "local-1",
        })
        self.assertEqual(out["state"], "LOCAL_COMPLETE")
        self.assertEqual(len(out["legs"]), 1)
        leg = out["legs"][0]
        self.assertEqual(leg["provider"], "LOCAL")
        self.assertIsNone(leg["provider_session_ref"])
        self.assertIsNone(out["responses"]["LOCAL"]["provider_provenance"]["provider_session_ref"])
        self.assertEqual(
            out["responses"]["LOCAL"]["provider_provenance"]["provider_session_ref_class"],
            "UNKNOWN_NOT_PROVIDER_ATTESTED",
        )
        for field in (
            "conversation_id", "binding_epoch", "correlation_id",
            "causation_id", "context_digest",
        ):
            self.assertTrue(out[field])
        self.assertTrue(leg["lane_id"])
        self.assertTrue(leg["message_id"])
        transcript = self.transcript(conv["conversation_id"])["messages"]
        self.assertEqual([x["role"] for x in transcript], ["USER", "ASSISTANT"])
        self.assertEqual(transcript[0]["correlation_id"], out["correlation_id"])
        self.assertEqual(transcript[1]["correlation_id"], out["correlation_id"])
        self.assertEqual(transcript[0]["causation_id"], transcript[1]["causation_id"])
        self.assertEqual(transcript[0]["context_digest"], transcript[1]["context_digest"])

    def test_saas_request_uses_distinct_broker_identity_and_delivers_later(self):
        conv = self.create("saas-root")
        out = submit_chat(self.store, self.gateway, conv["conversation_id"], {
            "message": "beta",
            "route": "SAAS",
            "client_request_id": "saas-1",
        })
        self.assertEqual(out["state"], "SAAS_QUEUED")
        request_id = out["saas_handoff"]["request_id"]
        self.assertEqual(out["saas_handoff"]["transport"], "CHATGPT_SENTINELX_MCP")
        self.assertNotEqual(request_id, conv["conversation_id"])
        self.assertIsNone(out["saas_handoff"]["provider_session_ref"])
        self.assertEqual(deliver_saas_once(self.store, self.control), [])
        before = self.transcript(conv["conversation_id"])["messages"]
        self.assertEqual([x["role"] for x in before], ["USER"])
        self.control.respond(request_id, "SAAS-DELAYED-ANSWER")
        delivered = deliver_saas_once(self.store, self.control)
        self.assertEqual(len(delivered), 1)
        after = self.transcript(conv["conversation_id"])["messages"]
        self.assertEqual([x["role"] for x in after], ["USER", "ASSISTANT"])
        self.assertEqual(after[-1]["content"], "SAAS-DELAYED-ANSWER")
        self.assertEqual(after[-1]["context_digest"], out["context_digest"])
        self.assertEqual(after[-1]["correlation_id"], out["correlation_id"])
        provider_meta=after[-1]["metadata"]["response_meta"]
        self.assertEqual(provider_meta["projection_digest"], out["saas_handoff"]["projection_digest"])
        self.assertEqual(provider_meta["response_digest"], sha256(b"SAAS-DELAYED-ANSWER").hexdigest())
        self.assertEqual(provider_meta["broker_binding_id"], "binding-" + request_id)
        self.assertEqual(provider_meta["broker_claim_generation"], 1)
        lanes = self.store("conversation_lanes", {"conversation_id": conv["conversation_id"]})["lanes"]
        saas_lane = next(x for x in lanes if x["provider"] == "SAAS")
        self.assertEqual(saas_lane["provider_session_ref"], "binding-" + request_id)
        self.assertEqual(after[-1]["metadata"]["provider_session_ref"], "binding-" + request_id)
        self.assertEqual(
            after[-1]["metadata"]["provider_session_ref_class"],
            "SAAS_BROKER_SESSION_BINDING",
        )

    def test_saas_dispatch_evidence_survives_threadstore_connection_close(self):
        conv = self.create("saas-dispatch-persistence")
        out = submit_chat(self.store, self.gateway, conv["conversation_id"], {
            "message": "persist dispatch",
            "route": "SAAS",
            "client_request_id": "saas-dispatch-persist-1",
        })
        request_id = out["saas_handoff"]["request_id"]
        candidate = self.store("conversation_chat_saas_candidates", {"limit": 16})["candidates"][0]
        evidence = self.store("conversation_chat_record_saas_dispatch", {
            "conversation_id": conv["conversation_id"],
            "request_message_id": candidate["message_id"],
            "request_id": request_id,
            "binding_epoch": candidate["binding_epoch"],
            "lane_id": candidate["lane_id"],
            "shared_context_digest": candidate["shared_context_digest"],
            "projection_digest": candidate["projection_digest"],
            "actual_payload_bytes_digest": "1" * 64,
            "turn_request_hash": "2" * 64,
            "turn_id": "turn-dispatch-persistence",
            "bridge_id": "bridge-dispatch-persistence",
            "external_thread_ref": "external-dispatch-persistence",
            "dispatch_state": "BOUND_SENT",
        })
        self.assertFalse(evidence["idempotent_replay"])
        with sqlite3.connect(self.store.path) as conn:
            raw = conn.execute(
                "SELECT metadata_json FROM conversation_messages WHERE message_id=?",
                (candidate["message_id"],),
            ).fetchone()[0]
        persisted = json.loads(raw)
        self.assertEqual(
            persisted["dispatch_evidence"]["actual_payload_bytes_digest"],
            "1" * 64,
        )
        replay = self.store("conversation_chat_record_saas_dispatch", {
            "conversation_id": conv["conversation_id"],
            "request_message_id": candidate["message_id"],
            "request_id": request_id,
            "binding_epoch": candidate["binding_epoch"],
            "lane_id": candidate["lane_id"],
            "shared_context_digest": candidate["shared_context_digest"],
            "projection_digest": candidate["projection_digest"],
            "actual_payload_bytes_digest": "1" * 64,
            "turn_request_hash": "2" * 64,
            "turn_id": "turn-dispatch-persistence",
            "bridge_id": "bridge-dispatch-persistence",
            "external_thread_ref": "external-dispatch-persistence",
            "dispatch_state": "BOUND_SENT",
        })
        self.assertTrue(replay["idempotent_replay"])

    def test_cancelled_saas_closes_mapping_without_fabricating_response(self):
        conv = self.create("saas-cancel-root")
        out = submit_chat(self.store, self.gateway, conv["conversation_id"], {
            "message": "cancel-me",
            "route": "SAAS",
            "client_request_id": "saas-cancel-1",
        })
        request_id = out["saas_handoff"]["request_id"]
        self.control.requests[request_id]["status"] = "CANCELLED"
        self.assertEqual(deliver_saas_once(self.store, self.control), [])
        pending = self.store("conversation_chat_saas_candidates", {"limit": 128})["candidates"]
        self.assertNotIn(request_id, {x["request_id"] for x in pending})
        transcript = self.transcript(conv["conversation_id"])["messages"]
        self.assertEqual([x["role"] for x in transcript], ["USER"])
        lanes = self.store("conversation_lanes", {"conversation_id": conv["conversation_id"]})["lanes"]
        saas_lane = next(x for x in lanes if x["lane_id"] == out["legs"][0]["lane_id"])
        self.assertEqual(saas_lane["state"], "FAILED")
        self.assertEqual(deliver_saas_once(self.store, self.control), [])

    def test_dual_freezes_one_context_and_dispatches_saas_before_local_without_hidden_state(self):
        conv = self.create("dual-root")
        first = submit_chat(self.store, self.gateway, conv["conversation_id"], {
            "message": "prior",
            "route": "LOCAL",
            "client_request_id": "seed-1",
        })
        self.assertEqual(first["state"], "LOCAL_COMPLETE")
        self.control.order.clear()
        out = submit_chat(self.store, self.gateway, conv["conversation_id"], {
            "message": "gamma",
            "route": "DUAL",
            "client_request_id": "dual-1",
        })
        self.assertEqual(out["state"], "DUAL_WAITING")
        self.assertEqual([x["provider"] for x in out["legs"]], ["LOCAL", "SAAS"])
        self.assertIsNone(out["legs"][0]["provider_session_ref"])
        self.assertIsNone(out["legs"][1]["provider_session_ref"])
        self.assertEqual(self.control.order[0][0], "SAAS_REQUEST")
        self.assertEqual(self.control.order[1][0], "LOCAL_CHAT")
        saas_prompt = self.control.order[0][2]
        self.assertNotIn("LOCAL-SECRET-OUTPUT:gamma", saas_prompt)
        self.assertIn("LOCAL-SECRET-OUTPUT:prior", saas_prompt)
        self.assertIn("gamma", saas_prompt)
        lane_rows = self.store("conversation_lanes", {
            "conversation_id": conv["conversation_id"],
        })["lanes"]
        dual_rows = [
            x for x in lane_rows
            if x["lane_id"] in {leg["lane_id"] for leg in out["legs"]}
        ]
        self.assertEqual({x["context_digest"] for x in dual_rows}, {out["context_digest"]})
        self.assertEqual(out["shared_context_digest"], self.gateway.ctx.digest)
        self.assertEqual(out["responses"]["LOCAL"]["provider_provenance"]["shared_context_digest"], out["shared_context_digest"])
        self.assertEqual(out["saas_handoff"]["shared_context_digest"], out["shared_context_digest"])
        self.assertNotEqual(out["responses"]["LOCAL"]["provider_provenance"]["projection_digest"], out["saas_handoff"]["projection_digest"])
        self.assertEqual(out["saas_handoff"]["projection_digest"], out["saas_handoff"]["broker_question_digest"])
        self.assertIsNone(out["saas_handoff"]["actual_provider_payload_bytes_digest"])
        request_id = out["saas_handoff"]["request_id"]
        self.control.respond(request_id, "SAAS-GAMMA")
        delivered = deliver_saas_once(self.store, self.control)
        self.assertEqual(len(delivered), 1)
        self.assertIsNotNone(delivered[0]["join"])
        lanes = self.store("conversation_lanes", {"conversation_id": conv["conversation_id"]})["lanes"]
        local_lane = next(x for x in lanes if x["provider"] == "LOCAL")
        saas_lane = next(x for x in lanes if x["provider"] == "SAAS")
        self.assertIsNone(local_lane["provider_session_ref"])
        self.assertEqual(saas_lane["provider_session_ref"], "binding-" + request_id)
        transcript = self.transcript(conv["conversation_id"])["messages"]
        self.assertEqual(
            [x["content"] for x in transcript],
            [
                "prior",
                "LOCAL-SECRET-OUTPUT:prior",
                "gamma",
                "### LOCAL\nLOCAL-SECRET-OUTPUT:gamma\n\n### SAAS\nSAAS-GAMMA",
            ],
        )

    def test_canonical_history_is_bounded_before_local_gateway(self):
        conv = self.create("bounded-history-root")
        for index in range(8):
            out = submit_chat(self.store, self.gateway, conv["conversation_id"], {
                "message": f"turn-{index}",
                "route": "LOCAL",
                "client_request_id": f"bounded-{index}",
            })
            self.assertEqual(out["state"], "LOCAL_COMPLETE")
        history = self.gateway.local_calls[-1]["history"]
        self.assertLessEqual(len(history), 8)
        self.assertLessEqual(sum(len(x["content"]) for x in history), 4200)
        self.assertEqual(history[-1]["content"], "LOCAL-SECRET-OUTPUT:turn-6")

    def test_delivery_cursor_survives_reconnect_and_suppresses_duplicates(self):
        conv = self.create("cursor-root")
        out = submit_chat(self.store, self.gateway, conv["conversation_id"], {
            "message": "delta",
            "route": "SAAS",
            "client_request_id": "cursor-1",
        })
        first = self.events(conv["conversation_id"], consumer="panel-persistent")
        self.assertEqual(len(first["events"]), 1)
        self.assertEqual(first["events"][0]["state"], "PERSISTED")
        self.store("conversation_chat_ack_cursor", {
            "conversation_id": conv["conversation_id"],
            "consumer_id": "panel-persistent",
            "last_sequence": first["next_cursor"],
        })
        reconnected = self.events(conv["conversation_id"], consumer="panel-persistent")
        self.assertEqual(reconnected["events"], [])
        self.control.respond(out["saas_handoff"]["request_id"], "SAAS-DELTA")
        deliver_saas_once(self.store, self.control)
        resumed = self.events(conv["conversation_id"], consumer="panel-persistent")
        self.assertEqual(len(resumed["events"]), 1)
        self.assertEqual(resumed["events"][0]["state"], "DELIVERED")
        self.assertEqual(
            resumed["events"][0]["response_message"]["content"],
            "SAAS-DELTA",
        )
        before_sequences = [x["sequence"] for x in self.events(
            conv["conversation_id"], consumer="observer", after=0
        )["events"]]
        self.assertEqual(before_sequences, sorted(before_sequences))
        self.assertEqual(deliver_saas_once(self.store, self.control), [])
        after_sequences = [x["sequence"] for x in self.events(
            conv["conversation_id"], consumer="observer2", after=0
        )["events"]]
        self.assertEqual(before_sequences, after_sequences)

    def test_switching_conversations_cannot_redirect_delayed_response(self):
        one = self.create("switch-one")
        two = self.create("switch-two")
        out_one = submit_chat(self.store, self.gateway, one["conversation_id"], {
            "message": "one",
            "route": "SAAS",
            "client_request_id": "switch-1",
        })
        out_two = submit_chat(self.store, self.gateway, two["conversation_id"], {
            "message": "two",
            "route": "SAAS",
            "client_request_id": "switch-2",
        })
        self.control.respond(out_one["saas_handoff"]["request_id"], "ANSWER-ONE")
        deliver_saas_once(self.store, self.control)
        one_events = self.events(one["conversation_id"], consumer="ui-one", after=0)["events"]
        two_events = self.events(two["conversation_id"], consumer="ui-two", after=0)["events"]
        self.assertTrue(any(
            x.get("response_message", {}).get("content") == "ANSWER-ONE"
            for x in one_events
            if x.get("response_message")
        ))
        self.assertFalse(any(x.get("response_message") for x in two_events))
        self.assertEqual(
            self.transcript(two["conversation_id"])["messages"][0]["content"],
            "two",
        )
        self.assertEqual(out_two["state"], "SAAS_QUEUED")

    def test_response_event_matches_all_required_request_identity_dimensions(self):
        conv = self.create("identity-response")
        out = submit_chat(self.store, self.gateway, conv["conversation_id"], {
            "message": "epsilon",
            "route": "LOCAL",
            "client_request_id": "identity-1",
        })
        rows = self.events(conv["conversation_id"], consumer="audit", after=0)["events"]
        delivered = [x for x in rows if x["state"] == "DELIVERED"][0]
        leg = out["legs"][0]
        self.assertEqual(delivered["conversation_id"], out["conversation_id"])
        self.assertEqual(delivered["binding_epoch"], out["binding_epoch"])
        self.assertEqual(delivered["lane_id"], leg["lane_id"])
        self.assertEqual(delivered["message_id"], leg["message_id"])
        self.assertEqual(delivered["causation_id"], out["causation_id"])
        self.assertEqual(delivered["correlation_id"], out["correlation_id"])
        self.assertEqual(delivered["context_digest"], out["context_digest"])
        response = delivered["response_message"]
        self.assertEqual(response["metadata"]["request_message_id"], leg["message_id"])

    def test_same_user_text_in_two_conversations_never_shares_saas_request(self):
        a = self.create("same-text-a")
        b = self.create("same-text-b")
        oa = submit_chat(self.store, self.gateway, a["conversation_id"], {
            "message": "identical",
            "route": "SAAS",
            "client_request_id": "same-1",
        })
        ob = submit_chat(self.store, self.gateway, b["conversation_id"], {
            "message": "identical",
            "route": "SAAS",
            "client_request_id": "same-1",
        })
        self.assertNotEqual(oa["context_digest"], ob["context_digest"])
        self.assertNotEqual(
            oa["saas_handoff"]["request_id"],
            ob["saas_handoff"]["request_id"],
        )
        self.assertIsNone(oa["saas_handoff"]["provider_session_ref"])
        self.assertIsNone(ob["saas_handoff"]["provider_session_ref"])


    def test_mission_bound_local_saas_and_dual_routes_preserve_binding_identity(self):
        for index,route in enumerate(("LOCAL","SAAS","DUAL"),1):
            conv=self.store("conversation_create",{
                "title":"bound-"+route,
                "mission_id":"M1",
                "idempotency_key":"bound-route-"+str(index),
            })
            out=submit_chat(self.store,self.gateway,conv["conversation_id"],{
                "message":"bound "+route.lower(),
                "route":route,
                "client_request_id":"bound-"+route.lower(),
            })
            got=self.store("conversation_get",{"conversation_id":conv["conversation_id"]})
            self.assertEqual(got["current_binding"]["mission_id"],"M1")
            self.assertEqual(got["current_binding"]["binding_epoch"],1)
            self.assertEqual(out["conversation_id"],conv["conversation_id"])
            self.assertEqual(out["route"],route)
            if route in {"SAAS","DUAL"}:
                self.control.respond(out["saas_handoff"]["request_id"],"BOUND-"+route+"-SAAS")
                delivered=deliver_saas_once(self.store,self.control)
                self.assertEqual(len(delivered),1)
            transcript=self.transcript(conv["conversation_id"])["messages"]
            self.assertTrue(transcript)

    def test_cross_conversation_response_injection_is_denied(self):
        a=self.create("inject-a")
        b=self.create("inject-b")
        out=submit_chat(self.store,self.gateway,a["conversation_id"],{
            "message":"source","route":"SAAS","client_request_id":"inject-1",
        })
        leg=out["legs"][0]
        with self.assertRaises(KeyError):
            self.store("conversation_chat_record_response",{
                "conversation_id":b["conversation_id"],
                "request_message_id":leg["message_id"],
                "provider":"SAAS",
                "response_text":"forged cross conversation",
                "response_meta":{"authority_effect":"NONE"},
            })
        self.assertEqual(self.transcript(b["conversation_id"])["messages"],[])

    def test_cross_lane_provider_injection_is_denied(self):
        conv=self.create("inject-lane")
        out=submit_chat(self.store,self.gateway,conv["conversation_id"],{
            "message":"lane","route":"SAAS","client_request_id":"inject-lane-1",
        })
        leg=out["legs"][0]
        with self.assertRaises(ConversationConflict):
            self.store("conversation_chat_record_response",{
                "conversation_id":conv["conversation_id"],
                "request_message_id":leg["message_id"],
                "provider":"LOCAL",
                "response_text":"wrong lane provider",
                "response_meta":{"authority_effect":"NONE"},
            })

    def test_stale_conflicting_provider_response_is_denied(self):
        conv=self.create("stale-provider")
        out=submit_chat(self.store,self.gateway,conv["conversation_id"],{
            "message":"stale","route":"SAAS","client_request_id":"stale-1",
        })
        request_id=out["saas_handoff"]["request_id"]
        self.control.respond(request_id,"FIRST")
        self.assertEqual(len(deliver_saas_once(self.store,self.control)),1)
        leg=out["legs"][0]
        with self.assertRaises(ConversationConflict):
            self.store("conversation_chat_record_response",{
                "conversation_id":conv["conversation_id"],
                "request_message_id":leg["message_id"],
                "provider":"SAAS",
                "response_text":"STALE-DIFFERENT",
                "response_meta":{"authority_effect":"NONE"},
            })
        self.assertEqual(self.transcript(conv["conversation_id"])["messages"][-1]["content"],"FIRST")

    def test_delivery_cursor_persists_across_threadstore_restart(self):
        path=Path(self.tmp.name)/"restart.db"
        first=ThreadStore(path)
        conv=first("conversation_create",{"title":"restart","idempotency_key":"restart-root"})
        control=FakeControl()
        gateway=FakeGateway(first,control)
        out=submit_chat(first,gateway,conv["conversation_id"],{
            "message":"restart","route":"SAAS","client_request_id":"restart-1",
        })
        initial=first("conversation_chat_events",{
            "conversation_id":conv["conversation_id"],"consumer_id":"restart-ui","after":0,
        })
        first("conversation_chat_ack_cursor",{
            "conversation_id":conv["conversation_id"],"consumer_id":"restart-ui",
            "last_sequence":initial["next_cursor"],
        })
        control.respond(out["saas_handoff"]["request_id"],"RESTART-ANSWER")
        deliver_saas_once(first,control)
        second=ThreadStore(path)
        resumed=second("conversation_chat_events",{
            "conversation_id":conv["conversation_id"],"consumer_id":"restart-ui",
        })
        self.assertEqual(len(resumed["events"]),1)
        self.assertEqual(resumed["events"][0]["response_message"]["content"],"RESTART-ANSWER")
        second("conversation_chat_ack_cursor",{
            "conversation_id":conv["conversation_id"],"consumer_id":"restart-ui",
            "last_sequence":resumed["next_cursor"],
        })
        third=ThreadStore(path)
        self.assertEqual(third("conversation_chat_events",{
            "conversation_id":conv["conversation_id"],"consumer_id":"restart-ui",
        })["events"],[])

class R24ConversationModelChatApiTests(unittest.TestCase):
    def test_http_chat_events_and_cursor_are_reactive_without_thread_cutover(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ThreadStore(Path(directory) / "threads.db")
            control = FakeControl()
            gateway = FakeGateway(store, control)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(gateway))
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
                request = urllib.request.Request(
                    base + path,
                    data=data,
                    headers=headers,
                    method=method,
                )
                try:
                    response = urllib.request.urlopen(request, timeout=5)
                    return response.status, json.loads(response.read())
                except urllib.error.HTTPError as error:
                    return error.code, json.loads(error.read())

            try:
                ui = urllib.request.urlopen(base + "/r24-model-chat", timeout=5).read().decode()
                self.assertIn("Canonical Model Chat", ui)
                self.assertIn("/api/conversations/", ui)
                self.assertIn("/events?", ui)
                self.assertIn("/cursor", ui)
                self.assertIn("setInterval(()=>void pollEvents(false),800)", ui)
                self.assertIn("Protocol plane", ui)
                self.assertIn("separate transcript", ui)
                self.assertIn("Native SaaS", ui)
                self.assertIn("Bind mission", ui)
                self.assertIn("Detach", ui)
                _, conv = req("/api/conversations", {
                    "title": "Reactive",
                    "idempotency_key": "api-reactive",
                })
                cid = conv["conversation_id"]
                status, queued = req("/api/conversations/" + cid + "/chat", {
                    "message": "zeta",
                    "route": "SAAS",
                    "client_request_id": "api-saas-1",
                })
                self.assertEqual(status, 201)
                self.assertEqual(queued["state"], "SAAS_QUEUED")
                status, initial = req(
                    "/api/conversations/" + cid + "/events?consumer_id=browser-r24"
                )
                self.assertEqual(status, 200)
                self.assertEqual([x["state"] for x in initial["events"]], ["PERSISTED"])
                req("/api/conversations/" + cid + "/cursor", {
                    "consumer_id": "browser-r24",
                    "last_sequence": initial["next_cursor"],
                })
                control.respond(queued["saas_handoff"]["request_id"], "API-DELAYED")
                deliver_saas_once(store, control)
                status, reactive = req(
                    "/api/conversations/" + cid + "/events?consumer_id=browser-r24"
                )
                self.assertEqual(status, 200)
                self.assertEqual([x["state"] for x in reactive["events"]], ["DELIVERED"])
                self.assertEqual(
                    reactive["events"][0]["response_message"]["content"],
                    "API-DELAYED",
                )
                status, legacy = req("/api/threads", {})
                self.assertEqual(status, 410)
                self.assertTrue(legacy["archival_read_only"])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
