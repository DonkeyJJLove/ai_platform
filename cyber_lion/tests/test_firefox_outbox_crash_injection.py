from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
UIA=(ROOT/'tools/firefox_mediator/open_session_mediator.ps1').read_text(encoding='utf-8')

class FirefoxOutboxCrashInjectionTests(unittest.TestCase):
    def recovery_block(self):
        start=UIA.index("if($j -and $j.state -eq 'SEND_ATTEMPT')")
        end=UIA.index("if($j -and $j.state -in @('SEND_CONFIRMED'",start)
        return UIA[start:end]

    def first_send_block(self):
        start=UIA.index('Wait-SendBudget $work')
        end=UIA.index('Note-Send $work',start)+len('Note-Send $work')
        return UIA[start:end]

    def test_crash_after_intent_before_attempt_is_pre_effect_and_reenterable(self):
        start=UIA.index("if($j -and $j.state -eq 'INTENT_DURABLE')")
        end=UIA.index("if($j -and $j.state -eq 'SEND_ATTEMPT')",start)
        block=UIA[start:end]
        self.assertIn('$j=$null',block)
        send=self.first_send_block()
        self.assertLess(send.index("state='INTENT_DURABLE'"),send.index("state='SEND_ATTEMPT'"))
        self.assertLess(send.index("state='SEND_ATTEMPT'"),send.index('Send-Prompt $prompt $docAll'))

    def test_crash_after_attempt_before_confirmation_never_resends(self):
        block=self.recovery_block()
        self.assertNotIn('Send-Prompt',block)
        self.assertNotIn('Set-Prompt',block)
        self.assertIn('Get-QuestionOccurrenceCount',block)
        self.assertIn("Set-SendUnknown $jpath $j 'ATTEMPT_EFFECT_NOT_PROVABLE_IN_BOUND_CONVERSATION'",block)
        self.assertIn("Set-SendUnknown $jpath $j 'ATTEMPT_NEW_CONVERSATION_NOT_PROVABLE'",block)
        self.assertIn("$confirmed.state='SEND_CONFIRMED'",block)

    def test_persisted_unknown_is_terminal_for_automatic_retry(self):
        start=UIA.index("if($j -and $j.state -eq 'SEND_UNKNOWN')")
        end=UIA.index("if($j -and $j.state -eq 'INTENT_DURABLE')",start)
        block=UIA[start:end]
        self.assertIn('Set-SendUnknown',block)
        self.assertIn('return',block)
        self.assertNotIn('Send-Prompt',block)
        self.assertNotIn('Set-Prompt',block)

    def test_confirmed_and_response_reconciled_recovery_do_not_resend(self):
        start=UIA.index("if($j -and $j.state -in @('SEND_CONFIRMED','RESPONSE_RECONCILED'))")
        end=UIA.index("elseif($j -and $j.conversation_url)",start)
        block=UIA[start:end]
        self.assertNotIn('Send-Prompt',block)
        self.assertNotIn('Set-Prompt',block)
        self.assertIn('RECOVERED_AFTER_CONFIRMED_SEND',block)

    def test_state_machine_has_required_durable_order(self):
        send=self.first_send_block()
        order=[
            send.index("state='INTENT_DURABLE'"),
            send.index("state='SEND_ATTEMPT'"),
            send.index('Send-Prompt $prompt $docAll'),
            send.index("state='SEND_CONFIRMED'"),
        ]
        self.assertEqual(order,sorted(order))
        self.assertIn("retry_policy='RECONCILE_FIRST_NO_BLIND_RETRY'",UIA)
        self.assertIn("state='RESPONSE_RECONCILED'",UIA)

if __name__=='__main__':
    unittest.main()
