# Cooperative production R6.19 — functional acceptance over current scheduler storage

Status: `TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED`. Authority effect: `NONE`.

R6.19 does not add a new execution mechanism. It closes a validation gap between the historical R6.17 qualification fixture and the current scheduler storage/claim path, then proves the already-existing R6.16/R6.17/runtime composition as one isolated functional chain.

## Why this increment was needed

R6.17 component tests used a reduced historical `mission_execution_assignments` fixture without the current scheduler columns `created_at`, `claimed_at` and `finished_at`. Qualification itself passed because it stops before claim/effect. A first functional test using the real current `global_scheduler.claim_assignment()` therefore failed with:

```text
OperationalError: no such column: claimed_at
```

That failure was a test-fixture/current-storage mismatch, not a cooperative qualification failure. R6.19 brings the fixture shape forward and requires it to pass the current scheduler migration.

## Functional chain proved

The new regression test executes the real current components in a temporary isolated filesystem/SQLite environment:

```text
R6.16 control-plane materialization
→ HELD assignment
→ canonical release evidence
→ READY

R6.17 qualification for MD001
→ provider evidence re-opened
→ private context/admission materialized
→ writer factory reconstructed
→ execution_performed=false

install qualified root into isolated worker registry
→ current global_scheduler.claim_assignment()
→ READY → CLAIMED
→ CooperativeWorkerRuntime
→ RuntimeExecutionEngine
→ bounded artifact write
→ exact byte readback
→ scheduler receipt/payload
→ PASS

distinct MD002 verifier root
→ verifier transfer materialization
→ HELD → READY
→ current scheduler claim
→ verify exact artifact bytes/digest
→ independent receipt
→ PASS
```

The deterministic fixture artifact is 25 bytes with SHA-256:

```text
5333bbd57e98dc79c9dea05acfe969cc66d9fd848cc0a8289e202c6d4fef6679
```

The builder runtime receipt reports `effect_state=OBSERVED`; builder and verifier both retain `authority_effect=NONE`; the verifier is MD002 while the producer is MD001.

## Qualification and claim semantics

The functional test also resolves an earlier concern about a possible immediate READY→CLAIM race.

The canonical worker loop enters `COOPERATIVE_ASSIGNMENT` only when `PROCESS_COOPERATIVE_RUNTIME.current(WORKER_ID)` is non-null. With the worker bootstrap in default `UNBOUND` mode, a cooperative READY row is therefore not consumed by the canonical cooperative worker path.

R6.17 remains a qualification proof, not authority. The scheduler does not treat `qualification_digest` as an authority grant. After an already-qualified composition root is explicitly installed, the normal scheduler claim and runtime admission/currentness fences remain authoritative.

This is not a proof against an arbitrary hostile client calling the claim API directly. It proves the canonical worker/process composition.

## Regression results

At the R6.19 candidate boundary:

```text
new functional acceptance suite: 9/9 PASS
cooperative/runtime/scheduler regression: 167/167 PASS
compileall: PASS
git diff --check: PASS
```

The wider regression includes process bootstrap, materializer registry, R6.16 control-plane materializer, R6.17 qualification, production stepper, context resolver, runtime root/composition, worker runtime/bootstrap, HELD release, scheduler storage reconciliation, Mission Control wiring and integration guards.

## Live readback remains separate

The current live R24 workers observed during R6.19 authoring are healthy as legacy material workers but do not contain the candidate cooperative activation:

```text
MD029 state=READY self_test=PASS cooperative_runtime_bootstrap=null provider=null
MD030 state=READY self_test=PASS cooperative_runtime_bootstrap=null provider=null
```

The current focused mission remains:

```text
LION-COOPERATIVE-PRODUCTION-PILOT-R3
REGISTERED
NOT_STARTED
authority=NONE
source=c4e3c889... / 3badc880...
```

That source is stale relative to current remote master and to the stacked R6.18/R6.19 candidates.

Therefore R6.19 proves **functional source integration**, not live deployment acceptance.

## Remaining boundary

The remaining functional blocker is upstream composition for a real assignment: R6.16 requires an already-provisioned `CooperativeRuntimeContext` plus independently re-observable RuntimeAdmission, provisioning, dispatch, runtime identity and currentness. Current source contains the contracts, admission/runtime engines and evidence adapters, but no current production composition entrypoint was found that builds the exact cooperative context for a newly-created real WRITE assignment.

The next source increment should bind that existing upstream runtime/admission plane to cooperative assignment preparation. It must reuse canonical owners and must not derive its own trust from the R6.14 worker provider DB.

Only after that source path is formalized and deployed should an exact current-source successor mission perform the first live SaaS/LOCAL → material write → independent verify loop.
