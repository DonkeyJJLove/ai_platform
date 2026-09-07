# R21 LPCL candidate build

This candidate materializes LION Process Contract Language as a non-effectful process-contract layer. It does not grant authority, evaluate policy, construct runtime admission, select an effect provider, or execute effects.

## Ownership

- `DonkeyJJLove/chunk-chunk`: formal process-semantics reference (`process.state`, `process.transition`, transition microcode, trajectory diagnostics).
- `DonkeyJJLove/ai_platform`: canonical LION integration contract (`CanonicalProcessIR`, validation/selection, Process→Action and Reconciliation→Process boundaries).
- `DonkeyJJLove/writeups`: research/history corpus.

The central `cyber_lion/registry/repositories.json` remains truth-subject-derived and is intentionally not rewritten by this semantic candidate. Reconciliation of that generated projection is a follow-on currentness task after the candidate contract passes exact-head CI.

## Currentness

Candidate base: `67a4f8243aa6805e47035e572bd458f73fd0b358` / tree `4f6fbc481c8df8f7e1fd75f04188207a1c6fbcf5`.

Any default-branch drift before integration invalidates attach assumptions and requires rebase/revalidation.

## Architecture placement

LPCL is represented inside the existing `EVOLUTIONARY_EPOCH` architecture layer. No 16th top-level layer and no 10th canonical flow are introduced in v1.

## Mandatory invariants

```text
PROCESS_TEXT != AUTHORITY
PROCESS_TRANSITION != ACTION_EXECUTION
ACTION_INTENT != ACTIONSPEC
ACTIONSPEC != PROPOSAL
PROPOSAL != PDP_ALLOW
PDP_ALLOW != RUNTIME_ADMISSION
RUNTIME_ADMISSION != EFFECT
EFFECT != OBSERVATION
OBSERVATION != RECONCILIATION
```

CI and independent semantic review are required before any integration decision.
