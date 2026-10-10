"""R5 source-only regression: one activated LPCL reacquires its Docker binding without restart.

All tests use an isolated SQLite file and mock the fleet observation.
They create no host containers, material effects, authority grants or SaaS requests.
"""
from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_lion.mission_control.application_factory_program import registration_payload


class ActivatedLpclAutoRebindTests(unittest.TestCase):
    def setUp(self):
        tools = Path(__file__).resolve().parents[2] / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        compat = importlib.import_module("lion_mission_control_compat")
        sys.modules["mission_control_compat"] = compat
        self.mc = importlib.import_module("lion_mission_control_v3")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        old_db, old_legacy = self.mc.DB, self.mc.LEGACY_DB
        self.addCleanup(lambda: setattr(self.mc, "DB", old_db))
        self.addCleanup(lambda: setattr(self.mc, "LEGACY_DB", old_legacy))
        self.mc.DB = Path(self.tmp.name) / "mission-control.db"
        self.mc.LEGACY_DB = Path(self.tmp.name) / "absent.db"
        self.mc.migrate()
        self.spec = registration_payload("a" * 40, "b" * 40)
        self.mid = self.spec["mission_id"]
        self.mc.register_lpcl_mission(self.spec)

    def _fixture_operator_launch(self):
        """Fixture only: set exact launch state inside a disposable database."""
        c = self.mc.connect()
        try:
            c.execute("UPDATE missions SET state='AUTHORIZED' WHERE mission_id=?", (self.mid,))
            c.execute(
                "UPDATE mission_process_specs SET authority_state='EXPLICIT_USER_ACTIVATION' WHERE mission_id=?",
                (self.mid,),
            )
            c.commit()
        finally:
            c.close()

    def _observed_workers(self):
        stamp = self.mc.now()
        return {
            "digest": "d" * 64,
            "observed_at": stamp,
            "source_head": self.spec["source_head"],
            "source_tree": self.spec["source_tree"],
            "physical_failure_domains": 1,
            "workers": [
                {
                    "material_worker_id": f"MD{i:03d}",
                    "pod_name": f"lion-r24-md{i:03d}",
                    "pod_uid": f"{i:064x}",
                    "container_id": f"{i:064x}",
                    "ready": 1,
                    "phase": "DOCKER_LOCAL_MODEL",
                    "restarts": 0,
                    "pod_ip": None,
                    "model": "gpt-oss-20b-MXFP4",
                }
                for i in range(1, 33)
            ],
        }

    def test_unlaunched_lpcl_never_rebinds_even_with_current_fleet(self):
        mc = self.mc
        with (
            patch.object(mc.operator_control, "autonomy_allowed", return_value=True),
            patch.object(mc, "_docker_local_model_currentness", return_value=self._observed_workers()) as observer,
            patch.object(mc, "bind_lpcl_execution") as binder,
        ):
            result = mc.reconcile_activated_unbound_docker_once(force=True)
        self.assertEqual(result["rebound"], [])
        observer.assert_not_called()
        binder.assert_not_called()

    def test_activated_lpcl_waits_when_fleet_is_unverified_without_effect(self):
        mc = self.mc
        self._fixture_operator_launch()
        with (
            patch.object(mc.operator_control, "autonomy_allowed", return_value=True),
            patch.object(mc, "_docker_local_model_currentness", side_effect=ValueError("fleet not ready")),
            patch.object(mc, "bind_lpcl_execution") as binder,
        ):
            result = mc.reconcile_activated_unbound_docker_once(force=True)
        binder.assert_not_called()
        self.assertEqual(result["rebound"], [])
        self.assertEqual(result["waiting"], [
            {"mission_id": self.mid, "gate": "DOCKER_FLEET_CURRENTNESS_REQUIRED"}
        ])
        c = mc.connect()
        try:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id=?", (self.mid,)).fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT adapter FROM missions WHERE mission_id=?", (self.mid,)).fetchone()[0], "LPCL_MISSION")
        finally:
            c.close()

    def test_activated_lpcl_rebinds_exactly_once_after_fleet_currentness(self):
        mc = self.mc
        self._fixture_operator_launch()
        with (
            patch.object(mc.operator_control, "autonomy_allowed", return_value=True),
            patch.object(mc, "_docker_local_model_currentness", return_value=self._observed_workers()),
        ):
            first = mc.reconcile_activated_unbound_docker_once(force=True)
            second = mc.reconcile_activated_unbound_docker_once(force=True)
        self.assertEqual(first["rebound"], [self.mid], first)
        self.assertEqual(second["rebound"], [], second)
        c = mc.connect()
        try:
            mission = c.execute("SELECT adapter,ready,materialized FROM missions WHERE mission_id=?", (self.mid,)).fetchone()
            self.assertEqual(mission["adapter"], mc.LPCL_DOCKER_LOCAL_MODEL_ADAPTER)
            self.assertEqual((mission["materialized"], mission["ready"]), (32, 32))
            self.assertEqual(c.execute("SELECT COUNT(*) FROM logical_drones WHERE mission_id=?", (self.mid,)).fetchone()[0], 4)
            self.assertEqual(c.execute(
                "SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'", (self.mid,)
            ).fetchone()[0], 4)
        finally:
            c.close()

    def test_current_but_foreign_source_fleet_cannot_rebind(self):
        mc = self.mc
        self._fixture_operator_launch()
        untrusted = dict(self._observed_workers(), source_tree="f" * 40)
        with (
            patch.object(mc.operator_control, "autonomy_allowed", return_value=True),
            patch.object(mc, "_docker_local_model_currentness", return_value=untrusted),
            patch.object(mc, "bind_lpcl_execution") as binder,
        ):
            outcome = mc.reconcile_activated_unbound_docker_once(force=True)
        binder.assert_not_called()
        self.assertEqual(outcome["rebound"], [])
        self.assertEqual(outcome["waiting"], [
            {"mission_id": self.mid, "gate": "DOCKER_FLEET_SOURCE_CURRENTNESS_DRIFT"}
        ])

    def test_changed_observation_between_probe_and_binding_denied(self):
        mc = self.mc
        self._fixture_operator_launch()
        first = self._observed_workers()
        second = dict(first, digest="e" * 64)
        with (
            patch.object(mc.operator_control, "autonomy_allowed", return_value=True),
            patch.object(mc, "_docker_local_model_currentness", side_effect=[first, second]),
        ):
            outcome = mc.reconcile_activated_unbound_docker_once(force=True)
        self.assertEqual(outcome["rebound"], [])
        self.assertEqual(outcome["waiting"], [
            {"mission_id": self.mid, "gate": "RUNTIME_BINDING_NOT_CONFIRMED",
             "error_class": "ValueError"}
        ])
        c = mc.connect()
        try:
            self.assertEqual(c.execute("SELECT adapter FROM missions WHERE mission_id=?", (self.mid,)).fetchone()[0], "LPCL_MISSION")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id=?", (self.mid,)).fetchone()[0], 0)
        finally:
            c.close()

    def test_existing_scheduler_invokes_rebinding_without_owning_second_driver(self):
        mc = self.mc
        with (
            patch.object(mc, "reconcile_activated_unbound_docker_once", return_value={"rebound": []}) as rebind,
            patch.object(mc, "reconcile_control_plane_late_saas"),
            patch.object(mc.global_sched, "next_dispatch", return_value=None),
        ):
            mc.global_scheduler_once()
        rebind.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
