# LPCL migration — v1.0 to v1.1 candidate

```text
STATUS=CANDIDATE_NOT_MERGED
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
```

LPCL v1.1 is an additive authoring-surface and execution-topology evolution over the integrated non-effectful ProcessIR model. Existing MissionSpec, EvolutionaryEpoch, ActionSpec, ActionProposal, PDP, RuntimeAdmission and effect/reconciliation contracts remain canonical in their current domains.

## Migration classes

Three source classes are kept distinct:

```text
LPCL_1_0_STRICT_JSON
VERSIONED_LPCL_1_1_RUN_PHASE
UNVERSIONED_HISTORICAL_RUN
```

They are not silently coerced into one another.

## LPCL 1.0

Existing strict LPCL 1.0 remains parseable by `parse_lpcl` and renders directly from `CanonicalProcessIR`. No bulk rewrite of historical 1.0 artifacts is required.

## Versioned LPCL 1.1

A new canonical authoring path is introduced:

```text
versioned RUN/PHASE text
→ parse_canonical_run
→ CanonicalRunAST
→ compile_canonical_run
→ CanonicalProcessIR
+ FleetMissionIR
```

The resulting ProcessIR is validated by the existing canonical contract. The compiler cannot weaken evidence, currentness, authority, replay or ActionIntent requirements.

## Historical RUN

Historical material remains evidence:

```text
unversioned historical RUN text
→ LegacyRunAdapter
→ classification
→ read-only semantic candidate where non-ambiguous
```

Classifications remain:

- `LOSSLESS_TRANSLATION`
- `LOSSY_BUT_SAFE`
- `AMBIGUOUS`
- `UNREPRESENTABLE`

Numbered PHASE semantics in historical material remain ambiguous to `LegacyRunAdapter`. They do **not** automatically become v1.1. Only an explicitly versioned canonical surface with the required controls is a v1.1 process candidate.

## Migration of RUN/PHASE authoring practice

For new processes, cross-thread authoring moves to the versioned form:

```text
RUN=
...
PROCESS_LANGUAGE=
LPCL
LPCL_VERSION=
1.1
MISSION_CLASS=
LOGICAL_FLEET_MISSION | LOCAL_FLEET_MISSION | HYBRID_FLEET_MISSION
...
PHASE_0=
...
```

Historical descriptive blocks (`ACTIONS`, `REQUIRE`, `VERIFY`, `DENY`, `RECORD`, etc.) may remain annotations, but machine-significant transition meaning must be represented by canonical phase controls. This prevents different threads from assigning different execution meaning to the same prose.

## Fleet mission migration

No existing fleet implementation is silently replaced. `FleetMissionIR` is an inert routing contract:

```text
CanonicalProcessIR
→ FleetMissionIR
→ bounded role routing
```

It carries no grants, credentials, PDP decisions, RuntimeAdmission or effect-provider selection. Existing fleet/swarm state machines remain valid until equivalence or integration is separately demonstrated.

## Architecture and documentation migration

The v1.1 candidate introduces an explicit process-orchestration projection:

```text
Intent
→ LPCL surface
→ ProcessIR
→ FleetMissionIR
→ ActionIntent if required
→ existing authority / runtime / effect chain
```

This projection must be reflected consistently in LPCL documentation, architecture documentation, capability projections and truth carriers. Truth/currentness carriers are updated only after noncarrier implementation and verification are frozen.

## Federation

The central repository registry remains truth-subject-derived. Manual early promotion of generated/currentness carriers is prohibited. Regeneration/reconciliation is downstream of successful candidate verification.

## Existing state machines

No bulk migration is authorized. `EvolutionaryEpochEngine`, MissionSpec, SwarmSpec and other domain state machines remain as-is until equivalence with generic ProcessIR and FleetMissionIR semantics is individually proven.

## Failure rule

Any ambiguous translation remains `AMBIGUOUS` or `UNREPRESENTABLE`; migration never invents missing authority, dependencies, role routing, currentness or transition outcomes.
