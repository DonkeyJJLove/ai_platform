from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cyber_lion.mission_control import dual_result_join, execution_driver, global_scheduler, operator_control
from tools.lion_operator_gateway import dispatch_protocol_message, reconcile_protocol_external_once, reconcile_protocol_local_once


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class FakeRuntime:
    def __init__(self, db: Path):
        self.db=db;self.saas={};self.saas_counter=0
    def connect(self):
        c=sqlite3.connect(self.db,timeout=2)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c
    def mc_post(self,path,value,timeout=10):
        if path!="/api/v3/saas-broker/requests":raise AssertionError(path)
        if value.get("scope_type")!="MISSION" or value.get("authority_effect")!="NONE" or value.get("mission_id")!="M1":raise AssertionError(value)
        self.saas_counter+=1;rid=f"saas-test-{self.saas_counter}"
        self.saas[rid]={"status":"WAITING_SUPERVISOR","state":"WAITING_SUPERVISOR","question":value["question"],"response_text":None,"response_digest":None}
        return {"request_id":rid,"transport":"TEST_SAAS"}
    def mc_get(self,path,timeout=8):
        if path.startswith("/api/v3/saas/requests/"):
            rid=path.rsplit("/",1)[1];return dict(self.saas[rid])
        if path.startswith("/api/v3/dual/"):
            rid=path.rsplit("/",1)[1];c=self.connect()
            try:return dual_result_join.join_result(c,rid)
            finally:c.close()
        raise AssertionError(path)
    def respond_saas(self,request_id,text):
        self.saas[request_id]={"status":"RESPONDED","state":"RESPONDED","response_text":text,"response_digest":operator_control.digest(text)}



class R24ProtocolCognitiveFanoutTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.db=Path(self.td.name)/"mc.db"
        c=sqlite3.connect(self.db);c.row_factory=sqlite3.Row
        c.execute("CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT NOT NULL DEFAULT 'RUNNING',updated_at TEXT)")
        c.execute("INSERT INTO missions VALUES('M1','RUNNING',?)",(now(),))
        c.execute("CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT,logical_id TEXT)")
        c.executemany("INSERT INTO material_workers VALUES(?,?,?)",[
            ("M1","MD001","LD001"),("M1","MD002","LD002"),
        ])
        c.execute("CREATE TABLE logical_drones(mission_id TEXT,logical_id TEXT,role TEXT)")
        c.executemany("INSERT INTO logical_drones VALUES(?,?,?)",[
            ("M1","LD001","ANALYST"),("M1","LD002","VERIFIER"),
        ])
        c.execute("""CREATE TABLE schema_migrations(
          version INTEGER,schema_id TEXT,applied_at TEXT,source_head TEXT,source_tree TEXT,
          migration_digest TEXT,note TEXT,UNIQUE(version,schema_id))""")
        execution_driver.migrate(c,now,source_head="a"*40,source_tree="b"*40)
        global_scheduler.migrate(c,now)
        operator_control.migrate(c,now)
        operator_control.ensure_primary_operator(c,now)
        execution_driver.ensure_driver(c,"M1",now,initial_state="ACTIVE")
        generation=execution_driver.snapshot(c,"M1")["generation"]
        for logical,material in (("LD001","MD001"),("LD002","MD002")):
            value={"material_worker_id":material,"binding_class":"DOCKER_LOCAL_MODEL"}
            c.execute("""INSERT INTO mission_execution_assignments(
              assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,
              input_digest,input_json,state,lease_generation,control_epoch,context_revision,
              plan_revision,dispatch_authority,created_at,claimed_at,finished_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              ("topology-"+logical,"M1","__TOPOLOGY__",logical,material,
               operator_control.digest(value),json.dumps(value,sort_keys=True),"BOUND",
               generation,0,0,0,"AUTONOMOUS",now(),now(),now()))
        c.commit();c.close()
        self.runtime=FakeRuntime(self.db)

    def _message(self, cid="broadcast", cognition_routes="LOCAL"):
        c=self.runtime.connect()
        try:
            payload={"content":"Cele misji, zgłaszać wszyscy."}
            if cognition_routes is not None:
                payload["cognition_routes"]={"default":cognition_routes} if isinstance(cognition_routes,str) else cognition_routes
            value={
                "command_id":cid,"mission_id":"M1","action":"MESSAGE",
                "target":"swarm:M1","payload":payload,
                "correlation_id":"a"*32,
            }
            out=operator_control.apply_command(c,value,now)
            return out["result"]
        finally:c.close()


    def test_swarm_freezes_four_exact_recipients_and_creates_one_assignment_each(self):
        msg=self._message()
        self.assertEqual(msg["recipient_count"],4)
        self.assertEqual(set(msg["recipients"]),{
            "drone:LD001","drone:LD002","worker:MD001","worker:MD002",
        })
        self.assertTrue(msg["fanout_id"].startswith("fanout-"))
        self.assertEqual(len(msg["recipient_set_digest"]),64)
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(out["state"],"COMPLETE_DISPATCH")
        self.assertEqual(len(out["created"]),4)
        self.assertEqual({x["participant_id"] for x in out["created"]},set(msg["recipients"]))
        c=self.runtime.connect()
        try:
            rows=c.execute("SELECT input_json FROM mission_execution_assignments WHERE input_json LIKE '%PROTOCOL_FANOUT_R1%'").fetchall()
            payloads=[json.loads(r["input_json"]) for r in rows]
            self.assertEqual(len(payloads),4)
            self.assertEqual({x["responding_participant_id"] for x in payloads},set(msg["recipients"]))
            self.assertEqual({x["fanout_id"] for x in payloads},{msg["fanout_id"]})
        finally:c.close()

    def test_replay_does_not_duplicate_protocol_assignments(self):
        msg=self._message()
        first=dispatch_protocol_message(self.runtime,msg["message_id"])
        second=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(len(first["created"]),4)
        self.assertEqual(len(second["created"]),0)
        self.assertEqual(len(second["existing"]),4)

    def test_new_participant_does_not_join_existing_frozen_fanout(self):
        msg=self._message()
        c=self.runtime.connect()
        try:
            c.execute("INSERT INTO logical_drones VALUES('M1','LD003','LATE')")
            c.execute("INSERT INTO material_workers VALUES('M1','MD003','LD003')")
            c.commit()
        finally:c.close()
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(out["expected"],4)
        self.assertEqual({x["participant_id"] for x in out["created"]},{
            "drone:LD001","drone:LD002","worker:MD001","worker:MD002",
        })

    def test_pause_fences_new_cognitive_assignments(self):
        msg=self._message()
        c=self.runtime.connect()
        try:
            operator_control.apply_command(c,{
                "command_id":"pause","mission_id":"M1","action":"PAUSE_SCOPE",
                "target":"mission:M1","payload":{},
            },now)
        finally:c.close()
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(out["state"],"FENCED")
        self.assertEqual(out["created"],[])
        c=self.runtime.connect()
        try:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE input_json LIKE '%PROTOCOL_FANOUT_R1%'").fetchone()[0],0)
        finally:c.close()

    def test_default_routes_logical_saas_and_material_local_are_frozen(self):
        msg=self._message(cid="auto-mixed",cognition_routes=None)
        self.assertEqual(msg["recipient_routes"],{
            "drone:LD001":"SAAS","drone:LD002":"SAAS",
            "worker:MD001":"LOCAL","worker:MD002":"LOCAL",
        })
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(out["state"],"COMPLETE_DISPATCH")
        self.assertEqual(len(out["created"]),4)
        self.assertEqual(self.runtime.saas_counter,2)
        c=self.runtime.connect()
        try:
            trajectories=[dict(r) for r in c.execute("SELECT participant_id,cognition_route,state,local_assignment_id,saas_request_id FROM protocol_cognitive_trajectories WHERE message_id=? ORDER BY participant_id",(msg["message_id"],))]
            self.assertEqual(len(trajectories),4)
            self.assertEqual({r["participant_id"]:r["cognition_route"] for r in trajectories},msg["recipient_routes"])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE input_json LIKE '%PROTOCOL_FANOUT_R1%'").fetchone()[0],2)
        finally:c.close()

    def test_explicit_mixed_routes_materialize_saas_dual_and_local_legs(self):
        routes={"participants":{
            "drone:LD001":"SAAS",
            "drone:LD002":"DUAL",
            "worker:MD001":"LOCAL",
            "worker:MD002":"LOCAL",
        }}
        msg=self._message(cid="explicit-mixed",cognition_routes=routes)
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(out["state"],"COMPLETE_DISPATCH")
        self.assertEqual(self.runtime.saas_counter,2)
        c=self.runtime.connect()
        try:
            rows={r["participant_id"]:dict(r) for r in c.execute("SELECT * FROM protocol_cognitive_trajectories WHERE message_id=?",(msg["message_id"],))}
            self.assertEqual({k:v["cognition_route"] for k,v in rows.items()},routes["participants"])
            self.assertTrue(rows["drone:LD001"]["saas_request_id"])
            self.assertTrue(rows["drone:LD002"]["dual_request_id"])
            self.assertTrue(rows["drone:LD002"]["saas_request_id"])
            self.assertTrue(rows["drone:LD002"]["local_assignment_id"])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE input_json LIKE '%PROTOCOL_FANOUT_R1%'").fetchone()[0],3)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_dual_evaluations").fetchone()[0],1)
        finally:c.close()

    def test_material_worker_nonlocal_route_is_rejected_at_admission(self):
        with self.assertRaisesRegex(ValueError,"material worker cognition route must be LOCAL"):
            self._message(cid="bad-worker-route",cognition_routes={"participants":{"worker:MD001":"SAAS"}})
        c=self.runtime.connect()
        try:self.assertEqual(c.execute("SELECT COUNT(*) FROM operator_messages").fetchone()[0],0)
        finally:c.close()

    def test_one_participant_response_cannot_satisfy_another_delivery(self):
        msg=self._message(cid="identity-bound")
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        chosen=next(x for x in out["created"] if x["participant_id"]=="worker:MD001")
        c=self.runtime.connect()
        try:
            applied=operator_control.note_assignment_application(c,chosen["assignment_id"],{
                "operator_message_ids":[msg["message_id"]],
                "responding_participant_id":"worker:MD001",
                "response_text":"MD001 independent response",
                "response_digest":operator_control.digest("MD001 independent response"),
                "model_call_id":"modelcall-test-md001",
            },now)
            c.commit()
            self.assertEqual(applied["response_message_ids"],[applied["response_message_ids"][0]])
            deliveries={r["recipient"]:r["delivery_state"] for r in c.execute("SELECT recipient,delivery_state FROM operator_message_deliveries WHERE message_id=?",(msg["message_id"],))}
            self.assertEqual(deliveries["worker:MD001"],"APPLIED")
            self.assertEqual(deliveries["worker:MD002"],"PERSISTED")
            self.assertEqual(deliveries["drone:LD001"],"PERSISTED")
            self.assertEqual(deliveries["drone:LD002"],"PERSISTED")
            replies=[dict(r) for r in c.execute("SELECT from_participant,causation_id,correlation_id,fanout_id,recipient_set_digest FROM operator_messages WHERE kind='RESPONSE'")]
            self.assertEqual(replies,[{"from_participant":"worker:MD001","causation_id":msg["message_id"],"correlation_id":"a"*32,"fanout_id":msg["fanout_id"],"recipient_set_digest":msg["recipient_set_digest"]}])
        finally:c.close()

    def test_dual_route_does_not_close_delivery_until_join(self):
        routes={"participants":{"drone:LD001":"DUAL","drone:LD002":"LOCAL","worker:MD001":"LOCAL","worker:MD002":"LOCAL"}}
        msg=self._message(cid="dual-join",cognition_routes=routes)
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        dual=next(x for x in out["created"] if x["participant_id"]=="drone:LD001")
        c=self.runtime.connect()
        try:
            operator_control.note_assignment_application(c,dual["assignment_id"],{
                "operator_message_ids":[msg["message_id"]],
                "responding_participant_id":"drone:LD001",
                "response_text":"local half",
                "response_digest":operator_control.digest("local half"),
                "model_call_id":"modelcall-dual-local",
            },now)
            state=c.execute("SELECT delivery_state FROM operator_message_deliveries WHERE message_id=? AND recipient='drone:LD001'",(msg["message_id"],)).fetchone()[0]
            self.assertEqual(state,"PERSISTED")
            dual_id=c.execute("SELECT dual_request_id FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id='drone:LD001'",(msg["message_id"],)).fetchone()[0]
            dual_result_join.record_response(c,dual_id,dual_result_join.LOCAL_PROVIDER,"local half",now,transport="LOCAL",authority_effect="NONE")
            dual_result_join.record_response(c,dual_id,dual_result_join.SAAS_PROVIDER,"saas half",now,transport="TEST_SAAS",authority_effect="NONE")
            c.commit()
        finally:c.close()
        recon=reconcile_protocol_external_once(self.runtime)
        self.assertEqual(recon["reconciled"],1)
        c=self.runtime.connect()
        try:
            delivery=c.execute("SELECT delivery_state FROM operator_message_deliveries WHERE message_id=? AND recipient='drone:LD001'",(msg["message_id"],)).fetchone()[0]
            self.assertEqual(delivery,"APPLIED")
            reply=dict(c.execute("SELECT from_participant,causation_id,correlation_id,content FROM operator_messages WHERE kind='RESPONSE' AND from_participant='drone:LD001'").fetchone())
            self.assertEqual(reply["causation_id"],msg["message_id"])
            self.assertEqual(reply["correlation_id"],"a"*32)
            self.assertIn("local half",reply["content"]);self.assertIn("saas half",reply["content"])
        finally:c.close()

    def test_saas_send_unknown_is_not_blindly_retried(self):
        c=self.runtime.connect()
        try:
            out=operator_control.apply_command(c,{
                "command_id":"unknown-send","mission_id":"M1","action":"MESSAGE","target":"drone:LD001",
                "payload":{"content":"status","cognition_routes":{"default":"SAAS"}},"correlation_id":"b"*32,
            },now)
            msg=out["result"]
        finally:c.close()
        calls={"n":0}
        def fail_post(path,value,timeout=10):
            calls["n"]+=1;raise TimeoutError("ambiguous send")
        self.runtime.mc_post=fail_post
        first=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(first["state"],"PARTIAL");self.assertEqual(calls["n"],1)
        second=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(calls["n"],1)
        self.assertEqual(second["existing"][0]["state"],"SAAS_SEND_UNKNOWN")

    def test_stop_fences_new_cognitive_assignments(self):
        msg=self._message(cid="stop-fence")
        c=self.runtime.connect()
        try:
            operator_control.apply_command(c,{
                "command_id":"stop","mission_id":"M1","action":"STOP_SCOPE",
                "target":"mission:M1","payload":{},
            },now)
        finally:c.close()
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(out["state"],"FENCED")
        self.assertEqual(out["created"],[])
        c=self.runtime.connect()
        try:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM protocol_cognitive_trajectories WHERE message_id=?",(msg["message_id"],)).fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE input_json LIKE '%PROTOCOL_FANOUT_R1%'").fetchone()[0],0)
        finally:c.close()


    def test_assignment_only_identity_cannot_join_canonical_recipient_set(self):
        c=self.runtime.connect()
        try:
            value={"material_worker_id":"MD999","binding_class":"DOCKER_LOCAL_MODEL"}
            c.execute("""INSERT INTO mission_execution_assignments(
              assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,
              input_digest,input_json,state,lease_generation,control_epoch,context_revision,
              plan_revision,dispatch_authority,created_at,claimed_at,finished_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              ("ghost-topology","M1","__TOPOLOGY__","LD999","MD999",
               operator_control.digest(value),json.dumps(value,sort_keys=True),"BOUND",
               1,0,0,0,"AUTONOMOUS",now(),now(),now()))
            c.commit()
        finally:c.close()
        msg=self._message(cid="canonical-registry-only")
        self.assertEqual(set(msg["recipients"]),{
            "drone:LD001","drone:LD002","worker:MD001","worker:MD002",
        })
        self.assertNotIn("drone:LD999",msg["recipients"])
        self.assertNotIn("worker:MD999",msg["recipients"])

    def test_completed_local_assignment_receipt_repairs_stale_ready_trajectory(self):
        msg=self._message(cid="local-reconcile")
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        chosen=next(x for x in out["created"] if x["participant_id"]=="worker:MD001")
        c=self.runtime.connect()
        try:
            claimed=global_scheduler.claim_assignment(
                c,chosen["assignment_id"],now,expected_material_drone_id="MD001"
            )
            result={
                "kind":"LOCAL_MODEL_INFERENCE",
                "model_call_id":"modelcall-reconcile-md001",
                "response_text":"recovered local receipt response",
                "response_digest":operator_control.digest("recovered local receipt response"),
                "responding_participant_id":"worker:MD001",
                "operator_message_ids":[msg["message_id"]],
                "authority_effect":"NONE",
            }
            receipt=global_scheduler.record_receipt(
                c,chosen["assignment_id"],result,now,
                material_drone_id="MD001",
                lease_generation=claimed["lease_generation"],
                status="PASS",
                authority_effect="NONE",
            )
            global_scheduler.store_assignment_payload(
                c,chosen["assignment_id"],receipt["receipt_id"],result,now
            )
            stale=c.execute(
                "SELECT state FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id='worker:MD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(stale,"LOCAL_ASSIGNMENT_READY")
            c.commit()
        finally:c.close()
        repaired=reconcile_protocol_local_once(self.runtime)
        self.assertGreaterEqual(repaired["reconciled"],1)
        c=self.runtime.connect()
        try:
            state=c.execute(
                "SELECT state FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id='worker:MD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(state,"RESPONSE_RECONCILED")
            delivery=c.execute(
                "SELECT delivery_state FROM operator_message_deliveries WHERE message_id=? AND recipient='worker:MD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(delivery,"APPLIED")
            reply=c.execute(
                "SELECT content FROM operator_messages WHERE kind='RESPONSE' AND from_participant='worker:MD001'"
            ).fetchone()[0]
            self.assertEqual(reply,"recovered local receipt response")
        finally:c.close()

    def test_pause_after_admission_cancels_ready_trajectories_explicitly(self):
        msg=self._message(cid="pause-after-admission")
        dispatched=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(len(dispatched["created"]),4)
        c=self.runtime.connect()
        try:
            operator_control.apply_command(c,{
                "command_id":"pause-after-dispatch","mission_id":"M1","action":"PAUSE_SCOPE",
                "target":"mission:M1","payload":{},
            },now)
        finally:c.close()
        reconciled=reconcile_protocol_local_once(self.runtime)
        self.assertEqual(reconciled["cancelled"],4)
        c=self.runtime.connect()
        try:
            states={r["participant_id"]:r["state"] for r in c.execute(
                "SELECT participant_id,state FROM protocol_cognitive_trajectories WHERE message_id=?",
                (msg["message_id"],)
            )}
            self.assertEqual(set(states.values()),{"CANCELLED"})
            delivery_states={r[0] for r in c.execute(
                "SELECT delivery_state FROM operator_message_deliveries WHERE message_id=?",
                (msg["message_id"],)
            )}
            self.assertEqual(delivery_states,{"CANCELLED"})
            message_state=c.execute(
                "SELECT state FROM operator_messages WHERE message_id=?",(msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(message_state,"CANCELLED")
        finally:c.close()

    def test_pause_after_claim_marks_explicit_cancellation_requested(self):
        msg=self._message(cid="pause-after-claim")
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        chosen=next(x for x in out["created"] if x["participant_id"]=="worker:MD001")
        c=self.runtime.connect()
        try:
            global_scheduler.claim_assignment(
                c,chosen["assignment_id"],now,expected_material_drone_id="MD001"
            )
            operator_control.apply_command(c,{
                "command_id":"pause-after-claim-command","mission_id":"M1","action":"PAUSE_SCOPE",
                "target":"mission:M1","payload":{},
            },now)
        finally:c.close()
        reconcile_protocol_local_once(self.runtime)
        c=self.runtime.connect()
        try:
            state=c.execute(
                "SELECT state FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id='worker:MD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(state,"CANCELLATION_REQUESTED")
            delivery=c.execute(
                "SELECT delivery_state FROM operator_message_deliveries WHERE message_id=? AND recipient='worker:MD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(delivery,"PERSISTED")
        finally:c.close()


    def test_wrong_participant_response_is_rejected_without_delivery_mutation(self):
        msg=self._message(cid="wrong-participant")
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        chosen=next(x for x in out["created"] if x["participant_id"]=="worker:MD001")
        c=self.runtime.connect()
        try:
            with self.assertRaisesRegex(ValueError,"participant identity mismatch"):
                operator_control.note_assignment_application(c,chosen["assignment_id"],{
                    "operator_message_ids":[msg["message_id"]],
                    "responding_participant_id":"worker:MD002",
                    "response_text":"forged other participant",
                    "response_digest":operator_control.digest("forged other participant"),
                    "model_call_id":"modelcall-wrong-participant",
                },now)
            states={r["recipient"]:r["delivery_state"] for r in c.execute(
                "SELECT recipient,delivery_state FROM operator_message_deliveries WHERE message_id=?",
                (msg["message_id"],)
            )}
            self.assertEqual(states["worker:MD001"],"PERSISTED")
            self.assertEqual(states["worker:MD002"],"PERSISTED")
        finally:c.close()

    def test_saas_participant_timeout_terminalizes_its_exact_trajectory(self):
        c=self.runtime.connect()
        try:
            out=operator_control.apply_command(c,{
                "command_id":"saas-timeout","mission_id":"M1","action":"MESSAGE","target":"drone:LD001",
                "payload":{"content":"timeout test","cognition_routes":{"default":"SAAS"}},"correlation_id":"c"*32,
            },now)
            msg=out["result"]
        finally:c.close()
        dispatch=dispatch_protocol_message(self.runtime,msg["message_id"])
        request_id=dispatch["created"][0]["saas_request_id"]
        self.runtime.saas[request_id].update({"status":"EXPIRED","state":"EXPIRED"})
        recon=reconcile_protocol_external_once(self.runtime)
        self.assertEqual(recon["failed"],1)
        c=self.runtime.connect()
        try:
            row=c.execute(
                "SELECT state FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id='drone:LD001'",
                (msg["message_id"],)
            ).fetchone()
            self.assertEqual(row["state"],"FAILED")
            delivery=c.execute(
                "SELECT delivery_state FROM operator_message_deliveries WHERE message_id=? AND recipient='drone:LD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(delivery,"FAILED")
        finally:c.close()

    def test_dual_local_leg_failure_terminalizes_participant(self):
        routes={"participants":{"drone:LD001":"DUAL","drone:LD002":"LOCAL","worker:MD001":"LOCAL","worker:MD002":"LOCAL"}}
        msg=self._message(cid="dual-local-failure",cognition_routes=routes)
        dispatch=dispatch_protocol_message(self.runtime,msg["message_id"])
        dual=next(x for x in dispatch["created"] if x["participant_id"]=="drone:LD001")
        c=self.runtime.connect()
        try:
            claimed=global_scheduler.claim_assignment(c,dual["assignment_id"],now,expected_material_drone_id="MD001")
            failure={"kind":"LOCAL_MODEL_INFERENCE","error":"synthetic local leg failure","authority_effect":"NONE"}
            receipt=global_scheduler.record_receipt(
                c,dual["assignment_id"],failure,now,
                material_drone_id="MD001",lease_generation=claimed["lease_generation"],
                status="FAIL",authority_effect="NONE"
            )
            global_scheduler.store_assignment_payload(c,dual["assignment_id"],receipt["receipt_id"],failure,now)
            c.commit()
        finally:c.close()
        local=reconcile_protocol_local_once(self.runtime)
        self.assertEqual(local["failed"],1)
        c=self.runtime.connect()
        try:
            state=c.execute(
                "SELECT state FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id='drone:LD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(state,"FAILED")
        finally:c.close()

    def test_dual_saas_leg_failure_terminalizes_participant(self):
        routes={"participants":{"drone:LD001":"DUAL","drone:LD002":"LOCAL","worker:MD001":"LOCAL","worker:MD002":"LOCAL"}}
        msg=self._message(cid="dual-saas-failure",cognition_routes=routes)
        dispatch=dispatch_protocol_message(self.runtime,msg["message_id"])
        dual=next(x for x in dispatch["created"] if x["participant_id"]=="drone:LD001")
        self.runtime.saas[dual["saas_request_id"]].update({"status":"EXPIRED","state":"EXPIRED"})
        external=reconcile_protocol_external_once(self.runtime)
        self.assertEqual(external["failed"],1)
        c=self.runtime.connect()
        try:
            state=c.execute(
                "SELECT state FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id='drone:LD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(state,"FAILED")
            delivery=c.execute(
                "SELECT delivery_state FROM operator_message_deliveries WHERE message_id=? AND recipient='drone:LD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(delivery,"FAILED")
        finally:c.close()

    def test_four_logical_four_material_produce_eight_independent_reconciliations(self):
        c=self.runtime.connect()
        try:
            c.executemany("INSERT INTO logical_drones VALUES(?,?,?)",[
                ("M1","LD003","ARCHITECT"),("M1","LD004","AUDITOR"),
            ])
            c.executemany("INSERT INTO material_workers VALUES(?,?,?)",[
                ("M1","MD003","LD003"),("M1","MD004","LD004"),
            ])
            generation=execution_driver.snapshot(c,"M1")["generation"]
            for logical,material in (("LD003","MD003"),("LD004","MD004")):
                value={"material_worker_id":material,"binding_class":"DOCKER_LOCAL_MODEL"}
                c.execute("""INSERT INTO mission_execution_assignments(
                  assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,
                  input_digest,input_json,state,lease_generation,control_epoch,context_revision,
                  plan_revision,dispatch_authority,created_at,claimed_at,finished_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  ("topology-"+logical,"M1","__TOPOLOGY__",logical,material,
                   operator_control.digest(value),json.dumps(value,sort_keys=True),"BOUND",
                   generation,0,0,0,"AUTONOMOUS",now(),now(),now()))
            c.commit()
        finally:c.close()
        msg=self._message(cid="eight-trajectories",cognition_routes=None)
        self.assertEqual(msg["recipient_count"],8)
        dispatch=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(dispatch["state"],"COMPLETE_DISPATCH")
        self.assertEqual(len(dispatch["created"]),8)
        local=[x for x in dispatch["created"] if x["participant_id"].startswith("worker:")]
        saas=[x for x in dispatch["created"] if x["participant_id"].startswith("drone:")]
        self.assertEqual((len(local),len(saas)),(4,4))
        c=self.runtime.connect()
        try:
            for item in local:
                participant=item["participant_id"]
                text="local response "+participant
                operator_control.note_assignment_application(c,item["assignment_id"],{
                    "operator_message_ids":[msg["message_id"]],
                    "responding_participant_id":participant,
                    "response_text":text,
                    "response_digest":operator_control.digest(text),
                    "model_call_id":"modelcall-"+participant.replace(":","-"),
                },now)
            c.commit()
        finally:c.close()
        for item in saas:
            self.runtime.respond_saas(item["saas_request_id"],"saas response "+item["participant_id"])
        external=reconcile_protocol_external_once(self.runtime)
        self.assertEqual(external["reconciled"],4)
        c=self.runtime.connect()
        try:
            trajectories=[dict(r) for r in c.execute(
                "SELECT participant_id,state,response_message_id FROM protocol_cognitive_trajectories WHERE message_id=? ORDER BY participant_id",
                (msg["message_id"],)
            )]
            self.assertEqual(len(trajectories),8)
            self.assertEqual({x["state"] for x in trajectories},{"RESPONSE_RECONCILED"})
            self.assertEqual(len({x["response_message_id"] for x in trajectories}),8)
            deliveries=[dict(r) for r in c.execute(
                "SELECT recipient,delivery_state FROM operator_message_deliveries WHERE message_id=? ORDER BY recipient",
                (msg["message_id"],)
            )]
            self.assertEqual(len(deliveries),8)
            self.assertEqual({x["delivery_state"] for x in deliveries},{"APPLIED"})
        finally:c.close()

    def test_cross_mission_target_injection_is_denied_before_fanout(self):
        c=self.runtime.connect()
        try:
            c.execute("INSERT INTO missions VALUES('M2','RUNNING',?)",(now(),))
            c.commit()
            with self.assertRaisesRegex(ValueError,"target mission mismatch|unresolved swarm target"):
                operator_control.apply_command(c,{
                    "command_id":"cross-mission","mission_id":"M1","action":"MESSAGE",
                    "target":"swarm:M2","payload":{"content":"forged cross mission"},
                    "correlation_id":"d"*32,
                },now)
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM operator_messages WHERE command_id='cross-mission'").fetchone()[0],
                0,
            )
        finally:c.close()

    def test_explicit_local_participant_failure_terminalizes_exact_delivery(self):
        msg=self._message(cid="local-participant-failure")
        dispatch=dispatch_protocol_message(self.runtime,msg["message_id"])
        chosen=next(x for x in dispatch["created"] if x["participant_id"]=="worker:MD001")
        c=self.runtime.connect()
        try:
            operator_control.fail_protocol_trajectory(
                c,msg["message_id"],"worker:MD001","LOCAL_MODEL_FAILED",now
            )
            c.commit()
            state=c.execute(
                "SELECT state FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id='worker:MD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            delivery=c.execute(
                "SELECT delivery_state FROM operator_message_deliveries WHERE message_id=? AND recipient='worker:MD001'",
                (msg["message_id"],)
            ).fetchone()[0]
            other=c.execute(
                "SELECT delivery_state FROM operator_message_deliveries WHERE message_id=? AND recipient='worker:MD002'",
                (msg["message_id"],)
            ).fetchone()[0]
            self.assertEqual(state,"FAILED")
            self.assertEqual(delivery,"FAILED")
            self.assertEqual(other,"PERSISTED")
            self.assertTrue(chosen["assignment_id"])
        finally:c.close()

if __name__=="__main__":
    unittest.main()
