# LPCL v1 — LION Process Contract Language

```text
STATUS=V1_0_INTEGRATED_NON_EFFECTFUL_PLUS_V1_1_SURFACE_CANDIDATE
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
V1_1_MERGE_STATE=NOT_MERGED
```

LPCL makes process orchestration above the existing LION Action plane explicit. `CanonicalProcessIR` remains the normative deterministic process contract. The v1.1 candidate adds a canonical human/model authoring surface and a separate non-authoritative fleet-mission routing contract; it does not create a second policy, authority, runtime-admission or execution plane.

## Architecture decision

The v1.1 candidate makes LPCL an explicit **process-orchestration plane** in the architecture projection without changing the ownership of the existing Action, PDP, RuntimeAdmission or effect planes. This is a semantic/documentation placement and a typed contract path, not a new authority source.

```text
Intent / Goal / World State
        ↓
LPCL canonical authoring surface
        ↓
CanonicalRunAST
        ↓
CanonicalProcessIR
        ↓
FleetMissionIR
        ↓
bounded role routing
        ↓
TransitionSelector / process semantics
        ↓
Legal next transition
        ├── INTERNAL
        └── ACTION_REQUIRED
                 ↓
          ActionIntentCandidate
                 ↓
          EXISTING ACTION PLANE
                 ↓
      ActionSpec / CanonicalActionIR
                 ↓
           ActionProposal
                 ↓
            canonical PDP
                 ↓
         RuntimeAdmission
                 ↓
            effect provider
                 ↓
               Effect
                 ↓
     independent observation
                 ↓
       runtime reconciliation
                 ↓
     ProcessTransitionOutcome
                 ↓
           ProcessState
```

The process/fleet layer does not encode executable paths, argv, shell semantics, network policy, filesystem allowlists, PDP decisions, runtime-admission objects, credentials, grants or effect-provider selection.

## Core invariant

```text
LPCL_SURFACE
!= LPCL_AST
!= CANONICAL_PROCESS_IR
!= FLEET_MISSION_IR
!= ACTION_INTENT
!= AUTHORITY_DECISION
!= RUNTIME_ADMISSION
!= EFFECT
!= OBSERVED_EFFECT
!= RECONCILED_CLOSURE
```

A process transition binds source state, trigger, dependencies, guards, evidence requirements, currentness requirements, authority requirements, a typed non-effectful operator, postconditions, outcomes and retry/replay/idempotency semantics.

```text
PASS != CURRENT
PASS != AUTHORIZED
PASS != ADMITTED
PASS != EFFECT_OCCURRED
PASS != OBSERVED
PASS != RECONCILED
```

`UNKNOWN` remains first class.

## Two explicitly versioned surfaces

### LPCL 1.0

The existing strict surface remains supported:

```text
LPCL 1.0
PROCESS <RFC8259 JSON>
MISSION <RFC8259 JSON>
...
END
```

It parses directly to `CanonicalProcessIR` and remains useful as a strict machine-oriented compatibility surface.

### LPCL 1.1 candidate

The candidate human/model authoring surface uses the historical LION key/value form:

```text
RUN=
<process-id>

PROCESS_LANGUAGE=
LPCL

LPCL_VERSION=
1.1

MISSION_CLASS=
HYBRID_FLEET_MISSION

PHASE_0=
...
```

The parser produces `CanonicalRunAST`; compilation produces the existing `CanonicalProcessIR` plus `FleetMissionIR`. Domain-specific blocks such as `PURPOSE`, `ACTIONS`, `VERIFY`, `DENY` or `RECORD` are annotations. Typed transition semantics must be expressed with canonical phase controls and cannot be overridden by prose.

## Fleet mission semantics

Every canonical v1.1 executable process declares exactly one of:

```text
LOGICAL_FLEET_MISSION
LOCAL_FLEET_MISSION
HYBRID_FLEET_MISSION
```

Fleet mission means execution topology and bounded role routing, not authority. Logical roles may be virtual or sequentially realized by one model runtime while preserving role identity and evidence lineage. `ACTION_REQUIRED` phases must route to a LOCAL role and may only emit `ActionIntentCandidate` through the existing Process→Action boundary.

## CONTINUE

`CONTINUE` is selection, not execution.

```text
eligible =
declared transitions
∩ source-state match
∩ dependencies
∩ guards
∩ evidence
∩ currentness
∩ process scope

CONTINUE =
first legal unfinished transition
under the declared SchedulingPolicy
```

An authority-context reference can make a transition eligible for handoff to the Action plane, but is not proof of a valid downstream grant.

## Historical RUN

The legacy rule is refined, not reversed:

```text
UNVERSIONED_HISTORICAL_RUN=DATA_ONLY
UNPARSED_RUN=DATA_ONLY
INVALID_CANONICAL_RUN=DATA_ONLY
VALID_VERSIONED_LPCL_1_1_RUN=PROCESS_CANDIDATE
PROCESS_CANDIDATE!=AUTHORITY
PROCESS_CANDIDATE!=RUNTIME_ADMISSION
PROCESS_CANDIDATE!=EFFECT
```

`LegacyRunAdapter` remains read-only and never turns ambiguous historical material into execution or authority. The new v1.1 surface is explicitly versioned and must pass canonical compilation.

## Existing domain state machines

LPCL does not silently replace `EvolutionaryEpochEngine`, MissionSpec, SwarmSpec, builder lifecycle or runtime admission. Existing domain state machines remain specialized unless equivalence with generic ProcessIR/FleetMissionIR semantics is separately demonstrated.

## Normative candidate references

- `docs/architecture/process-language/LPCL_LANGUAGE_CONSTITUTION.md`
- `docs/architecture/process-language/LPCL_CROSS_THREAD_GENERATION_STANDARD.md`
- `docs/architecture/process-language/LPCL_FLEET_MISSION_MODEL.md`
- `cyber_lion/process_language/lpcl_run_1_1.ebnf`

## Non-goals

LPCL cannot mint authority, evaluate a PDP, construct RuntimeAdmission, select an EffectProvider, execute raw shell, merge/deploy directly, self-certify effects or treat a receipt as reconciled closure. The v1.1 candidate cannot authorize its own merge or promote itself to AS-IS before independent repository reconciliation.
