# Startup Evolution Agent

Ograniczona agentowa pętla sterowania dla **startupu AI-Driven**.

Jej celem jest przekształcanie świeżego evidence rynkowego w najszybszy użyteczny eksperyment produktowy, tłumaczenie tego eksperymentu na najmniejszy audytowalny build software, autonomiczne wykonywanie wyłącznie ograniczonej pracy lokalnej, obserwacja wyniku i korekta modelu przedsięwzięcia.

```text
MarketObservation[]
→ MarketEvidenceBook
→ ProductHypothesis[]
→ VentureVector(t)
→ ranking
→ stage / bottleneck
→ Experiment
→ SoftwareBuildSpec
→ safe in-memory scaffold
→ StartupAuthorityGate
→ bounded local build OR approval-required external action
→ ExperimentOutcome
→ VentureVector(t+1)
→ EvolutionJournal / replay
```

## Moduły

- `models.py` — stan przedsięwzięcia, evidence, hipotezy i eksperymenty.
- `market_intelligence.py` — provenance, timestamps, deduplication, widoczność sprzeczności i freshness.
- `engine.py` — aktualizacje evidence, ranking hipotez, inferencja stage i wybór eksperymentu.
- `build_planner.py` — eksperyment → minimalna specyfikacja software → bezpieczny in-memory scaffold.
- `authority.py` — deterministyczna granica pomiędzy planowaniem i skutkiem zewnętrznym.
- `local_build.py` — ograniczona lokalna materializacja, compile/test i `BuildReceipt`.
- `journal.py` — append-only stan startupu i deterministyczny replay.
- `orchestrator.py` — `AIDrivenStartupAgent`, `CyclePlan` i korekta outcome.
- `demo.py` — uruchamialny przykład.

## Wektor przedsięwzięcia

```text
market_pull
evidence_strength
technical_feasibility
differentiation
distribution_access
delivery_velocity
security_readiness
unit_economics
learning_velocity
```

Wszystkie wymiary są normalizowane do `[0,1]`. Jest to reprezentacja/kalibracja inżynieryjna, a nie uniwersalne prawo empiryczne.

Istotny jest nie tylko bieżący wektor, ale jego trajektoria:

```text
V(t0) → ΔV → V(t1) → ΔV → V(t2)
```

## Evidence bieżącego rynku

Agent nie traktuje zapamiętanej wiedzy modelu jako aktualnego evidence rynkowego. `MarketObservation` wymaga źródła oraz observation/capture times uwzględniających strefę czasową. `MarketEvidenceBook` zapobiega wielokrotnemu liczeniu tego samego evidence i ujawnia sprzeczności zamiast po cichu je uśredniać.

Signals tracą wagę wraz z wiekiem i mogą być wykluczane po przekroczeniu skonfigurowanego market window.

```text
model memory != market observation
```

## Eksperymenty produktowe

Agent wybiera kolejny eksperyment na podstawie najsłabszych istotnych wymiarów i optymalizuje pod kątem information velocity, a nie liczby funkcji.

Eksperymenty obejmują:

- wywiady z klientami,
- problem smoke tests,
- lokalne prototypy,
- płatne pilotaże,
- testy cenowe,
- testy retencji.

Każdy eksperyment ma expected information gain, time-to-evidence, koszt, jawną success metric, stop condition i klasę authority.

## Tworzenie software

`SoftwareBuildPlanner` przekształca eksperyment w minimalny `SoftwareBuildSpec` zawierający komponenty, interfejsy, acceptance tests, security invariants i non-goals.

`SafeTemplateBuilder` renderuje tę specyfikację do **in-memory file map**. Sam nigdy nie zapisuje plików i odrzuca niebezpieczne ścieżki.

Dla zaufanych szablonów Cyber-Lion `BoundedLocalBuildRunner` może następnie zmaterializować scaffold w katalogu tymczasowym i uruchomić compile/tests.

Ważne:

> `BoundedLocalBuildRunner` **nie jest sandboxem bezpieczeństwa OS**. Używa path confinement, `shell=False`, timeout i zminimalizowanego environment, ale nie deklaruje izolacji kernela/sieci. Dowolny kod wygenerowany przez model wymaga silniejszego izolowanego execution providera.

## Authority

`analysis` i `local_prototype` mogą być dozwolone autonomicznie. `external_write`, `deploy` i `financial` wymagają jawnego applied gate event.

```text
model proposes
≠
organization authorizes
```

`AIDrivenStartupAgent.build_local(plan)` również odmawia wykonania planu, którego decyzja authority nie ma wartości `ALLOW`.

## Korekta outcome

Rzeczywisty wynik eksperymentu trafia do systemu jako `ExperimentOutcome`.

Warstwa korekty zmienia wyłącznie wymiary powiązane z eksperymentem. Udany prototyp nie poprawia automatycznie market pull, distribution ani security. Nieudany eksperyment rynkowy może obniżyć odpowiednie wymiary rynkowe. Wysokiej jakości wynik negatywny może mimo to zwiększyć `learning_velocity`.

```text
failed hypothesis
!=
failed learning process
```

## Replay

`EvolutionJournal` zapisuje cykle jako append-only JSONL. Replay waliduje ciągłość cykli, tożsamość startupu i `previous_vector == prior.vector` zamiast wymyślać brakujący stan.

## Uruchomienie

```bash
python -m cyber_lion.startup_agent.demo
python -m unittest discover -s cyber_lion/tests -p "test_*.py" -v
```

## Bieżąca granica

Agent potrafi obecnie:

1. przyjmować typowane obserwacje rynkowe,
2. rankingować konkurujące hipotezy,
3. wybierać kolejny eksperyment,
4. generować minimalny build spec i scaffold,
5. lokalnie compile/test zaufanych scaffoldów, gdy pozwala authority,
6. przyjmować outcome eksperymentów,
7. korygować wielowymiarowy stan przedsięwzięcia,
8. utrwalać i odtwarzać ścieżkę ewolucji.

Agent **nie potrafi jeszcze** autonomicznie przeglądać rynku, generować dowolnego kodu produkcyjnego, deployować, wydawać pieniędzy ani podpisywać zobowiązań handlowych. Te capabilities muszą pojawić się przez jawnych providerów i kontrakty authority Cyber-Lion.
