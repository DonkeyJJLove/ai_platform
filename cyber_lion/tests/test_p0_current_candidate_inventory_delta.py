"""Current candidate effect-surface delta against pinned P0 history.

Historical P0 receipts remain bound to b6cc132 source.  This suite instead
checks the *current* source-tree inventory independently: precise surface
delta, taxonomy, explicit newly introduced local-write effects and lack of
inherited historical mediation/authorization evidence.
"""
from __future__ import annotations

from pathlib import Path
import ast
from hashlib import sha256
import json
import subprocess
import unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler
from cyber_lion.tests.p0_historical_inventory import (
    HISTORICAL_HEAD, HISTORICAL_SCAN_DIGEST,
    pinned_p0_inventory,
)
from tools.p0_surface_closure_campaign import RECEIPT_IMPLIED_MOON_SURFACES

REPOSITORY = "DonkeyJJLove/ai_platform"
ADDED_PROVIDER_PATHS = frozenset({
    "cyber_lion.enterprise.cooperative_runtime_preparation_provider.py",
    "cyber_lion.mission_control.control_plane_reconnaissance.py",
    "cyber_lion.app_coordination.conversation_chat.py",
})
# Source-local location-based surface IDs are not a semantic owner or an
# admission. These offsets are grounded in the exact historical and R4 source
# scanner output, and each relocated call site must retain its effect class.
RELOCATED_CALLSITE_OFFSETS = {
    "cyber_lion.mission_control.control_plane_reconnaissance.py": (5, 22),
    "cyber_lion.app_coordination.conversation_chat.py": (15, 1),
}


def _production_path(path: str) -> bool:
    return (
        path.startswith("cyber_lion/")
        and path.endswith(".py")
        and "/tests/" not in "/" + path
    ) or (
        path.startswith(".github/workflows/")
        and path.endswith((".yml", ".yaml"))
    )


def live_candidate_inventory(root: Path):
    """Read exact tracked current source; no filesystem effect or authority."""
    paths = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True,
        stdout=subprocess.PIPE,
    ).stdout
    sources = {
        name: (root / name).read_text(encoding="utf-8", errors="strict")
        for raw in paths.split(b"\x00")
        if raw and _production_path(name := raw.decode("utf-8", "strict"))
    }
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        stdout=subprocess.PIPE, text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "write-tree"], cwd=root, check=True,
        stdout=subprocess.PIPE, text=True,
    ).stdout.strip()
    raw = EffectSurfaceScanner().scan(
        repository=REPOSITORY,
        revision=head,
        tree_digest=tree,
        sources=sources,
    )
    inventory, taxonomy, _ = EffectTaxonomyReconciler().reconcile(
        raw_inventory=raw, sources=sources,
    )
    return inventory, taxonomy


class P0CurrentCandidateInventoryDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.historical, cls.historical_taxonomy = pinned_p0_inventory(cls.root)
        cls.candidate, cls.candidate_taxonomy = live_candidate_inventory(cls.root)
        cls.historical_surfaces = {s.digest(): s for s in cls.historical.surfaces}
        cls.candidate_surfaces = {s.digest(): s for s in cls.candidate.surfaces}

    def test_frozen_historical_p0_source_identity_is_unchanged(self):
        self.assertEqual(self.historical.revision, HISTORICAL_HEAD)
        self.assertEqual(self.historical.scan_digest, HISTORICAL_SCAN_DIGEST)
        self.assertEqual(len(self.historical_surfaces), 567)
        self.assertFalse(self.historical.unclassified_refs)
        self.assertFalse(self.historical_taxonomy.unresolved_refs)

    def test_candidate_has_exactly_accounted_delta_and_resolved_taxonomy(self):
        previous = set(self.historical_surfaces)
        current = set(self.candidate_surfaces)
        # Historical 567 remains frozen. Current source adds exactly six
        # genuinely new cooperative runtime preparation write surfaces.
        # Fifteen conversation calls shifted +1 source line when R4 added its
        # mission-scaffold import, and five reconnaissance calls shifted +22
        # since the pinned historical P0 source. Neither shift adds an effect.
        self.assertEqual(len(previous & current), 547)
        self.assertEqual(len(current - previous), 26)
        self.assertEqual(len(previous - current), 20)
        self.assertEqual(len(current), 573)
        self.assertFalse(self.candidate.unclassified_refs)
        self.assertFalse(self.candidate_taxonomy.unresolved_refs)
        self.assertNotEqual(
            self.candidate.scan_digest, self.historical.scan_digest,
            "CURRENT_CANDIDATE_MUST_NOT_INHERIT_HISTORICAL_P0_DIGEST",
        )

    def test_all_new_surface_classes_and_owners_are_explicit(self):
        new = {
            digest: self.candidate_surfaces[digest]
            for digest in set(self.candidate_surfaces) - set(self.historical_surfaces)
        }
        self.assertEqual(
            {s.effect_provider for s in new.values()}, ADDED_PROVIDER_PATHS
        )
        self.assertEqual(
            {s.effect_class for s in new.values()}, {"persistent_state.write"}
        )
        self.assertEqual(
            {s.authority_class for s in new.values()}, {"local_write"}
        )
        self.assertEqual(
            {s.target_class for s in new.values()}, {"runtime"}
        )
        from collections import Counter
        providers = Counter(s.effect_provider for s in new.values())
        self.assertEqual(
            providers["cyber_lion.enterprise.cooperative_runtime_preparation_provider.py"],
            6,
        )
        self.assertEqual(
            providers["cyber_lion.mission_control.control_plane_reconnaissance.py"],
            5,
        )
        self.assertEqual(
            providers["cyber_lion.app_coordination.conversation_chat.py"],
            15,
        )

    def test_relocated_effects_keep_class_and_exact_callsite_identity(self):
        old = self.historical_surfaces
        current = self.candidate_surfaces
        removed = [old[k] for k in set(old) - set(current)]
        added = [current[k] for k in set(current) - set(old)]

        def normalized(entry):
            return (
                entry.effect_class, entry.authority_class, entry.target_class,
                tuple(sorted(
                    (call.split(":")[0], call.split(":")[-1])
                    for call in entry.entrypoints
                )),
            )

        def source_lines(items):
            return sorted(
                int(call.split(":")[1])
                for item in items for call in item.entrypoints
            )

        for provider, (count, offset) in RELOCATED_CALLSITE_OFFSETS.items():
            with self.subTest(provider=provider):
                old_records = [s for s in removed if s.effect_provider == provider]
                new_records = [s for s in added if s.effect_provider == provider]
                self.assertEqual((len(old_records), len(new_records)), (count, count))
                self.assertEqual(
                    sorted(map(normalized, old_records)),
                    sorted(map(normalized, new_records)),
                    "Location changes must not hide a new effect taxonomy",
                )
                self.assertEqual(
                    source_lines(new_records),
                    [line + offset for line in source_lines(old_records)],
                    "An unknown new callsite cannot inherit the old P0 inventory",
                )

    def test_r4_location_shift_did_not_change_sql_write_calls(self):
        # Independent AST freeze from exact predecessor
        # ai_platform@e0e979d5affca433743dc3eb2db8ed7cc7b40374:
        # 71 conn.execute expressions were observed in conversation_chat.py.
        # Rebinding LOCAL/SAAS scaffolds adds an import but no new SQL effect.
        path = self.root / "cyber_lion/app_coordination/conversation_chat.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = sorted(
            ast.dump(node, include_attributes=False)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "conn"
            and node.func.attr == "execute"
        )
        self.assertEqual(len(calls), 71)
        digest = sha256(json.dumps(
            calls, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        self.assertEqual(
            digest,
            "ef76fd6792d3ae27d58887c2aea0d324a788f1d50ed656c72689d10f63e51bd8",
            "A changed SQL effect must not be classified as a harmless line shift",
        )

    def test_historical_seven_still_exist_without_inheriting_current_closure(self):
        certified = set(RECEIPT_IMPLIED_MOON_SURFACES)
        new = set(self.candidate_surfaces) - set(self.historical_surfaces)
        self.assertEqual(len(certified), 7)
        self.assertTrue(certified.issubset(self.historical_surfaces))
        self.assertTrue(certified.issubset(self.candidate_surfaces))
        self.assertFalse(new & certified)
        # Presence does NOT assert new/current-mediated status or live authorization.
        self.assertNotEqual(self.candidate.scan_digest, HISTORICAL_SCAN_DIGEST)


if __name__ == "__main__":
    unittest.main()
