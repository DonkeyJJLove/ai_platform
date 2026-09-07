# LPCL v1 — LION Process Contract Language candidate

```text
STATUS=CANDIDATE_NOT_INTEGRATED
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
RESEARCH_BASE=67a4f8243aa6805e47035e572bd458f73fd0b358
RESEARCH_BASE_TREE=4f6fbc481c8df8f7e1fd75f04188207a1c6fbcf5
```

LPCL makes the process *above* the existing LION Action plane explicit. It is a
non-effectful process-contract language and canonical IR, not a second policy,
authority, runtime-admission or execution plane.

## Architecture decision

No new top-level architecture layer is required for v1. LPCL is a first-class
contract family spanning the existing `EVOLUTIONARY_EPOCH` and
`GOVERNED_SELF_IMPLEMENTATION` concerns.

The federation roles remain split:

- `DonkeyJJLove/chunk-chunk` is the formal/research semantic reference for
  process-state, process-transition, transition microcode and trajectory
  diagnostics. This role grants no runtime authority.
- `DonkeyJJLove/ai_platform` owns the canonical LION integration contract:
  `ProcessContract`/`CanonicalProcessIR`, fail-closed validation, transition
  selection, the Process→Action boundary and the reconciliation feedback
  boundary.
- `DonkeyJJLove/writeups` remains research/history evidence.

This avoids turning both repositories into silent owners of the same executable
contract.

## Boundary

```text
Goal / Mission / World State
        ↓
ProcessContract
        ↓
LPCL surface
        ↓
CanonicalProcessIR
        ↓
Process semantic validator
        ↓
TransitionSelector
        ↓
Legal next transition
        ├── internal process transition
        └── ActionIntentCandidate
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

The process layer does not encode executable paths, argv, shell semantics,
network policy, filesystem allowlists, PDP decisions, runtime admission objects
or effect-provider selection.

## Core semantic invariant

A process transition is a guarded transition contract. It binds source state,
trigger, dependencies, guards, evidence requirements, currentness requirements,
authority *requirements*, a typed non-effectful process operator, expected
postconditions, outcome mapping and retry/replay/idempotency policy.

State dimensions are not implicitly coercible:

```text
PASS != CURRENT
PASS != AUTHORIZED
PASS != ADMITTED
PASS != EFFECT_OCCURRED
PASS != OBSERVED
PASS != RECONCILED
```

`UNKNOWN` remains a first-class result.

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

An authority-context reference can make a transition eligible for handoff to the
Action plane, but it is not proof of a valid downstream grant. The Action/PDP/
RuntimeAdmission chain revalidates consequential authority independently.

## Canonical representation

```text
LPCL text
!=
ProcessAST
!=
CanonicalProcessIR
```

v1 uses strict LPCL statements carrying RFC8259 JSON values. The parser converts
them into the canonical Process IR. Duplicate statements, duplicate JSON keys,
unknown fields and noncanonical ProcessIR semantics fail closed.

The ProcessIR digest uses its own `LION/PROCESS-IR/1` domain and never reuses the
Action IR digest domain.

## Historical RUN

Historical `RUN` material remains evidence. `LegacyRunAdapter` only extracts a
candidate semantic representation. Procedural `MODE=...THEN...` or numbered
PHASE semantics are classified `AMBIGUOUS` until dependencies are reconstructed.
The adapter has no execution path.

## Existing domain state machines

LPCL does not replace `EvolutionaryEpochEngine`, MissionSpec, SwarmSpec, builder
lifecycle or runtime admission. Domain state machines may later consume generic
ProcessIR semantics where equivalence is demonstrated; otherwise they remain
specialized state machines.

## Non-goals

LPCL cannot mint authority, evaluate a PDP, construct RuntimeAdmission, select an
EffectProvider, execute raw shell, merge/deploy directly, self-certify effects or
treat a receipt as reconciled closure.
