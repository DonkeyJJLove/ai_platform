from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import lion_effect_admission_broker as broker


ROOT = Path(__file__).resolve().parents[2]
SOURCE_MAP = {
    "mission_control_v3.py": ROOT / "tools/lion_mission_control_v3.py",
    "mission_control_compat.py": ROOT / "tools/lion_mission_control_compat.py",
    "lion_mission_lifecycle_db.py": ROOT / "tools/lion_mission_lifecycle_db.py",
    "lion_saas_session_bridge.py": ROOT / "tools/lion_saas_session_bridge.py",
    "lion_saas_broker.py": ROOT / "tools/lion_saas_broker.py",
    "lion_firefox_broker_relay.py": ROOT / "tools/lion_firefox_broker_relay.py",
    "lion_operator_gateway.py": ROOT / "tools/lion_operator_gateway.py",
    "lion_operator_client.py": ROOT / "tools/lion_operator_client.py",
    "lion_operator_provision.py": ROOT / "tools/lion_operator_provision.py",
    "lion_operator_containment_helper.py": ROOT / "tools/lion_operator_containment_helper.py",
    "systemd/lion-operator-control.service": ROOT / "deploy/systemd/lion-operator-control.service",
    "cyber_lion/contracts/operator_intervention.py": ROOT / "cyber_lion/contracts/operator_intervention.py",
    "cyber_lion/mission_control/operator_control.py": ROOT / "cyber_lion/mission_control/operator_control.py",
    "cyber_lion/mission_control/hmk9d_process.py": ROOT / "cyber_lion/mission_control/hmk9d_process.py",
    "cyber_lion/mission_control/operator_swarm_session.py": ROOT / "cyber_lion/mission_control/operator_swarm_session.py",
    "cyber_lion/mission_control/model_calls.py": ROOT / "cyber_lion/mission_control/model_calls.py",
    "cyber_lion/contracts/mission_contract_profiles.py": ROOT / "cyber_lion/contracts/mission_contract_profiles.py",
    "cyber_lion/contracts/phase_execution_contract.py": ROOT / "cyber_lion/contracts/phase_execution_contract.py",
    "cyber_lion/contracts/action_ir.py": ROOT / "cyber_lion/contracts/action_ir.py",
    "cyber_lion/process_language/lpcl.py": ROOT / "cyber_lion/process_language/lpcl.py",
    "cyber_lion/mission_control/__init__.py": ROOT / "cyber_lion/mission_control/__init__.py",
    "cyber_lion/mission_control/execution_driver.py": ROOT / "cyber_lion/mission_control/execution_driver.py",
    "cyber_lion/mission_control/execution_driver_contract.py": ROOT / "cyber_lion/mission_control/execution_driver_contract.py",
    "cyber_lion/mission_control/dual_result_join.py": ROOT / "cyber_lion/mission_control/dual_result_join.py",
    "cyber_lion/mission_control/global_scheduler.py": ROOT / "cyber_lion/mission_control/global_scheduler.py",
    "cyber_lion/mission_control/mission_reconciliation.py": ROOT / "cyber_lion/mission_control/mission_reconciliation.py",
    "cyber_lion/mission_control/control_plane_reconnaissance.py": ROOT / "cyber_lion/mission_control/control_plane_reconnaissance.py",
    "cyber_lion/mission_control/supervisor_projection.py": ROOT / "cyber_lion/mission_control/supervisor_projection.py",
    "cyber_lion/mission_control/runtime_projection.py": ROOT / "cyber_lion/mission_control/runtime_projection.py",
    "cyber_lion/mission_control/phase_control.py": ROOT / "cyber_lion/mission_control/phase_control.py",
    "cyber_lion/mission_control/phase_curriculum.py": ROOT / "cyber_lion/mission_control/phase_curriculum.py",
    **{"static/" + name: ROOT / "deploy/mission-control/v3" / name
       for name in ("index.html", "app.css", "app.js", "passive.js", "control-v3.js")},
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MissionControlV3RestartPackageTests(unittest.TestCase):
    def materialize(self, root: Path) -> None:
        for name, source in SOURCE_MAP.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def test_required_package_manifest_matches_exact_repository_sources(self):
        self.assertEqual(set(broker.MISSION_CONTROL_V3_REQUIRED_SHA256), set(SOURCE_MAP))
        observed = {name: sha256_file(source) for name, source in SOURCE_MAP.items()}
        self.assertEqual(observed, broker.MISSION_CONTROL_V3_REQUIRED_SHA256)
        self.assertEqual(
            broker.MISSION_CONTROL_V3_SHA256,
            broker.MISSION_CONTROL_V3_REQUIRED_SHA256["mission_control_v3.py"],
        )

    def test_complete_exact_package_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.materialize(root)
            with patch.object(broker, "MISSION_CONTROL_V3_ROOT", root):
                self.assertEqual(
                    broker.mission_control_v3_package_identity(),
                    broker.MISSION_CONTROL_V3_REQUIRED_SHA256,
                )

    def test_missing_execution_driver_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.materialize(root)
            (root / "cyber_lion/mission_control/execution_driver.py").unlink()
            with patch.object(broker, "MISSION_CONTROL_V3_ROOT", root):
                with self.assertRaisesRegex(
                    broker.Deny,
                    r"^MISSION_CONTROL_V3_PACKAGE_MISSING:cyber_lion/mission_control/execution_driver\.py$",
                ):
                    broker.mission_control_v3_package_identity()

    def test_missing_action_ir_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.materialize(root)
            (root/'cyber_lion/contracts/action_ir.py').unlink()
            with patch.object(broker,'MISSION_CONTROL_V3_ROOT',root):
                with self.assertRaisesRegex(broker.Deny,'^MISSION_CONTROL_V3_PACKAGE_MISSING:cyber_lion/contracts/action_ir.py$'):
                    broker.mission_control_v3_package_identity()

    def test_missing_canonical_lpcl_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.materialize(root)
            (root/'cyber_lion/process_language/lpcl.py').unlink()
            with patch.object(broker,'MISSION_CONTROL_V3_ROOT',root):
                with self.assertRaisesRegex(broker.Deny,'^MISSION_CONTROL_V3_PACKAGE_MISSING:cyber_lion/process_language/lpcl.py$'):
                    broker.mission_control_v3_package_identity()

    def test_missing_phase_execution_contract_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.materialize(root)
            (root/'cyber_lion/contracts/phase_execution_contract.py').unlink()
            with patch.object(broker,'MISSION_CONTROL_V3_ROOT',root):
                with self.assertRaisesRegex(broker.Deny,'^MISSION_CONTROL_V3_PACKAGE_MISSING:cyber_lion/contracts/phase_execution_contract.py$'):
                    broker.mission_control_v3_package_identity()

    def test_missing_mission_contract_profile_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.materialize(root)
            (root/'cyber_lion/contracts/mission_contract_profiles.py').unlink()
            with patch.object(broker,'MISSION_CONTROL_V3_ROOT',root):
                with self.assertRaisesRegex(broker.Deny,'^MISSION_CONTROL_V3_PACKAGE_MISSING:cyber_lion/contracts/mission_contract_profiles.py$'):
                    broker.mission_control_v3_package_identity()

    def test_missing_mission_reconciliation_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.materialize(root)
            (root/'cyber_lion/mission_control/mission_reconciliation.py').unlink()
            with patch.object(broker,'MISSION_CONTROL_V3_ROOT',root):
                with self.assertRaisesRegex(broker.Deny,'^MISSION_CONTROL_V3_PACKAGE_MISSING:cyber_lion/mission_control/mission_reconciliation.py$'):
                    broker.mission_control_v3_package_identity()

    def test_missing_control_plane_reconnaissance_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.materialize(root)
            (root/'cyber_lion/mission_control/control_plane_reconnaissance.py').unlink()
            with patch.object(broker,'MISSION_CONTROL_V3_ROOT',root):
                with self.assertRaisesRegex(broker.Deny,'^MISSION_CONTROL_V3_PACKAGE_MISSING:cyber_lion/mission_control/control_plane_reconnaissance.py$'):
                    broker.mission_control_v3_package_identity()

    def test_drifted_dual_result_join_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.materialize(root)
            with (root / "cyber_lion/mission_control/dual_result_join.py").open("ab") as handle:
                handle.write(b"\n# drift\n")
            with patch.object(broker, "MISSION_CONTROL_V3_ROOT", root):
                with self.assertRaisesRegex(
                    broker.Deny,
                    r"^MISSION_CONTROL_V3_PACKAGE_IDENTITY:cyber_lion/mission_control/dual_result_join\.py:[0-9a-f]{64}$",
                ):
                    broker.mission_control_v3_package_identity()

    def test_package_imports_with_only_installed_root_on_pythonpath(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.materialize(root)
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "PYTHONPATH": str(root),
                "PYTHONDONTWRITEBYTECODE": "1",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }
            proc = subprocess.run(
                [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, r'%s'); import mission_control_v3; print('IMPORT_OK')" % root],
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "IMPORT_OK")

    def test_drifted_static_control_ui_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.materialize(root)
            with (root / 'static/control-v3.js').open('ab') as handle:
                handle.write(b'\n// stale frontend\n')
            with patch.object(broker, 'MISSION_CONTROL_V3_ROOT', root):
                with self.assertRaisesRegex(broker.Deny, '^MISSION_CONTROL_V3_PACKAGE_IDENTITY:static/control-v3.js:'):
                    broker.mission_control_v3_package_identity()


if __name__ == "__main__":
    unittest.main()
