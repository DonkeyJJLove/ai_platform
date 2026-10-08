# Cooperative production R6.22 — bounded single-worker preactivation capability

Status: `TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED`. Authority effect: `NONE`. Execution effect: `NONE`.

R6.22 removes the bootstrap cycle in the existing cooperative Mission Control driver without weakening the 32-worker production/verification readiness gate.

## Problem

Before R6.22 every cooperative phase entered `bootstrap_readiness(... expected_workers=32)` before the handler distinguished BOOTSTRAP, PRODUCTION or VERIFY. Therefore no mission phase could prepare the first R6.17-qualified worker through the same driver: full fleet provider readiness was required before the path that could establish provider readiness.

## Capability

R6.22 adds exactly one pre-readiness capability class:

```text
COOPERATIVE_WORKER_PREACTIVATION
capability_id = COOPERATIVE_WORKER_PREACTIVATION_R1
effect_ceiling = NONE
```

It is published by the process capability registry only when an exact `CooperativePreactivationProvider` is installed by a SHA-256-pinned external bootstrap module. Default state is `UNBOUND`.

## Finite preactivation sequence

```text
qualification-only HELD WRITE
→ existing R6.21/R6.20 preparation
→ existing R6.16 provider export
→ canonical HELD→READY release evidence
→ existing R6.17 single-worker qualification
→ mission_artifact: lion.cooperative-worker-qualification/v1
→ PASS
```

The assignment remains READY. It is never claimed or executed by R6.22. The result records `writer_factory_built=true`, `execution_performed=false`, `authority_effect=NONE`.

## Recovery

Before calling R6.17 the stepper writes an existing `mission_artifacts` journal with state `QUALIFYING`. Success changes it to `QUALIFIED`. An exception changes it to `UNKNOWN`.

A re-entry that finds `QUALIFYING` or `UNKNOWN` blocks with `PREACTIVATION_QUALIFICATION_UNKNOWN`; it does not blindly call R6.17 again. A completed qualification artifact makes the phase idempotently PASS without a second materialization or qualification.

## Driver isolation

`drive_cooperative_once()` branches on `COOPERATIVE_WORKER_PREACTIVATION_R1` before calling `bootstrap_readiness(32)`. All other cooperative capabilities remain on the previous path:

```text
PREACTIVATION -> exact provider required, no 32-worker gate

BOOTSTRAP / PRODUCTION / VERIFY
  -> bootstrap_readiness(32)
  -> production/verify additionally require process materializers
```

This is deliberate. R6.22 does not redefine readiness for material production.

## Validation

Focused R6.22 tests cover provider registry exactly-once, default UNBOUND, pinned external bootstrap, qualification PASS, mission-artifact persistence, idempotent re-entry and UNKNOWN/no-replay recovery.

At the candidate boundary the combined cooperative/runtime regression is `301/301 PASS`; compileall and git diff checks pass.

## Remaining boundary

R6.22 proves only one-worker preactivation. It does not install the qualified root in the live worker process and does not restart/rematerialize the fleet.

The next mission must therefore separate:

1. preactivation qualification of the selected worker;
2. separately admitted deployment/worker bootstrap of exact qualified source/dependencies;
3. full worker readiness readback;
4. production/verification only after the existing readiness gate passes.

Mission activation and deployment remain separate operator-authorized effects.
