from __future__ import annotations

import unittest

from cyber_lion.enterprise.merge_authority_consumption import (
    CallbackConsumptionReadCapability,
    MergeAuthorityConsumptionError,
    MergeAuthorityConsumptionKey,
    MergeAuthorityConsumptionReadCapability,
    MergeAuthorityConsumptionState,
    MergeAuthorityConsumptionWriteCapability,
)

REPO="DonkeyJJLove/ai_platform"; BASE="a"*40; HEAD="b"*40; GD="1"*64; LD="2"*64


class MergeAuthorityConsumptionContractTests(unittest.TestCase):
    def key(self):
        return MergeAuthorityConsumptionKey(REPO,248,BASE,HEAD,"grant",GD,LD,7,"merge").validate()

    def test_read_and_write_capabilities_are_distinct_types(self):
        self.assertIsNot(MergeAuthorityConsumptionReadCapability,MergeAuthorityConsumptionWriteCapability)
        self.assertFalse(hasattr(MergeAuthorityConsumptionReadCapability,"consume_exact"))

    def test_callback_read_capability_exposes_no_consume_method(self):
        cap=CallbackConsumptionReadCapability(lambda **_:{"state":"AVAILABLE","state_version":"1","provenance_id":"p"})
        self.assertFalse(hasattr(cap,"consume_exact")); self.assertFalse(hasattr(cap,"reserve_exact"))

    def test_read_observes_available_without_write(self):
        cap=CallbackConsumptionReadCapability(lambda **_:{"state":"AVAILABLE","state_version":"1","provenance_id":"p"})
        self.assertIs(cap.observe_consumption_exact(self.key()).state,MergeAuthorityConsumptionState.AVAILABLE)

    def test_read_observes_consumed_without_mutation(self):
        calls=[]
        def provider(**kwargs): calls.append(dict(kwargs)); return {"state":"CONSUMED","state_version":"2","provenance_id":"p2"}
        cap=CallbackConsumptionReadCapability(provider); obs=cap.observe_consumption_exact(self.key())
        self.assertIs(obs.state,MergeAuthorityConsumptionState.CONSUMED); self.assertEqual(len(calls),1)

    def test_unknown_state_remains_unknown(self):
        cap=CallbackConsumptionReadCapability(lambda **_:{"state":"UNKNOWN","state_version":"1","provenance_id":"p"})
        self.assertIs(cap.observe_consumption_exact(self.key()).state,MergeAuthorityConsumptionState.UNKNOWN)

    def test_provider_failure_is_unavailable_not_available(self):
        cap=CallbackConsumptionReadCapability(lambda **_:(_ for _ in ()).throw(RuntimeError("down")))
        with self.assertRaises(MergeAuthorityConsumptionError): cap.observe_consumption_exact(self.key())

    def test_malformed_provider_state_fails_closed(self):
        cap=CallbackConsumptionReadCapability(lambda **_:{"state":"NOT_A_STATE","state_version":"1","provenance_id":"p"})
        with self.assertRaises(MergeAuthorityConsumptionError): cap.observe_consumption_exact(self.key())

    def test_exact_key_binds_all_replay_dimensions(self):
        key=self.key(); changed=MergeAuthorityConsumptionKey(REPO,248,BASE,HEAD,"grant",GD,LD,7,"squash").validate()
        self.assertNotEqual(key.binding(),changed.binding())
