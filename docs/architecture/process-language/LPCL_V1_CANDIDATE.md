# LPCL v1 — kandydat LION Process Contract Language

```text
STATUS=CANDIDATE_NOT_INTEGRATED
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
RESEARCH_BASE=67a4f8243aa6805e47035e572bd458f73fd0b358
RESEARCH_BASE_TREE=4f6fbc481c8df8f7e1fd75f04188207a1c6fbcf5
```

LPCL jawnie opisuje proces *nad* istniejącym LION Action plane. Jest non-effectful process-contract language oraz canonical IR, a nie drugim policy, authority, runtime-admission ani execution plane.

Powyższy `STATUS` i `RESEARCH_BASE` są historycznym identity kandydata. Nie należy ich przepisywać na bieżący `master`; późniejsza integracja musi być wykazywana przez osobne exact Git/code/test evidence.

## Decyzja architektoniczna

Dla v1 nie jest wymagana nowa top-level architecture layer. LPCL jest first-class contract family przecinającą istniejące concerns `EVOLUTIONARY_EPOCH` i `GOVERNED_SELF_IMPLEMENTATION`.

Role federacji pozostają rozdzielone:

- `DonkeyJJLove/chunk-chunk` jest formalnym/badawczym semantic reference dla process-state, process-transition, transition microcode i trajectory diagnostics. Ta rola nie nadaje runtime authority.
- `DonkeyJJLove/ai_platform` posiada canonical LION integration contract: `ProcessContract`/`CanonicalProcessIR`, fail-closed validation, transition selection, granicę Process→Action i reconciliation feedback boundary.
- `DonkeyJJLove/writeups` pozostaje research/history evidence.

Dzięki temu dwa repozytoria nie stają się po cichu współwłaścicielami tego samego executable contract.

## Granica

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

Process layer nie koduje executable paths, argv, shell semantics, network policy, filesystem allowlists, decyzji PDP, obiektów runtime admission ani wyboru effect provider.

## Główny inwariant semantyczny

Process transition jest guarded transition contract. Wiąże source state, trigger, dependencies, guards, evidence requirements, currentness requirements, *wymagania* authority, typed non-effectful process operator, oczekiwane postconditions, outcome mapping oraz retry/replay/idempotency policy.

Wymiary stanu nie są implicit coercible:

```text
PASS != CURRENT
PASS != AUTHORIZED
PASS != ADMITTED
PASS != EFFECT_OCCURRED
PASS != OBSERVED
PASS != RECONCILED
```

`UNKNOWN` pozostaje first-class result.

## CONTINUE

`CONTINUE` jest selection, a nie execution.

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

Authority-context reference może uczynić transition eligible do handoffu do Action plane, ale nie jest dowodem poprawnego downstream grant. Łańcuch Action/PDP/RuntimeAdmission niezależnie rewaliduje consequential authority.

## Reprezentacja kanoniczna

```text
LPCL text
!=
ProcessAST
!=
CanonicalProcessIR
```

v1 używa strict LPCL statements zawierających wartości RFC8259 JSON. Parser konwertuje je do canonical Process IR. Duplicate statements, duplicate JSON keys, unknown fields i noncanonical `ProcessIR` semantics działają fail-closed.

Digest `ProcessIR` używa własnej domeny `LION/PROCESS-IR/1` i nigdy nie używa ponownie domeny digest Action IR.

## Historyczny RUN

Historyczny materiał `RUN` pozostaje evidence. `LegacyRunAdapter` jedynie ekstrahuje candidate semantic representation. Proceduralne `MODE=...THEN...` albo numerowane PHASE semantics są klasyfikowane jako `AMBIGUOUS`, dopóki dependencies nie zostaną odtworzone. Adapter nie ma execution path.

## Istniejące domenowe state machines

LPCL nie zastępuje `EvolutionaryEpochEngine`, `MissionSpec`, `SwarmSpec`, builder lifecycle ani runtime admission. Domenowe state machines mogą później konsumować generic `ProcessIR` semantics tam, gdzie equivalence została udowodniona; w przeciwnym razie pozostają specialized state machines.

## Non-goals

LPCL nie może mintować authority, oceniać PDP, konstruować `RuntimeAdmission`, wybierać `EffectProvider`, wykonywać raw shell, wykonywać bezpośrednio merge/deploy, self-certify effects ani traktować receipt jako reconciled closure.
