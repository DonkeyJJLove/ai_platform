# Cyber-Lion — Enterprise OS AI-Native

Ten katalog formalizuje cały ekosystem repozytoriów DonkeyJJLove jako **jedno ewoluujące przedsiębiorstwo AI-Native**, a nie zbiór niepowiązanych repozytoriów ani stały schemat organizacyjny.

Przedsiębiorstwo jest modelowane jako **dynamiczna mozaika capabilities, agentów, evidence, polityk, pamięci i domen wykonawczych**.

```text
ŚWIAT / RYNEK / SYGNAŁY SYSTEMOWE
            ↓
        R&D / EVIDENCE
            ↓
   HIPOTEZY / MODELE / REGUŁY
            ↓
        AGENT FOUNDRY
            ↓
  SPECYFIKACJE AGENTÓW + CAPABILITIES
            ↓
     DYNAMICZNA MOZAIKA / ROJE
            ↓
     SOFTWARE / ACTION PROPOSALS
            ↓
   GLITCHLAB Δ + INVARIANT GATES
            ↓
    AUTHORITY / POLICY / EXECUTION
            ↓
       RZECZYWISTA ZMIANA STANU
            ↓
 OBSERVABILITY / OUTCOME / MEMORY
            ↓
      KOLEJNA DELTA PRZEDSIĘBIORSTWA
```

## Organy przedsiębiorstwa

Bieżące repozytoria stają się federacyjnymi organami o jawnych odpowiedzialnościach:

| Repozytorium | Rola w przedsiębiorstwie |
|---|---|
| `ai_platform` | Enterprise Control Plane, Agent Foundry, kontrakty, orkiestracja capabilities i rojów |
| `glitchlab` | Kompilator ewolucji software/struktury: analiza Δ, AST↔Mosaic, inwarianty, SAST, walidacja napraw |
| `chunk-chunk` | Semantyka procesu i język przejść HMK-9D; chunking, mosty, progi, microcode |
| `HA2D` | Laboratorium kontekstu, pamięci i adaptacji Human–AI; candidate memory i semantic revision |
| `swarm` | Distributed Execution Mesh; workloady, transport, telemetria, orkiestracja i runtime enforcement |
| `sbom` | Intelligence tożsamości/provenance/supply-chain; AID, stan encji, delta i gate evidence |
| `mosaic_lab_pro.py` | Structural Intelligence Engine; grafy, abstrakcja λ, topologia i wizualizacja wieloskalowa |
| `SymulacjaKaskadySieciowej` | Simulation/Falsification Engine; dynamika scenariuszy, Monte Carlo, Morris/Sobol i stress testing |
| `hipotezy_nadawcze_LLM` | Epistemic Hypothesis Lab; falsyfikowalne hipotezy modelu/kanału i projektowanie eksperymentów |
| `writeups` | Korpus R&D/evidence, pamięć badawcza, propozycje architektury, publikacje i pipeline promocji |

Granice repozytoriów pozostają użyteczne dla ownership i niezależnej ewolucji. **Nie są same w sobie granicami authority ani tożsamościami subsystemów.**

## Teza podstawowa

Przedsiębiorstwo nie jest modelowane jako działy o stałych funkcjach zawodowych. Jest modelowane jako graf stanowy:

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

i ewoluuje przez jawne delty:

```text
Enterprise(t)
→ ChangeProposal
→ analiza Δ
→ ocena invariant/gate
→ bounded execution
→ OutcomeObserved
→ Enterprise(t+1)
```

## Trzy płaszczyzny

Cyber-Lion utrzymuje trzy rozdzielone płaszczyzny:

### SEM — inteligencja i reprezentacja

Badania, hipotezy, kompresja semantyczna, planowanie, symulacja, analiza kodu i modele strukturalne.

### MAND — mandat, polityka i pamięć

Tożsamość, provenance, authority, polityka, gates, commit kontekstu/pamięci, status evidence i reguły promocji.

### INF — infrastruktura i rzeczywiste skutki

Procesy, API, narzędzia, kontenery, sieci, pliki, deploymenty, zewnętrzne zapisy i systemy fizyczne/cyber-fizyczne.

Reguła krytyczna:

```text
SEM proposal
!=
MAND authorization
!=
INF effect
```

## Inwarianty normatywne

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

## Dokumenty

- [`AI_NATIVE_ENTERPRISE.md`](AI_NATIVE_ENTERPRISE.md) — architektura całego przedsiębiorstwa i model operacyjny.
- [`AGENT_SWARM_MODEL.md`](AGENT_SWARM_MODEL.md) — kontrakt pojedynczego agenta, Mosaic Cells i reguły dynamicznego roju.
- [`GENERATION_EVOLUTION_PROTOCOL.md`](GENERATION_EVOLUTION_PROTOCOL.md) — sposób, w jaki agenci generują i aktualizują polimorficzny ekosystem repozytoriów.
- [`RND_OPERATING_MODEL.md`](RND_OPERATING_MODEL.md) — sposób, w jaki `writeups`, hipotezy i symulacje stają się przetestowaną wiedzą platformy.
- [`REPOSITORY_EVOLUTION_PLAN.md`](REPOSITORY_EVOLUTION_PLAN.md) — konkretny target i etapowa roadmapa dla każdego repozytorium.

Wykonywalne kontrakty znajdują się w `cyber_lion/enterprise/models.py` i `planner.py`, a testy regresyjne pod `cyber_lion/tests/`.
