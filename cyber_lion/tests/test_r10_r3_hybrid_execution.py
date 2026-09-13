import hashlib
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from cyber_lion.app_coordination.local_intelligence_gateway import Gateway
from cyber_lion.app_coordination.hybrid_gateway_extension import apply_hybrid_gateway_extension
from cyber_lion.app_coordination.lion_context_provider import SOURCES, build_lion_context
from tools.lion_local_intelligence_runtime import LpclControlBridge


class HybridGatewayTests(unittest.TestCase):
    def ctxrepo(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        for rel in SOURCES:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / 'AGENTS.md').write_text('x', encoding='utf-8')
        auth = {'invariants': [
            'LPCL_GENERATION_NE_AUTHORITY',
            'USER_EXPLICIT_LAUNCH_OR_RUN_OF_EXACT_LPCL_IS_EXTERNAL_ACTIVATION_EVENT',
            'SUCCESSOR_IDENTITY_OUTSIDE_BOUND_SCOPE_REQUIRES_NEW_LPCL_AND_NEW_USER_LAUNCH',
        ]}
        (root / SOURCES[1]).write_text(json.dumps(auth), encoding='utf-8')
        for rel in SOURCES[2:-1]:
            (root / rel).write_text('x', encoding='utf-8')
        (root / SOURCES[-1]).write_text(json.dumps({'preferred_release': 'r9'}), encoding='utf-8')
        return td, root

    @staticmethod
    def cur(kind, args):
        if kind == 'github_branch':
            return {'head': 'a' * 40, 'tree': 'b' * 40}
        return {}

    @staticmethod
    def git(op, args):
        return {'head': 'a' * 40, 'tree': 'b' * 40} if op == 'head_tree' else []

    def test_context_declares_hybrid_identity(self):
        td, root = self.ctxrepo(); self.addCleanup(td.cleanup)
        ctx = build_lion_context(root)
        self.assertIn('HYBRID_AI_NATIVE_CONTROL_AND_EXECUTION_ENVIRONMENT', ctx.text)
        self.assertIn('gpt-oss-20b-MXFP4', ctx.text)
        self.assertIn('CHATGPT_SAAS_SUPERVISOR', ctx.text)
        self.assertIn('R8/R9/R10 are LION evolution/material/process epochs', ctx.text)

    def test_lion_definition_is_system_context_not_public_web(self):
        td, root = self.ctxrepo(); self.addCleanup(td.cleanup)
        class ExtendedGateway(Gateway):
            pass
        apply_hybrid_gateway_extension(ExtendedGateway)
        g = ExtendedGateway(root, None, None, None, 'http://127.0.0.1:8772', 'b' * 64, lambda m, n: 'local', self.cur, self.git)
        self.assertEqual(g._route('Co to LION')[0], 'SYSTEM_CONTEXT')
        self.assertEqual(g.state()['saas_supervisor']['transport'], 'EXTERNAL_SESSION_MEDIATED')
        self.assertFalse(g.state()['saas_supervisor']['automatic_hop_materialized'])

    def test_dual_evaluation_never_fakes_saas_answer(self):
        td, root = self.ctxrepo(); self.addCleanup(td.cleanup)
        calls = []
        class ExtendedGateway(Gateway):
            pass
        apply_hybrid_gateway_extension(ExtendedGateway)
        g = ExtendedGateway(root, None, None, None, 'http://127.0.0.1:8772', 'b' * 64, lambda m, n: (calls.append(m) or 'LOCAL'), self.cur, self.git)
        out = g.chat('Zapytaj model SaaS i model lokalny o to samo pytanie: Co to LION', output_language='pl')
        self.assertEqual(out['route'], 'DUAL_EVALUATION')
        self.assertEqual(out['local_evaluation']['answer'], 'LOCAL')
        self.assertEqual(out['local_evaluation']['route'], 'SYSTEM_CONTEXT')
        self.assertEqual(out['saas_handoff']['status'], 'AWAITING_EXTERNAL_SESSION_MEDIATION')
        self.assertFalse(out['saas_handoff']['automatic_hop_materialized'])
        self.assertEqual(len(calls), 1)


class ParserNormalizationTests(unittest.TestCase):
    def test_multiline_aliases_protocols_and_phase_are_normalized(self):
        class Broker:
            def call(self, *args, **kwargs):
                return {'result': {'head': 'a' * 40, 'tree': 'b' * 40}}
        bridge = LpclControlBridge(Broker())
        text = '''PROJECT=\nLION_EVOLUSION\nMODE=\nAUTONOMOUS_EXECUTE\nCONTROL_LANGUAGE=\nLPCL/1.1\nMISSION_ID=\nTEST-R1\nMISSION_TITLE=\nTest mission\nMISSION_OBJECTIVE=\nDo test\nLOGICAL_DRONES=\n12\nMATERIAL_FLEET_TARGET=\n64\nPROTOCOLS=\nLPCL\nAUTHORITY\nCURRENTNESS\nPHASE_01=\nCURRENTNESS_REACQUIRE\n'''
        spec = bridge.validate(text)['spec']
        self.assertEqual(spec['description'], 'Do test')
        self.assertEqual(spec['logical_count'], 12)
        self.assertEqual(spec['material_target'], 64)
        self.assertEqual(spec['protocols'], ['LPCL', 'AUTHORITY', 'CURRENTNESS'])
        self.assertEqual(spec['phases'], [{'id': 'CURRENTNESS_REACQUIRE', 'title': 'Currentness Reacquire'}])


class MissionRebindTests(unittest.TestCase):
    def test_authorized_continuation_rebinds_healthy_64_worker_fleet(self):
        tools = Path(__file__).resolve().parents[2] / 'tools'
        sys.path.insert(0, str(tools))
        compat = importlib.import_module('lion_mission_control_compat')
        sys.modules['mission_control_compat'] = compat
        mc = importlib.import_module('lion_mission_control_v3')
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        old_db, old_legacy = mc.DB, mc.LEGACY_DB
        self.addCleanup(lambda: setattr(mc, 'DB', old_db)); self.addCleanup(lambda: setattr(mc, 'LEGACY_DB', old_legacy))
        mc.DB = Path(td.name) / 'mc.db'; mc.LEGACY_DB = Path(td.name) / 'none.db'; mc.migrate()
        protocols = list(mc.PROTOCOLS)

        def spec(mid, text):
            return {'mission_id': mid, 'title': mid, 'objective': 'o', 'description': 'd', 'lpcl_digest': hashlib.sha256(text.encode()).hexdigest(), 'lpcl_text': text, 'source_head': 'a' * 40, 'source_tree': 'b' * 40, 'logical_count': 12, 'material_target': 64, 'phases': [{'id': 'CURRENTNESS_REACQUIRE', 'title': 'Currentness'}], 'protocols': protocols}

        mc.register_lpcl_mission(spec(mc.LPCL_REBIND_SOURCE, 'PROJECT=LION_EVOLUSION\n'))
        c = mc.connect(); roles = [('LD%02d' % i, 'OLD' + str(i), 6 if i <= 4 else 5) for i in range(1, 13)]
        for lid, role, n in roles:
            c.execute('INSERT INTO logical_drones VALUES(?,?,?,?,?,?)', (mc.LPCL_REBIND_SOURCE, lid, role, n, n, n))
            for j in range(n):
                c.execute('INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)', (mc.LPCL_REBIND_SOURCE, f'e3-{lid.lower()}-{j}', f'uid-{lid}-{j}', lid, 'Running', 1, 0, f'10.0.{int(lid[2:])}.{j+1}', mc.now()))
        c.execute('UPDATE missions SET state=?,runtime_state=?,materialized=64,ready=64 WHERE mission_id=?', ('RUNNING', 'RUNNING', mc.LPCL_REBIND_SOURCE))
        c.execute('UPDATE mission_process_specs SET authority_state=? WHERE mission_id=?', ('EXPLICIT_USER_ACTIVATION', mc.LPCL_REBIND_SOURCE)); c.commit(); c.close()

        text = 'CONTINUE_EXISTING_EPOCH3_MISSION=TRUE\nCREATE_PARALLEL_COMPETING_EPOCH3_MISSION=FALSE\nREUSE_EXISTING_HEALTHY_MATERIAL_FLEET=ALLOWED_AFTER_EXACT_IDENTITY_AND_MISSION_REBIND\n' + ''.join(f'LD{i:02d}=ROLE_{i:02d}\n' for i in range(1, 13))
        new = spec('EPOCH3-CLOSURE-HYBRID-SAAS-RECOVERY-R1', text)
        mc.register_lpcl_mission(new)
        out = mc.activate_lpcl_mission(new['mission_id'], {'lpcl_digest': new['lpcl_digest'], 'activation_event': 'EXPLICIT_UI_ACTIVATION'})
        self.assertEqual((out['state'], out['materialized'], out['ready']), ('RUNNING', 64, 64))
        self.assertEqual(out['process']['current_phase'], 'CURRENTNESS_REACQUIRE')
        self.assertEqual(out['logical'][0]['role'], 'ROLE_01')
        self.assertEqual(out['control_authority'], 'BOUNDED_LPCL_EXECUTION_ADAPTER')
        self.assertIn('ASSIGNMENT', {x['protocol'] for x in out['protocol_messages']})


if __name__ == '__main__':
    unittest.main()
