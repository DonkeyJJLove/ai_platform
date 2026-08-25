from __future__ import annotations

from dataclasses import asdict
import io
import json
import unittest
from unittest.mock import patch

from cyber_lion.contracts.builder_entry_permit import BUILDER_CAPABILITY_CLASS, TrustedBuilderSubject
from cyber_lion.contracts.build_authorization_consumption import BuildAuthorizationConsumptionPermit, SCHEMA_VERSION as CVER, compute_consumption_replay_digest
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
import cyber_lion.enterprise.builder_entry_permit as bep
from cyber_lion.enterprise.builder_entry_permit import (
    BuilderEntryPermitEngine,
    BuilderEntryPermitError,
    PinnedBuilderControlPlaneBackend,
    PinnedTrustedBuilderSubjectSource,
    TrustedBuilderSubjectSource,
    TrustedControlPlaneBuilderClient,
)
from cyber_lion.enterprise.candidate_build_authorization import LiveAdmittedResourceAuthority, LiveResourceAuthorityAdmission

D = lambda c: c * 64
S = lambda c: c * 40
REPO = "DonkeyJJLove/ai_platform"
MASTER = "f51bd8aa90a6040ca77f3b1f28b2f7c5a7499639"
TREE = "efde6fce25cf92fe0193faf3a4a24039f30a0c2b"
SCOPE = ("cyber_lion/example.py",)
RES = (f"repo-path:{REPO}:cyber_lion/example.py",)
NOW = "2026-08-25T01:30:00+00:00"


def live_receipt():
    return LiveAdmittedResourceAuthority(repository=REPO, mission_id="E004", grant_id="grant-R17", action="BUILD_CANDIDATE", resource_scope=RES, lineage_digest=D("3"), provenance_id="prov-R17", epoch=4, epoch_state_version=9, authority_ceiling="local_write", root_grant_id="root-R17", root_grant_digest=D("4"), authenticated_grant_digests=(D("1"), D("2")), leaf_key_id="key-R17", leaf_algorithm="ed25519", replay_digest=D("9"), admitted_at="2026-08-25T01:00:00+00:00")


def baseline(sha=MASTER, tree=TREE, observed="2026-08-25T01:20:00+00:00"):
    return TrustedRepositoryBaseline(REPO, sha, tree, observed)


def source_permit(live=None):
    live = live or live_receipt(); base = baseline()
    kwargs = dict(authorization_id="cba:" + D("a"), authorization_digest=D("b"), issuance_replay_digest=D("a"), repository=REPO, baseline_master_sha=MASTER, baseline_master_tree_sha=TREE, baseline_observation_digest=D("c"), current_baseline_digest=base.digest(), candidate_scope=SCOPE, resource_scope=RES, action="BUILD_CANDIDATE", grant_id="grant-R17", leaf_grant_digest=D("2"), authority_lineage_digest=D("3"), authority_provenance_id="prov-R17", authority_epoch=4, authority_state_version=9, root_grant_id="root-R17", root_grant_digest=D("4"), live_admission_digest=D("d"), current_authority_digest=live.digest(), authorization_valid_from="2026-08-25T00:00:00+00:00", authorization_expires_at="2026-08-26T00:00:00+00:00")
    replay = compute_consumption_replay_digest(**kwargs)
    return BuildAuthorizationConsumptionPermit(schema_version=CVER, consumption_permit_id="cbcp:" + replay, checked_at="2026-08-25T01:20:00+00:00", consumption_replay_digest=replay, **kwargs).sealed()


def builder_subject(instance="instance-01", identity="5"):
    return TrustedBuilderSubject(builder_subject_id="builder-R17", builder_instance_id=instance, capability_class=BUILDER_CAPABILITY_CLASS, repository=REPO, candidate_scope=SCOPE, resource_scope=RES, identity_digest=D(identity), implementation_digest=D("6"), attestation_digest=D("7"), valid_from="2026-08-25T00:00:00+00:00", expires_at="2026-08-26T00:00:00+00:00").sealed()


def builder_record(subject=None):
    subject = subject or builder_subject()
    return {"record_kind": "builder-subject", "lookup_key": {"repository": subject.repository, "builder_subject_id": subject.builder_subject_id, "builder_instance_id": subject.builder_instance_id, "candidate_scope_digest": bep._scope_digest(subject.candidate_scope, label="candidate_scope"), "resource_scope_digest": bep._scope_digest(subject.resource_scope, label="resource_scope"), "capability_class": subject.capability_class}, "subject": asdict(subject)}


class BaselineSource:
    def __init__(self, value): self.value = value
    def current(self, repository): return self.value


class F005:
    def __init__(self, state="QUARANTINED", effect="DENY"): self.value = {"state": state, "effect_authority": effect}
    def current(self): return self.value


class Replay:
    def __init__(self): self.seen = set(); self.calls = 0
    def consume(self, digest, *, consumed_at):
        self.calls += 1
        if digest in self.seen: return False
        self.seen.add(digest); return True


class ArbitraryResolver:
    def resolve_exact(self, **kwargs): return builder_subject()


class CallerDefinedSource(TrustedBuilderSubjectSource):
    def _lookup_exact(self, **kwargs): return (builder_subject(),)


class FakeHTTPResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self._io = io.BytesIO(self._raw)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit=-1): return self._io.read(limit)


class BuilderEntryPermitEngineTests(unittest.TestCase):
    def setUp(self):
        self.env = {"CYBER_LION_CP_PROVIDER_VERSION": "1.0.0", "CYBER_LION_CP_ENDPOINT": "https://control-plane.example", "CYBER_LION_CP_CREDENTIAL_ENV": "CYBER_LION_CP_TOKEN", "CYBER_LION_CP_TOKEN": "secret"}

    def _source(self):
        with patch.dict("os.environ", self.env, clear=True):
            return PinnedTrustedBuilderSubjectSource()

    def _engine(self, *, source=None, base=None, f005=None, replay=None):
        live = object.__new__(LiveResourceAuthorityAdmission)
        with patch.dict("os.environ", self.env, clear=True):
            return BuilderEntryPermitEngine(live_authority=live, baseline_source=BaselineSource(base or baseline()), f005_state_source=f005 or F005(), builder_source=source or self._source(), replay_guard=replay or Replay())

    def _issue(self, entry, *, records=None, provider_version="1.0.0", status=200, receipt=None, env=None):
        receipt = receipt or live_receipt()
        payload = {"provider_version": provider_version, "records": [builder_record()] if records is None else records}
        with patch.dict("os.environ", env or self.env, clear=True), patch.object(bep.urllib.request.OpenerDirector, "open", return_value=FakeHTTPResponse(payload, status=status)), patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=receipt):
            return entry.issue_permit(source_permit=source_permit(receipt), admitted_authority=receipt, builder_subject_id="builder-R17", builder_instance_id="instance-01", trusted_now=__import__("datetime").datetime.fromisoformat(NOW))

    def test_issues_non_effectful_exact_builder_bound_permit(self):
        permit = self._issue(self._engine())
        self.assertEqual((permit.builder_subject_id, permit.builder_instance_id), ("builder-R17", "instance-01"))
        self.assertEqual((permit.authority_effect, permit.execution_effect, permit.repository_ref_effect, permit.external_effect), ("NONE", "NONE", "NONE", "NONE"))
        permit.validate()

    def test_direct_store_and_runtime_factory_surface_absent(self):
        self.assertFalse(hasattr(bep, "SQLiteTrustedControlPlaneStore"))
        self.assertFalse(hasattr(bep, "_build_trusted_control_plane_store"))
        self.assertFalse(hasattr(bep, "_load_pinned_builder_records"))
        with self.assertRaises(TypeError): PinnedTrustedBuilderSubjectSource(records=(builder_subject(),))
        with self.assertRaises(TypeError): PinnedBuilderControlPlaneBackend(store=object())

    def test_client_configuration_is_process_only_and_exact(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(BuilderEntryPermitError): TrustedControlPlaneBuilderClient()
        bad = dict(self.env); bad["CYBER_LION_CP_PROVIDER_VERSION"] = "2.0.0"
        with patch.dict("os.environ", bad, clear=True):
            with self.assertRaises(BuilderEntryPermitError): TrustedControlPlaneBuilderClient()
        bad = dict(self.env); bad["CYBER_LION_CP_ENDPOINT"] = "https://user:pass@example/x?query=1"
        with patch.dict("os.environ", bad, clear=True):
            with self.assertRaises(BuilderEntryPermitError): TrustedControlPlaneBuilderClient()
        bad = dict(self.env); bad["CYBER_LION_CP_ENDPOINT"] = "http://control-plane.example"
        with patch.dict("os.environ", bad, clear=True):
            with self.assertRaises(BuilderEntryPermitError): TrustedControlPlaneBuilderClient()
        bad = dict(self.env); bad["CYBER_LION_CP_ENDPOINT"] = "file:///tmp/control-plane"
        with patch.dict("os.environ", bad, clear=True):
            with self.assertRaises(BuilderEntryPermitError): TrustedControlPlaneBuilderClient()

    def test_authoritative_configuration_fields_are_absent(self):
        with patch.dict("os.environ", self.env, clear=True):
            client = TrustedControlPlaneBuilderClient()
        for field in ("_endpoint", "_credential", "_credential_env", "_provider_version"):
            self.assertFalse(hasattr(client, field))
            with self.assertRaises((AttributeError, BuilderEntryPermitError)):
                setattr(client, field, "attacker")
        self.assertTrue(hasattr(client, "_configuration_digest"))
        self.assertFalse(hasattr(client, "_configuration_anchor"))

    def test_configuration_digest_and_sealed_flag_substitution_denied(self):
        with patch.dict("os.environ", self.env, clear=True):
            client = TrustedControlPlaneBuilderClient()
        object.__setattr__(client, "_configuration_digest", D("f"))
        with patch.dict("os.environ", self.env, clear=True):
            with self.assertRaises(BuilderEntryPermitError): client.verify_origin()
        with patch.dict("os.environ", self.env, clear=True):
            client = TrustedControlPlaneBuilderClient()
        object.__setattr__(client, "_sealed_configuration", False)
        with patch.dict("os.environ", self.env, clear=True):
            with self.assertRaises(BuilderEntryPermitError): client.verify_origin()

    def test_environment_drift_denied_without_refreshing_original_seal(self):
        with patch.dict("os.environ", self.env, clear=True):
            client = TrustedControlPlaneBuilderClient()
        original = client._configuration_digest
        mutations = (
            ("CYBER_LION_CP_ENDPOINT", "https://attacker.example"),
            ("CYBER_LION_CP_TOKEN", "attacker-secret"),
            ("CYBER_LION_CP_CREDENTIAL_ENV", "ALT_TOKEN"),
            ("CYBER_LION_CP_PROVIDER_VERSION", "2.0.0"),
        )
        for name, value in mutations:
            env = dict(self.env); env[name] = value
            if name == "CYBER_LION_CP_CREDENTIAL_ENV": env["ALT_TOKEN"] = "secret"
            with patch.dict("os.environ", env, clear=True):
                with self.assertRaises(BuilderEntryPermitError): client.verify_origin()
            self.assertEqual(client._configuration_digest, original)

    def test_coherent_endpoint_or_credential_reseal_is_denied(self):
        for name, value in (("CYBER_LION_CP_ENDPOINT", "https://attacker.example"), ("CYBER_LION_CP_TOKEN", "attacker-secret")):
            with patch.dict("os.environ", self.env, clear=True):
                client = TrustedControlPlaneBuilderClient()
            original = client._configuration_digest
            env = dict(self.env); env[name] = value
            with patch.dict("os.environ", env, clear=True):
                observed_digest = bep._observe_process_configuration()[-1]
                object.__setattr__(client, "_configuration_digest", observed_digest)
                with self.assertRaises(BuilderEntryPermitError): client.verify_origin()
                with self.assertRaises(BuilderEntryPermitError): bep._register_initial_client_configuration(client, observed_digest)
            object.__setattr__(client, "_configuration_digest", original)
            with patch.dict("os.environ", self.env, clear=True): client.verify_origin()

    def test_network_request_never_occurs_before_current_config_validation(self):
        source = self._source(); client = source.backend._client
        drift = dict(self.env); drift["CYBER_LION_CP_ENDPOINT"] = "https://attacker.example"
        called = []
        binding = {"repository": REPO, "builder_subject_id": "builder-R17", "builder_instance_id": "instance-01", "candidate_scope_digest": bep._scope_digest(SCOPE, label="candidate_scope"), "resource_scope_digest": bep._scope_digest(RES, label="resource_scope"), "capability_class": BUILDER_CAPABILITY_CLASS}
        with patch.dict("os.environ", drift, clear=True), patch.object(bep.urllib.request.OpenerDirector, "open", side_effect=lambda *a, **k: called.append(True)):
            with self.assertRaises(BuilderEntryPermitError): client.lookup_builder_subject_exact(binding=binding)
        self.assertEqual(called, [])

    def test_local_http_requires_explicit_loopback_mode(self):
        local = dict(self.env); local["CYBER_LION_CP_ENDPOINT"] = "http://127.0.0.1:8080"
        with patch.dict("os.environ", local, clear=True):
            with self.assertRaises(BuilderEntryPermitError): TrustedControlPlaneBuilderClient()
        local["CYBER_LION_CP_ALLOW_LOCAL_HTTP"] = "1"
        with patch.dict("os.environ", local, clear=True): TrustedControlPlaneBuilderClient().verify_origin()

    def test_redirect_handler_denies_redirects(self):
        handler = bep._NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(None, None, 302, "redirect", {}, "https://attacker.example"))

    def test_http_request_is_get_bearer_exact_and_query_bound(self):
        seen = []
        def fake(request, timeout):
            seen.append((request, timeout)); return FakeHTTPResponse({"provider_version": "1.0.0", "records": [builder_record()]})
        entry = self._engine()
        with patch.dict("os.environ", self.env, clear=True), patch.object(bep.urllib.request.OpenerDirector, "open", side_effect=fake), patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=live_receipt()):
            entry.issue_permit(source_permit=source_permit(), admitted_authority=live_receipt(), builder_subject_id="builder-R17", builder_instance_id="instance-01", trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
        request, timeout = seen[0]
        self.assertEqual(request.get_method(), "GET"); self.assertEqual(timeout, 5)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertIn("/v1/builder-subject?", request.full_url); self.assertNotIn("secret", request.full_url)

    def test_wire_scope_decoder_is_strict_and_reconstructs_tuple(self):
        wire = json.loads(json.dumps(builder_record()))
        subject = bep._subject_from_record(wire, expected_lookup=wire["lookup_key"])
        self.assertEqual(subject.candidate_scope, SCOPE)
        self.assertEqual(subject.resource_scope, RES)
        self.assertIs(type(subject.candidate_scope), tuple)
        self.assertIs(type(subject.resource_scope), tuple)
        mutations = (
            ("candidate_scope", "cyber_lion/example.py"),
            ("candidate_scope", tuple(SCOPE)),
            ("candidate_scope", []),
            ("candidate_scope", [SCOPE[0], SCOPE[0]]),
            ("candidate_scope", [1]),
            ("candidate_scope", ["../escape.py"]),
            ("candidate_scope", ["*.py"]),
            ("resource_scope", RES[0]),
            ("resource_scope", tuple(RES)),
            ("resource_scope", []),
            ("resource_scope", [RES[0], RES[0]]),
            ("resource_scope", [1]),
        )
        for field, value in mutations:
            bad = json.loads(json.dumps(builder_record()))
            bad["subject"][field] = value
            with self.assertRaises(BuilderEntryPermitError):
                bep._subject_from_record(bad, expected_lookup=bad["lookup_key"])

    def test_service_failures_do_not_burn_replay(self):
        for payload in (
            {"provider_version": "2.0.0", "records": [builder_record()]},
            {"provider_version": "1.0.0", "records": []},
            {"provider_version": "1.0.0", "records": [builder_record(), builder_record(builder_subject(identity="8"))]},
            {"provider_version": "1.0.0", "records": [{"bad": True}]}, b"not-json",
        ):
            replay = Replay(); entry = self._engine(replay=replay); response = FakeHTTPResponse(payload)
            with patch.dict("os.environ", self.env, clear=True), patch.object(bep.urllib.request.OpenerDirector, "open", return_value=response), patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=live_receipt()):
                with self.assertRaises(BuilderEntryPermitError): entry.issue_permit(source_permit=source_permit(), admitted_authority=live_receipt(), builder_subject_id="builder-R17", builder_instance_id="instance-01", trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
            self.assertEqual(replay.calls, 0)

    def test_subject_digest_and_binding_substitution_denied_before_replay(self):
        original = builder_subject()
        for field, value in (("identity_digest", D("8")), ("implementation_digest", D("8")), ("attestation_digest", D("8"))):
            raw = asdict(original); raw[field] = value
            record = builder_record(); record["subject"] = raw
            replay = Replay(); entry = self._engine(replay=replay)
            with self.assertRaises(BuilderEntryPermitError): self._issue(entry, records=[record])
            self.assertEqual(replay.calls, 0)

    def test_baseline_authority_and_f005_fail_before_service_and_replay(self):
        for entry in (self._engine(base=baseline(S("e"), TREE), replay=Replay()), self._engine(f005=F005("ACTIVE", "ALLOW"), replay=Replay())):
            with patch.dict("os.environ", self.env, clear=True), patch.object(bep.urllib.request.OpenerDirector, "open", side_effect=AssertionError("service should not be called")):
                with self.assertRaises(BuilderEntryPermitError): self._issue(entry)
        receipt = live_receipt(); drift = LiveAdmittedResourceAuthority(**{**receipt.__dict__, "epoch_state_version": 10})
        replay = Replay(); entry = self._engine(replay=replay)
        with patch.dict("os.environ", self.env, clear=True), patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=drift), patch.object(bep.urllib.request.OpenerDirector, "open", side_effect=AssertionError("service should not be called")):
            with self.assertRaises(BuilderEntryPermitError): entry.issue_permit(source_permit=source_permit(receipt), admitted_authority=receipt, builder_subject_id="builder-R17", builder_instance_id="instance-01", trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
        self.assertEqual(replay.calls, 0)

    def test_arbitrary_sources_and_subclasses_denied(self):
        live = object.__new__(LiveResourceAuthorityAdmission)
        for value in (ArbitraryResolver(), CallerDefinedSource()):
            with patch.dict("os.environ", self.env, clear=True):
                with self.assertRaises(BuilderEntryPermitError): BuilderEntryPermitEngine(live_authority=live, baseline_source=BaselineSource(baseline()), f005_state_source=F005(), builder_source=value, replay_guard=Replay())
        with self.assertRaises(TypeError):
            class BadClient(TrustedControlPlaneBuilderClient): pass
        with self.assertRaises(TypeError):
            class BadBackend(PinnedBuilderControlPlaneBackend): pass
        with self.assertRaises(TypeError):
            class BadSource(PinnedTrustedBuilderSubjectSource): pass

    def test_duplicate_entry_denied(self):
        replay = Replay(); entry = self._engine(replay=replay)
        self._issue(entry)
        with self.assertRaises(BuilderEntryPermitError): self._issue(entry)

    def test_no_effect_surface(self):
        BuilderEntryPermitEngine.assert_no_effect_surface()
        source = __import__("inspect").getsource(bep)
        for token in ("SQLiteTrustedControlPlaneStore", "put_builder_subject_record", "build_store as"):
            self.assertNotIn(token, source)
        for name in ("create" + "_branch", "create" + "_pr", "merge", "deploy", "release", "start" + "_builder", "build" + "_candidate"):
            self.assertFalse(hasattr(BuilderEntryPermitEngine, name))


if __name__ == "__main__":
    unittest.main()
