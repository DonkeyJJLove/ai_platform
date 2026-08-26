import unittest
from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest,ActionsRunCancelContractError

class ActionsRunCancelContractTests(unittest.TestCase):
    def test_exact_request(self):
        r=ActionsRunCancelRequest("DonkeyJJLove/ai_platform",123,"LION Actions Dispatch Bridge","issue_comment","a"*40,"QUEUE_RECOVERY_ONLY","r1").validate()
        self.assertEqual(len(r.payload_digest()),64)
    def test_wrong_repo_denied(self):
        with self.assertRaises(ActionsRunCancelContractError): ActionsRunCancelRequest("other/repo",1,"w","issue_comment","a"*40,"x","r").validate()
    def test_bad_run_denied(self):
        with self.assertRaises(ActionsRunCancelContractError): ActionsRunCancelRequest("DonkeyJJLove/ai_platform",0,"w","issue_comment","a"*40,"x","r").validate()

if __name__=="__main__": unittest.main()
