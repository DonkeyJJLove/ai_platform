from pathlib import Path
import sqlite3
import unittest

from tools import lion_saas_broker as broker

class ExplicitTransportRoutingTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.row_factory=sqlite3.Row
        self.c.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, schema_id TEXT, applied_at TEXT, source_head TEXT, source_tree TEXT, migration_digest TEXT, note TEXT)')
        self.now_value='2026-09-18T20:30:00Z'
        broker.migrate(self.c,self.now,source_head='a'*40,source_tree='b'*40)

    def tearDown(self):
        self.c.close()

    def now(self):
        return self.now_value

    def hb(self,transport,mediator):
        return broker.record_mediator_heartbeat(self.c,{
            'mediator_id':mediator,'transport':transport,'state':'READY',
            'project_title':'LION_EVOLUSION','chat_title':'TEST','browser':'TEST',
            'authority_effect':'NONE'},self.now)

    def create(self,transport=None,question='q'):
        return broker.create_request(
            self.c,None,question,self.now,scope_type='THREAD',
            thread_id='b'*32,authority_effect='NONE',transport=transport
        )

    def test_explicit_firefox_survives_secure_mcp_heartbeat(self):
        req=self.create(broker.FIREFOX_TRANSPORT)
        self.hb(broker.SECURE_MCP_TRANSPORT,'SECURE')
        saved=broker.request_status(self.c,req['request_id'],self.now)
        self.assertEqual(saved['transport'],broker.FIREFOX_TRANSPORT)
        self.assertEqual(saved['authority_effect'],'NONE')

    def test_explicit_secure_survives_firefox_heartbeat(self):
        req=self.create(broker.SECURE_MCP_TRANSPORT)
        self.hb(broker.FIREFOX_TRANSPORT,'FIREFOX')
        saved=broker.request_status(self.c,req['request_id'],self.now)
        self.assertEqual(saved['transport'],broker.SECURE_MCP_TRANSPORT)

    def test_explicit_sentinelx_survives_other_mediator_heartbeat(self):
        req=self.create(broker.SENTINELX_MCP_TRANSPORT)
        self.hb(broker.SECURE_MCP_TRANSPORT,'SECURE')
        saved=broker.request_status(self.c,req['request_id'],self.now)
        self.assertEqual(saved['transport'],broker.SENTINELX_MCP_TRANSPORT)
        self.assertEqual(broker.SUPPORTED_TRANSPORT_ATTESTATIONS[broker.SENTINELX_MCP_TRANSPORT],broker.SENTINELX_MCP_ATTESTATION_CLASS)

    def test_sentinelx_ready_heartbeat_is_automatic_channel(self):
        self.hb(broker.SENTINELX_MCP_TRANSPORT,'SENTINELX')
        status=broker.bridge_status(self.c,None,self.now)
        self.assertTrue(status['sentinelx_ready'])
        self.assertEqual(status['channel_state'],'SENTINELX_MCP_READY')
        self.assertEqual(status['transport'],broker.SENTINELX_MCP_TRANSPORT)
        self.assertEqual(status['automatic_hop'],'AVAILABLE')

    def test_unpinned_backward_compatibility_can_be_adopted(self):
        req=self.create()
        self.assertEqual(req['transport'],broker.TRANSPORT)
        out=self.hb(broker.FIREFOX_TRANSPORT,'FIREFOX')
        self.assertIn(req['request_id'],out['promoted_request_ids'])
        self.assertEqual(broker.request_status(self.c,req['request_id'],self.now)['transport'],broker.FIREFOX_TRANSPORT)

    def test_invalid_explicit_transport_rejected(self):
        with self.assertRaises(ValueError):
            self.create('NOT_A_TRANSPORT')

    def test_project_handoff_source_pins_firefox(self):
        src=(Path(__file__).resolve().parents[2]/'cyber_lion/app_coordination/saas_handoff_extension.py').read_text(encoding='utf-8')
        self.assertIn('"transport":"CHATGPT_FIREFOX_PROJECT_MEDIATED"',src)

    def test_api_contract_accepts_transport_field(self):
        src=(Path(__file__).resolve().parents[2]/'tools/lion_mission_control_v3.py').read_text(encoding='utf-8')
        self.assertIn("'transport'",src)
        self.assertIn("transport=x.get('transport')",src)

if __name__=='__main__':
    unittest.main()
