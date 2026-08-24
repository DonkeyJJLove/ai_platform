# Architektura przedsiębiorstwa AI-Native

## 1. Cel

Cyber-Lion traktuje samo przedsiębiorstwo jako ewoluujący system software-defined. Ludzie, agenci AI, repozytoria, usługi, polityki, artefakty badawcze i zasoby runtime są reprezentowane jako typowane encje połączone jawnymi relacjami.

Celem nie jest automatyzacja tradycyjnego schematu organizacyjnego. Celem jest stworzenie organizacji, której struktura może zmieniać się równie szybko jak rozwiązywany problem, przy zachowaniu tożsamości, provenance, bezpieczeństwa, obserwowalności i rollbacku.

Cel operacyjny:

> **Maksymalizuj bezpiecznie osiągalną capability na jednostkę czasu i evidence.**

Oznacza to, że przedsiębiorstwo musi szybko tworzyć, specjalizować, łączyć i rozwiązywać agentów, ale nigdy nie może mylić intelligence z authority ani confidence semantycznego z pozwoleniem na zmianę rzeczywistości.

---

## 2. Model stanu przedsiębiorstwa

W chwili `t` przedsiębiorstwo jest reprezentowane jako:

```text
E(t) = (
  N,      # encje/węzły
  R,      # typowane relacje
  C,      # capabilities
  A,      # definicje agentów i aktywne instancje
  W,      # struktury rojów/mozaik
  P,      # polityki / limity authority
  M,      # committed memory i context
  D,      # evidence / research / observations
  X,      # domeny wykonawcze i zasoby
  O       # stan obserwowalności
)
```

Zmiana przedsiębiorstwa nie jest free-form rewrite. Jest jawną deltą:

```text
ΔE : E(t) → E(t+1)
```

Każda consequential `ΔE` musi odpowiadać na pytania:

```text
DLACZEGO?
Z JAKIEGO EVIDENCE?
KTO / CO SIĘ ZMIENIA?
KTÓRE KONTRAKTY SIĘ ZMIENIAJĄ?
JAKIE AUTHORITY JEST WYMAGANE?
KTÓRA OBSERWOWALNOŚĆ MOŻE ULEC DEGRADACJI?
JAKI JEST BLAST RADIUS?
JAK TO JEST TESTOWANE?
JAK TO JEST ODTWARZANE?
JAK WYKONUJE SIĘ ROLLBACK?
```

---

## 3. Topologia organizacyjna: mozaika capabilities, nie stałe działy

Tradycyjna organizacja:

```text
Dział
→ Stanowisko
→ Stała odpowiedzialność
→ Kolejka ticketów
```

Target Cyber-Lion:

```text
Misja
→ wymagane capabilities
→ kontekst evidence/ryzyka
→ Agent Foundry
→ najmniejsza wystarczająca mozaika
→ ograniczone authority
→ execution
→ outcome
→ dissolve/reconfigure
```

Stabilny zespół może istnieć tam, gdzie uzasadnia go powtarzalna praca, ale jest wtedy cache'owaną topologią, a nie fundamentalnym prymitywem organizacyjnym.

Podstawową jednostką organizacyjną jest **Mosaic Cell**:

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

Wiele cells może łączyć się w tymczasowy rój. Rój może się dzielić, scalać lub rozwiązywać wraz ze zmianą swojego stanu.

---

## 4. Płaszczyzny przedsiębiorstwa

### 4.1 SEM — Semantic / Intelligence Plane

Odpowiada za interpretowanie, strukturyzowanie, tworzenie hipotez, symulowanie i proponowanie.

Główni providerzy:

- `writeups` — korpus evidence/research,
- `hipotezy_nadawcze_LLM` — projektowanie falsyfikowalnych hipotez,
- `chunk-chunk` — język transition/chunk/bridge,
- `HA2D` — eksperymenty adaptacji semantic/context,
- `mosaic_lab_pro.py` — reprezentacje strukturalne/topologiczne,
- `SymulacjaKaskadySieciowej` — symulacja i stress testing,
- `glitchlab` — analiza kodu/struktury i interpretacja zmian,
- providerzy modeli rejestrowani przez `ai_platform`.

SEM może generować:

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

SEM **nie** autoryzuje bezpośrednio consequential execution.

### 4.2 MAND — Mandate / Control Plane

Odpowiada za:

- identity,
- provenance,
- policy,
- limity authority,
- gates,
- promocję pamięci,
- status epistemiczny,
- rejestrację capabilities,
- swarm admission,
- promocję research-to-runtime.

Główni providerzy:

- `ai_platform`,
- koncepcje AID/provenance z `sbom`,
- kontrakty pamięci wyprowadzone z HA2D po formalizacji,
- Cyber-Lion EventEnvelope / Capability Registry.

### 4.3 INF — Infrastructure / Effect Plane

Odpowiada za rzeczywiste wykonanie:

- tworzenie procesów,
- mutacje filesystemu,
- wykonanie kodu,
- wywołania sieciowe,
- deployment,
- storage,
- wiadomości zewnętrzne,
- działania płatne,
- skutki cyber-fizyczne.

Kierunek głównych providerów:

- `swarm` → generyczny Execution Mesh,
- ograniczony lokalny build runtime w `ai_platform`,
- przyszli izolowani providerzy wykonawczy,
- infrastruktura i zewnętrzne konektory SaaS.

---

## 5. Organy przedsiębiorstwa i ich kontrakty

### `ai_platform` — Enterprise Control Plane + Agent Foundry

Ma stać się miejscem, w którym przedsiębiorstwo opisuje **co może istnieć i jak może się komponować**, a nie miejscem kopiowania każdej implementacji domenowej.

Odpowiedzialności:

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

GlitchLab staje się kompilatorem/walidatorem zmian organizacji i jej software.

Obecne mocne strony obejmują już:

```text
Δ-first analysis
AST ↔ Mosaic Φ/Ψ
I1–I4 invariant gates
living spec thresholds
SAST-Bridge
FixCandidate flow
BUS / EGDB / HUD observability
```

Rozszerzenie targetowe:

```text
Source code Δ
AgentSpec Δ
SwarmSpec Δ
Policy Δ
Schema Δ
Memory-contract Δ
Repository-manifest Δ
```

Zmiana Cyber-Lion powinna docelowo kompilować się do raportu zmiany GlitchLab, zanim stanie się consequential enterprise state transition.

### `chunk-chunk` — Process Semantics / Transition Microcode

HMK-9D staje się opcjonalną reprezentacją kontroli semantycznej trajektorii.

Jego wektor 9D:

```text
[T, S, R, E, I, F, A, P, D]
```

jest interpretowany na poziomie platformy jako **metadane procesu**, nie jako authority.

Użyteczne mapowania:

```text
T → latency / pozycja czasowa
S → spójność semantyczna
R → obciążenie relacjami/sprzężeniem
E → proxy kosztu obliczeniowego/poznawczego
I → klarowność tożsamości
F → klarowność misji/funkcji
A → granularność abstrakcji
P → predictive confidence
D → twardość commitment
```

Mosty stają się nazwanymi operatorami przejść. `Próg–Przejście` staje się szczególnie istotny na granicach gate.

Target: kompilować microcode HMK-9D do typowanych przejść procesu i adnotacji zdarzeń, pozostawiając decyzje permission poza modelem semantycznym.

### `HA2D` — Context / Memory / Human–AI Adaptation Lab

HA2D wnosi:

```text
PCE persistent context
MCV temporary memory
SNAP / THOUGHT / MORPH transitions
CMM integrity records
SMA / _neuro state-dynamics heuristics
HUD / human interaction
```

Rozróżnienie targetowe:

```text
working context
!=
memory candidate
!=
committed organizational memory
```

Przyszły Cyber-Lion Memory Service powinien wykorzystywać użyteczne koncepcje CMM, ale dodać:

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

`_neuro` pozostaje eksperymentalnym modelem process-state; może wpływać na priorytetyzację lub diagnostykę, ale nie może samodzielnie tworzyć authority.

### `swarm` — Execution Mesh

Obecne repo demonstruje już rozproszone usługi, telemetrię, Kubernetes, Istio, monitoring i RBAC. Target polega na uogólnieniu laboratorium dronów do generycznego execution mesh agentów/workloadów.

Docelowe odpowiedzialności:

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

Execution mesh musi konsumować `AgentSpec/SwarmSpec` i decyzje policy z MAND zamiast wywodzić permission z konfiguracji deploymentu.

### `sbom` — Provenance / Identity / Supply-Chain Intelligence

AID jest promowany jako compatibility anchor dla tożsamości encji przedsiębiorstwa.

Koncepcje SBOM są uogólniane do:

```text
software composition
agent composition
model composition
tool composition
policy composition
swarm composition
```

Rozszerzeniem targetowym jest szerszy **Relation / Decision BOM**:

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

Lab SBOM pozostaje specjalizacją supply-chain; wspólna identity/provenance żyje w kontraktach platformy.

### `mosaic_lab_pro.py` — Structural Intelligence Engine

Wartościowym prymitywem nie jest samo GUI, lecz wieloskalowa struktura grafowa:

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

Silnik powinien akceptować nie tylko Python AST, ale także:

```text
repository graph
agent graph
swarm graph
capability graph
authority graph
provenance graph
```

GUI staje się jednym z consumerów tego silnika.

### `SymulacjaKaskadySieciowej` — Simulation / Falsification Engine

Model domenowy pozostaje bez zmian. Wielokrotnego użytku wkładem są dyscyplina pakietu/interfejsu i metody:

```text
deterministic scenario run
Monte Carlo
Morris
Sobol
bifurcation / phase transition
stress envelope
```

Target: zdefiniować generyczny interfejs SimulationProvider, zachowując poszczególne modele jako pluginy domenowe.

Cyber-Lion powinien móc pytać:

```text
Co stanie się z organizacją, jeśli zmieni się ta polityka?
Co jeśli jedna klasa agentów zawiedzie?
Co jeśli opóźnienie evidence podwoi się?
Co jeśli authority zostanie nadmiernie oddelegowane?
Co jeśli rynek zmieni się przed dostarczeniem software?
```

### `hipotezy_nadawcze_LLM` — Epistemic Hypothesis Lab

Repozytorium pozostaje celowo małe i rygorystyczne.

Targetowa struktura pojedynczej hipotezy:

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

Jego output zasila R&D i symulację. Nigdy nie może bezpośrednio stać się polityką produkcyjną.

### `writeups` — R&D / Enterprise Research Memory

`writeups` staje się formalnym organem R&D i archiwum evidence.

Zawiera:

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

Ścieżka promocji do produkcji jest jawnie bramkowana; zobacz `RND_OPERATING_MODEL.md`.

---

## 6. Agent Foundry

Platforma tworzy agentów z jawnych specyfikacji zamiast ad hoc promptów.

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

Agent może używać LLM, kodu deterministycznego, reguł, symulacji lub polityki hybrydowej. Tożsamość agenta jest niezależna od providera modelu.

Zmiana GPT/model/backend nie tworzy automatycznie nowej roli organizacyjnej; zmiana mission, authority lub contract może ją utworzyć.

---

## 7. Dynamiczne formowanie roju

Misja jest dekomponowana do wymaganych capabilities. Swarm Planner wybiera najmniejszy wystarczający zbiór definicji agentów, który je pokrywa w granicach ryzyka i authority.

Koncepcyjnie:

```text
mission capabilities = {research, architecture, code, security, validation}

available agents:
A = {research, hypothesis}
B = {architecture, code}
C = {security, validation}
D = {code}

minimal sufficient swarm = {A, B, C}
```

Planner powinien optymalizować nie tylko liczbę agentów, ale także:

```text
coverage
observability
coordination cost
authority exposure
model/provider diversity
latency
reliability
```

Rój jest tymczasowy, chyba że powtarzające się wzorce misji uzasadniają cache'owanie jego topologii.

---

## 8. Topologia authority

Authority jest monotoniczne w dół:

```text
EnterprisePolicy
  ⊇ DomainPolicy
    ⊇ SwarmAuthority
      ⊇ AgentAuthority
        ⊇ ActionAuthority
```

Dziecko może zawęzić authority. Nie może go rozszerzyć.

Dynamiczne tworzenie agentów przebiega zatem według:

```text
parent authority ceiling
∩ mission authority
∩ agent template ceiling
∩ current observability allowance
= effective authority
```

---

## 9. Autonomia warunkowana obserwowalnością

Autonomia jest zmienną kontrolowaną:

```text
Autonomy ∝
(Provenance × Observability × Controllability × EvidenceQuality)
/
(Impact × Uncertainty × BoundaryExposure)
```

Reguła operacyjna:

```text
required observability missing
→ authority degrade
→ read-only / pause / freeze / revoke
```

Dla roju o wysokich konsekwencjach utrata jednej krytycznej relacji trace nie powinna jedynie tworzyć alertu; powinna zmniejszać osiągalny stan wykonawczy.

---

## 10. Rola człowieka

Ludzie nie znikają z tego przedsiębiorstwa. Ich rola zmienia się z ręcznego przenoszenia każdego zadania na definiowanie/zatwierdzanie:

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

Sama interakcja człowieka jest modelowana jako zdarzenia i decyzje, tak aby pozostawała obserwowalna i rekonstruowalna.

---

## 11. Definition of done dla ewolucji przedsiębiorstwa AI-Native

Nowa capability nie jest ukończona w chwili powstania kodu. Jest ukończona, gdy:

```text
1. capability ma identity i version
2. AgentSpec może ją konsumować
3. wymagane authority jest jawne
4. wymagane observations są jawne
5. execution path jest ograniczony
6. emitowane są events/provenance
7. GlitchLab potrafi sprawdzić jej deltę
8. testy zawierają przypadki negatywne/adversarialne
9. istnieje rollback/revocation
10. status R&D jest powiązany z evidence
11. README/registry/roadmap są zsynchronizowane
12. reguły kompozycji roju rozumieją capability
```
