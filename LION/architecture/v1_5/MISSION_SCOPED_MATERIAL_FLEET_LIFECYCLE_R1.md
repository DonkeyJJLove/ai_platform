# LION mission-scoped material fleet lifecycle R1

Status: **source candidate, not deployed; no runtime effect**. This increment extends the existing Mission Control scheduler and phase-contract model. It does not install a second scheduler, launch an LPCL mission, mint RuntimeAdmission, create material workers, or replace the historical Docker image.

## Observed problem

On MOON on 2026-10-08 the existing R24 `lion-r24-autonomy` fleet consisted of 32 uniquely identified containers `MD001–MD032`. Every worker was alive and reporting a recent heartbeat, but its source HEAD was historical `bdd2ba1632511617724dad7ab7066cc01f94f4a7`, not the then-current integrated `e0e979d5affca433743dc3eb2db8ed7cc7b40374`. Mission Control had zero active scheduler runs and no active assignments for nonterminal missions. A bounded real canary created and removed two isolated ephemeral containers, and the operator-scoped idle park stopped exactly the 32 historical containers without deleting them. Readback: 32 exited, ready 0, original identities preserved.

This matters because `tools/lion_mission_control_v3.py::bind_lpcl_execution` currently invokes `_docker_local_model_currentness(32)` **before** selecting and executing the first phase of a Docker-local-model LPCL mission. That is a valid full-fleet safety gate for the legacy binding but is incompatible with the newer Application Factory phase order: cognitive reconnaissance with zero material workers, one-worker preactivation, and only then full-fleet readiness. Deleting this gate would be unsafe; leaving it unchanged makes early phases wait for workers they should not require.

## Implemented source increment

The new `cyber_lion/mission_control/material_fleet_lifecycle.py` is a non-effectful read-only projection over the original Mission Control database and externally supplied canonical fleet currentness. It derives desired **cardinality** from the stored, independently compiled `PhaseExecutionContract` and verifies the *entire contract digest*. It does not guess from the phase name or infer permissions from a Docker label.

The demand mapping is: `CONTROL_PLANE_RECONNAISSANCE → 0`, `COOPERATIVE_WORKER_PREACTIVATION → 1`, `COOPERATIVE_ARTIFACT_BOOTSTRAP → 32`, `COOPERATIVE_ARTIFACT_PRODUCTION → 32`, `COOPERATIVE_ARTIFACT_VERIFY → 32`, and reconciled terminal state `→ 0`. The material count never becomes an execution permit by itself.

The projection reads exact mission and LPCL digests, declared phase contracts, current phase, driver lease/generation, operator pause/stop state, scheduler freshness, mission-scoped and cross-mission outstanding assignments and material leases, and the digest/age/identity of an optional fleet-currentness carrier. It never writes the database. A digest-valid fresh observation of 32 `exited` workers produces `PARKED_OBSERVED`; this is a source-observation class, **not** a canonical `PARKED` runtime state or authorization. A historical fleet source cannot be presented as ready for an exact new mission.

The standalone read-only operator entrypoint `tools/lion_material_fleet_lifecycle_probe.py` projects an existing canonical Mission Control SQLite database via `mode=ro` and `PRAGMA query_only=ON`. Optional fleet observation is loaded from a bounded JSON file. Its `--fail-if-blocked` mode exits nonzero on `BLOCKED`/`UNREGISTERED`. It deliberately supplies `current_source=None` until a trusted *deployed runtime* source-currentness provider is integrated. The resulting `CURRENT_RUNTIME_SOURCE_UNVERIFIED_OR_DRIFT` blocker is correct: local Git HEAD or GitHub `master` alone cannot attest the running Mission Control package. The CLI never issues claims, registration, phase transitions, Docker operations, or authority decisions. Every result has `effect_admitted=false`, `authority_effect=NONE`, `execution_effect=NONE`, and a canonical `projection_digest`.

The existing installed `tools/lion_mission_control_v3.py` is intentionally **unchanged**. A first direct HTTP-route integration attempt was rejected by exact-package staging tests: the pinned `mission_control_v3.py` hash changed and the new module was absent from the historical 91-file deployment closure. The source edit was reverted. The versioned deployment package must be rebuilt and tested as a new successor release rather than rewriting historical package manifests or weakening security tests.

## Required follow-on effect integration

The next implementation must connect this pure demand projection to the **existing** LPCL activation/execution binder and to an independently admitted mission-scoped Docker provider. It must not start MD001 on registration, nor pretend the first phase has full-32 binding. The one-worker preactivation only qualifies a source-pinned runtime; artifact production requires separately qualified MD001 and MD002 roles and the full canonical provider across 32 workers. The owner must reconcile non-idempotent writes, effects, admission consumption, pending work and other mission ownership before stopping shared workers.

Deployment also requires exact release/source attestation and an operator-launched LPCL bound to its mission, generation, conversation, and effect scopes. The historical `bdd2ba…` Docker fleet is parked; it must not be auto-restarted under the new `e0e979d…` mission identity. Existing Mission Control, Windows canonical `8780` writer and MAT12 helpers remain outside fleet lifecycle effects.

## Validation and evidence boundaries

The source test suite verifies the 0/1/32 mapping, canonical contract digest checks, LPCL authority-state gate, current source mismatch, freshness, unique worker identity, operator containment, exact driver binding, foreign mission work/leases, terminal reconciliation and immutability. The standalone probe rejects missing and symlinked databases, malformed carrier JSON, unverified caller-supplied source flags and blocked results, while verifying byte-for-byte database immutability. An independent read-only run against the real LION-AUTH-LAB Mission Control SQLite confirmed that historical Pilot R1/R3 remain blocked and the future Application Factory mission is not registered. No live LPCL activation or Docker workload was dispatched by this increment.

Prior host receipts are kept separately under `/srv/lion-e4-candidate-r1/outputs/LION_FLEET_LIFECYCLE_CANARY_20261008.json` and `/srv/lion-e4-candidate-r1/outputs/LION_FLEET_PARK_20261008.json`; they are evidence of the previous scoped test and idle park, **not** evidence of a deployed phase-aware controller. Exact test and branch evidence for this source increment must be recorded against its own HEAD/TREE rather than those historical runtime receipts.

## Stop boundaries

Do not merge this candidate as if it fully deployed a lifecycle controller. Do not register or activate Application Factory implicitly, re-start the 32 historical worker IDs to paint `READY`, clear historical material leases, override a Windows ThreadStore owner, mutate the protected `master`, or touch the unrelated PR #429. The next operator launch remains through the established LPCL/Mission Control path.
