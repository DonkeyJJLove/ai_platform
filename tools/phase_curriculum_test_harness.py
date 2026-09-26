from __future__ import annotations

import json
import sqlite3
import unittest

from cyber_lion.mission_control import phase_curriculum as curriculum


def now():
    return "2026-09-26T09:30:00Z"


class PhaseCurriculumTests(unittest.TestCase):
    def db(self):
        c=sqlite3.connect(":memory:")
        c.row_factory=sqlite3.Row
        c.executescript("""
        CREATE TABLE mission_phases(mission_id TEXT,phase_id TEXT,ordinal INTEGER,status TEXT);
        CREATE TABLE mission_phase_execution_contracts(
          mission_id TEXT,phase_id TEXT,execution_class TEXT,capability_classes_json TEXT,effect_ceiling TEXT,
          verify_before_mutate INTEGER,currentness_requirements_json TEXT,evidence_requirements_json TEXT,
          completion_predicates_json TEXT,contract_digest TEXT
        );
        CREATE TABLE mission_generic_phase_plans(
          mission_id TEXT,phase_id TEXT,evidence_json TEXT,evidence_digest TEXT,effect_receipt_digest TEXT,state TEXT
        );
        CREATE TABLE protocol_messages(
          id INTEGER PRIMARY KEY AUTOINCREMENT,mission_id TEXT,phase TEXT,protocol TEXT,payload_json TEXT,payload_digest TEXT,observed_at TEXT
        );
        CREATE TABLE missions(mission_id TEXT,state TEXT,runtime_state TEXT,source_head TEXT,source_tree TEXT,spec_json TEXT);
        CREATE TABLE mission_lineage(mission_id TEXT,root_mission_id TEXT,parent_mission_id TEXT,revision INTEGER,relation TEXT,source_epoch TEXT,source_stage TEXT,source_schema TEXT,created_at TEXT);
        CREATE TABLE mission_revision_compilations(revision_id TEXT,mission_id TEXT,successor_mission_id TEXT,state TEXT,created_at TEXT,activated_at TEXT);
        CREATE TABLE mission_artifacts(
          artifact_id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,phase_id TEXT,artifact_type TEXT NOT NULL,
          schema_id TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,content_digest TEXT NOT NULL,
          content_json TEXT NOT NULL,authority_effect TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
          UNIQUE(mission_id,artifact_type,phase_id)
        );
        """)
        curriculum.migrate(c,now)
        return c

    def contract(self,c,phase_id,currentness,evidence,predicate,ordinal):
        dg=curriculum.digest({"phase":phase_id,"currentness":currentness,"evidence":evidence})
        c.execute("INSERT INTO mission_phase_execution_contracts VALUES(?,?,?,?,?,?,?,?,?,?)",
                  ("M",phase_id,"VERIFY",json.dumps(["EPOCH_CLOSURE_RECONCILIATION"]),"NONE",1,
                   json.dumps(currentness),json.dumps(evidence),json.dumps([predicate+"=PASS"]),dg))
        c.execute("INSERT INTO mission_phases VALUES(?,?,?,?)",("M",phase_id,ordinal,"PASS" if ordinal<6 else "BLOCKED"))
        return dg

    def source_phase(self,c,phase_id,ordinal,currentness,outputs,evidence):
        self.contract(c,phase_id,currentness,outputs,phase_id+"_VERIFIED",ordinal)
        raw=json.dumps(evidence,sort_keys=True)
        c.execute("INSERT INTO mission_generic_phase_plans VALUES(?,?,?,?,?,?)",
                  ("M",phase_id,raw,curriculum.digest(evidence),"receipt-"+phase_id,"PASS"))

    def test_contract_classification_is_semantic_not_phase_id(self):
        local={"execution_class":"VERIFY","capability_classes":["X"],"effect_ceiling":"NONE","verify_before_mutate":True,
               "currentness_requirements":["CURRENT_MISSION_DB"],"evidence_requirements":["TASK_LEDGER"],"completion_predicates":["X=PASS"]}
        live={**local,"currentness_requirements":["LIVE_GIT","LIVE_GITHUB"],"evidence_requirements":["LINEAGE_GRAPH","PROVENANCE_MAP","SUPERSESSION_MAP"]}
        cognitive={**local,"currentness_requirements":["ASIS_GRAPH"],"evidence_requirements":["TARGET_MODEL","SURVIVOR_SET","DISPOSITION_LEDGER"]}
        self.assertEqual(curriculum.classify_contract(local),"LOCAL_DETERMINISTIC")
        self.assertEqual(curriculum.classify_contract(live),"LIVE_CONNECTOR")
        self.assertEqual(curriculum.classify_contract(cognitive),"COGNITIVE_SYNTHESIS")
        self.assertEqual(curriculum.contract_signature(live),curriculum.contract_signature(dict(live)))

    def test_p06_style_lineage_is_composed_from_prior_lessons(self):
        c=self.db()
        c.execute("INSERT INTO missions VALUES(?,?,?,?,?,?)",("M","RUNNING","DRIVER_RUNNING","a"*40,"b"*40,json.dumps({"task_id":"TASK-1"})))
        repo={"repository_census":{"default_heads":{"Org/repo":"a"*40}},"dependency_map":[],"local_evidence_producer":False}
        task={"ledger_summary":{"task_ledger":{"count":1,"task_ids":["TASK-1"],"digest":"1"*64},"mission_ledger":{"count":1,"digest":"2"*64}},"local_evidence_producer":True,"producer":"LOCAL"}
        cap={"capability_graph":{"entries":[{"capability_id":"CAP","executor_id":"EXEC","effect_ceiling":"NONE"}],"digest":"3"*64},
             "runtime_consumers":{"items":[{"capability_id":"CAP","consumers":[{"mission_id":"M","phase_id":"P","executor_id":"EXEC"}]}],"digest":"4"*64},
             "local_evidence_producer":True,"producer":"LOCAL"}
        self.source_phase(c,"A_REPO",1,["LIVE_GIT"],["REPOSITORY_CENSUS","DEPENDENCY_MAP"],repo)
        self.source_phase(c,"B_TASK",2,["CURRENT_MISSION_DB"],["TASK_LEDGER","MISSION_LEDGER"],task)
        self.source_phase(c,"C_CAP",3,["LIVE_RUNTIME"],["CAPABILITY_GRAPH","RUNTIME_CONSUMERS"],cap)
        target=self.contract(c,"TARGET",["LIVE_GIT","LIVE_GITHUB","CURRENT_MISSION_DB"],["LINEAGE_GRAPH","PROVENANCE_MAP","SUPERSESSION_MAP"],"TARGET_VERIFIED",6)
        contract=dict(c.execute("SELECT * FROM mission_phase_execution_contracts WHERE mission_id='M' AND phase_id='TARGET'").fetchone())
        learned=curriculum.learn_completed(c,"M",now)
        resolution=curriculum.resolve(c,"M","TARGET",contract,now)
        self.assertGreaterEqual(len(learned),3)
        self.assertEqual(resolution["recipe"],"COMPOSE_LINEAGE_V1")
        self.assertEqual(resolution["state"],"WAITING_CURRENTNESS")
        self.assertEqual(resolution["missing_currentness"],["LIVE_GIT","LIVE_GITHUB"])
        self.assertEqual(resolution["missing_evidence"],[])
        evidence=curriculum.compose_lineage(c,"M","TARGET",contract,resolution,{
          "passed_currentness":["LIVE_GIT","LIVE_GITHUB"],"evidence_refs":["test:git","test:github"],"authority_effect":"NONE"
        },now)
        self.assertEqual(evidence["checks"]["TARGET_VERIFIED"],"PASS")
        self.assertGreater(evidence["lineage_graph"]["node_count"],0)
        self.assertGreater(evidence["lineage_graph"]["edge_count"],0)
        self.assertEqual(evidence["supersession_map"]["inference_policy"],"EXPLICIT_ONLY")
        run=curriculum.latest_runs(c,"M")["TARGET"]
        self.assertEqual((run["state"],run["step"]),("PASS","COMPLETE"))
        self.assertRegex(run["result_digest"],r"^[0-9a-f]{64}$")
        self.assertEqual(run["authority_effect"],"NONE")
        self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0],"ok")


if __name__=="__main__":
    unittest.main()
