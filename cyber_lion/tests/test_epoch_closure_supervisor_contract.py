from __future__ import annotations

import hashlib
import json
import sqlite3
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import importlib
sys.modules.setdefault("mission_control_compat", importlib.import_module("lion_mission_control_compat"))

from cyber_lion.contracts.phase_execution_contract import (
    compile_panel_phase_contracts,
    preflight_execution_contracts,
)
from cyber_lion.mission_control.mission_reconciliation import (
    EPOCH_CLOSURE_CHECKS,
    EPOCH_CLOSURE_EVENT,
    EPOCH_CLOSURE_SCHEMA,
    _epoch_closure_check_values,
    _epoch_closure_evidence,
)
from tools import lion_mission_control_v3 as mission_control


class EpochClosureSupervisorContractTests(unittest.TestCase):
    def _conn(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """CREATE TABLE protocol_messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                protocol TEXT NOT NULL,
                from_id TEXT NOT NULL,
                to_id TEXT NOT NULL,
                phase TEXT,
                payload_json TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                observed_at TEXT NOT NULL
            )"""
        )
        return conn

    def _payload(self, *, head="a" * 40, tree="b" * 40, checks=None):
        values = {name: "PASS" for name in EPOCH_CLOSURE_CHECKS}
        if checks:
            values.update(checks)
        return {
            "schema": EPOCH_CLOSURE_SCHEMA,
            "event": EPOCH_CLOSURE_EVENT,
            "source_head": head,
            "source_tree": tree,
            "checks": values,
            "evidence_refs": [
                "github:DonkeyJJLove/ai_platform@exact-head",
                "sentinelx:MOON:r24-worker-currentness",
                "mission-control:8766:mission-db-readback",
            ],
            "authority_effect": "NONE",
        }

    def _insert(self, conn, payload, *, phase="FREEZE", from_id="CHATGPT_SAAS_SUPERVISOR"):
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        conn.execute(
            "INSERT INTO protocol_messages(mission_id,protocol,from_id,to_id,phase,payload_json,payload_digest,observed_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                "M1",
                "EVIDENCE",
                from_id,
                "MISSION_CONTROL",
                phase,
                raw,
                hashlib.sha256(raw.encode()).hexdigest(),
                "2026-09-25T12:00:00Z",
            ),
        )
        conn.commit()

    def test_exact_source_authority_free_package_is_accepted(self):
        conn = self._conn()
        self._insert(conn, self._payload())
        mission = {"source_head": "a" * 40, "source_tree": "b" * 40}
        evidence = _epoch_closure_evidence(conn, "M1", "FREEZE", mission)
        self.assertIsNotNone(evidence)
        values = _epoch_closure_check_values(evidence)
        self.assertTrue(values["EPOCH_CLOSURE_PLAN_RECONCILED"])

    def test_stale_source_or_wrong_sender_fails_closed(self):
        conn = self._conn()
        self._insert(conn, self._payload(head="c" * 40))
        self._insert(conn, self._payload(), from_id="MODEL_PROPOSAL")
        mission = {"source_head": "a" * 40, "source_tree": "b" * 40}
        self.assertIsNone(_epoch_closure_evidence(conn, "M1", "FREEZE", mission))

    def test_partial_check_vector_does_not_promote_terminal_reconciliation(self):
        values = _epoch_closure_check_values(
            self._payload(checks={"P07_CONTRADICTION_MATRIX_VERIFIED": "UNKNOWN"})
        )
        self.assertFalse(values["P07_CONTRADICTION_MATRIX_VERIFIED"])
        self.assertFalse(values["EPOCH_CLOSURE_PLAN_RECONCILED"])

    def test_lpcl12_epoch_closure_capability_preflights_ready_bound(self):
        pairs = {
            "PHASE_01_EXECUTION_CLASS": "VERIFY",
            "PHASE_01_CAPABILITY_CLASS": "EPOCH_CLOSURE_RECONCILIATION",
            "PHASE_01_EFFECT_CEILING": "NONE",
            "PHASE_01_BINDING_MODE": "DYNAMIC",
            "PHASE_01_ON_MISSING_CAPABILITY": "WAIT_AND_DISCOVER",
            "PHASE_01_AUTO_RESUME": "TRUE",
            "PHASE_01_VERIFY_BEFORE_MUTATE": "TRUE",
            "PHASE_01_CURRENTNESS": "EXACT_EPOCH_SOURCE",
            "PHASE_01_EVIDENCE": "EPOCH_CLOSURE_EVIDENCE",
            "PHASE_01_COMPLETION_01": "EPOCH_BOOTSTRAP_VERIFIED=PASS",
        }
        contracts = compile_panel_phase_contracts(
            pairs, "EPOCH-CLOSURE-TEST", [{"id": "FREEZE"}], "LPCL/1.2"
        )
        preflight = preflight_execution_contracts(
            contracts, mission_control.PROCESS_CAPABILITY_REGISTRY
        )
        self.assertEqual(preflight.invalid_count, 0)
        self.assertEqual(preflight.unbound_count, 0)
        self.assertEqual(preflight.bound_count, 1)
        self.assertEqual(preflight.mission_readiness, "READY_BOUND")
        cap = mission_control.PROCESS_CAPABILITY_REGISTRY["EPOCH_CLOSURE_RECONCILIATION"][0]
        self.assertEqual(cap["capability_id"], "GENERIC_MISSION_CONTRACT_RECONCILIATION")
        self.assertEqual(cap["effect_ceiling"], "NONE")


    def test_full_supervisor_lpcl_compiles_all_eighteen_phases_ready_bound(self):
        source = (ROOT / "LION/architecture/v1_4/EPOCH_CLOSURE_SUPERVISOR_LPCL_1_2.lpcl").read_text(encoding="utf-8")
        pairs = mission_control._lpcl_pairs(source)
        phases = []
        for ordinal in range(1, 19):
            raw = pairs[f"PHASE_{ordinal:02d}"]
            phase_id = raw.split("|", 1)[0].strip()
            phases.append({"id": phase_id})
        contracts = compile_panel_phase_contracts(
            pairs, pairs["MISSION_ID"], phases, pairs["CONTROL_LANGUAGE"]
        )
        preflight = preflight_execution_contracts(
            contracts, mission_control.PROCESS_CAPABILITY_REGISTRY
        )
        self.assertEqual(len(contracts), 18)
        self.assertEqual(preflight.invalid_count, 0)
        self.assertEqual(preflight.unbound_count, 0)
        self.assertEqual(preflight.bound_count, 18)
        self.assertEqual(preflight.mission_readiness, "READY_BOUND")
        self.assertTrue(all(c.effect_ceiling == "NONE" for c in contracts))


if __name__ == "__main__":
    unittest.main()
