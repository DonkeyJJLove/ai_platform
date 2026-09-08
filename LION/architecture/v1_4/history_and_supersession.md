# LION v1.4 — history, supersession and falsification boundaries

This directory preserves history while allowing evidence-bound v1.4 reconciliation. It does not rewrite v1.3, v14c2 or prior RAG32 records. Historical claims remain historical unless reacquired from live Git/source/test evidence.

## Superseded currentness

`LION/status.json` remains a historical E003-era projection whose `CURRENT` label is stale relative to live `master`. R22I does not silently rewrite that consumer-sensitive state file. For v1.4 documentation currentness, use `current_state.json` and its explicit default/candidate evidence semantics.

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
