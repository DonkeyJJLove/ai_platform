"""Current candidate effect-surface delta against pinned P0 history.

Historical P0 receipts remain bound to b6cc132 source.  This suite instead
checks the *current* source-tree inventory independently: precise surface
delta, taxonomy, explicit newly introduced local-write effects and lack of
inherited historical mediation/authorization evidence.
"""
from __future__ import annotations

from pathlib import Path
import ast
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
    "cyber_lion.enterprise.r11_runtime_admission_replay.py",
    "cyber_lion.enterprise.r11_canonical_pdp_evidence.py",
    "cyber_lion.enterprise.cooperative_dependency_provider.py",
    "cyber_lion.enterprise.r11_original_r620_signed_publisher.py",
})
# Historical source P0 is reconstructed from its Git object and checked
# against the frozen tree/scan digest by pinned_p0_inventory. Compare old
# and new AST in the *same* current Python interpreter: ast.dump bytes vary
# between Python 3.12 and 3.13, although the SQL call is unchanged.
RECON_RELOCATED_LINES = {
    62: 63,
    218: 219,
    225: 226,
    933: 983,
    938: 988,
    957: 1121,
    962: 1126,
    1276: 1482,
}
R10_NEW_RECON_CALLSITE = 1078
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
        # Of 39 newly minted location IDs, 24 replace historical
        # callsites: the original 15 conversation/8 recon relocations,
        # plus the original worker-verifier source's connection-local
        # PRAGMA query_only=ON shifted exactly 147 -> 148 by the added
        # import. It is NOT a new database write or inherited admission.
        # Prior 15 plus one NEW create-only R620 signer-record publication.
        # Neither a signed row nor a Git digest is inherited P0 authority.
        self.assertEqual(len(previous & current), 543)
        self.assertEqual(len(current - previous), 40)
        self.assertEqual(len(previous - current), 24)
        self.assertEqual(len(current), 583)
        self.assertEqual(len(current - previous) - len(previous - current), 16)
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
            "cyber_lion.enterprise.r11_runtime_admission_replay.py": 2,
            "cyber_lion.enterprise.r11_canonical_pdp_evidence.py": 2,
            "cyber_lion.enterprise.cooperative_dependency_provider.py": 1,
            "cyber_lion.enterprise.r11_original_r620_signed_publisher.py": 1,
        }))
        signed_path="cyber_lion/enterprise/r11_original_r620_signed_publisher.py"
        publisher=[s for s in new.values() if s.effect_provider==
                   "cyber_lion.enterprise.r11_original_r620_signed_publisher.py"]
        self.assertEqual(len(publisher),1)
        self.assertEqual(
            (publisher[0].effect_class,publisher[0].authority_class,
             publisher[0].target_class,publisher[0].entrypoints),
            ("persistent_state.write","local_write","runtime",
             (signed_path+":287:db.execute",)),
        )
        src=(self.root/signed_path).read_text(encoding="utf-8")
        calls=[n for n in ast.walk(ast.parse(src))
               if isinstance(n,ast.Call) and n.lineno==287
               and isinstance(n.func,ast.Attribute)
               and isinstance(n.func.value,ast.Name)
               and n.func.value.id=="db" and n.func.attr=="execute"
               and n.args]
        self.assertEqual(len(calls),1)
        self.assertTrue(ast.literal_eval(calls[0].args[0]).startswith(
            "INSERT INTO r11_original_r620_signed_parts "
        ))
        self.assertIn("BEGIN IMMEDIATE",src)
        self.assertNotIn("INSERT OR REPLACE",src)
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
        # R11's new replay DB genuinely writes to private persistent
        # state; the P0 inventory must retain exact owner, type, site and
        # AST statement identity instead of silently accepting +2 writes.
        replay_provider = "cyber_lion.enterprise.r11_runtime_admission_replay.py"
        replay = [s for s in new.values() if s.effect_provider == replay_provider]
        self.assertEqual(len(replay), 2)
        self.assertEqual({s.effect_class for s in replay}, {"persistent_state.write"})
        self.assertEqual({s.authority_class for s in replay}, {"local_write"})
        self.assertEqual({s.target_class for s in replay}, {"runtime"})
        path = "cyber_lion/enterprise/r11_runtime_admission_replay.py"
        self.assertEqual(
            {s.entrypoints for s in replay},
            {
                (path + ":91:db.execute",),
                (path + ":122:db.execute",),
            },
        )
        source = (self.root / path).read_text(encoding="utf-8")
        calls = [
            node for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and node.lineno in {91, 122}
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "db"
            and node.func.attr == "execute"
            and node.args
        ]
        self.assertEqual(
            sorted((node.lineno, ast.literal_eval(node.args[0]).split()[0])
                   for node in calls),
            [(91, "CREATE"), (122, "INSERT")],
        )
        self.assertIn("BEGIN IMMEDIATE", source)
        self.assertIn("mode=rw", source)
        # The separate original PDP evidence read/write bridge has exactly
        # two scanner-visible sites; this MUST NOT inherit a P0 admission.
        pdp_owner = "cyber_lion.enterprise.r11_canonical_pdp_evidence.py"
        pdp = [s for s in new.values() if s.effect_provider == pdp_owner]
        self.assertEqual(len(pdp),2)
        self.assertEqual({s.effect_class for s in pdp},{"persistent_state.write"})
        self.assertEqual(
            {s.entrypoints for s in pdp},
            {
                ("cyber_lion/enterprise/r11_canonical_pdp_evidence.py:90:db.execute",),
                ("cyber_lion/enterprise/r11_canonical_pdp_evidence.py:413:db.execute",),
            },
        )
        pdp_source = (self.root / "cyber_lion/enterprise/r11_canonical_pdp_evidence.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(pdp_source)
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node,ast.Call)
            and node.lineno in {90,413}
            and isinstance(node.func,ast.Attribute)
            and isinstance(node.func.value,ast.Name)
            and node.func.value.id == "db"
            and node.func.attr == "execute"
            and node.args
        ]
        self.assertEqual(
            sorted((node.lineno,ast.literal_eval(node.args[0]))
                   for node in calls),
            [
                (90,"PRAGMA query_only=ON"),
                (413,"INSERT INTO r11_original_pdp_evidence VALUES(?,?,?)"),
            ],
        )
        self.assertIn("OriginalPDPIssuanceObservation",pdp_source)
        self.assertIn("source/trust mismatch",pdp_source)
        self.assertFalse(set(new) & set(self.historical_surfaces))

    def test_original_worker_verifier_import_preserves_readonly_pragma_ast(self):
        # SOURCE RELOCATION, not a newly introduced writable SQL site.
        rel = "cyber_lion/enterprise/cooperative_dependency_provider.py"
        current = (self.root / rel).read_text(encoding="utf-8")
        old = subprocess.run(
            ["git","show",f"{HISTORICAL_HEAD}:{rel}"],
            cwd=self.root,check=True,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,timeout=30,
        ).stdout.decode("utf-8","strict")
        source_owner = "cyber_lion.enterprise.cooperative_dependency_provider.py"
        added = [
            s for s in self.candidate_surfaces.values()
            if s.digest() not in self.historical_surfaces
            and s.effect_provider == source_owner
        ]
        removed = [
            s for s in self.historical_surfaces.values()
            if s.digest() not in self.candidate_surfaces
            and s.effect_provider == source_owner
        ]
        self.assertEqual(
            [(len(removed),len(added))],
            [(1,1)],
        )
        self.assertEqual(
            (removed[0].entrypoints,added[0].entrypoints),
            (
                (rel+":147:db.execute",),
                (rel+":148:db.execute",),
            ),
        )
        self.assertEqual(
            (removed[0].effect_class,added[0].effect_class),
            ("persistent_state.write","persistent_state.write"),
        )
        def exact_readonly_sql(source,location):
            candidates=[
                node for node in ast.walk(ast.parse(source))
                if isinstance(node,ast.Call) and node.lineno==location
                and isinstance(node.func,ast.Attribute)
                and isinstance(node.func.value,ast.Name)
                and node.func.value.id=="db" and node.func.attr=="execute"
                and node.args and isinstance(node.args[0],ast.Constant)
            ]
            self.assertEqual(len(candidates),1)
            self.assertEqual(ast.literal_eval(candidates[0].args[0]),
                             "PRAGMA query_only=ON")
            return ast.dump(candidates[0],include_attributes=False)
        self.assertEqual(
            exact_readonly_sql(old,147),
            exact_readonly_sql(current,148),
        )
        # The actual changed boundary is the SHA-256-pinned verifier
        # import. It executes compiled checked bytes instead of calling
        # a second potentially drifted SourceFileLoader.
        self.assertIn('verified_code = compile(raw, str(path), "exec"',current)
        self.assertIn("exec(verified_code, module.__dict__)",current)
        self.assertNotIn("spec.loader.exec_module(module)",current)

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
        self.assertEqual(set(old_by_line), set(RECON_RELOCATED_LINES))
        self.assertEqual(
            set(new_by_line),
            set(RECON_RELOCATED_LINES.values()) | {R10_NEW_RECON_CALLSITE},
        )
        path = "cyber_lion/mission_control/control_plane_reconnaissance.py"
        historical_bytes = subprocess.run(
            ["git", "show", f"{HISTORICAL_HEAD}:{path}"],
            cwd=self.root, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30,
        ).stdout
        historical_tree = ast.parse(historical_bytes.decode("utf-8", "strict"))
        current_tree = ast.parse((self.root / path).read_text(encoding="utf-8"))

        def exact_sql_call_at(tree, location):
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
            return ast.dump(nodes[0], include_attributes=False), nodes[0]

        for previous_line, present_line in RECON_RELOCATED_LINES.items():
            with self.subTest(historical_line=previous_line, current_line=present_line):
                self.assertEqual(
                    normalized(old_by_line[previous_line]),
                    normalized(new_by_line[present_line]),
                )
                old_ast, _ = exact_sql_call_at(historical_tree, previous_line)
                present_ast, _ = exact_sql_call_at(current_tree, present_line)
                self.assertEqual(
                    old_ast, present_ast,
                    "Relocated SQL must match the pinned P0 Git object, "
                    "parsed under this same interpreter",
                )

        new_line = R10_NEW_RECON_CALLSITE
        _, new_node = exact_sql_call_at(current_tree, new_line)
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
        # R4 imported an additional source but did not change any of the
        # 71 conversation SQL calls. The original historical P0 commit is
        # already verified by pinned_p0_inventory; compare its full AST with
        # current source under the *same* Python interpreter. Hashing
        # ast.dump output from Python 3.12 and comparing on 3.13 is invalid.
        rel = "cyber_lion/app_coordination/conversation_chat.py"
        historic = subprocess.run(
            ["git", "show", f"{HISTORICAL_HEAD}:{rel}"],
            cwd=self.root, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30,
        ).stdout.decode("utf-8", "strict")
        current = (self.root / rel).read_text(encoding="utf-8")

        def sql_call_bodies(source):
            return sorted(
                ast.dump(node, include_attributes=False)
                for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "conn"
                and node.func.attr == "execute"
            )

        old_calls = sql_call_bodies(historic)
        new_calls = sql_call_bodies(current)
        self.assertEqual(len(old_calls), 71)
        self.assertEqual(len(new_calls), 71)
        self.assertEqual(
            new_calls, old_calls,
            "R4/R10 conversation SQL must retain all 71 pinned P0 calls",
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
