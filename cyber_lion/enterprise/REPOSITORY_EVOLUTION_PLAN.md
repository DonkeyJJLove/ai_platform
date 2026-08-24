# Plan ewolucji repozytoriów

Ta roadmapa przypisuje każdemu repozytorium stabilną **rolę w przedsiębiorstwie**, zachowując jego niezależną ewolucję. Celem jest federacja przez kontrakty, a nie przepisanie całości do monorepo.

## 1. `ai_platform` — Enterprise Control Plane / Agent Foundry

### Zachować

- kontrakty identity/event/capability Cyber-Lion,
- Startup Evolution Agent,
- provider plane,
- rozdzielenie authority,
- archeologię repozytoriów i architekturę przedsiębiorstwa.

### Budować dalej

**Faza A — Agent Foundry**

- schematy `AgentSpec` / `AgentInstance`,
- Agent Registry,
- versioning/supersession,
- mission → capability resolution,
- jawne wymagania memory/observability/authority.

**Faza B — Swarm Control Plane**

- `SwarmSpec`, `MosaicCell`, `MosaicDelta`,
- deterministyczny swarm planner,
- kontrakty spawn/delegate/dissolve,
- observability quorum,
- reguły topologii risk-class.

**Faza C — Enterprise Graph**

- encje/capabilities/agenci/roje/evidence/policy/execution jako typowany graf,
- adaptery do Mosaic Structural Engine,
- path queries dla authority/provenance.

**Faza D — Policy / Gate Engine**

- wspólny interfejs PDP,
- receipts GateRequested/GateApplied,
- authority degradation warunkowane obserwowalnością,
- enterprise lanes GREEN/AMBER/RED.

### Unikać

- kopiowania implementacji providerów do `ai_platform`,
- traktowania providera modelu jako tożsamości agenta,
- centralnego runtime z nieograniczonymi credentials.

---

## 2. `glitchlab` — Enterprise Evolution Compiler

### Bieżące zasoby

- inżynieria Δ-first,
- AST↔Mosaic `Φ/Ψ`,
- I1–I4,
- living thresholds α/β/ζ,
- SAST-Bridge,
- BUS/EGDB/HUD,
- kierunek FixCandidate/self-healing.

### Budować dalej

**Faza A — ustabilizować bieżący code compiler**

- dokończyć higienę pakietu,
- udowodnić dokumentowane entrypoints,
- domknąć historyczny Ruff debt przez ratchet,
- egzekwować bezpieczne execution wygenerowanego kodu przez izolowanego providera.

**Faza B — adaptery zewnętrznych delt**

Dodać typowane adaptery dla:

```text
AgentSpec
SwarmSpec
CapabilityDescriptor
Policy
JSON Schema
RepositoryManifest
MemoryContract
```

Output: jeden znormalizowany `EnterpriseDeltaReport`.

**Faza C — enterprise invariants**

Zaimplementować E1–E10 z `GENERATION_EVOLUTION_PROTOCOL.md` obok code-level I1–I4.

**Faza D — most Cyber-Lion**

- konsumować Cyber-Lion change proposal,
- emitować zdarzenia analityczne kompatybilne z EventEnvelope,
- wiązać findings z grafem entity/capability/agent/swarm,
- wystawiać ACCEPT/REVIEW/BLOCK z evidence.

### Unikać

- przekształcania samego GlitchLab w authority engine,
- cichego auto-fix consequential changes,
- rozszerzania jednego lokalnego registry do globalnego przez semantic overloading.

---

## 3. `chunk-chunk` — Process Semantics / HMK-9D Microcode

### Bieżące zasoby

- abstrakcja decyzyjna `S,Σ,A,F,g,H,a*`,
- przejścia `chunk–chunk→`,
- wektor 9D `[T,S,R,E,I,F,A,P,D]`,
- mosty i operatory progów,
- koncepcja energii lokalnej/globalnej,
- relacja z GlitchLab Δ/EGDB.

### Budować dalej

**Faza A — canonical schema**

- oddzielić normative schema od przykładów promptów,
- wersjonować `ProcessVector9D`, `Bridge`, `Transition`, `MicrocodeProgram`,
- zdefiniować units/ranges i obsługę UNKNOWN.

**Faza B — deterministyczny VM core**

- zaimplementować parser/executor microcode semantycznego modyfikującego wyłącznie process state,
- bez direct tool authority,
- deterministyczny event output.

**Faza C — integracja AgentSpec**

- pozwolić AgentSpec odwoływać się do process profile/bridges,
- emitować adnotacje 9D na zdarzeniach Cyber-Lion,
- mapować `THRESHOLD_TRANSITION` na candidate `GateRequested`, nie `GateApplied`.

**Faza D — geometria procesu roju**

- agregować lokalne transition vectors do diagnostyki MosaicCell/Swarm,
- metryki coupling i coordination-cost,
- adaptacyjną granularność chunków.

### Unikać

- przedstawiania `_neuro`/semantic bridge scores jako pomiarów fizycznych,
- pozwalania bridge operators tworzyć authority,
- przechowywania lokalnych virtual environments/runtime state w source.

---

## 4. `HA2D` — Context, Memory and Human–AI Adaptation Lab

### Bieżące zasoby

- PCE persistent context,
- MCV temporary context,
- konceptualne przejścia SNAP/THOUGHT/MORPH,
- rekordy CMM UUID/time/hash,
- heurystyki semantic revision SMA/_neuro,
- koncepcje HUD.

### Budować dalej

**Faza A — taksonomia stanów**

Sformalizować:

```text
WorkingContext
MemoryCandidate
CommittedMemory
SupersededMemory
```

z rygorystycznym rozdzieleniem.

**Faza B — kontrakt CMM v2**

Dodać:

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

**Faza C — adapter Memory Service**

- wystawić read/write capabilities przez Cyber-Lion Capability Registry,
- `MemoryCommitted` dopiero po MAND policy,
- zaimplementować testy replay/integrity.

**Faza D — Human–AI HUD**

- wyświetlać context provenance,
- pokazywać memory candidates vs committed state,
- eksponować confidence/uncertainty i granicę authority.

### Unikać

- self-declared semantic coherence jako dowodu prawdy,
- automatycznej persistent memory z outputu modelu,
- traktowania `_neuro` jako klinicznego EEG/fizjologii.

---

## 5. `swarm` — Distributed Execution Mesh

### Bieżące zasoby

- topologia workloadów Kubernetes,
- telemetria UDP/MQTT,
- APIs/PostgreSQL,
- Istio,
- Prometheus/Grafana/Jaeger,
- RBAC/NetworkPolicy,
- przykład AI service.

### Budować dalej

**Faza A — bezpieczeństwo/higiena labu**

- zintegrować remediation command-injection,
- kanoniczny README,
- przegląd least-authority RBAC,
- secrets przez Kubernetes Secret management zamiast przykładów ze statycznymi wartościami.

**Faza B — generyczna abstrakcja workloadu**

Zastąpić drone-specific assumptions orkiestracji rolami wielokrotnego użytku:

```text
ExecutionNode
AgentWorkload
TelemetryCollector
CapabilityBrokerClient
LocalPEP
```

Zachować symulację drona jako przykładowy workload.

**Faza C — runtime adapter Cyber-Lion**

- konsumować AgentSpec/SwarmSpec,
- wiązać tożsamość agenta z pod/workload identity,
- mapować capability lease → runtime resources,
- emitować action/process/effect receipts.

**Faza D — runtime warunkowany obserwowalnością**

- wymagane trace/health checks,
- stany DEGRADED/RESTRICTED/FROZEN,
- redukcja authority przy utracie evidence,
- capability kill/revoke.

### Unikać

- identity wyłącznie przez IP/PID,
- dziedziczenia szerokich uprawnień Kubernetes od koordynatora,
- nazywania samej konfiguracji Kubernetes/Istio kompletnym Agent Control Mesh.

---

## 6. `sbom` — Provenance, Identity and Composition Intelligence

### Bieżące zasoby

- AID,
- stabilny event envelope,
- `sbom → scan → delta → gate`,
- lab Jenkins/Elastic/Splunk,
- logika supply-chain state/delta.

### Budować dalej

**Faza A — zachować specjalizację SBOM**

- wzmocnić ścieżkę CycloneDX/signing/attestation,
- dependency i license/security metrics,
- niezawodna propagacja AID.

**Faza B — Cyber-Lion identity adapter v2**

- dual emit EntityIdentity/EventEnvelope,
- bezstratna kompatybilność legacy AID,
- jawna semantyka GateApplied.

**Faza C — badania Relation BOM / Decision BOM**

Prototypować rekordy composition dla:

```text
agent
model
tool
policy
swarm
execution artifact
```

Nie nazywać ich standaryzowanymi formatami SBOM, jeśli nie są odwzorowane na rzeczywisty standard.

**Faza D — provider grafu provenance**

- wystawić zapytania composition/delta do Enterprise Graph,
- powiązać build → dependency → scan → gate → execution receipt.

### Unikać

- zamieniania każdego rekordu telemetrii w pełny payload storage,
- mylenia AID owner mandate z runtime permission,
- redefiniowania istniejących standardów SBOM własną terminologią.

---

## 7. `mosaic_lab_pro.py` — Structural Intelligence Engine

### Bieżące zasoby

- graf AST,
- geometria S/H,
- pathing A*,
- parametr abstrakcji `λ`,
- kontrakcja supergrafu,
- stabilne inwarianty wizualizacji.

### Budować dalej

**Faza A — oddzielić engine od GUI**

Wyodrębnić reusable package:

```text
mosaic_core.graph
mosaic_core.topology
mosaic_core.abstraction
mosaic_core.path
mosaic_core.validation
```

Zachować GUI jako consumera.

**Faza B — generyczne adaptery grafów**

Obsłużyć:

```text
ASTGraph
RepositoryGraph
AgentGraph
SwarmGraph
CapabilityGraph
AuthorityGraph
ProvenanceGraph
```

**Faza C — wieloskalowa projekcja przedsiębiorstwa**

Użyć `λ` do przechodzenia:

```text
single action
→ agent
→ MosaicCell
→ swarm
→ repository
→ enterprise
```

**Faza D — provider anomalii strukturalnych**

- nieoczekiwane krawędzie cross-domain,
- skróty ścieżek authority,
- wysokie coupling,
- drift topologii,
- single points of failure.

### Unikać

- interpretowania samej geometrii jako prawdy,
- trwałego sprzęgania core algorithms z Tkinter/Matplotlib,
- używania similarity wizualnego jako decyzji authorization/security.

---

## 8. `SymulacjaKaskadySieciowej` — Simulation/Falsification Engine

### Bieżące zasoby

- packaged model interface,
- symulacja deterministyczna,
- Monte Carlo,
- Morris,
- Sobol,
- analiza bifurcation/phase,
- jawne rozróżnienie modelu od prognozy.

### Budować dalej

**Faza A — zachować obecny model Iran jako plugin domenowy**

Nie uogólniać jego równań przez ich usunięcie.

**Faza B — wspólny protokół SimulationProvider**

```text
ModelDescriptor
ScenarioSpec
ParameterDistribution
SimulationRequest
SimulationResult
SensitivityResult
ModelRiskStatement
```

**Faza C — modele przedsiębiorstwa**

Dodać odrębne pluginy dla:

- product/market timing,
- kaskad awarii agentów/rojów,
- propagacji authority,
- awarii obserwowalności,
- tradeoff software delivery/risk.

**Faza D — adapter Cyber-Lion**

Zdarzenia SimulationRequested/Completed z provenance seed/config/model-version.

### Unikać

- traktowania częstości z symulacji jako empirycznego prawdopodobieństwa incydentu,
- modyfikowania modelu domain-specific tak, aby pasował do każdego przyszłego zastosowania,
- ukrywania assumptions za jednym synthetic score.

---

## 9. `hipotezy_nadawcze_LLM` — Epistemic Hypothesis Lab

### Bieżące zasoby

- wąskie falsyfikowalne hipotezy,
- jawna teza text→token,
- warunki falsyfikacji,
- struktura evidence/argument.

### Budować dalej

**Faza A — schema HypothesisSpec**

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

**Faza B — experiment registry**

- przypadki testowe,
- metadane model/version,
- hashes wyników,
- wyniki negatywne.

**Faza C — adapter R&D**

- eksport do `writeups` ResearchRecord,
- linkowanie zamiast duplikowania hipotezy kanonicznej.

### Unikać

- wartości prawdopodobieństwa bez jawnego statusu/kalibracji,
- traktowania wyjaśnienia własnej hipotezy przez model jako walidacji,
- promowania analogii do rangi faktu naukowego.

---

## 10. `writeups` — R&D / Enterprise Research Memory

### Bieżące zasoby

- AI Security / SMB/PDB,
- projekty runtime/reference monitor,
- multi-agent mesh,
- LOCI,
- badania Human–AI,
- probabilistic studies,
- OSINT,
- publikacje i materiały reprodukowalności.

### Budować dalej

**Faza A — taksonomia R&D**

Dodać machine-readable/lightweight index dla:

```text
ResearchRecord
ArchitectureProposal
Experiment
Dataset/SourceSet
Finding
EngineeringCandidate
Publication
```

**Faza B — metadane epistemiczne**

Tagować podstawowe outputy statusem i supersession links.

**Faza C — adapter R&D Cyber-Lion**

- ingest metadanych do Evidence/Hypothesis registry,
- zachowanie document SHA/source links,
- generowanie SpecCandidate wyłącznie przez jawny promotion.

**Faza D — workflow rojów badawczych**

- source/evidence agent,
- hypothesis agent,
- falsification agent,
- simulation agent,
- methodology/security reviewer.

### Unikać

- traktowania całego prose jako równoważnego evidence,
- utraty wyników negatywnych/supersedowanych hipotez,
- pozwalania tekstowi writeup bezpośrednio konfigurować produkcję.

---

## 11. Kolejność implementacji cross-repository

### Wave 1 — kontrakty i stan

```text
ai_platform AgentSpec/SwarmSpec
→ chunk-chunk process schemas
→ HA2D memory contract
→ provider manifests in all repos
```

### Wave 2 — walidacja strukturalna

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

### Wave 5 — pełna zamknięta pętla

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

## 12. Wspólne wymagania repozytoriów

Każde repozytorium powinno docelowo zawierać:

```text
README.md
AI_NATIVE_ROADMAP.md
cyber-lion.manifest.json (lub równoważny wersjonowany manifest)
PROCESS_GUARD.md
security / execution scope
CI regression gate
```

Każdy wykonywalny provider powinien dodatkowo deklarować:

```text
capabilities
input/output schemas
side effects
required authority
required gates
observability events
rollback/revoke behavior
```
