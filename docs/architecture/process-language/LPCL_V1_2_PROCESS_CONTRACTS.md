# LPCL 1.2 — Process Contract extension

LPCL/1.2 is an additive process-contract extension of the v1.1 RUN/PHASE model. It does not grant authority and does not make historical unversioned RUN executable.

Canonical semantic owner: `LION/architecture/v1_4/LION_PROCESS_CONTRACT_PLANE.md`.
Machine contract: `cyber_lion/contracts/phase_execution_contract.py` (`lion.phase-execution-contract/v1`).

## Version rule

```text
LPCL/1.1 → compatible, LEGACY_INFERRED_SAFE phase contracts
LPCL/1.2 → explicit PhaseExecutionContract required for every executable phase
UNVERSIONED RUN → historical/data rules remain unchanged
```

## Panel-style phase contract

```text
PHASE_03=REPAIR_EXECUTION_BINDER|Repair generic LPCL execution binding
PHASE_03_EXECUTION_CLASS=VERIFY_THEN_REPAIR
PHASE_03_CAPABILITY_CLASS=REPOSITORY_AND_RUNTIME_RECONCILIATION
PHASE_03_EFFECT_CEILING=BOUNDED_REPOSITORY
PHASE_03_BINDING_MODE=DYNAMIC
PHASE_03_ON_MISSING_CAPABILITY=WAIT_AND_DISCOVER
PHASE_03_AUTO_RESUME=TRUE
PHASE_03_VERIFY_BEFORE_MUTATE=TRUE
PHASE_03_CURRENTNESS=EXACT_CURRENT_REPOSITORY,CURRENT_MISSION_RUNTIME,CURRENT_MATERIAL_BINDING
PHASE_03_EVIDENCE=LIVE_RUNTIME_READBACK,FOCUSED_REGRESSION,POSTCONDITION_RECONCILIATION
PHASE_03_COMPLETION_01=GENERIC_ADAPTER_BOUND=PASS
PHASE_03_COMPLETION_02=MATERIAL_READY_64=PASS
```

Completion predicates containing `=` must be inline on the `PHASE_XX_COMPLETION_NN=` line.

## Canonical RUN/PHASE fields

A v1.2 phase additionally uses:

```text
EXECUTION_CLASS
CAPABILITY_CLASS
EFFECT_CEILING
BINDING_MODE
ON_MISSING_CAPABILITY
AUTO_RESUME
VERIFY_BEFORE_MUTATE
CURRENTNESS_CONTRACT
EVIDENCE_CONTRACT
COMPLETION=<PREDICATE>=<EXPECTED>
```

The completion predicate is inline for the same lexical reason.

## Validation

The compiler fails closed on missing/invalid v1.2 contracts. Key constraints include:

- `OBSERVE` has `effect_ceiling=NONE`.
- `VERIFY_THEN_REPAIR` requires `VERIFY_BEFORE_MUTATE=TRUE`.
- `MUTATE` requires evidence requirements.
- verification classes require completion predicates.
- `AUTO_RESUME=TRUE` requires a deterministic waiting policy (`WAIT` or `WAIT_AND_DISCOVER`).
- capability binding must not exceed the contract's effect ceiling.

A valid dynamic contract may be unbound at activation. This is `VALID_UNBOUND_WAITING`, not `INVALID`.

## Preflight

Before activation the compiler returns `lion.mission-execution-preflight/v1` with contract/binding counts and closure status. `INVALID` blocks activation; valid dynamic waiting is allowed and is observable in Mission Control.

## Safety boundary

```text
LPCL 1.2 CONTRACT != CAPABILITY
CAPABILITY != AUTHORITY
EFFECT CEILING != AUTHORITY GRANT
MODEL PLAN != ACTION IR
ACTION IR != EFFECT
RECEIPT != COMPLETION
```

The extension therefore increases process determinism without collapsing the existing LION authority/runtime boundaries.
