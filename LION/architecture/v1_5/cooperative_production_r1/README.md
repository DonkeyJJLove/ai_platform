# Cooperative production R1 — artifact transfer primitive

Status: SOURCE_CANDIDATE. Not installed in the running worker, panel, scheduler or Docker fleet. This increment implements the bounded artifact carrier and fresh-workspace receiver needed by the cooperative-production program. It does not implement the complete production system.

## Implemented

`cyber_lion/mission_control/artifact_transfer.py` supplies `create_bundle`, `verify_bundle`, `materialize_bundle`, `verify_workspace` and a `verify`/`materialize` CLI. Exact bytes, including binary content and UTF-8/CRLF, are carried with per-file and whole-transfer hashes. The receiver requires an independently supplied expected binding and digest. This transport binding references repository/source, mission, assignment, conversation, epoch, generation, lease generation, context, projection, request and producer. Test identities are fixtures, not live Mission Control identities.

Materialization creates a fresh workspace, writes a final carrier, and reads the bytes back. It never overwrites an earlier workspace. Repeated calls intentionally create distinct workspaces; this is NOT exactly-once delivery. A partial write is not a completed transfer. Consumers must retain and reconcile their assignment/receipt using the existing ledger.

Limits: 64 files, 128 KiB per file, 512 KiB aggregate payload, 800000 bytes per bundle. ASCII portable filenames are intentional; file content is binary-safe. Rejects traversal, Windows reserved names, case collisions, duplicate JSON keys, substitution and malformed/oversized payloads. No archive extraction, shell evaluation, code execution, network listener or credential handling is introduced.

## Boundaries

This carrier is not sbom/AID, an authorization grant, a lease validator, a secret-content scanner, an artifact publisher or a new scheduler. Expected binding must come from the existing trusted control-plane consumer, not be copied from an untrusted carrier. Filesystem operations require a private caller-controlled parent: resistance to concurrent malicious filesystem mutations by the same user is NOT established. Large resumable transfers, retention and runtime sandbox execution are not implemented by this bounded inline profile.

## Validation

Thirty distinct tests run successfully in the assistant sandbox, Ubuntu on MOON and native Windows Python on MOON. Windows testing used the actual Windows interpreter, not a mocked encoding stream. See VALIDATION.json. These are byte-transport/component tests, not T01-T12 production acceptance or independent model evaluation.

## Existing owners and next integration

Existing R24 `material_contract_assignment_once` remains the worker consumer; `material_worker_runtime.py` remains the capability/identity contract. `execution_driver.py` remains the mission cursor owner. No production call site is wired to this new module yet. Read the complete assignment producer, receipt-fencing tests, R24 materializer and currentness consumer before changing the advertised worker profile. Add the bundle consumer through that existing assignment/receipt path, then compile and test the actual LPCL ingress.

This increment supports the artifact-exchange part of B02/C02 and acceptance T04/T05/T11 from the cooperative-production requirements; it does not close those acceptances. A00/PR407 and unfinished A01 remain preserved. No merge, live DB migration, engine restart, fleet mutation, new model session or mission activation is performed by this source increment.


## Later source evolution — R6.18/R6.19

Subsequent source candidates advance beyond the initial R1 carrier boundary without rewriting this document's historical R1 claims.

[R6.18 process bootstrap](COOPERATIVE_PROCESS_BOOTSTRAP_R6_18.md) supplies the missing fail-closed Mission Control process-composition install path for the existing cooperative materializer registry. Default mode remains UNBOUND; no authority, assignment or runtime effect is created by source integration.

[R6.19 functional acceptance](COOPERATIVE_FUNCTIONAL_ACCEPTANCE_R6_19.md) updates the historical R6.17 fixture to current scheduler storage and proves the isolated chain R6.16 release → R6.17 qualification → current scheduler claim → material write → distinct MD002 verification. This is functional source acceptance, not live deployment acceptance. The live R24 fleet remains a separately observed state.


[R6.20 runtime preparer](COOPERATIVE_RUNTIME_PREPARER_R6_20.md) adds the missing prepare-only composition edge from exact HELD cooperative WRITE + existing Action/PDP/provisioning/sandbox evidence into `CooperativeRuntimeContext`. It delegates admission to the existing `RuntimeAdmissionEngine.admit_bound_action(...)`, exposes no execution surface, and feeds the existing R6.16 materializer through an immutable prepared-context source.

[R6.21 durable preparation provider](COOPERATIVE_RUNTIME_PREPARATION_PROVIDER_R6_21.md) binds R6.20 to the existing R6.9 `SQLiteRuntimeAdmissionSource` and the existing R6.16 materializer. It journals `PREPARING → PREPARED → PUBLISHED`, reconstructs from an already-issued durable admission after restart, and classifies the narrow post-replay/pre-journal crash window as `ADMISSION_ISSUANCE_UNKNOWN` with no automatic retry.

[R6.22 preactivation](COOPERATIVE_PREACTIVATION_R6_22.md) adds one fail-closed `COOPERATIVE_WORKER_PREACTIVATION` capability before the 32-worker readiness gate. It drives a qualification-only HELD WRITE through R6.21/R6.16/R6.17, stores the result in the existing mission artifact ledger and never claims or executes that assignment. Production and verification readiness rules are unchanged.
