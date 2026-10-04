# Cooperative production R4 — canonical per-assignment runtime composition

Status: TESTED_SOURCE_CANDIDATE. This is not a deployment, live mission completion or a new authority source. Parent publication: `95f44213ca85c67660b6505e22d9153a754970e8` in PR408. R1 byte transport and R3 model-generated readiness corpus remain preserved.

## Implemented connection

`cyber_lion/enterprise/cooperative_runtime_composition.py` supplies `CooperativeRuntimeContext` and the concrete `CooperativeRuntimeWriterProvider`. The provider is the trusted `admitted_writer` dependency of `tools/lion_cooperative_worker_adapter.py`; it is never taken from a model-controlled payload.

The implemented call path is:

```text
cooperative_assignment_once
  -> validated claimed assignment and exact original input digest
  -> CooperativeRuntimeWriterProvider
  -> trusted per-assignment CooperativeRuntimeContext
  -> CanonicalCooperativeWriter
  -> RuntimeExecutionEngine
  -> EffectTimeCurrentnessGuardedSandbox
  -> ExecutorSandbox
  -> CooperativeArtifactBackend
  -> atomic no-replace artifact publication and byte readback
  -> canonical runtime receipt + effect-time currentness evidence
  -> existing assignment receipt interface
```

The context must already contain the admitted request/effect/runtime identity, exact provisioning and fleet dispatch, one-file write scope and sandbox runtime binding. The provider uses the existing canonical authority revalidator immediately before the effect. Revocation, changed policy, lost observability, stale dispatch, expired claim or substituted identities deny the operation. No admission is minted here.

Replay guards and budgets are supplied by the long-lived trusted composition root. Creating another provider must not reset them. Tests reconstruct a provider with the existing SQLite single-use guard and prove that a consumed admission cannot be used again. A failed effect-time check also does not silently restore a consumed admission. Unknown receipt delivery is not converted into a second write or a contradictory replacement receipt.

`cooperative_artifacts.py` publishes Linux-private-root files without replacing an existing artifact. Descriptor-relative operations reject symlink traversal and non-private hardlinked results; concurrent publication preserves the winning writer's bytes. This is not isolation against a malicious process sharing the same UID or a writable mount. The shared R24 `/gate` directory is not silently promoted to a production workspace boundary. Production provisioning still needs worker-owned storage and a bounded verifier transfer/read path.

## Executed validation

The new composition has 25 tests. The preserved development worktree passed 164 selected tests. A separate publication projection, based on the exact remote parent and only the selected files, passed 153 tests with zero failures, errors or skips. The difference is 11 tests of the still-unpublished prototype stepper/server integration, not removed failing tests. These are selected suites, not the full repository suite.

The exact composition and writer tests also ran in both existing containers `lion-r24-md001` and `lion-r24-md002` on MOON Docker Desktop: 36/36 passed in each. The staged import closure contained 58 files and 539869 bytes; source hashes were checked inside each container before testing. Each run used UID 65532 in a fresh `/tmp/lion-coop-r4-*` workspace. The original worker processes were not restarted and no live assignment queue was consumed.

These container executions are real, but their authority/currentness sources are explicitly synthetic test fixtures. They prove that the original adapter, enforcement layers and real filesystem compose under the tested conditions. They do not prove live authority issuance, the full panel-to-artifact path, independent failure domains, or general sandbox security. No new model call was made by R4. R3's separate real local-model generation/review and published readiness corpus retain their original scope.

See [R4 validation and checkpoint](RUNTIME_COMPOSITION_R4_VALIDATION.json). Reproduce the new focused suite from a Linux checkout:

```sh
python3 -B -m unittest cyber_lion.tests.test_cooperative_runtime_composition -v
```

## Remaining live integration, not a WAIT workaround

The observed R1 mission was `AUTHORIZED / NOT_STARTED`, without an execution driver, with `LPCL_EXECUTION_BIND:ValueError:lpcl execution adapter cardinality`. Its original 2-logical/32-material specification was not replaced by the unlaunched R2 candidate. The live registry did not advertise the cooperative providers. Neither LPCL syntactic validity nor waiting for those names creates an executor.

The next implementation boundary is the existing control-plane resolver of `assignment_id -> CooperativeRuntimeContext`: bind a real canonical admission, exact deployed executor/workspace, current dispatch, independently configured trust inputs, and existing persistent consumption/budget state. Then inject this provider into the admitted worker composition. The resolver must not reuse F009 proof constants or create an ALLOW from the artifact payload. The original Mission Control topology/preflight must also be corrected or replaced through an explicitly launched successor before the live pilot can execute.

The broader candidate `cooperative_production.py`, worker-profile/server modifications and R1/R2 LPCL files remain preserved in the original development worktree, but are not shipped by this selected source increment. In particular, production must not be called from the read-only generic executor. No daemon, new scheduler, new PDP, live DB migration, runtime rollout, merge or automatic next-mission activation is introduced here.

## Source and continuation record

The focused semantic review covered the cooperative artifact primitive, claim adapter, canonical writer and composition; original runtime execution/currentness and sandbox contracts; the relevant global-scheduler claim/receipt functions; and the corresponding tests. The 58-file staged import closure is byte coverage for execution, not a claim that all 58 files received a complete semantic audit. Full ai_platform/peer documentation review remains outside this completed increment.

Development worktree: `/srv/lion-e4-candidate-r1/cooperative-production-20261004-r1`. Clean publication projection: `/srv/lion-e4-candidate-r1/cooperative-publication-r4`. Actual logs, source manifest and container reports are retained under `cooperative-transfer-evidence/continuation-r4/` in the development worktree. Preserve PR407, PR408's previous commits and all unrelated worktrees.
