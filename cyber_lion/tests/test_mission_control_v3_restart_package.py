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
    'cyber_lion/contracts/action_ir.py': ROOT / 'cyber_lion/contracts/action_ir.py',
    'cyber_lion/contracts/action_proposal_context.py': ROOT / 'cyber_lion/contracts/action_proposal_context.py',
    'cyber_lion/contracts/action_proposal_projection.py': ROOT / 'cyber_lion/contracts/action_proposal_projection.py',
    'cyber_lion/contracts/action_runtime_binding.py': ROOT / 'cyber_lion/contracts/action_runtime_binding.py',
    'cyber_lion/contracts/builder_process_launch.py': ROOT / 'cyber_lion/contracts/builder_process_launch.py',
    'cyber_lion/contracts/cognitive_continuity.py': ROOT / 'cyber_lion/contracts/cognitive_continuity.py',
    'cyber_lion/contracts/enterprise_graph.py': ROOT / 'cyber_lion/contracts/enterprise_graph.py',
    'cyber_lion/contracts/executor_provisioning.py': ROOT / 'cyber_lion/contracts/executor_provisioning.py',
    'cyber_lion/contracts/executor_sandbox.py': ROOT / 'cyber_lion/contracts/executor_sandbox.py',
    'cyber_lion/contracts/mission_contract_profiles.py': ROOT / 'cyber_lion/contracts/mission_contract_profiles.py',
    'cyber_lion/contracts/operator_intervention.py': ROOT / 'cyber_lion/contracts/operator_intervention.py',
    'cyber_lion/contracts/phase_execution_contract.py': ROOT / 'cyber_lion/contracts/phase_execution_contract.py',
    'cyber_lion/contracts/policy_gate.py': ROOT / 'cyber_lion/contracts/policy_gate.py',
    'cyber_lion/contracts/process_ir.py': ROOT / 'cyber_lion/contracts/process_ir.py',
    'cyber_lion/contracts/repository_maintenance_sandbox.py': ROOT / 'cyber_lion/contracts/repository_maintenance_sandbox.py',
    'cyber_lion/contracts/runtime_currentness.py': ROOT / 'cyber_lion/contracts/runtime_currentness.py',
    'cyber_lion/contracts/runtime_enforcement.py': ROOT / 'cyber_lion/contracts/runtime_enforcement.py',
    'cyber_lion/contracts/runtime_execution.py': ROOT / 'cyber_lion/contracts/runtime_execution.py',
    'cyber_lion/contracts/swarm_status.py': ROOT / 'cyber_lion/contracts/swarm_status.py',
    'cyber_lion/enterprise/authority_grant.py': ROOT / 'cyber_lion/enterprise/authority_grant.py',
    'cyber_lion/enterprise/authority_source.py': ROOT / 'cyber_lion/enterprise/authority_source.py',
    'cyber_lion/enterprise/authority_source_adapter.py': ROOT / 'cyber_lion/enterprise/authority_source_adapter.py',
    'cyber_lion/enterprise/authority_verification.py': ROOT / 'cyber_lion/enterprise/authority_verification.py',
    'cyber_lion/enterprise/control_plane.py': ROOT / 'cyber_lion/enterprise/control_plane.py',
    'cyber_lion/enterprise/cooperative_context_resolver.py': ROOT / 'cyber_lion/enterprise/cooperative_context_resolver.py',
    'cyber_lion/enterprise/cooperative_control_plane_materializer.py': ROOT / 'cyber_lion/enterprise/cooperative_control_plane_materializer.py',
    'cyber_lion/enterprise/cooperative_dependency_provider.py': ROOT / 'cyber_lion/enterprise/cooperative_dependency_provider.py',
    'cyber_lion/enterprise/cooperative_provider_materialization.py': ROOT / 'cyber_lion/enterprise/cooperative_provider_materialization.py',
    'cyber_lion/enterprise/cooperative_runtime_composition.py': ROOT / 'cyber_lion/enterprise/cooperative_runtime_composition.py',
    'cyber_lion/enterprise/cooperative_runtime_evidence_exporter.py': ROOT / 'cyber_lion/enterprise/cooperative_runtime_evidence_exporter.py',
    'cyber_lion/enterprise/cooperative_runtime_evidence_sources.py': ROOT / 'cyber_lion/enterprise/cooperative_runtime_evidence_sources.py',
    'cyber_lion/enterprise/cooperative_runtime_preparation_provider.py': ROOT / 'cyber_lion/enterprise/cooperative_runtime_preparation_provider.py',
    'cyber_lion/enterprise/cooperative_runtime_preparer.py': ROOT / 'cyber_lion/enterprise/cooperative_runtime_preparer.py',
    'cyber_lion/enterprise/cooperative_runtime_root.py': ROOT / 'cyber_lion/enterprise/cooperative_runtime_root.py',
    'cyber_lion/enterprise/cooperative_runtime_writer.py': ROOT / 'cyber_lion/enterprise/cooperative_runtime_writer.py',
    'cyber_lion/enterprise/executor_sandbox.py': ROOT / 'cyber_lion/enterprise/executor_sandbox.py',
    'cyber_lion/enterprise/live_authority_admission.py': ROOT / 'cyber_lion/enterprise/live_authority_admission.py',
    'cyber_lion/enterprise/models.py': ROOT / 'cyber_lion/enterprise/models.py',
    'cyber_lion/enterprise/persistent_authority_state.py': ROOT / 'cyber_lion/enterprise/persistent_authority_state.py',
    'cyber_lion/enterprise/policy_gate.py': ROOT / 'cyber_lion/enterprise/policy_gate.py',
    'cyber_lion/enterprise/runtime_currentness.py': ROOT / 'cyber_lion/enterprise/runtime_currentness.py',
    'cyber_lion/enterprise/runtime_enforcement.py': ROOT / 'cyber_lion/enterprise/runtime_enforcement.py',
    'cyber_lion/enterprise/runtime_execution.py': ROOT / 'cyber_lion/enterprise/runtime_execution.py',
    'cyber_lion/enterprise/swarm_status_projection.py': ROOT / 'cyber_lion/enterprise/swarm_status_projection.py',
    'cyber_lion/enterprise/trusted_control_plane_providers.py': ROOT / 'cyber_lion/enterprise/trusted_control_plane_providers.py',
    'cyber_lion/enterprise/trusted_control_plane_service.py': ROOT / 'cyber_lion/enterprise/trusted_control_plane_service.py',
    'cyber_lion/mission_control/__init__.py': ROOT / 'cyber_lion/mission_control/__init__.py',
    'cyber_lion/mission_control/artifact_transfer.py': ROOT / 'cyber_lion/mission_control/artifact_transfer.py',
    'cyber_lion/mission_control/control_plane_reconnaissance.py': ROOT / 'cyber_lion/mission_control/control_plane_reconnaissance.py',
    'cyber_lion/mission_control/cooperative_artifacts.py': ROOT / 'cyber_lion/mission_control/cooperative_artifacts.py',
    'cyber_lion/mission_control/cooperative_materialization_registry.py': ROOT / 'cyber_lion/mission_control/cooperative_materialization_registry.py',
    'cyber_lion/mission_control/cooperative_preactivation.py': ROOT / 'cyber_lion/mission_control/cooperative_preactivation.py',
    'cyber_lion/mission_control/cooperative_preactivation_bootstrap.py': ROOT / 'cyber_lion/mission_control/cooperative_preactivation_bootstrap.py',
    'cyber_lion/mission_control/cooperative_process_bootstrap.py': ROOT / 'cyber_lion/mission_control/cooperative_process_bootstrap.py',
    'cyber_lion/mission_control/cooperative_production.py': ROOT / 'cyber_lion/mission_control/cooperative_production.py',
    'cyber_lion/mission_control/cooperative_readiness.py': ROOT / 'cyber_lion/mission_control/cooperative_readiness.py',
    'cyber_lion/mission_control/cooperative_worker_bootstrap.py': ROOT / 'cyber_lion/mission_control/cooperative_worker_bootstrap.py',
    'cyber_lion/mission_control/cooperative_worker_runtime.py': ROOT / 'cyber_lion/mission_control/cooperative_worker_runtime.py',
    'cyber_lion/mission_control/dual_result_join.py': ROOT / 'cyber_lion/mission_control/dual_result_join.py',
    'cyber_lion/mission_control/execution_driver.py': ROOT / 'cyber_lion/mission_control/execution_driver.py',
    'cyber_lion/mission_control/execution_driver_contract.py': ROOT / 'cyber_lion/mission_control/execution_driver_contract.py',
    'cyber_lion/mission_control/global_scheduler.py': ROOT / 'cyber_lion/mission_control/global_scheduler.py',
    'cyber_lion/mission_control/lpcl_runtime_selection.py': ROOT / 'cyber_lion/mission_control/lpcl_runtime_selection.py',
    'cyber_lion/mission_control/material_fleet_lifecycle.py': ROOT / 'cyber_lion/mission_control/material_fleet_lifecycle.py',
    'cyber_lion/mission_control/mission_reconciliation.py': ROOT / 'cyber_lion/mission_control/mission_reconciliation.py',
    'cyber_lion/mission_control/model_calls.py': ROOT / 'cyber_lion/mission_control/model_calls.py',
    'cyber_lion/mission_control/operator_control.py': ROOT / 'cyber_lion/mission_control/operator_control.py',
    'cyber_lion/mission_control/operator_swarm_session.py': ROOT / 'cyber_lion/mission_control/operator_swarm_session.py',
    'cyber_lion/mission_control/phase_control.py': ROOT / 'cyber_lion/mission_control/phase_control.py',
    'cyber_lion/mission_control/runtime_projection.py': ROOT / 'cyber_lion/mission_control/runtime_projection.py',
    'cyber_lion/mission_control/supervisor_projection.py': ROOT / 'cyber_lion/mission_control/supervisor_projection.py',
    'cyber_lion/process_language/lpcl.py': ROOT / 'cyber_lion/process_language/lpcl.py',
    'lion_firefox_broker_relay.py': ROOT / 'tools/lion_firefox_broker_relay.py',
    'lion_mission_lifecycle_db.py': ROOT / 'tools/lion_mission_lifecycle_db.py',
    'lion_operator_client.py': ROOT / 'tools/lion_operator_client.py',
    'lion_operator_containment_helper.py': ROOT / 'tools/lion_operator_containment_helper.py',
    'lion_operator_gateway.py': ROOT / 'tools/lion_operator_gateway.py',
    'lion_operator_provision.py': ROOT / 'tools/lion_operator_provision.py',
    'lion_saas_broker.py': ROOT / 'tools/lion_saas_broker.py',
    'lion_saas_session_bridge.py': ROOT / 'tools/lion_saas_session_bridge.py',
    'mission_control_compat.py': ROOT / 'tools/lion_mission_control_compat.py',
    'mission_control_v3.py': ROOT / 'tools/lion_mission_control_v3.py',
    'static/app.css': ROOT / 'deploy/mission-control/v3/app.css',
    'static/app.js': ROOT / 'deploy/mission-control/v3/app.js',
    'static/control-v3.js': ROOT / 'deploy/mission-control/v3/control-v3.js',
    'static/index.html': ROOT / 'deploy/mission-control/v3/index.html',
    'static/passive.js': ROOT / 'deploy/mission-control/v3/passive.js',
    'systemd/lion-operator-control.service': ROOT / 'deploy/systemd/lion-operator-control.service',
    'tools/lion_cooperative_worker_adapter.py': ROOT / 'tools/lion_cooperative_worker_adapter.py',
    'tools/lion_mission_lifecycle_db.py': ROOT / 'tools/lion_mission_lifecycle_db.py',
    'tools/lion_saas_broker.py': ROOT / 'tools/lion_saas_broker.py',
    'tools/lion_saas_session_bridge.py': ROOT / 'tools/lion_saas_session_bridge.py',
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
            {target:source.relative_to(ROOT).as_posix() for target,source in SOURCE_MAP.items()},
            broker.MISSION_CONTROL_V3_SOURCE_MAP,
        )
        import json
        manifest=json.loads(
            (ROOT/"LION/architecture/v1_5/application_factory_r1/DEPLOYMENT_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["file_count"],len(SOURCE_MAP))
        self.assertEqual(
            {row["target"]:(row["source"],row["sha256"]) for row in manifest["files"]},
            {target:(source.relative_to(ROOT).as_posix(),observed[target])
             for target,source in SOURCE_MAP.items()},
        )
        for path in (
            "cyber_lion/mission_control/material_fleet_lifecycle.py",
            "cyber_lion/mission_control/cooperative_process_bootstrap.py",
            "cyber_lion/mission_control/cooperative_preactivation.py",
            "cyber_lion/mission_control/cooperative_preactivation_bootstrap.py",
            "cyber_lion/enterprise/cooperative_runtime_preparer.py",
            "cyber_lion/enterprise/cooperative_runtime_preparation_provider.py",
            "tools/lion_cooperative_worker_adapter.py",
        ):
            self.assertIn(path,SOURCE_MAP)
        self.assertEqual(
            broker.MISSION_CONTROL_V3_SHA256,
            broker.MISSION_CONTROL_V3_REQUIRED_SHA256["mission_control_v3.py"],
        )

    def test_static_app_preserves_last_known_across_projection_and_transient_health_failures(self):
        source = SOURCE_MAP["static/app.js"].read_text(encoding="utf-8")
        self.assertIn("await get('/health')", source)
        self.assertIn("Promise.allSettled", source)
        self.assertIn("DEGRADED · LAST KNOWN", source)
        self.assertIn("healthFailureStreak<3", source)
        self.assertIn("OFFLINE after 3 consecutive health failures", source)
        self.assertIn("STALE — last known selected run retained", source)
        self.assertIn("EVENTS_REFRESH_INTERVAL_MS=15000", source)
        self.assertIn("EVENTS_FANOUT_LIMIT=12", source)
        self.assertIn("eventRefreshCandidates", source)
        self.assertIn("recentEventsCache", source)
        self.assertNotIn("latestFleet={};latestObservations={};renderSummary({})", source)
        self.assertNotIn("previous details are hidden", source)

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

    def test_missing_cognitive_continuity_contract_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.materialize(root)
            (root/'cyber_lion/contracts/cognitive_continuity.py').unlink()
            with patch.object(broker,'MISSION_CONTROL_V3_ROOT',root):
                with self.assertRaisesRegex(
                    broker.Deny,
                    '^MISSION_CONTROL_V3_PACKAGE_MISSING:cyber_lion/contracts/cognitive_continuity.py$',
                ):
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
