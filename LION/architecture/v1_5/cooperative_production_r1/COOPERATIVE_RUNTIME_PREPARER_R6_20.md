# Cooperative production R6.20 — canonical runtime context preparer

Status: `TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED`. Authority effect: `NONE`.

R6.20 closes the missing composition edge upstream of R6.16. It does not add a new PDP, authority source, scheduler, provisioning engine or runtime executor.

## Problem

R6.16 `CooperativeControlPlaneMaterializer` correctly requires an already-existing `CooperativeRuntimeContext`. It independently re-observes RuntimeAdmission, currentness, dispatch, provisioning and runtime identity before exporting bounded provider evidence. Before R6.20 there was no reusable production component that assembled that exact cooperative context for a newly created HELD WRITE assignment.

The repository already contains the necessary owners:

```text
ActionProposal + ExplicitActionProposalContext
        ↓
canonical PDPResult(ALLOW)
        ↓
RuntimeBindingCurrentness
        ↓
ProvisionedExecutor / ProviderTrustBinding
        ↓
RuntimeAdmissionEngine.admit_bound_action(...)
        ↓
RuntimeAdmission
```

and separately:

```text
SandboxRuntimeBinding
FleetDispatchBinding
ProvisioningBinding
ExecutionSandboxPolicy
```

R6.20 composes these existing records. It does not replace their producers.

## Preparation contract

`prepare_cooperative_runtime_context(...)` accepts exactly:

- one canonical `HELD` cooperative WRITE assignment,
- an existing absolute private artifact root,
- exact Action/PDP/currentness/live-authority/provisioning evidence,
- exact sandbox/dispatch/provisioning bindings,
- the existing `RuntimeAdmissionEngine`,
- one timezone-aware trusted time.

The assignment must carry `COOPERATIVE_ARTIFACT_WRITE` and `COOPERATIVE_ARTIFACT_PRODUCTION`. Its mission/generation/content digest are rebound to the exact artifact resource:

```text
<mission>/g<generation>/<artifact_name>
```

The proposal must be exactly:

```text
requested_authority = local_write
action_class        = WRITE_FILE
target              = exact artifact resource
payload_digest      = exact artifact bytes digest
```

The adapter delegates admission to `RuntimeAdmissionEngine.admit_bound_action(...)`; it never accepts caller-supplied `RequestedRuntimeEffect` or `RuntimeIdentityBinding`.

## Cross-owner validation

Before returning a context R6.20 requires consistency across:

```text
assignment
↔ proposal/context
↔ PDP ALLOW
↔ LiveAdmittedAuthority
↔ ProvisionedExecutor
↔ ProvisioningBinding
↔ FleetDispatchBinding
↔ SandboxRuntimeBinding
↔ ExecutionSandboxPolicy
↔ RuntimeAdmission
↔ RuntimeExecutionRequest
```

It rejects proposal target/payload substitution, non-HELD assignments, provisioning substitution, dispatch generation substitution, sandbox runtime substitution, DENY and runtime-admission replay.

## Prepared source

Runtime admission is intentionally single-use. R6.16 may re-read its `context_source` several times while materializing the private context carrier and exporting independently re-observed evidence.

R6.20 therefore provides `PreparedCooperativeContextSource`: an immutable, assignment-pinned source around one already-admitted context. Repeated reads return the same validated context and never re-run PDP/admission.

This is required for the intended sequence:

```text
prepare once
        ↓
PreparedCooperativeContextSource
        ├── R6.16 materializer read
        ├── R6.15 evidence exporter read
        └── later worker-side reconstruction/readback
```

## Functional integration with R6.16

R6.20 includes a vertical test using the current Mission Control storage shapes and migrations:

```text
current missions/process/operator/driver/scheduler tables
→ canonical HELD WRITE assignment
→ R6.20 context preparation
→ immutable prepared source
→ R6.16 context carrier
→ R6.15 bounded provider evidence export
→ canonical assignment release evidence
→ HELD → READY
```

No artifact bytes are written during this integration test.

## Validation

At the R6.20 candidate boundary:

```text
R6.20 focused suite: 11/11 PASS
combined cooperative/runtime regression: 256/256 PASS
compileall: PASS
git diff --check: PASS
```

The regression includes R6.16–R6.19, scheduler storage, worker qualification/runtime, R22I `admit_bound_action`, runtime enforcement/execution/currentness, executor provisioning and sandbox contracts.

## Remaining source wiring

R6.20 is a reusable preparer, but current Mission Control does not yet invoke it when `advance_build` creates a new HELD WRITE assignment.

The next increment must expose a process-composition dependency that, for one exact HELD assignment, supplies the existing canonical Action/PDP/provisioning/sandbox evidence and calls R6.20 exactly once. The resulting `PreparedCooperativeContextSource` must then be consumed by the existing R6.16 materializer.

That integration must remain dependency injection. Mission Control must not become a second PDP, provisioning provider or authority owner.

After that wiring, the source path from HELD assignment through preparation, R6.16 release, R6.17 qualification and the R6.19 proven write/verify chain is complete enough to author the current-source live successor mission.
