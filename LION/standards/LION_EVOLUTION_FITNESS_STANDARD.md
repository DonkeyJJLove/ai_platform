# LION Dynamic Evolution Fitness Standard — R1

Status: `CANDIDATE / SOURCE_BOUND`. Authority effect: `NONE`. Execution effect: `NONE`.

## Po co ten standard istnieje

LION ma już Evolution Spine, Formalization Kernel, ArchitectureCompiler, Mission Control, Semantic Cloud, ścieżki authority/effect, federacyjne owner maps oraz materialnych workerów. Brakującym elementem nie jest więc kolejny scheduler ani kolejny diagram architektury, lecz **deterministyczna reguła wyboru następnego przyrostu**.

Standard R1 odpowiada na pytanie: z kilku poprawnie opisanych kandydatów ewolucyjnych który powinien wejść na pojedynczą ścieżkę krytyczną teraz?

Odpowiedź nie może wynikać wyłącznie z priorytetu tekstowego, kolejności powstania pomysłu, wielkości modelu ani liczby repozytoriów. Kandydat ma zwiększać funkcjonalność systemu, a szczególnie zdolność LION do tworzenia następnych rozwiązań, przy możliwie małym rozszerzeniu authority, powierzchni zmiany, długu currentness i blast radius.

## Miejsce w istniejącej architekturze

R1 nie dodaje nowego `FLOW-11`. Jest projekcją decyzyjną wewnątrz istniejącego ownera roadmap/evolution i działa **przed** kompilacją wybranego `CandidateDesign` przez `ArchitectureCompiler`.

```text
CURRENT SOURCE / OBSERVATIONS
        ↓
Gap / currentness / dependency state
        ↓
bounded candidate set
        ↓
DYNAMIC EVOLUTION FITNESS
        ↓
one selected critical-path candidate
        ↓
existing ArchitectureCompiler
        ↓
EvolutionDelta
        ↓
AFM / RequiredFormalizationSet
        ↓
existing governed admission / mission path
```

To zachowuje istniejące `FLOW-01..FLOW-10`. Fitness nie nadaje authority, nie uruchamia misji, nie tworzy assignmentu i nie wykonuje repozytoryjnego lub materialnego efektu.

## Dwa poziomy selekcji

Najpierw działają bramki twarde. Kandydat odpada niezależnie od wyniku punktowego, jeżeli źródło nie jest aktualne, nie wiadomo kto jest ownerem, zależności nie są domknięte, pozostaje nierozliczony efekt, występuje konkurencyjny writer/kolizja, scope nie jest ograniczony, brakuje evidence binding albo projekt rozszerza authority w sposób niezgodny z parent scope.

Dopiero w zbiorze kandydatów dopuszczalnych analizowany jest wektor fitness. Standard zachowuje wiele wymiarów; nie redukuje architektury do jednego KPI. Najpierw usuwane są kandydaty Pareto-zdominowane. Skalarna funkcja utility służy dopiero do deterministycznego wyboru jednego elementu z pozostałego frontu.

## Co LION nagradza

Najwyższą wagę ma **generativity gain**: przyrost, który pozwala temu samemu mechanizmowi zbudować kolejne rodziny artefaktów lub aplikacji, jest cenniejszy niż jednorazowa naprawa o podobnym koszcie. Wysoko oceniane są również capability gain i integration closure — czyli zamknięcie rzeczywistego obiegu od intencji i kontekstu przez providerów, materializację, niezależne sprawdzenie aż do readbacku.

Dalej liczą się functional value, federation leverage, reuse leverage, verification strength, recovery strength oraz knowledge feedback. Federation leverage nie oznacza liczby dotkniętych repozytoriów: punktowany jest wyłącznie rzeczywisty producer→consumer edge. Reuse oznacza pierwszeństwo istniejącego ownera, kontraktu, Bean lub materializera przed tworzeniem nowej infrastruktury.

## Co LION karze

Najsilniejszą karą jest authority risk. Samobudująca się aplikacja nie może optymalizować zdolności przez przejmowanie własnego trust root. Blast radius, currentness debt i change surface zmniejszają fitness następnego kroku. Implementation i operational cost są kosztami niższego rzędu: droższy przyrost może wygrać, jeśli zamyka ogólny mechanizm generatywny, ale nie może wygrać przez pominięcie bezpieczeństwa, provenance albo recovery.

## Dynamika bez arbitralności

Dynamiczny charakter standardu polega na `pressure`. Bieżący system może źródłowo wykazać, że wąskim gardłem jest np. currentness, recovery, integracja SaaS+LOCAL albo generatywność fabryki. Taka obserwacja podnosi wagę **już istniejącego** wymiaru w zakresie 0–1000.

Pressure musi mieć `evidence_ref`. Nie może dodać nowego wymiaru, zmienić bramki FAIL na PASS ani wyprowadzić authority z wyniku modelu. Identyczne wejście, pressure i policy dają identyczny digest selekcji.

## Kierunek po R1

Pierwszy konsument istnieje już źródłowo: `ArchitectureCompiler.compile_selected(...)` przyjmuje dokładnie związany zestaw `CandidateDesign` i odpowiadające mu wektory fitness, wybiera jeden kandydat i przekazuje wyłącznie jego do istniejącego `compile(...)`. Następną luką nie jest więc integracja z kompilatorem, lecz zbudowanie source-bound adapterów pressure z bieżących Gap/currentness/effect/collision observations oraz podłączenie tego wyboru do autorowania Mission Program.

Najwyższy oczekiwany fitness w obecnym frontierze ma nie „więcej dokumentacji” ani „większa flota”, lecz **pierwszy prawdziwy zamknięty obieg SaaS + LOCAL + material worker + niezależny verifier, który tworzy użyteczny artefakt w ai_platform, a następnie ten sam mechanizm obsługuje drugą rodzinę produktu bez osobnego hard-coded workflow**. To jest przejście od systemu budującego siebie do kontrolowanej fabryki aplikacji.

## Niezmienniki

```text
FITNESS_SELECTION != AUTHORITY
FITNESS_SELECTION != SCHEDULING
DYNAMIC_PRESSURE != HARD_GATE_BYPASS
MODEL_OUTPUT != EVIDENCE_ROOT
STRUCTURE MAY RECUR
AUTHORITY MUST NOT AMPLIFY
UNKNOWN EFFECT -> RECONCILE, NEVER BLIND RETRY
CRITICAL_PATH_WIP = 1  (R1)
```

Implementacja referencyjna: `cyber_lion/architecture_projection/evolution_fitness.py`.

Machine-readable standard: `LION/standards/LION_EVOLUTION_FITNESS_STANDARD.json`.
