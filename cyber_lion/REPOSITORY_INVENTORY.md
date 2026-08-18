# CYBER-LION — Repository Inventory

Status labels used here:

- `EXECUTABLE` — current repository contains a functioning software mechanism relevant to the target role.
- `MIXED` — executable assets and major specifications coexist.
- `SPECIFICATION` — current value is primarily formal/documentary/research specification.
- `RESEARCH` — hypotheses/evidence/experiments rather than operational runtime.

The recommended disposition uses `KEEP / REFINE / EXTRACT / GENERALIZE / INTEGRATE / DEPRECATE / EXPERIMENTAL`.

## 1. `DonkeyJJLove/ai_platform`

**Observed state:** primarily architecture/specification. Root currently contains `platform.md`, `LAT_GLX_PROJECT_MOSAIC.MD`, experimental tests/reports and tracked IDE state. The QV9D material already models `INF / SEM / MAND`, semantic bridges and repository mapping, but the current repository is not yet an executable control plane.

**Current capabilities**

- QV9D semantic coordinate system.
- Project mosaic concept and repository-role mapping.
- Mapping rules from physical paths to semantic coordinates.
- Experimental comparison of 9D bridges.

**Unique asset:** existing conceptual place for cross-repository topology and governance.

**Debt / gap**

- static/stale project mosaic rather than discovered registry;
- no shared entity/event contract implementation;
- no capability registry runtime;
- no global graph service;
- no authority/policy engine;
- no cross-repo tracing runtime;
- existing process-upgrade PR should land before or be incorporated into compatibility work.

**Cyber-Lion role:** `Control Plane / Contract Authority / Registry / QV9D Mapping`.

**Disposition:** `KEEP + REFINE + GENERALIZE + INTEGRATE`.

---

## 2. `DonkeyJJLove/chunk-chunk`

**Observed state:** protocol-heavy repository with machine-readable `hmk9d_protocol.yaml`, large HMK-9D specification, prompts and semantic bridge definitions. It models `Δ`, 9D relational state and semantic transitions, but is not yet a general runtime context-routing service.

**Current capabilities**

- HMK-9D contract and axes `[T,S,R,E,I,F,A,P,D]`.
- `chunk–chunk→` transition model.
- semantic bridges and transition thresholds;
- local energy/risk representation;
- draft microcode/event vocabulary.

**Unique asset:** explicit structural representation of semantic/process trajectories.

**Debt / gap**

- distinction between conceptual metric and measured metric requires enforcement;
- no common Cyber-Lion entity/provenance envelope;
- no executable compression/router API demonstrated in current root inventory;
- tracked `.venv` still exists on default branch; process-upgrade PR is pending.

**Cyber-Lion role:** `Cognitive Compression & Context Routing contract/provider`.

**Disposition:** `KEEP + REFINE + EXPERIMENTAL + INTEGRATE`.

---

## 3. `DonkeyJJLove/glitchlab`

**Observed state:** substantial executable Python code plus architecture/specification. Existing modules include graph, AST mapping, mosaic, pipeline, registry, delta, analysis, security, tests and UI. Documentation already describes BUS/EGDB, SAST Bridge, invariants and fail-closed control.

**Current capabilities**

- AST and graph extraction;
- Delta-first representation and fingerprints;
- AST↔Mosaic transformations;
- invariants and threshold/gating concepts;
- local callable/filter registry;
- SAST normalization/prioritization concepts;
- BUS/EGDB event/telemetry architecture;
- GUI/HUD and analysis artifacts.

**Unique asset:** strongest current combined `SEM` engine for structural change, anomaly and invariant analysis.

**Debt / gap**

- packaging topology is inconsistent: `pyproject.toml` searches `src/glitchlab*`, while current `src/` inventory does not expose that package layout;
- generated/local state is tracked on default branch (`.env.local`, `*.egg-info`); process-upgrade PR is pending;
- local registry is not suitable as the global Cyber-Lion capability registry;
- documented sandbox/fail-closed claims must always be tied to actual execution enforcement.

**Cyber-Lion role:** `Anomaly / Novelty / Delta / Structural Analysis provider`.

**Disposition:** `KEEP + REFINE + EXTRACT adapters`; **do not rewrite core**.

---

## 4. `DonkeyJJLove/HA2D`

**Observed state:** predominantly cognitive-state/Human–AI specifications: PCE, MCV, SNAP, THOUGHT, MORPH_UNIT, `_neuro_`, HUD, revision viewer and context protocol. No comparable executable runtime was identified during root archaeology.

**Current capabilities**

- persistent vs temporary context concepts;
- delta/revision vocabulary;
- Human–AI HUD specification;
- cognitive-state and semantic-revision models.

**Unique asset:** explicit separation of persistent context, working context and human-facing replay concepts.

**Debt / gap**

- many statements are architectural/heuristic rather than implemented mechanisms;
- memory classes and memory-write policy are not shared contracts yet;
- `_neuro_` metrics require explicit scope as experimental process descriptors rather than physiological measurements;
- process-upgrade PR is pending.

**Cyber-Lion role:** `Cognitive State / Memory Contract / Human–AI Interaction Plane`.

**Disposition:** `KEEP + REFINE + FORMALISE + EXPERIMENTAL`.

---

## 5. `DonkeyJJLove/hipotezy_nadawcze_LLM`

**Observed state:** intentionally small research repository containing a README and a falsifiable hypothesis about the text→token channel.

**Current capabilities**

- hypothesis formulation;
- explicit falsification conditions;
- evidence/argument organization;
- communication/representation research.

**Unique asset:** epistemic laboratory whose output should be claims/evidence, not authority.

**Debt / gap**

- hypothesis probability estimates are not empirical measurements by default;
- no machine-readable hypothesis/evidence schema;
- no experiment registry yet;
- process-upgrade PR is pending.

**Cyber-Lion role:** `Communication Epistemology Lab / Hypothesis source`.

**Disposition:** `KEEP + EXPERIMENTAL + FORMALISE`; do not turn into runtime authority.

---

## 6. `DonkeyJJLove/mosaic_lab_pro.py`

**Observed state:** one large executable Python application plus README. It implements AST graph extraction, topology, A*, 3D honeycomb visualization and λ-controlled abstraction/supergraph behavior.

**Current capabilities**

- Python AST→graph transformation;
- structural edge classes;
- A* path planning within its geometry;
- λ abstraction and supergraph construction;
- interactive visualization.

**Unique asset:** working prototype for multi-level structural representation.

**Debt / gap**

- monolithic program couples analysis and GUI;
- no stable library/API boundary for cross-repo use;
- geometric representation must not be treated as semantic truth without an explicit mapping contract.

**Cyber-Lion role:** `Mosaic Structure / Abstraction Engine`.

**Disposition:** `KEEP + EXTRACT + REFINE`; first extract pure analysis interface, preserve UI compatibility.

---

## 7. `DonkeyJJLove/sbom`

**Observed state:** executable/lab DevSecOps environment plus strong data contract. AID is propagated through SBOM/scan/delta/gate events; repository includes Jenkins/toolbox, Elastic/Splunk alternatives and documentation.

**Current capabilities**

- stable Application Identity Descriptor (AID);
- event envelope with timestamp/event type/AID/payload;
- SBOM/scan/delta/gate process chain;
- CI/CD gating;
- analytics and identity-over-time.

**Unique asset:** strongest existing concrete identity/provenance/event contract in the portfolio.

**Debt / gap**

- AID is application-centric and must not be broken by generalization;
- broader Entity Identity needs a compatibility wrapper, not replacement;
- LBOM/Decision-BOM/Agent-BOM/etc. are target concepts, not current complete implementations.

**Cyber-Lion role:** `Provenance / Supply Chain / Identity compatibility anchor`.

**Disposition:** `KEEP + GENERALIZE via adapter + INTEGRATE`.

---

## 8. `DonkeyJJLove/swarm`

**Observed state:** executable distributed laboratory with drones, UDP/MQTT aggregation, Flask APIs, PostgreSQL, AI service, Kubernetes/Istio, monitoring, NetworkPolicy and RBAC.

**Current capabilities**

- distributed workers/producers;
- telemetry collection and transport;
- API and persistence;
- model inference service;
- Kubernetes execution topology;
- service mesh/monitoring;
- network and RBAC controls.

**Unique asset:** strongest current `INF` execution-mesh prototype.

**Debt / gap**

- raw domain JSON crosses services without Cyber-Lion identity/provenance/correlation envelope;
- no cross-service execution receipt;
- current aggregator RBAC includes deployment update/patch authority while observed aggregator code only forwards telemetry — this requires least-authority review;
- no explicit policy/gate between AI prediction and consequential action;
- duplicate `README.md` / `readme.md` on default branch is repository-state debt.

**Cyber-Lion role:** `Agent Execution Mesh / Event Transport / Tool & Sandbox execution target`.

**Disposition:** `KEEP + REFINE + INTEGRATE`; add adapters before changing domain services.

---

## 9. `DonkeyJJLove/SymulacjaKaskadySieciowej`

**Observed state:** packaged executable Python system-dynamics project with deterministic runs, Monte Carlo, Morris, Sobol, configuration, CLI and a reusable `run_model` interface.

**Current capabilities**

- scenario simulation;
- deterministic and stochastic execution;
- parameter validation;
- Monte Carlo;
- Morris/Sobol global sensitivity analysis;
- phase/bifurcation analysis;
- reproducible seed/config interfaces.

**Unique asset:** mature reusable simulation capability with explicit model-risk language.

**Debt / gap**

- current equations are domain-specific;
- should be exposed as a generic simulation capability contract without pretending the current model covers all propagation classes;
- observation graph→perturbation→N futures adapter does not yet exist as a general Cyber-Lion API.

**Cyber-Lion role:** `Propagation / Systemic Risk / Counterfactual Simulation provider`.

**Disposition:** `KEEP + WRAP + GENERALIZE interface`; preserve domain model intact.

---

## 10. `DonkeyJJLove/writeups`

**Observed state:** large, structured living research corpus with local README navigation, AI security architectures, experiments, PDF reports, LOCI, cyber research and epistemic materials.

**Current capabilities**

- evidence/research corpus;
- publication layer;
- architecture specifications;
- methodological records and negative/falsification material;
- navigable topic tree.

**Unique asset:** long-term research/evidence history across the entire ecosystem.

**Debt / gap**

- documents do not yet share a machine-readable epistemic/provenance manifest;
- free-form text must never become runtime policy/authority merely because it was retrieved;
- experiment/result/superseded relationships require explicit indexing before automated ingestion.

**Cyber-Lion role:** `Research Corpus / Evidence & Knowledge Provenance source`.

**Disposition:** `KEEP + INDEX + FORMALISE metadata`; do not use free-form corpus as direct authority source.

---

# Cross-repository maturity conclusion

```text
SPECIFICATION-DOMINANT:
  ai_platform
  chunk-chunk
  HA2D

EXECUTABLE / MIXED:
  glitchlab
  mosaic_lab_pro.py
  sbom
  swarm
  SymulacjaKaskadySieciowej

RESEARCH CORPUS / EPISTEMIC:
  hipotezy_nadawcze_LLM
  writeups
```

The target architecture must therefore be **federated through contracts and adapters**. Treating every repository as an already operational service would be an architectural category error.