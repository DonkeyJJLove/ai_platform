"""Offline fixtures only. No real session, authority issuer or live admission."""
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from cyber_lion.app_coordination.source_candidates import (
    CandidateSource, SourceRejected, SourceUnavailable, compare_index_receipt,
    load_configuration, canonical, LIMIT)
from cyber_lion.app_coordination.source_candidates import main
from cyber_lion.app_coordination.task_assignment import seal, digest
from cyber_lion.contracts.runtime_enforcement import RuntimeAdmission
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding


@dataclass(frozen=True)
class SyntheticBinding:
    task_digest: str
    assignment_digest: str
    qualification_digest: str
    action_digest: str
    context_digest: str
    provisioned_executor_digest: str
    completed_dependencies: tuple = ()

    def validate(self):
        for name, value in asdict(self).items():
            if name != "completed_dependencies":
                digest(value, name)
        return self


@dataclass(frozen=True)
class SyntheticBound:
    task_binding: SyntheticBinding
    source_revision: str
    runtime_admission: RuntimeAdmission


def decode_binding(payload):
    payload = dict(payload)
    payload["completed_dependencies"] = tuple(payload["completed_dependencies"])
    return SyntheticBinding(**payload).validate()


def decode_index(payload):
    return SyntheticBound(decode_binding(payload["task_binding"]),
                          payload["source_revision"],
                          RuntimeAdmission(**payload["runtime_admission"]).validate())


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime.now(timezone.utc)
        self.binding = SyntheticBinding("1"*64, "2"*64, "3"*64, "4"*64, "5"*64, "6"*64)
        fields = {
            "admission_id": "synthetic", "request_id": "synthetic-request",
            "gate_event_id": "synthetic-gate", "proposal_id": "synthetic-proposal",
            "policy_binding": "synthetic-policy", "effective_authority": "synthetic",
            "observability_state": "HEALTHY",
        }
        for name in ("gate_decision_digest", "pdp_receipt_digest", "pdp_evidence_digest",
                     "live_authority_digest", "authority_lineage_digest",
                     "requested_effect_digest", "runtime_identity_digest",
                     "provisioned_executor_digest", "replay_key"):
            fields[name] = "6"*64
        self.receipt = RuntimeAdmission(**fields).sealed()
        self.bound = SyntheticBound(self.binding, "9"*64, self.receipt)
        self.subject = {
            "mission_id": "APP_COORDINATION_R2", "task_id": "synthetic-task",
            "runtime_instance_id": "synthetic-runtime", "task_class": "DOCUMENT_SUMMARY",
            "checkpoint_revision": 1, "source_head": "a"*40,
            "session_record_digest": "7"*64, "qualification_digest": "3"*64,
            "task_digest": "1"*64, "provisioned_executor_digest": "6"*64}
        self.config = {
            "schema": "lion.e02.inactive-sources/v1", "enabled": False,
            "mode": "INACTIVE_CANDIDATE", "mission_id": "APP_COORDINATION_R2",
            "max_age_seconds": 300, "subject": self.subject, "sources": {}}
        self.snapshots = {}
        payloads = {"task_binding": asdict(self.binding), "request_index": asdict(self.bound),
                    "admission": asdict(self.receipt)}
        self.keys = {"task_binding": seal(self.binding), "request_index": "b"*64,
                     "admission": self.receipt.admission_digest}
        for kind in payloads:
            trust = RuntimeAdmissionSourceTrustBinding("synthetic-"+kind, "synthetic-instance",
                        "c"*64, "synthetic-anchor", "d"*64)
            self.config["sources"][kind] = {
                "locator": kind+".json", "snapshot_sha256": None, "trust": asdict(trust)}
            self.snapshots[kind] = {
                "schema": "lion.e02.source-snapshot/v1", "kind": kind,
                "source_binding": asdict(trust), "records": [{
                    "key": self.keys[kind], "subject": deepcopy(self.subject),
                    "issued_at": (self.now-timedelta(seconds=5)).isoformat(),
                    "expires_at": (self.now+timedelta(seconds=60)).isoformat(),
                    "payload": payloads[kind]}]}
        self.publish()

    def publish(self):
        for kind, value in self.snapshots.items():
            raw = canonical(value).encode()
            (self.root/(kind+".json")).write_bytes(raw)
            self.config["sources"][kind]["snapshot_sha256"] = sha256(raw).hexdigest()

    def load(self):
        return load_configuration(canonical(self.config).encode())

    def source(self, kind="admission", **kwargs):
        decoder = {"task_binding": decode_binding, "request_index": decode_index}.get(kind)
        return CandidateSource(self.load(), kind, self.root,
                               decode_payload=kwargs.get("decoder", decoder))

    def inspect(self, kind="admission"):
        return self.source(kind).inspect(self.keys[kind], self.now)

    def test_three_views_and_cross_source_readback_are_inert(self):
        for kind in self.keys:
            result = self.inspect(kind)
            self.assertFalse(result.dispatch_allowed)
            self.assertEqual(result.status, "CONSISTENT_UNAUTHENTICATED_CANDIDATE")
        self.assertEqual(compare_index_receipt(self.inspect("request_index"), self.inspect()),
                         "MATCH_UNAUTHENTICATED_NO_RETRY_OR_DISPATCH")

    def test_runtime_resolve_always_refuses_even_complete_fixture(self):
        for kind in self.keys:
            with self.assertRaises(SourceUnavailable):
                self.source(kind).resolve(self.keys[kind], self.now)

    def test_shipped_template_is_disabled_and_has_explicit_gaps(self):
        path=Path(__file__).parents[1]/"app_coordination/e02-sources.inactive.json"
        config=load_configuration(path.read_bytes())
        self.assertEqual(len(config.gaps()), 10)
        with self.assertRaises(SourceUnavailable):
            CandidateSource(config, "admission", self.root).inspect("a"*64,self.now)

    def test_live_or_synthetic_mode_cannot_load_as_production(self):
        for key,value in [("enabled",True),("enabled",0),("mode","LIVE"),("mode","SYNTHETIC")]:
            config=deepcopy(self.config);config[key]=value
            with self.assertRaises(SourceRejected):
                load_configuration(canonical(config).encode())

    def test_strict_json_rejects_duplicates_unknown_and_nonfinite(self):
        for raw in [b'{"enabled":false,"enabled":true}', b'{"x":NaN}', b'[]', b'\xff']:
            with self.assertRaises(SourceRejected): load_configuration(raw)
        self.config["extra"]=False
        with self.assertRaises(SourceRejected):self.load()

    def test_size_limit(self):
        with self.assertRaises(SourceRejected):load_configuration(b" "*(LIMIT+1))
        (self.root/"admission.json").write_bytes(b" "*(LIMIT+1))
        with self.assertRaises(SourceRejected):self.inspect()

    def test_missing_file_and_missing_record_are_unavailable(self):
        (self.root/"admission.json").unlink()
        with self.assertRaises(SourceUnavailable):self.inspect()
        self.snapshots["admission"]["records"]=[];self.publish()
        with self.assertRaises(SourceUnavailable):self.inspect()

    def test_snapshot_pin_detects_file_change(self):
        reader=self.source()
        (self.root/"admission.json").write_text("{}")
        with self.assertRaises(SourceRejected):
            reader.inspect(self.keys["admission"],self.now)

    def test_path_traversal_and_absolute_paths_rejected(self):
        for locator in ("../x.json","/x.json","C:/x.json","a\\x.json","a//x.json","./x.json"):
            with self.subTest(locator=locator):
                config=deepcopy(self.config);config["sources"]["admission"]["locator"]=locator
                with self.assertRaises(SourceRejected):
                    load_configuration(canonical(config).encode())

    def test_source_trust_substitution(self):
        self.snapshots["admission"]["source_binding"]["trust_anchor_id"]="other"
        self.publish()
        with self.assertRaises(SourceRejected):self.inspect()

    def test_index_and_receipt_source_identity_must_be_distinct(self):
        self.config["sources"]["request_index"]["trust"]=self.config["sources"]["admission"]["trust"]
        with self.assertRaises(SourceRejected):self.load()

    def test_every_subject_dimension_is_bound(self):
        for key, value in self.subject.items():
            with self.subTest(key=key):
                self.snapshots["admission"]["records"][0]["subject"]=deepcopy(self.subject)
                changed = value+1 if type(value) is int else ("f"*len(value) if key.endswith("digest") or key=="source_head" else value+"-other")
                self.snapshots["admission"]["records"][0]["subject"][key]=changed
                self.publish()
                with self.assertRaises(SourceRejected):self.inspect()

    def test_stale_future_naive_and_excessive_expiry(self):
        record=self.snapshots["admission"]["records"][0]
        values=[
          (self.now-timedelta(seconds=60),self.now),
          (self.now+timedelta(seconds=1),self.now+timedelta(seconds=60)),
          (self.now.replace(tzinfo=None),self.now+timedelta(seconds=60)),
          (self.now-timedelta(seconds=5),self.now+timedelta(seconds=301))]
        for issued,expires in values:
            record.update(issued_at=issued.isoformat(),expires_at=expires.isoformat());self.publish()
            with self.assertRaises(SourceRejected):self.inspect()

    def test_duplicate_keys_rejected_even_for_another_record(self):
        records=self.snapshots["admission"]["records"]
        records.extend([deepcopy(records[0]),deepcopy(records[0])]);self.publish()
        with self.assertRaises(SourceRejected):self.inspect()

    def test_canonical_receipt_tamper_detected_with_recomputed_file_pin(self):
        self.snapshots["admission"]["records"][0]["payload"]["effective_authority"]="changed"
        self.publish()
        with self.assertRaises(SourceRejected):self.inspect()

    def test_wrong_receipt_lookup_digest(self):
        self.keys["admission"]="e"*64
        self.snapshots["admission"]["records"][0]["key"]=self.keys["admission"];self.publish()
        with self.assertRaises(SourceRejected):self.inspect()

    def test_payload_decoder_is_required_and_cannot_return_pass_dict(self):
        for decoder in (None,lambda _:{"status":"PASS"}):
            with self.assertRaises(SourceRejected):
                self.source("task_binding",decoder=decoder).inspect(self.keys["task_binding"],self.now)

    def test_binding_payload_subject_mismatch(self):
        for kind in ("task_binding","request_index"):
            config=deepcopy(self.snapshots)
            record=self.snapshots[kind]["records"][0]["payload"]
            binding=record if kind=="task_binding" else record["task_binding"]
            binding["qualification_digest"]="f"*64
            self.publish()
            with self.assertRaises(SourceRejected):self.inspect(kind)
            self.snapshots=config

    def test_cross_source_receipt_mismatch(self):
        index=self.inspect("request_index");receipt=self.inspect()
        other=self.receipt
        other=replace(other,request_id="other",admission_digest="").sealed()
        receipt=replace(receipt,payload_json=canonical(asdict(other)))
        with self.assertRaises(SourceRejected):compare_index_receipt(index,receipt)

    def test_repeated_inspection_has_no_mutating_side_effect(self):
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(self.inspect(),self.inspect())
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})

    def test_cli_reports_valid_but_never_runtime_ready(self):
        path=Path(__file__).parents[1]/"app_coordination/e02-sources.inactive.json"
        output=StringIO()
        with redirect_stdout(output):
            code=main([str(path)])
        report=json.loads(output.getvalue())
        self.assertEqual(code,0)
        self.assertFalse(report["runtime_ready"])
        self.assertEqual(len(report["missing"]),10)


if __name__ == "__main__":
    unittest.main()
