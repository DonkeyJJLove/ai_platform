# Cyber-Lion repository inventory — v1.4 reconciliation

**Repository:** `DonkeyJJLove/ai_platform`  
**R20 evidence baseline:** `5d5a02b37fdfff4bcbf62f455d37ce4b86080f59` / tree `9725bebf8d9766c58096cfc34af06ffcb8aa32f1`

This file supersedes the older description of `ai_platform` as primarily a specification repository without an executable control plane. That statement is no longer accurate for the exact baseline above. Current source contains contract, policy/PDP, authority, provisioning, runtime-admission, runtime-execution, effect-currentness, mediation, observation/reconciliation, fleet/swarm, architecture-projection, code-perception and startup-evolution surfaces. Code presence still does **not** imply deployment, production authority or complete mediation.

## Current material surfaces

`cyber_lion/contracts/` owns source-level contracts for action IR, policy gates, authority/effects, runtime enforcement/execution/currentness/reconciliation, executor provisioning, complete/production mediation, fleet runtime trust/effect budget, Bean/Composition/Mosaic and related state. `cyber_lion/enterprise/` contains the corresponding governed implementation surfaces, including `CanonicalPolicyDecisionPoint`, `RuntimeAdmissionEngine`, `RuntimeExecutionEngine`, currentness mediation, `RuntimeReconciler`, fleet/swarm governance and production-mediation code.

`cyber_lion/architecture_projection/full_architecture.py` is the source-derived architecture owner for 15 architecture layers. `flows.py` owns nine canonical architecture flows. The documentation projection under `LION/architecture/v1_4/` indexes those source truths and records exact federation/currentness state.

## Action plane

R19P integrated a non-effectful exact ActionProposal → canonical PDP handoff. Runtime admission already exists. F009 also contains a bounded proof plane that constructs effect/runtime identity/PDP evidence and runs a controlled create-only file effect with a separate observer/reconciler. The unresolved general dependency is therefore a reusable canonical PDP-result-to-runtime-object materializer/binder, not a missing admission engine.

## Factory / autonomy

BeanSpec, CapabilityNeed, composition, Mosaic and builder-chain bindings are live material surfaces. Bounded candidate protocols are evidence only for their tested scope. General Factory generativity, activated child autonomy and Factory-of-Factories remain unproven.

## Runtime and authority non-claims

A PDP ALLOW is not runtime admission. Admission is not an effect. A receipt is not independent observation. Observation is not reconciled closure. The presence of production-mediation code is not evidence of production deployment. Global complete mediation remains `UNKNOWN` in R20 documentation.

Read the evidence-bound inventory at `LION/architecture/v1_4/README.md`; historical inventories remain useful only with their original baseline and lifecycle context.
