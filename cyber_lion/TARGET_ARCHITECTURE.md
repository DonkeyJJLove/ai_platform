# LION — Architektura docelowa i kierunek ewolucji

**Status dokumentu: ŻYWY DOKUMENT ARCHITEKTONICZNY — TARGET + DEVELOPMENT TRACK**

Ten dokument opisuje jednocześnie **architekturę docelową LION** oraz sposób, w jaki architektura ma dojrzewać równolegle z implementacją. Nie jest statyczną wizją końcową odłączoną od kodu. Każda istotna zmiana granicy zaufania, modelu authority, wykonania, obserwowalności, floty albo rekonsyliacji powinna prowadzić do ponownej obserwacji implementacji i — jeżeli zmienia model systemu — do aktualizacji tej architektury.

Dokument **nie jest źródłem execution authority**, nie zastępuje aktualnego stanu repozytorium, CI ani runtime i nie dowodzi, że wszystkie opisane mechanizmy działają produkcyjnie.

Historyczna nazwa **Cyber-Lion** pozostaje w przestrzeni nazw `cyber_lion` i w starszych dokumentach. Nazwą rozwijanego systemu jest obecnie **LION**.

---

## 0. Jak czytać ten dokument

LION rozwija się w trzech równoległych perspektywach:

```text
TARGET
— czym system ma się stać

IMPLEMENTATION
— co rzeczywiście istnieje w kodzie i testach

EVOLUTION
— jaka zweryfikowana różnica dzieli stan bieżący od targetu
```

Nie wolno mieszać tych perspektyw. Implementacja może wyprzedzić dokumentację, dokumentacja może opisywać target jeszcze niezaimplementowany, a projekcja stanu może stać się nieaktualna po kolejnym merge'u.

Dla dynamicznego stanu obowiązuje pierwszeństwo:

```text
REPRODUCED EXECUTION
>
LIVE CODE + CURRENT TESTS / CI
>
EXACT GIT STATE
>
MACHINE-GENERATED RUNTIME EVIDENCE
>
FRESH DERIVED PROJECTION
>
ACCEPTED ARCHITECTURE / GOVERNANCE
>
HISTORICAL SNAPSHOT
>
CHAT / PROMPT / SYNTHESIS
```

Architektura może ustanawiać wymaganie. Nie może sama udowodnić jego spełnienia.

Dla śledzenia rozwoju używane są stany:

```text
TARGET_ONLY
PLANNED
BUILDING
VERIFIED
INTEGRATED
OBSERVED
BLOCKED
QUARANTINED
SUPERSEDED
```

oraz stany epistemiczne:

```text
CURRENT
STALE
UNKNOWN
CONFLICTED
```

`INTEGRATED` nie oznacza automatycznie `OBSERVED`, a `UNKNOWN` nigdy nie oznacza sukcesu.

---

## 1. Cel architektoniczny LION

LION jest eksperymentalną platformą **nadzorowanej autonomii Human–AI**. Nie buduje „najbardziej autonomicznego agenta”. Buduje środowisko, w którym inteligencja może być szeroka, probabilistyczna, rozproszona i adaptacyjna, natomiast prawo do powodowania skutków pozostaje ograniczone, jawne, możliwe do odebrania i możliwe do późniejszej rekonstrukcji.

Fundamentalne rozdzielenie brzmi:

```text
PROBABILISTYCZNA INTELIGENCJA
!=
DETERMINISTYCZNA WŁADZA WYKONAWCZA
```

Model może:

```text
obserwować
interpretować
generować hipotezy
planować
proponować działanie
oceniać scenariusze
```

ale nie wynika z tego automatycznie prawo do:

```text
zapisu pliku
zmiany brancha
użycia credentiala
wywołania zewnętrznego API
merge'u
release'u
deployu
modyfikacji stanu produkcyjnego
```

LION ma być systemem, w którym **proposal, authorization i effect są różnymi bytami**.

---

## 2. Trzy płaszczyzny systemu

Architektura rozdziela trzy główne płaszczyzny:

```text
SEM
percepcja · reprezentacja · analiza · hipotezy · planowanie · symulacja

MAND
tożsamość · provenance · policy · authority · memory policy · audit

INF
procesy · pliki · API · sieć · sandbox · workflow · zewnętrzny efekt
```

Fundamentalna relacja:

```text
SEM proposal
!=
MAND authorization
!=
INF effect
```

Wspólny prompt, proces albo context window nie scala klas zaufania. Minimalnie należy odróżniać:

```text
DATA
INSTRUCTION
CONTEXT
IDENTITY
PROVENANCE
AUTHORITY
MEMORY
DECISION
ACTION
EFFECT
EVIDENCE
```

Ta separacja jest podstawą odporności na prompt injection, confused deputy, delegated-authority abuse, memory poisoning i transitive delegation.

---

## 3. Docelowe płaszczyzny funkcjonalne

W miarę dojrzewania LION trzy płaszczyzny SEM/MAND/INF rozwijają się w bardziej szczegółowe domeny funkcjonalne. Są to role architektoniczne; nie każda musi istnieć jako osobny proces lub repozytorium.

### GEP — Governance & Evidence Plane

Warstwa reguł, statusów epistemicznych, provenance, evidence, falsyfikacji i closure. Odpowiada za to, **co wolno uznać za zweryfikowane**, ale nie wykonuje skutków tylko dlatego, że twierdzenie jest dobrze udokumentowane.

### LRK — LION Reference Kernel

Referencyjny, możliwie deterministyczny rdzeń kontraktów i semantyki. Służy do definiowania inwariantów, walidacji, negatywnych przypadków i wzorców wykonania. Reference semantics nie są automatycznie production runtime.

### CLP — Cyber-Lion Live Platform

Bieżąca implementacja `cyber_lion` i jej kontraktów/warstw enterprise. Jest miejscem, w którym target jest stopniowo materializowany w kodzie.

### FCP — Fleet Control Plane

Planowanie misji, lifecycle floty, role, identity binding, lease'y, dependency graph, routing capabilities, heartbeat state i kontrola wspólnych budżetów skutków.

### FTR — Fleet Trusted Runtime

Warstwa wiążąca authority, currentness, runtime identity, admission, wykonanie i receipt. Jej celem jest doprowadzenie do sytuacji, w której model nie może sam stać się źródłem uprawnienia do działania.

### LEF — LION Executor Fabric

Rzeczywista warstwa dostarczająca niezależne executory: procesy, kontenery, VM/microVM, GitHub Actions albo inne kontrolowane workloady. Liczba logicznych dronów nie jest równoznaczna z liczbą instancji LEF.

### SEL — Sandbox Enforcement Layer

Mechanizmy egzekwujące granice systemowe wykonawcy: filesystem, procesy, sieć, credentials, namespace, capabilities, resource budget i inne efekty. Test kontraktu sandboxa nie jest jeszcze dowodem SEL na poziomie OS.

### CPF — Capability Provider Fabric

Jawne providery capabilities. Każdy provider deklaruje możliwości, input/output contract, wersję, trust class, effect surface, failure modes i warunki authority.

### RRP — Repository Reconciliation Plane

Warstwa porównująca oczekiwany i zaobserwowany skutek na repozytorium oraz prowadząca closure. RRP jest domyślnie read-only; cleanup wymaga nowego authority.

---

## 4. Kanoniczna pętla od świata do kolejnej ewolucji

Docelowy LION jest zamkniętą pętlą obserwacji, rozumowania, kontrolowanego wpływu i ponownej obserwacji:

```text
WORLD / REPOSITORY / SYSTEM / MARKET
                ↓
            OBSERVATION
                ↓
       EVIDENCE + PROVENANCE
                ↓
        SEMANTIC REASONING
                ↓
       HYPOTHESIS / GAP MODEL
                ↓
              MISSION
                ↓
       AGENT / SWARM FORMATION
                ↓
         ACTION PROPOSAL
                ↓
       INTENT NORMALIZATION
                ↓
 IDENTITY + BASELINE + AUTHORITY CONTEXT
                ↓
          PDP / POLICY GATE
                ↓
        TYPED BOUNDED GRANT
                ↓
   PEP / REFERENCE MONITOR BOUNDARY
                ↓
        EXECUTOR / SANDBOX
                ↓
          BOUNDED EFFECT
                ↓
      INDEPENDENT OBSERVATION
                ↓
          RECONCILIATION
                ↓
      RECEIPT / VERIFIED STATE
                ↓
      EVALUATION / LEARNING
                ↓
       ARCHITECTURE / POLICY Δ
                ↓
           NEXT MISSION
```

Pętla nie kończy się na `SUCCESS`. Sukces techniczny bez obserwacji efektu i rekonsyliacji jest stanem pośrednim.

---

## 5. Zakaz bezpośredniego cognition → effect

LION nie powinien posiadać legalnej ścieżki:

```text
LLM / retrieved document / hypothesis
        ↓
consequential API / repository / infrastructure effect
```

Model może wygenerować `ActionProposal`, ale nie może sam:

```text
mintować authority
zatwierdzić własnej polityki
rozszerzyć scope'u capability
wybrać siebie jako jedynego verifiera
uznać własnego effectu za zweryfikowany
```

Każde przejście z semantycznej propozycji do rzeczywistego skutku musi mieć jawny punkt transformacji z języka probabilistycznego do deterministycznego kontraktu wykonania.

---

## 6. Reference Monitor i complete mediation

Docelowo każdy consequential effect powinien przechodzić przez niepomijalny punkt egzekwowania polityki — **PEP / Reference Monitor boundary**.

Minimalne wymagania:

```text
1. każde działanie ma jawną tożsamość,
2. każde działanie ma mission binding,
3. każde działanie ma baseline i resource scope,
4. authority pochodzi z zewnętrznego wobec executora źródła,
5. policy decision jest oddzielona od execution,
6. grant jest ograniczony czasowo, operacyjnie i zasobowo,
7. executor nie może zwiększyć własnych uprawnień,
8. agent-to-agent transfer nie omija lokalnej polityki,
9. efekt jest obserwowany niezależnie od deklaracji executora,
10. utrata wymaganej obserwowalności degraduje authority,
11. krytyczny efekt ma rekonstruowalny receipt,
12. brak complete mediation oznacza brak prawa do twierdzenia o pełnej kontroli.
```

Samo tekstowe `allow/deny` w promptcie nie jest egzekwowaniem. Jeżeli zabronione narzędzie pozostaje technicznie osiągalne, granica authority pozostaje otwarta.

Dla mutacji repozytorium preferowany wzorzec to:

```text
DETACHED CANDIDATE PREPARATION
→ INDEPENDENT VERIFICATION
→ EXACT SINGLE-EFFECT ATTACHMENT
```

Executor finalnego attachmentu powinien posiadać wyłącznie capability potrzebną do jednego dokładnie zdefiniowanego ref-effectu, a nie ogólny zestaw uprawnień do repozytorium.

---

## 7. Model authority

Authority w LION jest **tłumione**, nie „dziedziczone przez autonomię”.

```text
child <= parent
executor <= mission
mission <= fleet envelope
```

Konsekwencje:

```text
verified identity != authorization
registered capability != authority
registry presence != authority
swarm membership != credential inheritance
model confidence != permission
prior success != future grant
observation != authority
recommendation != approval
```

Zwiększenie liczby agentów albo executorów nigdy nie może samo zwiększyć per-executor authority.

Flota posiada także agregowany effect budget, obejmujący zależnie od misji:

```text
max concurrent writers
max repositories
max branches
max changed paths
max consequential operations
credential exposure
external writes
cost / compute budget
```

---

## 8. Agent Foundry i tożsamość agenta

Docelowo agent nie jest nazwą modelu ani chat session. Agent jest jawnie opisanym podmiotem operacyjnym.

Minimalny `AgentSpec` powinien wiązać:

```text
agent identity
role
model/provider constraints
capabilities
context policy
memory policy
authority ceiling
observability requirements
mission compatibility
version / provenance
```

Instancja agenta powinna być odróżniona od specyfikacji. To samo `AgentSpec` może prowadzić do wielu instancji, ale każda instancja ma własny lifecycle i własne bindingi runtime.

Agent Registry jest źródłem opisu lifecycle/identity tylko w zakresie, w jakim jest aktualnym autorytatywnym stanem rejestru. Sam wpis nie przyznaje authority.

---

## 9. Flota, roje, formacje i mosaiki

Flota jest zarządzanym systemem współpracy, nie pętlą `for model in models`.

Każdy executor powinien być związany co najmniej z:

```text
immutable executor identity
mission
repository baseline
branch/path lease
authority context
sandbox/runtime binding
heartbeat/liveness
receipt chain
```

Role są rozdzielane:

```text
BUILDER
VERIFIER
OBSERVER
RECONCILER
AUTHORITY SOURCE
```

Builder nie powinien być jedynym finalnym verifierem własnego efektu.

Rój lub Mosaic Cell powstaje dla konkretnego problemu i może być rozwiązany po zakończeniu misji. Skład powinien wynikać z capability requirements, ryzyka, konfliktów ścieżek, lease state, health i observability, a nie z prostego przypisania „jeden model = jeden agent”.

Rejestry mogą reprezentować dziesiątki logicznych dronów. Taki wpis nie dowodzi istnienia tej samej liczby niezależnych procesów, maszyn, sandboxów ani production executorów.

---

## 10. Fleet Control Plane

FCP powinien odpowiadać za:

```text
mission lifecycle
agent/executor assignment
capability routing
branch/path ownership
lease management
dependency graph
heartbeat state
role separation
aggregate effect budget
revocation routing
closure preconditions
```

Scheduler nie może wydawać zadania wyłącznie dlatego, że executor deklaruje zdolność do jego wykonania. Routing musi uwzględniać:

```text
capability fit
authority ceiling
sandbox class
repository scope
lease state
dependencies
runtime health
observability
risk class
```

W przyszłym dojrzałym stanie FCP powinien być odporny na utratę pojedynczego executora i na częściowe partycje bez zwiększania authority pozostałych węzłów.

---

## 11. Trusted Runtime: admission, currentness, execution, reconciliation

FTR ma wiązać jedną trajektorię skutku:

```text
AUTHORITY
→ POLICY DECISION
→ RUNTIME IDENTITY
→ ADMISSION
→ CURRENTNESS
→ EXECUTION
→ OBSERVATION
→ RECONCILIATION
```

Ważne jest rozdzielenie czasu wydania decyzji od czasu rzeczywistego efektu. Authority lub policy poprawne w chwili planowania mogą być nieaktualne w chwili wykonania.

Dlatego przed consequential effect należy móc ponownie potwierdzić co najmniej:

```text
authority currentness
policy currentness
runtime identity
observability state
lease validity
replay / single-use state
```

Jeżeli któregokolwiek wymaganego elementu nie da się wiarygodnie potwierdzić, działanie wysokiego wpływu powinno zostać odrzucone albo przejść do jawnego stanu zdegradowanego.

---

## 12. Observability-conditioned authority

Docelowa zasada:

```text
OBSERVABILITY ↑
→ możliwa szersza przestrzeń authority

OBSERVABILITY ↓
→ authority nie może wzrosnąć
```

W szczególności:

```text
LOSS OF REQUIRED OBSERVATION
→ NO NEW HIGH-IMPACT AUTHORITY
```

Authority evaluation powinna uwzględniać:

```text
identity
mission
policy
provenance completeness
source trust
observer health
runtime integrity
requested impact
reversibility
currentness
execution history
```

Możliwe stany:

```text
NORMAL
→ DEGRADED
→ RESTRICTED
→ FROZEN
→ REVOKED
```

Reakcja na utratę telemetrii nie musi oznaczać paniki całego systemu. Musi być jednak proporcjonalna do klasy skutku. Dla efektów nieodwracalnych wymagania obserwowalności są najwyższe.

---

## 13. Execution Evidence Plane

Execution receipt nie jest automatycznie „prawdą”. Jest artefaktem ważnym w granicach zaufania do producenta, collectora, klucza, platformy i kompletności pomiaru.

Minimalny łańcuch powinien odpowiadać na pytania:

```text
kto
→ w ramach jakiej misji
→ na jakim baseline
→ z jakiego authority
→ według jakiej policy
→ w jakim runtime
→ wykonał jaką operację
→ jaki efekt obserwator zobaczył
→ czy efekt odpowiadał żądaniu
→ czy stan został zrekonsyliowany
```

Dla skutków wysokiego wpływu należy dążyć do separacji:

```text
AUTHORITY SOURCE
!= EXECUTOR
!= OBSERVER
!= VERIFIER / RECONCILER
```

Jeżeli ten sam skompromitowany komponent wykonuje efekt, obserwuje go i sam podpisuje własne twierdzenie o sukcesie, powstaje samozgłoszony dowód.

---

## 14. F009 — obecna ścieżka dojrzewania runtime evidence

F009 jest ważnym etapem rozwoju, ponieważ materializuje część docelowej granicy MAND → INF → EVIDENCE.

Obecny kierunek implementacji obejmuje między innymi:

```text
pre-runtime authority bootstrap
→ immutable / pinned authority inputs
→ provider trust binding
→ runtime admission
→ effect-time currentness
→ bounded sandbox effect
→ independent observer process
→ runtime reconciliation
→ receipt / proof artifacts
```

Istotne jest rozdzielenie bootstrapu authority od procesu runtime: proces wykonawczy nie powinien sam mintować lub podpisywać authority, z którego korzysta.

F009 pozostaje **ścieżką dowodową konkretnego runtime flow**, a nie uniwersalną gwarancją dla wszystkich efektów LION. Każdy nowy provider lub nowa klasa skutku musi osobno wykazać complete mediation, currentness, observation i reconciliation.

---

## 15. GitHub Actions jako bieżąca powierzchnia wykonawcza

GitHub Actions jest obecnie praktycznym providerem wykonania dla części misji i proofów. Nie należy jednak utożsamiać workflow run z pełnym LEF/SEL.

Rozwój E002 wprowadza warstwę łączącą:

```text
CONTROL-PLANE DISPATCH
→ GITHUB ACTIONS WORKFLOW
→ RUN IDENTITY / HEAD BINDING
→ OBSERVATION
→ FAILURE RECEIPT / SUCCESS EVIDENCE
```

Most musi zachowywać dokładne powiązanie dispatchu z konkretnym runem i ref/head. Historyczna kompatybilność czasowa może być dopuszczona tylko w jawnie ograniczonym modelu i powinna fail-closed przy niejednoznaczności.

GitHub Actions dostarcza użyteczną powierzchnię przejściową, ale target wymaga również niezależnych runtime providerów, które pozwolą badać isolation, credentials, attestation, liveness i revocation poza semantyką samego CI.

---

## 16. Rekonsyliacja i closure

Wykonanie nie kończy się na `SUCCESS` z narzędzia, workflow ani executora.

LION porównuje:

```text
EXPECTED EFFECT
vs
OBSERVED EFFECT
```

Misja lub batch nie mogą zostać uznane za zamknięte, jeżeli istnieje:

```text
unknown active mission
unknown result
unowned branch
unresolved write lease
unreconciled effect
observer disagreement
unknown post-effect state
```

Reconciliation jest domyślnie read-only. Jeżeli potrzebny jest cleanup, reset, branch delete albo inna korekta, musi istnieć nowe, jawne authority dla tego efektu.

Closure jest więc osobną właściwością systemu, a nie flagą ustawianą przez ostatniego executora.

---

## 17. Runtime providers i granice zaufania

LION nie zakłada jednego typu executora.

Docelowe klasy providerów:

```text
GitHub Actions
local controlled process
container / namespace sandbox
isolated VM / microVM
remote executor
future distributed execution provider
```

Każdy provider deklaruje:

```text
co potrafi wykonać
co może obserwować
co może wyegzekwować
czego nie może udowodnić
jakie ma failure modes
jaki ma trust anchor
jak wygląda revoke / freeze
```

Testowany kontrakt sandboxa nie dowodzi automatycznie OS-level isolation. Workload identity record nie dowodzi produkcyjnej atestacji. Zielone CI nie dowodzi complete mediation wszystkich skutków.

Docelowy trusted runtime wysokiego zaufania powinien wspierać:

```text
hardware/workload identity
attestation
credential isolation
bounded capabilities
sandbox enforcement
heartbeat / liveness
distributed revoke / freeze
currentness barriers
independent effect observation
tamper-evident receipts
```

---

## 18. Graf stanu jako projekcja epistemiczna

LION może utrzymywać globalny graf relacji:

```text
Entity
Repository
Artifact
Source
Observation
Evidence
Claim
Hypothesis
Agent
Mission
Swarm
Executor
Capability
Policy
Authority
Decision
Execution
Outcome
Memory
```

Przykładowe relacje:

```text
observed_from
derived_from
supports
contradicts
generated_by
consumed_by
executed_by
authorized_by
blocked_by
depends_on
changed
caused
correlated_with
supersedes
validated_by
```

Graf jest narzędziem korelacji, rekonstrukcji i planowania. Nie mintuje authority i nie zamienia automatycznie korelacji w przyczynowość.

Jeżeli projekcja konfliktuje z live GitHub, bieżącym authority source albo runtime evidence, należy odświeżyć projekcję.

---

## 19. Pamięć, uczenie i self-evolution

LION ma rozdzielać pamięć operacyjną od reguł wykonania.

```text
MODEL MEMORY
!=
POLICY
!=
AUTHORITY
```

Cykl ewolucyjny powinien zapisywać nie tylko „co się udało”, ale:

```text
co zaobserwowano
jakie hipotezy przyjęto
co zostało sfalsyfikowane
które mechanizmy zawiodły
które inwarianty przetrwały
jak zmieniła się architektura
jak zmienił się model ryzyka
które targety zostały osiągnięte
```

Self-evolution nie oznacza, że system może sam zwiększyć własne authority. Ewolucja może generować kandydatów zmian do kontraktów, polityk, kodu i topologii; ich promotion podlega tym samym bramkom co inne consequential changes.

---

## 20. Federacja providerów i repozytoriów

LION może integrować wyspecjalizowane repozytoria i usługi, ale rola providera nie powinna być przypisywana wyłącznie historyczną deklaracją.

Każdy provider powinien wejść przez adapter określający:

```text
capabilities
input/output contract
provenance
trust class
authority requirements
effect surface
failure modes
version / digest
observability
```

Repozytoria takie jak:

```text
glitchlab
swarm
sbom
chunk-chunk
HA2D
mosaic_lab_pro.py
SymulacjaKaskadySieciowej
hipotezy_nadawcze_LLM
writeups
```

mogą pełnić wyspecjalizowane role w szerszym systemie. Dokładna rola staje się częścią LION dopiero wtedy, gdy istnieje jawna i zweryfikowana integracja.

---

## 21. Model awarii

Architektura musi zakładać co najmniej:

```text
duplicate executor
duplicate mission
duplicate lease
duplicate branch owner
path overlap
stale baseline
lost heartbeat
forged / stale attestation
revoked executor or mission
dependency cycle
scheduler starvation
late result
result after cancellation
control-plane restart
authority-store restart
partial network partition
sandbox death
observer death
verifier death
reconciliation disagreement
telemetry loss
credential leakage
provider drift
policy drift
replay / duplicate effect
```

Każda taka sytuacja powinna:

```text
FAIL CLOSED
albo
ENTER EXPLICIT DEGRADED STATE
```

Nigdy nie może po cichu zwiększyć authority.

---

## 22. Security invariants

Docelowe niezmienniki bezpieczeństwa:

```text
I1  Probabilistic reasoning never directly implies execution authority.
I2  Loss of observability cannot increase authority.
I3  An agent cannot increase its own permissions.
I4  An executor cannot mint the authority it consumes.
I5  Agent-to-agent communication cannot bypass local policy.
I6  External AI never receives implicit direct authority over a protected resource.
I7  Critical effects require reconstructable execution evidence.
I8  Identity verification does not imply authorization.
I9  Registry state does not imply authority.
I10 Swarm formation does not imply credential inheritance.
I11 Compromise of a model must not automatically imply compromise of deterministic enforcement.
I12 Unknown state is never promoted to success.
I13 Integration does not imply post-effect observation.
I14 Cleanup requires separate authority.
I15 A builder cannot be the sole final verifier of its own consequential effect.
I16 Capability discovery is separate from capability permission.
I17 Currentness must be evaluated near effect time for high-impact actions.
I18 No production-control claim without complete mediation evidence for that effect path.
```

Te invariants powinny być okresowo atakowane przez testy negatywne i red-team architecture tests.

---

## 23. Model rozwoju architektury

Architektura rośnie razem z systemem przez jawny cykl:

```text
TARGET
→ OBSERVE IMPLEMENTATION
→ COMPUTE GAP
→ CREATE MISSION
→ ASSIGN DRONE / SWARM
→ BUILD
→ VERIFY
→ INTEGRATE
→ OBSERVE EFFECT
→ RECONCILE
→ UPDATE IMPLEMENTATION MAP
→ UPDATE DEPENDENCY GRAPH
→ UPDATE ARCHITECTURE IF THE MODEL CHANGED
→ SELECT NEXT GAP
```

Reguły przejść:

```text
BUILDING → VERIFIED
wymaga niezależnego evidence

VERIFIED → INTEGRATED
wymaga dokładnego, zweryfikowanego efektu

INTEGRATED → OBSERVED
wymaga post-effect observation

ANY → BLOCKED
wymaga jawnego, nierozwiązanego dependency/blockera

ANY → QUARANTINED
oznacza deny-only containment z jawną polityką resume

SUPERSEDED
wymaga wskazania replacementu i zachowania provenance
```

To jest mechanizm, dzięki któremu TARGET_ARCHITECTURE ma rozwijać się **równolegle do kodu**, a nie stać się dokumentem opisującym system sprzed kilku misji.

---

## 24. Etapy dojrzewania LION

Poniższe etapy nie są sztywnymi release'ami. Są klasami własności architektonicznych.

### Etap A — jawne kontrakty i epistemika

Cel:

```text
identity
events
provenance
capability registry
agent/mission/swarm specs
policy contracts
replayable state
```

Warunek przejścia: semantyka krytycznych obiektów nie istnieje wyłącznie w promptach.

### Etap B — governowana flota

Cel:

```text
immutable executor identity
mission binding
branch/path ownership
lease state
role separation
fleet budgets
reconciliation contracts
```

Warunek przejścia: zwiększenie liczby logicznych agentów nie zwiększa niejawnie authority.

### Etap C — deterministyczna granica runtime

Cel:

```text
canonical PDP
runtime admission
currentness
bounded execution
single-use / replay denial
execution receipts
```

Warunek przejścia: model nie ma bezpośredniej ścieżki cognition → effect w badanej klasie działań.

### Etap D — live runtime evidence

Cel:

```text
pre-runtime authority bootstrap
provider trust pins
independent observer
real effect observation
runtime reconciliation
failure receipts
```

Warunek przejścia: efekt można przypisać do konkretnego authority, runtime i obserwacji bez polegania wyłącznie na deklaracji executora.

### Etap E — niezależny Executor Fabric

Cel:

```text
real provisioning
OS/VM sandbox isolation
credential isolation
workload attestation
heartbeat
freeze / revoke
multi-executor scheduling
```

Warunek przejścia: istnieją niezależne instancje runtime, a nie tylko logiczne drony odwzorowane na wspólnej powierzchni wykonawczej.

### Etap F — distributed trusted fleet

Cel:

```text
distributed revocation
fault domains
partition handling
cross-executor receipts
aggregate effect budgets
survivable control plane
```

Warunek przejścia: utrata części floty lub control plane'u nie prowadzi do niekontrolowanego rozszerzenia uprawnień.

### Etap G — self-observing evolutionary operation

Cel:

```text
mission outcome evaluation
falsification registry
architecture gap recomputation
automatic candidate missions
controlled policy evolution
controlled architecture evolution
```

Warunek przejścia: system potrafi nie tylko wykonywać misje, ale również jawnie wykazać, czego nauczył się z ich powodzeń i porażek oraz które własne mechanizmy wymagają zmiany.

---

## 25. Bieżąca granica implementacyjna

W bieżącej linii rozwoju `master` istnieją już działające kontrakty i implementacje obejmujące między innymi:

```text
Agent Registry
Branch Ownership Registry
fleet coordination
executor provisioning contracts
executor sandbox contracts
canonical policy/PDP components
runtime admission
runtime execution
runtime currentness
runtime reconciliation
fleet snapshot / reconciliation paths
GitHub Actions dispatch bridge
run observation bridge
failure receipts
bounded temporal compatibility
F009 live-runtime evidence plane
```

Poziom dowodu jest jednak różny dla każdej warstwy. Część własności jest potwierdzona kodem i testami, część poprzez realne GitHub Actions, a część pozostaje targetem wymagającym niezależnego runtime lub silniejszej izolacji.

Najważniejsze ograniczenie interpretacyjne brzmi:

```text
IMPLEMENTED CONTRACT
!=
PRODUCTION ENFORCEMENT PROOF
```

oraz:

```text
LOGICAL FLEET
!=
PHYSICALLY INDEPENDENT EXECUTOR FABRIC
```

---

## 26. Najbliższy kierunek rozwoju architektury

Po obecnym etapie naturalna ścieżka nie polega na dodawaniu kolejnych abstrakcyjnych klas agentów, lecz na przesuwaniu granicy dowodu z poziomu kontraktu do poziomu rzeczywistego runtime.

Priorytet architektoniczny:

```text
1. external isolated runtime provider
2. authoritative effect-time currentness source
3. independent runtime observer
4. real credential isolation
5. real workload identity / attestation
6. freeze / revoke across runtime boundary
7. multi-executor provisioning
8. distributed failure handling
9. generalized Reference Monitor across effect classes
10. self-evaluation feeding the next architecture delta
```

Każdy kolejny krok powinien być traktowany jako próba falsyfikacji istniejącego modelu, a nie tylko jako implementacja kolejnego modułu.

---

## 27. Metryki dojrzewania architektury

Sukces LION nie powinien być mierzony liczbą agentów ani liczbą commitów. Istotne są właściwości kontroli i rekonstrukcji.

Przykładowe metryki:

```text
Decision Reconstructability
Effect-to-Action Attribution Rate
Authority Exposure
Observability Coverage
Independent Evidence Ratio
Containment Time
Revoke Latency
False Permit Rate
False Deny Rate
Unreconciled Effect Count
Unknown State Age
Branch/Lease Conflict Rate
Fleet Survivability
Executor Compromise Tolerance
Evidence Throughput
Policy-Gate Latency
```

Dla high-impact test set docelowo:

```text
UNATTRIBUTED HIGH-IMPACT EFFECTS = 0
UNKNOWN HIGH-IMPACT EFFECTS = 0
NEW AUTHORITY DURING REQUIRED-OBSERVATION LOSS = 0
```

---

## 28. Warunki, zanim wolno mówić o production-grade autonomy

LION nie powinien być określany jako produkcyjna infrastruktura autonomiczna tylko dlatego, że posiada dużą liczbę agentów, workflow albo testów.

Minimalny zestaw dowodów powinien obejmować:

```text
complete mediation dla zdefiniowanych effect classes
real workload identity
real sandbox / VM enforcement
credential isolation
independent observer path
currentness near effect time
replay protection
persistent heartbeat
revocation / freeze
reconciliation closure
failure-domain testing
independent verification
```

Dopiero wtedy konkretna ścieżka może zostać opisana jako production-controlled. Twierdzenie nie powinno automatycznie rozszerzać się na cały system.

---

## 29. Docelowy graf systemu

```text
                         OPERATOR / GOVERNANCE
                                  │
                       GEP — evidence / policy
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                 SEM / AI                  MAND / PDP
                    │                           │
              Agent Foundry                Authority
                    │                           │
               MissionSpec                     │
                    │                           │
          Fleet / Swarm Control Plane          │
                    └─────────────┬─────────────┘
                                  │
                         TYPED BOUNDED GRANT
                                  │
                       REFERENCE MONITOR / PEP
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                 LEF / FTR                   SEL
              executor runtime             sandbox
                    │                           │
                    └─────────────┬─────────────┘
                                  │
                                EFFECT
                                  │
                      INDEPENDENT OBSERVATION
                                  │
                               RECEIPT
                                  │
                                RRP
                          reconciliation
                                  │
                          VERIFIED STATE
                                  │
                         EVOLUTION / NEXT Δ
```

To nie jest graf fizycznego deploymentu. Jest grafem odpowiedzialności i granic zaufania.

---

## 30. Reguła końcowa

LION nie ma usuwać granicy pomiędzy probabilistycznym rozumowaniem a deterministyczną kontrolą. Ma tę granicę **utrzymywać, mierzyć i wykorzystywać**.

Docelowy system powinien umożliwiać:

```text
szeroką eksplorację
+ dynamiczną współpracę agentów
+ lokalną i globalną obserwację
+ jawne authority ceilings
+ deterministyczne consequence gates
+ izolowane wykonanie
+ niezależną obserwację efektu
+ rekonsyliację
+ kontrolowaną ewolucję
```

W najkrótszej formie:

```text
MODEL MOŻE PROPONOWAĆ.

FLOTA MOŻE PLANOWAĆ I DZIELIĆ PRACĘ.

PDP MOŻE AUTORYZOWAĆ.

PEP I EXECUTOR MOGĄ WYKONAĆ WYŁĄCZNIE OGRANICZONY EFEKT.

OBSERVER MA ZOBACZYĆ, CO NAPRAWDĘ SIĘ WYDARZYŁO.

RECONCILER MA USTALIĆ, CZY EFEKT ODPOWIADAŁ ZAMIAROWI.

EWOLUCJA MA WYNIKAĆ Z DOWODÓW, A NIE Z DEKLARACJI MODELU.
```

Architektura LION jest ukończona dopiero wtedy, gdy może rosnąć wraz z inteligencją systemu **bez równoległego, niekontrolowanego wzrostu jego władzy nad rzeczywistością**.
