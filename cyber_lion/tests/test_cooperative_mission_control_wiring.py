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
        self.assertIn("current.update(COOPERATIVE_CAPABILITY_REGISTRY)",source)
    def test_docker_binding_compiles_cooperative_handler_from_phase_contract(self):
        source=self.source()
        self.assertIn("cooperative_classes={cooperative_prod.CAPABILITY_BOOTSTRAP,cooperative_prod.CAPABILITY_PRODUCTION,cooperative_prod.CAPABILITY_VERIFY}",source)
        self.assertIn("handlers[prow['phase_id']]=cooperative if classes & cooperative_classes else generic",source)
    def test_generic_read_executor_does_not_own_cooperative_effects(self):
        tree=ast.parse(self.source())
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="_generic_execute_read_plan")
        text=ast.unparse(fn)
        self.assertNotIn("advance_build",text)
        self.assertNotIn("COOPERATIVE_ARTIFACT_PRODUCTION_R1",text)
    def test_live_stepper_requires_canonical_worker_provider_before_assignments(self):
        source=(ROOT/"cyber_lion/mission_control/cooperative_production.py").read_text(encoding="utf-8")
        self.assertIn('"provider_id": "COOPERATIVE_RUNTIME_WRITER_R5"',source)
        self.assertIn('"context_resolver": "PINNED_COOPERATIVE_CONTEXT_RESOLVER"',source)
        self.assertIn('"execution_engine": "RUNTIME_EXECUTION_ENGINE"',source)
if __name__=="__main__":unittest.main()
