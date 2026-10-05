"""Tests of exact integration functions; live I/O remains outside these fixtures."""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from cyber_lion.mission_control import cooperative_production as cp

ROOT=Path(__file__).resolve().parents[2]

class CooperativeIntegrationGuardsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.now=datetime(2026,10,4,22,0,0,tzinfo=timezone.utc)
        self.status={'material_worker_id':'MD001','observed_at':'2026-10-04T22:00:00Z','state':'READY','self_test':'PASS',
                     'transport_state':'READY','mission_control_reachability':'OK','model_reachability':'OK',
                     'direct_assignment_kinds':['COOPERATIVE_ARTIFACT_WRITE','COOPERATIVE_ARTIFACT_VERIFY'],
                     'architecture':{'runtime_instance_id':'runtime-fixture-1','architecture_capabilities':['COOPERATIVE_ARTIFACT_MATERIALIZATION','COOPERATIVE_ARTIFACT_INDEPENDENT_VERIFY']},
                     'cooperative_runtime_provider':{'state':'READY','provider_id':'COOPERATIVE_RUNTIME_WRITER_R5','context_resolver':'PINNED_COOPERATIVE_CONTEXT_RESOLVER','execution_engine':'RUNTIME_EXECUTION_ENGINE','authority_effect':'NONE'}}

    def write(self,value=None):
        (self.root/'MD001.json').write_text(json.dumps(value or self.status))

    def test_fresh_bound_status(self):
        self.write();result=cp.bootstrap_readiness(self.root,expected_workers=1,now_fn=lambda:self.now)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['workers'][0]['runtime_instance_id'],'runtime-fixture-1')

    def test_stale_ready_file_rejected(self):
        self.write(dict(self.status,observed_at='2026-10-04T21:59:39Z'))
        with self.assertRaisesRegex(cp.CooperativeProductionError,'stale'):cp.bootstrap_readiness(self.root,expected_workers=1,now_fn=lambda:self.now)

    def test_future_timestamp_rejected(self):
        self.write(dict(self.status,observed_at='2026-10-04T22:00:01Z'))
        with self.assertRaises(cp.CooperativeProductionError):cp.bootstrap_readiness(self.root,expected_workers=1,now_fn=lambda:self.now)

    def test_wrong_worker_name_rejected(self):
        self.write(dict(self.status,material_worker_id='MD002'))
        with self.assertRaises(cp.CooperativeProductionError):cp.bootstrap_readiness(self.root,expected_workers=1,now_fn=lambda:self.now)

    def test_duplicate_runtime_identity_rejected(self):
        self.write();(self.root/'MD002.json').write_text(json.dumps(dict(self.status,material_worker_id='MD002')))
        with self.assertRaisesRegex(cp.CooperativeProductionError,'duplicate'):cp.bootstrap_readiness(self.root,expected_workers=2,now_fn=lambda:self.now)

    def test_missing_model_reachability_rejected(self):
        self.write(dict(self.status,model_reachability='STALE'))
        with self.assertRaises(cp.CooperativeProductionError):cp.bootstrap_readiness(self.root,expected_workers=1,now_fn=lambda:self.now)

    def test_missing_canonical_runtime_provider_rejected(self):
        value=dict(self.status);value.pop('cooperative_runtime_provider')
        self.write(value)
        with self.assertRaisesRegex(cp.CooperativeProductionError,'canonical cooperative runtime provider'):
            cp.bootstrap_readiness(self.root,expected_workers=1,now_fn=lambda:self.now)

    def test_forged_runtime_provider_shape_rejected(self):
        value=dict(self.status,cooperative_runtime_provider={'state':'READY','authority_effect':'NONE'})
        self.write(value)
        with self.assertRaisesRegex(cp.CooperativeProductionError,'canonical cooperative runtime provider'):
            cp.bootstrap_readiness(self.root,expected_workers=1,now_fn=lambda:self.now)

    def test_invalid_worker_counts(self):
        for count in [0,-1,True,33]:
            with self.assertRaises(cp.CooperativeProductionError):cp.bootstrap_readiness(self.root,expected_workers=count,now_fn=lambda:self.now)

    def test_read_only_executor_cannot_start_cooperative_materialization(self):
        # Execute the original function AST with explicit observation-only doubles;
        # avoid importing the server module and creating a live database.
        tree=ast.parse((ROOT/'tools/lion_mission_control_v3.py').read_text(encoding='utf-8'))
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='_generic_execute_read_plan')
        calls=[]
        def forbidden(*args,**kwargs):raise AssertionError('production entered from read-only executor')
        namespace={'operator_control':SimpleNamespace(control_state=lambda *a:None,is_capability_revoked=lambda *a:False),
                   'global_sched':SimpleNamespace(update_generic_plan_state=lambda *a,**kw:calls.append((a,kw))),
                   'now':lambda:'2026-10-04T22:00:00Z','control_recon':SimpleNamespace(CAPABILITY_ID='CONTROL_PLANE_RECONNAISSANCE_V1'),
                   'cooperative_prod':SimpleNamespace(CAPABILITY_ID_BOOTSTRAP=cp.CAPABILITY_ID_BOOTSTRAP,CAPABILITY_ID_PRODUCTION=cp.CAPABILITY_ID_PRODUCTION,CAPABILITY_ID_VERIFY=cp.CAPABILITY_ID_VERIFY,advance_build=forbidden)}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<isolated-original-function>','exec'),namespace)
        result=namespace['_generic_execute_read_plan'](None,{'plan_id':'fixture-plan','mission_id':'M1','phase_id':'BUILD','capability':cp.CAPABILITY_ID_PRODUCTION,'authority_class':'NONE'})
        self.assertEqual(result['state'],'BLOCKED')
        self.assertEqual(result['gate'],'CAPABILITY_NOT_AVAILABLE')
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0][2],'WAITING_CURRENTNESS')

if __name__=='__main__':unittest.main()
