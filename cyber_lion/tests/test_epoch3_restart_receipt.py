from __future__ import annotations
import unittest
from unittest.mock import patch
from tools import lion_effect_admission_broker as broker


class Epoch3RestartReceiptTests(unittest.TestCase):
    @staticmethod
    def _snapshot(uids):
        pods=[{"name":f"e3-ld10-worker-{i}","uid":uid,"logical_drone":"ld10","ready":True} for i,uid in enumerate(uids)]
        pods.extend({"name":f"e3-other-{i}","uid":f"other-{i}","logical_drone":"ld01","ready":True} for i in range(59))
        return {"mission_id":broker.E3_ID,"state":"RUNNING","materialized":64,"ready":64,"unique_uid_count":64,"pods":pods}

    def test_restart_wait_rejects_ready_snapshot_while_old_uid_is_still_present(self):
        old="old-uid";first=self._snapshot([old,"b","c","d","e"]);second=self._snapshot(["new-uid","b","c","d","e"])
        with patch.object(broker,"e3_read",side_effect=[first,second]) as read:
            out=broker.e3_wait_restarted_uid(old,timeout=1,poll_interval=0)
        self.assertEqual(read.call_count,2)
        self.assertFalse(any(x.get("uid")==old for x in out["pods"]))
        self.assertEqual(out["ready"],64)
        self.assertEqual(out["unique_uid_count"],64)

    def test_restart_wait_times_out_fail_closed_instead_of_false_success(self):
        old="old-uid";stale=self._snapshot([old,"b","c","d","e"])
        with patch.object(broker,"e3_read",return_value=stale):
            with self.assertRaisesRegex(broker.Deny,"E3_RESTART_REPLACEMENT_TIMEOUT"):
                broker.e3_wait_restarted_uid(old,timeout=0.001,poll_interval=0)


if __name__=='__main__': unittest.main()
