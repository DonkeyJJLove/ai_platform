from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cyber_lion.mission_control import global_scheduler as gs
from cyber_lion.mission_control import control_plane_reconnaissance as cr
from cyber_lion.contracts.action_ir import CanonicalActionIR


def now():
    return "2026-09-15T12:00:00Z"


class ControlPlaneReconnaissanceTests(unittest.TestCase):
    def conn(self):
        c=sqlite3.connect(":memory:");c.row_factory=sqlite3.Row;gs.migrate(c,now);return c

    def test_migration_v4_and_artifact_store_are_non_authoritative(self):
        c=self.conn()
        migrations=[tuple(r) for r in c.execute("SELECT version,schema_id FROM mission_scheduler_migrations ORDER BY version")]
        self.assertIn((4,"lion.control-plane-reconnaissance/v1"),migrations)
        self.assertIn((5,"lion.recon-evidence-reacquisition/v1"),migrations)
        for name in ("mission_artifacts","mission_recon_material_leases","mission_recon_trajectories","mission_recon_saas_advisories","mission_recon_evidence_generations"):
            self.assertTrue(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())
        first=gs.put_artifact(c,"M","A",{"x":1},now,phase_id="P")
        same=gs.put_artifact(c,"M","A",{"x":1},now,phase_id="P")
        self.assertEqual((first["artifact_id"],first["content_digest"]),(same["artifact_id"],same["content_digest"]))
        with self.assertRaisesRegex(ValueError,"non-authoritative"):
            gs.put_artifact(c,"M","A2",{"x":1},now,authority_effect="WRITE")
        c.close()

    def test_recipe_registry_covers_current_target_vocabulary_and_unknown_fails_closed(self):
        currentness={
            "ALL_RECON_PHASE_RECEIPTS","BROKER_DB","BROKER_SOURCE","CANONICAL_PROCESS_LANGUAGE_SOURCE","CONTROL_PLANE_INTELLIGENCE_BUNDLE",
            "CURRENT_BROKER_STATE","CURRENT_POST_ASTRA_MISSION","DUAL_RESULT_STORE","GITHUB_MASTER","LIVE_8766_PACKAGE","LIVE_8766_RUNTIME",
            "LIVE_8780_RUNTIME","LIVE_BROKER_PROJECTION","LIVE_MISSION_CONTROL_PROJECTION","LIVE_PANEL_PROJECTION","LOCAL_PANEL_CHECKOUT",
            "LPCL12_PROCESS_CONTRACT","MISSION_CONTROL_DB","MISSION_CONTROL_SOURCE","PANEL_SOURCE","POST_RECON_BASELINE","PRE_RECON_BASELINE",
            "PRIVILEGED_BROKER_PACKAGE","RECON_EVIDENCE_SET","SAAS_SESSION_BINDINGS","THREAD_DB","THREAD_DELIVERY_SOURCE",
            "EXACT_GITHUB_MASTER","CURRENT_BROKER_DB",
        }
        evidence={
            "API_ROUTE_MAP","AUTOMATIC_CONSUMER_EVIDENCE","BINDING_DIFF","BINDING_STATE_COUNTS","BROKER_RECEIPT_ROWS","CAPABILITY_REGISTRY_READBACK",
            "CLAIM_GENERATION_READBACK","CLAIM_TO_EVIDENCE_MAP","CONTROL_PROVIDER_ROUTES","COUNTEREXAMPLES","CROSS_MISSION_BLOCKING_GATE",
            "CROSS_MISSION_RECEIPTS","CROSS_MISSION_STATE","DEDUPLICATION_RULE","DELETION_BEHAVIOR","DELIVERY_CANDIDATES","DRIVER_STATE_MODEL",
            "DUAL_CREATE_PATH","FIELD_BY_FIELD_PROJECTION_COMPARISON","FRONTEND_REVISION","GIT_IDENTITY","HEAD_TREE_READBACK","HEALTH_READBACK",
            "IMPLEMENTATION_GAP_MATRIX","INTELLIGENCE_BUNDLE","INTELLIGENCE_BUNDLE_DIGEST","JOIN_CONDITIONS","LANGUAGE_GAP_MATRIX","LOCAL_RESULT_PATH",
            "LPCL12_COMPILER_READBACK","MIGRATION_HISTORY","MODEL_ENDPOINT","PACKAGE_IDENTITY","PACKAGE_SHA256","PARSER_COMPARISON","PENDING_REQUEST_STATE",
            "PREFLIGHT_READBACK","PROCESS_ARGUMENTS","PROCESS_CONTRACT_STATE","PROCESS_IDENTITY","PROGRESS_STATE_HISTORY","RECEIPT_LINKAGE",
            "RECEIPT_STATE_COUNTS","REPOSITORY_DIFF","REQUEST_COUNT_DIFF","REQUEST_STATE_COUNTS","RESPONDED_ROWS","RUNTIME_PROCESS_IDENTITY",
            "SAAS_LINK_PATH","SCHEDULER_STATE_MODEL","SCHEMA_READBACK","SESSION_STATE","SQLITE_IDENTITY","STATE_DIFF","SUCCESSOR_CAPABILITY_MATRIX",
            "SUCCESSOR_COMPLETION_CONTRACT","SUCCESSOR_LPCL_PROPOSAL_DIGEST","THREAD_RUNTIME","TRANSPORT_CLASSIFICATION","UNCERTAINTY_REGISTER","WORKTREE_STATE",
            "EXACT_SOURCE_READBACK","CONTROL_PLANE_INTELLIGENCE_BUNDLE_READBACK",
        }
        self.assertEqual((currentness|evidence)-set(cr.TOKEN_DOMAIN),set())
        contract={"currentness_requirements":["UNKNOWN_X"],"evidence_requirements":[]}
        self.assertEqual(cr.build_observation_plan(contract)["unsupported_tokens"],["UNKNOWN_X"])

    def test_successor_lineage_resolves_exact_proposal_and_intelligence_digest(self):
        import hashlib
        c=self.conn()
        c.execute("CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,spec_digest TEXT,source_head TEXT,source_tree TEXT)")
        lpcl="MISSION_ID=SUCCESSOR\nCONTROL_LANGUAGE=LPCL/1.2\n";dg=hashlib.sha256(lpcl.encode()).hexdigest();intel_dg="a"*64
        c.execute("INSERT INTO missions VALUES(?,?,?,?,?)",("RECON","COMPLETE","b"*64,"1"*40,"2"*40))
        c.execute("INSERT INTO missions VALUES(?,?,?,?,?)",("SUCCESSOR","RUNNING",dg,"3"*40,"4"*40))
        gs.put_artifact(c,"RECON","CONTROL_PLANE_INTELLIGENCE_BUNDLE",{"bundle_digest":intel_dg,"authority_effect":"NONE"},now,schema_id=cr.INTELLIGENCE_SCHEMA)
        gs.put_artifact(c,"RECON","SUCCESSOR_REPAIR_LPCL_PROPOSAL",{"proposal_digest":dg,"lpcl_text":lpcl,"intelligence_bundle_digest":intel_dg,"authority_effect":"NONE"},now,schema_id=cr.SUCCESSOR_SCHEMA)
        out=cr._successor_lineage_snapshot(c,"SUCCESSOR")
        self.assertTrue(out["valid"],out);self.assertEqual(out["source_mission_id"],"RECON");self.assertEqual(out["proposal_digest"],dg);self.assertEqual(out["intelligence_bundle_digest"],intel_dg)
        gs.put_artifact(c,"RECON","CONTROL_PLANE_INTELLIGENCE_BUNDLE",{"bundle_digest":"c"*64,"authority_effect":"NONE"},now,schema_id=cr.INTELLIGENCE_SCHEMA)
        bad=cr._successor_lineage_snapshot(c,"SUCCESSOR")
        self.assertFalse(bad["valid"]);self.assertEqual(bad["reason"],"PREDECESSOR_INTELLIGENCE_DIGEST_MISMATCH")
        c.close()

    def test_repair_baseline_requires_exact_registered_source_live_package_broker_and_lineage(self):
        c=self.conn();dg="d"*64;head="1"*40;tree="2"*40
        observations={"domains":{
            "panel":{"runtime":{"pid":7,"runtime_source_sha256":"a"*64,"gateway_source_sha256":"b"*64},"repo":{"github_master":{"head":head,"tree":tree}}},
            "mission_control":{"runtime_identity":{"pid":9,"source_hashes":{"mission_control_v3.py":"c"*64,"cyber_lion/mission_control/control_plane_reconnaissance.py":"e"*64}},"db":{"integrity":"ok"},"mission":{"mission_id":"SUCCESSOR","spec_digest":dg,"source_head":head,"source_tree":tree},"preflight":{},"contracts":[]},
            "broker":{"schema_digest":"f"*64,"request_state_counts":{},"binding_state_counts":{},"responded_count":0,"receipt_count":0,"pending_count":0,"transports":[],"autonomous_transport_claimed":False},
            "successor_lineage":{"valid":True,"proposal_digest":dg,"mission_spec_digest":dg,"intelligence_bundle_digest":"9"*64,"expected_intelligence_bundle_digest":"9"*64},
        }}
        contract={"completion_predicates":["REPAIR_BASELINE_FROZEN=PASS"]}
        facts,detail=cr.derive_facts(c,"SUCCESSOR","FREEZE_REPAIR_BASELINE",contract,observations,artifacts={},baseline=None,local_analysis=None,saas_advisory=None)
        self.assertEqual(facts,{"REPAIR_BASELINE_FROZEN":True});self.assertTrue(detail["successor_baseline"]["predecessor_intelligence_bound"])
        observations["domains"]["panel"]["repo"]["github_master"]["tree"]="0"*40
        facts,_=cr.derive_facts(c,"SUCCESSOR","FREEZE_REPAIR_BASELINE",contract,observations,artifacts={},baseline=None,local_analysis=None,saas_advisory=None)
        self.assertEqual(facts,{"REPAIR_BASELINE_FROZEN":False})
        c.close()

    def test_no_target_phase_name_switch_exists(self):
        source=Path(cr.__file__).read_text(encoding="utf-8")
        for phase in (
            "FREEZE_MULTI_CARRIER_BASELINE","RECON_PANEL_8780_RUNTIME","RECON_LPCL_INTAKE_AND_PREFLIGHT",
            "RECON_MISSION_CONTROL_8766_RUNTIME","RECON_BROKER_STORAGE_LIFECYCLE","RECON_SAAS_TRANSPORT_TRUTH",
            "RECON_THREAD_DELIVERY_PATH","RECON_DUAL_EVALUATION_PATH","RECON_REVISION_COHERENCE","AUDIT_PANEL_TRUTH_PROJECTION",
            "AUDIT_BROKER_RECEIPT_COMPLETENESS","RECON_POST_ASTRA_MISSION","ASSESS_LPCL_1_2_LANGUAGE_GAPS",
            "BUILD_CONTROL_PLANE_INTELLIGENCE","BUILD_SUCCESSOR_REPAIR_CONTRACT","RECON_TERMINAL_VALIDATION",
        ):
            self.assertNotIn(phase,source)

    def test_material_leases_use_shared_pool_and_semantic_workers(self):
        c=self.conn()
        c.execute("CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT,pod_uid TEXT,logical_id TEXT,phase TEXT,ready INTEGER,restarts INTEGER,pod_ip TEXT,observed_at TEXT)")
        for i in range(1,65):c.execute("INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)",("M",f"p{i}",f"u{i}",f"MD{i:03d}","Running",1,0,None,now()))
        contract={"ordinal":13,"execution_class":"COGNITIVE","currentness_requirements":["RECON_EVIDENCE_SET"],"evidence_requirements":["LANGUAGE_GAP_MATRIX"]}
        rows=cr.ensure_material_leases(c,"M","P",contract,now)
        mids={r["material_drone_id"] for r in rows}
        self.assertEqual(len(rows),4)
        self.assertTrue({"MD025","MD026","MD027"}<=mids)
        self.assertTrue(all(r["execution_mode"]==cr.MATERIAL_EXECUTION_MODE for r in rows))
        cr.release_material_leases(c,"M","P",now)
        self.assertEqual({r[0] for r in c.execute("SELECT DISTINCT state FROM mission_recon_material_leases")},{"RELEASED"})
        c.close()

    def test_new_composite_observation_opens_explicit_evidence_reacquisition_generation(self):
        from unittest.mock import patch
        c=self.conn()
        c.execute("CREATE TABLE mission_execution_drivers(mission_id TEXT PRIMARY KEY,state TEXT,blocking_gate TEXT,generation INTEGER)")
        c.execute("INSERT INTO mission_execution_drivers VALUES('M','WAITING','EVIDENCE_INCOMPLETE',7)")
        panel={"runtime":{"runtime_source_sha256":"a"*64,"gateway_source_sha256":"b"*64,"feature_vector_digest":"c"*64},"repo":{"local_head":"1"*40,"local_tree":"2"*40,"github_master":{"head":"3"*40,"tree":"4"*40}},"thread_db":{"identity_digest":"d"*64,"schema_version":6,"integrity":"ok"},"source_features":{"x":True}}
        mc={"runtime_identity":{"source_hashes":{"mission_control_v3.py":"e"*64},"parser_sha256":"f"*64},"db":{"schema_version":40},"mission":{"mission_id":"M","spec_digest":"5"*64,"source_head":"6"*40,"source_tree":"7"*40,"adapter":"A"},"preflight":{"bound_count":1},"contracts":[{"contract_digest":"8"*64}],"bindings":[{"binding_digest":"9"*64}]}
        lang={"source_hashes":{"cyber_lion/process_language/lpcl.py":"a1"*32,"cyber_lion/contracts/phase_execution_contract.py":"b1"*32},"canonical_lpcl_source_present":True,"lpcl12_compiler_present":True}
        old_obs={"phase_id":"P","domains":{"panel":panel,"mission_control":mc,"process_language":lang}}
        old_fp=cr.observation_generation_fingerprint(old_obs)
        content={"schema":cr.EVIDENCE_BUNDLE_SCHEMA,"mission_id":"M","phase_id":"P","observations":old_obs,"model_view":{},"reacquisition_generation":1,"observation_fingerprint":old_fp,"authority_effect":"NONE"}
        art=gs.put_artifact(c,'M','RECON_EVIDENCE_BUNDLE',content,now,phase_id='P',schema_id=cr.EVIDENCE_BUNDLE_SCHEMA)
        cr._record_bundle_generation(c,'M','P',art,now)
        new_obs=json.loads(json.dumps(old_obs));new_obs["domains"]["mission_control"]["runtime_identity"]["parser_sha256"]="c1"*32
        new_fp=cr.observation_generation_fingerprint(new_obs)
        contract={"currentness_requirements":[],"evidence_requirements":[]}
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'source.db';sqlite3.connect(db).close()
            with patch.object(cr,'collect_observations',return_value=(new_obs,[])):
                req=cr.evidence_reacquisition_request(c,'M','P',gs.artifact(c,'M','RECON_EVIDENCE_BUNDLE',phase_id='P'),contract,db_path=db)
                self.assertIsNotNone(req);self.assertEqual(req['next_generation'],2);self.assertEqual(req['current_observation_fingerprint'],old_fp);self.assertEqual(req['new_observation_fingerprint'],new_fp)
                c.execute("UPDATE mission_execution_drivers SET state='ACTIVE',blocking_gate=NULL,generation=8 WHERE mission_id='M'");c.commit()
                active_req=cr.evidence_reacquisition_request(c,'M','P',gs.artifact(c,'M','RECON_EVIDENCE_BUNDLE',phase_id='P'),contract,db_path=db,require_parked=False)
                self.assertIsNotNone(active_req);self.assertEqual(active_req['new_observation_fingerprint'],new_fp)
                self.assertIsNone(cr.evidence_reacquisition_request(c,'M','P',gs.artifact(c,'M','RECON_EVIDENCE_BUNDLE',phase_id='P'),contract,db_path=db))
        gens=gs.recon_evidence_generations(c,'M','P');self.assertEqual(len(gens),1);self.assertEqual(gens[0]['evidence_bundle_digest'],art['content_digest'])
        c.close()

    def test_three_local_trajectories_are_idempotent_and_distinct(self):
        c=self.conn()
        c.execute("CREATE TABLE mission_execution_drivers(mission_id TEXT PRIMARY KEY,generation INTEGER NOT NULL)")
        c.execute("INSERT INTO mission_execution_drivers VALUES('M',7)")
        contract={"ordinal":13,"execution_class":"COGNITIVE","currentness_requirements":[],"evidence_requirements":[]}
        first=cr.ensure_local_trajectories(c,"M","P",contract,"e"*64,{"x":1},7,now)
        self.assertFalse(first["complete"])
        rows=[dict(r) for r in c.execute("SELECT * FROM mission_recon_trajectories ORDER BY trajectory_role")]
        self.assertEqual(len(rows),3);self.assertEqual(len({r["assignment_id"] for r in rows}),3)
        for row in rows:
            claimed=gs.claim_assignment(c,row["assignment_id"],now,expected_material_drone_id=c.execute("SELECT material_drone_id FROM mission_execution_assignments WHERE assignment_id=?",(row["assignment_id"],)).fetchone()[0])
            result={"kind":"LOCAL_MODEL_INFERENCE","trajectory_role":row["trajectory_role"],"evidence_bundle_digest":"e"*64,"response_text":"same answer","response_digest":"a"*64,"authority_effect":"NONE"}
            rec=gs.record_receipt(c,row["assignment_id"],result,now,material_drone_id=claimed["material_drone_id"],lease_generation=claimed["lease_generation"],status="PASS",authority_effect="NONE")
            gs.store_assignment_payload(c,row["assignment_id"],rec["receipt_id"],result,now)
        second=cr.ensure_local_trajectories(c,"M","P",contract,"e"*64,{"x":1},7,now)
        self.assertTrue(second["complete"]);self.assertTrue(second["distinct_result_digests"])
        count=c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id='M' AND phase_id='P'").fetchone()[0]
        cr.ensure_local_trajectories(c,"M","P",contract,"e"*64,{"x":1},7,now)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id='M' AND phase_id='P'").fetchone()[0],count)
        c.close()

    def test_saas_unavailable_is_noncritical_and_deduplicated(self):
        c=self.conn();contract={"execution_class":"COGNITIVE","evidence_requirements":[]}
        calls=[]
        def create(mid,q):calls.append((mid,q));raise RuntimeError("session mediated")
        one=cr.ensure_saas_advisory(c,"M","P",contract,"f"*64,{"x":1},now,create_request=create,request_status=lambda rid:None)
        two=cr.ensure_saas_advisory(c,"M","P",contract,"f"*64,{"x":1},now,create_request=create,request_status=lambda rid:None)
        self.assertEqual(one["state"],"UNAVAILABLE_OR_SESSION_MEDIATED");self.assertEqual(two["state"],"UNAVAILABLE_OR_SESSION_MEDIATED")
        self.assertEqual(len(calls),1);self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_recon_saas_advisories").fetchone()[0],1)
        c.close()

    def test_database_observation_connection_is_physically_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'ro.db';w=sqlite3.connect(path);w.execute('CREATE TABLE x(v INTEGER)');w.execute('INSERT INTO x VALUES(1)');w.commit();w.close()
            ro=cr.open_read_only(path)
            self.assertEqual(ro.execute('SELECT v FROM x').fetchone()[0],1)
            with self.assertRaises(sqlite3.OperationalError):ro.execute('INSERT INTO x VALUES(2)')
            ro.close()

    def test_action_ir_recon_boundary_is_read_only_pinned(self):
        # Build through the same producer contract rather than reimplementing validation.
        value={
          'schema_version':'1.0.0','action_id':'generic:'+'a'*40,'kind':'repository.observe','intent_ref':'M:P','mission_ref':'M','autonomy_ref':'GENERIC_LPCL_PHASE','bean_ref':'CONTROL_PLANE_RECONNAISSANCE',
          'target':{'host':'LION-AUTH-LAB','environment':'MISSION_CONTROL_V3','runtime':'CONTROL_PLANE_RECON'},
          'authority_request':{'domain':'mission_control','capability':cr.CAPABILITY_ID,'grant_ref':None},
          'boundary':{'shell':False,'network':'READ_ONLY_PINNED','filesystem_read':['/tmp/x'],'filesystem_write':[],'process_children':[],'timeout_ms':60000,'max_processes':1,'memory_limit_bytes':134217728},
          'preconditions':['LIVE_8766_RUNTIME'],'expected_effects':['READ_ONLY_EVIDENCE'],'forbidden_effects':['FILESYSTEM_WRITE'],'observation':{'observer_class':'deterministic_independent','required_events':['PROCESS_IDENTITY']},'reconciliation':{'mode':'EXACT','receipt':'REQUIRED'},
        }
        ir=CanonicalActionIR.from_mapping(value)
        parsed=ir.as_dict();self.assertFalse(parsed['boundary']['shell']);self.assertEqual(parsed['boundary']['network'],'READ_ONLY_PINNED');self.assertEqual(parsed['boundary']['filesystem_write'],[])

    def test_thread_delivery_exact_once_source_feature_detector_matches_mapping_syntax(self):
        from tools.lion_local_intelligence_runtime import _recon_source_features
        root=Path(__file__).resolve().parents[2]
        features=_recon_source_features(root)
        self.assertTrue(features["thread_delivery_exact_once"])
        self.assertTrue(features["dual_join"])

    def test_windows_observation_fingerprint_binds_loaded_semantics_and_is_stable(self):
        from tools.lion_local_intelligence_runtime import _recon_observation_fingerprint
        common=dict(phase='P',runtime_loaded_sha='a'*64,gateway_loaded_sha='b'*64,local={'head':'c'*40,'tree':'d'*40},github={'head':'e'*40,'tree':'f'*40},thread_identity='1'*64)
        one,fd1=_recon_observation_fingerprint(features={'thread_delivery_exact_once':False,'dual_join':False},**common)
        same,fd_same=_recon_observation_fingerprint(features={'thread_delivery_exact_once':False,'dual_join':False},**common)
        changed,fd2=_recon_observation_fingerprint(features={'thread_delivery_exact_once':True,'dual_join':True},**common)
        self.assertEqual((one,fd1),(same,fd_same))
        self.assertNotEqual(one,changed)
        self.assertNotEqual(fd1,fd2)

    def test_composite_observation_fingerprint_tracks_semantic_domains_not_heartbeat_noise(self):
        panel={"runtime":{"runtime_source_sha256":"a"*64,"gateway_source_sha256":"b"*64,"feature_vector_digest":"c"*64},"repo":{"local_head":"d"*40,"local_tree":"e"*40,"github_master":{"head":"f"*40,"tree":"1"*40}},"thread_db":{"identity_digest":"2"*64},"source_features":{"x":True}}
        mc={"runtime_identity":{"source_hashes":{"mission_control_v3.py":"3"*64},"parser_sha256":"4"*64},"db":{"schema_version":40},"mission":{"mission_id":"M","spec_digest":"5"*64,"source_head":"6"*40,"source_tree":"7"*40,"adapter":"A"},"preflight":{"bound_count":1},"contracts":[{"contract_digest":"8"*64}],"bindings":[{"binding_digest":"9"*64}],"driver":{"heartbeat_at":"t1"},"scheduler":{"heartbeat_at":"t1"}}
        lang={"source_hashes":{"cyber_lion/process_language/lpcl.py":"a1"*32,"cyber_lion/contracts/phase_execution_contract.py":"b1"*32},"canonical_lpcl_source_present":True,"lpcl12_compiler_present":True}
        one=cr.observation_generation_fingerprint({"phase_id":"P","domains":{"panel":panel,"mission_control":mc,"process_language":lang}})
        noisy=json.loads(json.dumps(mc));noisy["driver"]["heartbeat_at"]="t2";noisy["scheduler"]["heartbeat_at"]="t2"
        same=cr.observation_generation_fingerprint({"phase_id":"P","domains":{"panel":panel,"mission_control":noisy,"process_language":lang}})
        changed=json.loads(json.dumps(mc));changed["runtime_identity"]["parser_sha256"]="c1"*32
        diff_mc=cr.observation_generation_fingerprint({"phase_id":"P","domains":{"panel":panel,"mission_control":changed,"process_language":lang}})
        changed_lang=json.loads(json.dumps(lang));changed_lang["source_hashes"]["cyber_lion/process_language/lpcl.py"]="d1"*32
        diff_lang=cr.observation_generation_fingerprint({"phase_id":"P","domains":{"panel":panel,"mission_control":mc,"process_language":changed_lang}})
        self.assertEqual(one,same)
        self.assertNotEqual(one,diff_mc)
        self.assertNotEqual(one,diff_lang)

    def test_successor_proposal_is_artifact_only_and_self_validating_lpcl12(self):
        intel={"findings":[],"claim_to_evidence":[],"root_cause_candidates":[],"unknowns":[],"bundle_digest":"f"*64}
        proposal=cr._successor_proposal(intel,{"recommended_control_language":"LPCL/1.2"})
        self.assertFalse(proposal["registered"]);self.assertFalse(proposal["authorized"])
        self.assertIn("CONTROL_LANGUAGE=LPCL/1.2",proposal["lpcl_text"]);self.assertEqual(proposal["proposal_digest"],__import__('hashlib').sha256(proposal["lpcl_text"].encode()).hexdigest())
        self.assertTrue(proposal["validation"]["valid"]);self.assertEqual(proposal["validation"]["contract_count"],8)
        self.assertEqual(proposal["intelligence_bundle_digest"],"f"*64)
        self.assertEqual(set(proposal["required_capabilities"]),{"CONTROL_PLANE_RECONNAISSANCE","CONTROL_PLANE_REPAIR","REPOSITORY_CANDIDATE_PREPARE","BROKER_RECONCILIATION","PANEL_ACCEPTANCE"})
        pairs=cr._generated_lpcl_pairs(proposal["lpcl_text"]);phases=[{"id":spec["id"]} for spec in cr._successor_phase_profiles()]
        contracts=cr.compile_panel_phase_contracts(pairs,pairs["MISSION_ID"],phases,pairs["CONTROL_LANGUAGE"])
        self.assertEqual(len(contracts),8);self.assertTrue(all(c.contract_source=="DECLARED" for c in contracts))

    def test_historical_classifications_prefer_complete_parser_evidence(self):
        c=self.conn();baseline={"preflight":{"invalid_count":0,"bound_count":0,"unbound_count":16}}
        incomplete={"schema":cr.EVIDENCE_BUNDLE_SCHEMA,"observations":{"phase_id":"P0","domains":{"process_language":{"source_hashes":{"cyber_lion/process_language/lpcl.py":"1"*64}}}},"authority_effect":"NONE"}
        gs.put_artifact(c,"M","RECON_EVIDENCE_BUNDLE",incomplete,now,phase_id="P0",schema_id=cr.EVIDENCE_BUNDLE_SCHEMA)
        complete_obs={"phase_id":"P1","domains":{"panel":{"source_features":{"lpcl_parser_sha256":"2"*64}},"mission_control":{"runtime_identity":{"parser_sha256":"3"*64}},"process_language":{"source_hashes":{"cyber_lion/process_language/lpcl.py":"4"*64}}}}
        complete={"schema":cr.EVIDENCE_BUNDLE_SCHEMA,"observations":complete_obs,"authority_effect":"NONE"}
        gs.put_artifact(c,"M","RECON_EVIDENCE_BUNDLE",complete,now,phase_id="P1",schema_id=cr.EVIDENCE_BUNDLE_SCHEMA)
        merged,sources=cr.historical_classifications(c,"M",baseline)
        self.assertEqual(merged["parser_semantic_drift"]["classification"],"MULTIPLE_IMPLEMENTATIONS_WITH_CANONICAL_COMPILER")
        self.assertTrue(merged["parser_semantic_drift"]["identified"])
        self.assertEqual(merged["initial_capability_preflight"]["classification"],"VALID_BUT_UNBOUND")
        self.assertTrue(sources["parser_semantic_drift"])
        local={"parser_semantic_drift":{"identified":False,"classification":"INCOMPLETE"}}
        self.assertEqual(cr._merge_classifications(local,merged)["parser_semantic_drift"]["classification"],"MULTIPLE_IMPLEMENTATIONS_WITH_CANONICAL_COMPILER")
        c.close()


if __name__=='__main__':unittest.main()
