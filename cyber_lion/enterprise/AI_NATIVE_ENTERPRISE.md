# AI-Native Enterprise Architecture

## 1. Purpose

Cyber-Lion treats the company itself as an evolving software-defined system. Humans, AI agents, repositories, services, policies, research artifacts and runtime resources are all represented as typed entities connected by explicit relations.

The purpose is not to automate a traditional organization chart. The purpose is to create an organization whose structure can change as quickly as the problem being solved, while retaining identity, provenance, security, observability and rollback.

The operating objective is:

> **Maximize safely reachable capability per unit of time and evidence.**

This means the enterprise must be able to create, specialize, combine and dissolve agents rapidly, but it must never confuse intelligence with authority or semantic confidence with permission to change reality.

---

## 2. Enterprise state model

At time `t` the enterprise is represented as:

```text
E(t) = (
  N,      # entities/nodes
  R,      # typed relations
  C,      # capabilities
  A,      # agent definitions and active instances
  W,      # swarm/mosaic structures
  P,      # policies / authority ceilings
  M,      # committed memory and context
  D,      # evidence / research / observations
  X,      # execution domains and resources
  O       # observability state
)
```

An enterprise change is not a free-form rewrite. It is an explicit delta:

```text
ΔE : E(t) → E(t+1)
```

Every consequential `ΔE` must answer:

```text
WHY?
FROM WHICH EVIDENCE?
WHO / WHAT IS CHANGING?
WHICH CONTRACTS CHANGE?
WHICH AUTHORITY IS REQUIRED?
WHICH OBSERVABILITY CAN DEGRADE?
WHAT IS THE BLAST RADIUS?
HOW IS IT TESTED?
HOW IS IT REPLAYED?
HOW IS IT ROLLED BACK?
```

---

## 3. Organizational topology: capability mosaic, not permanent departments

Traditional organization:

```text
Department
→ Job title
→ Static responsibility
→ Ticket queue
```

Cyber-Lion target:

```text
Mission
→ required capabilities
→ evidence/risk context
→ Agent Foundry
→ smallest sufficient mosaic
→ bounded authority
→ execution
→ outcome
→ dissolve/reconfigure
```

A stable team may exist where repeated work justifies it, but it is a cached topology rather than a fundamental organizational primitive.

The primary organizational unit is the **Mosaic Cell**:

```text
MosaicCell = {
  mission,
  member agents,
  capabilities,
  authority ceiling,
  data/context scope,
  execution domain,
  observability requirement,
  success/termination conditions
}
```

Multiple cells can combine into a temporary swarm. A swarm can split, merge or dissolve as its state changes.

---

## 4. Enterprise planes

### 4.1 SEM — Semantic / Intelligence Plane

Responsible for interpreting, structuring, hypothesizing, simulating and proposing.

Primary providers:

- `writeups` — evidence/research corpus,
- `hipotezy_nadawcze_LLM` — falsifiable hypothesis design,
- `chunk-chunk` — transition/chunk/bridge language,
- `HA2D` — semantic/context adaptation experiments,
- `mosaic_lab_pro.py` — structural/topological representations,
- `SymulacjaKaskadySieciowej` — simulation and stress testing,
- `glitchlab` — code/structure analysis and change interpretation,
- model providers registered through `ai_platform`.

SEM may generate:

```text
Observation
Hypothesis
Structure
Plan
Simulation
Code proposal
FixCandidate
Swarm proposal
Policy proposal
```

SEM does **not** directly authorize consequential execution.

### 4.2 MAND — Mandate / Control Plane

Responsible for:

- identity,
- provenance,
- policy,
- authority ceilings,
- gates,
- memory promotion,
- epistemic status,
- capability registration,
- swarm admission,
- research-to-runtime promotion.

Primary providers:

- `ai_platform`,
- `sbom` AID/provenance concepts,
- HA2D-derived memory contracts after formalization,
- Cyber-Lion EventEnvelope / Capability Registry.

### 4.3 INF — Infrastructure / Effect Plane

Responsible for real execution:

- process creation,
- filesystem mutation,
- code execution,
- network calls,
- deployment,
- storage,
- external messages,
- paid actions,
- cyber-physical effects.

Primary provider direction:

- `swarm` → generic Execution Mesh,
- bounded local build runtime in `ai_platform`,
- future isolated execution providers,
- infrastructure and external SaaS connectors.

---

## 5. Enterprise organs and their contracts

### `ai_platform` — Enterprise Control Plane + Agent Foundry

Must become the place where the enterprise describes **what may exist and how it may compose**, not where every domain implementation is copied.

Responsibilities:

```text
EntityIdentity
EventEnvelope
CapabilityRegistry
AgentRegistry
AgentFactory
SwarmPlanner
Policy/Gate interfaces
Provider registry
Enterprise graph projection
mission lifecycle
startup/product control loops
```

### `glitchlab` — Evolution Compiler

GlitchLab becomes the compiler/validator for changes to the organization and its software.

Current strengths already include:

```text
Δ-first analysis
AST ↔ Mosaic Φ/Ψ
I1–I4 invariant gates
living spec thresholds
SAST-Bridge
FixCandidate flow
BUS / EGDB / HUD observability
```

Target extension:

```text
Source code Δ
AgentSpec Δ
SwarmSpec Δ
Policy Δ
Schema Δ
Memory-contract Δ
Repository-manifest Δ
```

A Cyber-Lion change should eventually compile into a GlitchLab change report before it can become a consequential enterprise state transition.

### `chunk-chunk` — Process Semantics / Transition Microcode

HMK-9D becomes an optional semantic control representation for trajectories.

Its 9D vector:

```text
[T, S, R, E, I, F, A, P, D]
```

is interpreted at platform level as **process metadata**, not as authority.

Useful mappings:

```text
T → latency / temporal position
S → semantic coherence
R → relation/coupling load
E → computational/cognitive cost proxy
I → identity clarity
F → mission/function clarity
A → abstraction granularity
P → predictive confidence
D → commitment hardness
```

Bridges become named transition operators. `Próg–Przejście` becomes particularly relevant to gate boundaries.

Target: compile HMK-9D microcode into typed process transitions and event annotations while keeping permission decisions outside the semantic model.

### `HA2D` — Context / Memory / Human–AI Adaptation Lab

HA2D contributes:

```text
PCE persistent context
MCV temporary memory
SNAP / THOUGHT / MORPH transitions
CMM integrity records
SMA / _neuro state-dynamics heuristics
HUD / human interaction
```

Target distinction:

```text
working context
!=
memory candidate
!=
committed organizational memory
```

A future Cyber-Lion Memory Service should use the useful CMM concepts but add:

```text
entity identity
provenance
source evidence
policy_id
candidate_event_id
retention class
sensitivity class
supersession relation
commit/reject decision
```

`_neuro` remains an experimental process-state model; it may affect prioritization or diagnostics but cannot independently create authority.

### `swarm` — Execution Mesh

Current repo already demonstrates distributed services, telemetry, Kubernetes, Istio, monitoring and RBAC. Target is to generalize from a drone laboratory to a generic agent/workload execution mesh.

Target responsibilities:

```text
AgentInstance launch
Workload identity binding
ExecutionDomain isolation
Capability materialization
resource budgets
egress control
inter-agent transport
runtime telemetry
process/result receipts
kill/freeze/revoke
```

The execution mesh must consume `AgentSpec/SwarmSpec` and policy decisions from MAND rather than infer permission from deployment configuration.

### `sbom` — Provenance / Identity / Supply-Chain Intelligence

AID is promoted as a compatibility anchor for enterprise entity identity.

SBOM concepts generalize to:

```text
software composition
agent composition
model composition
tool composition
policy composition
swarm composition
```

Target extension is a broader **Relation / Decision BOM**:

```text
Entity
→ components
→ sources
→ dependencies
→ capabilities
→ policy/gate decisions
→ generated artifacts
→ execution receipts
```

The SBOM lab remains the supply-chain specialization; shared identity/provenance lives in platform contracts.

### `mosaic_lab_pro.py` — Structural Intelligence Engine

The valuable primitive is not the GUI itself but multi-scale graph structure:

```text
micro nodes
→ grouped cells
→ supergraph
→ λ-controlled abstraction
```

Target extraction:

```text
mosaic_core/
  graph.py
  topology.py
  abstraction.py
  path.py
  validation.py
```

It should accept not only Python AST but also:

```text
repository graph
agent graph
swarm graph
capability graph
authority graph
provenance graph
```

The GUI becomes one consumer of this engine.

### `SymulacjaKaskadySieciowej` — Simulation / Falsification Engine

The domain model remains intact. The reusable contribution is its package/interface discipline and methods:

```text
deterministic scenario run
Monte Carlo
Morris
Sobol
bifurcation / phase transition
stress envelope
```

Target: define a generic SimulationProvider interface while preserving individual models as domain plugins.

Cyber-Lion should be able to ask:

```text
What happens to the organization if this policy changes?
What if one agent class fails?
What if evidence latency doubles?
What if authority is over-delegated?
What if the market moves before software ships?
```

### `hipotezy_nadawcze_LLM` — Epistemic Hypothesis Lab

This repository remains intentionally small and rigorous.

Target structure per hypothesis:

```text
Hypothesis
ObservableConsequences
Falsifiers
EvidenceFor
EvidenceAgainst
AlternativeExplanations
Confidence
ExperimentSpec
CurrentStatus
```

Its output feeds R&D and simulation. It must never directly become a production policy.

### `writeups` — R&D / Enterprise Research Memory

`writeups` becomes the formal R&D organ and evidence archive.

It contains:

```text
research questions
security architectures
falsification reports
experiments
OSINT
probabilistic studies
publications
reference designs
```

Its promotion path to production is explicitly gated; see `RND_OPERATING_MODEL.md`.

---

## 6. Agent Foundry

The platform creates agents from explicit specifications rather than ad hoc prompts.

```text
Mission
↓
required capabilities
↓
context / evidence scope
↓
risk class
↓
authority ceiling
↓
memory policy
↓
observability requirements
↓
AgentSpec
↓
validation
↓
AgentInstance
```

An agent may use an LLM, deterministic code, rules, simulation or a hybrid policy. The identity of the agent is independent of the model provider.

Changing GPT/model/backend does not automatically create a new organizational role; changing mission, authority or contract may.

---

## 7. Dynamic swarm formation

A mission is decomposed into required capabilities. The Swarm Planner selects the smallest sufficient set of agent definitions that covers them within risk and authority constraints.

Conceptually:

```text
mission capabilities = {research, architecture, code, security, validation}

available agents:
A = {research, hypothesis}
B = {architecture, code}
C = {security, validation}
D = {code}

minimal sufficient swarm = {A, B, C}
```

The planner should optimize not only number of agents but:

```text
coverage
observability
coordination cost
authority exposure
model/provider diversity
latency
reliability
```

A swarm is temporary unless repeated mission patterns justify caching its topology.

---

## 8. Authority topology

Authority is monotonic downward:

```text
EnterprisePolicy
  ⊇ DomainPolicy
    ⊇ SwarmAuthority
      ⊇ AgentAuthority
        ⊇ ActionAuthority
```

A child may narrow authority. It may not expand it.

Dynamic agent creation therefore follows:

```text
parent authority ceiling
∩ mission authority
∩ agent template ceiling
∩ current observability allowance
= effective authority
```

---

## 9. Observability-conditioned autonomy

Autonomy is a controlled variable:

```text
Autonomy ∝
(Provenance × Observability × Controllability × EvidenceQuality)
/
(Impact × Uncertainty × BoundaryExposure)
```

Operational rule:

```text
required observability missing
→ authority degrade
→ read-only / pause / freeze / revoke
```

For a high-consequence swarm, losing one critical trace relation should not merely create an alert; it should reduce the reachable execution state.

---

## 10. Human role

Humans do not disappear from this enterprise. Their role changes from manually carrying every task to defining/approving:

```text
mission
values / constraints
authority ceilings
high-impact gates
strategic evidence interpretation
exceptions
capital allocation
risk appetite
```

Human interaction itself is modeled as events and decisions so that it remains observable and reconstructable.

---

## 11. Definition of done for AI-Native enterprise evolution

A new capability is not complete when code exists. It is complete when:

```text
1. capability has identity and version
2. AgentSpec can consume it
3. required authority is explicit
4. required observations are explicit
5. execution path is bounded
6. events/provenance are emitted
7. GlitchLab can inspect its delta
8. tests include negative/adversarial cases
9. rollback/revocation exists
10. R&D status is linked to evidence
11. README/registry/roadmap are synchronized
12. swarm composition rules understand the capability
```
