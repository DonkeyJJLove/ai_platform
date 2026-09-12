"""Synthetic offline records; no host telemetry, keys or runtime effects."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.app_coordination.offline_decoders import (
    MAX_INTEGER, decode_passive_timing, decode_source_payload)
from cyber_lion.app_coordination.producer_records import (
    application_observation, local_runtime_observation, qualification_result)
from cyber_lion.app_coordination.source_candidates import SourceRejected, canonical
from cyber_lion.enterprise.live_runtime_evidence_plane import (
    RuntimeAdmissionReplayAdapter, SQLiteSingleUseGuard)


class TelemetryDecoderTests(unittest.TestCase):
    def setUp(self):
        self.value = dict(
            schema="lion.e02.passive-timing/v1", event_id="synthetic:event-1",
            producer_id="synthetic:producer", runtime_id="synthetic:runtime",
            boot_id="synthetic:boot", clock_id="synthetic:clock", run_id="synthetic:run",
            sequence=0, source_revision="a"*64, policy_revision="b"*64,
            event_kind="OPERATION_DURATION", operation_class="LOCAL_COMPUTE",
            monotonic_start_ns=100, monotonic_end_ns=150, duration_ns=50,
            observed_at_utc="2026-09-11T10:00:00.123456789Z",
            clock_uncertainty_ns=None, dropped_count=0, provenance="CALLER_SUPPLIED",
            evidence_ref=None, authority_effect="NONE")

    def parse(self, **changes):
        return decode_passive_timing(canonical({**self.value, **changes}).encode())

    def test_duration_roundtrip_preserves_nanoseconds(self):
        parsed=self.parse()
        self.assertEqual(json.loads(parsed.canonical_json), self.value)
        self.assertEqual(parsed.provenance_status, "UNVERIFIED")
        self.assertFalse(parsed.runtime_ready)
        with self.assertRaises(FrozenInstanceError):
            parsed.canonical_json="changed"

    def test_gap_and_zero_duration(self):
        gap=self.parse(event_kind="OBSERVATION_GAP", monotonic_start_ns=None,
            monotonic_end_ns=None, duration_ns=None, dropped_count=2)
        self.assertEqual(json.loads(gap.canonical_json)["dropped_count"], 2)
        self.assertEqual(json.loads(self.parse(monotonic_end_ns=100, duration_ns=0).canonical_json)["duration_ns"],0)

    def test_external_provenance_never_promotes_trust(self):
        result=self.parse(provenance="VERIFIED_EXTERNAL_SOURCE", evidence_ref="receipt:synthetic")
        self.assertEqual(result.provenance_status,"UNVERIFIED")
        self.assertEqual(result.authority_effect,"NONE")
        self.assertFalse(result.runtime_ready)

    def test_integer_boundaries_bool_float_and_overflow(self):
        for name in ("sequence","dropped_count","clock_uncertainty_ns",
                     "monotonic_start_ns","monotonic_end_ns","duration_ns"):
            for bad in (True,False,-1,MAX_INTEGER+1,1.0,"1",[],{}):
                with self.subTest(name=name,bad=bad),self.assertRaises(SourceRejected):
                    self.parse(**{name:bad})
        self.parse(sequence=MAX_INTEGER,clock_uncertainty_ns=MAX_INTEGER,
                   monotonic_start_ns=MAX_INTEGER,monotonic_end_ns=MAX_INTEGER,duration_ns=0)

    def test_invalid_duration_and_gap_combinations(self):
        for changes in (
            dict(duration_ns=49),dict(monotonic_end_ns=99),dict(duration_ns=None),
            dict(event_kind="OBSERVATION_GAP"),dict(event_kind="OBSERVATION_GAP",
                monotonic_start_ns=None,monotonic_end_ns=None,duration_ns=None,dropped_count=0)):
            with self.subTest(changes=changes),self.assertRaises(SourceRejected):
                self.parse(**changes)

    def test_utc_calendar_and_syntax(self):
        for stamp in ("2026-02-29T00:00:00Z","2026-09-11T24:00:00Z",
                      "2026-09-11T10:00:60Z","2026-09-11T10:00:00+00:00",
                      "2026-9-11T10:00:00Z","2026-09-11T10:00:00.1234567890Z",
                      "2026-09-11T10:00:00Z\n",None,{},123):
            with self.subTest(stamp=stamp),self.assertRaises(SourceRejected):
                self.parse(observed_at_utc=stamp)
        self.parse(observed_at_utc="2024-02-29T00:00:00Z")

    def test_identifiers_and_evidence_are_not_urls_or_payloads(self):
        for field in ("event_id","producer_id","runtime_id","boot_id","clock_id","run_id","evidence_ref"):
            for value in ("","a"*129,"https://example.test","/tmp/file","x\n","é",{},False):
                with self.subTest(field=field,value=value),self.assertRaises(SourceRejected):
                    self.parse(**{field:value})

    def test_unknown_fields_domains_and_hashes(self):
        for changes in (dict(extra="payload"),dict(schema="other"),dict(authority_effect="ALLOW"),
                        dict(provenance="AUTHENTICATED"),dict(operation_class="SHELL"),
                        dict(event_kind="COMMAND"),dict(source_revision="A"*64),
                        dict(policy_revision="b"*63)):
            with self.subTest(changes=changes),self.assertRaises(SourceRejected):
                self.parse(**changes)
        value=dict(self.value);value.pop("sequence")
        with self.assertRaises(SourceRejected):decode_passive_timing(canonical(value).encode())

    def test_strict_json_and_byte_limit(self):
        raw=canonical(self.value).encode()
        for invalid in (raw[:-1]+b',"sequence":0}',raw.replace(b'"sequence":0',b'"sequence":NaN'),
                        b"\xff",b"[]",b" "*16385,raw.decode()):
            with self.subTest(invalid_type=type(invalid)),self.assertRaises(SourceRejected):
                decode_passive_timing(invalid)
        exact=raw+b" "*(16384-len(raw))
        decode_passive_timing(exact)
        with self.assertRaises(SourceRejected):decode_passive_timing(exact+b" ")

    def test_no_io_or_implicit_evidence_resolution(self):
        # Initialize strptime's standard-library cache before instrumenting IO.
        self.parse()
        with patch("builtins.open",side_effect=AssertionError("unexpected file IO")), \
             patch("socket.socket",side_effect=AssertionError("unexpected network")), \
             patch("subprocess.run",side_effect=AssertionError("unexpected process")):
            result=self.parse(provenance="VERIFIED_EXTERNAL_SOURCE",evidence_ref="synthetic:ref")
        self.assertEqual(result.provenance_status,"UNVERIFIED")


class SourcePayloadDecoderTests(unittest.TestCase):
    def setUp(self):
        self.app=application_observation(thread_id="t",turn_id="v",host_id="h",
            state="active",observed_at="2026-09-11T10:00:00Z")
        self.local=local_runtime_observation(host_id="h",boot_id="b",pid=10,
            started_at="2026-09-11T09:00:00Z",observed_at="2026-09-11T10:00:00Z",
            image_digest="1"*64,model_digest="2"*64,configuration_digest="3"*64)
        self.qualification=qualification_result(task_class="LOCAL",runtime_digest="1"*64,
            suite_digest="2"*64,policy_digest="3"*64,report_digest="4"*64,
            required_cases=("a","b"),measured_results={"a":"PASS","b":"UNKNOWN"})

    def test_existing_constructors_roundtrip(self):
        for observation in (self.app,self.local,self.qualification):
            self.assertEqual(observation,decode_source_payload(
                observation.kind,observation.payload_json.encode()))

    def test_unknown_session_and_task_binding_domains_refused(self):
        for kind in ("APP_SESSION_ATTESTATION","TASK_BINDING_RECORD","",None,[]):
            with self.subTest(kind=kind),self.assertRaises(SourceRejected):
                decode_source_payload(kind,self.app.payload_json.encode())

    def test_exact_fields_and_strict_json(self):
        raw=self.app.payload_json.encode()
        for invalid in (raw[:-1]+b',"state":"active"}', b'{"state":"active"}',
                        raw[:-1]+b',"authority":"ALLOW"}'):
            with self.assertRaises(SourceRejected):
                decode_source_payload(self.app.kind,invalid)

    def test_local_process_and_digest_invariants(self):
        value=json.loads(self.local.payload_json)
        for changes in (dict(pid=True),dict(pid=0),dict(model_digest="bad"),
                        dict(started_at="2026-09-12T00:00:00Z")):
            with self.assertRaises(SourceRejected):
                decode_source_payload(self.local.kind,canonical({**value,**changes}).encode())

    def test_qualification_cannot_upgrade_outcome_or_scope(self):
        value=json.loads(self.qualification.payload_json)
        for changes in (dict(outcome="PASS"),dict(scope="RUNTIME_QUALIFIED"),
                        dict(required_cases=[]),dict(required_cases=["a","a"]),
                        dict(required_cases=[{}]),dict(outcomes={"a":"PASS"}),
                        dict(outcomes={"a":True,"b":"UNKNOWN"})):
            with self.subTest(changes=changes),self.assertRaises(SourceRejected):
                decode_source_payload(self.qualification.kind,canonical({**value,**changes}).encode())

    def test_measurement_fail_and_unknown_stay_observations(self):
        value=json.loads(self.qualification.payload_json)
        for outcome in ("FAIL","UNKNOWN","PASS"):
            raw={**value,"outcomes":{"a":"PASS","b":outcome},"outcome":outcome}
            result=decode_source_payload(self.qualification.kind,canonical(raw).encode())
            self.assertEqual(result.provenance,"CALLER_SUPPLIED_OBSERVATION_NOT_ATTESTATION")


class ExistingReplayCompatibilityTests(unittest.TestCase):
    def test_existing_adapter_persists_single_use_without_engine_or_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"synthetic-replay.sqlite"
            adapter=RuntimeAdmissionReplayAdapter(SQLiteSingleUseGuard(path))
            self.assertTrue(adapter.consume("synthetic-request"))
            self.assertFalse(adapter.consume("synthetic-request"))
            reopened=RuntimeAdmissionReplayAdapter(SQLiteSingleUseGuard(path))
            self.assertFalse(reopened.consume("synthetic-request"))
            self.assertTrue(reopened.consume("different-synthetic-request"))


if __name__ == "__main__":
    unittest.main()
