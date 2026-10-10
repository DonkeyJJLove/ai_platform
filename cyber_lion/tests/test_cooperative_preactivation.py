from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.mission_control import cooperative_preactivation as pre
from cyber_lion.enterprise.cooperative_runtime_root import QUALIFICATION_DOMAIN
from cyber_lion.mission_control import cooperative_preactivation_bootstrap as boot
from cyber_lion.mission_control import global_scheduler
from cyber_lion.tests.test_cooperative_runtime_preparation_provider import (
    CooperativeRuntimePreparationProviderTests,
)


D=lambda s: sha256(s.encode("utf-8")).hexdigest()


class CooperativePreactivationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=CooperativeRuntimePreparationProviderTests(
            "test_exact_preparation_publishes_durable_admission_and_is_repeatable"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db=self.fixture.mission_db
        self.calls={"materialize":0,"qualify":0}

    def materializer(self,presented):
        self.calls["materialize"]+=1
        self.assertEqual(presented["assignment"]["state"],"HELD")
        self.assertEqual(presented["input"]["kind"],"COOPERATIVE_ARTIFACT_WRITE")
        return {
            "materialization_kind":"RUNTIME_CONTEXT",
            "provider_id":"COOPERATIVE_RUNTIME_WRITER_R5",
            "evidence_digest":D("r622-control-plane:"+presented["assignment"]["assignment_id"]),
            "authority_effect":"NONE",
        }

    def qualifier(self,assignment_id,worker_id):
        self.calls["qualify"]+=1
        with __import__("sqlite3").connect(self.db) as db:
            db.row_factory=__import__("sqlite3").Row
            row=dict(db.execute(
                "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                (assignment_id,),
            ).fetchone())
            release=global_scheduler.held_assignment_release_evidence(db,assignment_id)
        evidence={
            "schema":"lion.cooperative-worker-qualification/v1",
            "assignment_id":assignment_id,
            "mission_id":row["mission_id"],
            "worker_id":worker_id,
            "lease_generation":int(row["lease_generation"]),
            "release_evidence_digest":release["evidence_digest"],
            "control_plane_evidence_digest":release["evidence"]["evidence_digest"],
            "private_context_pin_sha256":D("pin:"+assignment_id),
            "private_transfer_sha256":D("transfer:"+assignment_id),
            "private_materialization_digest":D("materialization:"+assignment_id),
            "runtime_admission_digest":D("admission:"+assignment_id),
            "provider_id":"COOPERATIVE_RUNTIME_WRITER_R5",
            "context_resolver":"PINNED_COOPERATIVE_CONTEXT_RESOLVER",
            "execution_engine":"RUNTIME_EXECUTION_ENGINE",
            "writer_factory_built":True,
            "execution_performed":False,
            "authority_effect":"NONE",
        }
        return {
            **evidence,
            "qualification_digest":sha256(
                QUALIFICATION_DOMAIN
                + json.dumps(evidence,sort_keys=True,separators=(",",":"),
                             ensure_ascii=False,allow_nan=False).encode("utf-8")
            ).hexdigest(),
        }

    def provider(self,*,qualifier=None):
        return pre.CooperativePreactivationProvider(
            write_materializer=self.materializer,
            qualifier=qualifier or self.qualifier,
            worker_id="MD029",
        ).validate()

    def advance(self,provider=None):
        import sqlite3
        with sqlite3.connect(self.db) as db:
            db.row_factory=sqlite3.Row
            return pre.advance_preactivation(
                db,
                mission_id="M1",
                phase_id="PREACTIVATE",
                generation=1,
                provider=provider or self.provider(),
                now_fn=lambda:"2026-10-08T05:30:00Z",
            )

    def test_single_worker_preactivation_releases_qualifies_and_persists_evidence(self):
        result=self.advance()
        self.assertEqual(result["state"],"PASS")
        self.assertEqual(result["worker_id"],"MD029")
        self.assertEqual(self.calls,{"materialize":1,"qualify":1})
        import sqlite3
        with sqlite3.connect(self.db) as db:
            db.row_factory=sqlite3.Row
            assignment=db.execute(
                "SELECT * FROM mission_execution_assignments "
                "WHERE mission_id='M1' AND phase_id='PREACTIVATE__COOP_PREACTIVATE'"
            ).fetchone()
            self.assertEqual(assignment["state"],"READY")
            self.assertIsNotNone(global_scheduler.held_assignment_release_evidence(
                db,assignment["assignment_id"]
            ))
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM mission_execution_receipts WHERE assignment_id=?",
                    (assignment["assignment_id"],),
                ).fetchone()[0],
                0,
            )
            artifact=global_scheduler.artifact(
                db,"M1",pre.ARTIFACT_TYPE,phase_id="PREACTIVATE"
            )
            journal=global_scheduler.artifact(
                db,"M1",pre.JOURNAL_TYPE,phase_id="PREACTIVATE"
            )
        self.assertEqual(artifact["content"]["schema"],pre.QUALIFICATION_SCHEMA)
        self.assertFalse(artifact["content"]["execution_performed"])
        self.assertEqual(journal["content"]["state"],"QUALIFIED")
        self.assertEqual(journal["content"]["qualification_digest"],
                         artifact["content"]["qualification_digest"])

        again=self.advance()
        self.assertEqual(again["state"],"PASS")
        self.assertEqual(self.calls,{"materialize":1,"qualify":1})

    def test_canonical_r617_release_receipt_and_digest_are_consumed(self):
        self.assertEqual(QUALIFICATION_DOMAIN,pre._QUALIFICATION_DOMAIN)
        self.assertEqual(self.advance()["state"],"PASS")
        import sqlite3
        with sqlite3.connect(self.db) as db:
            db.row_factory=sqlite3.Row
            assignment=dict(db.execute(
                "SELECT * FROM mission_execution_assignments "
                "WHERE mission_id='M1' AND phase_id='PREACTIVATE__COOP_PREACTIVATE'"
            ).fetchone())
            release=global_scheduler.held_assignment_release_evidence(
                db,assignment["assignment_id"]
            )
        self.assertNotEqual(
            release["evidence_digest"],release["evidence"]["evidence_digest"]
        )
        canonical=self.qualifier(assignment["assignment_id"],"MD029")
        value=pre._validate_qualification(
            canonical,assignment=assignment,worker_id="MD029",release=release
        )
        self.assertEqual(value["release_evidence_digest"],release["evidence_digest"])
        self.assertEqual(
            value["control_plane_evidence_digest"],
            release["evidence"]["evidence_digest"],
        )
        wrapped={
            **canonical,"bootstrap_version":"1.0.0","bootstrap_mode":"UNBOUND",
        }
        self.assertEqual(
            pre._validate_qualification(
                wrapped,assignment=assignment,worker_id="MD029",release=release
            ),wrapped,
        )

    def test_qualification_digest_and_release_substitution_fail_closed(self):
        self.assertEqual(self.advance()["state"],"PASS")
        import sqlite3
        with sqlite3.connect(self.db) as db:
            db.row_factory=sqlite3.Row
            assignment=dict(db.execute(
                "SELECT * FROM mission_execution_assignments "
                "WHERE mission_id='M1' AND phase_id='PREACTIVATE__COOP_PREACTIVATE'"
            ).fetchone())
            release=global_scheduler.held_assignment_release_evidence(
                db,assignment["assignment_id"]
            )
        canonical=self.qualifier(assignment["assignment_id"],"MD029")
        forged=dict(canonical,qualification_digest=D("fake-qualification"))
        with self.assertRaisesRegex(
            pre.CooperativePreactivationError,"canonical digest mismatch"
        ):
            pre._validate_qualification(
                forged,assignment=assignment,worker_id="MD029",release=release
            )
        wrong_release=dict(canonical,release_evidence_digest=release["evidence"]["evidence_digest"])
        with self.assertRaisesRegex(
            pre.CooperativePreactivationError,"release evidence substitution"
        ):
            pre._validate_qualification(
                wrong_release,assignment=assignment,worker_id="MD029",release=release
            )
        wrong_control=dict(canonical,control_plane_evidence_digest=D("wrong-control"))
        with self.assertRaisesRegex(
            pre.CooperativePreactivationError,"control-plane evidence substitution"
        ):
            pre._validate_qualification(
                wrong_control,assignment=assignment,worker_id="MD029",release=release
            )

    def test_qualification_exception_is_journaled_unknown_and_not_retried(self):
        def fail(*_):
            self.calls["qualify"]+=1
            raise RuntimeError("lost qualification return")
        provider=self.provider(qualifier=fail)
        first=self.advance(provider)
        self.assertEqual(first["state"],"BLOCKED")
        self.assertEqual(first["gate"],"PREACTIVATION_QUALIFICATION_UNKNOWN")
        self.assertEqual(self.calls["qualify"],1)
        second=self.advance(provider)
        self.assertEqual(second["state"],"BLOCKED")
        self.assertEqual(second["gate"],"PREACTIVATION_QUALIFICATION_UNKNOWN")
        self.assertEqual(self.calls["qualify"],1)

    def test_provider_registry_is_exactly_once(self):
        registry=pre.CooperativePreactivationRegistry()
        provider=self.provider()
        self.assertIsNone(registry.current())
        registry.install(provider)
        self.assertIs(registry.current(),provider)
        self.assertEqual(registry.status()["state"],"READY")
        with self.assertRaisesRegex(pre.CooperativePreactivationError,"already installed"):
            registry.install(provider)

    def test_capability_is_noneffectful(self):
        row=pre.capability_registry_entries()[pre.CAPABILITY_CLASS][0]
        self.assertEqual(row["capability_id"],pre.CAPABILITY_ID)
        self.assertEqual(row["effect_ceiling"],"NONE")


class CooperativePreactivationR617ProducerContractTests(unittest.TestCase):
    def test_real_r617_producer_schema_and_digests_bind_to_r622_consumer(self):
        # Full canonical R6.16 -> R6.17 producer path with disposable SQLite and
        # fixture runtime owners. This is NOT live RuntimeAdmission on a host.
        from cyber_lion.tests.test_cooperative_worker_qualification import (
            CooperativeWorkerQualificationTests,
        )
        import sqlite3

        fixture=CooperativeWorkerQualificationTests(
            "test_released_projection_qualifies_one_worker_without_claim_or_effect"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        release_result=fixture.release()
        qualification=fixture.worker().qualify_released_write_assignment(
            fixture.aid,material_worker_id="MD001"
        )
        with sqlite3.connect(fixture.control.fixture.db) as db:
            db.row_factory=sqlite3.Row
            assignment=dict(db.execute(
                "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                (fixture.aid,),
            ).fetchone())
            release=global_scheduler.held_assignment_release_evidence(db,fixture.aid)

        self.assertEqual(assignment["state"],"READY")
        self.assertEqual(release_result["authority_effect"],"NONE")
        self.assertEqual(
            qualification["release_evidence_digest"],release["evidence_digest"]
        )
        self.assertEqual(
            pre._validate_qualification(
                qualification,assignment=assignment,
                worker_id="MD001",release=release,
            ),qualification,
        )
        self.assertEqual(fixture.assignment_receipt_count(),0)
        self.assertEqual(list(fixture.artifacts.iterdir()), [])


class CooperativePreactivationBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(lambda:__import__("shutil").rmtree(self.root,ignore_errors=True))
        self.repo=self.root/"repo";self.repo.mkdir()
        self.external=self.root/"external";self.external.mkdir()
        self.module=self.external/"provider.py"
        self.module.write_text("# pinned preactivation fixture\n",encoding="utf-8")
        self.digest=sha256(self.module.read_bytes()).hexdigest()
        self.provider=pre.CooperativePreactivationProvider(
            write_materializer=lambda _: {},
            qualifier=lambda _a,_w: {},
            worker_id="MD029",
        ).validate()

    def env(self,**changes):
        value={
            "LION_COOPERATIVE_PREACTIVATION_BOOTSTRAP_MODE":boot.TRUSTED_EXTERNAL_MODE,
            "LION_COOPERATIVE_PREACTIVATION_BOOTSTRAP_VERSION":boot.BOOTSTRAP_VERSION,
            "LION_COOPERATIVE_PREACTIVATION_REPOSITORY_ROOT":str(self.repo),
            "LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_PATH":str(self.module),
            "LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_SHA256":self.digest,
            "LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_FACTORY":"build_provider",
        }
        value.update(changes);return value

    def test_default_unbound_installs_nothing(self):
        registry=pre.CooperativePreactivationRegistry()
        result=boot.bootstrap_preactivation_provider({},registry=registry)
        self.assertEqual(result["state"],"UNBOUND")
        self.assertIsNone(registry.current())

    def test_trusted_pinned_provider_installs_once(self):
        registry=pre.CooperativePreactivationRegistry()
        module=SimpleNamespace(build_provider=lambda:self.provider)
        with patch.object(boot,"_load_module",return_value=module):
            result=boot.bootstrap_preactivation_provider(self.env(),registry=registry)
        self.assertEqual(result["state"],"READY")
        self.assertEqual(result["worker_id"],"MD029")
        self.assertIs(registry.current(),self.provider)

    def test_dependency_module_inside_repository_is_denied(self):
        inside=self.repo/"provider.py";inside.write_text("# x\n",encoding="utf-8")
        env=self.env(
            LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_PATH=str(inside),
            LION_COOPERATIVE_PREACTIVATION_DEPENDENCY_MODULE_SHA256=sha256(
                inside.read_bytes()
            ).hexdigest(),
        )
        with self.assertRaisesRegex(
            boot.CooperativePreactivationBootstrapError,"outside repository"
        ):
            boot.bootstrap_preactivation_provider(
                env,registry=pre.CooperativePreactivationRegistry()
            )


if __name__=="__main__":
    unittest.main()
