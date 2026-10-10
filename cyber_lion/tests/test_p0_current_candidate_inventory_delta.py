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
    "cyber_lion.mission_control.native_cognitive_phase_zero.py",
})
# Historical callsite IDs are location-derived, not authority. Pinned P0
# (b6cc132) remains frozen; R10 independently changes recon body and
# adds a first-class native model POST + three local journal writes.
# These eight AST signatures are the original P0 mutating SQL call bodies,
# verified against that exact Git object. R10 must preserve them verbatim.
RECON_RELOCATED_AST = {
    62: (63, "79a09adcb3a7676251f3a6672b71fa563f26367cf85ed2ed54ce63f3be97fe34"),
    218: (219, "b347d1bbefc6d277a986ee97b31dbdda9159ad5f42de539581f8ff7d4616eaaa"),
    225: (226, "31bd0cfb6251751dc7a19037633286880f1fc25332b5a8e53c2bbbf16c638a36"),
    933: (983, "563ed525dc29a619d475bb6d91c7f06fa99825e646229262d923f89ce6bb8c12"),
    938: (988, "8a1822d4c1fbcd3f015a4c577b90848a0873d5eb75c1642bb6f8bd507a071af2"),
    957: (1121, "e28f853044152c92c86a9546b3f120fee8604615707032a41125d0fddcaf8a72"),
    962: (1126, "dc6b9c223763469a69e433945275ccf0d6d31fcf0a437763d48e8db304a4db10"),
    1276: (1482, "f1539b969b3cfcf2596c978beb2da1efffd09c9690457731b7f9aab4a24cc3c4"),
}
R10_NEW_RECON_CALLSITE = (1078, "082a8074a7bb0d3262e400a6bf8f4a2dfcbe7c8584051e2c2d2c79f212a0c8c7")
RELOCATED_CALLSITE_OFFSETS = {
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
        # Historical P0 (567) is immutable. R10 has 23 relocations of
        # the *same* semantic callsites: 15 conversation-chat (+1 line)
        # and eight recon records at explicitly verified AST locations.
        # Of 34 newly minted location IDs, only 11 are new effects:
        # six cooperative writes, one native-recon journal write,
        # and four native-model ledger/HTTP effects.
        self.assertEqual(len(previous & current), 544)
        self.assertEqual(len(current - previous), 34)
        self.assertEqual(len(previous - current), 23)
        self.assertEqual(len(current), 578)
        self.assertEqual(len(current - previous) - len(previous - current), 11)
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
            {s.effect_class for s in new.values()},
            {"persistent_state.write", "external.network.post"},
        )
        self.assertEqual(
            {s.authority_class for s in new.values()},
            {"local_write", "external_write"},
        )
        self.assertEqual(
            {s.target_class for s in new.values()}, {"runtime", "external"}
        )
        from collections import Counter
        providers = Counter(s.effect_provider for s in new.values())
        self.assertEqual(providers, Counter({
            "cyber_lion.enterprise.cooperative_runtime_preparation_provider.py": 6,
            "cyber_lion.mission_control.control_plane_reconnaissance.py": 9,
            "cyber_lion.app_coordination.conversation_chat.py": 15,
            "cyber_lion.mission_control.native_cognitive_phase_zero.py": 4,
        }))
        native = [
            s for s in new.values()
            if s.effect_provider == "cyber_lion.mission_control.native_cognitive_phase_zero.py"
        ]
        self.assertEqual(Counter(s.effect_class for s in native), Counter({
            "persistent_state.write": 3,
            "external.network.post": 1,
        }))
        self.assertEqual(
            {(s.authority_class, s.target_class) for s in native
             if s.effect_class == "external.network.post"},
            {("external_write", "external")},
        )
        # Neither a new model HTTP POST nor its three durable writes
        # inherits an old P0 admission or historical closure.
        self.assertFalse(set(new) & set(self.historical_surfaces))

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

        # R10 inserted a genuine LOCAL-trajectory write, moving the eight
        # original recon writes by different offsets. Reclassify only those
        # eight after matching their exact AST expressions independently.
        recon = "cyber_lion.mission_control.control_plane_reconnaissance.py"
        recon_old = [s for s in removed if s.effect_provider == recon]
        recon_new = [s for s in added if s.effect_provider == recon]
        self.assertEqual((len(recon_old), len(recon_new)), (8, 9))

        def one_line(surface):
            self.assertEqual(len(surface.entrypoints), 1)
            path, location, call = surface.entrypoints[0].split(":")
            self.assertEqual(path,
                             "cyber_lion/mission_control/control_plane_reconnaissance.py")
            self.assertEqual(call, "conn.execute")
            return int(location)

        old_by_line = {one_line(surface): surface for surface in recon_old}
        new_by_line = {one_line(surface): surface for surface in recon_new}
        self.assertEqual(set(old_by_line), set(RECON_RELOCATED_AST))
        self.assertEqual(
            set(new_by_line),
            {location for location, _ in RECON_RELOCATED_AST.values()}
            | {R10_NEW_RECON_CALLSITE[0]},
        )
        path = self.root / "cyber_lion/mission_control/control_plane_reconnaissance.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        def call_digest_at(location):
            nodes = [
                node for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and node.lineno == location
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "conn"
                and node.func.attr == "execute"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value.lstrip().upper().startswith(
                    ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE",
                     "DROP", "ALTER", "PRAGMA")
                )
            ]
            self.assertEqual(len(nodes), 1)
            return sha256(ast.dump(
                nodes[0], include_attributes=False
            ).encode("utf-8")).hexdigest(), nodes[0]

        for previous_line, (present_line, historical_call_sha) in RECON_RELOCATED_AST.items():
            with self.subTest(historical_line=previous_line, current_line=present_line):
                self.assertEqual(
                    normalized(old_by_line[previous_line]),
                    normalized(new_by_line[present_line]),
                )
                observed_sha, _ = call_digest_at(present_line)
                self.assertEqual(observed_sha, historical_call_sha,
                                 "Relocated recon SQL differs from pinned historical AST")

        new_line, expected_sha = R10_NEW_RECON_CALLSITE
        new_sql_sha, new_node = call_digest_at(new_line)
        self.assertEqual(new_sql_sha, expected_sha)
        self.assertEqual(
            (new_by_line[new_line].effect_class,
             new_by_line[new_line].authority_class,
             new_by_line[new_line].target_class),
            ("persistent_state.write", "local_write", "runtime"),
        )
        self.assertEqual(
            ast.literal_eval(new_node.args[0]),
            "INSERT INTO mission_recon_trajectories VALUES(?,?,?,?,?,?,?,?,?,?,?)",
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
