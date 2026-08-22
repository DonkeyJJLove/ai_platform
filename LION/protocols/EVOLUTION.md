# LION Evolution Protocol

LION evolves architecture by explicit deltas rather than by accumulating unrelated code.

```text
TARGET
→ OBSERVE IMPLEMENTATION
→ COMPUTE GAP
→ CREATE MISSION
→ ASSIGN DRONE/SWARM
→ BUILD
→ VERIFY
→ INTEGRATE
→ OBSERVE EFFECT
→ RECONCILE
→ UPDATE IMPLEMENTATION/DEPENDENCY PROJECTIONS
→ SELECT NEXT GAP
```

## State separation

Architectural lifecycle: `TARGET_ONLY | PLANNED | BUILDING | VERIFIED | INTEGRATED | OBSERVED | BLOCKED | QUARANTINED | SUPERSEDED`.

Epistemic freshness: `CURRENT | STALE | UNKNOWN | CONFLICTED`.

These dimensions are independent. For example, a component may be `INTEGRATED + STALE` until live state is re-observed.

## Mission selection

Prefer the smallest critical-path slice that closes a real target-vs-implementation gap. Keep WIP at one on the critical path unless partitions are explicitly proven independent. Preserve provider specialization and avoid premature migration into `ai_platform`.

## Projection update

Catalog files are reviewed projections. Dynamic facts must include provenance and freshness binding. Never rewrite normative target documents merely to make implementation appear complete.

## Authority

Evolution records describe what should or does exist. They do not mint execution, merge, credential, release or deployment authority.
