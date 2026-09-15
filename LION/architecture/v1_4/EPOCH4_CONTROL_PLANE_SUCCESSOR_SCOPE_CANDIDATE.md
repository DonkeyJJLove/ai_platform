# Epoch 4 Control Plane Successor Scope Candidate

**Status:** NON_AUTHORITATIVE_TARGET_SCOPE  
**Authority effect:** NONE  
**Source historical mission:** `LION-EPOCH3-FULL-CONTROL-PLANE-PANEL-AND-AUTONOMOUS-RUN-DISPATCHER-128L64M-R1`  
**Historical phase range:** 13–36  
**Reacquisition rule:** historical `PENDING` is not evidence of a present implementation gap. Every item below is classified against the current Epoch 3 terminal control-plane implementation and must be revalidated from current source/tests before a future Epoch 4 LPCL may authorize work.

This document is an architectural scope candidate only. It is **not** LPCL, does not register a mission, does not create authority, does not create an execution driver, does not create scheduler work, and cannot be used as an activation carrier.

| Historical phase | Historical intent | Current classification | Current implementation / evidence surface | Remaining gap / Epoch 4 carry-forward | Authority effect |
|---:|---|---|---|---|---|
| 13 | `MISSION_CONTROL_DELTA_REFRESH` | IMPLEMENTED_NEEDS_REVALIDATION | `tools/lion_mission_control_v3.py`; current mission projection and lifecycle/query repair | Revalidate the consolidated operational/history projection after lifecycle normalization | NONE |
| 14 | `LPCL_PANEL_DELTA_REFRESH` | IMPLEMENTED_NEEDS_REVALIDATION | `tools/lion_local_intelligence_runtime.py`; `cyber_lion/app_coordination/local_intelligence_gateway.py` | Revalidate exact-source intake plus operational/history selector after live deploy | NONE |
| 15 | `FOCUS_PIN_STATE_MACHINE` | ALREADY_IMPLEMENTED_AND_PROVEN | `set_focus_mission`, focus receipts, pinned read-only UI, `test_mission_focus.py` | No blind carry-forward; retain only regression coverage | NONE |
| 16 | `SEMANTIC_LABEL_PROJECTION` | ALREADY_IMPLEMENTED_AND_PROVEN | shared backend lifecycle classifier consumed by mission summaries and both panels | Revalidate labels against live database after normalization | NONE |
| 17 | `RAW_INSPECTOR` | ALREADY_IMPLEMENTED_AND_PROVEN | process/raw mission readback and historical schema context | Preserve read-only semantics; no execution authority from raw history | NONE |
| 18 | `RUN_REGISTRY_AND_RUN_DETAIL_REDESIGN` | ALREADY_IMPLEMENTED_AND_PROVEN | `/api/v3/missions/recent?view=operational|history|all`, lifecycle badges and read-only history detail | No new redesign inferred from historical PENDING | NONE |
| 19 | `ENVIRONMENT_AND_RECENT_EVENTS_REDESIGN` | IMPLEMENTED_NEEDS_REVALIDATION | normalized runtime/environment/observability projection | Revalidate freshness semantics and bounded recent-event windows | NONE |
| 20 | `CHAT_LAYOUT_AND_FIXED_COMPOSER` | ALREADY_IMPLEMENTED_AND_PROVEN | existing 8780 fixed composer / viewport-preserving render model | Preserve behavior; regression only | NONE |
| 21 | `LIFECYCLE_ACTION_CONTRACT_RECONCILIATION` | IMPLEMENTED_NEEDS_REVALIDATION | shared classifier, lifecycle capabilities, action gate, delete-preview gate | Live negative canaries for legacy/superseded action denial | NONE |
| 22 | `SCHEDULER_OBSERVABILITY` | ALREADY_IMPLEMENTED_AND_PROVEN | scheduler heartbeat, driver liveness, blocking-gate projection | Preserve; revalidate after restart | NONE |
| 23 | `SERVICE_RESTART_DURABILITY` | ALREADY_IMPLEMENTED_AND_PROVEN | existing restart durability predicates and prior successor terminal evidence | Re-run after lifecycle package deploy | NONE |
| 24 | `MULTI_RUN_CONCURRENCY_FALSIFICATION` | IMPLEMENTED_NEEDS_REVALIDATION | execution assignments, leases, per-mission driver state, concurrent registry reads | Re-run concurrency/lease isolation tests against lifecycle-separated registry | NONE |
| 25 | `BROWSER_DISCONNECT_FALSIFICATION` | IMPLEMENTED_NEEDS_REVALIDATION | durable Mission Control DB, server-side process state, browser polling/reopen behavior | Revalidate that history view/pinning creates no authority after disconnect/reopen | NONE |
| 26 | `SECURITY_AND_AUTHORITY_NEGATIVE_TESTS` | ALREADY_IMPLEMENTED_AND_PROVEN | fail-closed authority tests plus new legacy-history denial tests | Keep as terminal falsifier for future Epoch 4 changes | NONE |
| 27 | `FULL_REGRESSION_SUITE` | ALREADY_IMPLEMENTED_AND_PROVEN | Cyber-Lion full unittest suite | Must remain a terminal gate, not a new feature | NONE |
| 28 | `PRODUCTION_EFFECT_SURFACE_RECONCILIATION` | ALREADY_IMPLEMENTED_AND_PROVEN | production effect scanner / taxonomy reconciliation | Re-run on every candidate; unresolved must remain zero | NONE |
| 29 | `TRUTH_CARRIER_REBIND` | IMPLEMENTED_NEEDS_REVALIDATION | truth-carrier / scan-currentness model already present | Rebind only when code/tree changes; carriers last | NONE |
| 30 | `LOCAL_FINAL_CANDIDATE_VALIDATION` | ALREADY_IMPLEMENTED_AND_PROVEN | isolated exact-baseline candidate validation | Keep mandatory before publication | NONE |
| 31 | `PR337_NON_FORCE_FAST_FORWARD` | OBSOLETE | PR337 publication lineage is historical and no longer a current target | Do not recreate or replay PR337 | NONE |
| 32 | `EXACT_HEAD_CI_GATE` | ALREADY_IMPLEMENTED_AND_PROVEN | exact PR-head CI/currentness workflow model | Keep mandatory for any future successor candidate | NONE |
| 33 | `LIVE_EXACT_CARRIER_DEPLOYMENT` | IMPLEMENTED_NEEDS_REVALIDATION | bounded `MISSION_CONTROL_V3_INSTALL` deployment path | Required only when candidate changes live package bytes | NONE |
| 34 | `LIVE_RESTART_AND_RECOVERY_PROOF` | ALREADY_IMPLEMENTED_AND_PROVEN | Mission Control restart durability and source/package readback | Re-run after any live package change | NONE |
| 35 | `FULL_FUNCTIONALITY_AUTONOMOUS_ACCEPTANCE` | IMPLEMENTED_NEEDS_REVALIDATION | generic phase execution, scheduler, Mission Control, panel and broker surfaces | Future Epoch 4 must define its own exact mission acceptance predicates | NONE |
| 36 | `TERMINAL_RECONCILIATION` | ALREADY_IMPLEMENTED_AND_PROVEN | conjunctive terminal reconciliation model | Keep as final independent gate; never infer completion from publication alone | NONE |

## Candidate Epoch 4 scope after reacquisition

The historical phase list does **not** justify replaying phases 13–36. Most of the old scope is already implemented in the current control plane. A future Epoch 4 LPCL should therefore be substantially narrower and should focus on still-unproven deltas rather than historical status labels: lifecycle-separated live acceptance after restart; concurrency and browser-disconnect falsification against the new operational/history projection; exact-source LPCL intake across the expanded lifecycle protocol vocabulary; current implementation revalidation of environment/event projections; production-effect taxonomy/currentness rebind for any new code; and a new exact-digest terminal acceptance contract.

A future Epoch 4 mission requires a separately authored LPCL and separate explicit exact-digest activation. Nothing in this artifact supplies that authority.
