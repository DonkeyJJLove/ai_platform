import json
import subprocess
from pathlib import Path
import unittest

from cyber_lion.architecture_projection.truth_plane import SubjectEntry, subject_digest
from cyber_lion.contracts.formalization_closure import (
    ArtifactResult,
    CandidateBinding,
    FormalizationClosureRecord,
    GateResult,
)
from cyber_lion.contracts.formalization_registry import domain_digest
from cyber_lion.tests.test_v15_federated_architecture_artifacts import registry, manifest

ROOT=Path(__file__).resolve().parents[2]
V15=ROOT/"LION/architecture/v1_5"


def load(name):
    return json.loads((V15/name).read_text(encoding="utf-8"))


def closure():
    value=load("FORMALIZATION_CLOSURE_RECORD_FEDERATION_R1.json")
    return FormalizationClosureRecord(
        closure_id=value["closure_id"],
        candidate=CandidateBinding(**value["candidate"]),
        formalization_manifest_digest=value["formalization_manifest_digest"],
        artifact_results=tuple(
            ArtifactResult(
                item["artifact_id"],item["classification"],item["state"],
                tuple(item["evidence_refs"]),
            )
            for item in value["artifact_results"]
        ),
        semantic_owner_uniqueness=value["semantic_owner_uniqueness"],
        catalog_coverage=value["catalog_coverage"],
        discoverability_result=value["discoverability_result"],
        rag_result=value["rag_result"],
        required_test_results=tuple(
            GateResult(item["id"],item["result"],tuple(item["evidence_refs"]))
            for item in value["required_test_results"]
        ),
        required_eval_results=tuple(
            GateResult(item["id"],item["result"],tuple(item["evidence_refs"]))
            for item in value["required_eval_results"]
        ),
        currentness_result=value["currentness_result"],
        unknowns=tuple(value["unknowns"]),
        decision=value["decision"],
        authority_effect=value["authority_effect"],
        closure_digest=value["closure_digest"],
        schema_id=value["schema_id"],
    )


def git_text(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()


class V15FederatedArchitectureClosureTests(unittest.TestCase):
    def test_closure_is_valid_against_current_registry_and_afm(self):
        reg=registry();afm=manifest(reg);c=closure()
        self.assertEqual(c.validate(afm,reg),c)
        self.assertEqual(c.decision,"PASS")
        self.assertEqual(c.currentness_result,"CURRENT_CANDIDATE")
        self.assertFalse(c.unknowns)
        self.assertEqual(len(c.artifact_results),36)
        self.assertEqual(len(c.required_test_results),9)
        self.assertEqual(len(c.required_eval_results),5)

    def test_candidate_identity_digest_and_git_tree_are_exact(self):
        identity=load("FORMALIZATION_CANDIDATE_IDENTITY_R1.json")
        c=closure()
        payload=dict(identity)
        observed=payload.pop("candidate_digest")
        self.assertEqual(
            observed,
            domain_digest(b"LION/FORMALIZATION-CANDIDATE-IDENTITY/1\0",payload),
        )
        self.assertEqual(c.candidate.candidate_digest,observed)
        self.assertEqual(c.candidate.head,identity["source_head"])
        self.assertEqual(c.candidate.tree,identity["source_tree"])
        self.assertEqual(git_text("rev-parse",c.candidate.head),c.candidate.head)
        self.assertEqual(git_text("rev-parse",c.candidate.head+"^{tree}"),c.candidate.tree)

    def test_verification_bundle_digest_binds_same_candidate(self):
        verification=load("FORMALIZATION_VERIFICATION_BUNDLE_R1.json")
        c=closure()
        payload=dict(verification)
        observed=payload.pop("verification_digest")
        self.assertEqual(
            observed,
            domain_digest(b"LION/FORMALIZATION-VERIFICATION-BUNDLE/1\0",payload),
        )
        self.assertEqual(c.candidate.verification_digest,observed)
        self.assertEqual(verification["candidate_digest"],c.candidate.candidate_digest)
        self.assertEqual(verification["source_head"],c.candidate.head)
        self.assertEqual(verification["source_tree"],c.candidate.tree)
        self.assertEqual(verification["tests"]["full_python_corpus"]["result"],"PASS")
        self.assertEqual(verification["security"]["new_authority_or_effect_surface"],"NONE")
        self.assertEqual(verification["rag"]["hosted_project_retrieval"],"NOT_RUN")

    def test_candidate_commit_was_truth_current_when_closed(self):
        c=closure()
        raw=subprocess.run(
            ["git","ls-tree","-r","-z",c.candidate.head],
            cwd=ROOT,check=True,capture_output=True,
        ).stdout
        entries=[]
        for record in raw.split(b"\0"):
            if not record:
                continue
            meta,path_raw=record.split(b"\t",1)
            mode,obj_type,obj_sha=meta.decode("ascii").split()
            entries.append(SubjectEntry(path_raw.decode("utf-8"),mode,obj_type,obj_sha))
        observed=subject_digest(entries)
        state=json.loads(git_text("show",c.candidate.head+":LION/architecture/canonical-state-v1-3-candidate.json"))
        registry_data=json.loads(git_text("show",c.candidate.head+":cyber_lion/registry/repositories.json"))
        identity=load("FORMALIZATION_CANDIDATE_IDENTITY_R1.json")
        self.assertEqual(observed,identity["truth_subject"])
        self.assertEqual(state["baseline"]["subject_digest"],observed)
        self.assertEqual(registry_data["generated_from"],"truth-subject-v1@"+observed)

    def test_effect_eval_and_rag_evidence_bind_candidate(self):
        c=closure()
        effect=load("EFFECT_SURFACE_SCAN_REBIND_R1.json")
        evaluations=load("FEDERATED_ARCHITECTURE_EVAL_RESULTS_R1.json")
        rag=load("RAG_V15_FEDERATED_ARCHITECTURE_SOURCE_SET.json")
        probes=load("RAG_V15_FEDERATED_ARCHITECTURE_PROBES.json")
        bootstrap=json.loads((ROOT/"LION/rag/RAG_BOOTSTRAP.json").read_text(encoding="utf-8"))
        self.assertEqual(effect["candidate"]["head"],c.candidate.head)
        self.assertEqual(effect["candidate"]["tree"],c.candidate.tree)
        self.assertEqual(effect["semantic_delta"]["added_effect_surfaces"],0)
        self.assertEqual(effect["semantic_delta"]["removed_effect_surfaces"],0)
        self.assertEqual(evaluations["candidate_binding"]["head"],c.candidate.head)
        self.assertEqual(evaluations["overall"],"PASS")
        self.assertEqual(rag["currentness"],"CURRENT_CANDIDATE")
        self.assertEqual(rag["candidate_binding"]["head"],c.candidate.head)
        self.assertEqual(probes["currentness"],"CURRENT_CANDIDATE")
        self.assertEqual(probes["candidate_binding"]["head"],c.candidate.head)
        self.assertEqual(
            bootstrap["v15_federated_architecture_currentness"],
            "CURRENT_CANDIDATE_SOURCE_CLOSED",
        )
        self.assertEqual(
            bootstrap["preferred_release"],
            "lion-rag32-v1.4-r9-auth-lifecycle-candidate",
        )


if __name__=="__main__":
    unittest.main()
