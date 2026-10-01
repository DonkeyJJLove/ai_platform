import json
import subprocess
from pathlib import Path
import unittest

from cyber_lion.architecture_projection.truth_plane import SubjectEntry,subject_digest
from cyber_lion.contracts.formalization_closure import ArtifactResult,CandidateBinding,FormalizationClosureRecord,GateResult
from cyber_lion.contracts.formalization_registry import domain_digest
from cyber_lion.tests.test_v15_communication_envelope_formalization import manifest,registry

ROOT=Path(__file__).resolve().parents[2]
V15=ROOT/"LION/architecture/v1_5"

def load(name):
    return json.loads((V15/name).read_text(encoding="utf-8"))

def closure():
    v=load("FORMALIZATION_CLOSURE_RECORD_COMMUNICATION_ENVELOPE_R1.json")
    return FormalizationClosureRecord(
        closure_id=v["closure_id"],candidate=CandidateBinding(**v["candidate"]),
        formalization_manifest_digest=v["formalization_manifest_digest"],
        artifact_results=tuple(ArtifactResult(x["artifact_id"],x["classification"],x["state"],tuple(x["evidence_refs"])) for x in v["artifact_results"]),
        semantic_owner_uniqueness=v["semantic_owner_uniqueness"],catalog_coverage=v["catalog_coverage"],
        discoverability_result=v["discoverability_result"],rag_result=v["rag_result"],
        required_test_results=tuple(GateResult(x["id"],x["result"],tuple(x["evidence_refs"])) for x in v["required_test_results"]),
        required_eval_results=tuple(GateResult(x["id"],x["result"],tuple(x["evidence_refs"])) for x in v["required_eval_results"]),
        currentness_result=v["currentness_result"],unknowns=tuple(v["unknowns"]),decision=v["decision"],
        authority_effect=v["authority_effect"],closure_digest=v["closure_digest"],schema_id=v["schema_id"],
    )

def git_text(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()

class CommunicationEnvelopeClosureTests(unittest.TestCase):
    def test_fcr_validates_exact_36_17_4_pass_shape(self):
        c=closure(); a=manifest(); r=registry()
        self.assertEqual(c.validate(a,r),c)
        self.assertEqual(c.decision,"PASS")
        self.assertEqual(c.currentness_result,"CURRENT_CANDIDATE")
        self.assertFalse(c.unknowns)
        self.assertEqual((len(c.artifact_results),len(c.required_test_results),len(c.required_eval_results)),(36,17,4))

    def test_candidate_identity_digest_and_exact_git_object(self):
        ident=load("FORMALIZATION_CANDIDATE_IDENTITY_COMMUNICATION_ENVELOPE_R1.json")
        payload=dict(ident); observed=payload.pop("candidate_digest")
        self.assertEqual(observed,domain_digest(b"LION/FORMALIZATION-CANDIDATE-IDENTITY/1\0",payload))
        c=closure()
        self.assertEqual(c.candidate.candidate_digest,observed)
        self.assertEqual(c.candidate.head,ident["source_head"])
        self.assertEqual(c.candidate.tree,ident["source_tree"])
        self.assertEqual(git_text("rev-parse",c.candidate.head),c.candidate.head)
        self.assertEqual(git_text("rev-parse",c.candidate.head+"^{tree}"),c.candidate.tree)

    def test_candidate_truth_was_current_at_preclosure_head(self):
        ident=load("FORMALIZATION_CANDIDATE_IDENTITY_COMMUNICATION_ENVELOPE_R1.json")
        raw=subprocess.run(["git","ls-tree","-r","-z",ident["source_head"]],cwd=ROOT,check=True,capture_output=True).stdout
        entries=[]
        for rec in raw.split(b"\0"):
            if not rec: continue
            meta,path_raw=rec.split(b"\t",1)
            mode,obj_type,obj_sha=meta.decode("ascii").split()
            entries.append(SubjectEntry(path_raw.decode(),mode,obj_type,obj_sha))
        observed=subject_digest(entries)
        state=json.loads(git_text("show",ident["source_head"]+":LION/architecture/canonical-state-v1-3-candidate.json"))
        repos=json.loads(git_text("show",ident["source_head"]+":cyber_lion/registry/repositories.json"))
        self.assertEqual(observed,ident["truth_subject"])
        self.assertEqual(state["baseline"]["subject_digest"],observed)
        self.assertEqual(repos["generated_from"],"truth-subject-v1@"+observed)

    def test_verification_bundle_binds_candidate_and_zero_effect_delta(self):
        v=load("FORMALIZATION_VERIFICATION_BUNDLE_COMMUNICATION_ENVELOPE_R1.json")
        payload=dict(v); observed=payload.pop("verification_digest")
        self.assertEqual(observed,domain_digest(b"LION/FORMALIZATION-VERIFICATION-BUNDLE/1\0",payload))
        c=closure()
        self.assertEqual(c.candidate.verification_digest,observed)
        self.assertEqual(v["source_head"],c.candidate.head)
        self.assertEqual(v["source_tree"],c.candidate.tree)
        self.assertEqual(v["tests"]["full_python_corpus"],{"result":"PASS","tests":3523,"skipped":5})
        self.assertEqual(v["tests"]["r24_whole_integration_no_tests"]["result"],"PASS")
        sec=v["security"]["effect_surface_scan"]
        self.assertEqual((sec["source_count"],sec["surface_count"],sec["added"],sec["removed"],sec["taxonomy_unresolved"]),(370,519,0,0,0))
        self.assertEqual(v["security"]["new_authority_or_effect_surface"],"NONE")

    def test_eval_and_rag_sidecars_are_candidate_bound_without_release_promotion(self):
        e=load("COMMUNICATION_ENVELOPE_EVAL_RESULTS_R1.json")
        self.assertEqual(e["overall"],"PASS")
        self.assertEqual(len(e["results"]),4)
        self.assertTrue(all(x["result"]=="PASS" and not x["forbidden_action_observed"] for x in e["results"]))
        source=load("RAG_V15_COMMUNICATION_ENVELOPE_SOURCE_SET.json")
        probes=load("RAG_V15_COMMUNICATION_ENVELOPE_PROBES.json")
        boot=json.loads((ROOT/"LION/rag/RAG_BOOTSTRAP.json").read_text())
        c=closure()
        self.assertEqual(source["currentness"],"CURRENT_CANDIDATE")
        self.assertEqual(source["candidate_binding"]["head"],c.candidate.head)
        self.assertEqual(probes["candidate_binding"]["head"],c.candidate.head)
        self.assertEqual(probes["source_set_digest"],source["source_set_digest"])
        self.assertEqual(source["preferred_release_unchanged"],boot["preferred_release"])
        self.assertEqual(boot["v15_communication_envelope_currentness"],"CURRENT_CANDIDATE_SOURCE_CLOSED")
        self.assertEqual(source["live_truth_policy"],"RAG_NE_LIVE_TRUTH")

if __name__=="__main__":
    unittest.main()
