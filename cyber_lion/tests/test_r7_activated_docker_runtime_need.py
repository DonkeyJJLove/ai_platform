"""R7: the original scheduler durably parks an operator-launched Docker LPCL.

All effects are limited to a *temporary* SQLite Mission Control database:
no Docker calls, no material workers, no external SaaS, no authority grant.
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_lion.mission_control.application_factory_program import registration_payload


class DockerNeedTests(unittest.TestCase):
    def setUp(self):
        tool_dir=Path(__file__).resolve().parents[2]/"tools"
        if str(tool_dir) not in sys.path:sys.path.insert(0,str(tool_dir))
        sys.modules["mission_control_compat"]=importlib.import_module("lion_mission_control_compat")
        self.mc=importlib.import_module("lion_mission_control_v3")
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        saved_db,saved_legacy=self.mc.DB,self.mc.LEGACY_DB
        self.addCleanup(lambda:setattr(self.mc,"DB",saved_db))
        self.addCleanup(lambda:setattr(self.mc,"LEGACY_DB",saved_legacy))
        self.mc.DB=Path(self.tmp.name)/"r7-db.sqlite"
        self.mc.LEGACY_DB=Path(self.tmp.name)/"absent.sqlite"
        self.mc.migrate()
        self.payload=registration_payload("a"*40,"b"*40)
        self.mid=self.payload["mission_id"]
        self.mc.register_lpcl_mission(self.payload)

    def launch_fixture(self):
        c=self.mc.connect()
        try:
            c.execute("UPDATE missions SET state='AUTHORIZED' WHERE mission_id=?",(self.mid,))
            c.execute("UPDATE mission_process_specs SET authority_state='EXPLICIT_USER_ACTIVATION' WHERE mission_id=?",(self.mid,))
            c.commit()
        finally:c.close()

    def ready_observation(self):
        return {
          "digest":"d"*64,"source_head":self.payload["source_head"],"source_tree":self.payload["source_tree"],
          "observed_at":self.mc.now(),"physical_failure_domains":1,
          "workers":[{
            "material_worker_id":f"MD{i:03d}","pod_name":f"lion-r24-md{i:03d}",
            "pod_uid":f"{i:064x}","container_id":f"{i:064x}","ready":1,
            "phase":"DOCKER_LOCAL_MODEL","restarts":0,"pod_ip":None,
            "model":"gpt-oss-20b-MXFP4",
          } for i in range(1,33)],
        }

    def test_unlaunched_lpcl_does_not_create_driver_or_need(self):
        with patch.object(self.mc.operator_control,"autonomy_allowed",return_value=True):
            result=self.mc.park_activated_docker_lpcl_runtime_need(
              self.mid,gate="DOCKER_FLEET_CURRENTNESS_REQUIRED"
            )
        self.assertEqual(result["state"],"NOT_ELIGIBLE")
        c=self.mc.connect()
        try:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_drivers WHERE mission_id=?",(self.mid,)).fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM protocol_messages WHERE mission_id=? AND payload_json LIKE '%DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED%'",(self.mid,)).fetchone()[0],0)
        finally:c.close()

    def test_activated_no_fleet_is_durably_parked_one_time(self):
        self.launch_fixture()
        with (
          patch.object(self.mc.operator_control,"autonomy_allowed",return_value=True),
          patch.object(self.mc,"_docker_local_model_currentness",side_effect=ValueError("UNVERIFIED_FLEET")),
          patch.object(self.mc,"bind_lpcl_execution") as binder,
        ):
            first=self.mc.reconcile_activated_unbound_docker_once(force=True)
            second=self.mc.reconcile_activated_unbound_docker_once(force=True)
        binder.assert_not_called()
        self.assertEqual(first["waiting"],[{"mission_id":self.mid,"gate":"DOCKER_FLEET_CURRENTNESS_REQUIRED"}])
        self.assertEqual(second["waiting"],first["waiting"])
        c=self.mc.connect()
        try:
            m=c.execute("SELECT adapter,state,runtime_state,materialized,ready FROM missions WHERE mission_id=?",(self.mid,)).fetchone()
            self.assertEqual(tuple(m),("LPCL_MISSION","AUTHORIZED","DOCKER_FLEET_WAITING_FOR_ADMISSION",0,0))
            d=c.execute("SELECT state,blocking_gate,next_action,lease_owner FROM mission_execution_drivers WHERE mission_id=?",(self.mid,)).fetchone()
            self.assertEqual(tuple(d),("WAITING","DOCKER_FLEET_CURRENTNESS_REQUIRED","WAIT_FOR_ADMITTED_DOCKER_FLEET",None))
            self.assertEqual(c.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id=?",(self.mid,)).fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM logical_drones WHERE mission_id=?",(self.mid,)).fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=?",(self.mid,)).fetchone()[0],0)
            evs=c.execute("SELECT payload_json FROM protocol_messages WHERE mission_id=? AND payload_json LIKE '%DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED%'",(self.mid,)).fetchall()
            self.assertEqual(len(evs),1)
            event=json.loads(evs[0]["payload_json"])
            need=event["need"]
            self.assertEqual(need["source_head"],self.payload["source_head"])
            self.assertEqual(need["source_tree"],self.payload["source_tree"])
            self.assertEqual(need["lpcl_digest"],self.payload["lpcl_digest"])
            self.assertEqual(need["required_capability_class"],"DOCKER_FLEET_BOOTSTRAP")
            self.assertEqual(need["required_admission"],"CANONICAL_RUNTIME_ADMISSION_AND_EXPLICIT_LPCL")
            self.assertEqual(event["need_digest"],self.mc._payload_digest(need))
            self.assertEqual(need["runtime_effect"],"NONE")
        finally:c.close()

    def test_wait_does_not_erase_previous_diagnostic(self):
        self.launch_fixture()
        c=self.mc.connect()
        try:
            c.execute("UPDATE missions SET last_error=? WHERE mission_id=?",
                      ("PREEXISTING_SECURITY_DRIFT",self.mid))
            c.commit()
        finally:c.close()
        with patch.object(self.mc.operator_control,"autonomy_allowed",return_value=True):
            result=self.mc.park_activated_docker_lpcl_runtime_need(
                self.mid,gate="DOCKER_FLEET_CURRENTNESS_REQUIRED"
            )
        self.assertEqual(result["state"],"WAITING")
        c=self.mc.connect()
        try:
            self.assertEqual(c.execute("SELECT last_error FROM missions WHERE mission_id=?",
                                       (self.mid,)).fetchone()[0],"PREEXISTING_SECURITY_DRIFT")
        finally:c.close()

    def test_tampered_canonical_need_blocks_idempotent_success(self):
        self.launch_fixture()
        with patch.object(self.mc.operator_control,"autonomy_allowed",return_value=True):
            first=self.mc.park_activated_docker_lpcl_runtime_need(
                self.mid,gate="DOCKER_FLEET_CURRENTNESS_REQUIRED"
            )
            self.assertEqual(first["state"],"WAITING")
            c=self.mc.connect()
            try:
                row=c.execute("SELECT id,payload_json FROM protocol_messages "
                              "WHERE mission_id=? AND payload_json LIKE '%DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED%'",
                              (self.mid,)).fetchone()
                obj=json.loads(row["payload_json"])
                obj["need"]["source_tree"]="f"*40
                c.execute("UPDATE protocol_messages SET payload_json=? WHERE id=?",
                          (json.dumps(obj,sort_keys=True),row["id"]))
                c.commit()
            finally:c.close()
            with self.assertRaisesRegex(RuntimeError,"canonical Docker runtime need journal"):
                self.mc.park_activated_docker_lpcl_runtime_need(
                    self.mid,gate="DOCKER_FLEET_CURRENTNESS_REQUIRED"
                )
        c=self.mc.connect()
        try:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id=?",(self.mid,)).fetchone()[0],0)
            self.assertEqual(c.execute("SELECT state FROM mission_execution_drivers WHERE mission_id=?",(self.mid,)).fetchone()[0],"WAITING")
        finally:c.close()

    def test_stale_observation_rebinds_gate_but_not_worker_or_authority(self):
        self.launch_fixture()
        obs=dict(self.ready_observation(),source_tree="f"*40)
        with (
          patch.object(self.mc.operator_control,"autonomy_allowed",return_value=True),
          patch.object(self.mc,"_docker_local_model_currentness",return_value=obs),
          patch.object(self.mc,"bind_lpcl_execution") as binder,
        ):
            outcome=self.mc.reconcile_activated_unbound_docker_once(force=True)
        binder.assert_not_called()
        self.assertEqual(outcome["waiting"],[{"mission_id":self.mid,"gate":"DOCKER_FLEET_SOURCE_CURRENTNESS_DRIFT"}])
        c=self.mc.connect()
        try:
            d=c.execute("SELECT state,blocking_gate FROM mission_execution_drivers WHERE mission_id=?",(self.mid,)).fetchone()
            self.assertEqual(tuple(d),("WAITING","DOCKER_FLEET_SOURCE_CURRENTNESS_DRIFT"))
            self.assertEqual(c.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id=?",(self.mid,)).fetchone()[0],0)
        finally:c.close()

    def test_later_valid_cohort_resumes_same_driver_with_single_topology(self):
        self.launch_fixture()
        with patch.object(self.mc.operator_control,"autonomy_allowed",return_value=True):
            with patch.object(self.mc,"_docker_local_model_currentness",side_effect=ValueError("no cohort")):
                outcome=self.mc.reconcile_activated_unbound_docker_once(force=True)
                self.assertEqual(len(outcome["waiting"]),1)
            c=self.mc.connect()
            try:
                first=c.execute("SELECT driver_id FROM mission_execution_drivers WHERE mission_id=?",(self.mid,)).fetchone()[0]
                # Simulate prior 0-worker recon and 1-worker qualification in
                # this disposable fixture. Full 32-MD rebinding is legitimate
                # only from the later, explicit 32-worker phase.
                c.execute(
                    "UPDATE mission_phases SET status='PASS',progress=100.0 "
                    "WHERE mission_id=? AND ordinal IN (1,2)",(self.mid,)
                )
                c.commit()
            finally:c.close()
            with patch.object(self.mc,"_docker_local_model_currentness",return_value=self.ready_observation()):
                res=self.mc.reconcile_activated_unbound_docker_once(force=True)
        self.assertEqual(res["rebound"],[self.mid],res)
        c=self.mc.connect()
        try:
            d=c.execute("SELECT driver_id,state FROM mission_execution_drivers WHERE mission_id=?",(self.mid,)).fetchone()
            self.assertEqual(d["driver_id"],first)
            self.assertEqual(d["state"],"ACTIVE")
            m=c.execute("SELECT adapter,materialized,ready FROM missions WHERE mission_id=?",(self.mid,)).fetchone()
            self.assertEqual(tuple(m),(self.mc.LPCL_DOCKER_LOCAL_MODEL_ADAPTER,32,32))
            self.assertEqual(c.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id=?",(self.mid,)).fetchone()[0],32)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'",(self.mid,)).fetchone()[0],4)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM protocol_messages WHERE mission_id=? AND payload_json LIKE '%DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED%'",(self.mid,)).fetchone()[0],1)
        finally:c.close()

    def test_revoked_operator_fence_creates_no_need(self):
        self.launch_fixture()
        with patch.object(self.mc.operator_control,"autonomy_allowed",return_value=False):
            outcome=self.mc.reconcile_activated_unbound_docker_once(force=True)
        self.assertEqual(outcome["waiting"],[])
        self.assertEqual(outcome["rebound"],[])
        c=self.mc.connect()
        try:self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_drivers WHERE mission_id=?",(self.mid,)).fetchone()[0],0)
        finally:c.close()

    def test_arbitrary_gate_is_denied(self):
        self.launch_fixture()
        with self.assertRaisesRegex(ValueError,"unrecognized Docker runtime wait gate"):
            self.mc.park_activated_docker_lpcl_runtime_need(self.mid,gate="DOCKER_COMPOSE_UP")

if __name__=="__main__":
    unittest.main()
