# Model operacyjny R&D

## 1. R&D jest organem przedsiębiorstwa, a nie katalogiem dokumentów

W Cyber-Lion `writeups` jest długoterminowym **korpusem R&D / evidence** przedsiębiorstwa AI-Native. Przechowuje pytania badawcze, raporty falsyfikacyjne, hipotezy architektoniczne, badania bezpieczeństwa, OSINT, symulacje, eksperymenty i publikacje.

Jego rolą nie jest bezpośrednie konfigurowanie systemów produkcyjnych. Jego rolą jest tworzenie **candidate knowledge**, która może zostać wypromowana do wykonywalnych specyfikacji dopiero po jawnej walidacji.

```text
ŚWIAT / INCYDENT / RYNEK / EKSPERYMENT
                ↓
            OBSERWACJA R&D
                ↓
             HIPOTEZA
                ↓
       FALSYFIKACJA / TEST
                ↓
       REPRODUKOWALNE EVIDENCE
                ↓
         REGUŁA INŻYNIERYJNA
                ↓
          SPEC CANDIDATE
                ↓
       SHADOW / SIMULATION
                ↓
             GATE
                ↓
       NORMATIVE RUNTIME SPEC
```

Inwariant podstawowy:

```text
RESEARCH CLAIM != RUNTIME AUTHORITY
```

---

## 2. Obiekt badawczy

Każdy ważny wynik badawczy powinien docelowo dać się reprezentować jako:

```text
ResearchRecord = {
  research_id,
  title,
  question,
  hypothesis,
  scope,
  sources,
  evidence_for,
  evidence_against,
  methods,
  simulations,
  assumptions,
  falsifiers,
  limitations,
  epistemic_status,
  confidence,
  artifacts,
  related_findings,
  candidate_rules,
  supersedes,
  superseded_by
}
```

`writeups` pozostaje human-readable corpus; przyszły machine-readable index wystawi te pola platformie.

---

## 3. Stany epistemiczne

Używaj ścisłej drabiny:

```text
QUESTION
→ HYPOTHESIS
→ OBSERVED
→ REPRODUCED
→ ENGINEERING_CANDIDATE
→ SHADOW_VALIDATED
→ NORMATIVE
→ SUPERSEDED
```

Drabina ta jest czymś innym niż confidence. Nawet wysoce prawdopodobna hipoteza pozostaje hipotezą, dopóki nie posiada wymaganego evidence i ścieżki walidacji.

Dla materiału ilościowego zachowuj istniejące rozróżnienie:

```text
OBSERVED
DERIVED
CALIBRATED
ASSUMED
HYPOTHESIS
SPECULATION
STRESS_PARAMETER
```

Konwergencja Monte Carlo zmniejsza sampling noise **wewnątrz modelu**. Nie promuje automatycznie calibrated assumption do statusu zaobserwowanej częstotliwości świata rzeczywistego.

---

## 4. Research Cells

Praca R&D jest wykonywana przez tymczasowe mozaiki badawcze, a nie jednego monolitycznego research agenta.

Przykład:

```text
R&D Cell
├── Source / Evidence Agent
├── Hypothesis Agent
├── Falsification Agent
├── Simulation Agent
├── Security/Methodology Auditor
└── Human Research Owner
```

Dla exploratory work o niższym ryzyku mniej ról może zostać połączonych. Dla high-impact policy albo security research generowanie hipotezy i falsyfikacja **POWINNY** być rozdzielone pomiędzy niezależnych agentów/providerów.

---

## 5. Łańcuch zdarzeń R&D

```text
ResearchQuestionCreated
→ ObservationAttached
→ HypothesisGenerated
→ EvidenceAttached
→ HypothesisUpdated
→ SimulationRequested
→ SimulationCompleted
→ FalsificationResult
→ EngineeringRuleProposed
→ SpecCandidateCreated
→ ShadowValidationCompleted
→ GateApplied
→ SpecPromoted
```

Wszystkie kroki powinny współdzielić correlation/provenance IDs przez Cyber-Lion `EventEnvelope`.

---

## 6. Klasy promocji

### Klasa R0 — narracyjna / exploratory

Przykłady:

- eseje,
- analogie,
- szkice koncepcyjne,
- spekulatywne architektury.

Mogą informować generowanie hipotez. Nie mogą bezpośrednio stać się kontrolą runtime.

### Klasa R1 — formalna hipoteza

Musi zawierać:

- jawne twierdzenie,
- falsifiers,
- alternatywne wyjaśnienia,
- status evidence.

### Klasa R2 — zreprodukowany eksperyment / analiza

Musi zawierać:

- reprodukowalne wejścia albo czytelne odwołania do źródeł,
- metodę,
- outputy,
- ograniczenia,
- wyniki negatywne tam, gdzie są istotne.

### Klasa R3 — engineering candidate

Wynik badawczy jest tłumaczony do candidate invariant, policy, schema, algorithm albo test.

Wymaga:

- jawnego mapowania evidence → rule,
- failure modes,
- rollbacku,
- proponowanych metryk.

### Klasa R4 — shadow validated

Candidate działa bez authority nad rzeczywistymi konsekwencjami i jest porównywany z istniejącym zachowaniem.

### Klasa R5 — normative

Może wpływać na production execution po niezależnym gate/approval i wersjonowanym release.

---

## 7. Promocja badań bezpieczeństwa

Security findings używają najsilniejszej ścieżki promocji:

```text
finding
→ reproduction
→ exploitability/impact classification
→ missing invariant
→ generalized rule
→ regression family
→ GlitchLab/SAST integration
→ shadow validation
→ policy/enforcement candidate
→ gate
→ runtime control
```

Pojedynczy payload lub patch specyficzny dla CVE nie jest produktem końcowym. Preferowany rezultat to uogólniony inwariant na poziomie klasy problemu.

---

## 8. Kontrakt writeups ↔ ai_platform

Docelowy przyszły interfejs:

```text
writeups ResearchRecord
        ↓
R&D index adapter
        ↓
Cyber-Lion Evidence / Hypothesis registry
        ↓
engineering candidate
        ↓
Agent Foundry / Policy / Simulation / GlitchLab
```

Adapter musi zachować oryginalną ścieżkę dokumentu, commit SHA, cytowane źródła i status epistemiczny.

---

## 9. Repozytorium hipotez ↔ R&D

`hipotezy_nadawcze_LLM` pozostaje dedykowanym małym laboratorium dla wąskich hipotez model/channel.

Jego rekordy powinny być linkowalne do `writeups` przez ID, a nie kopiowane i po cichu zmieniane.

Target:

```text
HypothesisSpec
→ ExperimentSpec
→ Result
→ ResearchRecord
```

---

## 10. Rola symulacji

Symulacja jest wzmacniaczem falsyfikacji, a nie zamiennikiem evidence.

Żądanie symulacji zawiera:

```text
model_id
model_version
scenario
parameter distribution
seed strategy
assumptions
requested metrics
stress conditions
```

Output zawiera:

```text
result
convergence diagnostics
sensitivity
failure region
model-risk notes
```

System **MUSI** zachować rozróżnienie:

```text
SIMULATED
!=
OBSERVED
```

---

## 11. Pamięć badawcza

Committed R&D memory powinna przechowywać:

```text
co było wiadomo
kiedy było wiadomo
source/evidence
które hipotezy odrzucono
jakich assumptions użyto
która wersja reguły została wyprowadzona
co później ją supersedowało
```

Zapobiega to wielokrotnemu odkrywaniu przez organizację tego samego problemu albo cichemu przywracaniu unieważnionych assumptions.

---

## 12. Obserwowalność R&D

Mierz więcej niż liczbę publikacji.

Użyteczne metryki:

```text
time question → falsifiable hypothesis
time hypothesis → experiment
reproduction rate
negative-result retention
research → engineering-candidate conversion
candidate → normative conversion
supersession frequency
research lineage completeness
model-risk disclosure completeness
```

Celem jest learning velocity z integralnością epistemiczną.

---

## 13. Rola człowieka w R&D

Ludzie pozostają ownerami:

- strategicznych pytań badawczych,
- interpretacji niejednoznacznego evidence świata rzeczywistego,
- zakresu etycznego/prawnego,
- high-impact promotion decisions,
- decyzji, czy użyteczna reguła inżynieryjna jest zgodna z celami przedsiębiorstwa.

Agenci przyspieszają zbieranie, formalizację, symulację, falsyfikację i syntezę.

---

## 14. Definition of done dla wypromowanego wyniku badawczego

Wynik badawczy kwalifikuje się do użycia normatywnego tylko wtedy, gdy:

```text
1. original evidence is reconstructable
2. epistemic state is explicit
3. falsifiers were defined
4. contrary evidence is retained
5. engineering rule is separately specified
6. tests/regressions exist
7. model/simulation risk is disclosed
8. shadow behavior was observed where applicable
9. authority/security impact is reviewed
10. versioned promotion event exists
11. rollback/supersession path exists
```
