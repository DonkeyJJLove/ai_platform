# CYBER-LION — inwentarz repozytoriów

Etykiety statusu używane w tym dokumencie:

- `EXECUTABLE` — bieżące repozytorium zawiera działający mechanizm software istotny dla roli docelowej.
- `MIXED` — współistnieją wykonywalne zasoby i istotne specyfikacje.
- `SPECIFICATION` — bieżąca wartość ma przede wszystkim charakter formalny/dokumentacyjny/badawczy.
- `RESEARCH` — repozytorium zawiera hipotezy/evidence/eksperymenty, a nie operacyjny runtime.

Zalecana klasyfikacja dalszych działań używa: `KEEP / REFINE / EXTRACT / GENERALIZE / INTEGRATE / DEPRECATE / EXPERIMENTAL`.

## 1. `DonkeyJJLove/ai_platform`

**Zaobserwowany stan:** przede wszystkim architektura/specyfikacja. Root zawiera obecnie `platform.md`, `LAT_GLX_PROJECT_MOSAIC.MD`, eksperymentalne testy/raporty i śledzony stan IDE. Materiał QV9D już modeluje `INF / SEM / MAND`, mosty semantyczne i mapowanie repozytoriów, ale repozytorium nie jest jeszcze wykonywalnym control plane'em.

**Bieżące capabilities**

- semantyczny układ współrzędnych QV9D,
- koncepcja project mosaic i mapowanie ról repozytoriów,
- reguły mapowania fizycznych ścieżek na współrzędne semantyczne,
- eksperymentalne porównanie mostów 9D.

**Unikalny zasób:** istniejące miejsce koncepcyjne dla topologii cross-repository i governance.

**Dług / luka**

- statyczna/nieaktualna project mosaic zamiast discovered registry,
- brak implementacji wspólnego kontraktu encji/zdarzeń,
- brak runtime capability registry,
- brak global graph service,
- brak authority/policy engine,
- brak runtime cross-repo tracing,
- istniejący PR process-upgrade powinien zostać zintegrowany przed pracami kompatybilnościowymi albo włączony do tych prac.

**Rola Cyber-Lion:** `Control Plane / Contract Authority / Registry / QV9D Mapping`.

**Disposition:** `KEEP + REFINE + GENERALIZE + INTEGRATE`.

---

## 2. `DonkeyJJLove/chunk-chunk`

**Zaobserwowany stan:** repozytorium silnie zorientowane na protokół, z machine-readable `hmk9d_protocol.yaml`, obszerną specyfikacją HMK-9D, promptami i definicjami mostów semantycznych. Modeluje `Δ`, relacyjny stan 9D i przejścia semantyczne, ale nie jest jeszcze ogólnym runtime service routingu kontekstu.

**Bieżące capabilities**

- kontrakt HMK-9D i osie `[T,S,R,E,I,F,A,P,D]`,
- model przejścia `chunk–chunk→`,
- mosty semantyczne i progi przejść,
- lokalna reprezentacja energii/ryzyka,
- roboczy słownik microcode/event.

**Unikalny zasób:** jawna strukturalna reprezentacja trajektorii semantycznych/procesowych.

**Dług / luka**

- rozróżnienie między metryką koncepcyjną i mierzoną wymaga enforcement,
- brak wspólnej Cyber-Lion entity/provenance envelope,
- w bieżącym root inventory nie wykazano wykonywalnego compression/router API,
- śledzone `.venv` nadal istnieje na default branch; PR process-upgrade oczekuje.

**Rola Cyber-Lion:** `Cognitive Compression & Context Routing contract/provider`.

**Disposition:** `KEEP + REFINE + EXPERIMENTAL + INTEGRATE`.

---

## 3. `DonkeyJJLove/glitchlab`

**Zaobserwowany stan:** znaczna ilość wykonywalnego kodu Python oraz architektury/specyfikacji. Istniejące moduły obejmują grafy, mapowanie AST, mosaic, pipeline, registry, delta, analysis, security, testy i UI. Dokumentacja opisuje już BUS/EGDB, SAST Bridge, inwarianty i fail-closed control.

**Bieżące capabilities**

- ekstrakcja AST i grafów,
- reprezentacja delta-first i fingerprints,
- transformacje AST↔Mosaic,
- inwarianty oraz koncepcje thresholds/gating,
- lokalne callable/filter registry,
- koncepcje normalizacji/prioritization SAST,
- architektura zdarzeń/telemetrii BUS/EGDB,
- GUI/HUD i artefakty analityczne.

**Unikalny zasób:** najsilniejszy bieżący połączony silnik `SEM` do analizy zmiany strukturalnej, anomalii i inwariantów.

**Dług / luka**

- topologia pakowania jest niespójna: `pyproject.toml` wyszukuje `src/glitchlab*`, podczas gdy bieżący inventory `src/` nie ujawnia takiego układu pakietu,
- generated/local state jest śledzony na default branch (`.env.local`, `*.egg-info`); PR process-upgrade oczekuje,
- lokalny registry nie nadaje się na globalny capability registry Cyber-Lion,
- deklaracje dokumentacyjne dotyczące sandbox/fail-closed muszą zawsze być związane z rzeczywistym enforcement wykonania.

**Rola Cyber-Lion:** `Anomaly / Novelty / Delta / Structural Analysis provider`.

**Disposition:** `KEEP + REFINE + EXTRACT adapters`; **nie przepisywać core**.

---

## 4. `DonkeyJJLove/HA2D`

**Zaobserwowany stan:** przede wszystkim specyfikacje cognitive-state/Human–AI: PCE, MCV, SNAP, THOUGHT, MORPH_UNIT, `_neuro_`, HUD, revision viewer i context protocol. Podczas archeologii root nie zidentyfikowano porównywalnego wykonywalnego runtime.

**Bieżące capabilities**

- koncepcje persistent vs temporary context,
- słownik delta/revision,
- specyfikacja Human–AI HUD,
- modele cognitive-state i semantic-revision.

**Unikalny zasób:** jawne rozdzielenie persistent context, working context i human-facing replay.

**Dług / luka**

- wiele twierdzeń ma charakter architektoniczny/heurystyczny zamiast implementacyjny,
- klasy pamięci i polityka memory-write nie są jeszcze wspólnymi kontraktami,
- metryki `_neuro_` wymagają jawnego zakresu jako eksperymentalne deskryptory procesu, a nie pomiary fizjologiczne,
- PR process-upgrade oczekuje.

**Rola Cyber-Lion:** `Cognitive State / Memory Contract / Human–AI Interaction Plane`.

**Disposition:** `KEEP + REFINE + FORMALISE + EXPERIMENTAL`.

---

## 5. `DonkeyJJLove/hipotezy_nadawcze_LLM`

**Zaobserwowany stan:** celowo małe repozytorium badawcze zawierające README i falsyfikowalną hipotezę dotyczącą kanału text→token.

**Bieżące capabilities**

- formułowanie hipotez,
- jawne warunki falsyfikacji,
- organizacja evidence/argumentów,
- badania komunikacji/reprezentacji.

**Unikalny zasób:** laboratorium epistemiczne, którego output powinien mieć postać claims/evidence, a nie authority.

**Dług / luka**

- estymaty prawdopodobieństwa hipotez domyślnie nie są pomiarami empirycznymi,
- brak machine-readable schema hipotez/evidence,
- brak experiment registry,
- PR process-upgrade oczekuje.

**Rola Cyber-Lion:** `Communication Epistemology Lab / Hypothesis source`.

**Disposition:** `KEEP + EXPERIMENTAL + FORMALISE`; nie przekształcać w runtime authority.

---

## 6. `DonkeyJJLove/mosaic_lab_pro.py`

**Zaobserwowany stan:** jedna duża wykonywalna aplikacja Python oraz README. Implementuje ekstrakcję grafu AST, topologię, A*, wizualizację honeycomb 3D i abstraction/supergraph sterowane λ.

**Bieżące capabilities**

- transformacja Python AST→graf,
- klasy krawędzi strukturalnych,
- planowanie ścieżek A* we własnej geometrii,
- abstrakcja λ i konstrukcja supergrafu,
- interaktywna wizualizacja.

**Unikalny zasób:** działający prototyp wielopoziomowej reprezentacji strukturalnej.

**Dług / luka**

- monolityczny program łączy analizę i GUI,
- brak stabilnej granicy library/API do użycia cross-repo,
- reprezentacja geometryczna nie może być traktowana jako prawda semantyczna bez jawnego kontraktu mapowania.

**Rola Cyber-Lion:** `Mosaic Structure / Abstraction Engine`.

**Disposition:** `KEEP + EXTRACT + REFINE`; najpierw wyodrębnić czysty interfejs analityczny, zachowując kompatybilność UI.

---

## 7. `DonkeyJJLove/sbom`

**Zaobserwowany stan:** wykonywalne/laboratoryjne środowisko DevSecOps z silnym kontraktem danych. AID jest propagowany przez zdarzenia SBOM/scan/delta/gate; repozytorium zawiera Jenkins/toolbox, alternatywy Elastic/Splunk i dokumentację.

**Bieżące capabilities**

- stabilny Application Identity Descriptor (AID),
- event envelope z timestamp/event type/AID/payload,
- łańcuch procesu SBOM/scan/delta/gate,
- CI/CD gating,
- analityka i identity-over-time.

**Unikalny zasób:** najsilniejszy istniejący konkretny kontrakt identity/provenance/event w portfolio.

**Dług / luka**

- AID jest application-centric i nie może zostać złamany przez generalizację,
- szersza Entity Identity wymaga compatibility wrapper, a nie zastąpienia,
- LBOM/Decision-BOM/Agent-BOM itd. są koncepcjami targetowymi, a nie bieżącymi kompletnymi implementacjami.

**Rola Cyber-Lion:** `Provenance / Supply Chain / Identity compatibility anchor`.

**Disposition:** `KEEP + GENERALIZE via adapter + INTEGRATE`.

---

## 8. `DonkeyJJLove/swarm`

**Zaobserwowany stan:** wykonywalne rozproszone laboratorium z dronami, agregacją UDP/MQTT, Flask APIs, PostgreSQL, AI service, Kubernetes/Istio, monitoringiem, NetworkPolicy i RBAC.

**Bieżące capabilities**

- rozproszeni workerzy/producenci,
- zbieranie i transport telemetrii,
- API i persistence,
- model inference service,
- topologia wykonawcza Kubernetes,
- service mesh/monitoring,
- kontrole sieciowe i RBAC.

**Unikalny zasób:** najsilniejszy bieżący prototyp execution-mesh `INF`.

**Dług / luka**

- surowy domain JSON przechodzi między usługami bez Cyber-Lion identity/provenance/correlation envelope,
- brak cross-service execution receipt,
- bieżący RBAC agregatora obejmuje authority update/patch deploymentów, podczas gdy zaobserwowany kod agregatora jedynie forwarduje telemetrię — wymaga to przeglądu least-authority,
- brak jawnego policy/gate pomiędzy predykcją AI i consequential action,
- duplikat `README.md` / `readme.md` na default branch jest długiem stanu repozytorium.

**Rola Cyber-Lion:** `Agent Execution Mesh / Event Transport / Tool & Sandbox execution target`.

**Disposition:** `KEEP + REFINE + INTEGRATE`; dodać adaptery przed zmianą usług domenowych.

---

## 9. `DonkeyJJLove/SymulacjaKaskadySieciowej`

**Zaobserwowany stan:** spakowany wykonywalny projekt system-dynamics w Pythonie z deterministycznymi przebiegami, Monte Carlo, Morris, Sobol, konfiguracją, CLI i wielokrotnego użytku interfejsem `run_model`.

**Bieżące capabilities**

- symulacja scenariuszy,
- deterministyczne i stochastyczne execution,
- walidacja parametrów,
- Monte Carlo,
- globalna analiza wrażliwości Morris/Sobol,
- analiza phase/bifurcation,
- reprodukowalne interfejsy seed/config.

**Unikalny zasób:** dojrzała capability symulacyjna wielokrotnego użytku z jawnym językiem model-risk.

**Dług / luka**

- bieżące równania są domain-specific,
- capability powinna zostać wystawiona przez ogólny kontrakt symulacji bez sugerowania, że aktualny model obejmuje wszystkie klasy propagacji,
- adapter observation graph→perturbation→N futures nie istnieje jeszcze jako ogólne API Cyber-Lion.

**Rola Cyber-Lion:** `Propagation / Systemic Risk / Counterfactual Simulation provider`.

**Disposition:** `KEEP + WRAP + GENERALIZE interface`; zachować model domenowy bez zmian.

---

## 10. `DonkeyJJLove/writeups`

**Zaobserwowany stan:** duży, ustrukturyzowany żywy korpus badawczy z lokalną nawigacją README, architekturami AI security, eksperymentami, raportami PDF, LOCI, cyber research i materiałami epistemicznymi.

**Bieżące capabilities**

- korpus evidence/research,
- warstwa publikacyjna,
- specyfikacje architektury,
- rekordy metodologiczne i materiał negatywny/falsyfikacyjny,
- nawigowalne drzewo tematów.

**Unikalny zasób:** długoterminowa historia badań/evidence całego ekosystemu.

**Dług / luka**

- dokumenty nie mają jeszcze wspólnego machine-readable manifestu epistemic/provenance,
- free-form text nigdy nie może stać się runtime policy/authority tylko dlatego, że został pobrany,
- relacje experiment/result/superseded wymagają jawnego indeksowania przed automatycznym ingestem.

**Rola Cyber-Lion:** `Research Corpus / Evidence & Knowledge Provenance source`.

**Disposition:** `KEEP + INDEX + FORMALISE metadata`; nie używać free-form corpus jako bezpośredniego authority source.

---

# Wniosek dotyczący dojrzałości cross-repository

```text
SPECIFICATION-DOMINANT:
  ai_platform
  chunk-chunk
  HA2D

EXECUTABLE / MIXED:
  glitchlab
  mosaic_lab_pro.py
  sbom
  swarm
  SymulacjaKaskadySieciowej

RESEARCH CORPUS / EPISTEMIC:
  hipotezy_nadawcze_LLM
  writeups
```

Architektura docelowa musi zatem być **federowana przez kontrakty i adaptery**. Traktowanie każdego repozytorium jako już działającej usługi operacyjnej byłoby błędem kategorii architektonicznej.
