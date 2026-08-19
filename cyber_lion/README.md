# CYBER-LION — AI-Native Enterprise Control Plane

Status: **EXECUTABLE ARCHITECTURE / ACTIVE EVOLUTION**

Cyber-Lion is a **federated AI-Native enterprise operating system** built from the DonkeyJJLove repository ecosystem. It is not a monolith and does not equate repository boundaries with subsystem or authority boundaries.

Its purpose is to create and evolve agents, compose them into dynamic Mosaic Cells and swarms, connect research to software and execution, and preserve identity, provenance, observability, security and rollback across every consequential transition.

## Core operating model

```text
WORLD / MARKET / SYSTEM
          ↓
      OBSERVATION
          ↓
    R&D / HYPOTHESIS
          ↓
        MISSION
          ↓
      AGENT FOUNDRY
          ↓
     AgentSpec[]
          ↓
  MosaicCell / SwarmSpec
          ↓
   proposal / software Δ
          ↓
 GLITCHLAB / INVARIANTS
          ↓
  POLICY / AUTHORITY GATE
          ↓
     EXECUTION MESH
          ↓
        EFFECT
          ↓
 OBSERVABILITY / OUTCOME
          ↓
 MEMORY / R&D / NEXT Δ
```

## Governing invariants

```text
OPEN INTELLIGENCE != OPEN AUTHORITY
NO ACTION WITHOUT IDENTITY
NO AUTHORITY WITHOUT PROVENANCE
NO ESCALATION WITHOUT APPLIED GATE
NO MEMORY WRITE WITHOUT POLICY
NO DECISION WITHOUT TRACE
NO CROSS-SYSTEM CALL WITHOUT CONTRACT
NO GLOBAL CLAIM FROM LOCAL OBSERVATION
NO LOST OBSERVABILITY WITHOUT AUTHORITY DEGRADATION
NO PROBABILISTIC OUTPUT DIRECTLY AS EXECUTION
NO FORMALISED RULE LEFT AS REPEATED LLM GUESS
NO SWARM MEMBER WITHOUT AGENT SPEC
NO AGENT SPAWN WITHOUT IDENTITY + BUDGET + AUTHORITY CEILING
NO ENTERPRISE CHANGE WITHOUT DELTA + TEST + ROLLBACK
```

## Implemented foundations

Current executable Cyber-Lion includes:

- `EntityIdentity` and lossless SBOM/AID compatibility,
- typed `EventEnvelope`, provenance and authority,
- `CapabilityRegistry`,
- provider plane with provenance receipts,
- Startup Evolution Agent,
- provenance/time-aware MarketEvidenceBook,
- SoftwareBuildPlanner and safe template generation,
- bounded local build runner,
- EvolutionJournal/replay,
- startup CLI/JSON import,
- `AgentSpec`, `MissionSpec`, `SwarmSpec`, `MosaicDelta`,
- deterministic capability-based `SwarmPlanner`.

## Enterprise architecture

The current repository ecosystem is treated as federated organs:

```text
ai_platform              → Enterprise Control Plane / Agent Foundry
glitchlab                → Enterprise Evolution Compiler
chunk-chunk              → Process Semantics / HMK-9D
HA2D                     → Context / Memory / Human-AI Adaptation Lab
swarm                    → Distributed Execution Mesh
sbom                     → Identity / Provenance / Composition Intelligence
mosaic_lab_pro.py        → Structural Intelligence Engine
SymulacjaKaskadySieciowej→ Simulation / Falsification Engine
hipotezy_nadawcze_LLM    → Epistemic Hypothesis Lab
writeups                 → R&D / Enterprise Research Memory
```

Full synthesis: [`enterprise/README.md`](enterprise/README.md).

Key documents:

1. [`enterprise/AI_NATIVE_ENTERPRISE.md`](enterprise/AI_NATIVE_ENTERPRISE.md) — enterprise state model and repository roles.
2. [`enterprise/AGENT_SWARM_MODEL.md`](enterprise/AGENT_SWARM_MODEL.md) — single-agent, Mosaic Cell and dynamic swarm contracts.
3. [`enterprise/GENERATION_EVOLUTION_PROTOCOL.md`](enterprise/GENERATION_EVOLUTION_PROTOCOL.md) — safe generation/update rules for the polymorphic ecosystem.
4. [`enterprise/RND_OPERATING_MODEL.md`](enterprise/RND_OPERATING_MODEL.md) — R&D evidence and promotion pipeline.
5. [`enterprise/REPOSITORY_EVOLUTION_PLAN.md`](enterprise/REPOSITORY_EVOLUTION_PLAN.md) — concrete roadmap for every repository.

## Three planes

```text
SEM  — observation, cognition, representation, simulation, proposals
MAND — identity, provenance, policy, memory, authority, gates
INF  — processes, APIs, files, networks, deployment, external effects
```

Fundamental relation:

```text
SEM proposal != MAND authorization != INF effect
```

## Architecture analysis retained

The original archaeology remains relevant and is preserved as evidence for migration decisions:

- [`REPOSITORY_INVENTORY.md`](REPOSITORY_INVENTORY.md)
- [`CAPABILITY_MAP.md`](CAPABILITY_MAP.md)
- [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md)
- [`CONTRACT_MAP.md`](CONTRACT_MAP.md)
- [`EVENT_DATA_MODEL.md`](EVENT_DATA_MODEL.md)
- [`MIGRATION_MAP.md`](MIGRATION_MAP.md)
- [`SCIENTIFIC_STATUS.md`](SCIENTIFIC_STATUS.md)

## Migration discipline

```text
archaeology
→ typed contract
→ compatibility adapter
→ provider implementation
→ consumer integration
→ negative/adversarial tests
→ observability proof
→ deterministic gate
→ bounded execution
→ outcome/replay
→ deprecate legacy only after compatibility proof
```

Cyber-Lion should evolve aggressively in **proposal and research space**, while consequential execution remains narrow, reconstructable and revocable.

## Workload identity proof boundary

`EntityIdentity` remains descriptive identity; it is not cryptographic attestation. RCCM-1E-I adds an adapter-neutral `WorkloadIdentityProof` whose canonical signed payload is verified through an injected verifier boundary and yields a separate `VerifiedWorkloadIdentity`.

Verification fails closed for invalid signatures, signed-field tampering, invalid validity windows, stale/not-yet-valid proofs, verifier rejection, and verifier exceptions. `VerifiedWorkloadIdentity` deliberately contains no authority or capability grant: **verified identity != authorization**.

The standard-library HMAC profile used by unit tests is a deterministic test fixture only. It is not a production workload identity provider, does not implement custom PKI, and does not access or persist real private-key material.
