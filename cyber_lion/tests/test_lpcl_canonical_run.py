from __future__ import annotations

import unittest

from cyber_lion.process_language.canonical_run import CanonicalRunError, compile_canonical_run


HYBRID_RUN = r'''RUN=
LPCL-CANONICAL-SMOKE-R1

PROCESS_LANGUAGE=
LPCL

LPCL_VERSION=
1.1

MISSION_CLASS=
HYBRID_FLEET_MISSION

MISSION_ID=
lpcl-smoke-r1

PRIMARY_GOAL=
REACQUIRE_CURRENT_STATE
MATERIALIZE_ONE_BOUNDED_CANDIDATE

SCOPE_DOMAINS=
repository

SCOPE_RESOURCES=
repo:DonkeyJJLove/ai_platform

WIDENING_ALLOWED=
FALSE

LOGICAL_FLEET_ROLES=
ANALYST

LOCAL_FLEET_ROLES=
MATERIALIZER
OBSERVER

ROLE_SEPARATION=
MATERIALIZER!=OBSERVER

PHASE_0=
LIVE_STATE_REACQUISITION

TRANSITION_CLASS=
INTERNAL

OPERATOR=
REACQUIRE

ROLE=
ANALYST

EVIDENCE_REQUIREMENTS=
evidence:live-master

CURRENTNESS_REQUIREMENTS=
currentness:master

AUTHORITY_REQUIREMENTS=

EXPECTED_POSTCONDITIONS=
master-identity-bound

REPLAY_POLICY=
DENY

IDEMPOTENCY_CLASS=
PURE

RETRY_MAX_ATTEMPTS=
0

RETRY_ON_EXHAUSTED=
HANDOFF

PHASE_1=
CREATE_BOUNDED_CANDIDATE

TRANSITION_CLASS=
ACTION_REQUIRED

OPERATOR=
EMIT_ACTION_INTENT

ROLE=
MATERIALIZER

EVIDENCE_REQUIREMENTS=
evidence:design-freeze

CURRENTNESS_REQUIREMENTS=
currentness:master

AUTHORITY_REQUIREMENTS=
authority-context:candidate-write

EXPECTED_POSTCONDITIONS=
candidate-created

WRITE_SCOPES=
candidate:lpcl-smoke-r1

REPLAY_POLICY=
DENY

IDEMPOTENCY_CLASS=
IDEMPOTENT

RETRY_MAX_ATTEMPTS=
0

RETRY_ON_EXHAUSTED=
HANDOFF

LINEAGE=
test:lpcl-canonical-run

END
'''


class CanonicalRunSurfaceTests(unittest.TestCase):
    def test_hybrid_surface_compiles_to_process_and_fleet_ir(self):
        compiled = compile_canonical_run(HYBRID_RUN)
        self.assertEqual(compiled.process_ir.as_dict()["process_id"], "LPCL-CANONICAL-SMOKE-R1")
        self.assertEqual(compiled.fleet_mission_ir.fleet_class, "HYBRID")
        self.assertEqual(
            dict(compiled.fleet_mission_ir.routing),
            {"phase-0": "ANALYST", "phase-1": "MATERIALIZER"},
        )
        self.assertEqual(compiled.fleet_mission_ir.authority_effect, "NONE")
        self.assertEqual(compiled.fleet_mission_ir.runtime_effect, "NONE")

    def test_end_requires_full_input_consumption(self):
        for suffix in ("END\n", "UNKNOWN_FIELD=ignored\nEND\n", HYBRID_RUN):
            with self.subTest(suffix=suffix[:30]):
                with self.assertRaises(CanonicalRunError):
                    compile_canonical_run(HYBRID_RUN + suffix)

    def test_comments_after_end_preserve_semantics(self):
        original = compile_canonical_run(HYBRID_RUN)
        commented = compile_canonical_run(HYBRID_RUN + "\n# trailing comment\n")
        self.assertEqual(original.process_ir.as_dict(), commented.process_ir.as_dict())

    def test_action_required_must_route_to_local_role(self):
        broken = HYBRID_RUN.replace("ROLE=\nMATERIALIZER", "ROLE=\nANALYST", 1)
        with self.assertRaisesRegex(CanonicalRunError, "LOCAL role"):
            compile_canonical_run(broken)

    def test_logical_only_mission_cannot_contain_action_required_phase(self):
        broken = HYBRID_RUN.replace("HYBRID_FLEET_MISSION", "LOGICAL_FLEET_MISSION")
        broken = broken.replace("LOCAL_FLEET_ROLES=\nMATERIALIZER\nOBSERVER\n", "")
        broken = broken.replace("ROLE_SEPARATION=\nMATERIALIZER!=OBSERVER\n", "")
        with self.assertRaises(CanonicalRunError):
            compile_canonical_run(broken)

    def test_unversioned_run_is_not_canonical_surface(self):
        broken = HYBRID_RUN.replace("LPCL_VERSION=\n1.1\n", "")
        with self.assertRaisesRegex(CanonicalRunError, "LPCL_VERSION"):
            compile_canonical_run(broken)

    def test_unknown_control_field_fails_closed(self):
        broken = HYBRID_RUN.replace("TRANSITION_CLASS=", "TRANSITION_CLAS=")
        with self.assertRaises(CanonicalRunError):
            compile_canonical_run(broken)


if __name__ == "__main__":
    unittest.main()
