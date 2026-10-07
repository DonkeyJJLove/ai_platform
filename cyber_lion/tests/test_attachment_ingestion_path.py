from __future__ import annotations

import base64
import json
import sqlite3
import unittest
from hashlib import sha256

from cyber_lion.app_coordination.attachment_ingestion import (
    build_inline_text_projections,
    finalize_attachment_projections,
    ingest_inline_attachments,
)
from cyber_lion.app_coordination.conversation_chat import prepare_chat
from cyber_lion.app_coordination.conversation_domain import create_conversation
from cyber_lion.app_coordination.local_intelligence_gateway import Gateway
from cyber_lion.app_coordination.conversation_schema import migrate_conversation_schema
from cyber_lion.contracts.attachment_projection import (
    AttachmentProjectionError,
    ProviderCapabilitySnapshot,
)


class AttachmentIngestionPathTests(unittest.TestCase):
    def caps(self, provider="LOCAL", **overrides):
        value = dict(
            provider=provider, endpoint_ref="test:" + provider.lower(),
            model_release_ref=None, observed_at="2026-10-06T20:00:00Z",
            currentness="CURRENT", text_input="SUPPORTED", image_input="UNKNOWN",
            native_file_input="UNKNOWN", native_pdf_input="UNKNOWN",
            structured_data_input="UNKNOWN", workspace_access="UNKNOWN",
            network_access="UNKNOWN", session_persistence="UNKNOWN",
            streaming="UNKNOWN", max_payload_bytes=None, parallel_calls=None,
            context_budget=None, evidence_refs=("test:attachment-ingestion",),
        )
        value.update(overrides)
        return ProviderCapabilitySnapshot(**value).sealed()

    def raw(self, content=b"alpha\nbeta\n", media_type="text/plain"):
        return [{"display_name":"evidence.txt","media_type":media_type,
                 "data_b64":base64.b64encode(content).decode("ascii")}]

    def test_actual_bytes_manifest_projection_and_final_payload_are_distinctly_bound(self):
        items = ingest_inline_attachments(
            self.raw(), source_domain="PANEL", producer="LPCL_PANEL",
            mission_id="M1", conversation_id="conv-1", assignment_id=None, generation=1,
        )
        manifest = items[0]["manifest"]
        self.assertEqual(manifest["original_content_digest"], sha256(b"alpha\nbeta\n").hexdigest())
        segments, provisional = build_inline_text_projections(items, self.caps())
        self.assertEqual(len(segments), 1)
        self.assertIn(manifest["manifest_digest"], segments[0])
        self.assertIsNone(provisional[0]["actual_provider_payload_digest"])
        final = finalize_attachment_projections(provisional, "d" * 64)
        self.assertEqual(final[0]["actual_provider_payload_digest"], "d" * 64)
        self.assertNotEqual(final[0]["projection_digest"], provisional[0]["projection_digest"])

    def test_fresh_saas_transport_capability_is_current_before_conversation_bridge_exists(self):
        gateway = Gateway.__new__(Gateway)
        gateway.model = "http://127.0.0.1:8772"
        gateway.currentness_provider = lambda kind, args: {"models": [{"id": "local-model"}]}
        gateway.control_provider = lambda op, args: {
            "transport": "CHATGPT_SENTINELX_MCP",
            "channel_state": "SENTINELX_MCP_READY",
            "sentinelx_ready": True,
            "mediator": {
                "state": "READY",
                "fresh": True,
                "mediator_id": "LION_SENTINELX_MCP_BRIDGE_R1",
            },
        } if op == "saas_status" else {}
        snapshots = gateway._provider_capability_snapshots({"external_bridges": []}, [])
        saas = snapshots["SAAS"]
        self.assertEqual(saas["currentness"], "CURRENT")
        self.assertEqual(saas["text_input"], "SUPPORTED")
        self.assertEqual(saas["endpoint_ref"], "transport:CHATGPT_SENTINELX_MCP")
        self.assertIn("runtime:saas_status:CHATGPT_SENTINELX_MCP", saas["evidence_refs"][0])

    def test_stale_saas_transport_does_not_promote_attachment_capability(self):
        gateway = Gateway.__new__(Gateway)
        gateway.model = "http://127.0.0.1:8772"
        gateway.currentness_provider = lambda kind, args: {"models": [{"id": "local-model"}]}
        gateway.control_provider = lambda op, args: {
            "transport": "CHATGPT_SENTINELX_MCP",
            "channel_state": "SENTINELX_MCP_READY",
            "sentinelx_ready": True,
            "mediator": {"state": "READY", "fresh": False},
        } if op == "saas_status" else {}
        snapshots = gateway._provider_capability_snapshots({"external_bridges": []}, [])
        saas = snapshots["SAAS"]
        self.assertEqual(saas["currentness"], "UNKNOWN")
        self.assertEqual(saas["text_input"], "UNKNOWN")

    def test_binary_or_native_input_does_not_silently_fall_back_to_text(self):
        items = ingest_inline_attachments(
            self.raw(b"%PDF-1.7", "application/pdf"), source_domain="PANEL",
            producer="LPCL_PANEL", mission_id=None, conversation_id="conv-1",
            assignment_id=None, generation=1,
        )
        with self.assertRaisesRegex(AttachmentProjectionError, "text"):
            build_inline_text_projections(items, self.caps())

    def test_prepare_chat_binds_attachment_manifest_digests_into_context_and_replay(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        migrate_conversation_schema(conn)
        created = create_conversation(
            conn, {"title":"attachment","conversation_id":"conv-attach-1",
                   "idempotency_key":"create-attach-1"}, now=1.0,
        )
        args = {
            "conversation_id":created["conversation_id"], "message":"read attachment",
            "route":"LOCAL", "client_request_id":"req-attach-1", "output_language":"en",
            "shared_context_digest":"a"*64, "attachments":self.raw(b"first"),
        }
        first = prepare_chat(conn, args, now=2.0)
        self.assertEqual(len(first["attachment_manifest_digests"]), 1)
        stored = conn.execute(
            "SELECT metadata_json FROM conversation_messages WHERE message_id=?",
            (first["legs"][0]["message_id"],),
        ).fetchone()[0]
        meta = json.loads(stored)
        self.assertEqual(meta["attachment_manifest_digests"], first["attachment_manifest_digests"])
        replay = prepare_chat(conn, args, now=3.0)
        self.assertTrue(replay["idempotent_replay"])
        changed = dict(args); changed["attachments"] = self.raw(b"second")
        with self.assertRaisesRegex(Exception, "idempotency conflict"):
            prepare_chat(conn, changed, now=4.0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
