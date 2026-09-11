# LPCL v1.1 design-freeze receipt

```text
STATUS=CANDIDATE_DESIGN_FROZEN_FOR_IMPLEMENTATION
BASE_REPOSITORY=DonkeyJJLove/ai_platform
BASE_BRANCH=master
BASE_HEAD=70929bb895726c0b4a552295e595e373191b0d2b
BASE_TREE=0c463f98122145a1a39287240136d1a824a8038c
WORK_BRANCH=architecture/lpcl-canonical-interpretation-r1
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
MERGE_AUTHORITY=NONE
```

This receipt records the semantic design used by the LPCL v1.1 candidate. Candidate HEAD is intentionally not embedded because this document itself is part of the noncarrier mutation set; exact candidate identity is obtained from Git and frozen only after verification.

## Frozen decisions

```text
CANONICAL_HUMAN_SURFACE=VERSIONED_RUN_PHASE_KEY_VALUE
MACHINE_SEMANTICS=CANONICAL_PROCESS_IR
EXECUTION_TOPOLOGY=FLEET_MISSION_IR
FLEET_CLASSES=LOGICAL_LOCAL_HYBRID
ACTION_REQUIRED_OPERATOR=EMIT_ACTION_INTENT
ACTION_REQUIRED_EXECUTION_DOMAIN=LOCAL
FLEET_AUTHORITY_EFFECT=NONE
FLEET_RUNTIME_EFFECT=NONE
FLEET_EFFECT_PROVIDER_EFFECT=NONE
LEGACY_UNVERSIONED_RUN=DATA_ONLY
LPCL_1_0_STRICT_JSON=EXPLICIT_COMPATIBILITY_SURFACE
TOP_LEVEL_ARCHITECTURE_LAYER_COUNT=UNCHANGED_15
PROCESS_ORCHESTRATION=EXPLICIT_CROSS_LAYER_PROJECTION
CARRIER_POLICY=CARRIER_LAST
```

## Canonical interpretation boundary

```text
process source
→ interpret_process_source
   ├── LPCL 1.0 strict → CanonicalProcessIR compatibility candidate
   ├── LPCL 1.1 versioned RUN/PHASE → CanonicalProcessIR + FleetMissionIR
   └── unversioned historical RUN → data-only LegacyRun classification
```

No branch of this interpreter creates authority or execution.

## v1.1 conformance profile

A canonical v1.1 process candidate must explicitly provide `TERMINATION` and `LINEAGE`. `TERMINATION` is currently frozen to `COMPLETE_ON_DONE`. Any declared `AUTHORITY_EFFECT`, `RUNTIME_EFFECT`, `EXECUTION_EFFECT` or `EFFECT_PROVIDER_EFFECT` must be `NONE`.

## Counterexample incorporated during materialization

The first compiler candidate allowed a surface to compile without the cross-thread standard's required `TERMINATION` and `LINEAGE` declarations. The implementation was therefore not treated as verified. The unified interpretation boundary was tightened so a versioned v1.1 source lacking those controls fails closed. This receipt includes that correction in the frozen candidate semantics.

## Non-goals

The candidate does not replace the PDP, RuntimeAdmission, effect providers, Action IR, existing specialized mission/swarm state machines or physical fleet attestation. Logical role separation is not proof of physical independence.
