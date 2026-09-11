from __future__ import annotations

import unittest

from cyber_lion.architecture_projection.process_orchestration import (
    canonical_process_orchestration_projection,
)
from cyber_lion.process_language.canonical_run import compile_canonical_run


BASE = r'''RUN=
LPCL-CROSS-THREAD-R1

PROCESS_LANGUAGE=
LPCL

LPCL_VERSION=
1.1

MISSION_CLASS=
LOGICAL_FLEET_MISSION

MISSION_ID=
lpcl-cross-thread-r1

PRIMARY_GOAL=
RECONSTRUCT_CURRENT_REPOSITORY_STATE

SCOPE_DOMAINS=
repository

SCOPE_RESOURCES=
repo:DonkeyJJLove/ai_platform

WIDENING_ALLOWED=
FALSE

LOGICAL_FLEET_ROLES=
ANALYST

PHASE_0=
REACQUIRE

TRANSITION_CLASS=
INTERNAL

OPERATOR=
REACQUIRE

ROLE=
ANALYST

EVIDENCE_REQUIREMENTS=
evidence:repository

CURRENTNESS_REQUIREMENTS=
currentness:master

AUTHORITY_REQUIREMENTS=

EXPECTED_POSTCONDITIONS=
repository-current

REPLAY_POLICY=
DENY

IDEMPOTENCY_CLASS=
PURE

RETRY_MAX_ATTEMPTS=
0

RETRY_ON_EXHAUSTED=
HANDOFF

LINEAGE=
test:cross-thread

END
'''


class LPCLCrossThreadConformanceTests(unittest.TestCase):
    def test_annotations_do_not_change_compiled_semantics(self):
        variant = BASE.replace(
            "PHASE_0=\nREACQUIRE",
            "PURPOSE=\nHUMAN_READABLE_VARIATION\n\nACTIONS=\nREACQUIRE_MASTER_HEAD\n\nPHASE_0=\nREACQUIRE",
        )
        left = compile_canonical_run(BASE)
        right = compile_canonical_run(variant)
        self.assertEqual(left.process_ir, right.process_ir)
        self.assertEqual(left.fleet_mission_ir, right.fleet_mission_ir)

    def test_process_orchestration_projection_preserves_existing_layer_set(self):
        projection = canonical_process_orchestration_projection()
        self.assertFalse(projection.adds_top_level_layer)
        self.assertEqual(projection.authority_effect, "NONE")
        self.assertEqual(projection.runtime_effect, "NONE")
        self.assertEqual(projection.effect_provider_effect, "NONE")
        self.assertEqual(projection.fleet_mission_classes, ("LOGICAL", "LOCAL", "HYBRID"))

    def test_annotation_cannot_smuggle_action_operator(self):
        variant = BASE.replace(
            "PHASE_0=\nREACQUIRE",
            "ACTIONS=\nEMIT_ACTION_INTENT\nRAW_SHELL\n\nPHASE_0=\nREACQUIRE",
        )
        compiled = compile_canonical_run(variant)
        transition = compiled.process_ir.as_dict()["transitions"][0]
        self.assertEqual(transition["transition_class"], "INTERNAL")
        self.assertEqual(transition["operator"], "REACQUIRE")
        self.assertEqual(compiled.fleet_mission_ir.authority_effect, "NONE")


if __name__ == "__main__":
    unittest.main()
