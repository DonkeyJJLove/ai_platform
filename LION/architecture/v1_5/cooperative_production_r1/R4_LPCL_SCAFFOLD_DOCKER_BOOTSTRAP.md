# R4 – mission-bound cognitive scaffolding and deterministic Docker fleet preflight

Status: **SOURCE CANDIDATE – NOT INSTALLED / NOT ACTIVATED**. Base: `ai_platform:master@e0e979d5affca433743dc3eb2db8ed7cc7b40374`. Operator owns future LPCL launch. This source increment changes neither the live Mission Control DB nor the Windows Desktop runtime; it does not start, stop or recreate a container. It retains the original global scheduler and authority/effect engines.

## Verified AS-IS and critical ownership

`local_intelligence_gateway.Gateway.prepare_cognitive_sync` obtains an exact Mission Control mission, canonical conversation binding and `SynchronizationCheckpoint`. `conversation_chat.submit_chat` is the existing LOCAL/SAAS/DUAL dispatcher; `CanonicalConversationSaaSConsumer` is the existing durable SaaS delivery consumer. The current implementation can deliver model responses without authorizing a worker. `SynchronizationCheckpoint.to_dict()` previously returned Python tuples where the independent JSON contract requires arrays; this source candidate fixes the direct in-process wire projection.

`global_scheduler.bind_dynamic_local_model_fleet` is the existing 32-worker Docker topology binder for any supported logical count (including 8). `tools/lion_mission_control_v3.bind_lpcl_execution` consumes `_docker_local_model_currentness()` only **after an exact activated LPCL**, and currently demands a fresh `READY` 32-worker observation before binding. It does not create or launch the fleet when the 32 containers are absent or stopped. `LION/runtime_compat/r24/docker-autonomy/materialize.py` is the existing physical materializer; its confirm identity is hard-wired to an older R24 64/32 mission, and it modifies/removes existing runtime source/status directories. It must not be called as a generic bootstrap for an unrelated 8/32 LPCL.

R24 uses Docker Desktop Linux containers through Compose project `lion-r24-autonomy`, **not an active Docker Swarm cluster**. The submitted PDF reports contain historical architectural proposals, including sometimes conflating Docker Swarm, models and transport; those claims are not substituted for the current exact source or MOON observation.

## Executed reconnaissance on MOON

Read-only `docker compose config --format json` exposes 32 services, `worker-01..worker-32`, with container identities `lion-r24-md001..032`, read-only roots and the declared `LION_MATERIAL_EXECUTOR_V2` label. `docker inspect` observed **32 stopped containers**, all `exited` with code 137, `OOMKilled=false`, Compose project `lion-r24-autonomy`, one image ID. Neither the exit code nor these labels prove why they stopped or justify automatic restart.

The existing runtime `identity.json` declares `source_head=bdd2ba1632511617724dad7ab7066cc01f94f4a7`; the retained `materialization-receipt.json` declares `source_head=8bb1916eab50dcea847549092d77103da11397a2`. They disagree with each other and with current master. **This cohort is not an admitted restart candidate**. The read-only classification reports `BLOCKED: RUNTIME_SOURCE_OR_RECEIPT_DRIFT` with no Docker effect.

## Candidate – bounded cognitive projection

New `mission_cooperative_scaffold.py` consumes the already-validated Mission Control LPCL bytes and SHA, exact source HEAD/TREE, canonical conversation `mission_id`, `conversation_id`, `binding_epoch`, binding context, source objectives, fleet targets and phase execution contracts, plus the exact strict synchronization checkpoint. It emits a common scaffold digest and two **distinct** LOCAL/SAAS role projections with independent projection and scaffold-byte digests. Both projections have `authority_effect=NONE`, never install a capability or worker. Model output remains proposal-only.

The existing `prepare_cognitive_sync` now composes this scaffold for the first bounded DUAL synchronization turn (neutral ANALYST/ANALYST roles in bootstrap, not hard-coded builder/verifier by provider geography). `conversation_chat.submit_chat` checks the immutable identity and decoded source-bound projection **before** calling either provider. It places the relevant scaffold inside the existing SaaS `_saas_prompt` before conversational history and prepends the LOCAL scaffold to the existing LOCAL request. It does not add a second conversation/queue; all existing request/correlation/causation/context and external-bridge identity remain owned by the canonical stack.

**Remaining cognitive binding:** Current synchronization must be exercised against a newly operator-bound LPCL after panel staging, and phase-specific role/context projection must be refreshed for every later provider call. A successful model reply alone must not set `cognitive_readiness=READY`; the existing readiness validator requires current actual payload/response digests and a valid synchronization checkpoint.

## Candidate – deterministic material fleet plan

New `docker_local_fleet_plan.py` accepts exact mission LPCL and the already-resolved R24 Docker Compose configuration. It derives all 32 worker identities and the current binder's round-robin mapping for N logical drones; N=8 maps LD001–LD008 to MD001–MD008 while 24 material workers remain available. The plan has explicit admission and identity-reacquisition requirements, but **cannot run Docker**. Its observer compares sealed `fleet-currentness.py` source evidence separately from host/engine transport evidence; unsealed labels are at most a structural observation.

`classify_existing_docker_runtime` distinguishes `ABSENT`, `STOPPED_COHORT`, `RESTART_CANDIDATE`, `OBSERVED_RUNNING` and `BLOCKED`. A stopped cohort requires exact original identity/receipt consistency and currently bound mission source, or it is blocked. No plan text, `docker ps` output or model instruction can bypass current authority and admission.

## R4.2 source candidate – one-shot admitted Docker effect consumer

`cyber_lion/mission_control/docker_fleet_bootstrap_executor.py` now supplies
`DockerFleetBootstrapExecutor` and the concrete
`MoonDockerComposeRuntime` restricted to the existing R24 prepared runtime
root and Compose project. The executor consumes *already issued* canonical
`RuntimeAdmission`, `RuntimeIdentityBinding`,
`RequestedRuntimeEffect`, `RuntimeAdmissionSourceTrustBinding` and exact
`LiveAdmittedAuthority`. Its existing-owner
`LiveAuthorityAdmission.revalidate()` is mandatory at effect time.
A distinct `SQLiteAdmissionConsumptionGuard` may provide durable one-use
consumption; the consumer never constructs PDP ALLOW or mints authority.

Only `DOCKER_FLEET_BOOTSTRAP` on the literal resource
`docker://MOON/lion-r24-autonomy` and executor
`LION_R24_DOCKER_BOOTSTRAP_EXECUTOR` are accepted. Runtime preflight rereads
the current mission and its `EXPLICIT_USER_ACTIVATION`, admission, source
manifest, Compose bytes, exact 32 worker identities, Docker image identity,
and the bound runtime attestation digest before consuming the admission.
The strict installed Compose policy checks read-only worker roots, dropped
capabilities, no-new-privileges, CPU/memory/PID ceilings, exact bind mounts,
per-worker private directories, and denies host networking or Docker socket
mounts. Source, Compose configuration, Docker image attestation and inventory
are reobserved just before durable admission consumption.
The effect command is strictly `docker compose -p lion-r24-autonomy
-f <verified-runtime>/compose.yaml up -d --no-recreate`, not a shell
expression or model-generated argv. After effect, up to 90 bounded **read-only
currentness polls** require all 32 per-worker heartbeats and source-matched
currentness. A saved outcome `OBSERVED` requires the full readback. Otherwise
the admission stays consumed and the receipt is
`EFFECT_UNKNOWN_RECONCILE`; automatic repetition is forbidden.

The materializer **does not repair or overwrite** the historical
inconsistent runtime. Because the stopped R24 cohort's saved runtime identity
and materialization receipt have different source SHA, the candidate correctly
denies effect before launch. A second read-only test of the installed MOON
Compose configuration returned `WORKER_MOUNT_COUNT_DRIFT:worker-01`:
that historical runtime has 5 mounts per worker while the current repository
source defines 10 (including private cooperative workspace and provider/control
mounts). Neither source nor mount restrictions are weakened for the old fleet.
An authorized fresh, non-destructive staging owner must prepare exact source
bytes and a matching receipt before either `ABSENT` or
`RESTART_CANDIDATE` is usable.

**This is not yet a deployed or registered capability.** Missing composition
edges are: (1) operator-activated LPCL's actual action/PDP/provisioning
owner issues the new typed `DOCKER_FLEET_BOOTSTRAP` effect and publishes a
current RuntimeAdmission, (2) the existing mission driver publishes one
durable effect assignment and exact runtime identity to this one-shot
consumer, (3) the trusted MOON host executor and its admission source/guard
are installed and admitted, and (4) the observed 32-worker receipt is
consumed by the existing `bind_dynamic_local_model_fleet` before the phase
advances. The existing `RuntimeExecutionEngine` has a *different closed*
sandbox action vocabulary; silently disguising Docker `up` as `RUN_TEST`
would violate the intended effect class. Neither this document nor this
source candidate installs an alternative global driver, authorization
engine, broker, queue, or external permanent daemon.

Tests use synthetic typed admission/provisioning fixtures and a fake Docker
runner; they test gating/replay/unknown outcomes and the exact argv but do
NOT establish that the running canonical PDP can issue this effect for an
operator-launched LPCL. That integration is the next concrete source change.

## Other essential closures before autonomy

- **Mission driver progress:** one durable scheduler driver and capability registry. `REGISTERED` is not `ACTIVE`; `VALID_WITH_DYNAMIC_BINDING` is not `READY_BOUND`.
- **Operator launch and continuity:** exact LPCL activation event, fresh `mission_id/source_head/tree/spec_digest`, stable `conversation_id/binding_epoch/lane_id`, separate LOCAL/SaaS projections and actual sent-payload byte digests. Current model agreement is not independent verification.
- **Worker task route:** producer must issue a real, idempotent assignment to MDxxx; material executor must claim the current lease generation, execute the admitted sandbox action, commit a receipt and return a verified artifact under its immutable workspace identity. The coordinator must reconcile before phase completion.
- **Sandbox and artifact exchange:** two bounded workspaces, exact content bytes and source-based artifact carrier. A SaaS chat filesystem is not the MOON host filesystem. Reuse existing `artifact_transfer.py` after binding the real producer/consumer to assignment and receipt.
- **Restart and recovery:** recover pending SaaS SEND_UNKNOWN, stale Docker source, claim lease expiry, duplicate effect, host failure, and model interruption without double execution. Failure/UNKNOWN is a terminal or waiting condition until new evidence.
- **Independent panel acceptance:** register a new mission from LPCL Panel, run the actual sync and inspect delivery/readiness, then operator-activate the exact version and observe real Docker workloads. Only actual returned bytes and readback, never historical Cluster Observatory cards, may close the mission.

## Targeted test evidence and explicit limits

Tests for the scaffolding, 32-worker plan and admitted one-shot effect consumer include mission LPCL digest substitution, wrong binding/epoch, modified scaffold bytes, independent provider prompt routing through existing submitter, strict sync JSON serialization, exact 32-service Compose structure, wrong runtime, duplicate IDs/incorrect Compose project, stopped cohort/restart-vs-block decisions and unsealed currentness are in `cyber_lion/tests/test_r4_mission_scaffold_docker_plan.py`. The current source suite and original LPCL suites run independently. Docker Compose parsing and Docker inspect were executed **read-only**. No new worker was started and no operator activation was consumed.

**First next step:** wire the exact `DOCKER_FLEET_BOOTSTRAP` capability into the original operator-authorized phase/action/PDP/provisioning and execution driver path; provision new immutable runtime source evidence, install the one-shot MOON consumer using the existing durable admission store, and independently read back the 32 worker heartbeats and assignment/receipt ledger after an operator-launched new LPCL. Do not label current source-only tests a passed live material roundtrip.


## PR #435 current-candidate effect inventory reconciliation

GitHub Core workflow on the first published candidate correctly stopped in the
**full 4,191-test suite**: three tests still expected the predecessor's exact
production source path count and effect-surface lineage. Historical P0 remains
unchanged: 567 frozen surfaces. Current R4 introduces precisely three
production modules (mission scaffold, Docker fleet plan, Docker effect
consumer), so the source scan changes from 424 to **427** production files.

Current source effect-surface count stays **573**, unresolved refs **0**.
The compared P0-current delta contains 547 shared historical surfaces, 26
new location-derived records and 20 superseded locations. Six are the
previously explicitly owned cooperative-runtime preparation writes; five
control-plane-reconnaissance SQL callsites moved by +22 source lines, and
15 conversation-chat SQL callsites moved by +1 due to the new scaffold
import. Neither new module contributes a new scanner-recorded
`persistent_state.write` surface. The 15 conversation SQL calls were
independently paired with their historical entrypoints and their **71 total
`conn.execute` AST expression trees** hash-identically to the exact
master predecessor `e0e979d5affca433743dc3eb2db8ed7cc7b40374`.
This excludes a hidden SQL mutation being disguised as a harmless LOC move.

The tests `test_host_authority_separation.py` and
`test_p0_current_candidate_inventory_delta.py` now pin this *exact* new
candidate epoch and verify the provider, class, target, line displacement,
and AST fingerprint. This is a source currentness reconciliation, not
new approval, mediation, or an assertion of new runtime execution.
