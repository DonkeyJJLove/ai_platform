from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
RELAY=(ROOT/"tools/lion_secure_mcp_broker_relay.py").read_text(encoding="utf-8")
NODE=(ROOT/"tools/firefox_mediator/mediator.js").read_text(encoding="utf-8")
MISSION=(ROOT/"tools/lion_mission_control_v3.py").read_text(encoding="utf-8")

class SecureMcpBrokerRelayTests(unittest.TestCase):
    def test_secure_mcp_relay_binds_exact_request_to_turn(self):
        self.assertIn('"command_id":"MC-"+rid',RELAY)
        self.assertIn('"broker_request_id":rid',RELAY)
        self.assertIn('"turn_id":turn["turn_id"]',RELAY)
        self.assertIn('"turn_request_hash":turn.get("request_hash")',RELAY)

    def test_wakeup_is_separate_from_secure_mcp_completion(self):
        self.assertIn('wakeup_driver":"FIREFOX_NODE_PROJECT_MANAGER"',RELAY)
        self.assertIn('Use LION-MCP-R2.',RELAY)
        self.assertIn('lion_get_turn',RELAY)
        self.assertIn('lion_complete_turn',RELAY)
        self.assertIn('OPENAI_SECURE_MCP_TUNNEL_TOOL_ROUNDTRIP',RELAY)
        self.assertIn('WAKEUP_TRANSPORT="CHATGPT_FIREFOX_PROJECT_MEDIATED"',RELAY)
        self.assertIn('"transport":WAKEUP_TRANSPORT',RELAY)

    def test_ready_requires_ingress_and_node_driver(self):
        self.assertIn('state="READY" if ingress_ready(a.ingress,token) and ok_driver else "DEGRADED"',RELAY)
        self.assertIn('node-manager-status.json',RELAY)
        self.assertIn('worker_alive',RELAY)
        self.assertIn('mediator.get("state")=="READY"',RELAY)
        self.assertIn('mediator.get("project_verified") is True',RELAY)
        self.assertNotIn('mediator_age<=ttl',RELAY)
        self.assertIn('driver_ready(a.ipc_dir)',RELAY)
        self.assertNotIn('driver_ready(a.ipc)',RELAY)

    def test_node_manager_writes_fresh_status(self):
        self.assertIn('node-manager-status.json',NODE)
        self.assertIn('setInterval(writeManagerStatus, 5000)',NODE)
        self.assertIn('worker_alive: !!child',NODE)

    def test_mission_control_supervises_secure_relay_child(self):
        self.assertIn("def _start_secure_mcp_broker_relay(port):",MISSION)
        self.assertIn("relay=_start_secure_mcp_broker_relay(a.port)",MISSION)
        self.assertIn("secure-mcp-ingress.token",MISSION)
        self.assertIn("secure-mcp-relay",MISSION)

    def test_browser_work_item_does_not_carry_secrets(self):
        start=RELAY.index('work={"schema":"lion.firefox-mediator-work/v2"')
        end=RELAY.index('atomic(Path(ipc)',start)
        block=RELAY[start:end]
        self.assertNotIn('response_token',block)
        self.assertNotIn('mediator-key',block)
        self.assertNotIn('ingress-token',block)

    def test_reconcile_before_new_claim_and_no_blind_retry(self):
        loop=RELAY.index('for sf in sorted(state_dir.glob("saas-*.json"))')
        claim=RELAY.index('if state=="READY":claim_new',loop)
        self.assertLess(loop,claim)
        self.assertIn('if sf.exists():return',RELAY)
        self.assertIn('queue_wakeup(a.ipc_dir',RELAY)
        self.assertIn('wakeup_evidence(a.ipc_dir,rid)',RELAY)
        self.assertIn('SAAS_DISPATCH_PENDING',RELAY)
        self.assertIn('if bs.get("status")!="CLAIMED"',RELAY)
        self.assertIn('/claim","POST",{}',RELAY)
        self.assertIn('BROKER_TERMINAL_',RELAY)
        self.assertIn('(Path(a.ipc_dir)/"inbox"/(rid+".json")).unlink()',RELAY)
        self.assertIn('write_terminal_wakeup_receipt',RELAY)
        self.assertIn('terminal_without_response',RELAY)
        self.assertIn('if isinstance(rec,dict) and rec.get("state") not in FINAL:return',RELAY)

if __name__=="__main__":unittest.main()
