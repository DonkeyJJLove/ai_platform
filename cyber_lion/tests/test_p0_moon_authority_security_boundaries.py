from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.moon_file_write import _require_trusted_permission
from cyber_lion.enterprise.moon_file_write_mediation import MoonFileWriteMediationError, _require_current_admission
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from tools.p0_moon_security_boundary_evidence import _admission, materialize_security_boundary_evidence

REPO = "DonkeyJJLove/ai_platform"


def current():
    root = Path(__file__).resolve().parents[2]
    src = {}
    for p in subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines():
        if (p.startswith("cyber_lion/") and p.endswith(".py") and "/tests/" not in f"/{p}") or (p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))):
            src[p] = (root / p).read_text()
    rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    raw = EffectSurfaceScanner().scan(repository=REPO, revision=rev, tree_digest=tree, sources=src)
    inv, report, _ = EffectTaxonomyReconciler().reconcile(raw_inventory=raw, sources=src)
    return root, inv, report


class MoonAuthoritySecurityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.inv, cls.tax = current()
        cls.records, cls.satisfactions, cls.report, cls.policy, cls.closure, cls.carrier, cls.topology = materialize_security_boundary_evidence(inventory=cls.inv, taxonomy_report=cls.tax, repo_root=cls.root)

    def test_pure_permission_trusted_values_pass(self):
        for value in ("admin", "maintain", "write"):
            self.assertEqual(_require_trusted_permission(value), value)

    def test_pure_permission_untrusted_values_denied_without_network(self):
        with patch("cyber_lion.enterprise.moon_file_write.http.client.HTTPSConnection", side_effect=AssertionError("network forbidden")):
            for value in ("read", "triage", "none"):
                with self.assertRaisesRegex(MoonFileWriteMediationError, "^actor permission is not trusted$"):
                    _require_trusted_permission(value)

    def test_pre_fence_stale_authority_denied_without_sqlite_or_effect(self):
        a = _admission("3" * 64, "4" * 64)
        b = _admission("5" * 64, "6" * 64)
        with patch("cyber_lion.enterprise.moon_file_write_mediation.sqlite3.connect", side_effect=AssertionError("fence forbidden")):
            with self.assertRaisesRegex(MoonFileWriteMediationError, "^authority drift$"):
                _require_current_admission(a, b)

    def test_pre_fence_and_post_prepare_currentness_order_is_exact(self):
        text = (self.root / "cyber_lion/enterprise/moon_file_write_mediation.py").read_text()
        execute = text[text.index("    def execute(self, request: MoonFileWriteRequest)"):]
        i_pre = execute.index("pre_fence_admission = self.admissions.resolve(request)")
        i_pre_check = execute.index("_require_current_admission(admission, pre_fence_admission)")
        i_prepare = execute.index("self.fence.prepare(")
        i_post = execute.index("current_admission = self.admissions.resolve(request)")
        i_post_check = execute.index("_require_current_admission(admission, current_admission)")
        i_attempt = execute.index("self.fence.mark_attempted(")
        i_effect = execute.index("self.effect.write_exact(")
        self.assertLess(i_pre, i_pre_check); self.assertLess(i_pre_check, i_prepare)
        self.assertLess(i_prepare, i_post); self.assertLess(i_post, i_post_check)
        self.assertLess(i_post_check, i_attempt); self.assertLess(i_attempt, i_effect)
        self.assertIn("self.fence.mark_unknown(effect_key)", execute)

    def test_security_evidence_records_are_effect_free_and_actual(self):
        self.assertEqual({r.attack_id for r in self.records}, {"UNTRUSTED_PERMISSION", "STALE_AUTHORITY_SOURCE"})
        for record in self.records:
            self.assertTrue(record.record_digest)
            self.assertEqual(set(record.observed_denials), {record.expected_denial})
            self.assertEqual(set(record.observed_exception_types), {"MoonFileWriteMediationError"})
            self.assertFalse(any((record.network_effect, record.filesystem_effect, record.database_effect, record.authority_mutation, record.repository_mutation, record.target_mutation)))

    def test_security_requirements_are_satisfied_without_becoming_bypass_results(self):
        self.assertEqual({x.attack_id for x in self.satisfactions}, {"UNTRUSTED_PERMISSION", "STALE_AUTHORITY_SOURCE"})
        self.assertTrue(all(x.status == "CANONICAL_NEGATIVE_EVIDENCE_PRESENT" for x in self.satisfactions))
        self.assertEqual({x.attack_id for x in self.policy.security_requirements}, {"UNTRUSTED_PERMISSION", "STALE_AUTHORITY_SOURCE"})
        self.assertEqual({x.classification for x in self.policy.security_requirements}, {"POST_OBSERVATION_DECISION", "DOWNSTREAM_CURRENTNESS_GUARD"})
        self.assertEqual(len(self.closure), 7)
        self.assertTrue(all(x.status == "MEDIATED" for x in self.closure))
        self.assertEqual(self.report.remaining_security_requirement_keys, ())
        self.assertEqual(self.report.global_status, "UNKNOWN")
        self.assertEqual(self.carrier.global_status, "UNKNOWN")

    def test_no_live_workflow_or_effect_fixture_is_introduced(self):
        self.assertFalse((self.root / ".github/workflows/lion-moon-security-boundary-evidence.yml").exists())
        evidence_text = (self.root / "tools/p0_moon_security_boundary_evidence.py").read_text()
        self.assertNotIn("HTTPSConnection", evidence_text)
        self.assertNotIn("DurableMoonFileWriteFence(", evidence_text)
        self.assertNotIn("write_exact(", evidence_text)


if __name__ == "__main__":
    unittest.main()
