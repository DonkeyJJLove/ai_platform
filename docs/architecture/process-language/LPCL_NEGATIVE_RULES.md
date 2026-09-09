# LPCL semantic negative rules

This document is the human-readable companion to `cyber_lion/process_language/negative_corpus.json`.

The validator must fail closed on these classes:

- epistemic coercion (`UNKNOWN -> PASS`, `PASS -> CURRENT`);
- currentness without an evidence-bound basis;
- authority requirement interpreted as a grant or any process-level authority minting;
- raw effect semantics, raw shell, PDP, RuntimeAdmission or EffectProvider selection inside ProcessIR;
- consequential closure without independent observation and reconciliation;
- direct execution of historical RUN material;
- drift continuation without reacquisition;
- unbounded continuation/retry or cycles without a bound/progress condition;
- parallel transitions with unresolved scope/authority/replay/reconciliation conflicts;
- retry scope widening;
- non-idempotent partial-effect retry without reconciliation-first semantics;
- dependency bypass;
- ActionSpec execution fields leaking upward into ProcessIR;
- reuse of the existing `process_profile` namespace for LPCL semantic identity;
- treating historical PHASE order as authoritative when it conflicts with reconstructed dependencies.

These are architecture invariants, not merely parser errors.
