from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path
import unittest

import cyber_lion.lcms as lcms
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.tests.test_action_spec_schema import _validate

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "cyber_lion/contracts/v1/action_spec.schema.json"
MATRIX_PATH = ROOT / "cyber_lion/contracts/v1/action_spec_support_matrix.json"
EBNF_PATH = ROOT / "cyber_lion/contracts/v1/lcms.ebnf"
C0_HEAD = "d31a6385793909909b62d2d6bf7825713dbe3dab"
C0_TREE = "e1977c7f1375cfc458c06afa91d469c612a7bc0d"


def minimal_source(*, set_order: int = 0, map_order: int = 0) -> str:
    pre = '["baseline-exact","schema-pinned"]' if set_order == 0 else '["schema-pinned","baseline-exact"]'
    read = '["/workspace/ai_platform/**","/var/tmp/lion/**"]' if set_order == 0 else '["/var/tmp/lion/**","/workspace/ai_platform/**"]'
    return f'''ACTION c1.observe.1 {{
    schema_version = "lion.action-spec/v1.3-candidate";
    kind = "repository.observe";
    intent_ref = "intent:c1";
    mission_ref = "mission:c1";
    autonomy_ref = "autonomy:lion";
    bean_ref = "bean:lcms";
    target {{
        host = "LAB-DEBIAN";
        environment = "WSL2";
        runtime = "schema-only";
    }}
    authority_request {{
        domain = "information.read";
        capability = "repository.observe";
        grant_ref = null;
    }}
    boundary {{
        shell = false;
        network = "DENY";
        filesystem_read = {read};
        filesystem_write = [];
        process_children = [];
        timeout_ms = 1000;
        max_processes = 1;
        memory_limit_bytes = 1048576;
    }}
    preconditions = {pre};
    expected_effects = ["repository state described"];
    forbidden_effects = ["authority effect","runtime execution","transport effect"];
    observation {{
        observer_class = "deterministic_independent";
        required_events = ["schema-validated","source-parsed"];
    }}
    reconciliation {{
        mode = "EXACT";
        receipt = "REQUIRED";
    }}
}}\n'''


def reordered_minimal_source() -> str:
    return '''ACTION c1.observe.1 {
    forbidden_effects = ["transport effect","runtime execution","authority effect"];
    expected_effects = ["repository state described"];
    preconditions = ["schema-pinned","baseline-exact"];
    reconciliation {
        receipt = "REQUIRED";
        mode = "EXACT";
    }
    observation {
        required_events = ["source-parsed","schema-validated"];
        observer_class = "deterministic_independent";
    }
    boundary {
        memory_limit_bytes = 1048576;
        max_processes = 1;
        timeout_ms = 1000;
        process_children = [];
        filesystem_write = [];
        filesystem_read = ["/var/tmp/lion/**","/workspace/ai_platform/**"];
        network = "DENY";
        shell = false;
    }
    authority_request {
        grant_ref = null;
        capability = "repository.observe";
        domain = "information.read";
    }
    target {
        runtime = "schema-only";
        environment = "WSL2";
        host = "LAB-DEBIAN";
    }
    bean_ref = "bean:lcms";
    autonomy_ref = "autonomy:lion";
    mission_ref = "mission:c1";
    intent_ref = "intent:c1";
    kind = "repository.observe";
    schema_version = "lion.action-spec/v1.3-candidate";
}
'''


def process_source(arguments: list[str]) -> str:
    args = json.dumps(arguments, separators=(",", ":"))
    return f'''ACTION c1.process.1 {{
    schema_version = "lion.action-spec/v1.3-candidate";
    kind = "process.exec";
    intent_ref = "intent:c1-process-shape";
    mission_ref = "mission:c1";
    autonomy_ref = "autonomy:lion";
    bean_ref = "bean:process-shape";
    target {{
        host = "LAB-DEBIAN";
        environment = "WSL2";
        runtime = "schema-only";
    }}
    executable {{
        path = "/usr/bin/python3";
        digest = "sha256:{'0' * 64}";
    }}
    arguments = {args};
    workspace {{
        repository = "DonkeyJJLove/ai_platform";
        commit = "{C0_HEAD}";
        tree = "{C0_TREE}";
        path = "/workspace/ai_platform";
    }}
    environment {{
        inherit = false;
        allow = {{"LANG":"C.UTF-8","PYTHONHASHSEED":"0"}};
    }}
    io {{
        stdin = "NONE";
        stdout = "CAPTURE";
        stderr = "CAPTURE";
        tty = false;
    }}
    authority_request {{
        domain = "information.read";
        capability = "test.execute";
        grant_ref = null;
    }}
    boundary {{
        shell = false;
        network = "DENY";
        filesystem_read = ["/workspace/ai_platform/**"];
        filesystem_write = ["/var/tmp/lion/**"];
        process_children = ["/usr/bin/python3"];
        timeout_ms = 900000;
        max_processes = 8;
        memory_limit_bytes = 4294967296;
    }}
    preconditions = ["executable digest exact","workspace commit exact","workspace tree exact"];
    expected_effects = ["exit status observed","stderr captured","stdout captured","test process created"];
    forbidden_effects = ["credential read","network connection","repository mutation","service mutation"];
    observation {{
        observer_class = "independent";
        required_events = ["child-process-closure","filesystem-delta","network-delta","process-exit"];
    }}
    reconciliation {{
        mode = "EXACT";
        receipt = "REQUIRED";
    }}
}}\n'''


class LCMSCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

    def test_c0_dependency_digests_are_exact(self):
        self.assertEqual(sha256(SCHEMA_PATH.read_bytes()).hexdigest(), lcms.C0_ACTION_SPEC_SCHEMA_SHA256)
        self.assertEqual(sha256(MATRIX_PATH.read_bytes()).hexdigest(), lcms.C0_ACTION_SPEC_SUPPORT_MATRIX_SHA256)
        self.assertEqual(lcms.ACTION_SPEC_SCHEMA_VERSION, "lion.action-spec/v1.3-candidate")

    def test_one_semantic_action_has_one_canonical_ir(self):
        a = lcms.compile_lcms(minimal_source())
        b = lcms.compile_lcms(reordered_minimal_source())
        self.assertEqual(a.canonical_ir, b.canonical_ir)
        self.assertEqual(a.canonical_ir_bytes, b.canonical_ir_bytes)
        self.assertEqual(a.canonical_ir_digest, b.canonical_ir_digest)
        self.assertEqual(a.canonical_lcms, b.canonical_lcms)

    def test_set_like_order_is_normalized_but_argument_order_is_semantic(self):
        a = lcms.compile_lcms(minimal_source(set_order=0))
        b = lcms.compile_lcms(minimal_source(set_order=1))
        self.assertEqual(a.canonical_ir_digest, b.canonical_ir_digest)
        p1 = lcms.compile_lcms(process_source(["-m", "unittest", "-v"]))
        p2 = lcms.compile_lcms(process_source(["unittest", "-m", "-v"]))
        self.assertNotEqual(p1.canonical_ir_digest, p2.canonical_ir_digest)
        self.assertNotEqual(p1.canonical_ir["arguments"], p2.canonical_ir["arguments"])

    def test_canonical_round_trip_is_idempotent(self):
        first = lcms.compile_lcms(reordered_minimal_source())
        second = lcms.compile_lcms(first.canonical_lcms)
        self.assertEqual(first.canonical_lcms, second.canonical_lcms)
        self.assertEqual(first.canonical_ir_bytes, second.canonical_ir_bytes)
        self.assertEqual(first.canonical_ir_digest, second.canonical_ir_digest)

    def test_compiled_ir_validates_against_frozen_c0_schema(self):
        for source in (minimal_source(), process_source(["-m", "unittest", "-v"])):
            compiled = lcms.compile_lcms(source)
            _validate(compiled.canonical_ir, self.schema, self.schema)

    def test_parser_and_normalizer_are_distinct(self):
        parsed = lcms.parse_lcms(minimal_source())
        self.assertEqual(parsed["preconditions"], ["baseline-exact", "schema-pinned"])
        normalized = lcms.normalize_action_ir(parsed)
        self.assertEqual(normalized["preconditions"], ["baseline-exact", "schema-pinned"])
        parsed_reversed = lcms.parse_lcms(minimal_source(set_order=1))
        self.assertEqual(parsed_reversed["preconditions"], ["schema-pinned", "baseline-exact"])
        self.assertEqual(lcms.normalize_action_ir(parsed_reversed)["preconditions"], normalized["preconditions"])

    def test_duplicate_top_level_field_fails_closed(self):
        source = minimal_source().replace(
            '    kind = "repository.observe";\n',
            '    kind = "repository.observe";\n    kind = "repository.observe";\n',
        )
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(source)

    def test_duplicate_block_field_fails_closed(self):
        source = minimal_source().replace(
            '        host = "LAB-DEBIAN";\n',
            '        host = "LAB-DEBIAN";\n        host = "LAB-DEBIAN";\n',
        )
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(source)

    def test_duplicate_map_key_fails_closed(self):
        source = process_source(["-V"]).replace(
            'allow = {"LANG":"C.UTF-8","PYTHONHASHSEED":"0"};',
            'allow = {"LANG":"C.UTF-8","LANG":"C","PYTHONHASHSEED":"0"};',
        )
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(source)

    def test_alias_and_redundant_action_id_fail_closed(self):
        alias = minimal_source().replace("schema_version =", "schema =", 1)
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(alias)
        redundant = minimal_source().replace(
            '    schema_version = "lion.action-spec/v1.3-candidate";\n',
            '    action_id = "c1.observe.1";\n    schema_version = "lion.action-spec/v1.3-candidate";\n',
        )
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(redundant)

    def test_noncanonical_unicode_and_whitespace_fail_closed(self):
        escaped = minimal_source().replace('"intent:c1"', '"intent:\\u00e9"')
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(escaped)
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(minimal_source().replace("    kind", "\tkind", 1))

    def test_trailing_comma_fails_closed(self):
        source = minimal_source().replace(
            '["baseline-exact","schema-pinned"]',
            '["baseline-exact","schema-pinned",]',
        )
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(source)

    def test_path_traversal_and_non_normalized_path_fail_closed(self):
        traversal = process_source(["-V"]).replace('/workspace/ai_platform";', '/workspace/../etc";', 1)
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(traversal)
        doubled = process_source(["-V"]).replace('/usr/bin/python3";', '/usr//bin/python3";', 1)
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(doubled)

    def test_unknown_enums_and_shell_true_fail_closed(self):
        bad_kind = minimal_source().replace('kind = "repository.observe";', 'kind = "shell.exec";')
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(bad_kind)
        bad_network = minimal_source().replace('network = "DENY";', 'network = "ANY";')
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(bad_network)
        shell = minimal_source().replace('shell = false;', 'shell = true;')
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(shell)

    def test_missing_required_and_incomplete_process_shape_fail_closed(self):
        missing = minimal_source().replace('    bean_ref = "bean:lcms";\n', '')
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(missing)
        incomplete = process_source(["-V"])
        start = incomplete.index("    io {")
        end = incomplete.index("    authority_request {", start)
        incomplete = incomplete[:start] + incomplete[end:]
        with self.assertRaises(lcms.LCMSError):
            lcms.compile_lcms(incomplete)

    def test_reserved_plan_node_edge_fail_closed(self):
        grammar = EBNF_PATH.read_text(encoding="utf-8")
        for reserved in ("PLAN", "NODE", "EDGE"):
            self.assertIn(f'"{reserved}"', grammar)
            with self.assertRaises(lcms.LCMSError):
                lcms.parse_lcms(f"{reserved} c1.x {{}}\n")

    def test_target_only_contract_is_not_promoted_to_runtime_support(self):
        self.assertEqual(self.matrix["target_only"]["runtime_support"], "NONE_FROM_ACTIONSPEC_SCHEMA")
        self.assertEqual(self.matrix["target_only"]["transport_support"], "NONE")
        self.assertEqual(self.matrix["target_only"]["authority_effect"], "NONE")
        self.assertTrue(self.matrix["invariants"]["target_only_does_not_imply_runtime_support"])
        source = inspect.getsource(lcms)
        for forbidden in ("subprocess", "socket", "urllib", "requests", "os.system", "Popen"):
            self.assertNotIn(forbidden, source)

    def test_lcms_parser_adds_no_effect_surface(self):
        path = "cyber_lion/lcms.py"
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="1" * 40,
            tree_digest="2" * 40,
            sources={path: (ROOT / path).read_text(encoding="utf-8")},
        )
        self.assertEqual(inventory.surfaces, ())
        self.assertEqual(inventory.unclassified_refs, ())


if __name__ == "__main__":
    unittest.main()
