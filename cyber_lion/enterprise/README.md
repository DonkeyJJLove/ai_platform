# Cyber-Lion AI-Native Enterprise OS

This directory formalizes the whole DonkeyJJLove repository ecosystem as **one evolving AI-Native enterprise**, rather than a collection of unrelated repositories or a fixed organization chart.

The enterprise is modeled as a **dynamic mosaic of capabilities, agents, evidence, policies, memory and execution domains**.

```text
WORLD / MARKET / SYSTEM SIGNALS
            ↓
        R&D / EVIDENCE
            ↓
   HYPOTHESES / MODELS / RULES
            ↓
        AGENT FOUNDRY
            ↓
  AGENT SPECIFICATIONS + CAPABILITIES
            ↓
     DYNAMIC MOSAIC / SWARMS
            ↓
     SOFTWARE / ACTION PROPOSALS
            ↓
   GLITCHLAB Δ + INVARIANT GATES
            ↓
    AUTHORITY / POLICY / EXECUTION
            ↓
       REAL STATE CHANGE
            ↓
 OBSERVABILITY / OUTCOME / MEMORY
            ↓
      NEXT ENTERPRISE DELTA
```

## Enterprise organs

The current repositories become federated organs with explicit responsibilities:

| Repository | Enterprise role |
|---|---|
| `ai_platform` | Enterprise Control Plane, Agent Foundry, contracts, capability and swarm orchestration |
| `glitchlab` | Software/structure evolution compiler: Δ analysis, AST↔Mosaic, invariants, SAST, repair validation |
| `chunk-chunk` | Process semantics and HMK-9D transition language; chunking, bridges, thresholds, microcode |
| `HA2D` | Context, memory and Human–AI adaptation laboratory; candidate memory and semantic revision |
| `swarm` | Distributed Execution Mesh; workloads, transport, telemetry, orchestration and runtime enforcement |
| `sbom` | Identity/provenance/supply-chain intelligence; AID, entity state, delta and gate evidence |
| `mosaic_lab_pro.py` | Structural Intelligence Engine; graphs, abstraction λ, topology and multi-scale visualization |
| `SymulacjaKaskadySieciowej` | Simulation/Falsification Engine; scenario dynamics, Monte Carlo, Morris/Sobol and stress testing |
| `hipotezy_nadawcze_LLM` | Epistemic Hypothesis Lab; falsifiable model/channel hypotheses and experimental design |
| `writeups` | R&D/evidence corpus, research memory, architecture proposals, publications and promotion pipeline |

Repository boundaries remain useful for ownership and independent evolution. They are **not authority boundaries and not subsystem identities by themselves**.

## Core thesis

The company is not modeled as departments with permanent job functions. It is modeled as a stateful graph:

```text
Enterprise(t) =
  Entities
+ Capabilities
+ AgentSpecs
+ SwarmSpecs
+ Policies
+ Evidence
+ Memory
+ ExecutionDomains
+ Observability
+ Artifacts
```

and evolves by explicit deltas:

```text
Enterprise(t)
→ ChangeProposal
→ Δ analysis
→ invariant/gate evaluation
→ bounded execution
→ OutcomeObserved
→ Enterprise(t+1)
```

## Three planes

Cyber-Lion keeps three planes distinct:

### SEM — intelligence and representation

Research, hypotheses, semantic compression, planning, simulation, code analysis and structural models.

### MAND — mandate, policy and memory

Identity, provenance, authority, policy, gates, context/memory commit, evidence status and promotion rules.

### INF — infrastructure and real effects

Processes, APIs, tools, containers, networks, files, deployments, external writes and physical/cyber-physical systems.

The critical rule is:

```text
SEM proposal
!=
MAND authorization
!=
INF effect
```

## Normative invariants

```text
OPEN INTELLIGENCE != OPEN AUTHORITY
NO ACTION WITHOUT IDENTITY
NO AUTHORITY WITHOUT PROVENANCE
NO MEMORY COMMIT WITHOUT POLICY
NO CROSS-SYSTEM CALL WITHOUT CONTRACT
NO SWARM MEMBER WITHOUT AGENT SPEC
NO AGENT SPAWN WITHOUT IDENTITY + BUDGET + AUTHORITY CEILING
NO OBSERVABILITY LOSS WITHOUT AUTHORITY DEGRADATION
NO PROBABILISTIC OUTPUT DIRECTLY AS EXECUTION
NO RESEARCH CLAIM DIRECTLY PROMOTED TO RUNTIME RULE
NO ENTERPRISE CHANGE WITHOUT DELTA + TEST + ROLLBACK
```

## Documents

- [`AI_NATIVE_ENTERPRISE.md`](AI_NATIVE_ENTERPRISE.md) — whole-enterprise architecture and operating model.
- [`AGENT_SWARM_MODEL.md`](AGENT_SWARM_MODEL.md) — single-agent contract, mosaic cells and dynamic swarm rules.
- [`GENERATION_EVOLUTION_PROTOCOL.md`](GENERATION_EVOLUTION_PROTOCOL.md) — how agents generate and update the polymorphic repository ecosystem.
- [`RND_OPERATING_MODEL.md`](RND_OPERATING_MODEL.md) — how `writeups`, hypotheses and simulations become tested platform knowledge.
- [`REPOSITORY_EVOLUTION_PLAN.md`](REPOSITORY_EVOLUTION_PLAN.md) — concrete target and staged roadmap for every repository.

The executable contracts live in `cyber_lion/enterprise/models.py` and `planner.py`, with regression tests under `cyber_lion/tests/`.
