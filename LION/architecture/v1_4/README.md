# LION architecture documentation — v1.4 candidate

**Origin process:** R20  
**Completion/reconciliation process:** R20Q  
**Evidence baseline:** `5d5a02b37fdfff4bcbf62f455d37ce4b86080f59` / tree `9725bebf8d9766c58096cfc34af06ffcb8aa32f1`  
**Authority effect of this documentation:** `NONE`

This directory is the v1.4 documentation homeostasis layer. It does not replace source code, contracts, runtime evidence or historical RAG records. It routes each concept to one primary semantic owner and provides exact-baseline machine projections for high-cardinality facts.

## Current architecture

The source-derived architecture model is owned by `cyber_lion/architecture_projection/full_architecture.py`: 15 canonical layers and nine canonical flows. R20/R20Q supplement that model with current federation, material-object, capability and contract catalogs; they do not mint a second executable architecture.

The live system already contains canonical PDP evaluation, runtime admission, runtime execution, effect-time currentness and independent reconciliation surfaces. F009 additionally demonstrates a bounded live proof path. The first unfinished **general** Action-plane dependency is therefore not another admission engine; it is a reusable canonical materializer/binder from an ALLOW decision plus exact proposal/current authority/provisioning to `RequestedRuntimeEffect`, `RuntimeIdentityBinding` and `CanonicalPDPDecisionEvidence` consumed by the existing `RuntimeAdmissionEngine`.

Bean/Composition/Mosaic primitives and bounded B0 candidate protocols exist. They do not prove unrestricted Factory generativity, activated recursive autonomy or Factory-of-Factories.

## Evidence and authority boundaries

Documentation is not authority. A PDP ALLOW is not runtime admission; admission is not an effect; an execution receipt is not independent observation; observation is not reconciled closure. Code presence is not deployment evidence. Four logical WSL2 hosts were observed during R20, but physical failure-domain independence was not proven. No local model service was observed during that host revalidation. R20Q revalidates Git/documentation state; it does not silently promote those host observations to a newer runtime observation.

## Navigation

- `current_state.json` — exact-baseline current-state projection; host/runtime observations retain their stated R20 evidence epoch.
- `federation_current_vector.json` — R20Q-revalidated Git identities plus role/layer/maturity fields copied from the exact live registry.
- `material_object_catalog.json` — architecture-material objects; explicitly not an exhaustive all-symbol AST census.
- `capability_catalog.json` — integrated, bounded, partial, target and unproven capabilities.
- `contract_catalog.json` — material contracts and compatibility contradictions.
- `event_state_catalog.json` — the nine canonical architecture flows and state semantics.
- `semantic_owners.json` — exactly one primary owner for each required global documentation concept.
- `documentation_gap_register.json` — repaired and intentionally unresolved documentation/formal gaps.
- `documentation_mutation_manifest.json` — documentation-only mutation scope.
- `DOCUMENTATION_UPDATE_PLAN.md` — update policy and dependency order.
- `history_and_supersession.md` — preserved supersession/falsification lineage.

Existing human semantic owners remain `cyber_lion/CAPABILITY_MAP.md`, `CONTRACT_MAP.md`, `EVENT_DATA_MODEL.md`, `SCIENTIFIC_STATUS.md`, `TARGET_ARCHITECTURE.md`, `cyber_lion/enterprise/README.md` and `AI_NATIVE_ROADMAP.md`. The exact routing between owners is canonicalized by `semantic_owners.json` for this candidate.
