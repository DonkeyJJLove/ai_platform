import unittest
from cyber_lion.adapters.sbom import SBOMAdapterError, adapt_sbom_event

BASE={
    "@timestamp":"2026-01-25T19:13:49.574Z",
    "event_type":"sbom",
    "aid":{"app_id":"sbom","owner_team":"K82M","env":"lab","vcs_ref":"local","app_version":"0.0.0","repo":"DonkeyJJLove/sbom"},
    "msg":"hello",
    "payload":{"x":1},
}

class SBOMAdapterTests(unittest.TestCase):
    def test_preserves_legacy_event(self):
        out=adapt_sbom_event(BASE,correlation_id="cycle:1")
        self.assertEqual(out.payload["compat"]["sbom_event"],BASE)
        self.assertEqual(out.entity["compat"]["aid"],BASE["aid"])
    def test_delta_maps_to_delta_detected(self):
        event={**BASE,"event_type":"delta"}
        self.assertEqual(adapt_sbom_event(event,correlation_id="cycle:1").event_type,"DeltaDetected")
    def test_legacy_gate_is_not_promoted_to_authority(self):
        event={**BASE,"event_type":"gate","payload":{"result":"allow"}}
        out=adapt_sbom_event(event,correlation_id="cycle:1")
        self.assertEqual(out.event_type,"ObservationCreated")
        self.assertIsNone(out.authority.gate_event_id)
        self.assertEqual(out.payload["authority_interpretation"],"none")
    def test_missing_correlation_fails_closed(self):
        with self.assertRaises(SBOMAdapterError): adapt_sbom_event(BASE,correlation_id="")
    def test_event_id_is_deterministic_for_same_input(self):
        a=adapt_sbom_event(BASE,correlation_id="cycle:1")
        b=adapt_sbom_event(BASE,correlation_id="cycle:1")
        self.assertEqual(a.event_id,b.event_id)

if __name__=="__main__": unittest.main()
