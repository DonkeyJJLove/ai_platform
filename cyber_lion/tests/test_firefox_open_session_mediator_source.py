from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'tools/firefox_mediator/open_session_mediator.ps1'

class FirefoxOpenSessionMediatorSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=SOURCE.read_text(encoding='utf-8')

    def test_existing_authenticated_firefox_project_identity_is_explicit(self):
        t=self.text
        self.assertIn("LION_FIREFOX_OPEN_SESSION_MEDIATOR_R2",t)
        self.assertIn("CHATGPT_FIREFOX_PROJECT_MEDIATED",t)
        self.assertIn("LION_EVOLUSION",t)
        self.assertIn("ONE_CHAT_PER_MISSION_WITH_TERMINAL_ROLLOVER",t)
        self.assertIn("new_thread_per_request=$false",t)
        self.assertIn("EXISTING_AUTHENTICATED_FIREFOX",t)

    def test_send_attempt_recovery_never_blindly_resends(self):
        t=self.text
        self.assertIn("function Find-ConversationLink",t)
        self.assertIn("function Open-ConversationLink",t)
        self.assertIn("recovered_after_send=$true",t)
        start=t.index("if($j -and $j.state -eq 'SEND_ATTEMPT')")
        end=t.index("if($j -and $j.state -in @('SEND_CONFIRMED'",start)
        recovery=t[start:end]
        self.assertIn("Get-QuestionOccurrenceCount",recovery)
        self.assertIn("Set-SendUnknown",recovery)
        self.assertIn("Wait-NewConversation",recovery)
        self.assertNotIn("Send-Prompt",recovery)
        self.assertNotIn("Set-Prompt",recovery)
        self.assertIn("RECONCILE_FIRST_NO_BLIND_RETRY",t)

    def test_new_send_snapshots_project_chats_before_send(self):
        t=self.text
        i=t.index("$beforeChats=Get-ProjectChatSnapshot")
        j=t.index("Send-Prompt",i)
        k=t.index("Wait-NewConversation",j)
        self.assertLess(i,j)
        self.assertIn("$beforeChats",t[k:k+300])

    def test_no_browser_credential_export_primitives(self):
        low=self.text.lower()
        for forbidden in ('cookies.sqlite','logins.json','key4.db','sessionstore.jsonlz4','authorization: bearer','chatgpt session token'):
            self.assertNotIn(forbidden,low)

if __name__=='__main__': unittest.main()
