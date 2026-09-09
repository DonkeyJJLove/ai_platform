# LION architecture documentation — v1.4 candidate

**Origin process:** R20  
**Completion/reconciliation process:** R23  
**LPCL interpretation evolution:** `architecture/lpcl-canonical-interpretation-r1` candidate, not merged  
**Evidence baseline:** master `67a4f8243aa6805e47035e572bd458f73fd0b358` / tree `4f6fbc481c8df8f7e1fd75f04188207a1c6fbcf5`; R23 pre-documentation candidate `5f90f1c11e9f997ed9c5e3ac1b02c6d802d15745` / tree `5dd5dc653c24bdd810faeb61f901328ad246e3a7`  
**Authority effect of this documentation:** `NONE`

This directory is the v1.4 documentation homeostasis layer. It does not replace source code, contracts, runtime evidence or historical RAG records. It routes each concept to one primary semantic owner and provides exact-baseline machine projections for high-cardinality facts.

## Current architecture

The source-derived architecture model is owned by `cyber_lion/architecture_projection/full_architecture.py`: 15 canonical layers and nine canonical flows. R23 reconciles that model with the consolidated LPCL/Process, Action→Runtime and P0 source lineages while preserving the existing canonical flow set; it does not mint a second executable architecture, PDP, runtime admission engine or authority source.

The consolidated R23 candidate contains the R21 LPCL/Canonical Process IR layer, the R22I governed Action→Runtime binder-consumption path, canonical PDP evaluation, runtime admission, runtime execution, effect-time currentness and independent reconciliation surfaces. LPCL is non-effectful: ACTION_REQUIRED transitions can emit only a non-authoritative `ActionIntentCandidate`; they do not evaluate the PDP, create RuntimeAdmission, choose an EffectProvider or execute an effect. F009 and P0 remain bounded TEST_ONLY evidence rather than general or production authority.

Bean/Composition/Mosaic primitives and bounded B0 candidate protocols exist. They do not prove unrestricted Factory generativity, activated recursive autonomy or Factory-of-Factories.

## LPCL process-orchestration projection — v1.1 candidate

The LPCL interpretation candidate does **not** add a sixteenth top-level architecture layer. It makes process orchestration an explicit cross-layer projection over the existing 15-layer architecture. The source projection is `cyber_lion/architecture_projection/process_orchestration.py` and binds existing layers as follows:

```text
INTENT / GOAL
→ LPCL canonical RUN/PHASE surface              [EVOLUTIONARY_EPOCH]
→ CanonicalRunAST                              [EVOLUTIONARY_EPOCH]
→ CanonicalProcessIR                           [EVOLUTIONARY_EPOCH]
→ FleetMissionIR                               [FLEET_AND_SWARM]
→ bounded role routing                         [FLEET_AND_SWARM]
→ ActionIntentCandidate when ACTION_REQUIRED   [GOVERNED_SELF_IMPLEMENTATION]
→ existing authority decision                  [AUTHORITY_AND_EFFECT]
→ existing RuntimeAdmission                    [TRUSTED_RUNTIME]
→ existing effect boundary                     [AUTHORITY_AND_EFFECT]
→ independent observation                      [OBSERVABILITY_AND_RECONCILIATION]
→ reconciliation                               [OBSERVABILITY_AND_RECONCILIATION]
```

This is a candidate projection until its implementation, tests, documentation, currentness carriers and final exact head are independently reconciled. It must not be read as an AS-IS promotion merely because the candidate files exist.

The candidate defines three execution-topology classes:

```text
LOGICAL_FLEET_MISSION
LOCAL_FLEET_MISSION
HYBRID_FLEET_MISSION
```

`FleetMissionIR` is non-authoritative. It binds roles and transition routing but contains no grants, credentials, PDP result, RuntimeAdmission or raw effect provider. A LOGICAL role may be virtual and sequentially materialized by one model runtime while retaining logical identity and evidence lineage. A material `ACTION_REQUIRED` transition must route to a LOCAL role and still crosses the existing Process→Action→PDP→RuntimeAdmission boundary.

The candidate also establishes one authoring convention for future LION threads: explicitly versioned LPCL 1.1 processes use the key/value `RUN=/PHASE_N=` surface and compile into canonical machine semantics. Historical unversioned RUN material remains data. Strict JSON LPCL 1.0 remains an explicitly versioned compatibility/machine surface rather than the default human authoring form.

Normative candidate documents:

- `docs/architecture/process-language/LPCL_LANGUAGE_CONSTITUTION.md`
- `docs/architecture/process-language/LPCL_CROSS_THREAD_GENERATION_STANDARD.md`
- `docs/architecture/process-language/LPCL_FLEET_MISSION_MODEL.md`
- `docs/architecture/process-language/LPCL_MIGRATION.md`

## Evidence and authority boundaries

Documentation is not authority. A PDP ALLOW is not runtime admission; admission is not an effect; an execution receipt is not independent observation; observation is not reconciled closure. Code presence is not deployment evidence. Four logical WSL2 hosts were observed during R20, but physical failure-domain independence was not proven. No local model service was observed during that host revalidation. R20Q revalidates Git/documentation state; it does not silently promote those host observations to a newer runtime observation.

The LPCL v1.1 candidate preserves the same boundary:

```text
PROCESS_CANDIDATE != AUTHORITY
FLEET_MISSION != AUTHORITY
ACTION_INTENT != AUTHORITY_DECISION
AUTHORITY_DECISION != RUNTIME_ADMISSION
RUNTIME_ADMISSION != EFFECT
REPORTED_EFFECT != OBSERVED_EFFECT
OBSERVED_EFFECT != RECONCILED_CLOSURE
```

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
