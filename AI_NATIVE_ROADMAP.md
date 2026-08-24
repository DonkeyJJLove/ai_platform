# ai_platform — mapa rozwoju przedsiębiorstwa AI-Native

`ai_platform` ewoluuje z repozytorium specyfikacji semantycznych i platformowych w **Cyber-Lion Enterprise Control Plane oraz Agent Foundry**.

Startup Evolution Agent jest pierwszym konkretnym agentem organizacyjnym zbudowanym na platformie. Nie stanowi docelowej tożsamości całej platformy.

## Cel

```text
MISJA
→ wymagania dotyczące capabilities
→ Agent Foundry
→ kandydaci AgentSpec
→ dynamiczna MosaicCell / SwarmSpec
→ polityka + limit authority
→ provider wykonawczy
→ obserwowalność + receipts
→ wynik
→ pamięć / R&D
→ kolejna delta organizacyjna
```

## Sekwencja budowy

### 1. Agent Foundry

- AgentSpec / AgentInstance,
- Agent Registry,
- lifecycle i supersession,
- niezależność od providera/modelu,
- polityka kontekstu i pamięci,
- wymagania dotyczące authority i obserwowalności.

### 2. Dynamiczny Swarm Control Plane

- MissionSpec,
- SwarmSpec,
- MosaicCell,
- MosaicDelta,
- deterministyczny planner pokrycia capabilities,
- kontrakty spawn/delegation/dissolve,
- reguły topologii zależne od klasy ryzyka.

### 3. Enterprise Graph

Ujednolicenie projekcji:

```text
repozytoria
encje
agenci
roje
capabilities
polityki
authority
provenance
evidence
wykonanie
artefakty
```

### 4. Most Evolution Compiler

Przekazywanie zmian source/AgentSpec/SwarmSpec/policy/schema do GlitchLab w celu analizy delty i sprawdzenia inwariantów.

### 5. Execution Mesh

Wykorzystanie `swarm` jako podstawy rozproszonego wykonywania workloadów, wiązania tożsamości, telemetrii, ograniczeń runtime oraz mechanizmów revoke/freeze.

### 6. Promocja R&D

Połączenie `writeups`, `hipotezy_nadawcze_LLM` i providerów symulacji przez jawne kontrakty evidence/hypothesis/spec-candidate.

## Odniesienia normatywne

- [`cyber_lion/enterprise/README.md`](cyber_lion/enterprise/README.md)
- [`cyber_lion/enterprise/AI_NATIVE_ENTERPRISE.md`](cyber_lion/enterprise/AI_NATIVE_ENTERPRISE.md)
- [`cyber_lion/enterprise/AGENT_SWARM_MODEL.md`](cyber_lion/enterprise/AGENT_SWARM_MODEL.md)
- [`cyber_lion/enterprise/GENERATION_EVOLUTION_PROTOCOL.md`](cyber_lion/enterprise/GENERATION_EVOLUTION_PROTOCOL.md)
- [`cyber_lion/enterprise/RND_OPERATING_MODEL.md`](cyber_lion/enterprise/RND_OPERATING_MODEL.md)
- [`cyber_lion/enterprise/REPOSITORY_EVOLUTION_PLAN.md`](cyber_lion/enterprise/REPOSITORY_EVOLUTION_PLAN.md)

## Inwarianty

```text
repo != subsystem
model != tożsamość agenta
registered capability != authority
semantic state != permission
working context != committed memory
simulation != observation
generated artifact != trusted artifact
swarm formation != credential inheritance
observability loss ⇒ authority degradation
```
