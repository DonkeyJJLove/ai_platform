# CYBER-LION — rejestr statusu naukowego i implementacyjnego

Cyber-Lion łączy wykonywalne oprogramowanie, specyfikacje architektury, heurystyki inżynieryjne i hipotezy badawcze. Kategorie te nie mogą zlewać się ze sobą.

## Słownik statusów

```text
FACT / OBSERVED
DERIVED
MODEL
HYPOTHESIS
EXPERIMENTAL
SPECIFICATION
IMPLEMENTED
MODEL_RESULT
NEGATIVE_RESULT
SUPERSEDED
UNKNOWN
```

## Rejestr konstruktów

| Konstrukt | Bieżący status | Granica evidence / implementacji |
|---|---|---|
| INF / SEM / MAND | `SPECIFICATION` | istniejąca klasyfikacja architektoniczna QV9D/ai_platform |
| Mapowanie repozytoriów QV9D | `SPECIFICATION + EXPERIMENTAL` | istniejąca statyczna mosaic i eksperymentalne porównania promptów; nie jest globalnym runtime registry |
| Wektor stanu HMK-9D 9D | `MODEL + EXPERIMENTAL` | jawny YAML/specyfikacja; wagi mostów są autorskimi parametrami modelu, a nie uniwersalnymi stałymi empirycznymi |
| `chunk–chunk→` | `MODEL` | jawna reprezentacja przejścia; ogólny runtime router nie został jeszcze ustanowiony |
| Analiza GlitchLab Δ / AST | `IMPLEMENTED` | istnieją wykonywalne moduły Python |
| GlitchLab I1–I4 / αβZ | `MIXED: IMPLEMENTED/SPECIFICATION` | część mechanizmów/kodu oraz dokumentacja architektoniczna; poszczególne ścieżki enforcement wymagają weryfikacji na poziomie testów |
| Lokalny registry GlitchLab | `IMPLEMENTED` | callable registry; **nie** jest globalnym capability registry |
| Mosaic AST→graph / abstrakcja λ | `IMPLEMENTED PROTOTYPE` | wykonywalna aplikacja monolityczna |
| AID identity-over-time | `IMPLEMENTED CONTRACT/LAB` | jawny kontrakt AID i envelope SBOM/scan/delta/gate |
| Uogólniona Cyber-Lion Entity Identity | `TARGET SPECIFICATION` | jeszcze niezaimplementowana |
| Rozproszone execution Swarm | `IMPLEMENTED LAB` | artefakty UDP/MQTT/APIs/Kubernetes/Istio/RBAC/monitoring |
| Typowany event bus Cyber-Lion | `TARGET SPECIFICATION` | adaptery/runtime jeszcze niezaimplementowane |
| HA2D PCE/MCV/SNAP/MORPH | `SPECIFICATION / EXPERIMENTAL` | głównie dokumentacyjny model cognitive-state |
| `_neuro_` / SMA | `EXPERIMENTAL PROCESS MODEL` | bez empirycznego oprzyrządowania nie może być przedstawiany jako pomiar kliniczny/fizjologiczny |
| Teza H-LLM text→token | `HYPOTHESIS` | istnieją jawne kryteria falsyfikacji; wartość prawdopodobieństwa sama w sobie nie jest dowodem empirycznym |
| Model Cascade SD | `IMPLEMENTED MODEL` | wykonywalny pakiet i interfejs modelu |
| Wyniki Monte Carlo/Morris/Sobol | `MODEL_RESULT` | warunkowe względem modelu, parametryzacji i seed; nie są zaobserwowanymi faktami geopolitycznymi |
| Korpus writeups | `OBSERVED ARTIFACT CORPUS` | dokumenty istnieją; twierdzenia w ich wnętrzu zachowują własny status epistemiczny |
| Security Model Boundary / PDB | `AUTHORED SECURITY MODEL` | research/writeups; należy traktować jako konstrukt modelowy/architektoniczny, chyba że konkretne twierdzenie empiryczne ma niezależne źródło |
| Cyber-Lion Control Plane | `TARGET SPECIFICATION` | bieżący ai_platform nie jest jeszcze runtime opisanym przez ten termin |

## Inwarianty naukowe

### S1 — Symulacja jest warunkowa

```text
large N
⇒ lower sampling noise inside model
NOT
⇒ empirical truth of model
```

### S2 — Reprezentacja nie jest rzeczywistością

```text
graph / QV9D / λ / HMK-9D coordinate
= representation
!= direct proof of hidden real-world state
```

### S3 — Spójność semantyczna nie jest evidence

Spójne wyjaśnienie, relacja embeddingowa lub wygenerowana hipoteza nie walidują się same.

### S4 — Output badawczy ma zero implicit authority

```text
HYPOTHESIS / MODEL_RESULT / WRITEUP
cannot directly authorize ACTION
```

### S5 — Rekord falsyfikacji jest obiektem pierwszej klasy

Wyniki negatywne i supersedowane modele pozostają powiązane przez provenance zamiast znikać z historii epistemicznej.

## Wymagane metadane przyszłych heurystyk

Każda nowa heurystyka Cyber-Lion powinna docelowo zawierać:

```yaml
heuristic_id:
status: HYPOTHESIS|EXPERIMENTAL|DERIVED
scope:
assumptions: []
metric:
evidence_for: []
evidence_against: []
known_counterexamples: []
falsification_tests: []
last_reviewed:
```

Heurystyka może wpływać na ranking/eksplorację przed formalizacją, ale nie może być jedyną bramką dla nieodwracalnego high-authority execution, chyba że odpowiednia polityka jawnie dopuszcza takie ryzyko.

## Reguła distillation

Gdy wielokrotnie zwalidowana własność może zostać wyrażona deterministycznie:

```text
heuristic/model interpretation
→ validator / schema / invariant / test / policy
```

Mechanizm deterministyczny staje się źródłem enforcement. Historyczna heurystyka pozostaje powiązana jako provenance, zamiast pozostawać wielokrotnie zgadywaną interpretacją LLM.
