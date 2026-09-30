# Federated Architecture AS-IS — v1.5

Status: `SOURCE_DERIVED_CANDIDATE`. Authority effect: `NONE`.

## System boundary

LION is a ten-repository federation. `ai_platform` owns the global control, contracts, semantic ownership, architecture projection, formalization, truth/currentness and federation routing. Peer repositories own local semantics or capabilities and expose those through `cyber-lion.repository.json` plus bounded `AGENTS.md` discovery rather than copying global architecture.

Exact post-peer federation identity is carried by `FEDERATION_LIVE_SNAPSHOT.json`. `ARCHITECTURE_DOCUMENT_CENSUS.json`, `ARCHITECTURE_DOCUMENT_GRAPH.json`, `REPOSITORY_ROLE_MATRIX.json`, `CROSS_REPOSITORY_DEPENDENCY_GRAPH.json` and `ARCHITECTURE_RECONCILIATION.json` are deterministic non-authoritative projections generated from exact repository identities and manifests.

## Code-derived architecture

The active candidate projects 15 canonical layers and 10 canonical flows. Exact projection input tree, model digest, element count and gap count are owned by `CODE_DERIVED_ARCHITECTURE.json`; this prose intentionally does not duplicate current Git-bound values.

The new canonical `FLOW-10` represents architecture-knowledge homeostasis:

```text
FEDERATION_STATE
→ ARCHITECTURE_DOCUMENT_CENSUS
→ ARCHITECTURE_DOCUMENT_GRAPH
→ ARCHITECTURE_RECONCILIATION
→ EVOLUTION_DELTA
→ REQUIRED_FORMALIZATION_SET
→ RAG_DISCOVERABILITY
→ FEDERATION_VECTOR
→ TRUTH_CARRIERS
```

No new top-level architecture layer is introduced. The loop is bound into existing `ARCHITECTURE_PROJECTION`, `EVOLUTIONARY_EPOCH`, `GOVERNED_SELF_IMPLEMENTATION`, `OBSERVABILITY_AND_RECONCILIATION` and currentness surfaces.

## Formalization and admission

The local Architecture Formalization Kernel remains `AFM → RequiredFormalizationSet → FCR`. `FederatedFormalizationBinding` adds only the missing federation binding: exact `FleetBaseline`, dependency-graph digest and one disposition per repository (`UPDATE`, `VALIDATE_ONLY`, `NOT_APPLICABLE`). It has no authority or execution effect.

Architecture-changing admission can use `GovernedChangeAdmissionEngine.derive_formalized_request(...)`, which verifies proposal binding, AFM, local FCR and federation binding before entering the existing governed admission path. Formalization therefore becomes functionally relevant without becoming authority.

## Documentation currentness

`LION/architecture/v1_4/current_state.json` remains historical lineage and is no longer a live primary owner. `LION/architecture/v1_5/semantic_owners.json` is the canonical semantic-owner map for this epoch. `AI_NATIVE_ROADMAP.md` remains historical input; `AI_NATIVE_ROADMAP_NEXT.md` is the new dependency-derived roadmap candidate.

Human prose explains rationale, boundaries and migration. Exact repository/federation identities, role matrices, document census, dependency graph and reconciliation are machine-derived.

## Boundary

This AS-IS projection does not prove runtime deployment, physical independence or authority. Those remain separate evidence planes.
