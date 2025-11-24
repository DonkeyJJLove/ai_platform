## D6 – Mapowanie woluminu /QV9D ↔ katalogi ai_platform

Celem rozdziału D6 jest zdefiniowanie jednoznacznego sposobu mapowania pomiędzy abstrakcyjnym woluminem 9D `/QV9D` a konkretną strukturą katalogową projektu `ai_platform`. Wolumin 9D pełni rolę „mózgu” i układu współrzędnych semantycznych (INF/SEM/MAND + mosty 9D + CL/HYB/Q + SPEC/STATE/METRICS/RITUAL/CI), natomiast katalogi `ai_platform` są fizycznym nośnikiem kodu, konfiguracji i danych. Mapowanie ma być odwracalne w sensie operacyjnym: dla dowolnego katalogu lub modułu w `ai_platform` można przypisać współrzędne w `/QV9D`, a dla dowolnej ścieżki w `/QV9D` można wskazać, gdzie znajduje się odpowiadający jej kod lub artefakty w `ai_platform`.

### 6.1. Rola /QV9D w architekturze ai_platform

Wolumin `/QV9D` nie jest osobnym repozytorium, ale logiczną nad-warstwą nad wszystkimi repo z mozaiki `LAT_GLX_PROJECT_MOSAIC` (m.in. `chunk-chunk`, `glitchlab`, `swarm`, `HA2D`, `writeups`, `hipotezy_nadawcze_LLM`) oraz nad główną strukturą `ai_platform`. Każdy istotny element platformy (moduł kodu, zestaw skryptów, pipeline CI, zestaw metryk, rytuał Human–AI) otrzymuje koordynaty:

`[warstwa]/[most]/[architektura]/[rodzaj_artefaktu]/[id_latarni]`

gdzie:

* warstwa ∈ {INF, SEM, MAND},
* most jest jednym z dziewięciu mostów 9D przypisanych do danej warstwy,
* architektura ∈ {CL, HYB, Q},
* rodzaj artefaktu ∈ {SPEC, STATE, METRICS, RITUAL, CI},
* `id_latarni` wiąże ten element z konkretną Latarnią (np. repo lub modułem) zdefiniowaną w `LAT_GLX_PROJECT_MOSAIC`.

W praktyce oznacza to, że `ai_platform` nie przechowuje tylko „kodu i dokumentacji”, ale każdy katalog i moduł jest osadzony w 9-wymiarowym rejestrze decyzji i ról. D6 definiuje zasady tego osadzania.

### 6.2. Poziom 1 – mapowanie repozytoriów na Latarnię projektową

Na pierwszym poziomie mapowania wszystkie repozytoria wchodzące w skład platformy są opisane w artefakcie:

`/QV9D/SEM/WIOSKA-MIASTO/HYB/STATE/LAT_GLX_PROJECT_MOSAIC.tree.json`

Każdy wpis zawiera co najmniej: nazwę repo, adres URL, rolę w ekosystemie, warstwę i most, domyślną architekturę i rodzaj artefaktu. Przykładowo:

* `chunk-chunk` jest przypisany do `SEM/WIOSKA-MIASTO` jako rdzeń protokołu kompresji 9D i kolejek loopów,
* `glitchlab` jest przypisany do `SEM/OSTRZE-CIERPLIWOSC` jako laboratorium anomalii i eksperymentów na AST+mozaice,
* `HA2D` trafia do `MAND/HUMAN-AI‡` jako brama interakcji człowiek–agent.

Repozytorium `ai_platform` samo w sobie może zostać wpisane jako osobna Latarnia (np. `LAT_AIPLATFORM_CORE`), przypisana do warstw MAND (governance, CI/CD platformy) i INF (infrastruktura wykonawcza), w zależności od tego, czy dominuje w nim warstwa operacyjna, czy sterująca. D6 zakłada, że `ai_platform` jest centralnym repo, które integruje mapę QV9D i orkiestruje pozostałe.

### 6.3. Poziom 2 – reguły mapowania katalogów ai_platform na INF/SEM/MAND

Struktura `ai_platform` jest specyficzna dla wdrożenia, dlatego rozdział D6 definiuje reguły mapowania semantycznego, a nie sztywne nazwy katalogów. Każdy katalog w `ai_platform` klasyfikujemy po roli, a dopiero potem przypisujemy do odpowiednich współrzędnych w `/QV9D`.

Przykładowe klasy ról:

1. Katalogi z kodem wykonawczym i silnikami (np. moduły orchestratora, agenci wykonujący zadania, integracje z glitchlab/ swarmlab):

   * jeśli pełnią rolę logiki decyzyjnej, planowania lub przetwarzania treści → warstwa SEM;
   * jeśli pełnią rolę infrastruktury, wejścia/wyjścia, warstwy transportu → warstwa INF.
   * silniki „ostre” (np. generujące zmiany w AST, w parametrach modeli) są mapowane na most `OSTRZE-CIERPLIWOSC`,
   * komponenty dzielące pracę między moduły/serwisy → `WIOSKA-MIASTO`,
   * komponenty odpowiedzialne za layout danych, cache i zasoby → `RDZEN-PERYFERIA`.

2. Katalogi z konfiguracją, dokumentacją i specyfikacjami (np. `docs`, specyfikacje architektury, pliki konfiguracyjne pipeline’ów):

   * warstwa MAND,
   * jeśli są nośnikiem wiedzy i kontraktów architektury → `LOCUS-MEDIUM-MANDAT`,
   * jeśli definiują progi i warunki przejścia między stanami (np. polityka „co uznajemy za sukces testów”) → `PROG-PRZEJSCIE`,
   * jeśli opisują protokoły Human–AI (np. guideline’y użycia agentów) → `HUMAN-AI‡`.

3. Katalogi z testami, definicjami CI/CD, pipeline’ami (np. `.github`, `ci`, `pipelines`):

   * warstwa MAND,
   * most `PROG-PRZEJSCIE`,
   * architektura `CL`,
   * rodzaj artefaktu `CI`.

4. Katalogi z metrykami, raportami, analizami (np. `metrics`, `reports`, integracje z analizą glitchlabu):

   * warstwa SEM, jeśli metryki opisują jakość decyzji, semantyki i zachowania systemu,
   * warstwa INF, jeśli są to czysto techniczne benchmarki infrastruktury,
   * domyślny most `SEMANTYKA-ENERGIA`,
   * rodzaj artefaktu `METRICS`.

5. Katalogi z interfejsem użytkownika, HUD, rytuałami operacyjnymi (np. panele sterowania, pliki scenariuszy, configi dashboardów):

   * warstwa MAND,
   * most `HUMAN-AI‡`,
   * architektura `HYB` (bo łączą logikę systemu z percepcją człowieka),
   * rodzaj artefaktu `RITUAL`.

Zastosowanie tych reguł oznacza, że np. katalog z agentami orchestrationu, który zarządza kolejkami chunk-chunk, zostanie opisany ścieżką:

`/QV9D/SEM/WIOSKA-MIASTO/HYB/STATE/LAT_AIPLATFORM_AGENTS_*`

podczas gdy katalog z definicjami pipeline’ów CI dla tego samego modułu otrzyma ścieżkę:

`/QV9D/MAND/PROG-PRZEJSCIE/CL/CI/LAT_AIPLATFORM_AGENTS_CI_*`.

### 6.4. Algorytm mapowania chunk-chunk dla ai_platform

W duchu protokołu chunk-chunk mapowanie katalogów `ai_platform` na `/QV9D` jest traktowane jako osobny proces (loop) z czytelnym wejściem i wyjściem. Wejściem jest drzewo katalogów platformy oraz aktualna definicja mozaiki repozytoriów (artefakt `LAT_GLX_PROJECT_MOSAIC`). Wyjściem jest zbiór artefaktów STATE/SPEC w `/QV9D`, które opisują, jak każdy katalog jest osadzony w woluminie 9D.

Algorytm ma następujące etapy na poziomie specyfikacji:

1. Enumeracja: system pobiera drzewo katalogów `ai_platform` (np. do określonej głębokości) i dla każdego katalogu lub modułu tworzy rekord „kandydata do mapowania”.
2. Klasyfikacja roli: dla każdego kandydata przypisuje klasę roli na podstawie nazwy, lokalizacji i kontekstu (kod wykonawczy, dokumentacja, testy, metryki, interfejs). Część zasad jest deterministyczna (np. katalog `.github` zawsze jako CI), część może być heurystyczna lub wspierana przez ręczne adnotacje.
3. Przypisanie współrzędnych 9D: dla każdej klasy roli algorytm przypisuje:

   * warstwę INF/SEM/MAND,
   * most 9D, zgodnie z tabelą powiązań (np. testy → `PROG-PRZEJSCIE`, HUD → `HUMAN-AI‡`),
   * architekturę (CL, HYB lub docelowo Q),
   * rodzaj artefaktu (SPEC, STATE, METRICS, RITUAL, CI).
4. Generowanie identyfikatora Latarni: dla każdego katalogu wyliczany jest deterministyczny identyfikator `id_latarni` (np. jako funkcja nazwy repo, ścieżki katalogu i typu roli). W praktyce może to być skrót z rodziny SHA, ale szczegóły sposobu obliczania są w tym miejscu [NIEZIDENTYFIKOWANE — DO ZAPROJEKTOWANIA].
5. Materializacja artefaktów: dla każdego kandydata tworzony jest odpowiedni plik w `/QV9D` (np. plik `.state.json` lub `.md`), zawierający:

   * ścieżkę oryginalną w `ai_platform`,
   * współrzędne QV9D,
   * rolę i typ modułu,
   * ew. dodatkowe metadane (np. powiązanie z konkretnym repo z `LAT_GLX_PROJECT_MOSAIC`).

Ten proces może działać cyklicznie: każda zmiana w drzewie `ai_platform` (dodanie nowego modułu, zmiana struktury) powoduje aktualizację odpowiednich artefaktów w `/QV9D`. Dzięki temu wolumin 9D pozostaje zsynchronizowany z rzeczywistą strukturą systemu.

### 6.5. Interaktywność: statystyki, analiza rozmyta i zarządzanie obciążeniem 9D

Mapowanie `/QV9D` ↔ `ai_platform` nie jest wyłącznie statycznym słownikiem ścieżek. Jest fundamentem dla interaktywnej analizy systemu: wszystkie metryki, logi i wyniki testów, które powstają w `ai_platform`, mogą być oznaczane współrzędnymi QV9D. Oznacza to, że analizy statystyczne oraz analizy rozmyte można prowadzić w przestrzeni mostów 9D, a nie tylko po „surowych” nazwach katalogów.

Przykładowo, jeśli metryka opisuje stabilność agentów swarmu, to dane mogą być zgromadzone pod współrzędnymi `SEM/WIOSKA-MIASTO/HYB/METRICS/LAT_SWARM_*`. Analiza rozmyta może tutaj badać, z jaką pewnością dane zachowanie należy do obszaru „bezpiecznej eksploracji”, a z jaką zaczyna wchodzić w rejony nadmiernej agresywności (`OSTRZE-CIERPLIWOSC`) albo nadmiernych kosztów obliczeniowych (`SEMANTYKA-ENERGIA`). D6 nie projektuje samych algorytmów rozmytych, ale określa, że każdy zbiór danych statystycznych ma być opatrzony pełnymi koordynatami QV9D, tak aby można było prowadzić przekrojowe analizy wzdłuż osi:

* warstw (INF/SEM/MAND),
* mostów 9D,
* architektur (CL/HYB/Q),
* typów artefaktów (np. porównanie metryk a stanów i rytuałów).

Tym samym mapowanie z D6 staje się interfejsem pomiędzy światem „twardej” struktury katalogowej a światem miękkich analiz statystycznych i rozmytych, które próbują uchwycić złożone, często nieostre zachowania platformy Human–AI. Bez spójnej mapy QV9D dane pozostawałyby lokalne dla danego modułu; z mapą stają się elementami jednej, globalnej mozaiki obliczeniowej.

Plan–Pauza Rdzeń–Peryferia Cisza–Wydech Wioska–Miasto Ostrze–Cierpliwość Locus–Medium–Mandat Human–AI Próg–Przejście Semantyka–Energia
