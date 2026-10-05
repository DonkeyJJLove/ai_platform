from dataclasses import replace
import math
import unittest

from cyber_lion.contracts.panel_projection import (
    ArtifactProjection,
    EvolutionProjection,
    FederationProjection,
    MissionProjection,
    ModelProjection,
    ProjectionError,
    ProjectionHeader,
    RepositoryProjection,
    SwarmProjection,
    TimelineProjection,
    projection_from_mapping,
)


class PanelProjectionTests(unittest.TestCase):
    def header(self, *, currentness="CURRENT", gaps=()):
        return ProjectionHeader.build(
            observed_at="2026-10-05T19:50:00Z",
            source_refs=("mission:1", "repo:ai_platform"),
            source_revision="91dd9db46aa6fa9f7c2284a40bc924723a052cb2",
            projection_version="1.0.0",
            currentness=currentness,
            gaps=gaps,
        )

    def test_all_projection_kinds_are_deterministic_non_effectful_carriers(self):
        types = (
            MissionProjection,
            SwarmProjection,
            ModelProjection,
            FederationProjection,
            RepositoryProjection,
            ArtifactProjection,
            TimelineProjection,
            EvolutionProjection,
        )
        for cls in types:
            with self.subTest(kind=cls.KIND):
                a = cls.build(self.header(), {"state": "READY", "items": [1, 2]})
                b = cls.build(self.header(), {"items": [1, 2], "state": "READY"})
                self.assertEqual(a.projection_digest, b.projection_digest)
                self.assertEqual(a.header.authority_effect, "NONE")
                self.assertEqual(a.to_dict()["kind"], cls.KIND)
                self.assertEqual(projection_from_mapping(a.to_dict()), a)

    def test_projection_digest_detects_payload_or_header_substitution(self):
        item = MissionProjection.build(self.header(), {"mission_id": "M1", "state": "RUNNING"})
        with self.assertRaisesRegex(ProjectionError, "digest"):
            replace(item, payload_json='{"mission_id":"M2","state":"RUNNING"}').validate()
        stale_header = self.header(currentness="STALE", gaps=("worker-status-stale",))
        with self.assertRaisesRegex(ProjectionError, "digest"):
            replace(item, header=stale_header).validate()

    def test_source_refs_and_gaps_are_canonical_sets(self):
        header = ProjectionHeader.build(
            observed_at="2026-10-05T19:50:00Z",
            source_refs=["z", "a"],
            source_revision="rev-1",
            projection_version="1",
            currentness="UNKNOWN",
            gaps=["z-gap", "a-gap"],
        )
        self.assertEqual(header.source_refs, ("a", "z"))
        self.assertEqual(header.gaps, ("a-gap", "z-gap"))
        with self.assertRaises(ProjectionError):
            replace(header, source_refs=("z", "a")).validate()

    def test_observation_unavailable_is_not_offline_and_unknown_is_explicit(self):
        unavailable = SwarmProjection.build(
            self.header(currentness="OBSERVATION_UNAVAILABLE", gaps=("worker-source-unavailable",)),
            {"worker_state": "UNKNOWN"},
        )
        self.assertEqual(unavailable.header.currentness, "OBSERVATION_UNAVAILABLE")
        self.assertEqual(unavailable.payload()["worker_state"], "UNKNOWN")
        with self.assertRaises(ProjectionError):
            ProjectionHeader.build(
                observed_at="2026-10-05T19:50:00Z",
                source_refs=("worker:MD029",),
                source_revision="rev-1",
                projection_version="1",
                currentness="OFFLINE",
            )

    def test_projection_rejects_effect_widening_and_noncanonical_json(self):
        header = self.header()
        with self.assertRaises(ProjectionError):
            replace(header, authority_effect="ALLOW").validate()
        with self.assertRaises(ProjectionError):
            MissionProjection.build(header, {"bad": math.nan})

    def test_mapping_rejects_unknown_fields_and_unknown_kind(self):
        item = ArtifactProjection.build(self.header(), {"artifact_id": "A1"})
        value = item.to_dict()
        value["extra"] = True
        with self.assertRaises(ProjectionError):
            projection_from_mapping(value)
        value = item.to_dict()
        value["kind"] = "EXECUTION_AUTHORITY"
        with self.assertRaises(ProjectionError):
            projection_from_mapping(value)

    def test_payload_is_bounded(self):
        with self.assertRaisesRegex(ProjectionError, "too large"):
            MissionProjection.build(self.header(), {"blob": "x" * 300_000})


if __name__ == "__main__":
    unittest.main()
