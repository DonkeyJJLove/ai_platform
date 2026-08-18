# CYBER-LION — Target Architecture

## 1. Architectural position

Cyber-Lion is a **federated cognitive-execution platform**. Existing repositories remain specialized providers. `ai_platform` owns shared contracts, discovery and control-plane state; it does not absorb all implementation code.

The target follows three primary planes:

```text
INF  = infrastructure / transport / execution
SEM  = structure / reasoning / simulation / analysis
MAND = identity / authority / policy / provenance / audit
```

A component may participate in more than one plane, but every consequential path must make the transition between them explicit.

## 2. Target system

```text
                                   CYBER-LION
                                        |
                  +---------------------+---------------------+
                  |        CONTROL PLANE — ai_platform       |
                  | registry · contracts · graph · QV9D      |
                  | policy decisions · configuration · trace |
                  +---------------------+---------------------+
                                        |
            +---------------------------+---------------------------+
            |                           |                           |
       COGNITION / SEM             AUTHORITY / MAND            EXECUTION / INF
            |                           |                           |
   chunk-chunk / HMK9D             Entity Identity             swarm mesh
   HA2D state contract             Provenance                  tool workers
   hipotezy/evidence               Policy/Gate                 sandbox executors
   glitchlab analysis              Execution Receipt           transport/storage
   mosaic structure                Memory Policy               workload identity
   cascade simulator               Audit/Replay                telemetry
            |                           |                           |
            +---------------------------+---------------------------+
                                        |
                              GLOBAL EVENT / GRAPH STATE
                                        |
                              evidence + observations
                                        |
                                    writeups
```

## 3. No direct cognition→effect path

The platform forbids:

```text
LLM / hypothesis / retrieved document
        ↓
consequential API call
```

The required path is:

```text
Observation / Context
        ↓
Reasoning / Hypothesis
        ↓
DecisionProposal
        ↓
Identity + Provenance + Capability
        ↓
GateRequested
        ↓
GateApplied(ALLOW / REDUCE / APPROVE / DENY)
        ↓
Deterministic execution contract
        ↓
ActionExecuted
        ↓
ExecutionReceipt
        ↓
OutcomeObserved
```

## 4. Control plane responsibilities

`ai_platform` target responsibilities:

- schema and contract version registry;
- Entity/Capability/Repository registry;
- QV9D mapping as annotation, not authority;
- routing based on declared capabilities;
- global event metadata and correlation;
- graph state of entities, observations, claims, decisions and executions;
- policy/gate decision interface;
- configuration and deployment topology metadata;
- experiment/research registration;
- replay query contract.

It should **not**:

- own every provider's local state;
- reinterpret provider output as trusted evidence without provenance;
- execute privileged actions directly by default;
- replace local safety mechanisms such as Kubernetes RBAC or GlitchLab Guard.

## 5. Provider responsibilities

### `chunk-chunk`

Provides typed context compression/route proposals and HMK-9D annotations. Compression must preserve audit-critical provenance. A bridge score is not authority.

### `glitchlab`

Provides delta, graph, anomaly, invariant and structural analysis. Local registry stays local. Cross-system integration uses an adapter exporting declared capabilities and typed results.

### `HA2D`

Defines working/persistent cognitive-state contracts and Human–AI replay/HUD semantics. Persistent writes require memory policy events.

### `mosaic_lab_pro.py`

Provides pure structure/abstraction transformations through an extracted library interface. UI remains a consumer of the same library.

### `sbom`

Provides AID compatibility, supply-chain evidence and BOM/gate observations. Existing AID contract remains valid; generalized entity identity wraps it.

### `swarm`

Provides distributed execution, transport and future sandbox/tool workers. It consumes already-authorized execution contracts; it does not infer authority from model output.

### `SymulacjaKaskadySieciowej`

Provides scenario/simulation capability through a versioned adapter. Simulation outcomes are model outputs and carry model/version/parameter/seed provenance.

### `hipotezy_nadawcze_LLM`

Provides research claims and falsification records. Its outputs have epistemic status, never direct execution authority.

### `writeups`

Provides evidence/research documents with metadata. Retrieval returns typed `EvidenceCandidate`, not policy or executable instruction.

## 6. Global graph model

Minimum node types:

```text
Entity
Repository
Artifact
Source
Observation
Claim
Hypothesis
Evidence
Agent
Model
Tool
Capability
Policy
Gate
Decision
Execution
Outcome
Memory
Experiment
```

Minimum edge types:

```text
observed_from
derived_from
supports
contradicts
generated_by
consumed_by
executed_by
authorized_by
blocked_by
depends_on
changed
caused
correlated_with
stored_in
supersedes
validated_by
```

Graph edges carry provenance and confidence where relevant. The graph stores relationships; it does not automatically convert correlation into causation.

## 7. Epistemic state machine

```text
UNKNOWN    → EXPLORE
UNDERSTOOD → DISTILL
FORMALISED → DETERMINISE
```

A transition to `FORMALISED` requires a deterministic representation such as schema, validator, invariant, test or policy. Once formalized, repeated LLM interpretation must not remain the only enforcement mechanism.

## 8. Authority degradation

Target rule:

```text
observability loss
→ trust degradation
→ authority degradation
```

Authority evaluation consumes at least:

```text
identity
policy
provenance completeness
observability state
environment
requested impact
risk state
current execution history
```

Loss of required observability cannot silently preserve previous high authority.

## 9. Security boundaries

At minimum distinguish:

```text
DATA
INSTRUCTION
CONTEXT
AUTHORITY
MEMORY
DECISION
ACTION
```

Co-location in a prompt or context window does not merge trust classes. Adapters must maintain typed provenance through compression, retrieval and inter-agent transfer.

## 10. Design principle

```text
wide exploration
+ narrow, explicit authority
+ deterministic consequence gates
+ complete causal trace
```

This is the architectural core of Cyber-Lion.