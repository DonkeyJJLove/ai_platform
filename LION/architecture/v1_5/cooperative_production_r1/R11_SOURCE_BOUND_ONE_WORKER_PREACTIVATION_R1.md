# R11 — source-bound one-worker preactivation (implementation candidate)

Status: TESTED_SOURCE_CANDIDATE / NOT_MERGED / NOT_DEPLOYED.
Scope: existing Application Factory PREACTIVATE_BUILDER phase.
Owner: ai_platform Mission Control and cooperative runtime.
Authority effect: NONE. Artifact execution: NONE.

## Concrete closed gap

The existing R6.21 durable CooperativeRuntimePreparationProvider is now
bound to the canonical R6.16 CooperativeControlPlaneMaterializer and R6.17
CooperativeRuntimeCompositionRoot by the typed
CooperativeSourceBoundPreactivation object, loaded only through the existing
SHA-256-pinned external bootstrap. The new bootstrap mode
SOURCE_BOUND_PRODUCTION_R11 is fail-closed, not default. Default UNBOUND remains.
Historical TRUSTED_EXTERNAL_R1 remains compatible for older clients, while
the canonical Application Factory driver rejects it before preactivation.

This composition validates identical Mission Control database identity across
all three owners; exact R6.21 context source, SQLite admission publisher and
source-trust bindings; independent read-only R6.17 worker evidence DB bound
to the R6.16 publisher; private workspace boundary and exact selected worker.
A wrong type, source or factory is rejected before registration.

A producer/consumer defect is fixed in the existing
PinnedCooperativeContextResolver: HELD-to-READY does not mint a worker
execution lease. READY qualification now requires the canonical release-ledger
record, matching recomputed digest, mission/assignment coordinates, bounded
R6.16 materialization provider and current driver lease. Any existing stale
assignment lease fails. CLAIMED execution still requires a non-expired
assignment lease and the original currentness/authority fences.

## Bounded source-path acceptance

The original cooperative_preactivation.advance_preactivation was exercised
with a disposable Mission Control SQLite database, R6.21 / R6.16 / R6.17
implementation code, and synthetic authority/provisioning fixtures. This
performed only HELD WRITE preparation, durable simulated admission, provider
export, HELD-to-READY, worker-private qualification, and an existing canonical
artifact/journal record. The assignment remained READY, the physical artifact
directory empty, and execution receipts zero. Idempotent re-entry yielded
the same qualification digest.

Negative acceptance includes missing and substituted release evidence,
expired driver/assignment leases, CLAIMED without an execution lease,
wrong worker, mismatched source owners and a raw callable substituted for the
typed source-bound factory. Source validation, 93-file package import and P0
regressions remain separate requirements.

## Boundary not yet crossed

The test uses synthetic authority input and does not establish production
RuntimeAdmission, a live authenticated provider, an operating worker process,
a current SaaS session, a deployed cohort, or any physical artifact effect.
Real production activation needs an independently current
CooperativeRuntimePreparationEvidence producer (Action, PDP, live authority,
provisioning, sandbox, dispatch and currentness), signed/pinned external
factory, current operator-launched exact LPCL, and separate runtime admission.
Nothing in this source candidate grants those effects.

Publish source/CI first. The original 32-worker BUILD/VERIFY readiness gate,
independent byte-level verification and terminal mission reconciliation are
unchanged. No production mission is started by this increment.
