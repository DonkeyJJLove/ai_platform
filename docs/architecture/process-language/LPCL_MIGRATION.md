# LPCL migration candidate

LPCL v1 is introduced as an additive candidate. Existing MissionSpec, EvolutionaryEpoch, ActionSpec, ActionProposal, PDP, RuntimeAdmission and effect/reconciliation contracts remain canonical in their current domains.

## Historical RUN

```text
historical RUN text
→ LegacyRunAdapter
→ classification
→ semantic candidate only when non-ambiguous
→ canonical ProcessIR validation
```

Classifications:

- `LOSSLESS_TRANSLATION`
- `LOSSY_BUT_SAFE`
- `AMBIGUOUS`
- `UNREPRESENTABLE`

The current adapter intentionally classifies procedural `MODE=...THEN...`, numbered PHASE semantics or ambiguous authority fields as `AMBIGUOUS`. It never executes historical text.

## Federation

The current central repository registry is truth-subject-derived. This candidate records the split ownership explicitly but does not manually rewrite that generated currentness carrier. Regeneration/reconciliation of that carrier is downstream of successful LPCL contract CI.

## Existing state machines

No bulk migration is authorized. `EvolutionaryEpochEngine` and other domain state machines remain as-is until equivalence with generic TransitionSpec semantics is individually proven.
