from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest

from cyber_lion.contracts.action_ir import (
    ActionIRContractError,
    CanonicalActionIR,
    action_ir_payload_digest,
    canonical_action_ir_bytes,
)
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.control_plane import ActionProposal


class CanonicalActionIRTests(unittest.TestCase):
    def minimal(self):
        return {
            "schema_version": "1.0.0",
            "action_id": "r19j.observe.1",
            "kind": "repository.observe",
            "intent_ref": "intent:r19j",
            "mission_ref": "mission:r19j",
            "autonomy_ref": "autonomy:lion",
            "bean_ref": "bean:r19j",
            "target": {"host": "github", "environment": "candidate", "runtime": "none"},
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
            "forbidden_effects": ["execution", "authority-minting"],
            "observation": {"observer_class": "deterministic_independent", "required_events": ["ir-validated"]},
            "reconciliation": {"mode": "EXACT", "receipt": "REQUIRED"},
        }

    def process(self):
        value = self.minimal()
        value["kind"] = "process.exec"
        value.update({
            "executable": {"path": "/usr/bin/python3", "digest": "sha256:" + "0" * 64},
            "arguments": ["-V"],
            "workspace": {
                "repository": "DonkeyJJLove/ai_platform",
                "commit": "1" * 40,
                "tree": "2" * 40,
                "path": "/workspace",
            },
            "environment": {"inherit": False, "allow": {}},
            "io": {"stdin": "NONE", "stdout": "CAPTURE", "stderr": "CAPTURE", "tty": False},
        })
        return value

    def test_mapping_has_single_deterministic_canonical_byte_representation(self):
        value = self.minimal()
        reordered = {key: value[key] for key in reversed(tuple(value))}
        a = CanonicalActionIR.from_mapping(value)
        b = CanonicalActionIR.from_mapping(reordered)
        self.assertEqual(a.canonical_bytes, b.canonical_bytes)
        self.assertEqual(a.payload_digest, b.payload_digest)
        self.assertEqual(a.payload_digest, sha256(a.canonical_bytes).hexdigest())
        self.assertEqual(len(a.payload_digest), 64)
        self.assertNotIn(" ", a.canonical_bytes.decode("utf-8"))

    def test_payload_digest_binds_existing_actionproposal_without_minting_authority(self):
        ir = CanonicalActionIR.from_mapping(self.minimal())
        proposal = ActionProposal(
            proposal_id="proposal:r19j",
            mission_id="mission:r19j",
            swarm_id="swarm:r19j",
            proposer_agent_id="agent:r19j",
            capability="observe",
            requested_authority="read",
            action_class="repository.observe",
            target="github:DonkeyJJLove/ai_platform",
            consequential=True,
            evidence_refs=("ir:" + ir.payload_digest,),
            required_observability=("ir-validated",),
            payload_digest=ir.payload_digest,
        ).validate()
        self.assertEqual(proposal.payload_digest, ir.payload_digest)
        self.assertEqual(proposal.requested_authority, "read")

    def test_process_exec_requires_complete_execution_shape(self):
        CanonicalActionIR.from_mapping(self.process())
        broken = self.process()
        broken.pop("workspace")
        with self.assertRaisesRegex(ActionIRContractError, "requires execution-shaped"):
            CanonicalActionIR.from_mapping(broken)

    def test_unknown_property_and_duplicate_json_key_fail_closed(self):
        value = self.minimal()
        value["transport"] = "forbidden"
        with self.assertRaisesRegex(ActionIRContractError, "keys are not canonical"):
            CanonicalActionIR.from_mapping(value)
        raw = '{"schema_version":"1.0.0","schema_version":"1.0.0"}'
        with self.assertRaisesRegex(ActionIRContractError, "duplicate JSON object key"):
            CanonicalActionIR.from_json(raw)

    def test_implementation_does_not_silently_strengthen_live_schema(self):
        value = self.minimal()
        value["authority_request"]["grant_ref"] = ""
        value["executable"] = {"path": "/../schema-valid", "digest": "sha256:" + "1" * 64}
        ir = CanonicalActionIR.from_mapping(value)
        self.assertEqual(ir.as_dict()["authority_request"]["grant_ref"], "")
        self.assertEqual(ir.as_dict()["executable"]["path"], "/../schema-valid")

        process = self.process()
        process["arguments"] = [""]
        self.assertEqual(CanonicalActionIR.from_mapping(process).as_dict()["arguments"], [""])

    def test_canonical_utf8_is_stable_without_ascii_rewriting(self):
        value = self.minimal()
        value["intent_ref"] = "intent:żółw"
        ir = CanonicalActionIR.from_mapping(value)
        self.assertIn("żółw".encode("utf-8"), ir.canonical_bytes)
        self.assertEqual(CanonicalActionIR.from_json(ir.canonical_bytes), ir)

    def test_digest_helper_matches_object(self):
        value = self.minimal()
        self.assertEqual(action_ir_payload_digest(value), CanonicalActionIR.from_mapping(value).payload_digest)
        self.assertEqual(canonical_action_ir_bytes(value), CanonicalActionIR.from_mapping(value).canonical_bytes)

    def test_contract_module_adds_no_effect_surface(self):
        source = Path("cyber_lion/contracts/action_ir.py").read_text(encoding="utf-8")
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="0" * 40,
            tree_digest="0" * 40,
            sources={"cyber_lion/contracts/action_ir.py": source},
        )
        self.assertEqual(inventory.surfaces, ())


if __name__ == "__main__":
    unittest.main()
