from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.authority_verification import AuthorityVerificationContext, IssuerKeyBinding
from cyber_lion.enterprise.cooperative_dependency_provider import (
    CONFIG_SCHEMA,
    PROVIDER_FACTORY_VERSION,
    CooperativeDependencyProviderError,
    build_dependencies_from_environment,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteCooperativeRuntimeEvidencePublisher,
)
from cyber_lion.mission_control.cooperative_worker_bootstrap import CooperativeRuntimeBootstrapDependencies


class CooperativeDependencyProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.external = self.base / "external"
        self.external.mkdir()
        self.contexts = self.external / "contexts"
        self.contexts.mkdir()
        self.state = self.base / "worker-state"
        self.state.mkdir()

        self.mission_db = self.external / "mission.sqlite"
        sqlite3.connect(self.mission_db).close()

        self.evidence_db = self.external / "evidence.sqlite"
        SQLiteCooperativeRuntimeEvidencePublisher(self.evidence_db)

        self.control_db = self.external / "control.sqlite"
        with sqlite3.connect(self.control_db) as db:
            db.execute(
                "CREATE TABLE authority_lineage("
                "repository TEXT,pr_number INTEGER,base_sha TEXT,head_sha TEXT,"
                "mission_id TEXT,grant_id TEXT,record_json TEXT)"
            )

        self.authority_db = self.external / "authority.sqlite"
        with sqlite3.connect(self.authority_db) as db:
            db.executescript(
                """
                CREATE TABLE authority_epoch_state(
                  trust_domain TEXT,tenant_id TEXT,organization_id TEXT,mission_id TEXT,
                  epoch INTEGER,revoked_json TEXT,version INTEGER);
                CREATE TABLE authority_root_anchor(
                  trust_domain TEXT,tenant_id TEXT,organization_id TEXT,mission_id TEXT,
                  epoch INTEGER,root_grant_id TEXT,root_grant_digest TEXT);
                """
            )

        self.verifier = self.external / "verifier.py"
        self.verifier.write_text(
            "def verify(payload, signature, key_id, algorithm):\n"
            "    return True\n"
            "def ready():\n"
            "    return True\n",
            encoding="utf-8",
        )

        durable = RuntimeAdmissionSourceTrustBinding(
            "cooperative-durable-admission",
            "cooperative-durable-admission:test",
            "1" * 64,
            "cooperative-worker",
            "2" * 64,
        ).validate()
        config = {
            "schema": CONFIG_SCHEMA,
            "factory_version": PROVIDER_FACTORY_VERSION,
            "authority_context": asdict(
                AuthorityVerificationContext("td", "tenant", "org", "M1").validate()
            ),
            "issuer_keys": [
                asdict(IssuerKeyBinding("root", "td", "key-1", "ed25519").validate())
            ],
            "upstream_admission_trust": asdict(rt.trust()),
            "durable_admission_trust": asdict(durable),
            "currentness_trust": asdict(rc.trust()),
        }
        self.config = self.external / "provider-config.json"
        self.config.write_text(json.dumps(config), encoding="utf-8")

    def env(self, **changes):
        value = {
            "LION_COOPERATIVE_PROVIDER_FACTORY_VERSION": PROVIDER_FACTORY_VERSION,
            "LION_COOPERATIVE_REPOSITORY_ROOT": str(self.repo),
            "LION_COOPERATIVE_MISSION_DB_PATH": str(self.mission_db),
            "LION_COOPERATIVE_PROVIDER_DB_PATH": str(self.evidence_db),
            "LION_COOPERATIVE_CONTEXT_CARRIER_ROOT": str(self.contexts),
            "LION_COOPERATIVE_CONTROL_PLANE_DB_PATH": str(self.control_db),
            "LION_COOPERATIVE_AUTHORITY_STATE_DB_PATH": str(self.authority_db),
            "LION_COOPERATIVE_LOCAL_AUTHORITY_STATE_PATH": str(self.state / "authority-local.sqlite"),
            "LION_COOPERATIVE_PROVIDER_CONFIG_PATH": str(self.config),
            "LION_COOPERATIVE_VERIFIER_MODULE_PATH": str(self.verifier),
            "LION_COOPERATIVE_VERIFIER_MODULE_SHA256": sha256(self.verifier.read_bytes()).hexdigest(),
            "LION_COOPERATIVE_VERIFIER_CALLABLE": "verify",
            "LION_COOPERATIVE_VERIFIER_READY_CALLABLE": "ready",
        }
        value.update(changes)
        return value

    def test_builds_exact_non_authorizing_dependency_set_from_external_sources(self):
        with patch.dict("os.environ", self.env(), clear=True):
            deps = build_dependencies_from_environment()
        self.assertIs(type(deps), CooperativeRuntimeBootstrapDependencies)
        self.assertEqual(deps.authority_effect, "NONE")
        self.assertEqual(
            (
                deps.upstream_admission_source.source_id,
                deps.upstream_admission_source.source_instance_id,
                deps.upstream_admission_source.implementation_digest,
                deps.upstream_admission_source.trust_anchor_id,
                deps.upstream_admission_source.trust_anchor_digest,
            ),
            rt.trust().binding(),
        )
        self.assertEqual(
            (
                deps.currentness_source.source_id,
                deps.currentness_source.source_instance_id,
                deps.currentness_source.implementation_digest,
                deps.currentness_source.trust_anchor_id,
                deps.currentness_source.trust_anchor_digest,
            ),
            rc.trust().binding(),
        )
        self.assertTrue((self.state / "authority-local.sqlite").is_file())

    def test_verifier_digest_substitution_fails_closed_before_dependencies_exist(self):
        with patch.dict(
            "os.environ",
            self.env(LION_COOPERATIVE_VERIFIER_MODULE_SHA256="0" * 64),
            clear=True,
        ):
            with self.assertRaisesRegex(CooperativeDependencyProviderError, "digest mismatch"):
                build_dependencies_from_environment()

    def test_config_inside_repository_is_denied(self):
        inside = self.repo / "provider-config.json"
        inside.write_bytes(self.config.read_bytes())
        with patch.dict(
            "os.environ",
            self.env(LION_COOPERATIVE_PROVIDER_CONFIG_PATH=str(inside)),
            clear=True,
        ):
            with self.assertRaisesRegex(CooperativeDependencyProviderError, "outside repository"):
                build_dependencies_from_environment()

    def test_runtime_evidence_database_inside_repository_is_denied(self):
        inside = self.repo / "evidence.sqlite"
        inside.write_bytes(self.evidence_db.read_bytes())
        with patch.dict(
            "os.environ",
            self.env(LION_COOPERATIVE_PROVIDER_DB_PATH=str(inside)),
            clear=True,
        ):
            with self.assertRaisesRegex(CooperativeDependencyProviderError, "outside repository"):
                build_dependencies_from_environment()

    def test_bad_factory_version_fails_closed(self):
        with patch.dict(
            "os.environ",
            self.env(LION_COOPERATIVE_PROVIDER_FACTORY_VERSION="9.9.9"),
            clear=True,
        ):
            with self.assertRaisesRegex(CooperativeDependencyProviderError, "version mismatch"):
                build_dependencies_from_environment()

    def test_external_shim_contains_only_canonical_factory_delegation(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "LION/runtime_compat/r24/docker-autonomy/cooperative-provider.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "from cyber_lion.enterprise.cooperative_dependency_provider import "
            "build_dependencies_from_environment",
            source,
        )
        self.assertIn("return build_dependencies_from_environment()", source)
        self.assertNotIn("RuntimeAdmission(", source)
        self.assertNotIn("LiveAdmittedAuthority(", source)


if __name__ == "__main__":
    unittest.main()
