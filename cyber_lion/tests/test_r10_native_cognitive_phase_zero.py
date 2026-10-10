"""R10 native LOCAL phase-0: ephemeral SQLite, real R7 mission gates, fake HTTP.

No production mission, invented material lease, Docker, SaaS call or worker.
"""
from __future__ import annotations

from copy import deepcopy
import importlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_lion.mission_control.application_factory_program import registration_payload
from cyber_lion.mission_control import global_scheduler as sched
from cyber_lion.mission_control import native_cognitive_phase_zero as native


class NativeCognitivePhaseZeroTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[2]
        if str(root/"tools") not in sys.path:
            sys.path.insert(0,str(root/"tools"))
        sys.modules["mission_control_compat"]=importlib.import_module("lion_mission_control_compat")
        self.mc=importlib.import_module("lion_mission_control_v3")
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        saved_db,saved_legacy=self.mc.DB,self.mc.LEGACY_DB
        self.addCleanup(lambda:setattr(self.mc,"DB",saved_db))
        self.addCleanup(lambda:setattr(self.mc,"LEGACY_DB",saved_legacy))
        self.mc.DB=Path(self.tmp.name)/"native.db"
        self.mc.LEGACY_DB=Path(self.tmp.name)/"absent.db"
        self.mc.migrate()
        self.spec=registration_payload("a"*40,"b"*40)
        self.mid=self.spec["mission_id"]
        self.mc.register_lpcl_mission(self.spec)
        self.c=self.mc.connect()
        self.addCleanup(self.c.close)
        self.c.execute("UPDATE missions SET state='AUTHORIZED' WHERE mission_id=?",(self.mid,))
        self.c.execute("UPDATE mission_process_specs SET authority_state='EXPLICIT_USER_ACTIVATION' WHERE mission_id=?",(self.mid,))
        self.c.commit()
        # Disposable fixture simulates the operator-control record that the
        # canonical UI activation creates; it grants no production rights.
        self.mc.operator_control.ensure_control_state(self.c,self.mid,self.mc.now)
        self.c.commit()
        with patch.object(self.mc.operator_control,"autonomy_allowed",return_value=True):
            result=self.mc.park_activated_docker_lpcl_runtime_need(
                self.mid,gate="DOCKER_FLEET_CURRENTNESS_REQUIRED"
            )
        self.assertEqual(result["state"],"WAITING")
        self.contract=sched.phase_execution_contract(self.c,self.mid,"CROSS_MODEL_RECON")
        self.source={"head":self.spec["source_head"],"tree":self.spec["source_tree"]}
        self.evidence={"schema":"lion.control-plane-evidence-bundle/v1",
                       "mission_id":self.mid,"phase_id":"CROSS_MODEL_RECON",
                       "observations":{"schema":"lion.test-control-plane-observation/v1"},
                       "authority_effect":"NONE"}
        saved=sched.put_artifact(self.c,self.mid,"RECON_EVIDENCE_BUNDLE",self.evidence,
                                 self.mc.now,phase_id="CROSS_MODEL_RECON",
                                 schema_id="lion.control-plane-evidence-bundle/v1")
        self.edigest=saved["content_digest"]
        native.migrate(self.c)
        self.role="PRIMARY_RECONSTRUCTION"
        self.messages=[{"role":"system","content":"You are an independent proposal-only analyst."},
                       {"role":"user","content":"Summarize evidence of this test without claiming effects."}]

    def intent(self):
        with patch.object(native.operator_control,"autonomy_allowed",return_value=True):
            return native.prepare_intent(
                self.c,mission_id=self.mid,phase_id="CROSS_MODEL_RECON",
                role=self.role,evidence_bundle_digest=self.edigest,
                messages=self.messages,contract_digest=self.contract["contract_digest"],
                current_source=self.source,now_fn=self.mc.now
            )

    def send(self, prior,transport):
        with patch.object(native.operator_control,"autonomy_allowed",return_value=True):
            return native.send_once(self.c,intent=prior,messages=self.messages,
                 evidence_bundle_digest=self.edigest,contract_digest=self.contract["contract_digest"],
                 current_source=self.source,transport=transport,now_fn=self.mc.now)

    def fake_transport(self,messages):
        self.assertEqual(messages,self.messages)
        response='{"claims":[],"unknowns":["test"],"summary":"A response, not an effect."}'
        return (response,
                json.dumps({"choices":[{"message":{"content":response},"finish_reason":"stop"}]}).encode(),
                "gpt-oss-20b",__import__("hashlib").sha256(native._http_payload(messages)).hexdigest())

    def test_exact_r7_wait_allows_durable_native_intent_without_material_worker(self):
        data=self.intent()
        self.assertEqual(data["state"],"INTENT_DURABLE")
        self.assertEqual(data["source_head"],self.spec["source_head"])
        again=self.intent()
        self.assertEqual(again["call_id"],data["call_id"])
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM mission_native_cognitive_trajectories").fetchone()[0],1)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM mission_recon_material_leases").fetchone()[0],0)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id=?",(self.mid,)).fetchone()[0],0)

    def test_actual_result_and_raw_http_digest_are_durable_and_one_shot(self):
        intent=self.intent()
        receipt=self.send(intent,self.fake_transport)
        self.assertEqual(receipt["state"],"RESPONSE_RECONCILED")
        self.assertEqual(receipt["authority_effect"],"NONE")
        self.assertIsNone(receipt["model_attested"])
        with patch.object(native.operator_control,"autonomy_allowed",return_value=True):
            readback=native.read_response(self.c,call_id=intent["call_id"],mission_id=self.mid,
                        phase_id="CROSS_MODEL_RECON",role=self.role,evidence_bundle_digest=self.edigest,
                        current_source=self.source,contract_digest=self.contract["contract_digest"])
        self.assertEqual(readback["response_digest"],receipt["response_digest"])
        self.assertEqual(readback["receipt_digest"],receipt["receipt_digest"])
        self.assertTrue(readback["response_text"])
        with self.assertRaisesRegex(native.NativeCognitiveError,"UNCERTAIN_OR_COMPLETE_SEND_REPLAY_DENIED"):
            self.send(intent,self.fake_transport)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM mission_native_cognitive_trajectories").fetchone()[0],1)

    def test_failure_after_send_fails_closed_with_no_network_retry(self):
        counter=0
        def interrupted(messages):
            nonlocal counter
            counter+=1
            raise TimeoutError("response unknown")
        intent=self.intent()
        with self.assertRaises(TimeoutError):
            self.send(intent,interrupted)
        row=self.c.execute("SELECT state,response_digest FROM mission_native_cognitive_trajectories").fetchone()
        self.assertEqual(row["state"],"SEND_UNKNOWN")
        self.assertIsNone(row["response_digest"])
        with self.assertRaisesRegex(native.NativeCognitiveError,"UNCERTAIN_OR_COMPLETE_SEND_REPLAY_DENIED"):
            self.send(intent,interrupted)
        self.assertEqual(counter,1)

    def test_unlaunched_or_unbound_operator_never_creates_intent(self):
        self.c.execute("UPDATE mission_process_specs SET authority_state='NONE' WHERE mission_id=?",(self.mid,))
        self.c.commit()
        with self.assertRaisesRegex(native.NativeCognitiveError,"SOURCE_BOUND_PREMATERIAL_MISSION_REQUIRED"):
            self.intent()
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM mission_native_cognitive_trajectories").fetchone()[0],0)

    def test_source_head_drift_denies_before_intent_or_model(self):
        self.source["head"]="c"*40
        with self.assertRaisesRegex(native.NativeCognitiveError,"INDEPENDENT_SOURCE_CURRENTNESS_REQUIRED"):
            self.intent()

    def test_foreign_driver_owner_or_generation_denies_response(self):
        intent=self.intent()
        self.c.execute("UPDATE mission_execution_drivers SET generation=generation+1 WHERE mission_id=?",(self.mid,))
        self.c.commit()
        with self.assertRaisesRegex(native.NativeCognitiveError,"NATIVE_COGNITIVE_BINDING_DRIFT"):
            self.send(intent,self.fake_transport)
        self.assertEqual(self.c.execute("SELECT state FROM mission_native_cognitive_trajectories").fetchone()[0],"INTENT_DURABLE")

    def test_changed_evidence_digest_or_prompt_never_replays(self):
        intent=self.intent()
        self.messages[1]["content"]="different meaning"
        with self.assertRaisesRegex(native.NativeCognitiveError,"NATIVE_COGNITIVE_BINDING_DRIFT"):
            self.send(intent,self.fake_transport)
        self.assertEqual(self.c.execute("SELECT state FROM mission_native_cognitive_trajectories").fetchone()[0],"INTENT_DURABLE")

    def test_stored_response_tamper_detected_during_readback(self):
        intent=self.intent();self.send(intent,self.fake_transport)
        self.c.execute("UPDATE mission_native_cognitive_trajectories SET response_text='forged'")
        self.c.commit()
        with patch.object(native.operator_control,"autonomy_allowed",return_value=True):
            with self.assertRaisesRegex(native.NativeCognitiveError,"NATIVE_RESPONSE_CONTENT_DRIFT"):
                native.read_response(self.c,call_id=intent["call_id"],mission_id=self.mid,
                    phase_id="CROSS_MODEL_RECON",role=self.role,evidence_bundle_digest=self.edigest,
                    current_source=self.source,contract_digest=self.contract["contract_digest"])

    def test_real_phase_zero_waits_for_windows_evidence_not_a_synthetic_pass(self):
        """No Windows observation means no LOCAL or SaaS traffic, no progress."""
        # A new live mission has no evidence bundle before the first observer.
        self.c.execute("DELETE FROM mission_artifacts WHERE mission_id=? AND artifact_type='RECON_EVIDENCE_BUNDLE'",
                       (self.mid,))
        self.c.commit()
        with (
            patch.object(self.mc,"_current_master_identity",
                         return_value=(self.source["head"],self.source["tree"])),
            patch.object(native.operator_control,"autonomy_allowed",return_value=True),
            patch.object(native,"native_llamacpp_transport") as model,
        ):
            result=self.mc.advance_native_cognitive_phase_zero_once()
        self.assertEqual(result["state"],"WAITING")
        self.assertEqual(result["gate"],"EVIDENCE_INCOMPLETE")
        persisted=self.c.execute(
            "SELECT blocking_gate,next_action FROM mission_execution_drivers WHERE mission_id=?",
            (self.mid,)
        ).fetchone()
        self.assertEqual(tuple(persisted),
                         ("EVIDENCE_INCOMPLETE","WAIT_FOR_PHASE_ZERO_EVIDENCE"))
        model.assert_not_called()
        with (
            patch.object(self.mc.operator_control,"autonomy_allowed",return_value=True),
            patch.object(self.mc,"_docker_local_model_currentness",
                         side_effect=AssertionError("phase zero must not check 32 workers")) as fleet
        ):
            rebinder=self.mc.reconcile_activated_unbound_docker_once(force=True)
        fleet.assert_not_called()
        self.assertEqual(rebinder["waiting"],[
            {"mission_id":self.mid,"gate":"EVIDENCE_INCOMPLETE"}
        ])
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM material_workers WHERE mission_id=?",(self.mid,)
        ).fetchone()[0],0)
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM mission_recon_material_leases WHERE mission_id=?",(self.mid,)
        ).fetchone()[0],0)
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM mission_native_cognitive_trajectories").fetchone()[0],0)
        self.assertEqual(self.c.execute(
            "SELECT status FROM mission_phases WHERE mission_id=? AND phase_id='CROSS_MODEL_RECON'",
            (self.mid,)).fetchone()[0],"PENDING")

    def test_expired_saas_session_cannot_complete_cross_model_intelligence(self):
        from cyber_lion.mission_control import control_plane_reconnaissance as recon
        calls=[]
        def create(mid,question):
            calls.append((mid,len(question)))
            raise RuntimeError("EXPIRED_SAAS_SESSION")
        advisory=recon.ensure_saas_advisory(
            self.c,self.mid,"CROSS_MODEL_RECON",self.contract,
            self.edigest,{"bounded":"test-source-evidence"},self.mc.now,
            create_request=create,
            request_status=lambda req_id: (_ for _ in ()).throw(
                AssertionError("no nonexistent SaaS request may be polled")
            ),
        )
        self.assertTrue(advisory["required"])
        self.assertEqual(advisory["state"],"UNAVAILABLE_OR_SESSION_MEDIATED")
        self.assertIsNone(advisory["response_digest"])
        self.assertIsNone(advisory["receipt_digest"])
        self.assertEqual(len(calls),1)
        synthetic_intel={
            "bundle_digest":"a"*64,
            "local_model_trajectories":[{"state":"PASS"}],
            "saas_advisories":[{
                "state":"UNAVAILABLE_OR_SESSION_MEDIATED",
                "response_digest":None,"receipt_digest":None,
            }],
        }
        facts,_=recon.derive_facts(
            self.c,self.mid,"CROSS_MODEL_RECON",self.contract,
            {"domains":{}},
            artifacts={"CONTROL_PLANE_INTELLIGENCE_BUNDLE":synthetic_intel},
            baseline=None,
            local_analysis={"trajectories":[{"raw_digest":"b"*64}]},
            saas_advisory=advisory,
        )
        self.assertEqual(set(facts),{"CROSS_MODEL_INTELLIGENCE_BOUND"})
        self.assertFalse(facts["CROSS_MODEL_INTELLIGENCE_BOUND"])

    def test_incomplete_preexisting_evidence_bundle_is_quarantined(self):
        """Legacy or forged artifact cannot accidentally supply missing model_view."""
        with (
            patch.object(self.mc,"_current_master_identity",
                         return_value=(self.source["head"],self.source["tree"])),
            patch.object(native.operator_control,"autonomy_allowed",return_value=True),
            patch.object(native,"native_llamacpp_transport") as model,
        ):
            result=self.mc.advance_native_cognitive_phase_zero_once()
        self.assertEqual(result["state"],"WAITING")
        self.assertEqual(result["gate"],"NATIVE_EVIDENCE_BUNDLE_REACQUIRE_REQUIRED")
        model.assert_not_called()
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM mission_native_cognitive_trajectories").fetchone()[0],0)
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM mission_recon_material_leases").fetchone()[0],0)

    def test_phase_one_wait_gate_not_overwritten_by_full_fleet_rebinder(self):
        """A source-bound completed phase 0 cannot be rewound to 32 MD readiness."""
        self.c.execute(
            "UPDATE mission_phases SET status='PASS',progress=100.0 WHERE mission_id=? AND phase_id='CROSS_MODEL_RECON'",
            (self.mid,),
        )
        self.c.execute(
            "UPDATE missions SET state='WAITING' WHERE mission_id=?",(self.mid,)
        )
        self.mc.driver_wait_for_execution_binding(
            self.c,self.mid,self.mc.now,
            blocking_gate="PHASE1_ONE_WORKER_PREACTIVATION_REQUIRED",
            waiting_reason="Phase zero verified",next_action="WAIT_FOR_ADMITTED_ONE_WORKER",
        )
        self.c.commit()
        with (
            patch.object(self.mc.operator_control,"autonomy_allowed",return_value=True),
            patch.object(self.mc,"_docker_local_model_currentness",
                         side_effect=AssertionError("premature all-fleet probe")) as fleet,
        ):
            res=self.mc.reconcile_activated_unbound_docker_once(force=True)
        fleet.assert_not_called()
        self.assertEqual(res["rebound"],[])
        self.assertEqual(res["waiting"],[
            {"mission_id":self.mid,"gate":"PHASE1_ONE_WORKER_PREACTIVATION_REQUIRED"}
        ])
        d=self.c.execute(
            "SELECT state,blocking_gate,next_action FROM mission_execution_drivers WHERE mission_id=?",
            (self.mid,)
        ).fetchone()
        self.assertEqual(tuple(d),(
            "WAITING","PHASE1_ONE_WORKER_PREACTIVATION_REQUIRED",
            "WAIT_FOR_ADMITTED_ONE_WORKER"
        ))

    def test_native_transport_is_fixed_model_endpoint_no_proxy_no_redirect(self):
        import hashlib
        import urllib.request
        messages=[{"role":"system","content":"proposal-only"},
                  {"role":"user","content":"Return JSON, no material changes."}]
        response='{"claims":[],"unknowns":[],"summary":"no effect"}'
        raw=json.dumps({"choices":[{"message":{"content":response},"finish_reason":"stop"}],
                        "model":"registered-local"}).encode()
        called=[]
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):return None
            def read(self,_):return raw
        class Opener:
            def open(self,request,timeout):
                called.append((request.full_url,request.method,request.data,timeout))
                return Response()
        def build(*handlers):
            self.assertEqual(len(handlers),2)
            self.assertIsInstance(handlers[0],urllib.request.ProxyHandler)
            self.assertEqual(handlers[0].proxies,{})
            self.assertIsInstance(handlers[1],native._NoRedirect)
            return Opener()
        with patch.object(native.urllib.request,"build_opener",side_effect=build):
            text,bytes_value,model,request_hash=native.native_llamacpp_transport(messages)
        self.assertEqual(text,response)
        self.assertEqual(bytes_value,raw)
        self.assertEqual(model,"registered-local")
        self.assertEqual(len(called),1)
        self.assertEqual(called[0][0],"http://172.25.128.1:8772/v1/chat/completions")
        self.assertEqual(called[0][1],"POST")
        self.assertEqual(hashlib.sha256(called[0][2]).hexdigest(),request_hash)
        self.assertEqual(called[0][3],30)
        with self.assertRaisesRegex(native.NativeCognitiveError,"LOCAL_REDIRECT_DENIED"):
            native._NoRedirect().redirect_request(None,None,None,None,None,None)
        with patch.object(native,"FIXED_ENDPOINT","http://outside.example.org:8772"):
            with self.assertRaisesRegex(native.NativeCognitiveError,"NATIVE_ENDPOINT_SUBSTITUTION_DENIED"):
                native.native_llamacpp_transport(messages)

    def test_mismatched_transport_request_bytes_is_quarantined_before_receipt(self):
        prepared=self.intent()
        def wrong_transport(messages):
            a=self.fake_transport(messages)
            return (a[0],a[1],a[2],"f"*64)
        with self.assertRaisesRegex(native.NativeCognitiveError,"NATIVE_HTTP_REQUEST_BYTES_DRIFT"):
            self.send(prepared,wrong_transport)
        self.assertEqual(self.c.execute(
            "SELECT state FROM mission_native_cognitive_trajectories").fetchone()[0],
            "SEND_UNKNOWN")
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM mission_native_cognitive_trajectories WHERE receipt_digest IS NOT NULL"
        ).fetchone()[0],0)

    def test_exact_native_trajectories_produce_three_durable_unassigned_receipts(self):
        from cyber_lion.mission_control import control_plane_reconnaissance as recon
        calls=[]
        def transport(messages):
            role=next(x for x in recon.TRAJECTORY_ROLES if x in messages[1]["content"])
            calls.append(role)
            text=json.dumps({"claims":[],"unknowns":[role],"summary":"Proposal: "+role})
            raw=json.dumps({"choices":[{"message":{"content":text},"finish_reason":"stop"}]}).encode()
            return text,raw,"local-mock",__import__("hashlib").sha256(native._http_payload(messages)).hexdigest()
        with patch.object(native.operator_control,"autonomy_allowed",return_value=True):
            for i in range(3):
                result=recon.ensure_native_local_trajectories(
                    self.c,self.mid,"CROSS_MODEL_RECON",self.contract,self.edigest,
                    {"bounded":"source-view"},1,self.mc.now,
                    current_source=self.source,transport=transport,
                )
            self.assertTrue(result["complete"])
            self.assertEqual(len(result["result_digests"]),3)
            self.assertEqual(len(set(result["result_digests"])),3)
            self.assertFalse(result["independent_providers"])
            self.assertTrue(result["common_model_ancestor"])
            analysis=recon._analysis_from_trajectory_rows(
                self.c,self.mid,"CROSS_MODEL_RECON",self.edigest,
                native_current_source=self.source,
                native_contract_digest=self.contract["contract_digest"],
            )
            self.assertEqual(len(analysis["trajectories"]),3)
            self.assertEqual(analysis["independence_state"],
                             "SHARED_NATIVE_LOCAL_MODEL_ANCESTOR")
            self.assertFalse(analysis["model_attested"])
            self.assertIn("NATIVE_LOCAL_TRAJECTORIES_NOT_INDEPENDENT_MODELS",
                          analysis["unknowns"])
            self.assertEqual(calls,list(recon.TRAJECTORY_ROLES))
            repeat=recon.ensure_native_local_trajectories(
                    self.c,self.mid,"CROSS_MODEL_RECON",self.contract,self.edigest,
                    {"bounded":"source-view"},1,self.mc.now,
                    current_source=self.source,transport=transport,
                )
            self.assertTrue(repeat["complete"])
        self.assertEqual(len(calls),3)
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM mission_recon_trajectories WHERE mission_id=? AND assignment_id IS NULL",
            (self.mid,)).fetchone()[0],3)
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM mission_recon_material_leases WHERE mission_id=?",
            (self.mid,)).fetchone()[0],0)
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=?",
            (self.mid,)).fetchone()[0],0)

    def test_native_phase_zero_unknown_send_does_not_repeat_through_recon(self):
        from cyber_lion.mission_control import control_plane_reconnaissance as recon
        called=0
        def unavailable(messages):
            nonlocal called
            called+=1
            raise TimeoutError("outcome cannot be reconciled")
        with patch.object(native.operator_control,"autonomy_allowed",return_value=True):
            for i in range(2):
                result=recon.ensure_native_local_trajectories(
                    self.c,self.mid,"CROSS_MODEL_RECON",self.contract,self.edigest,
                    {"bounded":"source-view"},1,self.mc.now,
                    current_source=self.source,transport=unavailable,
                )
                self.assertEqual(result["gate"],"NATIVE_LOCAL_SEND_UNKNOWN_RECONCILE_ONLY")
        self.assertEqual(called,1)
        self.assertEqual(self.c.execute(
            "SELECT state FROM mission_native_cognitive_trajectories").fetchone()[0],
            "SEND_UNKNOWN")

    def test_existing_scheduler_can_reach_zero_material_path_without_docker(self):
        with (
            patch.object(self.mc,"_current_master_identity",
                         return_value=(self.source["head"],self.source["tree"])),
            patch.object(native.operator_control,"autonomy_allowed",return_value=True),
            patch.object(self.mc.control_recon,"execute_phase",
                         return_value={"state":"WAITING","gate":"NATIVE_LOCAL_NEXT_ROLE_PENDING"}) as execute,
        ):
            result=self.mc.advance_native_cognitive_phase_zero_once()
        self.assertEqual(result["gate"],"NATIVE_LOCAL_NEXT_ROLE_PENDING")
        self.assertEqual(execute.call_count,1)
        kw=execute.call_args.kwargs
        self.assertEqual(kw["native_current_source"],self.source)
        self.assertIs(kw["native_transport"],native.native_llamacpp_transport)
        self.assertEqual(kw["driver_generation"],1)
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM material_workers WHERE mission_id=?",(self.mid,)
        ).fetchone()[0],0)
        self.assertEqual(self.c.execute(
            "SELECT COUNT(*) FROM mission_recon_material_leases WHERE mission_id=?",(self.mid,)
        ).fetchone()[0],0)

    def test_unregistered_phase_or_role_refused_without_network(self):
        with patch.object(native.operator_control,"autonomy_allowed",return_value=True):
            with self.assertRaisesRegex(native.NativeCognitiveError,"PHASE_ZERO_ONLY"):
                native.prepare_intent(self.c,mission_id=self.mid,phase_id="BUILD_CROSS_MODEL_ARTIFACT",
                    role=self.role,evidence_bundle_digest=self.edigest,messages=self.messages,
                    contract_digest=self.contract["contract_digest"],current_source=self.source,now_fn=self.mc.now)
        self.role="OPERATE_WINDOWS"
        with self.assertRaisesRegex(native.NativeCognitiveError,"UNREGISTERED_TRAJECTORY_ROLE"):
            self.intent()


if __name__=="__main__":
    unittest.main()
