# Cooperative production R5 — concrete context resolver and runtime discriminator

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Base: `47015cbba498ca91f194a890110d143671c6271d`. This increment extends the R4 composition in the same PR408. It does not issue authority, activate a successor, deploy a worker loop or advance an existing live mission.

## Implemented connection

`cyber_lion/enterprise/cooperative_context_resolver.py` now supplies the concrete `PinnedCooperativeContextResolver`, not merely another abstract context-source interface. It reads the original Mission Control SQLite tables in a query-only transaction and resolves an independently pinned per-assignment context reference. The reference contains existing provisioning/policy/dispatch/request/effect/identity contracts and an admission digest, never an embedded admission or a model-selected authority source. The original trusted RuntimeAdmissionSource supplies the actual admission; the original dispatch source and an independently provisioned runtime-identity source must match.

The resolver checks the exact claimed assignment, mission, driver phase, generation, operator control epoch, context/plan revisions, active leases, original input digest, capability revocation and exact activated LPCL bytes. Missing canonical state is not interpreted as permission. Duplicate JSON keys, substituted source pins, path indirection, changed files and replaced database identities fail closed. The record serializer `context_reference_bytes` converts an already-provisioned typed context to bytes without publishing it or authorizing it.

The R4 provider now invokes this resolver twice: once to obtain the context and again at the filesystem boundary. A pause or driver-phase change between the first lookup and the write therefore stops the write. The original effect-time authority/policy/observability guard, dispatch fence, single-use admission consumption and sandbox budget remain in force. A failed final check does not silently restore the consumed admission.

```text
existing assigned task
 -> original Mission Control snapshot + independently pinned context reference
 -> original admission source + current dispatch + runtime identity
 -> CooperativeRuntimeContext
 -> existing R4 writer/enforcement composition
 -> final context revalidation
 -> exact artifact write/readback
 -> original runtime receipt
```

This is a control-plane resolver. It must not be implemented in a worker by giving every worker a writable copy of the global Mission Control database. Live installation still requires the existing trusted composition to provide the real per-assignment reference/pin, canonical sources and worker-owned storage. The configured private roots and database identity checks are not a security boundary against a hostile process sharing the same UID. The local SQLite snapshot is not a distributed transaction; the effect-time checks remain necessary.

## Root cause of the original pilot failure

The original R1 LPCL omitted `MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL`. Mission Control therefore selected the older Epoch3 branch and raised `lpcl execution adapter cardinality`. The 2-logical/32-material topology itself is supported by the existing Docker binder. An original-code integration test proves that the explicit Docker discriminator binds LD001 to MD001 and LD002 to MD002 while retaining all 32 material workers. No logical-count rewrite or fleet replacement is necessary.

`lpcl_runtime_selection.py` is shared by the panel bridge and execution binder. Validation now returns a separate `runtime_preflight` containing the selected adapter or a precise diagnostic. Language validity and dynamic capability readiness remain separate. Missing/unsupported runtime is not inferred from PILOT_* hints, container names or the active browser tab. The execution binder refuses it with an explicit runtime diagnostic. The original registered R1 bytes and activation digest remain unchanged; this change does not silently substitute or launch the unlaunched R2.

## Executed tests

There are 45 new resolver tests and 13 new runtime-selection tests. The selected 278-test suite passed with no failures, errors or skips. It includes the unchanged original Docker rematerialization and LPCL rebind suites. The new resolver/previous writer/composition selection also passed 81/81 cases in each of the existing MOON containers MD001 and MD002, using the same 59-file import closure under UID65532. The original worker main processes and start times were preserved.

SQLite, files and containers in these tests are real. Admission/currentness/runtime identities and activation events are explicitly synthetic test fixtures, not live authorization or deployment evidence. Neither R5 nor its tests made another local-model call. R3's previously generated corpus remains separate.

The initial regression run recorded one failure because R4 asserted exactly one context lookup. That assertion was changed to require exactly two lookups of the same assignment. Two negative controls remove only the final callback and demonstrate that both the pause-race and phase-race regressions are detected. Their two expected failures are negative-control success, not a passing production suite. Original logs are retained.

## Publication and remaining boundary

The historical `LION/evidence/r24-whole-integration/PACKAGE_MANIFEST.json` is preserved. Its recorded package includes the old panel bridge, so the historical whole-integration gate may correctly report PACKAGE_IDENTITY_MISMATCH for this source delta. Do not rehash historical deployment evidence merely to make CI green. A separate candidate source-package manifest and its source-only classification are included in the validation record; they do not replace historical evidence or constitute a runtime cutover.

The next operational step is to bind the existing trusted admission/provisioning producer to the new reference serializer and resolver, provision private worker storage and bounded verifier transfer, and inject the tested composition into the existing worker consumer. The original pilot also needs an explicitly accepted corrected runtime declaration. The broad development prototype remains preserved; read-only generic execution must not become a write authorization path.

A combined scoped source read covering the runbook, authorization-lifecycle file and two control-plane provider/composition implementation files was rejected by the tool safety boundary in this increment. That operation was not retried through another transport. Dependent live deployment/authority integration is not claimed complete; the independent resolver and topology source/test work continued. This is not a full ai_platform or peer audit.

Worktree: `/srv/lion-e4-candidate-r1/cooperative-resolver-r5`. Raw evidence: the preserved development worktree's `cooperative-transfer-evidence/continuation-r5/`. The source delta was prepared without resetting the dirty development checkout or modifying PR407. See `RUNTIME_RESOLVER_R5_VALIDATION.json` for exact hashes and test scopes.
