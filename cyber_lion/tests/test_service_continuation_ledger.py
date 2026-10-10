"""Contract and replay tests for source-bound, non-authorizing service ledger."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest

from cyber_lion.contracts.service_continuation_ledger import (
    ServiceContinuationLedgerError, GENESIS,
    assert_append_only, next_ready_tasks, propose_event, validate_ledger,
)

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "LION/architecture/v1_5/SERVICE_CONTINUATION_LEDGER_R1.json"
CLI = ROOT / "tools/lion_service_continuation_ledger.py"


class ServiceContinuationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.source = LEDGER.read_bytes()
        self.published = json.loads(self.source)
        self.ledger = deepcopy(self.published)
        self.ledger["events"] = []
        self.ledger["revision"] = 1
        self.ledger["event_chain_head"] = GENESIS
        self.at = "2026-10-11T09:00:00Z"

    def test_seed_has_real_pending_tasks_without_effect(self):
        states = validate_ledger(self.ledger)
        self.assertEqual(len(states), 16)
        self.assertEqual(sum(x == "READY" for x in states.values()), 3)
        self.assertEqual(states["SVC-0001"], "READY")
        self.assertEqual(states["SVC-0004"], "BLOCKED")
        self.assertEqual(states["SVC-0014"], "BLOCKED")
        self.assertEqual(self.ledger["event_chain_head"], GENESIS)
        self.assertEqual((self.ledger["authority_effect"], self.ledger["runtime_effect"]), ("NONE", "NONE"))
        self.assertEqual(self.ledger["baseline"]["source_head"],
                         "222d52e57ebf17b950322e2a097f9ed94271cf9c")

    def test_published_revision_replays_nine_source_bound_events(self):
        states = validate_ledger(self.published)
        self.assertEqual(self.published["revision"], 10)
        self.assertEqual(len(self.published["events"]), 9)
        self.assertEqual(states["SVC-0001"], "COMPLETE")
        self.assertEqual(states["SVC-0002"], "COMPLETE")
        self.assertEqual(states["SVC-0003"], "READY")
        self.assertEqual(states["SVC-0016"], "IN_PROGRESS")
        self.assertNotEqual(self.published["event_chain_head"], GENESIS)
        self.assertEqual(sum(x == "COMPLETE" for x in states.values()), 2)

    def test_next_ready_is_dependency_reduced_no_scheduler(self):
        ready = next_ready_tasks(self.ledger)
        self.assertEqual({x["task_id"] for x in ready},
                         {"SVC-0001", "SVC-0015", "SVC-0016"})
        self.assertTrue(all(x["first_action"] for x in ready))

    def test_propose_then_replay_valid_and_original_byte_unchanged(self):
        nxt = propose_event(self.ledger, kind="TRANSITION", task_id="SVC-0001",
                            actor="human-review", observed_at=self.at,
                            evidence_refs=["SOURCE:read-back-check"], to_state="IN_PROGRESS")
        self.assertEqual(validate_ledger(nxt)["SVC-0001"], "IN_PROGRESS")
        self.assertEqual(nxt["revision"], 2)
        self.assertEqual(nxt["events"][0]["previous_digest"], GENESIS)
        assert_append_only(self.ledger, nxt)
        self.assertEqual(LEDGER.read_bytes(), self.source)

    def test_tampering_event_and_chain_or_sequence_is_denied(self):
        nxt = propose_event(self.ledger, kind="TRANSITION", task_id="SVC-0001",
                            actor="operator", observed_at=self.at,
                            evidence_refs=["SOURCE:check"], to_state="IN_PROGRESS")
        for field, value in (("actor", "forged-actor"), ("sequence", 9),
                             ("previous_digest", "f" * 64), ("digest", "f" * 64)):
            with self.subTest(field=field):
                mutated = deepcopy(nxt)
                mutated["events"][0][field] = value
                with self.assertRaises(ServiceContinuationLedgerError):
                    validate_ledger(mutated)
        bad = deepcopy(nxt)
        bad["event_chain_head"] = GENESIS
        with self.assertRaises(ServiceContinuationLedgerError):
            validate_ledger(bad)

    def test_arbitrary_authority_or_effect_change_is_denied(self):
        for field, value in (("authority_effect", "ALLOW"), ("runtime_effect", "EXECUTED")):
            fake = deepcopy(self.ledger)
            fake[field] = value
            with self.assertRaises(ServiceContinuationLedgerError):
                validate_ledger(fake)
        fake = deepcopy(self.ledger)
        fake["tasks"][0]["authorization_gate"] = "NONE_READ_ONLY"
        fake["tasks"][0]["effect_class"] = "MERGE"
        with self.assertRaises(ServiceContinuationLedgerError):
            validate_ledger(fake)

    def test_blocked_task_cannot_be_promoted_before_dependencies(self):
        with self.assertRaises(ServiceContinuationLedgerError):
            propose_event(self.ledger, kind="TRANSITION", task_id="SVC-0002",
                          actor="operator", observed_at=self.at,
                          evidence_refs=["TEST:fixture"], to_state="READY")
        with self.assertRaises(ServiceContinuationLedgerError):
            propose_event(self.ledger, kind="TRANSITION", task_id="SVC-0014",
                          actor="operator", observed_at=self.at,
                          evidence_refs=["SOURCE:manual"], to_state="IN_PROGRESS")

    def test_no_direct_completed_or_verified_without_evidence(self):
        with self.assertRaises(ServiceContinuationLedgerError):
            propose_event(self.ledger, kind="TRANSITION", task_id="SVC-0001",
                          actor="model", observed_at=self.at, evidence_refs=[],
                          to_state="COMPLETE")
        in_progress = propose_event(self.ledger, kind="TRANSITION", task_id="SVC-0001",
                                    actor="operator", observed_at=self.at,
                                    evidence_refs=["TEST:start"], to_state="IN_PROGRESS")
        with self.assertRaises(ServiceContinuationLedgerError):
            propose_event(in_progress, kind="TRANSITION", task_id="SVC-0001",
                          actor="operator", observed_at=self.at, evidence_refs=[],
                          to_state="VERIFIED")
        verified = propose_event(in_progress, kind="TRANSITION", task_id="SVC-0001",
                                 actor="operator", observed_at=self.at,
                                 evidence_refs=["TEST:exact-verification"], to_state="VERIFIED")
        with self.assertRaises(ServiceContinuationLedgerError):
            propose_event(verified, kind="TRANSITION", task_id="SVC-0001",
                          actor="operator", observed_at=self.at,
                          evidence_refs=["SIGNED:signature-not-completion"], to_state="COMPLETE")
        done = propose_event(verified, kind="TRANSITION", task_id="SVC-0001",
                             actor="operator", observed_at=self.at,
                             evidence_refs=["TEST:independently-read-result"], to_state="COMPLETE")
        self.assertEqual(validate_ledger(done)["SVC-0001"], "COMPLETE")

    def test_effectful_task_cannot_complete_without_operator_reference(self):
        fake = deepcopy(self.ledger)
        fake["tasks"] = [x for x in fake["tasks"] if x["task_id"] == "SVC-0016"]
        # Baseline-only fixture reuses a real effectful task without dependencies.
        validate_ledger(fake)
        in_progress = propose_event(fake, kind="TRANSITION", task_id="SVC-0016",
                                    actor="reviewer", observed_at=self.at,
                                    evidence_refs=["SOURCE:branch"], to_state="IN_PROGRESS")
        verified = propose_event(in_progress, kind="TRANSITION", task_id="SVC-0016",
                                 actor="reviewer", observed_at=self.at,
                                 evidence_refs=["TEST:source-tests"], to_state="VERIFIED")
        with self.assertRaises(ServiceContinuationLedgerError):
            propose_event(verified, kind="TRANSITION", task_id="SVC-0016",
                          actor="reviewer", observed_at=self.at,
                          evidence_refs=["CI:green"], to_state="COMPLETE")
        accepted = propose_event(verified, kind="TRANSITION", task_id="SVC-0016",
                                 actor="reviewer", observed_at=self.at,
                                 evidence_refs=["CI:green", "OPERATOR:exact-source-approval"],
                                 to_state="COMPLETE")
        self.assertEqual(validate_ledger(accepted)["SVC-0016"], "COMPLETE")

    def test_register_future_task_is_event_not_baseline_rewrite(self):
        task = {
            **self.ledger["tasks"][0],
            "task_id": "SVC-0017",
            "title": "Future independent research",
            "dependencies": [],
            "scope": "FUTURE-NOT-LAUNCHED",
        }
        proposal = propose_event(self.ledger, kind="REGISTER_TASK", task_id="SVC-0017",
                                 task=task, actor="operator", observed_at=self.at,
                                 evidence_refs=["SOURCE:new-operator-requirement"])
        self.assertEqual(len(validate_ledger(proposal)), 17)
        self.assertIn("SVC-0017", {x["task_id"] for x in next_ready_tasks(proposal)})
        assert_append_only(self.ledger, proposal)

    def test_task_mutation_and_erased_event_history_denied(self):
        proposal = propose_event(self.ledger, kind="TRANSITION", task_id="SVC-0001",
                                 actor="operator", observed_at=self.at,
                                 evidence_refs=["TEST:check"], to_state="IN_PROGRESS")
        clone = deepcopy(proposal)
        clone["tasks"][0]["title"] = "rewritten original"
        with self.assertRaises(ServiceContinuationLedgerError):
            assert_append_only(self.ledger, clone)
        clone = deepcopy(proposal)
        clone["events"] = []
        clone["revision"] = 1
        clone["event_chain_head"] = GENESIS
        with self.assertRaises(ServiceContinuationLedgerError):
            assert_append_only(self.ledger, clone)

    def test_cycle_duplicate_refs_and_invalid_status_denied(self):
        clone = deepcopy(self.ledger)
        clone["tasks"][0]["dependencies"] = ["SVC-0002"]
        with self.assertRaises(ServiceContinuationLedgerError):
            validate_ledger(clone)
        clone = deepcopy(self.ledger)
        clone["tasks"][0]["source_refs"] = ["untyped-evidence"]
        with self.assertRaises(ServiceContinuationLedgerError):
            validate_ledger(clone)
        clone = deepcopy(self.ledger)
        clone["tasks"][0]["initial_state"] = "COMPLETE"
        with self.assertRaises(ServiceContinuationLedgerError):
            validate_ledger(clone)

    def test_cli_validate_next_and_propose_are_read_only(self):
        for cmd in (["validate"], ["next"],
                    ["propose-transition", "--task", "SVC-0015", "--to", "IN_PROGRESS",
                     "--actor", "operator", "--at", self.at,
                     "--evidence-ref", "SOURCE:manual-readback"]):
            p = subprocess.run([sys.executable, str(CLI), *cmd],
                               cwd=ROOT, capture_output=True, text=True, timeout=12)
            self.assertEqual(p.returncode, 0, p.stderr)
            value = json.loads(p.stdout)
            self.assertIn("authority_effect", value) if cmd[0] != "propose-transition" else self.assertEqual(value["authority_effect"], "NONE")
        self.assertEqual(LEDGER.read_bytes(), self.source)

    def test_schema_file_is_valid_json_schema_or_declared(self):
        schema = json.loads((ROOT / "LION/architecture/v1_5/SERVICE_CONTINUATION_LEDGER.schema.json").read_text("utf-8"))
        self.assertTrue(schema["$id"].endswith("/service-continuation-ledger-v1.schema.json"))
        self.assertEqual(schema["properties"]["authority_effect"]["const"], "NONE")
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(self.ledger)


    def test_formalization_registry_routes_six_surfaces_and_digest(self):
        from cyber_lion.contracts.formalization_registry import FormalizationRegistry
        reg_data = json.loads((ROOT / "LION/architecture/v1_5/FORMALIZATION_REGISTRY_FEDERATION_R1.json").read_text("utf-8"))
        registry = FormalizationRegistry.from_dict(reg_data)
        self.assertEqual(registry.registry_digest, registry.compute_digest())
        owners = [x for x in reg_data["entries"] if x["semantic_owner_concept"] == "service_continuation"]
        self.assertEqual(len(owners), 6)
        self.assertEqual(len({x["artifact_id"] for x in owners}), 6)
        self.assertTrue(all((ROOT / x["path"]).is_file() for x in owners))
        self.assertTrue(all("cyber_lion/tests/test_service_continuation_ledger.py" in x["validation_refs"] for x in owners))

    def test_service_ledger_has_one_declared_semantic_owner(self):
        owners = json.loads((ROOT / "LION/architecture/v1_5/semantic_owners.json").read_text("utf-8"))
        matching = [x for x in owners["owners"] if x["concept"] == "service_continuation"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["primary"], "cyber_lion/contracts/service_continuation_ledger.py")
        self.assertIn("LION/architecture/v1_5/SERVICE_CONTINUATION_LEDGER_R1.json", matching[0]["secondary"])

    def test_human_entrypoints_and_contract_map_route_to_owner(self):
        for path in ("README.md", "LION/README.md", "LION/architecture/v1_5/README.md",
                     "AGENTS.md", "LION/AGENTS.md", "LION/codex/CODEX_RUNBOOK.md",
                     "cyber_lion/CONTRACT_MAP.md", "LION/architecture/v1_5/FEDERATED_ARCHITECTURE_TARGET.md"):
            with self.subTest(path=path):
                self.assertIn("SERVICE_CONTINUATION_LEDGER", (ROOT / path).read_text("utf-8"))
        guide = (ROOT / "LION/architecture/v1_5/SERVICE_CONTINUATION_LEDGER.md").read_text("utf-8")
        self.assertIn("not an event dispatcher", guide)
        self.assertIn("TRUST CHANGE", guide)
        self.assertIn("NOT permission to provision", guide)

    def test_future_chronology_and_old_task_id_are_denied(self):
        earlier = "2026-01-01T00:00:00Z"
        with self.assertRaises(ServiceContinuationLedgerError):
            propose_event(self.ledger, kind="TRANSITION", task_id="SVC-0001",
                          actor="operator", observed_at=earlier,
                          evidence_refs=["SOURCE:old"], to_state="IN_PROGRESS")
        task = {**self.ledger["tasks"][0], "task_id": "SVC-0000",
                "dependencies": [], "title": "Out of order"}
        with self.assertRaises(ServiceContinuationLedgerError):
            propose_event(self.ledger, kind="REGISTER_TASK", task_id="SVC-0000",
                          actor="operator", observed_at=self.at,
                          evidence_refs=["SOURCE:old"], task=task)


if __name__ == "__main__":
    unittest.main()
