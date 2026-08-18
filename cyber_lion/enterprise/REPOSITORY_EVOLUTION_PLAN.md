# Repository Evolution Plan

This roadmap assigns every repository a stable **enterprise role** while preserving independent evolution. The goal is federation through contracts, not a monorepo rewrite.

## 1. `ai_platform` — Enterprise Control Plane / Agent Foundry

### Keep

- Cyber-Lion identity/event/capability contracts,
- Startup Evolution Agent,
- provider plane,
- authority separation,
- repository archaeology and enterprise architecture.

### Build next

**Phase A — Agent Foundry**

- `AgentSpec` / `AgentInstance` schemas,
- Agent Registry,
- versioning/supersession,
- mission → capability resolution,
- explicit memory/observability/authority requirements.

**Phase B — Swarm Control Plane**

- `SwarmSpec`, `MosaicCell`, `MosaicDelta`,
- deterministic swarm planner,
- spawn/delegate/dissolve contracts,
- observability quorum,
- risk-class topology rules.

**Phase C — Enterprise Graph**

- project entities/capabilities/agents/swarms/evidence/policy/execution as typed graph,
- adapters to Mosaic Structural Engine,
- path queries for authority/provenance.

**Phase D — Policy / Gate Engine**

- common PDP interface,
- GateRequested/GateApplied receipts,
- observability-conditioned authority degradation,
- enterprise GREEN/AMBER/RED lanes.

### Avoid

- copying provider implementations into `ai_platform`,
- treating a model provider as agent identity,
- central runtime with unrestricted credentials.

---

## 2. `glitchlab` — Enterprise Evolution Compiler

### Current assets

- Δ-first engineering,
- AST↔Mosaic `Φ/Ψ`,
- I1–I4,
- α/β/ζ living thresholds,
- SAST-Bridge,
- BUS/EGDB/HUD,
- FixCandidate/self-healing direction.

### Build next

**Phase A — stabilize current code compiler**

- complete package hygiene,
- prove documented entrypoints,
- close historical Ruff debt by ratchet,
- enforce safe generated-code execution via isolated provider.

**Phase B — external delta adapters**

Add typed adapters for:

```text
AgentSpec
SwarmSpec
CapabilityDescriptor
Policy
JSON Schema
RepositoryManifest
MemoryContract
```

Output one normalized `EnterpriseDeltaReport`.

**Phase C — enterprise invariants**

Implement E1–E10 from `GENERATION_EVOLUTION_PROTOCOL.md` beside code-level I1–I4.

**Phase D — Cyber-Lion bridge**

- consume Cyber-Lion change proposal,
- emit EventEnvelope-compatible analysis events,
- bind findings to entity/capability/agent/swarm graph,
- expose ACCEPT/REVIEW/BLOCK with evidence.

### Avoid

- turning GlitchLab itself into the authority engine,
- silently auto-fixing consequential changes,
- expanding one local registry into a global registry by semantic overloading.

---

## 3. `chunk-chunk` — Process Semantics / HMK-9D Microcode

### Current assets

- `S,Σ,A,F,g,H,a*` decision abstraction,
- `chunk–chunk→` transitions,
- 9D vector `[T,S,R,E,I,F,A,P,D]`,
- bridges and threshold operators,
- local/global energy concept,
- relation to GlitchLab Δ/EGDB.

### Build next

**Phase A — canonical schema**

- separate normative schema from prompt examples,
- version `ProcessVector9D`, `Bridge`, `Transition`, `MicrocodeProgram`,
- define units/ranges and UNKNOWN handling.

**Phase B — deterministic VM core**

- implement parser/executor for semantic microcode that modifies process state only,
- no direct tool authority,
- deterministic event output.

**Phase C — AgentSpec integration**

- allow an AgentSpec to reference process profile/bridges,
- emit 9D annotations on Cyber-Lion events,
- map `THRESHOLD_TRANSITION` to GateRequested candidate, not GateApplied.

**Phase D — swarm process geometry**

- aggregate local transition vectors into MosaicCell/Swarm diagnostics,
- coupling and coordination-cost metrics,
- adaptive chunk granularity.

### Avoid

- presenting `_neuro`/semantic bridge scores as physical measurements,
- letting bridge operators create authority,
- putting local virtual environments/runtime state in source.

---

## 4. `HA2D` — Context, Memory and Human–AI Adaptation Lab

### Current assets

- PCE persistent context,
- MCV temporary context,
- SNAP/THOUGHT/MORPH conceptual transitions,
- CMM UUID/time/hash records,
- SMA/_neuro semantic revision heuristics,
- HUD concepts.

### Build next

**Phase A — state taxonomy**

Formalize:

```text
WorkingContext
MemoryCandidate
CommittedMemory
SupersededMemory
```

with strict separation.

**Phase B — CMM v2 contract**

Add:

```text
EntityIdentity
provenance
source_event_ids
sensitivity
retention
policy_id
candidate_event_id
supersedes
content hash
```

**Phase C — Memory Service adapter**

- expose read/write capabilities through Cyber-Lion Capability Registry,
- MemoryCommitted only after MAND policy,
- implement replay/integrity tests.

**Phase D — Human–AI HUD**

- display context provenance,
- show memory candidates vs committed state,
- expose confidence/uncertainty and authority boundary.

### Avoid

- self-declared semantic coherence as proof of truth,
- automatic persistent memory from model output,
- treating `_neuro` as clinical EEG/physiology.

---

## 5. `swarm` — Distributed Execution Mesh

### Current assets

- Kubernetes workload topology,
- UDP/MQTT telemetry,
- APIs/PostgreSQL,
- Istio,
- Prometheus/Grafana/Jaeger,
- RBAC/NetworkPolicy,
- AI service example.

### Build next

**Phase A — lab security/hygiene**

- merge command-injection remediation,
- canonical README,
- least-authority review of RBAC,
- secrets from Kubernetes Secret management rather than examples with static values.

**Phase B — generic workload abstraction**

Replace drone-specific orchestration assumptions with reusable roles:

```text
ExecutionNode
AgentWorkload
TelemetryCollector
CapabilityBrokerClient
LocalPEP
```

Keep drone simulation as one example workload.

**Phase C — Cyber-Lion runtime adapter**

- consume AgentSpec/SwarmSpec,
- bind agent identity to pod/workload identity,
- map capability lease → runtime resources,
- emit action/process/effect receipts.

**Phase D — observability-conditioned runtime**

- required trace/health checks,
- DEGRADED/RESTRICTED/FROZEN states,
- authority reduction on evidence loss,
- kill/revoke capability.

### Avoid

- identity by IP/PID only,
- inheriting broad Kubernetes permissions from coordinator,
- calling Kubernetes/Istio configuration itself a complete Agent Control Mesh.

---

## 6. `sbom` — Provenance, Identity and Composition Intelligence

### Current assets

- AID,
- stable event envelope,
- `sbom → scan → delta → gate`,
- Jenkins/Elastic/Splunk lab,
- supply-chain state/delta logic.

### Build next

**Phase A — preserve SBOM specialization**

- strengthen CycloneDX/signing/attestation path,
- dependency and license/security metrics,
- reliable AID propagation.

**Phase B — Cyber-Lion identity adapter v2**

- dual emit EntityIdentity/EventEnvelope,
- lossless legacy AID compatibility,
- explicit GateApplied semantics.

**Phase C — Relation BOM / Decision BOM research**

Prototype composition records for:

```text
agent
model
tool
policy
swarm
execution artifact
```

Do not call these standardized SBOM formats unless mapped to an actual standard.

**Phase D — provenance graph provider**

- expose composition/delta queries to Enterprise Graph,
- link build → dependency → scan → gate → execution receipt.

### Avoid

- turning every telemetry record into full payload storage,
- conflating AID owner mandate with runtime permission,
- redefining existing SBOM standards under custom terms.

---

## 7. `mosaic_lab_pro.py` — Structural Intelligence Engine

### Current assets

- AST graph,
- S/H geometry,
- A* pathing,
- abstraction parameter `λ`,
- supergraph contraction,
- stable visualization invariants.

### Build next

**Phase A — split engine from GUI**

Extract reusable package:

```text
mosaic_core.graph
mosaic_core.topology
mosaic_core.abstraction
mosaic_core.path
mosaic_core.validation
```

Retain GUI as a consumer.

**Phase B — generic graph adapters**

Support:

```text
ASTGraph
RepositoryGraph
AgentGraph
SwarmGraph
CapabilityGraph
AuthorityGraph
ProvenanceGraph
```

**Phase C — multi-scale enterprise projection**

Use `λ` to move from:

```text
single action
→ agent
→ MosaicCell
→ swarm
→ repository
→ enterprise
```

**Phase D — structural anomaly provider**

- unexpected cross-domain edges,
- authority path shortcuts,
- high coupling,
- topology drift,
- single points of failure.

### Avoid

- interpreting geometry itself as truth,
- coupling core algorithms permanently to Tkinter/Matplotlib,
- using visual similarity as authorization/security decision.

---

## 8. `SymulacjaKaskadySieciowej` — Simulation/Falsification Engine

### Current assets

- packaged model interface,
- deterministic simulation,
- Monte Carlo,
- Morris,
- Sobol,
- bifurcation/phase analysis,
- explicit distinction between model and forecast.

### Build next

**Phase A — preserve current Iran model as domain plugin**

Do not genericize its equations away.

**Phase B — common SimulationProvider protocol**

```text
ModelDescriptor
ScenarioSpec
ParameterDistribution
SimulationRequest
SimulationResult
SensitivityResult
ModelRiskStatement
```

**Phase C — enterprise models**

Add separate plugins for:

- product/market timing,
- agent/swarm failure cascades,
- authority propagation,
- observability failure,
- software delivery/risk tradeoff.

**Phase D — Cyber-Lion adapter**

SimulationRequested/Completed events with seed/config/model-version provenance.

### Avoid

- using simulation frequency as empirical incident probability,
- modifying domain-specific model to fit every future use case,
- hiding assumptions behind one synthetic score.

---

## 9. `hipotezy_nadawcze_LLM` — Epistemic Hypothesis Lab

### Current assets

- narrow falsifiable hypotheses,
- explicit text→token thesis,
- falsification conditions,
- evidence/argument structure.

### Build next

**Phase A — HypothesisSpec schema**

```text
id
claim
scope
observable consequences
falsifiers
evidence for/against
alternatives
confidence
status
```

**Phase B — experiment registry**

- test cases,
- model/version metadata,
- result hashes,
- negative results.

**Phase C — R&D adapter**

- export to `writeups` ResearchRecord,
- link rather than duplicate canonical hypothesis.

### Avoid

- probability values without explicit status/calibration,
- model explaining its own hypothesis as validation,
- promoting analogy into scientific fact.

---

## 10. `writeups` — R&D / Enterprise Research Memory

### Current assets

- AI Security / SMB/PDB,
- runtime/reference monitor designs,
- multi-agent mesh,
- LOCI,
- Human–AI research,
- probabilistic studies,
- OSINT,
- publications and reproducibility material.

### Build next

**Phase A — R&D taxonomy**

Add machine-readable/lightweight index for:

```text
ResearchRecord
ArchitectureProposal
Experiment
Dataset/SourceSet
Finding
EngineeringCandidate
Publication
```

**Phase B — epistemic metadata**

Tag core outputs with status and supersession links.

**Phase C — Cyber-Lion R&D adapter**

- ingest metadata into Evidence/Hypothesis registry,
- preserve document SHA/source links,
- generate SpecCandidate only through explicit promotion.

**Phase D — research swarm workflows**

- source/evidence agent,
- hypothesis agent,
- falsification agent,
- simulation agent,
- methodology/security reviewer.

### Avoid

- treating all prose as equivalent evidence,
- losing negative results/superseded hypotheses,
- letting writeup text configure production directly.

---

## 11. Cross-repository implementation order

### Wave 1 — contracts and state

```text
ai_platform AgentSpec/SwarmSpec
→ chunk-chunk process schemas
→ HA2D memory contract
→ provider manifests in all repos
```

### Wave 2 — structural validation

```text
GlitchLab enterprise-delta adapters
→ Mosaic core extraction
→ common graph identities
```

### Wave 3 — execution

```text
Swarm generic Execution Mesh
→ runtime identity/capabilities
→ observability-conditioned authority
```

### Wave 4 — research/simulation

```text
writeups R&D index
→ hypothesis adapter
→ SimulationProvider
→ research swarm
```

### Wave 5 — full closed loop

```text
market/world observation
→ R&D/product mission
→ dynamic swarm
→ software generation
→ GlitchLab validation
→ execution mesh
→ outcome
→ memory / research
→ next enterprise delta
```

---

## 12. Common repository requirements

Every repository should eventually contain:

```text
README.md
AI_NATIVE_ROADMAP.md
cyber-lion.manifest.json (or equivalent versioned manifest)
PROCESS_GUARD.md
security / execution scope
CI regression gate
```

Every executable provider should additionally declare:

```text
capabilities
input/output schemas
side effects
required authority
required gates
observability events
rollback/revoke behavior
```
