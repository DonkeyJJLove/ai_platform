from __future__ import annotations
import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
MC=ROOT/"tools/lion_mission_control_v3.py"
class CooperativeMissionControlWiringTests(unittest.TestCase):
    def source(self):return MC.read_text(encoding="utf-8")
    def test_cooperative_provider_has_dedicated_scheduler_route(self):
        source=self.source()
        self.assertIn("COOPERATIVE_PHASE_HANDLER='COOPERATIVE_PRODUCTION_PHASE'",source)
        self.assertIn("elif _registered_cooperative_driver(mid):drive_cooperative_once(mid)",source)
        self.assertIn("PROCESS_CAPABILITY_REGISTRY[cooperative_prod.CAPABILITY_BOOTSTRAP]",source)
        self.assertIn("def _process_capability_registry_current():",source)
        self.assertIn("COOPERATIVE_MATERIALIZERS.current()",source)
        self.assertIn("current[cooperative_prod.CAPABILITY_PRODUCTION]",source)
        self.assertIn("current[cooperative_prod.CAPABILITY_VERIFY]",source)
    def test_docker_binding_compiles_cooperative_handler_from_phase_contract(self):
        source=self.source()
        for capability in (
            "cooperative_prod.CAPABILITY_BOOTSTRAP",
            "cooperative_prod.CAPABILITY_PRODUCTION",
            "cooperative_prod.CAPABILITY_VERIFY",
            "cooperative_preactivation.CAPABILITY_CLASS",
        ):
            self.assertIn(capability, source)
        self.assertIn("handlers[prow['phase_id']]=cooperative if classes & cooperative_classes else generic",source)
    def test_generic_read_executor_does_not_own_cooperative_effects(self):
        tree=ast.parse(self.source())
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="_generic_execute_read_plan")
        text=ast.unparse(fn)
        self.assertNotIn("advance_build",text)
        self.assertNotIn("COOPERATIVE_ARTIFACT_PRODUCTION_R1",text)
    def test_effectful_stepper_requires_trusted_process_materializer(self):
        source=self.source()
        self.assertIn("gate='COOPERATIVE_MATERIALIZER_NOT_BOUND'",source)
        self.assertIn("write_materializer=materializers.write_materializer",source)
        self.assertIn("verify_materializer=materializers.verify_materializer",source)

    def test_process_bootstrap_owns_exactly_one_registry_install_path(self):
        source=self.source()
        self.assertIn(
            "from cyber_lion.mission_control import cooperative_process_bootstrap as cooperative_process_bootstrap",
            source,
        )
        self.assertIn(
            "COOPERATIVE_PROCESS_BOOTSTRAP=cooperative_process_bootstrap.bootstrap_process_materializers(",
            source,
        )
        self.assertEqual(source.count("COOPERATIVE_MATERIALIZERS=CooperativeMaterializationRegistry()"),1)
        self.assertEqual(source.count("bootstrap_process_materializers("),1)

    def test_preactivation_is_the_only_cooperative_path_before_full_fleet_readiness(self):
        tree=ast.parse(self.source())
        fn=next(
            node for node in tree.body
            if isinstance(node,ast.FunctionDef) and node.name=="drive_cooperative_once"
        )
        text=ast.unparse(fn)
        self.assertLess(
            text.index("cooperative_preactivation.CAPABILITY_ID"),
            text.index("bootstrap_readiness"),
        )
        registry_fn=next(
            node for node in tree.body
            if isinstance(node,ast.FunctionDef) and node.name=="_process_capability_registry_current"
        )
        registry_text=ast.unparse(registry_fn)
        self.assertIn("COOPERATIVE_PREACTIVATION.current() is not None",registry_text)
        self.assertLess(
            registry_text.index("COOPERATIVE_PREACTIVATION.current()"),
            registry_text.index("bootstrap_readiness"),
        )

    def test_application_factory_requires_source_bound_r11_provider(self):
        tree=ast.parse(self.source())
        fn=next(
            x for x in tree.body if isinstance(x,ast.FunctionDef)
            and x.name=="drive_cooperative_once"
        )
        body=ast.unparse(fn)
        self.assertIn("LION-APPLICATION-FACTORY-CROSS-MODEL-R1",body)
        from cyber_lion.mission_control.application_factory_program import MISSION_ID
        self.assertEqual(MISSION_ID,"LION-APPLICATION-FACTORY-CROSS-MODEL-R1")
        self.assertIn("cooperative_preactivation_bootstrap.SOURCE_BOUND_MODE",body)
        self.assertIn("R11_SOURCE_BOUND_PREACTIVATION_REQUIRED",body)
        self.assertLess(
            body.index("R11_SOURCE_BOUND_PREACTIVATION_REQUIRED"),
            body.index("advance_preactivation"),
        )

    def test_live_stepper_requires_canonical_worker_provider_before_assignments(self):
        source=(ROOT/"cyber_lion/mission_control/cooperative_production.py").read_text(encoding="utf-8")
        self.assertIn('"provider_id": "COOPERATIVE_RUNTIME_WRITER_R5"',source)
        self.assertIn('"context_resolver": "PINNED_COOPERATIVE_CONTEXT_RESOLVER"',source)
        self.assertIn('"execution_engine": "RUNTIME_EXECUTION_ENGINE"',source)
if __name__=="__main__":unittest.main()
