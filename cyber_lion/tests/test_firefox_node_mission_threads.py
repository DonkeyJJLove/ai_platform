from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
NODE=ROOT/'tools/firefox_mediator/mediator.js'
UIA=ROOT/'tools/firefox_mediator/open_session_mediator.ps1'
RELAY=ROOT/'tools/lion_firefox_broker_relay.py'
BACKGROUND=ROOT/'tools/firefox_mediator/background_driver.cjs'
EDGE_UIA=ROOT/'tools/firefox_mediator/edge_session_worker.ps1'

class FirefoxNodeMissionThreadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node=NODE.read_text(encoding='utf-8')
        cls.uia=UIA.read_text(encoding='utf-8')
        cls.relay=RELAY.read_text(encoding='utf-8')
        cls.background=BACKGROUND.read_text(encoding='utf-8')
        cls.edge_uia=EDGE_UIA.read_text(encoding='utf-8')

    def test_node_normal_path_is_native_background_and_uia_is_manual_only(self):
        t=self.node
        self.assertIn('lion-node-saas-background-manager',t)
        self.assertIn('background_driver.cjs',t)
        self.assertIn('startBackground()',t)
        self.assertIn('driver_mode:"NODE_BACKGROUND"',t)
        self.assertIn('/control/bootstrap/start',t)
        self.assertIn('operator_action_required:true',t)
        self.assertIn('legacy_normal_open_disabled',t)
        self.assertIn('legacy_uia_worker_disabled',t)
        self.assertNotIn('startWorker();',t)
        self.assertNotIn('lion-firefox-uia-node-manager',t)
        self.assertIn('backgroundGeneration',t)
        self.assertIn('suppressBackgroundRestart',t)
        self.assertIn('scheduleBackgroundRestart',t)
        self.assertIn('taskkill.exe',t)
        self.assertIn('/T',t)
        self.assertIn('/F',t)

    def test_background_driver_owns_single_minimized_edge_bridge(self):
        t=self.background
        self.assertIn('execution_bridge:"MINIMIZED_EDGE_UIA"',t)
        self.assertIn('saas-background-profile-r1',t)
        self.assertIn('--start-minimized',t)
        self.assertIn('--force-renderer-accessibility',t)
        self.assertIn('edge_session_worker.ps1',t)
        self.assertIn('visible_window_count:0',t)
        self.assertIn('driver_mode:"NODE_BACKGROUND"',t)
        self.assertIn('taskkill.exe',t)

    def test_minimized_edge_readiness_accepts_bound_project_conversation(self):
        t=self.edge_uia
        self.assertIn("$projectPrefix=($target -replace '/project$','')",t)
        self.assertIn('$norm -like "$projectPrefix/c/*"',t)
        self.assertIn("'PROJECT_CONVERSATION'",t)
        self.assertIn('Ensure-Minimized',t)
        self.assertIn("window_state='MINIMIZED'",t)
        self.assertIn('visible_window_count=0',t)
        self.assertNotIn('Document -or $doc.Current.IsOffscreen',t)
        self.assertIn("'RECEIPT_CONFIRMED'",t)
        self.assertIn("response_source='BROKER_RECEIPT'",t)
        self.assertIn('$receiptPath=Join-Path $Receipts "$rid.json"',t)
        self.assertIn('function Reconcile-TerminalJournals',t)
        self.assertIn('Note-MissionTurnByKey',t)
        self.assertIn("[string]$j.state -ne 'SEND_CONFIRMED'",t)
        self.assertIn('Reconcile-TerminalJournals',t)

    def test_uia_persists_one_conversation_per_mission_scope(self):
        t=self.uia
        self.assertIn("$MissionThreads = Join-Path $Ipc 'mission-threads'",t)
        self.assertIn("schema='lion.firefox-mediator.mission-thread/v3'",t)
        self.assertIn('Get-MissionKey',t)
        self.assertIn('Bind-MissionConversation',t)
        self.assertIn('active_conversation_url',t)
        self.assertIn('Open-BoundConversationAny',t)
        self.assertIn("openReason=if($rolloverReason)",t)

    def test_rollover_requires_explicit_terminal_reason(self):
        t=self.uia
        self.assertIn('Get-ExplicitTerminalReason',t)
        self.assertIn("reason='BOUND_CHAT_TRANSIENT_UNAVAILABLE_NO_ROLLOVER'",t)
        self.assertIn("Set-RateLimitBackoff 'BOUND_CHAT_RATE_LIMIT_TRANSIENT'",t)
        self.assertNotIn("Close-MissionConversation $work 'BOUND_CHAT_UNAVAILABLE_OR_TERMINAL'",t)

    def test_rate_limit_safe_path_has_backoff_and_send_pacing(self):
        t=self.uia
        self.assertIn('$MinSendIntervalSeconds = 45',t)
        self.assertIn('$JitterMaxSeconds = 135',t)
        self.assertIn('$RateLimitCooldownSeconds = 900',t)
        self.assertIn('Test-RateLimitInDocument',t)
        self.assertIn('Set-RateLimitBackoff',t)
        self.assertIn('Wait-SendBudget',t)
        self.assertIn('RATE_LIMITED_NO_RETRY',t)
        self.assertIn('AUTO_TITLE_ONLY_NO_POST_RESPONSE_NAVIGATION',t)
        self.assertNotIn('Navigate-ToUrl $conversation.Window $ProjectHomeUrl',t)

    def test_idle_loop_does_not_touch_browser(self):
        t=self.uia
        self.assertIn("if(-not $file){return}",t)
        self.assertNotIn("if(-not $file){$null=Ensure-ProjectHome;return}",t)

    def test_unknown_send_recovery_is_reconcile_first_no_blind_resend(self):
        t=self.uia
        self.assertIn("if($j -and $j.state -eq 'SEND_UNKNOWN')",t)
        self.assertIn("reason='SEND_UNKNOWN_RECONCILE_REQUIRED'",t)
        self.assertIn("retry_policy='RECONCILE_FIRST_NO_BLIND_RETRY'",t)
        start=t.index("if($j -and $j.state -eq 'SEND_ATTEMPT')")
        end=t.index("if($j -and $j.state -in @('SEND_CONFIRMED'",start)
        block=t[start:end]
        self.assertIn('Get-QuestionOccurrenceCount',block)
        self.assertIn('Set-SendUnknown',block)
        self.assertNotIn('Send-Prompt',block)

    def test_external_send_is_surrounded_by_durable_intent_attempt_and_confirmation(self):
        t=self.uia
        start=t.index('Wait-SendBudget $work')
        end=t.index('Note-Send $work',start)+len('Note-Send $work')
        block=t[start:end]
        self.assertLess(block.index("state='INTENT_DURABLE'"),block.index("state='SEND_ATTEMPT'"))
        self.assertLess(block.index("state='SEND_ATTEMPT'"),block.index('Send-Prompt $prompt $docAll'))
        self.assertLess(block.index('Send-Prompt $prompt $docAll'),block.index("state='SEND_CONFIRMED'"))
        self.assertIn('before_question_count',block)

    def test_mission_turn_count_is_idempotent_per_request(self):
        t=self.uia
        start=t.index('function Note-MissionTurn')
        end=t.index('function Open-BoundConversation',start)
        block=t[start:end]
        self.assertIn("last_completed_request_id -eq [string]$Work.request_id",block)

    def test_relay_carries_mission_identity_without_session_secret(self):
        t=self.relay
        self.assertIn("'schema':'lion.firefox-mediator-work/v2'",t)
        self.assertIn("'mission_id':row.get('mission_id')",t)
        self.assertIn("'thread_policy':'ONE_CHAT_PER_MISSION_WITH_TERMINAL_ROLLOVER'",t)
        start=t.index("work={'schema':'lion.firefox-mediator-work/v2'")
        end=t.index("atomic_json(inbox/(rid+'.json')",start)
        work=t[start:end]
        self.assertNotIn('response_token',work)
        self.assertNotIn('saas-mediator.key',work)

    def test_worker_filters_automation_firefox_instances_and_avoids_window_fanout(self):
        t=self.uia
        self.assertIn('Test-InteractiveFirefoxWindow',t)
        self.assertIn('--marionette|-headless|-no-remote|rust_mozprofile',t)
        self.assertIn('Find-ProjectTargetWindow',t)
        self.assertIn('TARGET_URL_PRESENT_NOT_READY',t)
        self.assertIn('for($attempt=1;$attempt -le 3;$attempt++)',t)
        self.assertIn('Refresh-Readiness',t)
        self.assertIn('$projectHome=Ensure-ProjectHome',t)
        self.assertIn('$LastReadinessProbe',t)
        self.assertIn('PROJECT_SURFACE_NOT_VERIFIED',t)
        self.assertIn("@('SUPERSEDED','CANCELLED')",t)
        self.assertIn('terminal_without_response',t)
        self.assertIn('Get-FirefoxProcess([int]$ProcessId)',t)
        self.assertNotIn('Get-FirefoxProcess([int]$Pid)',t)

    def test_conversation_bound_recovery_resumes_send_not_response_wait(self):
        t=self.uia
        start=t.index("if($j -and $j.state -eq 'CONVERSATION_BOUND'")
        end=t.index("elseif($j -and $j.conversation_url)",start)
        block=t[start:end]
        self.assertIn('Wait-SendBudget $work',block)
        self.assertIn("state='INTENT_DURABLE'",block)
        self.assertIn("state='SEND_ATTEMPT'",block)
        self.assertIn('Send-Prompt $prompt $docAll',block)
        self.assertIn("state='SEND_CONFIRMED'",block)

    def test_no_browser_credential_export_primitives(self):
        low=(self.node+'\n'+self.uia).lower()
        for forbidden in (
            'cookies.sqlite','logins.json','key4.db','sessionstore.jsonlz4',
            'authorization: bearer','chatgpt session token'
        ):
            self.assertNotIn(forbidden,low)

if __name__=='__main__':
    unittest.main()
