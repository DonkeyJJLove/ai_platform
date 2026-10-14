"""Current candidate effect-surface delta against pinned P0 history.

Historical P0 receipts remain bound to b6cc132 source.  This suite instead
checks the *current* source-tree inventory independently: precise surface
delta, taxonomy, explicit newly introduced local-write effects and lack of
inherited historical mediation/authorization evidence.
"""
from __future__ import annotations

import ast
from pathlib import Path
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
})


# The pre-write canonical epoch/context fence moves the *existing* bridge
# INSERT by eight lines. Scanner identity includes source line, even when
# the mutation AST itself is byte-for-byte unchanged. These exact digests
# are treated as a one-to-one relabeling, never as a new authority surface.
BRIDGE_WRITE_PATH = "cyber_lion/app_coordination/conversation_domain.py"
BRIDGE_WRITE_OLD_LINE = 553
BRIDGE_WRITE_NEW_LINE = 561
BRIDGE_WRITE_OLD_DIGEST = "51e1311c247ac2d7e4f6afdb602d6171d0ad4b40b46201f402fdf364c0ea0c5e"
BRIDGE_WRITE_NEW_DIGEST = "a7e21632dd62143c2770cb1dd446be1c632ecac52f247930c90b15e5c08c6422"
BRIDGE_WRITE_SQL = "INSERT INTO conversation_external_bridges VALUES(?,?,?,?,?,?,?,?)"


def _exact_existing_bridge_insert_ast(source: str, line: int) -> str:
    tree = ast.parse(source, filename=BRIDGE_WRITE_PATH)
    matches = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node, "lineno", None) == line
        and isinstance(node.func, ast.Attribute) and node.func.attr == "execute"
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "conn"
        and node.args and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == BRIDGE_WRITE_SQL
    ]
    if len(matches) != 1:
        raise AssertionError("exact historic/current bridge write AST identity not observed")
    return ast.dump(matches[0], include_attributes=False)


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

    def _verified_bridge_relocation(self):
        previous = self.historical_surfaces.get(BRIDGE_WRITE_OLD_DIGEST)
        current = self.candidate_surfaces.get(BRIDGE_WRITE_NEW_DIGEST)
        self.assertIsNotNone(previous, "pinned historical bridge INSERT absent")
        self.assertIsNotNone(current, "exact candidate bridge INSERT absent")
        self.assertEqual(previous.entrypoints, (
            f"{BRIDGE_WRITE_PATH}:{BRIDGE_WRITE_OLD_LINE}:conn.execute",
        ))
        self.assertEqual(current.entrypoints, (
            f"{BRIDGE_WRITE_PATH}:{BRIDGE_WRITE_NEW_LINE}:conn.execute",
        ))
        for attribute in (
            "effect_provider", "implementation_refs", "effect_class",
            "target_class", "mutation_kind", "authority_class",
            "currentness_requirement", "pep_required",
            "observer_required", "reconciliation_required",
            "epistemic_state",
        ):
            self.assertEqual(
                getattr(previous, attribute), getattr(current, attribute),
                f"bridge relocated effect changed {attribute}",
            )
        self.assertEqual(previous.effect_class, "persistent_state.write")
        self.assertEqual(previous.authority_class, "local_write")
        original_blob = subprocess.run(
            ["git", "show", f"{HISTORICAL_HEAD}:{BRIDGE_WRITE_PATH}"],
            cwd=self.root, check=True, stdout=subprocess.PIPE,
        ).stdout.decode("utf-8", "strict")
        candidate_blob = subprocess.run(
            ["git", "show", f"HEAD:{BRIDGE_WRITE_PATH}"],
            cwd=self.root, check=True, stdout=subprocess.PIPE,
        ).stdout.decode("utf-8", "strict")
        self.assertEqual(
            _exact_existing_bridge_insert_ast(original_blob, BRIDGE_WRITE_OLD_LINE),
            _exact_existing_bridge_insert_ast(candidate_blob, BRIDGE_WRITE_NEW_LINE),
            "the source-level SQL write must be AST identical after relocation",
        )
        return previous, current

    def test_existing_bridge_write_relocation_has_exact_ast_and_provenance(self):
        self._verified_bridge_relocation()

    def test_candidate_has_exactly_accounted_delta_and_resolved_taxonomy(self):
        previous = set(self.historical_surfaces)
        current = set(self.candidate_surfaces)
        self._verified_bridge_relocation()
        # Surface IDs hash the source location. Preserve the original
        # semantic 562/11/5 census with exactly one proven AST-identical
        # relocated bridge write (553 -> 561), rather than hiding a new
        # producer or weakening taxonomy/currentness checks.
        self.assertEqual(len(previous & current) + 1, 562)
        self.assertEqual(len((current - previous) - {BRIDGE_WRITE_NEW_DIGEST}), 11)
        self.assertEqual(len((previous - current) - {BRIDGE_WRITE_OLD_DIGEST}), 5)
        self.assertEqual(len(current), 573)
        self.assertFalse(self.candidate.unclassified_refs)
        self.assertFalse(self.candidate_taxonomy.unresolved_refs)
        self.assertNotEqual(
            self.candidate.scan_digest, self.historical.scan_digest,
            "CURRENT_CANDIDATE_MUST_NOT_INHERIT_HISTORICAL_P0_DIGEST",
        )

    def test_all_new_surface_classes_and_owners_are_explicit(self):
        self._verified_bridge_relocation()
        new = {
            digest: self.candidate_surfaces[digest]
            for digest in set(self.candidate_surfaces) - set(self.historical_surfaces)
            if digest != BRIDGE_WRITE_NEW_DIGEST
        }
        self.assertEqual(len(new), 11)
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
