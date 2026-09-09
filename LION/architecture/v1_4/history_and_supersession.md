# LION v1.4 — history, supersession and falsification boundaries

This directory preserves history while allowing evidence-bound v1.4 reconciliation. It does not rewrite v1.3, v14c2 or prior RAG32 records. Historical claims remain historical unless reacquired from live Git/source/test evidence.

## Superseded currentness

`LION/status.json` remains a historical E003-era projection whose `CURRENT` label is stale relative to live `master`. R23 does not silently rewrite that consumer-sensitive state file. For v1.4 documentation currentness, use `current_state.json` and its explicit default/candidate evidence semantics.

## R22C–R22H source/truth lineage

R22C introduced the full-symbol-census workflow and implementation. Literal reconstruction of `host_authority_separation._production_path` falsified an inherited assumption: `.github/workflows/*.yml` and `*.yaml` are production sources, while Python under `cyber_lion/tests/**` is excluded from the production source set. The master production source count is 256. The R22H candidate observation contains four production additions and no removals, yielding 260 sources.

The two later R22F production additions are `cyber_lion/contracts/action_runtime_binding.py` and `cyber_lion/contracts/model_plane_adapter.py`. Exact Core inventory on the R22H lineage observed 236 effect surfaces and six raw unclassified references, with the taxonomy layer resolving all six without hiding them. This is explicit source-set identity drift with stable effect surface, not evidence that source changes can be ignored.

R22G repaired only literally proven stale source-count/scan pins and the same-tree regression fixture. R22H then completed documentation reconciliation and carrier-last binding on the frozen noncarrier tree. Historical R22H subject digests remain historical and are not reused after later R22I noncarrier changes.

## R22I — governed Action runtime binder consumption

R22I started by falsifying whether `RuntimeAdmissionEngine` already consumed the exact output of `bind_allowed_action_to_runtime_inputs`. It did not: the existing admission path independently accepted `gate`, PDP receipt, effect and runtime identity, while canonical PDP evidence was separately resolved. The missing frontier was therefore exact binder-output consumption, not a missing runtime admission engine.

R22I materialized `RuntimeAdmissionEngine.admit_bound_action` as a high-level governed path. It invokes the existing inert binder, verifies the returned `CanonicalPDPDecisionEvidence` against the canonical PDP source, and passes the exact binder-produced `RequestedRuntimeEffect` and `RuntimeIdentityBinding` into the existing `admit` primitive. It does not create a new executor, provider, generic effect entrypoint, authority source, secret-resolution path or deployment path.

Falsification then exposed a narrower contract gap: the earlier `RuntimeBindingCurrentness` did not bind the exact `ProvisionedExecutor` digest. A coherent alternate provisioning tuple could therefore remain internally self-consistent. R22I closes that gap with `provisioned_executor_digest`, so coherent provisioning substitution is denied by trusted currentness rather than only by incidental field mismatch.

The R22I regression matrix proves exact allow consumption and fail-closed behavior for DENY, stale currentness, action/resource/payload/authority/mission/provisioning/runtime-identity/PDP-receipt substitution and replay. The high-level path accepts no caller-supplied effect or runtime identity and adds no alternate effect surface. On exact candidate `b4045878be064586a61efa0f3ec8be5103a5a08c`, all R22I tests pass. Core ran 2283 tests with exactly one failure and two skips; the sole failure was the intentionally stale truth carrier (`CHECKOUT_SUBJECT_DIGEST_DRIFT`).

The same exact pre-documentation observation preserved production source count 260, effect surfaces 236, six raw unclassified references and zero reconciled unclassified references. The production scan digest is `c643ab174bec81dc86fde535be72230c88cfc557a2ca5596f9362db259d02724`. Global complete mediation remains `UNKNOWN`.

## Model plane / ASTRA

`cyber_lion/contracts/model_plane_adapter.py` is a provider-independent contract with ASTRA as a compatibility target. It does not select a provider, configure an endpoint, read a secret, execute inference, deploy a runtime or mint authority. ASTRA runtime remains `NOT_OBSERVED`.

## Factory claims

B0 remains a bounded PASS for two unseen problem families inside its closed grammar. R22F added a counterexample outside that grammar (`float-list`), which is rejected with `GenerativityProtocolError`. Therefore general Factory generativity is explicitly falsified outside the B0 grammar rather than inferred from bounded success. Activated child autonomy and Factory-of-Factories remain unproven; real child activation remains a human-authority boundary.

## Federation drift carried from R22H

The last explicit live federation sweep remains the R22H ten-repository vector. R22I does not promote that historical sweep into a new federation observation and does not change registry membership, default-branch assignments or repository authority. Federation reads grant no authority and produce no runtime effect.

## Truth-carrier rule for R22I

All R22I production, test and documentation mutations are noncarrier work. Only after that work is verified and frozen may the truth subject be recomputed while excluding exactly `LION/architecture/canonical-state-v1-3-candidate.json` and `cyber_lion/registry/repositories.json`. Those two carriers must then be the contiguous final repository-file commits. After the second carrier commit no repository file may change; only readback, exact-head verification and PR metadata are allowed.

## Human authority boundaries

R22I preserves `R22E-HAB-BRANCH-MAINTENANCE-001`, real child activation, mark-ready, merge, RAG publication, runtime deployment and production deployment as boundaries outside this autonomous repository-documentation/truth-reconciliation lane.

## R23 — frontier consolidation and process-plane reconciliation

R23 reconstructed the live candidate graph from master `67a4f8243aa6805e47035e572bd458f73fd0b358` and consolidated the R21 LPCL/Process lineage, R21/P0 TEST_ONLY materialization lineage and the R22C→R22H→R22I governed Action→Runtime lineage into one short-lived integration train. The merge conflict set was currentness/truth-carrier material rather than contradictory implementation semantics. Recomputing the combined production set yielded 268 production sources, 236 effect surfaces, six raw unclassified references, zero unresolved taxonomy references and scan digest `5f6561edcd368c2acce5f0e216bc9e21324da2913035e92ef175b7aca5b773a2`; neither predecessor scan digest was reused as current truth.

The exact pre-documentation candidate `5f90f1c11e9f997ed9c5e3ac1b02c6d802d15745` / `5dd5dc653c24bdd810faeb61f901328ad246e3a7` passes 2410 repository tests. LPCL/Canonical Process IR is integrated as a non-effectful layer: it can select process transitions and emit non-authoritative ActionIntentCandidate values, but cannot mint authority, evaluate the PDP, construct RuntimeAdmission, select an EffectProvider or execute an effect. R22I binder consumption remains the governed Action→Runtime path and does not become a second execution plane.

During R23 currentness transport, a transient `tools/.r23-placeholder` commit was accidentally created. The mutation was detected immediately, removed before freeze and excluded from the final exact tree. The process therefore records it as an operational counterexample rather than laundering it away; exact tree equality with the locally validated candidate prevented the transient artifact from entering the frozen state.

R23 truth closure follows the same carrier-last invariant: after all noncarrier source/test/documentation reconciliation is verified, compute `LION/TRUTH-SUBJECT/1` excluding exactly `LION/architecture/canonical-state-v1-3-candidate.json` and `cyber_lion/registry/repositories.json`; update only those carriers as the final repository-file commits, then perform read-only exact-head verification. Runtime/merge/production authority remain separate.

## R24 → R23 post-merge reconciliation

R24 repository-ref authority provisioning was merged into `master` as `ab1ab2f2cbdeda1f10b2c73e78acf230f5be21da` / tree `0dea4254efc0c3da3db5fa994a9b87e9a2f85ba2` before R23 consolidation was published. The previously frozen R23 head therefore ceased to be directly mergeable and was treated as historical source evidence rather than stale publication authority.

A fresh three-way reconciliation against the merged R24 baseline produced exactly 13 textual conflicts. Eleven were current scan/count expectation carriers in MOON tests/tools; two were the global truth carriers. No conflict existed in the R23 process/runtime implementation or in the R24 repository-ref authority implementation. The combined clean pre-documentation candidate `93afd90f781d5421ad30dfcad92650347965dd0d` / tree `e7f56e9de9a014a2371192c191e8f5471a547a37` contains 268 production sources and 239 effect surfaces, with six raw unclassified references and zero unresolved references after taxonomy reconciliation. Its stable scan digest is `861d7e2aed0d5e1dbf32aa6e13ae942682876cec4efcf4985bed4d14815725e2`.

The exact clean pre-documentation reconciliation candidate passes 2425 repository tests with five controlled skips. Historical R23 evidence remains historical and is not rewritten to the new digest. The reconciliation is non-promoting until documentation is frozen, the truth subject is rebound carrier-last, exact-head CI/security passes, and a separately administered exact PR #303 merge authority is observed current.
