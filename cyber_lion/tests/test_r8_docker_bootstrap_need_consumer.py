"""R8 consumer tests exercise the original executor on a synthetic runtime.

No real Docker engine, SaaS, operator grant, container, or production DB is touched.
The synthetic RuntimeAdmission is a fixture, not authorization for MOON.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.mission_control.docker_bootstrap_need_consumer import (
    AdmittedDockerBootstrapInputs,
    DockerBootstrapNeedConsumer,
    DockerBootstrapNeedError,
    NEED_SCHEMA, SCHEMA, verified_durable_need,
    _digest,
)
from cyber_lion.tests import test_r4_docker_fleet_bootstrap_executor as original_executor_tests


class CanonicalNeedConsumerTests(unittest.TestCase):
    def setUp(self):
        fixture=original_executor_tests.BoundedDockerBootstrapTests(
            "test_one_admission_starts_one_prepared_absent_fleet"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fx=fixture
        self.need={
            "schema":NEED_SCHEMA,
            "mission_id":fixture.mission["mission_id"],
            "source_head":fixture.mission["source_head"],
            "source_tree":fixture.mission["source_tree"],
            "lpcl_digest":fixture.mission["spec_digest"],
            "material_runtime":"DOCKER_LOCAL_MODEL",
            "logical_target":fixture.mission["logical_count"],
            "material_target":32,
            "runtime_resource":"docker://MOON/lion-r24-autonomy",
            "required_capability_class":"DOCKER_FLEET_BOOTSTRAP",
            "effect_class":"BOUNDED_MATERIAL",
            "required_admission":"CANONICAL_RUNTIME_ADMISSION_AND_EXPLICIT_LPCL",
            "gate":"DOCKER_FLEET_CURRENTNESS_REQUIRED",
            "authority_effect":"NONE",
            "runtime_effect":"NONE",
        }
        self.envelope={
            "event":"DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED",
            "need":self.need,
            "need_digest":_digest(self.need),
            "operator_activation_preserved":True,
            "authority_effect":"NONE",
        }
        self.message={
            "id":1,
            "protocol":"CONTROL",
            "from_id":"GLOBAL_MISSION_SCHEDULER_V1",
            "to_id":"MISSION_CONTROL",
            "direction":"INTERNAL","phase":None,
            "payload_digest":_digest(self.envelope),
            "payload":self.envelope,
        }
        self.snapshot={
            **fixture.mission,
            "runtime_state":"DOCKER_FLEET_WAITING_FOR_ADMISSION",
            "materialized":0,
            "ready":0,
            "workers":[],
            "execution_driver":{
                "driver_id":"driver-1",
                "state":"WAITING",
                "generation":1,
                "blocking_gate":"DOCKER_FLEET_CURRENTNESS_REQUIRED",
                "next_action":"WAIT_FOR_ADMITTED_DOCKER_FLEET",
                "lease_owner":None,
            },
            "protocol_messages":[self.message],
        }
        self.source={
            "head":fixture.mission["source_head"],
            "tree":fixture.mission["source_tree"],
        }
        self.admitted=AdmittedDockerBootstrapInputs(
            admission=fixture.admission,
            effect=fixture.effect,
            identity=fixture.identity,
            authority=fixture.live,
            execution_id="bounded-r8-test-consumption",
        )
        self.calls=0

    def build(self, *, admission=None):
        def resolve(*args):
            self.calls+=1
            return admission
        return DockerBootstrapNeedConsumer(
            snapshot_source=lambda mid: copy.deepcopy(self.snapshot),
            current_source=lambda: dict(self.source),
            admission_source=resolve,
            executor=self.fx.executor,
        )

    def test_verified_need_remains_non_authorizing(self):
        v=verified_durable_need(self.snapshot,self.source)
        self.assertEqual(v["schema"],SCHEMA)
        self.assertEqual(v["need_digest"],_digest(self.need))
        self.assertEqual(v["authority_effect"],"NONE")
        self.assertEqual(v["runtime_effect"],"NONE")
        self.assertEqual(self.fx.runtime.started,0)

    def test_without_admission_no_docker_effect(self):
        c=self.build()
        v=c.advance(self.fx.mission["mission_id"])
        self.assertEqual(v["state"],"WAITING_RUNTIME_ADMISSION")
        self.assertEqual(self.calls,1)
        self.assertEqual(self.fx.runtime.started,0)
        self.assertEqual(self.fx.guard_count(),0)

    def test_exact_admitted_mission_uses_original_one_shot_executor(self):
        c=self.build(admission=self.admitted)
        with patch.object(LiveAuthorityAdmission,"revalidate",return_value=self.fx.live):
            result=c.advance(self.fx.mission["mission_id"])
        self.assertEqual(result["state"],"OBSERVED_BY_ORIGINAL_EXECUTOR")
        self.assertEqual(self.fx.runtime.started,1)
        self.assertEqual(self.fx.guard_count(),1)
        self.assertEqual(len(self.fx.runtime.saved),1)
        self.assertEqual(result["original_result"]["result"],"OBSERVED")

    def test_foreign_source_fails_before_admission_lookup(self):
        self.source["head"]="f"*40
        c=self.build(admission=self.admitted)
        with self.assertRaisesRegex(DockerBootstrapNeedError,"INDEPENDENT_SOURCE_DRIFT"):
            c.advance(self.fx.mission["mission_id"])
        self.assertEqual(self.calls,0)
        self.assertEqual(self.fx.runtime.started,0)

    def test_changed_need_payload_or_digest_is_denied(self):
        self.envelope["need"]["source_tree"]="f"*40
        c=self.build(admission=self.admitted)
        with self.assertRaisesRegex(DockerBootstrapNeedError,"CANONICAL_MESSAGE_DIGEST_DRIFT"):
            c.advance(self.fx.mission["mission_id"])
        self.assertEqual(self.calls,0)
        self.assertEqual(self.fx.runtime.started,0)

    def test_duplicate_need_is_denied(self):
        self.snapshot["protocol_messages"].append(copy.deepcopy(self.message))
        with self.assertRaisesRegex(DockerBootstrapNeedError,"CANONICAL_NEED_MESSAGE_ORDER_INVALID"):
            verified_durable_need(self.snapshot,self.source)

    def test_newer_gate_supersedes_valid_historical_need(self):
        newer_need=dict(self.need,gate="DOCKER_FLEET_SOURCE_CURRENTNESS_DRIFT")
        newer_envelope={
            "event":"DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED",
            "need":newer_need,
            "need_digest":_digest(newer_need),
            "operator_activation_preserved":True,
            "authority_effect":"NONE",
        }
        newer_message={
            **self.message,
            "id":2,
            "payload":newer_envelope,
            "payload_digest":_digest(newer_envelope),
        }
        self.snapshot["protocol_messages"]=[newer_message,self.message]
        self.snapshot["execution_driver"]["blocking_gate"]="DOCKER_FLEET_SOURCE_CURRENTNESS_DRIFT"
        out=verified_durable_need(self.snapshot,self.source)
        self.assertEqual(out["need_digest"],_digest(newer_need))
        self.assertEqual(out["message_digest"],newer_message["payload_digest"])

    def test_historical_need_tampering_blocks_newer_gate(self):
        self.test_newer_gate_supersedes_valid_historical_need()
        self.message["payload"]["need"]["source_head"]="f"*40
        with self.assertRaisesRegex(DockerBootstrapNeedError,"HISTORICAL_NEED_JOURNAL_DRIFT"):
            verified_durable_need(self.snapshot,self.source)

    def test_driver_generation_change_pre_effect_blocks_original_executor(self):
        count=0
        def snapshot(_):
            nonlocal count
            count+=1
            value=copy.deepcopy(self.snapshot)
            if count>1:
                value["execution_driver"]["generation"]=2
            return value
        consumer=DockerBootstrapNeedConsumer(
            snapshot_source=snapshot,
            current_source=lambda:dict(self.source),
            admission_source=lambda *args:self.admitted,
            executor=self.fx.executor,
        )
        with self.assertRaisesRegex(DockerBootstrapNeedError,"DURABLE_RUNTIME_NEED_CHANGED_PRE_EFFECT"):
            consumer.advance(self.fx.mission["mission_id"])
        self.assertEqual(count,2)
        self.assertEqual(self.fx.runtime.started,0)
        self.assertEqual(self.fx.guard_count(),0)

    def test_unlaunched_and_foreign_driver_are_denied(self):
        self.snapshot["process"]["authority_state"]="NONE"
        with self.assertRaisesRegex(DockerBootstrapNeedError,"OPERATOR_ACTIVATION_REQUIRED"):
            verified_durable_need(self.snapshot,self.source)
        self.snapshot["process"]["authority_state"]="EXPLICIT_USER_ACTIVATION"
        self.snapshot["execution_driver"]["lease_owner"]="foreign"
        with self.assertRaisesRegex(DockerBootstrapNeedError,"DURABLE_RUNTIME_WAIT_DRIVER_REQUIRED"):
            verified_durable_need(self.snapshot,self.source)

    def test_historical_prepared_runtime_source_mismatch_blocks_admission(self):
        self.fx.runtime.identity["source_tree"]="f"*40
        c=self.build(admission=self.admitted)
        with self.assertRaisesRegex(DockerBootstrapNeedError,"PREPARED_RUNTIME_SOURCE_OR_RECEIPT_DRIFT"):
            c.advance(self.fx.mission["mission_id"])
        self.assertEqual(self.calls,0)
        self.assertEqual(self.fx.runtime.started,0)

    def test_invalid_runtime_receipt_returns_wait_not_authority(self):
        with patch.object(self.fx.runtime,"identity_and_receipt",
                          side_effect=__import__("cyber_lion.mission_control.docker_fleet_bootstrap_executor",
                                                 fromlist=["DockerFleetBootstrapError"]).DockerFleetBootstrapError("PREPARED_RUNTIME_SOURCE_RECEIPT_DRIFT")):
            result=self.build(admission=self.admitted).advance(self.fx.mission["mission_id"])
        self.assertEqual(result["state"],"WAITING_PREPARED_RUNTIME")
        self.assertEqual(self.calls,0)
        self.assertEqual(self.fx.runtime.started,0)

    def test_wrong_effect_scope_does_not_execute(self):
        effect=copy.copy(self.fx.effect)
        object.__setattr__(effect,"resource","docker://MOON/different")
        corrupt=AdmittedDockerBootstrapInputs(
            admission=self.fx.admission,effect=effect,
            identity=self.fx.identity,authority=self.fx.live,execution_id="denied"
        )
        with self.assertRaisesRegex(DockerBootstrapNeedError,"RUNTIME_ADMISSION_OR_EFFECT_SCOPE_DRIFT"):
            self.build(admission=corrupt).advance(self.fx.mission["mission_id"])
        self.assertEqual(self.fx.runtime.started,0)

    def test_unknown_effect_never_repeats_real_start(self):
        self.fx.runtime.fail_launch=True
        c=self.build(admission=self.admitted)
        with patch.object(LiveAuthorityAdmission,"revalidate",return_value=self.fx.live):
            first=c.advance(self.fx.mission["mission_id"])
            self.assertEqual(first["state"],"RECONCILE_EFFECT")
            self.assertEqual(first["original_result"]["result"],"EFFECT_UNKNOWN_RECONCILE")
            self.assertEqual(self.fx.runtime.started,1)
            # The canonical consumption guard prevents any second effect.
            with self.assertRaisesRegex(Exception,"DUPLICATE_DOCKER_BOOTSTRAP_ADMISSION"):
                c.advance(self.fx.mission["mission_id"])
        self.assertEqual(self.fx.runtime.started,1)
        self.assertEqual(self.fx.guard_count(),1)


if __name__ == "__main__":
    unittest.main()
