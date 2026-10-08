# Cooperative production R6.18 — Mission Control process composition bootstrap

Status: `TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED`. Authority effect: `NONE`. Execution effect: `NONE`.

R6.18 closes a source-level wiring gap discovered while reconciling R6.16 and R6.17 with the current Mission Control process.

## Problem

Current Mission Control already contains `COOPERATIVE_MATERIALIZERS=CooperativeMaterializationRegistry()` and refuses cooperative production/verification when that registry is unbound. The source also contains the R6.16 `CooperativeControlPlaneMaterializer` and the R6.10 `CooperativeRuntimeCompositionRoot.materialization_provider()` machinery.

Before R6.18 there was no production call site that installed an exact `CooperativeMaterializationProvider` into the Mission Control registry.

This absence is fail-closed, but it participates in the live bootstrap cycle:

```text
worker provider READY
  required by bootstrap_readiness(32)
        ↓
PRODUCTION / VERIFY capabilities become bindable
        ↓
Mission Control needs COOPERATIVE_MATERIALIZERS
        ↓
registry had no production installation owner
```

R6.18 addresses only the missing **process composition binding**. It does not weaken worker readiness and does not attempt to solve single-worker qualification by pretending the fleet is ready.

## Composition

The new `cyber_lion/mission_control/cooperative_process_bootstrap.py` supports exactly two modes.

`UNBOUND` is the default. It installs nothing and requires the registry to remain empty.

`TRUSTED_EXTERNAL_R1` requires an exact bootstrap version, repository root, an external regular dependency module outside the repository, its exact SHA-256 digest and a bounded factory name. The factory must return the exact `CooperativeProcessBootstrapDependencies` type.

That object contains exactly:

```text
CooperativeControlPlaneMaterializer
    → WRITE materialization / R6.16 provider export

CooperativeRuntimeCompositionRoot
    → VERIFY transfer materialization / existing R6.10 owner
```

Both must bind the same Mission Control database inode. The bootstrap then creates the existing `CooperativeMaterializationProvider` and installs it exactly once into the existing registry.

## What the bootstrap does not do

It does not construct or issue RuntimeAdmission, LiveAdmittedAuthority, dispatch, provisioning, currentness, context, assignments or release evidence. It does not call PDP, create HELD/READY assignments, claim work, write an application artifact, restart a worker, rematerialize the fleet, schedule a phase or activate an LPCL.

The external process dependency module therefore has a narrow responsibility: compose already-existing canonical upstream owners. It may not use the R6.14 worker provider DB as the source of the R6.15/R6.16 export decision; doing so would create self-confirming evidence.

## Mission Control wiring

`tools/lion_mission_control_v3.py` now invokes the bootstrap once against the existing process-local registry. With no explicit environment configuration the result is:

```text
state=UNBOUND
authority_effect=NONE
execution_effect=NONE
```

Thus merely integrating or deploying these source bytes does not make cooperative production live.

## Remaining bootstrap cycle

R6.18 deliberately leaves the next problem visible. The current capability projection still requires `bootstrap_readiness(... expected_workers=32)` before exposing production/verify capabilities. Current live workers are not R6.17-qualified and the old R3 mission is stale relative to current source.

The next increment must introduce a **bounded pre-activation single-worker qualification path** using the existing R6.16 HELD→READY evidence and R6.17 qualification entrypoint. It must not call the artifact writer and must not mark the whole fleet ready.

Only after that bounded qualification can a separately admitted deployment/activation install the worker runtime provider and permit the first real application-factory artifact loop.
