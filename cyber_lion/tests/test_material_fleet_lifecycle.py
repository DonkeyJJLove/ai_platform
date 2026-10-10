"""R6 source-only mission-scoped fleet demand, admission and HTTP projection tests."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch

from cyber_lion.mission_control import application_factory_program as program
from cyber_lion.mission_control import material_fleet_lifecycle as lifecycle

HEAD = "a" * 40
TREE = "b" * 40
OLD_HEAD = "c" * 40
OLD_TREE = "d" * 40
UTC = datetime(2026, 10, 8, 13, 50, tzinfo=timezone.utc)
MID = program.MISSION_ID


def carrier(*, head=HEAD, tree=TREE, ready=0, at=UTC, duplicate=False):
    workers = []
    for i in range(1, 33):
        cid = f"{i:064x}"
        workers.append({
            "material_worker_id": f"MD{i:03d}",
            "container_id": cid,
            "container_state": "running" if ready else "exited",
            "ready": bool(ready),
            "model": "gpt-oss-20b-MXFP4",
        })
    if duplicate:
        workers[-1]["container_id"] = workers[0]["container_id"]
    value = {
        "schema": lifecycle.CARRIER_SCHEMA,
        "physical_host": "MOON",
        "observed_at": at.isoformat(),
        "source_head": head,
        "source_tree": tree,
        "state": "READY" if ready else "DEGRADED",
        "ready": 32 if ready else 0,
        "materialized": 32,
        "workers": workers,
    }
    value["currentness_digest"] = lifecycle._digest(value)
    return value


class MaterialFleetLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE missions(
             mission_id TEXT PRIMARY KEY, state TEXT, source_head TEXT, source_tree TEXT,
             spec_digest TEXT, material_target INTEGER);
            CREATE TABLE mission_process_specs(
             mission_id TEXT PRIMARY KEY, lpcl_text TEXT, authority_state TEXT, current_phase TEXT);
            CREATE TABLE mission_phases(mission_id TEXT, phase_id TEXT, status TEXT, ordinal INTEGER);
            CREATE TABLE mission_phase_execution_contracts(
             mission_id TEXT, phase_id TEXT, ordinal INTEGER, contract_version TEXT,
             execution_class TEXT, capability_classes_json TEXT, effect_ceiling TEXT,
             binding_mode TEXT, on_missing_capability TEXT, auto_resume INTEGER,
             verify_before_mutate INTEGER, currentness_requirements_json TEXT,
             evidence_requirements_json TEXT, completion_predicates_json TEXT,
             contract_source TEXT, contract_digest TEXT, compiler_version TEXT);
            CREATE TABLE mission_execution_drivers(
             mission_id TEXT PRIMARY KEY, state TEXT, generation INTEGER, current_phase TEXT,
             lease_owner TEXT, lease_expires_at TEXT, checkpoint_digest TEXT);
            CREATE TABLE mission_operator_control(
             mission_id TEXT PRIMARY KEY, control_epoch INTEGER, pause_latch INTEGER, stop_latch INTEGER);
            CREATE TABLE mission_scheduler_state(state TEXT, heartbeat_at TEXT);
            CREATE TABLE mission_execution_assignments(
             mission_id TEXT, phase_id TEXT, state TEXT);
            CREATE TABLE mission_recon_material_leases(mission_id TEXT, state TEXT);
            """
        )
        self.lpcl = program.panel_lpcl_text()
        self.lpcl_digest = sha256(self.lpcl.encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO missions VALUES(?,?,?,?,?,?)",
            (MID, "RUNNING", HEAD, TREE, self.lpcl_digest, 32),
        )
        self.db.execute(
            "INSERT INTO mission_process_specs VALUES(?,?,?,?)",
            (MID, self.lpcl, "EXPLICIT_USER_ACTIVATION", program.PHASES[0].phase_id),
        )
        self.phase(0)
        self.db.execute(
            "INSERT INTO mission_execution_drivers VALUES(?,?,?,?,?,?,?)",
            (MID, "ACTIVE", 1, program.PHASES[0].phase_id,
             "global-mission-driver", (UTC + timedelta(seconds=25)).isoformat(), None),
        )
        self.db.execute(
            "INSERT INTO mission_operator_control VALUES(?,?,?,?)",
            (MID, 1, 0, 0),
        )
        self.db.execute(
            "INSERT INTO mission_scheduler_state VALUES(?,?)",
            ("ACTIVE", UTC.isoformat()),
        )
        self.db.commit()

    def phase(self, index):
        self.db.execute("DELETE FROM mission_phases WHERE mission_id=?", (MID,))
        self.db.execute("DELETE FROM mission_phase_execution_contracts WHERE mission_id=?", (MID,))
        for n, spec in enumerate(program.PHASES):
            status = "PASS" if n < index else "RUNNING" if n == index else "PENDING"
            self.db.execute(
                "INSERT INTO mission_phases VALUES(?,?,?,?)",
                (MID, spec.phase_id, status, n + 1),
            )
            compiled = program.panel_contracts()[n].as_dict()
            self.db.execute(
                "INSERT INTO mission_phase_execution_contracts VALUES(" + ",".join(["?"] * 17) + ")",
                (
                    MID, spec.phase_id, n + 1, compiled["contract_version"],
                    compiled["execution_class"], json.dumps(compiled["capability_classes"]),
                    compiled["effect_ceiling"], compiled["binding_mode"],
                    compiled["on_missing_capability"], int(compiled["auto_resume"]),
                    int(compiled["verify_before_mutate"]),
                    json.dumps(compiled["currentness_requirements"]),
                    json.dumps(compiled["evidence_requirements"]),
                    json.dumps(compiled["completion_predicates"]),
                    compiled["contract_source"], compiled["contract_digest"],
                    compiled["compiler_version"],
                ),
            )
        if index < len(program.PHASES):
            self.db.execute(
                "UPDATE mission_execution_drivers SET current_phase=? WHERE mission_id=?",
                (program.PHASES[index].phase_id, MID),
            )
            self.db.execute(
                "UPDATE mission_process_specs SET current_phase=? WHERE mission_id=?",
                (program.PHASES[index].phase_id, MID),
            )
        self.db.commit()

    def preview(self, *, fleet=None, source=None, at=UTC):
        return lifecycle.project_lifecycle(
            self.db, MID, fleet_carrier=carrier() if fleet is None else fleet,
            current_source={"head": HEAD, "tree": TREE} if source is None else source,
            at=at,
        )

    def test_unregistered_mission_has_no_worker_demand_or_effect(self):
        r = lifecycle.project_lifecycle(
            self.db, "NONEXISTENT", fleet_carrier=carrier(),
            current_source={"head": HEAD, "tree": TREE}, at=UTC,
        )
        self.assertEqual((r["state"], r["desired_workers"], r["candidate_transition"]),
                         ("UNREGISTERED", None, "NONE"))
        self.assertEqual(r["blockers"], ["MISSION_NOT_REGISTERED"])

    def test_phase_zero_cognitive_needs_no_worker(self):
        r = self.preview()
        self.assertEqual(r["state"], "NO_MATERIAL_EXECUTION_REQUIRED")
        self.assertEqual(r["desired_workers"], 0)
        self.assertEqual(r["observed_fleet"]["state"], "PARKED_OBSERVED")
        self.assertEqual(r["blockers"], [])
        self.assertFalse(r["effect_admitted"])

    def test_phase_zero_existing_full_fleet_is_only_park_proposal(self):
        r = self.preview(fleet=carrier(ready=32))
        self.assertEqual(r["candidate_transition"], "PARK_AFTER_INDEPENDENT_ADMISSION")
        self.assertEqual(r["execution_effect"], "NONE")

    def test_single_worker_preactivation_is_one_not_32(self):
        self.phase(1)
        r = self.preview()
        self.assertEqual(r["phase_id"], program.PHASES[1].phase_id)
        self.assertEqual(r["desired_workers"], 1)
        self.assertEqual(r["state"], "AWAIT_SINGLE_WORKER_QUALIFICATION")
        self.assertEqual(r["candidate_transition"], "PREACTIVATE_ONE_AFTER_INDEPENDENT_ADMISSION")
        self.assertFalse(r["effect_admitted"])

    def test_full_fleet_is_required_only_from_phase_three(self):
        self.phase(2)
        r = self.preview()
        self.assertEqual(r["desired_workers"], 32)
        self.assertEqual(r["state"], "AWAIT_FULL_FLEET_PROVIDER_READINESS")
        self.assertEqual(r["candidate_transition"], "DEPLOY_32_AFTER_INDEPENDENT_ADMISSION")

    def test_build_and_verify_remain_32_and_never_mint_admission(self):
        for ix in (3, 4):
            with self.subTest(phase=ix):
                self.phase(ix)
                r = self.preview(fleet=carrier(ready=32))
                self.assertEqual(r["desired_workers"], 32)
                self.assertFalse(r["effect_admitted"])

    def test_source_drift_fails_closed(self):
        r = self.preview(source={"head": OLD_HEAD, "tree": OLD_TREE})
        self.assertIn("CURRENT_RUNTIME_SOURCE_UNVERIFIED_OR_DRIFT", r["blockers"])
        self.assertEqual(r["candidate_transition"], "NONE")

    def test_no_trusted_runtime_source_fails_closed(self):
        r = lifecycle.project_lifecycle(
            self.db, MID, fleet_carrier=carrier(), at=UTC,
        )
        self.assertIn("CURRENT_RUNTIME_SOURCE_UNVERIFIED_OR_DRIFT", r["blockers"])

    def test_historical_worker_source_cannot_masquerade_as_ready(self):
        self.phase(2)
        r = self.preview(fleet=carrier(head=OLD_HEAD, tree=OLD_TREE, ready=32))
        self.assertIn("FLEET_WORKER_SOURCE_DRIFT", r["blockers"])
        self.assertEqual(r["state"], "BLOCKED")

    def test_unactivated_lpcl_never_proposes_effect(self):
        self.db.execute(
            "UPDATE mission_process_specs SET authority_state='NONE' WHERE mission_id=?", (MID,),
        )
        self.db.commit()
        r = self.preview(fleet=carrier(ready=32))
        self.assertIn("LPCL_NOT_EXPLICITLY_ACTIVATED", r["blockers"])
        self.assertEqual(r["candidate_transition"], "NONE")

    def test_lpcl_digest_mismatch_fails_closed(self):
        self.db.execute(
            "UPDATE missions SET spec_digest=? WHERE mission_id=?", ("0" * 64, MID),
        )
        self.db.commit()
        self.assertIn("LPCL_SOURCE_DIGEST_MISMATCH", self.preview()["blockers"])

    def test_phase_contract_drift_fails_closed(self):
        self.db.execute(
            "UPDATE mission_phase_execution_contracts SET effect_ceiling='BOUNDED_MATERIAL' "
            "WHERE mission_id=? AND phase_id=?", (MID, program.PHASES[0].phase_id),
        )
        self.db.commit()
        self.assertIn("PHASE_CONTRACT_SEMANTIC_DRIFT", self.preview()["blockers"])

    def test_unknown_capability_fails_closed(self):
        modified = replace(
            program.panel_contracts()[0],
            capability_classes=("SYNTHETIC_NEW_CAPABILITY",),
        ).as_dict()
        self.db.execute(
            "UPDATE mission_phase_execution_contracts SET capability_classes_json=?,contract_digest=? "
            "WHERE mission_id=? AND phase_id=?",
            (json.dumps(modified["capability_classes"]), modified["contract_digest"],
             MID, program.PHASES[0].phase_id),
        )
        self.db.commit()
        self.assertIn("PHASE_CAPABILITY_NOT_MAPPED", self.preview()["blockers"])

    def test_operator_stop_latch_blocks_even_read_only_candidate(self):
        self.db.execute(
            "UPDATE mission_operator_control SET stop_latch=1 WHERE mission_id=?", (MID,),
        )
        self.db.commit()
        self.assertIn("OPERATOR_PAUSE_OR_STOP_LATCH", self.preview()["blockers"])

    def test_driver_wrong_phase_blocks(self):
        self.db.execute(
            "UPDATE mission_execution_drivers SET current_phase='FOREIGN' WHERE mission_id=?", (MID,),
        )
        self.db.commit()
        self.assertIn("MISSION_DRIVER_PHASE_DRIFT", self.preview()["blockers"])

    def test_stale_scheduler_heartbeat_blocks(self):
        self.db.execute(
            "UPDATE mission_scheduler_state SET heartbeat_at=?",
            ((UTC - timedelta(minutes=4)).isoformat(),),
        )
        self.db.commit()
        self.assertIn("GLOBAL_SCHEDULER_HEARTBEAT_STALE", self.preview()["blockers"])

    def test_tampered_carrier_digest_cannot_claim_ready(self):
        f = carrier(ready=32)
        f["ready"] = 0
        self.phase(2)
        r = self.preview(fleet=f)
        self.assertEqual(r["observed_fleet"]["state"], "INVALID")
        self.assertIn("FLEET_OBSERVATION_UNAVAILABLE_OR_INVALID", r["blockers"])

    def test_stale_carrier_blocks_material_stage(self):
        self.phase(2)
        r = self.preview(fleet=carrier(at=UTC - timedelta(minutes=5)))
        self.assertEqual(r["observed_fleet"]["state"], "STALE")
        self.assertIn("FLEET_OBSERVATION_UNAVAILABLE_OR_INVALID", r["blockers"])

    def test_duplicate_container_identity_is_invalid(self):
        r = self.preview(fleet=carrier(duplicate=True))
        self.assertEqual(r["observed_fleet"]["state"], "INVALID")

    def test_terminal_phase_is_zero_only_after_reconciliation(self):
        self.phase(4)
        self.db.execute("UPDATE mission_phases SET status='PASS' WHERE mission_id=?", (MID,))
        self.db.execute("UPDATE missions SET state='COMPLETE' WHERE mission_id=?", (MID,))
        self.db.execute(
            "UPDATE mission_execution_drivers SET state='COMPLETE',checkpoint_digest=? WHERE mission_id=?",
            ("e" * 64, MID),
        )
        self.db.commit()
        r = self.preview(fleet=carrier(ready=32))
        self.assertEqual(r["desired_workers"], 0)
        self.assertEqual(r["phase_id"], "TERMINAL")
        self.assertEqual(r["candidate_transition"], "PARK_AFTER_INDEPENDENT_ADMISSION")

    def test_unfinished_assignment_blocks_terminal_park(self):
        self.db.execute("UPDATE mission_phases SET status='PASS' WHERE mission_id=?", (MID,))
        self.db.execute("UPDATE missions SET state='COMPLETE' WHERE mission_id=?", (MID,))
        self.db.execute(
            "UPDATE mission_execution_drivers SET state='COMPLETE',checkpoint_digest=? WHERE mission_id=?",
            ("e" * 64, MID),
        )
        self.db.execute(
            "INSERT INTO mission_execution_assignments VALUES(?,?,?)", (MID, "BUILD_CROSS_MODEL_ARTIFACT", "CLAIMED"),
        )
        self.db.commit()
        r = self.preview(fleet=carrier(ready=32))
        self.assertIn("INFLIGHT_ASSIGNMENTS_OR_LEASES_NOT_RECONCILED", r["blockers"])
        self.assertEqual(r["candidate_transition"], "NONE")

    def test_active_material_lease_blocks_terminal_park(self):
        self.db.execute("UPDATE mission_phases SET status='PASS' WHERE mission_id=?", (MID,))
        self.db.execute("UPDATE missions SET state='COMPLETE' WHERE mission_id=?", (MID,))
        self.db.execute(
            "UPDATE mission_execution_drivers SET state='COMPLETE',checkpoint_digest=? WHERE mission_id=?",
            ("e" * 64, MID),
        )
        self.db.execute(
            "INSERT INTO mission_recon_material_leases VALUES(?,?)", (MID, "ACTIVE"),
        )
        self.db.commit()
        self.assertIn("INFLIGHT_ASSIGNMENTS_OR_LEASES_NOT_RECONCILED", self.preview()["blockers"])

    def test_foreign_mission_assignment_blocks_shared_fleet_parking(self):
        self.db.execute("UPDATE mission_phases SET status='PASS' WHERE mission_id=?", (MID,))
        self.db.execute("UPDATE missions SET state='COMPLETE' WHERE mission_id=?", (MID,))
        self.db.execute(
            "UPDATE mission_execution_drivers SET state='COMPLETE',checkpoint_digest=? WHERE mission_id=?",
            ("e" * 64, MID),
        )
        self.db.execute(
            "INSERT INTO missions VALUES(?,?,?,?,?,?)",
            ("OTHER-ACTIVE-MISSION", "RUNNING", HEAD, TREE, "f" * 64, 32),
        )
        self.db.execute(
            "INSERT INTO mission_execution_assignments VALUES(?,?,?)",
            ("OTHER-ACTIVE-MISSION", "BUILD", "CLAIMED"),
        )
        self.db.commit()
        r = self.preview(fleet=carrier(ready=32))
        self.assertIn("SHARED_FLEET_FOREIGN_MISSION_WORK_INFLIGHT", r["blockers"])
        self.assertEqual(r["candidate_transition"], "NONE")

    def test_foreign_mission_lease_blocks_shared_fleet_parking(self):
        self.db.execute("UPDATE mission_phases SET status='PASS' WHERE mission_id=?", (MID,))
        self.db.execute("UPDATE missions SET state='COMPLETE' WHERE mission_id=?", (MID,))
        self.db.execute(
            "UPDATE mission_execution_drivers SET state='COMPLETE',checkpoint_digest=? WHERE mission_id=?",
            ("e" * 64, MID),
        )
        self.db.execute(
            "INSERT INTO missions VALUES(?,?,?,?,?,?)",
            ("OTHER-ACTIVE-MISSION", "RUNNING", HEAD, TREE, "f" * 64, 32),
        )
        self.db.execute(
            "INSERT INTO mission_recon_material_leases VALUES(?,?)",
            ("OTHER-ACTIVE-MISSION", "ACTIVE"),
        )
        self.db.commit()
        r = self.preview(fleet=carrier(ready=32))
        self.assertIn("SHARED_FLEET_FOREIGN_MISSION_WORK_INFLIGHT", r["blockers"])

    def test_unreconciled_terminal_driver_is_not_park_authority(self):
        self.db.execute("UPDATE mission_phases SET status='PASS' WHERE mission_id=?", (MID,))
        self.db.execute("UPDATE missions SET state='COMPLETE' WHERE mission_id=?", (MID,))
        self.db.commit()
        r = self.preview(fleet=carrier(ready=32))
        self.assertIn("TERMINAL_RECONCILIATION_NOT_ATTESTED", r["blockers"])
        self.assertEqual(r["candidate_transition"], "NONE")

    def test_expired_driver_lease_cannot_propose_mission_effect(self):
        self.db.execute(
            "UPDATE mission_execution_drivers SET lease_expires_at=? WHERE mission_id=?",
            ((UTC - timedelta(seconds=5)).isoformat(), MID),
        )
        self.db.commit()
        r = self.preview()
        self.assertIn("MISSION_DRIVER_NOT_DISPATCHABLE", r["blockers"])
        self.assertEqual(r["candidate_transition"], "NONE")

    def test_blocked_driver_state_never_proposes_transition(self):
        self.db.execute(
            "UPDATE mission_execution_drivers SET state='BLOCKED' WHERE mission_id=?", (MID,),
        )
        self.db.commit()
        self.assertIn("MISSION_DRIVER_NOT_DISPATCHABLE", self.preview()["blockers"])

    def test_missing_operator_control_currentness_fails_closed(self):
        self.db.execute("DELETE FROM mission_operator_control WHERE mission_id=?", (MID,))
        self.db.commit()
        self.assertIn("OPERATOR_CONTROL_CURRENTNESS_UNKNOWN", self.preview()["blockers"])

    def test_tampered_contract_digest_detected_with_canonical_contract(self):
        self.db.execute(
            "UPDATE mission_phase_execution_contracts SET contract_digest=? "
            "WHERE mission_id=? AND phase_id=?",
            ("0" * 64, MID, program.PHASES[0].phase_id),
        )
        self.db.commit()
        self.assertIn("PHASE_CONTRACT_SEMANTIC_DRIFT", self.preview()["blockers"])

    def test_null_worker_id_is_invalid_not_exception(self):
        f = carrier()
        f["workers"][0]["material_worker_id"] = None
        f["currentness_digest"] = lifecycle._digest(
            {key: value for key, value in f.items() if key != "currentness_digest"}
        )
        result = self.preview(fleet=f)
        self.assertEqual(result["observed_fleet"]["state"], "INVALID")

    def test_historical_parked_fleet_cannot_rebind_to_new_mission(self):
        self.phase(1)
        r = self.preview(fleet=carrier(head=OLD_HEAD, tree=OLD_TREE, ready=0))
        self.assertIn("FLEET_WORKER_SOURCE_DRIFT", r["blockers"])
        self.assertEqual(r["candidate_transition"], "NONE")

    def test_projection_queries_are_read_only_and_digest_sealed(self):
        before = self.db.total_changes
        self.db.execute("PRAGMA query_only=ON")
        r = self.preview()
        self.assertEqual(self.db.total_changes, before)
        supplied = r["projection_digest"]
        body = dict(r)
        body.pop("projection_digest")
        self.assertEqual(supplied, lifecycle._digest(body))
        self.assertEqual(r["authority_effect"], "NONE")

    def test_readonly_query_dispatcher_rejects_unregistered_sql_without_db_write(self):
        before = self.db.total_changes
        with self.assertRaisesRegex(
            lifecycle.FleetLifecycleProjectionError, "unregistered read-only projection query"
        ):
            lifecycle._one(
                self.db,
                "UPDATE missions SET state='COMPLETE' WHERE mission_id=?",
                (MID,),
            )
        self.assertEqual(self.db.total_changes, before)
        self.assertEqual(
            self.db.execute("SELECT state FROM missions WHERE mission_id=?", (MID,)).fetchone()[0],
            "RUNNING",
        )

    def test_no_direct_docker_or_model_executor_in_projection_source(self):
        module = Path(lifecycle.__file__).read_text()
        self.assertNotIn("subprocess.run", module)
        self.assertNotIn("docker stop", module.lower())
        self.assertNotIn("runtime_admission = True", module)


class MaterialFleetLifecycleProbeTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        fixture = MaterialFleetLifecycleTests(
            "test_phase_zero_cognitive_needs_no_worker"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.db_file = self.root / "mission-control.db"
        with sqlite3.connect(self.db_file) as target:
            fixture.db.backup(target)
        self.carrier_file = self.root / "fleet-currentness.json"
        self.carrier_file.write_text(json.dumps(carrier()), encoding="utf-8")

    def test_cli_reads_real_sqlite_fixture_without_db_mutation(self):
        from tools import lion_material_fleet_lifecycle_probe as probe
        before = sha256(self.db_file.read_bytes()).hexdigest()
        result = probe.project_from_database(
            db_path=str(self.db_file), mission_id=MID,
            fleet_carrier_path=str(self.carrier_file), now=UTC,
        )
        after = sha256(self.db_file.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["effect_admitted"])
        self.assertIn("CURRENT_RUNTIME_SOURCE_UNVERIFIED_OR_DRIFT", result["blockers"])

    def test_cli_missing_database_does_not_create_one(self):
        from tools import lion_material_fleet_lifecycle_probe as probe
        target = self.root / "not-a-mission.db"
        with self.assertRaises(probe.ProbeError):
            probe.project_from_database(db_path=str(target), mission_id=MID, now=UTC)
        self.assertFalse(target.exists())

    def test_cli_symlinked_database_is_denied(self):
        from tools import lion_material_fleet_lifecycle_probe as probe
        target = self.root / "pointer.db"
        target.symlink_to(self.db_file)
        with self.assertRaises(probe.ProbeError):
            probe.project_from_database(db_path=str(target), mission_id=MID, now=UTC)

    def test_cli_rejects_malformed_fleet_carrier(self):
        from tools import lion_material_fleet_lifecycle_probe as probe
        self.carrier_file.write_text("not-json", encoding="utf-8")
        with self.assertRaises(probe.ProbeError):
            probe.project_from_database(
                db_path=str(self.db_file), mission_id=MID,
                fleet_carrier_path=str(self.carrier_file), now=UTC,
            )

    def test_cli_fail_if_blocked_exits_nonzero_with_bounded_projection(self):
        import os
        import subprocess
        target = Path(__file__).resolve().parents[2] / "tools" / "lion_material_fleet_lifecycle_probe.py"
        result = subprocess.run(
            [
                sys.executable, "-B", str(target),
                "--db", str(self.db_file),
                "--mission-id", MID,
                "--fleet-carrier", str(self.carrier_file),
                "--fail-if-blocked",
            ], capture_output=True, text=True, timeout=10,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["authority_effect"], "NONE")
        self.assertEqual(output["execution_effect"], "NONE")
        self.assertEqual(output["state"], "BLOCKED")

    def test_cli_has_no_self_attested_source_or_mutation_flags(self):
        import subprocess
        target = Path(__file__).resolve().parents[2] / "tools" / "lion_material_fleet_lifecycle_probe.py"
        result = subprocess.run(
            [
                sys.executable, "-B", str(target), "--db", str(self.db_file),
                "--mission-id", MID, "--source-head", HEAD,
            ], capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)

    def test_current_mission_control_uses_existing_phase_projection_without_effect(self):
        src = (Path(__file__).resolve().parents[2] / "tools" /
               "lion_mission_control_v3.py").read_text(encoding="utf-8")
        self.assertIn("material_fleet_lifecycle as scoped_fleet", src)
        self.assertIn("mission_material_fleet_lifecycle_snapshot", src)
        self.assertIn("scoped_fleet.project_lifecycle(", src)
        self.assertIn("fleet_carrier=None,current_source=None", src)
        self.assertNotIn("scoped_fleet.deploy", src)
        self.assertNotIn("scoped_fleet.issue_admission", src)

    def test_real_mission_control_projection_reads_exact_0_1_32_phase_contracts(self):
        import importlib
        tools = Path(__file__).resolve().parents[2] / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        sys.modules["mission_control_compat"] = importlib.import_module(
            "lion_mission_control_compat"
        )
        mc = importlib.import_module("lion_mission_control_v3")
        fixture = MaterialFleetLifecycleTests("test_phase_zero_cognitive_needs_no_worker")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for index, expected in enumerate((0, 1, 32, 32, 32)):
            fixture.phase(index)
            count_before = fixture.db.total_changes
            projected = mc.mission_material_fleet_lifecycle_snapshot(fixture.db, MID)
            self.assertEqual(projected["desired_workers"], expected)
            self.assertEqual(projected["phase_id"], program.PHASES[index].phase_id)
            self.assertEqual(projected["state"], "BLOCKED")
            self.assertIn("CURRENT_RUNTIME_SOURCE_UNVERIFIED_OR_DRIFT", projected["blockers"])
            self.assertFalse(projected["effect_admitted"])
            self.assertEqual(projected["execution_effect"], "NONE")
            self.assertEqual(fixture.db.total_changes, count_before)


if __name__ == "__main__":
    unittest.main()
