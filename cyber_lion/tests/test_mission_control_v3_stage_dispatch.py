"""Bounded staging operation wiring for existing Mission Control V3 broker.

Tests use only temporary package roots, pinned source bytes and mocked host
identity. They never contact GitHub, perform a privileged live stage, restart
a unit, or mutate a mission database.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import lion_effect_admission_broker as broker
from cyber_lion.tests.test_mission_control_v3_restart_package import SOURCE_MAP

ROOT = Path(__file__).resolve().parents[2]
HEAD = "e9129ec0166e40bebf96986313008d87a11b04eb"
TREE = "1e6c3d97c75e1bc65e6632a0ff76a5bf9bbc7284"
RID = "c" * 64


def request(**extra):
    return {
        "schema_version": broker.SCHEMA,
        "request_id": RID,
        "operation": "MISSION_CONTROL_V3_STAGE_CURRENT_MASTER",
        "source_head": HEAD,
        "source_tree": TREE,
        **extra,
    }


def handle_with_bound_peer(value):
    with (
        patch.object(broker, "peer_uid", return_value=42424),
        patch.object(broker.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=42424)),
        patch.object(broker.os, "getuid", return_value=0),
        patch.object(broker.socket, "gethostname", return_value=broker.EXPECTED_HOST),
    ):
        return broker.handle(value)


class MissionControlV3StageDispatchTests(unittest.TestCase):
    def test_stage_is_listed_in_existing_broker_allowlist(self):
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(broker, "IDENTITY_FILE", Path(td) / "absent-identity.json"),
        ):
            result = handle_with_bound_peer({
                "schema_version": broker.SCHEMA,
                "request_id": RID,
                "operation": "PING",
            })
        self.assertIn("MISSION_CONTROL_V3_STAGE_CURRENT_MASTER", result["operations"])
        self.assertIn("MISSION_CONTROL_V3_INSTALL", result["operations"])

    def test_existing_broker_dispatches_stage_to_one_canonical_owner(self):
        expected = {"staged": True, "test_marker": "NO_EFFECT"}
        with patch.object(
            broker, "mission_control_v3_stage_current_master",
            return_value=expected,
        ) as call:
            result = handle_with_bound_peer(request())
        self.assertEqual(result, expected)
        call.assert_called_once_with(request())

    def test_noncanonical_extra_field_fails_before_checkout(self):
        with patch.object(broker, "_mission_control_v3_checkout_current_master") as checkout:
            with self.assertRaisesRegex(broker.Deny, "MISSION_CONTROL_V3_STAGE_FIELD_SET"):
                broker.mission_control_v3_stage_current_master(
                    request(unrequested="widening")
                )
            checkout.assert_not_called()

    def test_existing_currentness_gate_denies_source_substitution(self):
        with (
            patch.object(broker, "_mission_control_v3_source_envelope",
                         side_effect=broker.Deny("MISSION_CONTROL_V3_SOURCE_DRIFT")),
            patch.object(broker, "_mission_control_v3_checkout_current_master") as checkout,
        ):
            with self.assertRaisesRegex(broker.Deny, "SOURCE_DRIFT"):
                broker.mission_control_v3_stage_current_master(request())
            checkout.assert_not_called()

    def test_pinned_package_stage_and_receipt_use_only_temporary_root(self):
        with tempfile.TemporaryDirectory(prefix="lion-r6-stage-") as temp:
            root = Path(temp)
            checkout = root / "checkout"
            stage = root / "stage"
            state = root / "state"
            checkout.mkdir()
            for _target, source in sorted(SOURCE_MAP.items()):
                relative = source.relative_to(ROOT)
                dest = checkout / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copyfile(source, dest)

            with (
                patch.object(broker, "MISSION_CONTROL_V3_STAGE_ROOT", stage),
                patch.object(broker, "MISSION_CONTROL_V3_DEPLOY_STATE", state),
                patch.object(broker, "_mission_control_v3_source_envelope",
                             return_value=(HEAD, TREE)) as gate,
                patch.object(broker, "_mission_control_v3_checkout_current_master",
                             return_value=checkout) as source,
            ):
                result = broker.mission_control_v3_stage_current_master(request())
                identity, meta = broker._mission_control_v3_stage_readback(HEAD, TREE)
            gate.assert_called_once_with(request())
            source.assert_called_once_with(HEAD, TREE)
            self.assertTrue(result["staged"])
            self.assertEqual(result["file_count"], len(SOURCE_MAP))
            # R9 installs the original, read-only 0/1/32 phase projector
            # as the 92nd exact-source package item.
            self.assertEqual(len(identity), 93)
            self.assertEqual(result["package_identity"], identity)
            self.assertEqual(meta["source_head"], HEAD)
            self.assertEqual(meta["source_tree"], TREE)
            self.assertEqual(meta["runtime_effect"], "NONE")
            self.assertEqual(result["control_receipt"]["operation"],
                             "MISSION_CONTROL_V3_STAGE_CURRENT_MASTER")
            self.assertEqual(result["control_receipt"]["runtime_effect"], "NONE")
            receipt = state / "receipts" / (RID + ".stage.json")
            self.assertTrue(receipt.is_file())
            self.assertEqual(
                json.loads(receipt.read_text(encoding="utf-8"))["receipt_digest"],
                result["control_receipt"]["receipt_digest"],
            )
            self.assertFalse(checkout.exists())


    def test_existing_stage_receipt_denies_replay_before_checkout(self):
        with tempfile.TemporaryDirectory(prefix="lion-stage-replay-") as td:
            state = Path(td) / "state"
            receipt = state / "receipts" / (RID + ".stage.json")
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text('{"existing":true}', encoding="utf-8")
            with (
                patch.object(broker, "MISSION_CONTROL_V3_DEPLOY_STATE", state),
                patch.object(broker, "_mission_control_v3_source_envelope",
                             return_value=(HEAD, TREE)),
                patch.object(broker, "_mission_control_v3_checkout_current_master") as checkout,
            ):
                with self.assertRaisesRegex(broker.Deny, "STAGE_REQUEST_REPLAY"):
                    broker.mission_control_v3_stage_current_master(request())
                checkout.assert_not_called()
            self.assertEqual(receipt.read_text(encoding="utf-8"), '{"existing":true}')

    def test_missing_package_dependency_preserves_previous_good_stage(self):
        with tempfile.TemporaryDirectory(prefix="lion-stage-rollback-") as td:
            root = Path(td)
            checkout = root / "source"
            stage = root / "stage"
            state = root / "state"
            checkout.mkdir()
            for source in SOURCE_MAP.values():
                rel = source.relative_to(ROOT)
                target = checkout / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.copyfile(source, target)

            with patch.object(broker, "MISSION_CONTROL_V3_DEPLOY_STATE", state):
                good = broker.mission_control_v3_materialize_stage_from_checkout(
                    checkout, stage, source_head=HEAD, source_tree=TREE,
                    request_id=RID,
                )
                self.assertTrue(good["staged"])
                old_identity = broker.mission_control_v3_package_identity_at(stage)
                self.assertEqual(len(old_identity), 93)
                missing = checkout / "cyber_lion/mission_control/cooperative_preactivation.py"
                self.assertTrue(missing.exists())
                missing.unlink()
                with self.assertRaisesRegex(broker.Deny, "SOURCE_FILE"):
                    broker.mission_control_v3_materialize_stage_from_checkout(
                        checkout, stage, source_head=HEAD, source_tree=TREE,
                        request_id="d" * 64,
                    )
                after = broker.mission_control_v3_package_identity_at(stage)
                self.assertEqual(after, old_identity)
                self.assertEqual(len(after), 93)
                self.assertEqual(
                    json.loads((stage / broker.MISSION_CONTROL_V3_STAGE_IDENTITY)
                               .read_text(encoding="utf-8"))["source_head"], HEAD
                )


if __name__ == "__main__":
    unittest.main()
