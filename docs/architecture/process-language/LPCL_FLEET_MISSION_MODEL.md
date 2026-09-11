# LPCL Fleet Mission Model — v1.1 candidate

```text
STATUS=CANDIDATE_NOT_MERGED
ARCHITECTURE_EPOCH=1.4
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
```

## Purpose

`FleetMissionIR` binds a compiled LPCL process to an execution topology without granting authority. It complements `CanonicalProcessIR`; it does not replace MissionSpec, SwarmSpec, ActionSpec, PDP, RuntimeAdmission or effect providers.

```text
CanonicalProcessIR
→ FleetMissionIR
→ bounded role routing
→ INTERNAL transition
   OR
   ACTION_REQUIRED → ActionIntentCandidate
→ existing Action/PDP/RuntimeAdmission path
```

## Mission classes

```text
LOGICAL
LOCAL
HYBRID
```

`LOGICAL` contains only logical roles. `LOCAL` contains only local/material execution roles. `HYBRID` contains both and must route at least one transition through each execution domain.

## Role identity

A role is a bounded process execution identity. Logical roles may be implemented sequentially by one model runtime, but role identity and evidence lineage remain distinct. A local role represents a material execution position and must be rebound to exact runtime identity by the existing downstream runtime mechanisms before an effect can occur.

`FleetMissionIR` stores no credentials, grants, PDP decisions, RuntimeAdmission objects or raw execution provider selection.

## Routing

Routing maps canonical ProcessIR transition IDs to declared role IDs. For the canonical RUN/PHASE surface the mapping is deterministic:

```text
PHASE_0 → phase-0 → ROLE declared in PHASE_0
PHASE_1 → phase-1 → ROLE declared in PHASE_1
...
```

`ACTION_REQUIRED` transitions must route to a LOCAL role. A LOGICAL-only mission therefore cannot compile a material action transition.

## Separation

`ROLE_SEPARATION=ROLE_A!=ROLE_B` becomes symmetric logical independence metadata. It prevents silent identity collapse in the mission model but does not by itself prove physical or process isolation. Claims requiring physical independence still need independent runtime evidence.

## Authority invariant

```text
FLEET_MISSION_IR.authority_effect=NONE
FLEET_MISSION_IR.runtime_effect=NONE
FLEET_MISSION_IR.effect_provider_effect=NONE
```

This invariant is validated by the contract. Any future attempt to encode an authority grant or effect provider into FleetMissionIR is a schema violation rather than a new execution path.

## Existing fleet policy relationship

The model preserves the restrict-only ordering already used by LION fleet governance:

```text
child ≤ explicit external grant
executor ≤ mission
mission ≤ fleet envelope
budget ≤ granted effect envelope
```

Fleet routing can restrict who may attempt a transition. It cannot enlarge the downstream authority envelope.
