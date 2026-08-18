from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from cyber_lion.startup_agent import MarketEvidenceBook, MarketObservation
from cyber_lion.startup_agent.models import StartupModelError


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)


def obs(oid, *, direction="supports", magnitude=0.8, topic="pain", source="customer-1", days=0):
    return MarketObservation(
        observation_id=oid,
        hypothesis_id="h1",
        source=source,
        source_class="customer",
        observed_at=NOW - timedelta(days=days),
        captured_at=NOW,
        topic=topic,
        signal_kind="pain",
        direction=direction,
        magnitude=magnitude,
        confidence=0.9,
        claim=f"claim-{oid}",
        evidence_ref=f"ref-{oid}",
    )


class MarketIntelligenceTests(unittest.TestCase):
    def test_duplicate_fingerprint_is_not_double_counted(self):
        book = MarketEvidenceBook()
        first = obs("a")
        duplicate = MarketObservation(
            observation_id="b",
            hypothesis_id=first.hypothesis_id,
            source=first.source,
            source_class=first.source_class,
            observed_at=first.observed_at,
            captured_at=first.captured_at,
            topic=first.topic,
            signal_kind=first.signal_kind,
            direction=first.direction,
            magnitude=first.magnitude,
            confidence=first.confidence,
            claim=first.claim,
            evidence_ref=first.evidence_ref,
        )
        self.assertTrue(book.add(first))
        self.assertFalse(book.add(duplicate))
        self.assertEqual(len(book.observations()), 1)

    def test_same_id_cannot_change_observation(self):
        book = MarketEvidenceBook()
        book.add(obs("a"))
        with self.assertRaises(StartupModelError):
            book.add(obs("a", magnitude=0.1))

    def test_contradiction_is_explicit(self):
        book = MarketEvidenceBook()
        book.extend([
            obs("support", direction="supports", source="customer-1"),
            obs("against", direction="contradicts", source="customer-2"),
        ])
        contradictions = book.contradictions("h1")
        self.assertEqual(len(contradictions), 1)
        self.assertEqual(contradictions[0].topic, "pain")

    def test_contradicting_evidence_maps_to_low_signal_strength(self):
        signal = obs("against", direction="contradicts", magnitude=0.9).to_market_signal()
        self.assertAlmostEqual(signal.strength, 0.1)
        self.assertEqual(signal.confidence, 0.9)

    def test_freshness_report_is_time_explicit(self):
        book = MarketEvidenceBook()
        book.extend([obs("new", days=2), obs("old", days=90, source="customer-old")])
        report = book.freshness_report(now=NOW, fresh_days=30)
        self.assertEqual(report["total"], 2.0)
        self.assertEqual(report["fresh"], 1.0)
        self.assertEqual(report["fresh_ratio"], 0.5)

    def test_capture_before_observation_is_rejected(self):
        invalid = MarketObservation(
            "x", "h1", "source", "customer",
            observed_at=NOW,
            captured_at=NOW - timedelta(days=1),
            topic="pain", signal_kind="pain", direction="supports",
            magnitude=0.5, confidence=0.5, claim="x",
        )
        with self.assertRaises(StartupModelError):
            invalid.validate()


if __name__ == "__main__":
    unittest.main()
