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
        for name in ("mission_artifacts","mission_recon_material_leases","mission_recon_trajectories","mission_recon_saas_advisories"):
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
        }
        self.assertEqual((currentness|evidence)-set(cr.TOKEN_DOMAIN),set())
        contract={"currentness_requirements":["UNKNOWN_X"],"evidence_requirements":[]}
        self.assertEqual(cr.build_observation_plan(contract)["unsupported_tokens"],["UNKNOWN_X"])

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

    def test_successor_proposal_is_artifact_only(self):
        intel={"findings":[],"claim_to_evidence":[],"root_cause_candidates":[],"unknowns":[]}
        proposal=cr._successor_proposal(intel,{"recommended_control_language":"LPCL/1.2"})
        self.assertFalse(proposal["registered"]);self.assertFalse(proposal["authorized"])
        self.assertIn("CONTROL_LANGUAGE=LPCL/1.2",proposal["lpcl_text"]);self.assertEqual(proposal["proposal_digest"],__import__('hashlib').sha256(proposal["lpcl_text"].encode()).hexdigest())


if __name__=='__main__':unittest.main()
