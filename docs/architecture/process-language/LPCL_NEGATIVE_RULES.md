# LPCL semantic negative rules

This document is the human-readable companion to both falsification corpora:

- `cyber_lion/process_language/negative_corpus.json` — strict LPCL 1.0 / ProcessIR architecture invariants;
- `cyber_lion/process_language/canonical_run_negative_corpus.json` — LPCL 1.1 RUN/PHASE and fleet-mission conformance.

The interpretation and semantic validators must fail closed on these classes:

- epistemic coercion (`UNKNOWN -> PASS`, `PASS -> CURRENT`);
- currentness without an evidence-bound basis;
- authority requirement interpreted as a grant or any process/fleet-level authority minting;
- raw effect semantics, raw shell, PDP, RuntimeAdmission or EffectProvider selection inside ProcessIR/FleetMissionIR;
- consequential closure without independent observation and reconciliation;
- direct execution or silent promotion of unversioned historical RUN material;
- explicitly versioned v1.1 source missing `TERMINATION` or `LINEAGE`;
- unknown or inconsistent fleet mission class;
- LOGICAL-only mission containing an `ACTION_REQUIRED` transition;
- `ACTION_REQUIRED` routed to a non-LOCAL role;
- `ACTION_REQUIRED` using any operator other than `EMIT_ACTION_INTENT`;
- undeclared role routing or invalid role-separation references;
- fleet mission carrying non-`NONE` authority/runtime/effect-provider effect;
- v1.1 surface declaring non-`NONE` authority/runtime/execution/effect-provider effect posture;
- annotation blocks (`ACTIONS`, `VERIFY`, `RECORD`, etc.) overriding typed transition semantics;
- drift continuation without reacquisition;
- unbounded continuation/retry or cycles without a bound/progress condition;
- parallel transitions with unresolved scope/authority/replay/reconciliation conflicts;
- retry scope widening;
- non-idempotent partial-effect retry without reconciliation-first semantics;
- dependency bypass;
- ActionSpec execution fields leaking upward into ProcessIR;
- reuse of the existing `process_profile` namespace for LPCL semantic identity;
- treating historical PHASE order as authoritative when it has not passed the explicit v1.1 profile and canonical compilation.

These are architecture invariants, not merely parser errors. A conformant parser/compiler/interpreter may be stricter than the examples but must never weaken these boundaries.
