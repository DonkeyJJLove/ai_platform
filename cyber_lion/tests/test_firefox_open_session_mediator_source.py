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
        self.assertIn("NEW_THREAD_PER_REQUEST",t)
        self.assertIn("EXISTING_AUTHENTICATED_FIREFOX",t)

    def test_send_triggered_recovery_never_resends(self):
        t=self.text
        self.assertIn("function Find-ConversationLink",t)
        self.assertIn("function Open-ConversationLink",t)
        self.assertIn("recovered_after_send=$true",t)
        recovery=t.index("elseif($j -and $j.state -in @('SEND_TRIGGERED','USER_MESSAGE_OBSERVED','ASSISTANT_MESSAGE_OBSERVED'))")
        normal=t.index("} else {", recovery)
        recovery_block=t[recovery:normal]
        self.assertIn("Wait-NewConversation",recovery_block)
        self.assertNotIn("Send-Prompt",recovery_block)

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
