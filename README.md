# LION / ai_platform

**Eksperymentalna platforma nadzorowanej autonomii Human–AI do budowy, koordynacji i kontrolowanego wykonywania złożonych procesów przez agentów i roje.**

`ai_platform` jest repozytorium, w którym rozwijany jest **LION** — control plane i zestaw kontraktów wykonawczych oddzielających probabilistyczne rozumowanie agentów od deterministycznej autoryzacji, wykonania, obserwacji i rekonsyliacji skutków.

Historyczna nazwa **Cyber-Lion** pozostaje w przestrzeni nazw pakietu `cyber_lion` i w części dokumentacji. Nazwą całego rozwijanego systemu jest obecnie **LION**.

LION nie jest pojedynczym chatbotem, agentem kodującym ani pętlą wywołań modelu. Jest próbą zbudowania infrastruktury, w której wiele agentów może badać problem, tworzyć hipotezy, dzielić pracę i proponować działania, ale prawo do zmiany rzeczywistości pozostaje oddzielnym, jawnym i kontrolowanym mechanizmem.

---

## Po co istnieje LION

Podstawowy problem jest prosty: model AI może być bardzo dobry w analizie i generowaniu propozycji, ale jego pewność nie jest uprawnieniem do wykonania działania.

LION rozdziela więc:

```text
obserwację
→ interpretację
→ hipotezę
→ plan / proposal
→ autoryzację
→ wykonanie
→ receipt
→ obserwację skutku
→ rekonsyliację
→ kolejną ewolucję
```

Najważniejsza relacja architektoniczna brzmi:

```text
PROBABILISTYCZNA INTELIGENCJA
!=
DETERMINISTYCZNA WŁADZA WYKONAWCZA
```

Model może proponować. System kontroli może autoryzować. Wykonawca może wykonać tylko to, co zostało jawnie dopuszczone. Skutek musi być później obserwowalny i możliwy do przypisania do konkretnej misji, wykonawcy, polityki i decyzji.

---

## Główne niezmienniki

```text
OPEN INTELLIGENCE != OPEN AUTHORITY
PROPOSAL != AUTHORIZATION != EFFECT
NO ACTION WITHOUT IDENTITY
NO AUTHORITY WITHOUT PROVENANCE
NO PROBABILISTIC OUTPUT DIRECTLY AS EXECUTION
NO OBSERVABILITY LOSS WITHOUT AUTHORITY DEGRADATION
NO AGENT SPAWN WITHOUT IDENTITY + BUDGET + AUTHORITY CEILING
NO CROSS-SYSTEM CALL WITHOUT CONTRACT
NO GLOBAL CLAIM FROM LOCAL OBSERVATION
NO CONSEQUENTIAL EFFECT WITHOUT RECONSTRUCTABLE EVIDENCE
```

W praktyce oznacza to, że wzrost zdolności poznawczych agenta nie może automatycznie zwiększać jego uprawnień. Pogorszenie obserwowalności nie może zwiększać zakresu dozwolonych działań.

---

## Architektura

LION rozdziela system na trzy główne płaszczyzny:

```text
SEM  — percepcja, badania, hipotezy, analiza, planowanie, symulacja
MAND — tożsamość, provenance, polityka, autoryzacja, pamięć, audyt
INF  — procesy, pliki, API, sieć, sandboxy, workflow i realne skutki
```

Przejście między nimi ma być jawne:

```text
ŹRÓDŁA / SYSTEM / REPOZYTORIUM
            ↓
        OBSERWACJA
            ↓
      SEM — reasoning
            ↓
      DecisionProposal
            ↓
 MAND — identity / policy / authority
            ↓
      typed grant / gate
            ↓
   INF — bounded execution
            ↓
      ExecutionReceipt
            ↓
      OBSERWACJA SKUTKU
            ↓
       REKONSYLIACJA
            ↓
       NASTĘPNY STAN
```

Docelowo każdy istotny efekt powinien przechodzić przez deterministyczny punkt egzekwowania polityki — PEP / reference-monitor boundary — zamiast wynikać bezpośrednio z tekstowego polecenia modelu.

Pełny opis kierunku architektonicznego znajduje się w [`cyber_lion/TARGET_ARCHITECTURE.md`](cyber_lion/TARGET_ARCHITECTURE.md).

---

## Cykl operacyjny LION

Warstwa `/LION/` jest powierzchnią nawigacji, koordynacji i projekcji stanu. Nie jest sama w sobie źródłem authority.

Podstawowy cykl pracy ma postać:

```text
TARGET
→ OBSERVE
→ GAP
→ MISSION
→ DRONE / SWARM
→ BUILD
→ VERIFY
→ INTEGRATE
→ OBSERVE
→ RECONCILE
→ UPDATE PROJECTIONS
→ NEXT GAP
```

Agent lub rój najpierw obserwuje stan źródłowy, następnie otrzymuje ograniczoną misję, buduje kandydata, przechodzi weryfikację, a dopiero potem może dojść do kontrolowanej integracji. Po wykonaniu efekt jest ponownie obserwowany i rekonsyliowany z oczekiwanym stanem.

Punktem wejścia do tej warstwy jest [`LION/README.md`](LION/README.md), a jej katalogiem [`LION/catalog.json`](LION/catalog.json).

---

## Flota, roje i drony

Flota jest zarządzanym podsystemem, a nie pętlą `for` uruchamiającą kolejne modele.

Każdy executor powinien być związany co najmniej z:

```text
identity
mission
repository baseline
branch / path lease
authority context
sandbox binding
heartbeat
receipt chain
```

Zakres authority jest ograniczany w dół hierarchii:

```text
child <= parent
executor <= mission
mission <= fleet envelope
```

Zwiększenie liczby dronów nie może zwiększać uprawnień pojedynczego wykonawcy. Flota posiada również wspólny budżet skutków, m.in. dla liczby równoległych writerów, repozytoriów, branchy i modyfikowanych ścieżek.

Role buildera, verifiera, obserwatora i rekonsyliatora są rozdzielane od źródła authority. Builder nie powinien być jedynym końcowym verifierem własnego efektu.

Rejestry mogą opisywać wiele **logicznych dronów i rojów**. Sama obecność wpisu w rejestrze nie jest dowodem istnienia tej samej liczby niezależnych procesów produkcyjnych, sandboxów lub fizycznych executorów.

---

## Co jest obecnie zaimplementowane

Aktualny `master` zawiera znacznie więcej niż pierwotny Startup Evolution Agent. Główne klasy implementacji obejmują dziś:

- typowane kontrakty zdarzeń, provenance i tożsamości;
- `AgentRegistry` i `BranchOwnershipRegistry`;
- kontrakty i implementacje authority source, authority grant oraz weryfikacji authority;
- deterministyczny policy gate / PDP;
- provisioning executorów i kontrakty sandboxa;
- koordynację floty, observation sources, snapshoty runtime oraz rekonsyliację;
- runtime admission, currentness, execution i reconciliation;
- preconditions oraz mechanizmy zamykania misji i efektów;
- GitHub Actions jako kontrolowaną powierzchnię wykonawczą dla części misji;
- most dispatch → workflow run → observation;
- fail-closed failure receipts i temporal compatibility dla historycznych dispatchy;
- F009 live-runtime evidence plane z oddzieleniem bootstrapu authority od procesu runtime, przypiętymi wejściami trust oraz niezależnym procesem obserwacyjnym;
- testy regresyjne, kontraktowe, negatywne i adversarialne pod `cyber_lion/tests/`;
- operacyjne mapy, rejestry misji, kanałów, dronów i zależności w `/LION/`.

Pakiet `cyber_lion/startup_agent/` nadal istnieje jako wcześniejszy eksperymentalny subsystem. Nie opisuje już jednak zakresu całego `ai_platform`.

---

## Runtime evidence i kontrola skutków

Jednym z obecnych kierunków implementacyjnych jest powiązanie konkretnego działania z authority, polityką, tożsamością runtime i niezależną obserwacją efektu.

Uproszczony przepływ:

```text
MODEL / AGENT
    ↓ proposal
CONTROL PLANE
    ↓
POLICY / AUTHORITY
    ↓ admission
EXECUTOR / SANDBOX
    ↓ bounded effect
OBSERVATION SOURCE
    ↓
RECONCILIATION
    ↓
RECEIPT / VERIFIED STATE
```

Kod F009 rozwija ten model przez pre-runtime authority bootstrap, brak możliwości mintowania authority przez sam proces runtime, przypięte trust bindings, single-use semantics i oddzielny observer procesu/skutku.

To nadal nie oznacza, że każdy możliwy efekt w repozytorium posiada już produkcyjny, niepomijalny monitor referencyjny. Taki poziom gwarancji wymaga dowodu dla konkretnej ścieżki wykonawczej.

---

## Źródła prawdy

LION celowo nie traktuje dokumentacji ani historii czatu jako aktualnego runtime state.

Dla dynamicznego stanu obowiązuje zasada:

```text
LIVE GITHUB / CURRENT CI
>
EXACT GIT STATE
>
FRESH DERIVED PROJECTION
>
STALE PROJECTION
>
CHAT CONTEXT
```

`LION/status.json`, rejestry i mapy są użytecznymi projekcjami, ale mogą się zestarzeć. Przed działaniem wywołującym skutek stan repozytorium, CI, branchy i authority powinien zostać ponownie zaobserwowany.

---

## Status projektu

**Stan: aktywny rozwój eksperymentalny / executable architecture.**

LION posiada działające kontrakty, implementacje runtime, workflow GitHub Actions oraz szeroki zestaw testów. Repozytorium nie powinno jednak być opisywane jako ukończona, produkcyjna infrastruktura autonomiczna.

W szczególności wynik testu kontraktowego lub CI nie jest automatycznie dowodem:

- produkcyjnej izolacji OS dla każdej ścieżki wykonania;
- kompletnego production PKI i workload attestation;
- pełnej distributed revocation;
- produkcyjnej izolacji credentials;
- istnienia dużej liczby niezależnych fizycznych executorów;
- kompletnej end-to-end atestacji zewnętrznego modelu AI i każdego zewnętrznego efektu.

LION rozdziela więc trzy klasy stwierdzeń:

```text
OBSERVED / REPRODUCED
IMPLEMENTED / TESTED
TARGET / NOT YET PROVEN
```

Nieudowodniony target nie powinien być przedstawiany jako stan bieżący.

---

## Struktura repozytorium

```text
ai_platform/
├── README.md
├── AI_NATIVE_ROADMAP.md
├── platform.md
├── LION/
│   ├── README.md
│   ├── catalog.json
│   ├── status.json
│   ├── architecture/
│   ├── evolution/
│   ├── ops/
│   ├── protocols/
│   └── schemas/
├── cyber_lion/
│   ├── contracts/
│   ├── enterprise/
│   ├── adapters/
│   ├── registry/
│   ├── startup_agent/
│   └── tests/
├── examples/
├── tests/
└── .github/workflows/
```

Najważniejsze dokumenty:

- [`LION/README.md`](LION/README.md) — operacyjny punkt wejścia;
- [`LION/catalog.json`](LION/catalog.json) — katalog źródeł, map i rejestrów;
- [`cyber_lion/TARGET_ARCHITECTURE.md`](cyber_lion/TARGET_ARCHITECTURE.md) — architektura docelowa;
- [`cyber_lion/enterprise/README.md`](cyber_lion/enterprise/README.md) — model federacyjnej organizacji AI-Native;
- [`AI_NATIVE_ROADMAP.md`](AI_NATIVE_ROADMAP.md) — mapa ewolucji;
- [`LION/status.json`](LION/status.json) — projekcja stanu, wymagająca porównania z live GitHub przed użyciem operacyjnym.

---

## Uruchomienie testów

```bash
git clone https://github.com/DonkeyJJLove/ai_platform.git
cd ai_platform

python -m compileall cyber_lion
python -m unittest discover -s cyber_lion/tests -p "test_*.py" -v
```

Część przepływów integracyjnych jest wykonywana przez GitHub Actions i może wymagać środowiska runnera, kontekstu GitHub, OpenSSL albo innych jawnie wskazanych providerów. Testy lokalne nie zastępują dowodu właściwości konkretnego środowiska produkcyjnego.

---

## Status epistemiczny

LION jest jednocześnie systemem inżynieryjnym i programem badawczym. Dlatego należy rozróżniać:

```text
OBSERVED      — zaobserwowany stan lub efekt
DERIVED       — wynik deterministycznego przekształcenia
HYPOTHESIS    — twierdzenie oczekujące na falsyfikację
EXPERIMENTAL  — mechanizm w trakcie walidacji
TARGET        — architektura docelowa, jeszcze nieudowodniona
```

Confidence nie jest prawdą. Symulacja nie jest obserwacją świata. Wpis w rejestrze nie jest authority. Output modelu nie jest execution grant.

---

## Kierunek

Celem LION nie jest „autonomiczny agent, który może zrobić wszystko”.

Celem jest infrastruktura, w której **inteligencja może być rozproszona, adaptacyjna i probabilistyczna, podczas gdy prawo do wpływania na rzeczywistość pozostaje jawne, ograniczone, obserwowalne, weryfikowalne i odwoływalne**.

W skrócie:

```text
MYŚL SZEROKO.
DZIAŁAJ W WĄSKIM AUTHORITY.
OBSERWUJ SKUTEK.
REKONSYLIUJ STAN.
EWOLUUJ NA PODSTAWIE DOWODÓW.
```
