# R21 — build kandydata LPCL

Ten historyczny candidate materializuje LION Process Contract Language jako non-effectful process-contract layer. Nie grantuje authority, nie ocenia policy, nie konstruuje runtime admission, nie wybiera effect provider i nie wykonuje effects.

## Ownership

- `DonkeyJJLove/chunk-chunk`: formalny process-semantics reference (`process.state`, `process.transition`, transition microcode, trajectory diagnostics).
- `DonkeyJJLove/ai_platform`: canonical LION integration contract (`CanonicalProcessIR`, validation/selection, granice Process→Action i Reconciliation→Process).
- `DonkeyJJLove/writeups`: research/history corpus.

Centralny `cyber_lion/registry/repositories.json` pozostaje truth-subject-derived i celowo nie był przepisywany przez tego semantic candidate. Reconciliation tej generowanej projekcji jest osobnym currentness task po przejściu exact-head CI przez candidate contract.

## Currentness

Historyczny candidate base: `67a4f8243aa6805e47035e572bd458f73fd0b358` / tree `4f6fbc481c8df8f7e1fd75f04188207a1c6fbcf5`.

Każdy default-branch drift przed integracją unieważniał attach assumptions i wymagał rebase/revalidation. Ten exact baseline pozostaje częścią historycznego lineage i nie powinien być zastępowany dzisiejszym `master`.

## Umiejscowienie w architekturze

LPCL jest reprezentowany wewnątrz istniejącej architecture layer `EVOLUTIONARY_EPOCH`. W v1 nie wprowadzono 16. top-level layer ani 10. canonical flow.

## Obowiązkowe inwarianty

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

Przed każdą decyzją integracyjną wymagane są CI i niezależny semantic review związane z właściwym exact head. Sam ten dokument nie jest integration authority.
