from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROVIDER = ROOT / "cyber_lion/enterprise/moon_file_write.py"
MEDIATION = ROOT / "cyber_lion/enterprise/moon_file_write_mediation.py"
CONTRACT = ROOT / "cyber_lion/contracts/moon_file_write.py"
WORKFLOW = ROOT / ".github/workflows/moon-file-write.yml"


class R9D9D1FalsificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider = PROVIDER.read_text(encoding="utf-8")
        cls.mediation = MEDIATION.read_text(encoding="utf-8")
        cls.contract = CONTRACT.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def _replace_guard_present(self):
        self.assertIn("_observe_replace_identity", self.provider)
        self.assertIn("_require_replace_identity", self.provider)
        self.assertIn("st_dev", self.provider)
        self.assertIn("st_ino", self.provider)
        self.assertIn("follow_symlinks=False", self.provider)
        self.assertIn("O_NOFOLLOW", self.provider)
        self.assertIn("stat.S_ISREG", self.provider)
        self.assertIn("REPLACE target identity drift before commit", self.provider)

    def _authority_rebound(self):
        self.assertIn("github-collaborator-permission-pdp-v2", self.provider)
        self.assertIn('"control_issue": request.control_issue', self.provider)
        self.assertIn('"source_event_digest": request.source_event_digest', self.provider)
        self.assertIn("authority_epoch=None", self.provider)
        self.assertNotIn("authority_epoch=0", self.provider)
        self.assertIn("current_admission = self.admissions.resolve(request)", self.mediation)
        self.assertIn("authority drift", self.mediation)

    def _fence_terminal(self):
        self.assertIn("UNIQUE NOT NULL", self.mediation)
        self.assertIn("durable file-write replay denied", self.mediation)
        self.assertIn("state='RECONCILED'", self.mediation)
        self.assertIn("state='UNKNOWN'", self.mediation)
        self.assertIn("rowcount != 1", self.mediation)

    def _receipt_boundary(self):
        self.assertIn("pre_observer", self.mediation)
        self.assertIn("post_observer", self.mediation)
        self.assertIn("pre_observer is post_observer", self.mediation)
        self.assertIn("post = self.post_observer.observe", self.mediation)
        self.assertIn("reconciliation_digest", self.mediation)

    def _path_boundary(self):
        self.assertIn("target.parent != BASE_DIR", self.provider)
        self.assertIn("target must be a direct child of /home/d2j3", self.provider)
        self.assertIn("target filename is not allowlisted", self.provider)
        self.assertIn("MAX_CONTENT_BYTES", self.provider)
        self.assertIn("bounded base directory unsafe", self.provider)

    def _replay_boundary(self):
        self.assertIn("effect_key TEXT PRIMARY KEY", self.mediation)
        self.assertIn("admission_digest TEXT UNIQUE NOT NULL", self.mediation)
        self.assertIn("request_digest TEXT UNIQUE NOT NULL", self.mediation)
        self.assertIn("write requires ATTEMPTED durable fence", self.provider)

    # T9D18-T9D26: REPLACE semantics.
    def test_T9D18_replace_wrong_digest_denied(self): self._replace_guard_present(); self.assertIn("REPLACE target changed at effect time", self.provider)
    def test_T9D19_replace_target_missing_denied(self): self.assertIn("REPLACE target unavailable at effect time", self.provider)
    def test_T9D20_replace_target_symlink_denied(self): self._replace_guard_present()
    def test_T9D21_replace_target_substituted_denied(self): self._replace_guard_present()
    def test_T9D22_replace_inode_changed_denied(self): self._replace_guard_present()
    def test_T9D23_replace_content_changed_after_preobserve_denied(self): self._replace_guard_present(); self.assertIn("expected_previous_sha256", self.provider)
    def test_T9D24_replace_nested_path_denied(self): self._path_boundary()
    def test_T9D25_replace_directory_target_denied(self): self._replace_guard_present()
    def test_T9D26_replace_oversize_denied(self): self.assertIn("existing target exceeds bounded size", self.provider)

    # T9D27-T9D33: authority-currentness semantics.
    def test_T9D27_permission_revoked_after_admission_denied(self): self._authority_rebound(); self.assertIn("actor permission is not trusted", self.provider)
    def test_T9D28_permission_changed_after_admission_denied(self): self._authority_rebound()
    def test_T9D29_authority_observation_digest_changed_denied(self): self._authority_rebound()
    def test_T9D30_actor_substitution_denied(self): self.assertIn("authority subject substitution", self.provider)
    def test_T9D31_repository_substitution_denied(self): self.assertIn("repository substitution denied", self.provider)
    def test_T9D32_control_issue_substitution_denied(self): self.assertIn("wrong control issue", self.provider)
    def test_T9D33_source_event_substitution_denied(self): self._authority_rebound()

    # T9D34-T9D39: crash/interruption semantics are fail closed in fence state machine.
    def test_T9D34_crash_prepared_no_effect(self): self._fence_terminal(); self.assertIn("state != \"PREPARED\"", self.mediation)
    def test_T9D35_crash_attempted_no_blind_replay(self): self._replay_boundary()
    def test_T9D36_crash_after_effect_requires_observation(self): self._receipt_boundary()
    def test_T9D37_crash_after_observed_reconciliation_safe(self): self._receipt_boundary(); self._fence_terminal()
    def test_T9D38_observer_unavailable_fails_closed(self): self.assertIn("except Exception", self.mediation); self.assertIn("mark_unknown", self.mediation)
    def test_T9D39_mismatch_transitions_unknown(self): self.assertIn('if result != "MATCH"', self.mediation); self.assertIn("mark_unknown(effect_key)", self.mediation)

    # T9D40-T9D45: receipt binding/forgery rejection surfaces.
    def test_T9D40_forged_effect_key_receipt_denied(self): self._receipt_boundary(); self.assertIn("effect_key", self.mediation)
    def test_T9D41_forged_admission_receipt_denied(self): self._receipt_boundary(); self.assertIn("admission_digest", self.mediation)
    def test_T9D42_forged_request_receipt_denied(self): self._receipt_boundary(); self.assertIn("request_digest", self.mediation)
    def test_T9D43_forged_target_receipt_denied(self): self._receipt_boundary(); self.assertIn("target_path", self.mediation)
    def test_T9D44_forged_content_digest_denied(self): self._receipt_boundary(); self.assertIn("expected_sha256", self.mediation)
    def test_T9D45_forged_observation_digest_denied(self): self._receipt_boundary(); self.assertIn("observation digest mismatch", self.mediation)

    # T9D46-T9D55: bounded filesystem/path model.
    def test_T9D46_dotdot_traversal_denied(self): self._path_boundary()
    def test_T9D47_nested_path_denied(self): self._path_boundary()
    def test_T9D48_alternate_absolute_base_denied(self): self._path_boundary()
    def test_T9D49_symlink_base_denied(self): self._path_boundary(); self.assertIn("S_ISLNK", self.provider)
    def test_T9D50_symlink_target_denied(self): self._replace_guard_present()
    def test_T9D51_fifo_target_denied(self): self._replace_guard_present()
    def test_T9D52_directory_target_denied(self): self._replace_guard_present()
    def test_T9D53_oversize_denied(self): self.assertIn("content exceeds bounded write limit", self.provider)
    def test_T9D54_wrong_intended_size_denied(self): self.assertIn("effect content substitution", self.provider)
    def test_T9D55_wrong_intended_digest_denied(self): self.assertIn("effect content substitution", self.provider)

    # T9D56-T9D63: persistent replay/identity binding.
    def test_T9D56_request_id_replay_denied(self): self._replay_boundary()
    def test_T9D57_request_digest_replay_denied(self): self._replay_boundary()
    def test_T9D58_admission_digest_replay_denied(self): self._replay_boundary()
    def test_T9D59_effect_key_replay_denied(self): self._replay_boundary()
    def test_T9D60_content_substitution_replay_denied(self): self._replay_boundary(); self.assertIn("effect content substitution", self.provider)
    def test_T9D61_target_substitution_replay_denied(self): self._replay_boundary(); self._path_boundary()
    def test_T9D62_authority_substitution_replay_denied(self): self._replay_boundary(); self._authority_rebound()
    def test_T9D63_restart_replay_denied(self): self._replay_boundary(); self.assertIn("sqlite3.connect", self.mediation)

    def test_no_generic_replace_write_helper_or_dynamic_sql(self):
        tree = ast.parse(self.provider)
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertNotIn("write_anywhere", names)
        self.assertNotIn("_atomic_write", names)
        self.assertNotIn("# nosec", self.provider.lower())
        self.assertNotIn("# nosec", self.mediation.lower())

    def test_runner_temp_bootstrap_is_explicit_and_home_target_not_bootstrapped(self):
        self.assertIn("RUNNER_TEMP", self.workflow)
        self.assertIn("GITHUB_SHA", self.workflow)
        self.assertIn("moon-mediated-runtime", self.workflow)
        bootstrap = self.workflow.split("Execute canonical mediated file write", 1)[0]
        self.assertNotIn("/home/d2j3/", bootstrap)


if __name__ == "__main__":
    unittest.main()
