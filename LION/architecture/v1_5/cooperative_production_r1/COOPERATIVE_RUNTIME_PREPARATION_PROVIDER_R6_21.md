# Cooperative production R6.21 — durable runtime preparation provider

Status: `TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED`. Authority effect: `NONE`.

R6.21 binds the R6.20 prepare-only adapter to the existing R6.9 durable RuntimeAdmission source and to the existing R6.16 control-plane materializer.

It does not add a new PDP, authority source, scheduler, provisioning engine, runtime executor or artifact writer.

## Why R6.21 exists

R6.20 can issue one exact RuntimeAdmission through the existing `RuntimeAdmissionEngine.admit_bound_action(...)` and compose `CooperativeRuntimeContext`. R6.16 intentionally refuses to trust that context as the sole RuntimeAdmission source: the exporter independently calls a canonical `RuntimeAdmissionSource.resolve(...)`.

R6.9 already provides the durable owner: `SQLiteRuntimeAdmissionSource`. It stores immutable sealed RuntimeAdmission records with independent provenance, append-only publication and no authority issuance.

## Durable sequence

```text
canonical assignment readback
→ R6.20 pure preflight
→ journal PREPARING
→ existing RuntimeAdmissionEngine
→ sealed RuntimeAdmission
→ journal PREPARED
→ SQLiteRuntimeAdmissionSource.publish
→ durable admission readback
→ journal PUBLISHED
→ reconstruct CooperativeRuntimeContext from durable admission
→ PreparedCooperativeContextSource
→ existing R6.16 materializer/exporter
→ canonical HELD-to-READY scheduler transition
```

No artifact bytes are written during this preparation sequence.

## Recovery semantics

The preparation journal lives in the same private runtime-state SQLite file as the existing R6.9 admission source, but it is not an authority source.

States: `PREPARING`, `PREPARED`, `PUBLISHED`, `ADMISSION_ISSUANCE_UNKNOWN`.

`PREPARED` stores the exact already-sealed admission. A restart after PREPARED can finish publication without calling RuntimeAdmissionEngine again. A restart after durable publication but before the PUBLISHED journal transition resolves the existing admission, verifies exact equality and completes the journal transition.

The narrow crash window after runtime-admission replay consumption but before PREPARED becomes durable cannot be safely auto-replayed. The assignment remains HELD and the provider classifies the state as `ADMISSION_ISSUANCE_UNKNOWN`. No automatic retry and no artifact execution follows.

## Preflight before journal

All pure assignment/proposal/provisioning/sandbox checks run before PREPARING is inserted. Invalid state, target, payload, generation, provisioning, dispatch or sandbox evidence therefore cannot consume replay or create a false UNKNOWN journal.

## Durable reconstruction

R6.20 also exposes a reconstruction path for an already-issued trusted admission. A durable RuntimeAdmission plus exact original Action/PDP/currentness/provisioning evidence and the same HELD assignment is re-bound to the same RequestedRuntimeEffect/runtime identity and reconstructed into the same CooperativeRuntimeContext without touching the replay guard.

## R6.21 → R6.16 vertical acceptance

The integration test uses current Mission Control storage/migrations: `missions`, `mission_process_specs`, `operator_control`, `execution_driver` and `global_scheduler`.

```text
current HELD WRITE
→ R6.21 durable provider
→ durable RuntimeAdmission
→ R6.16 context carrier
→ R6.15 provider evidence export
→ canonical scheduler evidence record
→ HELD-to-READY
```

The R6.16 exporter reads the same durable admission independently. All seven provider evidence classes are present exactly once. The artifact root remains empty.

## Validation

At the R6.21 candidate boundary the combined cooperative/runtime regression is `287/287 PASS`; compileall and git diff checks pass.

## Remaining boundary

The runtime source chain is now complete enough to author a current-source successor:

```text
HELD assignment
→ R6.21 durable preparation
→ R6.16 provider export
→ R6.17 worker qualification
→ worker runtime installation
→ current scheduler claim
→ artifact WRITE
→ distinct verifier
→ reconciliation
```

The next increment should therefore be a finite current-source Mission Program/LPCL successor for the first live SaaS + LOCAL + material-worker artifact loop. Mission activation remains a separate operator action.
