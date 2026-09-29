from __future__ import annotations

import json
import sqlite3
import unittest

from cyber_lion.app_coordination.conversation_backfill import (
    ConversationBackfillError,
    MIGRATION_VERSION,
    apply_manifest,
    apply_mission_entry,
    build_dry_run_manifest,
    build_mission_dry_run_entry,
    deterministic_conversation_id,
    legacy_evidence_for_mission,
    verify_mission_entry,
)
from cyber_lion.app_coordination.conversation_schema import migrate_conversation_schema


def legacy_conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE threads(
          thread_id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL
        );
        CREATE TABLE messages(
          message_id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,seq INTEGER NOT NULL,
          role TEXT NOT NULL,content TEXT NOT NULL,created_at REAL NOT NULL,meta_json TEXT NOT NULL,
          UNIQUE(thread_id,seq)
        );
        CREATE TABLE thread_bindings(
          thread_id TEXT PRIMARY KEY,mission_id TEXT,target TEXT NOT NULL,channel TEXT NOT NULL,
          binding_revision INTEGER NOT NULL,binding_state TEXT NOT NULL,
          created_at REAL NOT NULL,updated_at REAL NOT NULL
        );
        CREATE TABLE thread_model_routes(
          thread_id TEXT PRIMARY KEY,model_route TEXT NOT NULL,route_revision INTEGER NOT NULL,
          created_at REAL NOT NULL,updated_at REAL NOT NULL
        );
        """
    )
    return c


def conversation_conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    migrate_conversation_schema(c, now_fn=lambda: 1.0)
    return c


def mission(mid, state="RUNNING", **extra):
    return {
        "mission_id": mid,
        "title": "Mission " + mid,
        "adapter": extra.pop("adapter", "LPCL"),
        "spec_digest": extra.pop("spec_digest", "a" * 64),
        "source_head": extra.pop("source_head", "b" * 40),
        "source_tree": extra.pop("source_tree", "c" * 40),
        "created_at": extra.pop("created_at", "2026-09-28T00:00:00Z"),
        "state": state,
        "runtime_state": extra.pop("runtime_state", "READY"),
        "material_target": extra.pop("material_target", 1),
        "materialized": extra.pop("materialized", 1),
        "ready": extra.pop("ready", 1),
        "updated_at": extra.pop("updated_at", "2026-09-28T00:01:00Z"),
        "last_error": extra.pop("last_error", None),
        **extra,
    }


class R24ConversationBackfillTests(unittest.TestCase):
    def test_deterministic_identity_depends_only_on_version_and_mission(self):
        a = deterministic_conversation_id("M1")
        b = deterministic_conversation_id("M1")
        c = deterministic_conversation_id("M2")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.startswith("conv-mig-"))
        self.assertEqual(
            a,
            deterministic_conversation_id("M1", MIGRATION_VERSION),
        )

    def test_absent_history_with_existing_empty_legacy_thread_stays_empty(self):
        c = legacy_conn()
        c.execute("INSERT INTO threads VALUES('t1','legacy',1,1)")
        c.execute("INSERT INTO thread_bindings VALUES('t1','M1','mission:M1','LION_BUS',1,'MISSION_BOUND',1,1)")
        c.execute("INSERT INTO thread_model_routes VALUES('t1','SAAS',1,1,1)")
        e = legacy_evidence_for_mission(c, "M1")
        self.assertEqual(e["history_classification"], "ABSENT")
        self.assertEqual(e["history_copy_policy"], "EMPTY_CANONICAL_TRANSCRIPT")
        self.assertEqual(e["legacy_thread_refs"][0]["message_count"], 0)
        self.assertEqual(len(e["legacy_evidence_digest"]), 64)

    def test_ambiguous_legacy_history_is_never_promoted_to_exact(self):
        c = legacy_conn()
        c.execute("INSERT INTO threads VALUES('t1','legacy',1,2)")
        c.execute("INSERT INTO thread_bindings VALUES('t1','M1','mission:M1','LION_BUS',1,'MISSION_BOUND',1,2)")
        c.execute("INSERT INTO messages VALUES('m1','t1',1,'user','legacy content',1.5,'{}')")
        e = legacy_evidence_for_mission(c, "M1")
        self.assertEqual(e["history_classification"], "AMBIGUOUS")
        self.assertEqual(e["history_copy_policy"], "FORBID_CANONICAL_COPY_ARCHIVE_LINK_ONLY")
        self.assertFalse(e["legacy_thread_refs"][0]["messages"][0]["exact_attribution"])
        self.assertNotIn("content", e["legacy_thread_refs"][0]["messages"])

    def test_exact_history_requires_explicit_per_message_attribution(self):
        c = legacy_conn()
        c.execute("INSERT INTO threads VALUES('t1','legacy',1,2)")
        c.execute("INSERT INTO thread_bindings VALUES('t1','M1','mission:M1','LION_BUS',1,'MISSION_BOUND',1,2)")
        meta = json.dumps({"mission_id": "M1", "legacy_history_attribution": "EXACT"})
        c.execute("INSERT INTO messages VALUES('m1','t1',1,'user','exact content',1.5,?)", (meta,))
        e = legacy_evidence_for_mission(c, "M1")
        self.assertEqual(e["history_classification"], "EXACT_ATTRIBUTABLE")
        self.assertEqual(e["history_copy_policy"], "EXACT_HISTORY_MAY_BE_IMPORTED_READ_ONLY")

    def test_dry_run_contains_required_fields_and_no_mutation(self):
        legacy = legacy_conn()
        before = legacy.total_changes
        manifest = build_dry_run_manifest(
            [mission("M2"), mission("M1"), mission("DONE", state="COMPLETE")],
            legacy,
            generated_at="2026-09-28T17:30:00+02:00",
        )
        self.assertEqual(legacy.total_changes, before)
        self.assertEqual(manifest["mode"], "DRY_RUN")
        self.assertEqual(manifest["mission_count"], 2)
        self.assertEqual([x["mission_id"] for x in manifest["entries"]], ["M1", "M2"])
        for entry in manifest["entries"]:
            self.assertEqual(entry["proposed_binding_epoch"], 1)
            self.assertEqual(entry["proposed_binding_state"], "BOUND")
            self.assertIn(entry["history_classification"], {"EXACT_ATTRIBUTABLE", "AMBIGUOUS", "ABSENT"})
            self.assertEqual(entry["provenance"]["authority_effect"], "NONE")
            self.assertTrue(entry["provenance"]["no_protocol_event_reinterpretation"])
            self.assertEqual(len(entry["source_digests"]["cutover_source_digest"]), 64)
            self.assertEqual(
                entry["rollback_pointer"]["pre_apply_state"],
                "NO_CANONICAL_MUTATION_IN_DRY_RUN",
            )

    def test_recorded_legacy_mission_requires_h4_review(self):
        c = legacy_conn()
        entry = build_mission_dry_run_entry(
            mission("legacy::vkt", state="RECORDED_RUNNING", adapter="LEGACY_OBSERVATION:VKT_R3"),
            c,
        )
        self.assertEqual(entry["cutover_eligibility"], "H4_REVIEW_LEGACY_RECORDED_MISSION")

    def test_apply_requires_h4_allowlist_and_is_idempotent(self):
        legacy = legacy_conn()
        manifest = build_dry_run_manifest([mission("M1")], legacy)
        entry = manifest["entries"][0]
        c = conversation_conn()
        with self.assertRaisesRegex(ConversationBackfillError, "not approved"):
            apply_mission_entry(c, entry, approved_mission_ids=set(), now_fn=lambda: 5.0)
        # The manifest-level API must skip all non-approved missions without mutation.
        skipped = apply_manifest(c, manifest, approved_mission_ids=set())
        self.assertEqual(skipped["applied"], [])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 0)

        first = apply_manifest(c, manifest, approved_mission_ids={"M1"}, now_fn=lambda: 10.0)
        self.assertEqual(len(first["applied"]), 1)
        self.assertFalse(first["applied"][0]["idempotent_replay"])
        second = apply_manifest(c, manifest, approved_mission_ids={"M1"}, now_fn=lambda: 20.0)
        self.assertTrue(second["applied"][0]["idempotent_replay"])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 1)
        verified = verify_mission_entry(c, entry)
        self.assertTrue(verified["verified"])
        self.assertEqual(verified["binding_epoch"], 1)
        self.assertEqual(verified["history_classification"], "ABSENT")

    def test_ambiguous_history_apply_creates_no_canonical_messages(self):
        legacy = legacy_conn()
        legacy.execute("INSERT INTO threads VALUES('t1','legacy',1,2)")
        legacy.execute("INSERT INTO thread_bindings VALUES('t1','M1','mission:M1','LION_BUS',1,'MISSION_BOUND',1,2)")
        legacy.execute("INSERT INTO messages VALUES('m1','t1',1,'user','do not copy me',1.5,'{}')")
        manifest = build_dry_run_manifest([mission("M1")], legacy)
        self.assertEqual(manifest["entries"][0]["history_classification"], "AMBIGUOUS")
        c = conversation_conn()
        out = apply_manifest(c, manifest, approved_mission_ids={"M1"}, now_fn=lambda: 10.0)
        self.assertFalse(out["failures"])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0], 0)
        details = json.loads(c.execute(
            "SELECT details_json FROM conversation_migration_provenance"
        ).fetchone()[0])
        self.assertFalse(details["protocol_events_imported_as_chat_messages"])
        self.assertEqual(details["task_history_classification"], "AMBIGUOUS")

    def test_per_mission_atomicity_and_resume(self):
        legacy = legacy_conn()
        manifest = build_dry_run_manifest([mission("M1"), mission("M2")], legacy)
        broken = json.loads(json.dumps(manifest))
        broken["entries"][1]["proposed_conversation_id"] = "conv-mig-wrong"
        c = conversation_conn()
        first = apply_manifest(
            c, broken, approved_mission_ids={"M1", "M2"}, now_fn=lambda: 10.0
        )
        self.assertEqual(len(first["applied"]), 1)
        self.assertEqual(first["failures"][0]["mission_id"], "M2")
        self.assertEqual(first["resume_from_mission_id"], "M2")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 1)

        resumed = apply_manifest(
            c, manifest, approved_mission_ids={"M1", "M2"}, now_fn=lambda: 20.0
        )
        self.assertFalse(resumed["failures"])
        self.assertEqual(len(resumed["applied"]), 2)
        self.assertTrue(resumed["applied"][0]["idempotent_replay"])
        self.assertFalse(resumed["applied"][1]["idempotent_replay"])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 2)


    def test_exact_attributable_migration_preserves_provenance_without_fabrication(self):
        legacy = legacy_conn()
        legacy.execute("INSERT INTO threads VALUES('t1','legacy',1,2)")
        legacy.execute("INSERT INTO thread_bindings VALUES('t1','M1','mission:M1','LION_BUS',1,'MISSION_BOUND',1,2)")
        meta = json.dumps({"mission_id": "M1", "legacy_history_attribution": "EXACT"})
        legacy.execute("INSERT INTO messages VALUES('m1','t1',1,'user','exact legacy',1.5,?)", (meta,))
        manifest = build_dry_run_manifest([mission("M1")], legacy)
        entry = manifest["entries"][0]
        self.assertEqual(entry["history_classification"], "EXACT_ATTRIBUTABLE")
        c = conversation_conn()
        applied = apply_manifest(c, manifest, approved_mission_ids={"M1"}, now_fn=lambda: 10.0)
        self.assertFalse(applied["failures"])
        verified = verify_mission_entry(c, entry)
        self.assertEqual(verified["history_classification"], "EXACT_ATTRIBUTABLE")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0], 0)
        details = json.loads(c.execute(
            "SELECT details_json FROM conversation_migration_provenance WHERE mission_id='M1'"
        ).fetchone()[0])
        self.assertEqual(details["history_copy_policy"], "EXACT_HISTORY_MAY_BE_IMPORTED_READ_ONLY")
        self.assertFalse(details["protocol_events_imported_as_chat_messages"])

    def test_partial_cutover_has_working_preapply_rollback_snapshot(self):
        legacy = legacy_conn()
        manifest = build_dry_run_manifest([mission("M1"), mission("M2")], legacy)
        c = conversation_conn()
        rollback = sqlite3.connect(":memory:")
        c.backup(rollback)
        first_only = {"mode": "DRY_RUN", "entries": [manifest["entries"][0]]}
        out = apply_manifest(c, first_only, approved_mission_ids={"M1"}, now_fn=lambda: 10.0)
        self.assertEqual(len(out["applied"]), 1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 1)
        restored = sqlite3.connect(":memory:")
        rollback.backup(restored)
        self.assertEqual(restored.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 0)
        self.assertEqual(
            manifest["entries"][0]["rollback_pointer"]["pre_apply_state"],
            "NO_CANONICAL_MUTATION_IN_DRY_RUN",
        )
        rollback.close()
        restored.close()

if __name__ == "__main__":
    unittest.main()
