# R8 — canonical Docker bootstrap need → original admitted effect

Status: **SOURCE CANDIDATE / NOT MERGED / NOT INSTALLED / NO LIVE MATERIAL EFFECT**.

## Scope

R7 stores a typed and source-bound `DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED`
on an operator-launched LPCL in the existing
`GLOBAL_MISSION_SCHEDULER_V1`. R8 implements the matching **consumer** in
`cyber_lion/mission_control/docker_bootstrap_need_consumer.py`.
No second scheduler, authority issuer, container manager, browser integration
or shell interpreter is created.

The bounded progression is:

```text
canonical Mission Control snapshot + journaled R7 CapabilityNeed
  + independent source HEAD/TREE (not from the message itself)
  -> strict active-driver, LPCL digest, message and generation validation
  -> original MoonDockerComposeRuntime: 32-worker Compose/security plan
  -> exact, externally materialized identity.json + receipt
  -> WAITING_RUNTIME_ADMISSION (no effect unless separate issuer acted)
  -> original RuntimeAdmission + RequestedRuntimeEffect + RuntimeIdentityBinding
     + LiveAdmittedAuthority from trusted runtime admission source
  -> source/driver/generation readback directly before effect
  -> existing DockerFleetBootstrapExecutor.execute(...)
     -> consumed-once SQLite admission guard
     -> source/currentness/admission/live-authority revalidation
     -> exact Compose argv and independent 32-heartbeat readback
     -> observed receipt or EFFECT_UNKNOWN_RECONCILE
```

The dependency injection points are `snapshot_source`,
`current_source`, `admission_source`, and an **exact instance** of
the original `DockerFleetBootstrapExecutor`. Only a trusted host
composition root may bind these sources. No HTTP request or model output
can fabricate a `RuntimeAdmission`, a PDP allow receipt or a
`LiveAdmittedAuthority`. A protocol message is evidence of *need*,
not authorization.

## Safety gates

The consumer verifies every persisted need message, its exact digests,
record identifiers and declared source. A newer, coherent gate may
supersede a previously persisted one; a changed historical message
blocks the current operation. It rejects a missing operator activation,
foreign/wait-state lease owner, wrong driver generation, materialized
cohort spoofing, changed source HEAD/TREE and unrelated Docker scope.

A materialized runtime that fails current-source/receipt agreement
is rejected before admission lookup. The consumer then checks the
independently issued, concrete admission and rereads the canonical
mission journal and source before entering the existing original
executor. The original executor retains its own identity, authority,
admission, prepared-runtime and Docker inventory checks.

`EFFECT_UNKNOWN_RECONCILE` is a terminal *uncertain* effect state;
it is **not** permission to run `docker compose up` again. The
original durable `SQLiteAdmissionConsumptionGuard` denies any
second consumption. Observation and independent downstream
reconciliation still own completion.

## What was exercised

Unit tests use the original R24 executor with a synthetic, ephemeral
SQLite admission state and in-memory fake runtime. Test success
means the **source code path** can consume exact evidence and
issue one effect to that fake runtime; it is **not** a real admission,
MOON container launch or proof that the independent issuer is installed.
Tests cover absent admission, one admitted action, duplicate/changed
messages, source drift, old prepared runtime/receipt, foreign driver,
generation drift before effect, wrong effect resource and
effect-unknown non-retry.

## Deployment dependency

No live `snapshot_source`, `admission_source` or per-mission host
composition for this adapter is installed. Source-to-effect handoff
must be delivered through an existing trusted message fabric and bound
to the original admission issuer, not by exposing an unmediated
`POST /docker-up` API. The old 32 R24 containers remain stopped,
historically mismatched and ineligible for restart. The exact R7
source wait record and this consumer do not fix initial
`CROSS_MODEL_RECON` material-lease dependency or install
preactivation, production and verification materializers.

**Next concrete implementation:** trusted MOON runtime composition
that resolves a durable admitted effect from the original
`SQLiteRuntimeAdmissionSource` and authority verifier, consumes
the canonical mission source from the already-installed Mission
Control, and uses this R8 adapter in the existing scheduler's
effect lifecycle. Establish a fresh immutable 32-worker runtime
with source/receipt/compose/mount validation before any actual effect.
User must explicitly activate exact LPCL and its bound effects.


## Effect-surface inventory readback

R8 adds exactly one tracked production Python module to the static host
inventory: 427 → 428 paths. Independent scanner census remains
573 recognized effect surfaces and 6 unclassified references; this is
**not** a claim that a new execution path is non-consequential. The host
authority regression additionally checks the AST for exactly one
`self.executor.execute(...)` delegation to the previously inventoried
R24 one-shot effect boundary, and denies direct `subprocess`,
`socket` or `os` imports in this adapter. Production adoption
still requires source- and admission-bound runtime owners, not just
a positive static count.
