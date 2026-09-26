import tempfile
import time
import unittest
from pathlib import Path

from cyber_lion.mission_control import operator_control
from tools.lion_operator_gateway import Runtime


class OperatorPairingOtpTests(unittest.TestCase):
    def runtime(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);root=Path(td.name)
        def secret(name,ch):
            p=root/name;p.write_text(ch*64,encoding='utf-8');return p
        floor=root/'floor.json'
        return Runtime(
            root/'operator.db',
            secret('gateway.key','a'),
            secret('proxy.key','b'),
            secret('panel.key','c'),
            secret('pairing.key','d'),
            floor,
            'http://127.0.0.1:8766',
            bootstrap_primary=True,
        )

    def test_one_time_128_bit_challenge_pairs_and_cannot_replay(self):
        rt=self.runtime()
        challenge=rt.issue_panel_pairing_challenge('c'*64)
        self.assertEqual(len(challenge['challenge_id']),32)
        self.assertEqual(len(challenge['pairing_code']),32)
        self.assertEqual(challenge['attempts_remaining'],3)
        paired=rt.pair_panel('c'*64,challenge['pairing_code'],challenge['challenge_id'])
        self.assertTrue(paired['paired'])
        self.assertEqual(paired['principal_id'],operator_control.PRIMARY_OPERATOR)
        with self.assertRaisesRegex(PermissionError,'expired or invalid'):
            rt.pair_panel('c'*64,challenge['pairing_code'],challenge['challenge_id'])

    def test_wrong_code_consumes_three_attempts(self):
        rt=self.runtime();challenge=rt.issue_panel_pairing_challenge('c'*64)
        for _ in range(2):
            with self.assertRaisesRegex(PermissionError,'challenge denied'):
                rt.pair_panel('c'*64,'0'*32,challenge['challenge_id'])
        with self.assertRaisesRegex(PermissionError,'challenge denied'):
            rt.pair_panel('c'*64,'0'*32,challenge['challenge_id'])
        with self.assertRaisesRegex(PermissionError,'expired or invalid'):
            rt.pair_panel('c'*64,challenge['pairing_code'],challenge['challenge_id'])

    def test_challenge_is_transport_authenticated_and_short_lived(self):
        rt=self.runtime()
        with self.assertRaisesRegex(PermissionError,'panel transport authentication'):
            rt.issue_panel_pairing_challenge('x'*64)
        challenge=rt.issue_panel_pairing_challenge('c'*64)
        rt.pairing_challenges[challenge['challenge_id']]['expires']=time.time()-1
        with self.assertRaisesRegex(PermissionError,'expired or invalid'):
            rt.pair_panel('c'*64,challenge['pairing_code'],challenge['challenge_id'])


if __name__=='__main__':
    unittest.main()
