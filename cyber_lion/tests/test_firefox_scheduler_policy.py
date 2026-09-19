from pathlib import Path
import hashlib
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
UIA=ROOT/'tools/firefox_mediator/open_session_mediator.ps1'

class FirefoxSchedulerPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=UIA.read_text(encoding='utf-8')

    def _param(self,name):
        m=re.search(r'\[int\]\$'+re.escape(name)+r'\s*=\s*(\d+)',self.text)
        self.assertIsNotNone(m,name)
        return int(m.group(1))

    @staticmethod
    def jitter(seed,lo,hi):
        bucket=int(hashlib.sha256(seed.encode('utf-8')).hexdigest()[:8],16)
        return lo + bucket % ((hi-lo)+1)

    def test_scheduler_has_floor_jitter_and_long_rate_limit_cooldown(self):
        floor=self._param('MinSendIntervalSeconds')
        lo=self._param('JitterMinSeconds')
        hi=self._param('JitterMaxSeconds')
        cooldown=self._param('RateLimitCooldownSeconds')
        self.assertGreaterEqual(floor,30)
        self.assertGreater(hi,lo)
        self.assertGreaterEqual(cooldown,600)

    def test_deterministic_jitter_is_bounded_and_not_constant(self):
        lo=self._param('JitterMinSeconds')
        hi=self._param('JitterMaxSeconds')
        vals=[self.jitter('request-'+str(i),lo,hi) for i in range(32)]
        self.assertTrue(all(lo<=x<=hi for x in vals))
        self.assertGreater(len(set(vals)),8)
        self.assertEqual(vals,[self.jitter('request-'+str(i),lo,hi) for i in range(32)])

    def test_no_fixed_turn_interval_contract(self):
        t=self.text
        self.assertNotIn('TURN_INTERVAL',t)
        self.assertIn('Get-RequiredSendGapSeconds',t)
        self.assertIn('Get-DeterministicJitterSeconds',t)
        self.assertIn("(Get-MissionKey $Work)+'|'",t)

    def test_previous_receipt_is_gate_for_next_real_send(self):
        t=self.text
        self.assertIn('Test-PreviousReceiptReady',t)
        self.assertIn("throw 'PREVIOUS_RECEIPT_REQUIRED'",t)
        self.assertIn("receipt.status -eq 'RESPONDED'",t)
        self.assertIn('receipt.receipt_digest',t)
        self.assertIn('last_completed_request_id',t)

    def test_rate_limit_is_fail_closed(self):
        t=self.text
        self.assertIn('Set-RateLimitBackoff',t)
        self.assertIn('Test-BackoffActive',t)
        self.assertIn("throw 'RATE_LIMITED_NO_RETRY'",t)
        self.assertIn("if(Test-BackoffActive){return}",t)

    def test_idle_and_passive_paths_do_not_send(self):
        t=self.text
        self.assertIn("if(-not $file){return}",t)
        passive=t[t.index('function Test-RateLimitInDocument'):t.index('function Get-WindowText')]
        self.assertNotIn('Send-Prompt',passive)
        self.assertNotIn('Set-Prompt',passive)

    def test_unknown_external_effect_is_never_blindly_retried(self):
        t=self.text
        start=t.index("if($j -and $j.state -eq 'SEND_ATTEMPT')")
        end=t.index("if($j -and $j.state -in @('SEND_CONFIRMED'",start)
        recovery=t[start:end]
        self.assertIn('Set-SendUnknown',recovery)
        self.assertIn('Get-QuestionOccurrenceCount',recovery)
        self.assertNotIn('Send-Prompt',recovery)
        self.assertNotIn('Set-Prompt',recovery)
        self.assertIn("retry_policy='RECONCILE_FIRST_NO_BLIND_RETRY'",t)

    def test_durable_intent_precedes_non_idempotent_send(self):
        t=self.text
        send=t.index('Send-Prompt $prompt $docAll')
        attempt=t.rfind("state='SEND_ATTEMPT'",0,send)
        intent=t.rfind("state='INTENT_DURABLE'",0,attempt)
        confirmed=t.index("state='SEND_CONFIRMED'",send)
        self.assertGreaterEqual(intent,0)
        self.assertLess(intent,attempt)
        self.assertLess(attempt,send)
        self.assertLess(send,confirmed)

if __name__=='__main__':
    unittest.main()
