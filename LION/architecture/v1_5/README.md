# LION architecture 1.5 — federated architecture knowledge

Status: `INTEGRATED_FOUNDATION` on `master`. Authority effect: `NONE`. Runtime effect: `NONE`.

This directory is the current architecture-knowledge root for LION v1.5. It extends the existing Architecture Formalization Kernel without creating a new top-level scheduler, broker, authority engine or runtime owner.

The foundation is integrated; individual successor increments remain candidates until their own exact-tree formalization, CI, merge and post-integration reconciliation close.

## Read order

1. `FEDERATED_ARCHITECTURE_AS_IS.md` — source-derived system geometry and boundaries.
2. `FEDERATED_ARCHITECTURE_TARGET.md` — target knowledge/currentness behavior.
3. `semantic_owners.json` — exactly one primary owner per required global concept.
4. `FORMALIZATION_REGISTRY_FEDERATION_R1.json` — federation-aware formalization surface registry.
5. `FEDERATION_LIVE_SNAPSHOT.json` — source-bound federation observation used as a projection baseline; it is not self-refreshing live truth.
6. `ARCHITECTURE_DOCUMENT_CENSUS.json` and `ARCHITECTURE_DOCUMENT_GRAPH.json` — architecture-bearing documents and functional relations.
7. `CODE_DERIVED_ARCHITECTURE.json` and `DOCUMENT_DERIVED_ARCHITECTURE.json` — independent code/document projections.
8. `ARCHITECTURE_RECONCILIATION.json` and `ARCHITECTURE_CONTRADICTION_REGISTER.json` — alignment, stale claims and conflicts.
9. `DOCUMENTATION_CURRENTNESS_MODEL.json` — typed currentness dimensions, including public entrypoint currentness.
10. `ROADMAP_RECONCILIATION.json` and `AI_NATIVE_ROADMAP_NEXT.md` — dependency-derived frontier.

Public/project entrypoints are `README.md`, `LION/README.md` and this file. They are architecture knowledge and must route to the same current epoch.

## Service Continuation Ledger R1 — source candidate

[Service Continuation Ledger](SERVICE_CONTINUATION_LEDGER.md) formalizes a versioned service handoff and task-dependency contract. The canonical source instance [SERVICE_CONTINUATION_LEDGER_R1.json](SERVICE_CONTINUATION_LEDGER_R1.json) records incomplete R11 work, evidence references, explicit separate authorization gates and first concrete next actions. Its [JSON Schema](SERVICE_CONTINUATION_LEDGER.schema.json), Python contract, validation CLI and negative tests are owned by the service_continuation entry in semantic_owners.json and registered in FORMALIZATION_REGISTRY_FEDERATION_R1.json.

This is a **non-authorizing SOURCE CANDIDATE** until its own Git/CI/admission/merge closure; it is not a deployed Mission Control feed. Read live Git, CI, authority state and host runtime independently. It must never initiate a new LPCL merely because a dependency becomes READY.

## Core invariant

```text
ARCHITECTURE_DOCUMENTATION
= versioned architecture knowledge
+ tested formalization surface
+ bounded input/output of evolution
!= authority
```

Human prose explains rationale and boundaries. Machine-derivable identities, roles, document graphs and reconciliation are generated from exact source-bound inputs.

## Global-owner overlay

The federation baseline snapshot can legitimately predate a local architecture change in `ai_platform`. The architecture-knowledge generator therefore supports an **exact local-owner Git overlay**:

```text
FEDERATION BASELINE SNAPSHOT
+ EXACT ai_platform SOURCE COMMIT
→ CENSUS / GRAPH / RECONCILIATION / DOCUMENT PROJECTION
```

This prevents the global owner from classifying itself from its own older manifest. The overlay is source-bound evidence only; it does not grant authority or imply runtime currentness.

## Formalization path

```text
EvolutionDelta
→ ArchitectureFormalizationManifest
→ RequiredFormalizationSet
→ FederatedFormalizationBinding
→ GovernedChangeProposal
→ FormalizationProposalBinding
→ candidate + independent verification
→ FormalizationClosureRecord
→ GovernedChangeAdmissionEngine.derive_formalized_request
→ existing authority/effect path
```

`FederatedFormalizationBinding` binds one local AFM to an exact `FleetBaseline` and a disposition for every repository. It grants no authority.

## Currentness

- `LION/architecture/v1_4/current_state.json` is historical compatibility, not the live v1.5 currentness owner.
- `LION/architecture/v1_4/semantic_owners.json` is a historical compatibility projection.
- `AI_NATIVE_ROADMAP.md` is historical roadmap input.
- stored `FEDERATION_LIVE_SNAPSHOT.json` is projection input evidence and can become stale relative to later Git;
- `LION/architecture/canonical-state-v1-3-candidate.json` plus truth-plane validation remain the truth/currentness carrier path;
- `LION/architecture/v1_4/federation_current_vector.json` remains the exact federation Git-currentness carrier for its bound epoch;
- RAG remains versioned knowledge and never substitutes for live reacquisition.

## Documentation homeostasis

```text
SOURCE / FEDERATION CHANGE
→ invalidate dependent architecture knowledge
→ overlay current global owner when required
→ regenerate machine projections
→ reconcile code/document/federation
→ refresh README.md + LION/README.md + v1.5 root
→ run discoverability/RAG probes
→ formalization closure
→ federation vector
→ truth carriers last
```

A projection may be correct for its source binding and still be stale for a later live claim. `CURRENT` must therefore always be interpreted with its bound identity and evidence class.

## Peer policy

Peer repositories own only their local architecture knowledge through `AGENTS.md`, `cyber-lion.repository.json` and explicitly listed local artifacts. The global federation architecture is not copied into peers; federation-wide questions route back to `ai_platform`.

## Current successor increment

`CommunicationEnvelope` is integrated in `master` as a non-effectful semantic contract: `CommunicationEnvelope != transport != delivery != cognition != authority`. Its completed formalization remains immutable evidence for that integration epoch.

`MissionIntent`, `QueryPlan`, `RagContextEnvelope`, `SemanticScaffoldIR` and `SemanticRelevance` are integrated as the non-effectful Semantic Cloud representation chain. The federation-finalization program additionally integrates the repository-local F01–F09 provider/consumer work packages without transferring global ownership or runtime authority. See `FEDERATION_FINAL_RECONCILIATION_SOURCE_R1.md` for the source-bound pre-carrier vector.


## Semantic Cloud candidate

Semantic Cloud R1 is an integrated non-effectful representation layer over MissionIntent, QueryPlan, RagContextEnvelope, SemanticScaffoldIR and SemanticRelevance. It reuses existing CapabilityNeed/Composition/Mosaic and the existing governed Action path; it creates no scheduler, runtime or authority owner.

See [SEMANTIC_CLOUD_INTEGRATION_TARGET.md](SEMANTIC_CLOUD_INTEGRATION_TARGET.md).

## Edge Yoke R6 — candidate execution-boundary integration

[Implementation and operator entrypoint](../../../docs/architecture/edge-yoke/README.md): existing R5 context resolver wrapped by a deny-only observer gate, original artifact transfer, isolated two-worker qualification and evidence-correction adapter. No second scheduler or authority owner. Global closure, deployment and the historical package-lineage issue remain separately evaluated.

## Architecture Studio / Compiler R1

The deterministic, non-effectful ArchitectureCompiler is present in the current source tree. It binds an exact source baseline and typed CandidateDesign to the existing EvolutionDelta -> ArchitectureFormalizationManifest -> RequiredFormalizationSet path and stops before governed admission.

Architecture Studio remains PARTIAL: the repository provides the source-bound architecture read-model, federation knowledge graph, status/currentness/gap projections and visual render plans, but the interactive Electron graph explorer/composer and formalization-impact preview are still not implemented.

The [architecture_studio_compiler_r1/](architecture_studio_compiler_r1/) directory preserves source-candidate/formalization evidence from its authoring boundary; do not reinterpret that historical package status as a claim that the current source is absent. Integration, formalization/currentness closure and deployment remain distinct planes.

## Project Reality / Mental Matrix reconciliation — candidate

The candidate [Project Reality → Evolution Path R1](PROJECT_REALITY_EVOLUTION_PATH_R1.md) composes existing `WorldSnapshot`, `SystemSnapshot`, federation/currentness evidence, `SemanticAtom` and `EnterpriseGraph` into a source-bound `ProjectRealitySnapshot` and a read-only `ProjectClaimProjection`.

This deliberately **does not** create a second truth database or a separate Mental Matrix orchestrator. Mental Matrix narrative/visual/publication views and the future interactive Architecture Studio are different read/proposal projections over the same reality, evidence and lineage substrate. Narrative cannot promote epistemic state, and neither surface carries authority/effect.

The candidate implementation is `cyber_lion/architecture_projection/project_reality.py`. Its first functional consumer is Dynamic Evolution Fitness: candidate-specific gate observations and evidence-bound pressure are converted into `EvolutionRealityContext`, preserving UNKNOWN as fail-closed.

## Dynamic Evolution Fitness R1 candidate

The roadmap/evolution owner now has a candidate deterministic fitness projection for selecting **one** bounded critical-path evolution candidate. `ProjectRealityAdapter` supplies source-bound gates/pressure, then `ArchitectureCompiler.compile_selected(...)` delegates only the chosen `CandidateDesign` to the existing compiler. Hard source/authority/effect/collision/evidence gates run before Pareto and evidence-bound pressure.

See [LION Evolution Fitness Standard](../../standards/LION_EVOLUTION_FITNESS_STANDARD.md). It adds no scheduler, FLOW-11, authority source or execution surface. The intended next high-value acceptance is a real SaaS + LOCAL + material-worker artifact loop followed by a second task-family proof using the same factory mechanism.

## Application Factory R1 — cross-model material successor candidate

The [Application Factory R1 package](application_factory_r1/README.md) is the finite successor candidate for the roadmap acceptance named above. It uses one mission artifact ledger to retain independent LOCAL trajectories and a responded SaaS advisory, binds the resulting `CONTROL_PLANE_INTELLIGENCE_BUNDLE` digest into cooperative material production, performs one-worker preactivation before the unchanged full-fleet readiness gate, and requires a distinct verifier.

The package is source-only. Its `REGISTRATION_PREVIEW.json` is intentionally not a live registration payload; exact deployed HEAD/TREE must be reacquired and the payload regenerated immediately before any separate registration/activation action.
