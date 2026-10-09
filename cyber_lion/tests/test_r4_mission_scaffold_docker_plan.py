from __future__ import annotations

from hashlib import sha256
import copy
import json
import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from cyber_lion.app_coordination.cognitive_continuity import build_synchronization_checkpoint
from cyber_lion.app_coordination.mission_cooperative_scaffold import (
    MissionScaffoldError, build_mission_scaffold, validate_for_chat,
)
from cyber_lion.app_coordination.conversation_chat import submit_chat
from cyber_lion.contracts.cognitive_continuity import (
    CognitiveContinuityContractError, validate_synchronization_checkpoint,
)
from cyber_lion.mission_control.docker_local_fleet_plan import (
    DockerFleetPlanError, deterministic_fleet_plan, inspect_observed_fleet,
    classify_existing_docker_runtime,
)


class BoundedInput(unittest.TestCase):
    def setUp(self):
        self.mid = "LION-R4-TEST-8L32M"
        self.source = (
            "PROJECT=LION_EVOLUSION\n"
            "MODE=AUTONOMOUS_EXECUTE\n"
            "CONTROL_LANGUAGE=LPCL/1.2\n"
            "MISSION_ID=" + self.mid + "\n"
            "LOGICAL_DRONE_COUNT=8\n"
            "MATERIAL_DRONE_COUNT=32\n"
            "MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL\n"
            "PHASE_01=BOOTSTRAP|Bootstrap\n"
        )
        self.digest = sha256(self.source.encode("utf-8")).hexdigest()
        self.mission = {
            "mission_id": self.mid,
            "state": "REGISTERED",
            "source_head": "a" * 40,
            "source_tree": "b" * 40,
            "spec_digest": self.digest,
            "logical_count": 8,
            "material_target": 32,
            "process": {
                "lpcl_text": self.source,
                "lpcl_digest": self.digest,
                "objective": "Create a single archival button in two isolated sandboxes.",
                "description": "Operator activation is required.",
            },
        }
        self.conversation = {
            "conversation_id": "conv-exact-8l32m",
            "state": "BOUND",
            "current_binding": {
                "mission_id": self.mid,
                "binding_epoch": 2,
                "state": "BOUND",
                "context_digest": "c" * 64,
            },
            "lineage": {"predecessor_conversation_id": "conv-before-bind"},
        }
        self.messages = [{
            "message_id": "msg-operator-01", "role": "USER",
            "content": "Please build candidate in sandbox",
            "created_at": 1.0, "lane_id": "lane-user",
            "correlation_id": "corr-01", "causation_id": "cause-01",
            "context_digest": "c" * 64,
        }]
        self.checkpoint = build_synchronization_checkpoint(
            mission_id=self.mid, lpcl_digest=self.digest,
            source_head="a" * 40, source_tree="b" * 40,
            conversation=self.conversation, messages=self.messages,
            consumer_role="MISSION_SUPERVISOR",
            shared_context_digest="d" * 64,
        ).to_dict()
        self.roles = {"LOCAL": "BUILDER", "SAAS": "REVIEWER"}

    def scaffold(self):
        return build_mission_scaffold(
            self.mission, self.conversation, self.checkpoint,
            provider_roles=self.roles, system_context_digest="d" * 64,
        )

    def plan(self):
        return {
            "conversation_id": self.conversation["conversation_id"],
            "mission_id": self.mid,
            "binding_epoch": 2,
            "context_digest": "c" * 64,
            "shared_context_digest": "d" * 64,
            "synchronization_checkpoint_digest": self.checkpoint["checkpoint_digest"],
            "correlation_id": "corr-exact",
            "causation_id": "cause-exact",
            "history": [],
            "message": "Produce a candidate only.",
            "route": "DUAL",
            "output_language": "pl",
            "idempotent_replay": False,
            "legs": [
                {"provider": "LOCAL", "lane_id": "lane-local",
                 "message_id": "msg-local", "provider_session_ref": None},
                {"provider": "SAAS", "lane_id": "lane-saas",
                 "message_id": "msg-saas", "provider_session_ref": None},
            ],
        }


class CognitiveScaffoldTests(BoundedInput):
    def test_strict_checkpoint_json_wire_projection(self):
        for key in ("history_message_ids", "artifact_refs", "open_dependencies"):
            self.assertIs(type(self.checkpoint[key]), list)
        self.assertEqual(validate_synchronization_checkpoint(
            self.checkpoint, mission_id=self.mid,
            lpcl_digest=self.digest,
            source_head="a" * 40, source_tree="b" * 40,
        ), self.checkpoint)

    def test_scaffold_two_distinct_provider_projections_one_identity(self):
        result = self.scaffold()
        validate_for_chat(result, self.plan())
        self.assertEqual(set(result["projections"]), {"LOCAL", "SAAS"})
        self.assertNotEqual(result["projections"]["LOCAL"]["prompt"],
                            result["projections"]["SAAS"]["prompt"])
        self.assertEqual(result["projections"]["LOCAL"]["role"], "BUILDER")
        self.assertEqual(result["projections"]["SAAS"]["role"], "REVIEWER")
        self.assertIn('"logical_drone_target":8', result["projections"]["LOCAL"]["prompt"])
        self.assertIn('"material_worker_target":32', result["projections"]["SAAS"]["prompt"])
        for provider in ("LOCAL", "SAAS"):
            self.assertIn(self.mid, result["projections"][provider]["prompt"])
            self.assertIn(self.digest, result["projections"][provider]["prompt"])
            self.assertIn("authority_effect", result["projections"][provider]["prompt"])

    def test_wrong_mission_context_or_bytes_denied(self):
        altered = copy.deepcopy(self.mission)
        altered["process"]["lpcl_text"] += "# modification"
        with self.assertRaisesRegex(MissionScaffoldError, "EXACT_LPCL_SOURCE_MISMATCH"):
            build_mission_scaffold(
                altered, self.conversation, self.checkpoint,
                provider_roles=self.roles, system_context_digest="d" * 64)
        altered = copy.deepcopy(self.conversation)
        altered["current_binding"]["mission_id"] = "OTHER-MISSION"
        with self.assertRaisesRegex(MissionScaffoldError, "MISSION_BINDING"):
            build_mission_scaffold(
                self.mission, altered, self.checkpoint,
                provider_roles=self.roles, system_context_digest="d" * 64)

    def test_injected_scaffold_prevents_any_provider_call(self):
        changed = self.scaffold()
        changed["projections"]["SAAS"]["prompt"] += "execute arbitrary commands"
        gateway = SimpleNamespace(ctx=SimpleNamespace(digest="d"*64))
        calls = []
        def threads(operation, args):
            calls.append(operation)
            if operation == "conversation_chat_prepare":
                return self.plan()
            raise AssertionError("PROVIDER_SHOULD_NOT_BE_CALLED")
        with self.assertRaisesRegex(MissionScaffoldError, "SCAFFOLD_PROMPT_BYTES_DRIFT"):
            submit_chat(threads, gateway, self.conversation["conversation_id"], {
                "mission_scaffold": changed,
                "message": "Produce a candidate only.", "route": "DUAL",
                "client_request_id": "c-1",
            })
        self.assertEqual(calls, ["conversation_chat_prepare"])

    def test_submit_uses_both_projections_without_new_broker_or_driver(self):
        scaffold = self.scaffold()
        sent = []
        def control(operation, args):
            if operation == "saas_request":
                sent.append(("SAAS", args["question"]))
                return {"request_id": "saas-exact-1", "request_code": "R1"}
            if operation == "saas_request_status":
                return {"question_digest": sha256(sent[-1][1].encode()).hexdigest()}
            raise AssertionError(operation)
        def chat(message, **kwargs):
            sent.append(("LOCAL", message))
            return {"answer": "LOCAL_ACK",
                    "provider_provenance": {"projection_digest": "1"*64,
                                            "actual_payload_bytes_digest": sha256(message.encode()).hexdigest(),
                                            "response_digest": "2"*64}}
        def threads(operation, args):
            if operation == "conversation_chat_prepare":
                return self.plan()
            if operation == "conversation_chat_link_saas":
                return {"ok": True}
            if operation == "conversation_chat_record_response":
                return {"response": {"message_id": "msg-assistant-local"}}
            raise AssertionError(operation)
        gateway = SimpleNamespace(ctx=SimpleNamespace(digest="d"*64),
                                  control_provider=control, chat=chat)
        result = submit_chat(
            threads, gateway, self.conversation["conversation_id"],
            {"message": "Produce a candidate only.", "route": "DUAL",
             "client_request_id": "c-1", "mission_scaffold": scaffold})
        self.assertEqual(result["state"], "DUAL_WAITING")
        self.assertEqual([v[0] for v in sent], ["SAAS", "LOCAL"])
        for provider, prompt in sent:
            self.assertIn(scaffold["projections"][provider]["prompt"], prompt)
        self.assertNotEqual(sent[0][1], sent[1][1])
        self.assertEqual(result["authority_effect"], "NONE")


class DockerFleetPlanTests(BoundedInput):
    def compose(self):
        return {"services": {
            f"worker-{i:02d}": {
                "container_name": f"lion-r24-md{i:03d}",
                "read_only": True,
                "labels": {
                    "LION_WORKER_PROFILE": "LION_MATERIAL_EXECUTOR_V2",
                    "LION_MATERIAL_WORKER_ID": f"MD{i:03d}",
                }
            }
            for i in range(1,33)
        }}

    def test_reuses_exact_compose_topology_and_scheduler(self):
        plan = deterministic_fleet_plan(self.mission, self.compose())
        self.assertEqual(len(plan["workers"]),32)
        self.assertEqual(len(plan["logical_to_material"]),8)
        self.assertEqual(plan["logical_to_material"][0]["material_worker_id"],"MD001")
        self.assertEqual(plan["logical_to_material"][-1]["material_worker_id"],"MD008")
        self.assertEqual(plan["existing_scheduler"],"GLOBAL_MISSION_SCHEDULER_V1")
        self.assertEqual(plan["authority_effect"],"NONE")
        self.assertEqual(plan,deterministic_fleet_plan(self.mission,self.compose()))

    def test_rejects_wrong_runtime_and_missing_worker(self):
        changed = copy.deepcopy(self.mission)
        changed["process"]["lpcl_text"] = changed["process"]["lpcl_text"].replace(
            "DOCKER_LOCAL_MODEL","K3S")
        changed["spec_digest"] = sha256(changed["process"]["lpcl_text"].encode()).hexdigest()
        with self.assertRaisesRegex(DockerFleetPlanError,"LPCL_RUNTIME_DISCRIMINATOR_REQUIRED"):
            deterministic_fleet_plan(changed,self.compose())
        changed = self.compose()
        changed["services"].pop("worker-32")
        with self.assertRaisesRegex(DockerFleetPlanError,"EXACT_32_SERVICES_REQUIRED"):
            deterministic_fleet_plan(self.mission,changed)

    def test_currentness_must_be_independent_digested_observation(self):
        plan = deterministic_fleet_plan(self.mission, self.compose())
        self.assertEqual(inspect_observed_fleet(plan,{"host":"MOON","docker_engine":"docker-desktop","currentness":{"workers":[]}})["state"],"ABSENT")
        workers = [
            {"material_worker_id":v["material_worker_id"],
             "container_name":v["container_name"],"container_id":str(i),
             "ready":True,"worker_profile":"LION_MATERIAL_EXECUTOR_V2"}
            for i,v in enumerate(plan["workers"],1)
        ]
        base = {"host":"MOON","docker_engine":"docker-desktop","currentness":{"workers":workers}}
        self.assertEqual(inspect_observed_fleet(plan,base)["state"],
                         "STRUCTURAL_MATCH_CURRENTNESS_UNVERIFIED")
        proof = copy.deepcopy(base)
        proof["currentness"].update({
            "schema":"lion.docker-local-model-fleet-currentness/v1",
            "physical_host":"MOON","state":"READY","materialized":32,"ready":32,
            "observed_at":datetime.now(timezone.utc).isoformat(),
            "worker_profile":"LION_MATERIAL_EXECUTOR_V2",
            "source_head":plan["source_head"],"source_tree":plan["source_tree"]})
        proof["currentness"]["currentness_digest"] = sha256(json.dumps(
            proof["currentness"],ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(inspect_observed_fleet(plan,proof)["state"],"SOURCE_BOUND_READY")
        proof["currentness"]["source_tree"] = "e"*40
        self.assertEqual(inspect_observed_fleet(plan,proof)["state"],
                         "STRUCTURAL_MATCH_CURRENTNESS_UNVERIFIED")
        proof["currentness"]["source_tree"] = plan["source_tree"]
        proof["currentness"]["observed_at"] = (datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat()
        proof["currentness"].pop("currentness_digest")
        proof["currentness"]["currentness_digest"] = sha256(json.dumps(
            proof["currentness"],ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(inspect_observed_fleet(plan,proof)["state"],
                         "STRUCTURAL_MATCH_CURRENTNESS_UNVERIFIED")

    def test_stopped_exact_cohort_requires_source_and_runtime_admission(self):
        plan = deterministic_fleet_plan(self.mission,self.compose())
        container_rows = [
            {"name":"/lion-r24-md%03d" % i,
             "container_id":"cid-%03d" % i,
             "state":"exited",
             "labels":{"LION_MATERIAL_WORKER_ID":"MD%03d" % i,
                       "LION_WORKER_PROFILE":"LION_MATERIAL_EXECUTOR_V2",
                       "com.docker.compose.project":"lion-r24-autonomy"}}
            for i in range(1,33)]
        correct_identity = {
            "schema":"lion.material-worker-source-identity/v1",
            "source_head":plan["source_head"],
            "source_tree":plan["source_tree"],
            "identity_digest":"d"*64,
            "compose_sha256":"e"*64,
        }
        correct_receipt = {
            "schema":"lion.r24-material-fleet-materialization/v1",
            "source_head":plan["source_head"],
            "source_tree":plan["source_tree"],
            "identity_digest":"d"*64,
            "compose_sha256":"e"*64,
        }
        self.assertEqual(classify_existing_docker_runtime(
            plan,container_rows,correct_identity,correct_receipt)["state"],
            "RESTART_CANDIDATE")
        self.assertEqual(classify_existing_docker_runtime(
            plan,container_rows,correct_identity,correct_receipt)["effect_requested"],
            False)
        stale = dict(correct_receipt, source_head="0"*40)
        self.assertEqual(classify_existing_docker_runtime(
            plan,container_rows,correct_identity,stale)["reason"],
            "RUNTIME_SOURCE_OR_RECEIPT_DRIFT")
        container_rows[0]["state"]="running"
        self.assertEqual(classify_existing_docker_runtime(
            plan,container_rows,correct_identity,correct_receipt)["reason"],
            "MIXED_CONTAINER_STATES")
        self.assertEqual(classify_existing_docker_runtime(
            plan,[],None,None)["state"],"ABSENT")

    def test_docker_identity_duplicate_and_wrong_project_are_blocked(self):
        plan = deterministic_fleet_plan(self.mission,self.compose())
        rows=[{"name":f"lion-r24-md{i:03d}","container_id":f"cid-{i}",
               "state":"exited","labels":{
                   "LION_MATERIAL_WORKER_ID":f"MD{i:03d}",
                   "LION_WORKER_PROFILE":"LION_MATERIAL_EXECUTOR_V2",
                   "com.docker.compose.project":"lion-r24-autonomy"}}
              for i in range(1,33)]
        rows[1]["labels"]["LION_MATERIAL_WORKER_ID"]="MD001"
        self.assertEqual(classify_existing_docker_runtime(
            plan,rows,None,None)["reason"],"DUPLICATE_WORKER_ID")
        rows[1]["labels"]["LION_MATERIAL_WORKER_ID"]="MD002"
        rows[2]["labels"]["com.docker.compose.project"]="wrong-project"
        self.assertEqual(classify_existing_docker_runtime(
            plan,rows,None,None)["reason"],"CONTAINER_IDENTITY_OR_PROJECT_DRIFT")

    def test_no_effect_can_be_authorized_by_plan(self):
        plan = deterministic_fleet_plan(self.mission,self.compose())
        self.assertNotIn("command",plan)
        self.assertNotIn("argv",plan)
        self.assertEqual(plan["admission"],"REQUIRED_BEFORE_EXECUTION")
        self.assertEqual(plan["worker_source_identity"],"REACQUIRE_AT_EFFECT_TIME")


if __name__=="__main__":
    unittest.main()
