# Model agenta i mozaiki roju

## 1. Pojedynczy agent jako formalny obiekt organizacyjny

Agent AI nie jest definiowany przez prompt ani nazwę modelu. W Cyber-Lion agent jest wersjonowanym kontraktem:

```text
AgentSpec = (
  identity,
  mission,
  role,
  capabilities,
  inputs,
  outputs,
  context_scope,
  memory_policy,
  authority_ceiling,
  execution_domain,
  observability_requirements,
  budgets,
  stop_conditions,
  escalation_policy,
  epistemic_requirements,
  process_coordinates
)
```

Provider modelu jest szczegółem implementacyjnym podporządkowanym funkcji policy.

```text
AgentSpec
    ↓
Policy Provider (LLM / rules / hybrid / simulator)
    ↓
Action Proposal
    ↓
Policy / Gate
    ↓
Execution Provider
```

## 2. Stan agenta

Działający agent ma jawny stan niezależny od ukrytych aktywacji modelu:

```text
AgentState(t) = {
  instance_id,
  agent_spec_version,
  mission_id,
  active_task,
  context_refs,
  memory_refs,
  evidence_refs,
  capability_set,
  effective_authority,
  observability_state,
  budget_remaining,
  current_process_vector,
  last_decision,
  lifecycle_state
}
```

Lifecycle:

```text
DEFINED
→ ADMITTED
→ ACTIVE
→ DEGRADED
→ PAUSED
→ COMPLETED
→ DISSOLVED

lub

ACTIVE → QUARANTINED → REVOKED
```

## 3. Adnotacja procesu HMK-9D

Wektor HMK-9D może adnotować przejście agenta:

```text
r(Δ) = [T,S,R,E,I,F,A,P,D]
```

Interpretacja platformowa:

- `T` — obciążenie czasowe/opóźnienie,
- `S` — spójność semantyczna,
- `R` — obciążenie sprzężeniem/relacjami,
- `E` — proxy kosztu zasobowego/poznawczego,
- `I` — klarowność tożsamości,
- `F` — klarowność misji/mandatu,
- `A` — abstrakcja/granularność chunków,
- `P` — predykcja/confidence,
- `D` — twardość zobowiązania.

Wektor ten jest **metadanymi opisowymi/kontrolnymi**. Nie jest permission.

Reguła przejścia:

```text
SemanticTransition(Δ)
→ EventEnvelope
→ invariant evaluation
→ authority evaluation
→ optional effect
```

## 4. Mosty jako operatory procesu

Mosty HMK są interpretowane jako nazwane transformacje dostępne dla plannerów agentów.

Przykłady:

```text
PLAN_PAUSE
→ zmniejsz commitment / wymuś jawny plan

CORE_PERIPH
→ zmniejsz scope / wyizoluj rdzeń misji

VILLAGE_CITY
→ przełącz widok lokalny ↔ systemowy

EDGE_PATIENCE
→ zmień granularność chunków / kompromis precyzja–szybkość

LOCUS_MEDIUM_MANDATE
→ uczyń identity/channel/authority jawnymi

THRESHOLD_TRANSITION
→ przygotuj granicę gate/commit
```

Mosty mogą zmieniać reprezentację stanu lub strategię planowania. Nie mogą omijać kontroli MAND.

---

## 5. Mosaic Cell

Mosaic Cell jest najmniejszą wieloagentową jednostką organizacyjną.

```text
MosaicCell = {
  cell_id,
  mission_id,
  member_agent_ids,
  capability_coverage,
  topology,
  context_scope,
  authority_ceiling,
  observability_requirement,
  synchronization_policy,
  completion_condition
}
```

Cell nie musi być trwała. Może istnieć dla jednego artefaktu, jednego incydentu, jednego eksperymentu rynkowego albo jednej delty software.

Przykłady:

```text
Research Cell
  Researcher Agent
  Hypothesis Auditor Agent
  Simulation Agent

Software Cell
  Architect Agent
  Builder Agent
  Security Agent
  Test/Verifier Agent

Market Cell
  Market Intelligence Agent
  Product Hypothesis Agent
  Economics Agent
```

## 6. Rój

Rój jest ograniczonym w czasie grafem Mosaic Cells i/lub agentów utworzonym wokół misji.

```text
SwarmSpec = (
  swarm_id,
  mission,
  required_capabilities,
  member_agents,
  topology,
  coordination_policy,
  authority_ceiling,
  observability_quorum,
  risk_class,
  resource_budget,
  spawn_policy,
  reconfiguration_policy,
  dissolve_condition
)
```

Sam rój posiada tożsamość i emituje zdarzenia.

## 7. Dynamiczne formowanie

Formowanie wynika z pokrycia capabilities:

```text
MissionSpec
→ required capabilities
→ candidate AgentSpecs
→ policy filtering
→ authority filtering
→ observability filtering
→ minimal sufficient set
→ topology selection
→ SwarmSpec
```

Domyślnym celem jest ograniczony problem set-cover:

```text
minimalizuj:
  number_of_agents
+ coordination_cost
+ authority_exposure
+ expected_latency

przy warunkach:
  capability_coverage = 100%
  authority <= mission ceiling
  observability >= required quorum
  resource budget respected
  risk-class invariants satisfied
```

## 8. Klasy ryzyka i wymagana topologia

### GREEN

Analiza read-only, odwracalne transformacje, lokalne badania.

Dozwolone:

- małe autonomiczne cells,
- brak obowiązkowego niezależnego verifiera, jeżeli wszystkie efekty są non-consequential.

### AMBER

Zapisy kodu, wywołania zewnętrzne, tworzenie persistent memory candidate, praca cross-domain.

Wymagane:

- jawny policy/gate,
- niezależna capability walidacji,
- pełny trace/correlation,
- rollback.

### RED

Deployment produkcyjny, privileged access, zobowiązanie finansowe, infrastruktura krytyczna, nieodwracalne skutki zewnętrzne.

Wymagane:

- niezależny verifier agent lub human approval,
- deterministyczny enforcement,
- pełne provenance,
- 100% pokrycia wymaganej obserwacji,
- ograniczony blast radius,
- capability revoke/freeze.

## 9. Reguły spawn

Rój może dynamicznie utworzyć agenta tylko wtedy, gdy:

```text
required capability is not sufficiently covered
AND
agent template exists
AND
new identity is issued
AND
effective authority <= swarm ceiling
AND
resource budget remains
AND
observability contract can be satisfied
AND
spawn event is emitted
```

Zakazane:

```text
anonymous sub-agent
inherit all parent credentials
implicit memory access
implicit external egress
authority expansion by delegation chain
```

## 10. Delegacja

Delegacja jest reprezentowana jawnie:

```text
Delegation = {
  delegator,
  delegate,
  mission/task scope,
  capability subset,
  authority subset,
  data scope,
  expiration,
  correlation_id
}
```

Reguła monotoniczna:

```text
Authority(delegate)
⊆ Authority(delegator)
```

Bez jawnego nowego rekordu delegacji nie wolno przyjmować założenia o dziedziczeniu tranzytywnym.

## 11. Wybór topologii

Możliwe topologie:

### Pipeline liniowy

Użyteczny, gdy artefakty przechodzą przez wyraźne transformacje.

```text
Research → Architect → Builder → Security → Verifier
```

### Hub-and-spoke

Użyteczny dla koordynatora ze specjalizowanymi workerami.

```text
            Coordinator
           /     |      \
      Research  Code   Security
```

### Peer-review mesh

Użyteczny, gdy istotna jest różnorodność modeli/providerów.

```text
A ↔ B ↔ C
↖   ↕   ↗
  Verifier
```

### Hierarchia mozaikowa

Użyteczna dla dużych misji:

```text
Mission Swarm
├── Market Cell
├── Product Cell
├── Software Cell
├── Security Cell
└── R&D Cell
```

Topologia jest wybierana na podstawie struktury misji i ryzyka, a nie preferencji estetycznej.

## 12. Reguły rekonfiguracji

Rój może się rekonfigurować, gdy:

```text
capability gap detected
agent failure
observability degradation
mission decomposition changes
risk class changes
new evidence invalidates plan
budget threshold crossed
```

Rekonfiguracja tworzy `MosaicDelta`:

```text
MosaicDelta = {
  added_nodes,
  removed_nodes,
  added_edges,
  removed_edges,
  capability_changes,
  authority_changes,
  reason,
  evidence_refs
}
```

`MosaicDelta` rozszerzająca authority jest consequential i wymaga gate.

## 13. Observability quorum

`observability_quorum` nie jest wyłącznie procentem agentów emitujących logi. Jest pokryciem **wymaganego łańcucha przyczynowego**.

Dla consequential execution:

```text
proposal
→ decision
→ gate
→ capability issue
→ execution
→ effect
→ outcome
```

wszystkie elementy muszą być rekonstruowalne.

Jeżeli zniknie którekolwiek wymagane ogniwo:

```text
observability state ↓
→ effective authority ↓
```

## 14. Obsługa konfliktów

Agenci mogą się nie zgadzać. Niezgodność jest zachowywana jako evidence zamiast być nadpisywana.

```text
Agent A: hypothesis H, confidence .72
Agent B: hypothesis ¬H, confidence .64
```

staje się:

```text
ConflictRecord
→ evidence comparison
→ experiment/simulation request
→ updated confidence
```

Konsensus większościowy nie jest domyślnym mechanizmem prawdy.

## 15. Rozwiązanie roju

Rój jest rozwiązywany, gdy:

```text
mission completed
mission falsified
budget exhausted
risk no longer acceptable
required observability cannot be restored
capabilities moved to a stable cached cell
```

Dissolution emituje stan końcowy i unieważnia tymczasowe credentials/capabilities.

## 16. Trwała topologia jako wyuczona organizacja

Wielokrotnie skuteczne roje mogą stać się szablonami wielokrotnego użytku:

```text
successful SwarmSpec instances
→ pattern detection
→ candidate template
→ simulation / review
→ SwarmTemplate vN
```

W ten sposób organizacja uczy się własnej struktury bez trwałego jej zamrażania.
