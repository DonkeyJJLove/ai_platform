import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

MODULE=Path(__file__).resolve().parents[2]/"tools"/"lion_reasoning_lineage_journal_r1.py"
spec=importlib.util.spec_from_file_location("lion_reasoning_lineage_journal_r1",MODULE)
journal=importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


def sample(name="test-one",classification="TEST_RESULT",status="PASS",
           claim="Source-bound non-mutating test completed"):
    return journal.event(
        case_id="LION-ARCHIVE-TEST-R1",event_id=name,
        classification=classification,status=status,statement=claim,
        evidence_refs=["a"*64],observed_at="2026-10-08T21:30:00+00:00",
        source_head="a"*40,
    )


class ReasoningJournalTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"journal"

    def test_append_source_and_independent_readback(self):
        x=journal.append_event(self.root,sample())
        self.assertEqual(x["result"],"PASS_RECORDED_AND_RECONCILED")
        self.assertEqual(x["events"],1)
        self.assertEqual(x["authority_effect"],"NONE")
        y=journal.read_journal(self.root,"LION-ARCHIVE-TEST-R1")
        self.assertEqual(y["head_digest"],x["head_digest"])
        self.assertEqual(y["status"],"VERIFIED")
        self.assertEqual(self.root.stat().st_mode&0o777,0o700)

    def test_two_records_form_causal_hash_chain(self):
        first=journal.append_event(self.root,sample())
        second=journal.append_event(self.root,sample(
            name="hypothesis-two",classification="HYPOTHESIS",status="UNKNOWN",
            claim="Producer did not prove end-to-end communication"))
        self.assertEqual(second["events"],2)
        self.assertNotEqual(first["head_digest"],second["head_digest"])
        path=journal._filename(self.root,"LION-ARCHIVE-TEST-R1")
        lines=[json.loads(v) for v in path.read_text().splitlines()]
        self.assertEqual(lines[1]["previous_digest"],lines[0]["event_digest"])
        self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_repeat_is_idempotent_not_duplicate(self):
        first=journal.append_event(self.root,sample())
        repeat=journal.append_event(self.root,sample())
        self.assertEqual(repeat["result"],"PASS_IDEMPOTENT_ALREADY_RECORDED")
        self.assertEqual(repeat["events"],1)
        self.assertEqual(repeat["head_digest"],first["head_digest"])

    def test_same_event_id_with_different_claim_denied(self):
        journal.append_event(self.root,sample())
        with self.assertRaisesRegex(journal.JournalError,"EVENT_ID_CONFLICT"):
            journal.append_event(self.root,sample(claim="Contradictory content"))

    def test_chain_tamper_detection(self):
        journal.append_event(self.root,sample())
        filename=journal._filename(self.root,"LION-ARCHIVE-TEST-R1")
        text=filename.read_text()
        filename.write_text(text.replace("completed","FAILED"),encoding="utf-8")
        with self.assertRaisesRegex(journal.JournalError,"EVENT_TAMPERED"):
            journal.read_journal(self.root,"LION-ARCHIVE-TEST-R1")

    def test_model_hypothesis_cannot_claim_observed_pass(self):
        with self.assertRaisesRegex(journal.JournalError,"PASS_ONLY_VALID_FOR_TEST_RESULT"):
            journal.append_event(self.root,sample(classification="HYPOTHESIS"))
        with self.assertRaisesRegex(journal.JournalError,"HYPOTHESIS_NOT_OBSERVATION"):
            journal.append_event(self.root,sample(classification="HYPOTHESIS",status="OBSERVED"))
        with self.assertRaisesRegex(journal.JournalError,"OBSERVATION_REQUIRES_SOURCE_DIGEST"):
            journal.append_event(self.root,journal.event(
                case_id="LION-ARCHIVE-TEST-R1",event_id="no-source",
                classification="RUNTIME_OBSERVATION",status="OBSERVED",
                statement="Unverified",evidence_refs=[],source_head="a"*40))

    def test_symlink_journal_prevents_write(self):
        self.root.mkdir()
        path=journal._filename(self.root,"LION-ARCHIVE-TEST-R1")
        external=Path(self.temp.name)/"external"
        external.write_text("ORIGINAL")
        path.symlink_to(external)
        with self.assertRaisesRegex(journal.JournalError,"JOURNAL_SYMLINK_DENIED"):
            journal.append_event(self.root,sample())
        self.assertEqual(external.read_text(),"ORIGINAL")

    def test_bad_case_id_and_oversized_claim(self):
        with self.assertRaisesRegex(journal.JournalError,"CASE_OR_EVENT_ID_INVALID"):
            journal.append_event(self.root,{**sample(),"case_id":"../outside"})
        with self.assertRaisesRegex(journal.JournalError,"CLAIM_BOUND_INVALID"):
            journal.append_event(self.root,sample(claim="X"*1300))


if __name__=="__main__":
    unittest.main()
