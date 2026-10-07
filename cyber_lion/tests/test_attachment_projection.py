from __future__ import annotations
import unittest

from cyber_lion.contracts.attachment_projection import (
    AttachmentManifest,
    AttachmentProjection,
    AttachmentProjectionError,
    ProviderCapabilitySnapshot,
    validate_mode_for_capabilities,
)


class AttachmentProjectionTests(unittest.TestCase):
    def caps(self, **overrides):
        base = dict(
            provider="LOCAL", endpoint_ref="http://127.0.0.1:8772",
            model_release_ref=None, observed_at="2026-10-06T12:00:00Z",
            currentness="CURRENT", text_input="SUPPORTED", image_input="UNKNOWN",
            native_file_input="UNKNOWN", native_pdf_input="UNKNOWN",
            structured_data_input="SUPPORTED", workspace_access="UNKNOWN",
            network_access="UNKNOWN", session_persistence="UNSUPPORTED",
            streaming="UNKNOWN", max_payload_bytes=100000, parallel_calls=1,
            context_budget=4096, evidence_refs=("source:llama-server-config",),
        )
        base.update(overrides)
        return ProviderCapabilitySnapshot(**base).sealed()

    def manifest(self, media_type="text/plain", digest="a" * 64):
        return AttachmentManifest(
            attachment_id="attachment-1", source_artifact_ref="artifact:A1",
            original_content_digest=digest, byte_size=12, media_type=media_type,
            display_name="a.txt", source_domain="PANEL", classification="INTERNAL",
            producer="operator", mission_id="M1", conversation_id="conv-1",
            assignment_id=None, generation=1,
        ).sealed()

    def test_local_text_projection_is_allowed(self):
        m = self.manifest()
        c = self.caps()
        validate_mode_for_capabilities(m, c, "INLINE_TEXT")
        p = AttachmentProjection(
            projection_id="ap-1", attachment_manifest_digest=m.manifest_digest,
            provider_capability_digest=c.snapshot_digest, provider="LOCAL",
            mode="INLINE_TEXT", transformation_id="identity:utf8",
            derived_projection_digest="b" * 64, actual_provider_payload_digest="c" * 64,
            coverage="FULL", truncated=False, currentness="CURRENT",
        ).sealed()
        self.assertEqual(p.authority_effect, "NONE")

    def test_native_image_unknown_fails_closed(self):
        with self.assertRaises(AttachmentProjectionError):
            validate_mode_for_capabilities(self.manifest("image/png"), self.caps(), "NATIVE_IMAGE")

    def test_native_pdf_unknown_fails_closed(self):
        with self.assertRaises(AttachmentProjectionError):
            validate_mode_for_capabilities(self.manifest("application/pdf"), self.caps(native_file_input="SUPPORTED"), "NATIVE_FILE")

    def test_one_byte_change_changes_manifest_digest(self):
        left = self.manifest(digest="a" * 64)
        right = self.manifest(digest="b" * 64)
        self.assertNotEqual(left.manifest_digest, right.manifest_digest)

    def test_unsupported_cannot_claim_provider_payload(self):
        m = self.manifest("application/pdf")
        c = self.caps()
        with self.assertRaises(AttachmentProjectionError):
            AttachmentProjection(
                projection_id="ap-2", attachment_manifest_digest=m.manifest_digest,
                provider_capability_digest=c.snapshot_digest, provider="LOCAL",
                mode="UNSUPPORTED", transformation_id="none",
                derived_projection_digest=None, actual_provider_payload_digest="c" * 64,
                coverage="NONE", truncated=False, currentness="CURRENT",
            ).sealed()


if __name__ == "__main__":
    unittest.main()
