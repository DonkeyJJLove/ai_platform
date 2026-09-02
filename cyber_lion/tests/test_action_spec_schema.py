from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "cyber_lion/contracts/v1/action_spec.schema.json"
MATRIX_PATH = ROOT / "cyber_lion/contracts/v1/action_spec_support_matrix.json"
ACTION_PROPOSAL_PATH = ROOT / "cyber_lion/contracts/v1/action_proposal.schema.json"

BASELINE_SHA = "22ae615c3ec6eedf2a500d0d70d8ecc97ba1cabd"
BASELINE_TREE = "ac8474a13d46e568787b2fc5bd77955e8b0febda"
LIVE_AUTHORITY = ["none", "read", "local_write", "external_write", "financial", "deploy", "privileged"]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _check_type(value, expected):
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    raise AssertionError(f"unsupported test validator type {expected!r}")


def _validate(instance, spec, root):
    if "$ref" in spec:
        assert spec["$ref"] == "#/$defs/uniqueStrings"
        spec = root["$defs"]["uniqueStrings"]

    if "type" in spec:
        expected = spec["type"]
        if isinstance(expected, list):
            assert any(_check_type(instance, item) for item in expected), (instance, expected)
        else:
            assert _check_type(instance, expected), (instance, expected)

    if "const" in spec:
        assert instance == spec["const"], (instance, spec["const"])
    if "enum" in spec:
        assert instance in spec["enum"], (instance, spec["enum"])

    if isinstance(instance, str):
        if "minLength" in spec:
            assert len(instance) >= spec["minLength"]
        if "maxLength" in spec:
            assert len(instance) <= spec["maxLength"]
        if "pattern" in spec:
            assert re.search(spec["pattern"], instance), (instance, spec["pattern"])

    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in spec:
            assert instance >= spec["minimum"]
        if "maximum" in spec:
            assert instance <= spec["maximum"]

    if isinstance(instance, list):
        if "maxItems" in spec:
            assert len(instance) <= spec["maxItems"]
        if spec.get("uniqueItems"):
            rendered = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in instance]
            assert len(rendered) == len(set(rendered))
        if "items" in spec:
            for item in instance:
                _validate(item, spec["items"], root)

    if isinstance(instance, dict):
        required = spec.get("required", [])
        for name in required:
            assert name in instance, f"missing required {name}"
        properties = spec.get("properties", {})
        additional = spec.get("additionalProperties", True)
        for name, value in instance.items():
            if name in properties:
                _validate(value, properties[name], root)
            elif additional is False:
                raise AssertionError(f"unexpected property {name}")
            elif isinstance(additional, dict):
                _validate(value, additional, root)

    for rule in spec.get("allOf", []):
        condition = rule.get("if")
        then = rule.get("then")
        if condition and then:
            matched = True
            for name, subspec in condition.get("properties", {}).items():
                if name not in instance:
                    matched = False
                    break
                try:
                    _validate(instance[name], subspec, root)
                except AssertionError:
                    matched = False
                    break
            if matched:
                _validate(instance, then, root)


class ActionSpecSchemaFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = _load(SCHEMA_PATH)
        cls.matrix = _load(MATRIX_PATH)
        cls.action_proposal = _load(ACTION_PROPOSAL_PATH)

    def _minimal(self):
        return {
            "schema_version": "lion.action-spec/v1.3-candidate",
            "action_id": "c0.observe.1",
            "kind": "repository.observe",
            "intent_ref": "intent:c0",
            "mission_ref": "mission:c0",
            "autonomy_ref": "autonomy:lion",
            "bean_ref": "bean:c0",
            "target": {"host": "github", "environment": "candidate", "runtime": "schema-only"},
            "authority_request": {"domain": "repository", "capability": "observe", "grant_ref": None},
            "boundary": {
                "shell": False,
                "network": "DENY",
                "filesystem_read": [],
                "filesystem_write": [],
                "process_children": [],
                "timeout_ms": 1000,
                "max_processes": 1,
                "memory_limit_bytes": 1048576,
            },
            "preconditions": ["baseline-exact"],
            "expected_effects": [],
            "forbidden_effects": ["runtime-execution", "authority-effect", "transport-effect"],
            "observation": {"observer_class": "deterministic_independent", "required_events": ["schema-validated"]},
            "reconciliation": {"mode": "EXACT", "receipt": "REQUIRED"},
        }

    def test_baseline_and_fail_closed_metadata_are_exact(self):
        c0 = self.schema["x-lion-c0"]
        self.assertEqual(c0["baseline_sha"], BASELINE_SHA)
        self.assertEqual(c0["baseline_tree"], BASELINE_TREE)
        self.assertEqual(c0["runtime_execution"], "NONE")
        self.assertEqual(c0["transport_implementation"], "NONE")
        self.assertEqual(c0["authority_effect"], "NONE")
        self.assertEqual(c0["supersedes"], "NONE_UNTIL_INTEGRATED")

    def test_live_actionproposal_contract_is_preserved_as_as_is(self):
        self.assertEqual(self.action_proposal["properties"]["requested_authority"]["enum"], LIVE_AUTHORITY)
        self.assertEqual(self.matrix["as_is"]["requested_authority"], LIVE_AUTHORITY)
        self.assertEqual(self.action_proposal["properties"]["target"]["type"], "string")
        self.assertTrue(self.matrix["as_is"]["payload_digest_binding"])
        self.assertIn("payload_digest", self.action_proposal["properties"])

    def test_financial_vocabulary_contradiction_is_preserved(self):
        contradiction = {row["id"]: row for row in self.matrix["contradictions"]}["C0-FINANCIAL-AUTHORITY-VOCABULARY"]
        self.assertEqual(contradiction["status"], "PRESERVED")
        self.assertEqual(contradiction["resolution"], "NO_SILENT_MAPPING")
        authority_request = self.schema["properties"]["authority_request"]["properties"]
        self.assertNotIn("requested_authority", authority_request)

    def test_missing_v12_actionspec_contradiction_is_preserved(self):
        contradiction = {row["id"]: row for row in self.matrix["contradictions"]}["C0-V1_2-ACTIONSPEC-ABSENT"]
        self.assertEqual(contradiction["status"], "PRESERVED")
        self.assertEqual(contradiction["resolution"], "NEW_CANDIDATE_NOT_SUPERSESSION")

    def test_target_shape_contradiction_is_preserved(self):
        contradiction = {row["id"]: row for row in self.matrix["contradictions"]}["C0-TARGET-SHAPE"]
        self.assertEqual(contradiction["status"], "PRESERVED")
        self.assertEqual(contradiction["resolution"], "NO_IMPLICIT_RUNTIME_COERCION")
        self.assertEqual(self.action_proposal["properties"]["target"]["type"], "string")
        self.assertEqual(self.schema["properties"]["target"]["type"], "object")

    def test_target_only_fields_cannot_claim_runtime_support(self):
        target_only = set(self.matrix["target_only"]["fields"])
        self.assertTrue({"kind", "target", "authority_request", "boundary", "observation", "reconciliation"} <= target_only)
        self.assertEqual(self.matrix["target_only"]["runtime_support"], "NONE_FROM_ACTIONSPEC_SCHEMA")
        self.assertEqual(self.matrix["target_only"]["transport_support"], "NONE")
        self.assertEqual(self.matrix["target_only"]["authority_effect"], "NONE")
        self.assertTrue(self.matrix["invariants"]["target_only_does_not_imply_runtime_support"])
        self.assertTrue(self.matrix["invariants"]["no_transport_implementation"])
        self.assertTrue(self.matrix["invariants"]["no_process_execution"])
        self.assertTrue(self.matrix["invariants"]["no_authority_minting"])

    def test_schema_has_no_transport_or_authority_minting_primitive(self):
        serialized = json.dumps(self.schema, sort_keys=True).lower()
        for forbidden in (
            '"http_method"', '"socket"', '"private_key"', '"mint_authority"',
            '"signing_key"', '"authority_issuer"', '"transport_provider"',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_minimal_schema_instance_validates(self):
        _validate(self._minimal(), self.schema, self.schema)

    def test_process_exec_shape_is_schema_only_but_type_valid(self):
        value = self._minimal()
        value["kind"] = "process.exec"
        value.update({
            "executable": {"path": "/usr/bin/python3", "digest": "sha256:" + "0" * 64},
            "arguments": ["-V"],
            "workspace": {
                "repository": "DonkeyJJLove/ai_platform",
                "commit": BASELINE_SHA,
                "tree": BASELINE_TREE,
                "path": "/workspace",
            },
            "environment": {"inherit": False, "allow": {}},
            "io": {"stdin": "NONE", "stdout": "CAPTURE", "stderr": "CAPTURE", "tty": False},
        })
        _validate(value, self.schema, self.schema)

    def test_process_exec_missing_execution_shape_fails_type_validation(self):
        value = self._minimal()
        value["kind"] = "process.exec"
        with self.assertRaises(AssertionError):
            _validate(value, self.schema, self.schema)

    def test_shell_true_is_rejected(self):
        value = self._minimal()
        value["boundary"]["shell"] = True
        with self.assertRaises(AssertionError):
            _validate(value, self.schema, self.schema)

    def test_duplicate_preconditions_are_rejected(self):
        value = self._minimal()
        value["preconditions"] = ["same", "same"]
        with self.assertRaises(AssertionError):
            _validate(value, self.schema, self.schema)

    def test_unknown_top_level_property_is_rejected(self):
        value = self._minimal()
        value["transport"] = "forbidden"
        with self.assertRaises(AssertionError):
            _validate(value, self.schema, self.schema)

    def test_invalid_executable_digest_is_rejected(self):
        value = self._minimal()
        value["kind"] = "process.exec"
        value.update({
            "executable": {"path": "/usr/bin/python3", "digest": "sha256:bad"},
            "arguments": [],
            "workspace": {
                "repository": "DonkeyJJLove/ai_platform",
                "commit": BASELINE_SHA,
                "tree": BASELINE_TREE,
                "path": "/workspace",
            },
            "environment": {"inherit": False, "allow": {}},
            "io": {"stdin": "NONE", "stdout": "CAPTURE", "stderr": "CAPTURE", "tty": False},
        })
        with self.assertRaises(AssertionError):
            _validate(value, self.schema, self.schema)


if __name__ == "__main__":
    unittest.main()
