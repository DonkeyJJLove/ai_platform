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
