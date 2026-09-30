# LION architecture 1.5 — federated architecture knowledge

Status: `CANDIDATE_ONLY` until exact-tree formalization, CI, merge and post-integration reconciliation close. Authority effect: `NONE`. Runtime effect: `NONE`.

This directory is the v1.5 architecture-knowledge root. It extends the existing Architecture Formalization Kernel without creating a new top-level layer, scheduler, broker, authority engine or runtime owner.

## Read order

1. `FEDERATED_ARCHITECTURE_AS_IS.md` — source-derived system geometry.
2. `FEDERATED_ARCHITECTURE_TARGET.md` — target knowledge/currentness behavior.
3. `semantic_owners.json` — exactly one primary owner per required global concept.
4. `FORMALIZATION_REGISTRY_FEDERATION_R1.json` — current federation-aware formalization surface registry.
5. `FEDERATION_LIVE_SNAPSHOT.json` — exact post-peer repository identities used by generated projections.
6. `ARCHITECTURE_DOCUMENT_CENSUS.json` and `ARCHITECTURE_DOCUMENT_GRAPH.json` — architecture-bearing documents and functional relations.
7. `CODE_DERIVED_ARCHITECTURE.json` and `DOCUMENT_DERIVED_ARCHITECTURE.json` — independent code/document projections.
8. `ARCHITECTURE_RECONCILIATION.json` and `ARCHITECTURE_CONTRADICTION_REGISTER.json` — alignment, stale claims and conflicts.
9. `DOCUMENTATION_CURRENTNESS_MODEL.json` — typed currentness dimensions.
10. `ROADMAP_RECONCILIATION.json` and `AI_NATIVE_ROADMAP_NEXT.md` — dependency-derived frontier.

## Core invariant

```text
ARCHITECTURE_DOCUMENTATION
= versioned architecture knowledge
+ tested formalization surface
+ bounded input/output of evolution
!= authority
```

Architecture knowledge is regenerated from exact repository/federation observations. Human prose explains rationale and boundaries; machine-derivable identities, roles, dependency graphs and reconciliation are generated.

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

`FederatedFormalizationBinding` binds one local AFM to the existing exact `FleetBaseline` and a disposition for every repository. It grants no authority.

## Currentness

- `LION/architecture/v1_4/current_state.json` is historical compatibility, not the live v1.5 currentness owner.
- `LION/architecture/v1_4/semantic_owners.json` is a historical compatibility projection.
- `AI_NATIVE_ROADMAP.md` is historical roadmap input.
- `LION/architecture/canonical-state-v1-3-candidate.json` plus truth-plane validation remain the truth/currentness carrier path.
- `LION/architecture/v1_4/federation_current_vector.json` remains the exact federation Git-currentness carrier and is regenerated after integration.
- RAG remains versioned knowledge and never substitutes for live reacquisition.

## Peer policy

Peer repositories own only their local architecture knowledge through `AGENTS.md`, `cyber-lion.repository.json` and explicitly listed local artifacts. The global federation architecture is not copied into peers; federation-wide questions route back to `ai_platform`.

## Next frontier

The current dependency-derived order is documented in `AI_NATIVE_ROADMAP_NEXT.md`. The preserved `mission/v15-communication-envelope-r1` branch is not merged as-is; it is reconciled only after this foundation closes.
