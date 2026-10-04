# LION: architektura ewolucyjna — kandydat pierwszego przyrostu

## Status i źródła

To źródłowo ograniczony projekt dalszego rozwoju oraz rzeczywista poprawka właściciela kontekstu. Nie jest pełnym zakończeniem polecenia `LION-FEDERATION-EVOLUTION-ARCHITECTURE-AND-MISSION-PROGRAM-R1`. Nie zamknięto pełnego mianownika dokumentacji, implementacji wszystkich peerów, formalizacji ani czterech materialnych odbiorów. `SOURCE_COVERAGE.json` zapisuje pełne i częściowe odczyty; wszystko poza nimi pozostaje NOT_READ.

Bazą ai_platform jest `0e24fd481697bf85fd5c4a4fdb93c39a757ff463`, tree `6d4e04fd6327b4e1130c7baf86090789d701b815`. Główne refy wszystkich dziesięciu repozytoriów odczytano ponownie. Odrębnie oznaczono cztery drzewa przeniesione z RAG26 dla tych samych commitów, których nie odczytano ponownie z obiektu commit. Wektor nie jest atomowym snapshotem ani deployment vector.

Kanoniczne źródła tej analizy: [root architektury](../README.md), [semantic owners](../semantic_owners.json), [rekonsyliacja F01–F09](../FEDERATION_FINAL_RECONCILIATION_SOURCE_R1.md), [process contract plane](../../v1_4/LION_PROCESS_CONTRACT_PLANE.md), [authorization lifecycle](../../v1_4/AUTHORIZATION_LIFECYCLE_CONTRACT.json) i [registry repozytoriów](../../../../cyber_lion/registry/repositories.json). Treści odczytano na powyższym ref; bieżące relatywne linki służą nawigacji, nie zastępują pinów w ledgerze.

## AS-IS: źródła, a nie deklarowany działający obieg

ai_platform pozostaje globalnym właścicielem kontraktów, integracji i programu misji. Root v1.5 opisuje zintegrowane kontrakty CommunicationEnvelope, MissionIntent, QueryPlan, RagContextEnvelope, SemanticScaffoldIR i SemanticRelevance. To dowód deklarowanego stanu źródłowego. Sam dokument nie potwierdza pełnego consumer path ani działającej inferencji.

Źródłowa rekonsyliacja opisuje ukończone F01–F09: swarm ma adapter roundtripu, chunk-chunk semantykę procesu, glitchlab analizę delty, HA2D snapshoty, hipotezy_nadawcze_LLM kontrakty eksperymentu, mosaic_lab_pro.py projekcję headless, sbom tożsamość artefaktu, SymulacjaKaskadySieciowej eksport wyników, writeups indeks korpusu. W tym przyroście nie przeczytano pełnych implementacji i testów peerów. Dyspozycja VERIFY oznacza sprawdzenie użycia istniejących zdolności, nie założenie ich nieistnienia ani obowiązek ponownego napisania.

Odczytany `build_lion_context` jest bezpośrednio wywoływany przez konstruktor Gateway. Dotychczas pętla odczytywała i hashowała pliki, lecz JSON autoryzacji i bootstrapu otwierała ponownie do interpretacji. Kontrolowana zmiana pliku po pierwszym odczycie pozwalała powiązać nową interpretację z digestem starych bajtów. Jest to potwierdzony kontrprzykład spójności pochodzenia; nie dowód obejścia materialnego PDP lub uzyskania autoryzacji.

Provider nadal zawiera stałe ARCHITECTURE_EPOCH=1.4, MATERIAL_EPOCH=R10, nazwę modelu i liczniki. Gateway powiela podobne literały w `state()`, tekście do modelu i komunikacie systemowym. Zmiana samego providera nie wystarczy do usunięcia fałszywych deklaracji z rzeczywiście wysyłanego żądania. Konieczne jest domknięcie odczytu bramy, jej rozszerzenia i testów, a następnie zmiana u obecnego ownera.

Bootstrap nadal preferuje R9. Wybrany przez operatora `lion-rag30-v1.5-r1` jest kontekstem tego autorowania; PR406 z publikacją pakietu pozostaje odrębnym przyrostem. Nie nadpisano bootstrapu i nie powtórzono publikacji tamtego pakietu. Root README i LION/README zachowują ponadto starszy akapit o MissionIntent jako następnym frontierze, mimo nowszego opisu zintegrowanego Semantic Cloud w korzeniu v1.5. Sprzeczność zapisano; w tym ograniczonym patchu nie awansowano całej dokumentacji do nowego stanu.

Na MOON zachowano wcześniejszy checkout i jego nieśledzone pliki. Nowy katalog źródłowy powstał osobno. Testy uruchamiano w tym katalogu, z fixture i zasobami tymczasowymi. Nie startowano usług, modeli ani workloadów federacji. Historyczna informacja o nieaktywnym K3S z wcześniejszej rekonsyliacji nie jest nową obserwacją runtime.

## CANDIDATE: wykonana delta A00

Poprawka istniejącego `lion_context_provider.py` przechowuje każdy odczyt źródła raz i interpretuje JSON dokładnie z przechowanych bajtów. Odrzuca niejednoznaczne powtórzone klucze, nieobiektowy JSON, błędny typ tablicy invariantów oraz niepoprawny identyfikator wydania. Identyfikator ma od 1 do 256 znaków ASCII, zaczyna się znakiem alfanumerycznym i dalej zawiera tylko znaki alfanumeryczne, kropkę, podkreślenie lub łącznik. Nie może wprowadzić kolejnej linii do tekstu kontekstu.

Interfejs LionContext, zestaw SOURCES/FED/INV, wymagane niezmienniki autoryzacji i domena digestu pozostają bez zmian. Poprawne, dotychczas obsługiwane wejście zachowuje dokładny digest. Nie zmieniono starych assertions, aby uzyskać wynik PASS. Nowe przypadki testowe uruchomiono również przeciwko oryginalnemu blobowi i uzyskano oczekiwane błędy; w kandydacie wszystkie 22 metody testowe przechodzą. Na MOON przeszło łącznie 37 testów z 15 istniejącymi regresjami Gateway, a `git diff --check` nie wykazał błędów.

Ta poprawka nie tworzy atomowego snapshotu wszystkich plików, nie ustala bieżącej zgody operatora, nie naprawia możliwego wyścigu symlinków i nie zmienia ograniczenia rozmiaru sprawdzanego po odczycie. Nie usuwa też wymienionych wyżej stałych twierdzeń o modelu, liczebności i epokach. Te ograniczenia są jawne, zamiast zostać ukryte pod ogólnym PASS.

## TARGET: rozwój zdolności całej federacji

W docelowym przepływie potrzeba operatora staje się MissionIntent z ograniczeniami, a QueryPlan wyznacza pytania potrzebne do decyzji. RagContextEnvelope zawiera rzeczywiście użyte źródła i cutoff. Scaffold i graf relewancji zachowują negacje, hipotezy, niepewność i zależności, a projekcje wybierają różne perspektywy dla konkretnych konsumentów. Kontrola między obiektami sprawdza relacje parent digest, scope, source, consumer i czas; poprawne validate pojedynczych obiektów nie wystarcza. Nowy walidator nie powstaje, jeżeli istniejący composition root już zapewnia taką kontrolę.

CognitiveInvocation, ModelCallV2 i ModelRelease wiążą wywołanie z rzeczywistą sesją i wersją modelu. Wspólny digest kontekstu, digest projekcji i hash faktycznie wysłanych bajtów pozostają oddzielne. Rola buildera, krytyka albo koordynatora wynika z zadania i capabilities, a nie z lokalności modelu. Wyniki SaaS i LOCAL zachowują oddzielne provenance. Wspólne źródło nie staje się dwoma niezależnymi dowodami.

Conversation plane ma zachować rozmowę, misję, epokę bindingu, lane, wiadomość, korelację i generację przez cały obieg. Istniejący durable bridge pozostaje właścicielem powiązania z sesją SaaS. Cold-start dołącza jawnie wybrane instrukcje jako wersjonowany kontekst; nie przepisuje zamrożonych identyfikatorów. SEND_UNKNOWN wymaga odtworzenia stanu przed retry. SaaS nie jest zastępowany innym produktem API w celu ukrycia brakującego transportu.

Process Contract Plane wiąże zamiar fazy, kontrakt wykonania, capability, Action i completion bez utożsamiania tych etapów. Istniejący driver oraz scheduler mają jednego właściciela kursora i trwały fence przy handoffie. Kompilacja rzeczywistym `compile_canonical_run` i test właściwego ingressu są niezależnymi warunkami. Nie zdefiniowano nowych enumów runtime na podstawie nazw misji tego projektu. Brak providera wymaga implementacji konkretnego ograniczonego interfejsu, nie kolejnej nieskończonej pętli WAIT_AND_DISCOVER.

Fabryka rozpoczyna od Gap/CapabilityNeed i oceny reuse. Istniejący komponent jest preferowany, gdy spełnia potrzebę i ograniczenia. W przeciwnym razie powstaje kandydat Bean, jawna kompozycja i Mosaic. Materializer korzysta z kontrolowanej ścieżki Action/authority/runtime/admission, a worker swarm otrzymuje konkretne wejście i granice workspace. Bajty są rzeczywiście przenoszone lub wskazywane osiągalną referencją; `/mnt/data` sesji SaaS nie jest współdzielonym filesystemem MOON.

Przekrój strukturalny używa funkcji chunk-chunk, glitchlab, mosaic i sbom tylko tam, gdzie ich wynik stanowi wejście kolejnego konsumenta. Przekrój dowodowy zachowuje hipotezę, falsyfikator, seed symulacji, ModelRiskStatement, AID, negatywny wynik w writeups oraz snapshot HA2D. Wynik symulacji nie zmienia klasy na obserwację live. Nie każdy peer uczestniczy w każdym wywołaniu; oba przekroje mają własny test integracyjny.

Nowa użyteczna zdolność zostaje wykazana dopiero wtedy, gdy wspólny mechanizm obsłuży dwie różne, wcześniej niezakodowane jako dwa osobne workflow potrzeby. Kontrolnie błędny kandydat ma wrócić jako kontrprzykład, a poprawiona generacja zachować lineage. Generowanie kodu, wykonanie workloadu i samomodyfikacja control plane nie dziedziczą wspólnej zgody. Wytworzenie poprawnego patcha nie uruchamia jego wdrożenia.

Recovery obejmuje restart po zapisie artefaktu i przed ACK, duplikat, reorder, spóźniony wynik, podmianę bajtów, wygasły binding i anulowanie. Poprawny wynik to niezależnie potwierdzony efekt albo jawne zatrzymanie zależnego działania, nigdy automatyczne ponowienie nieznanego skutku. Koszty, limity tokenów i wall-clock muszą otrzymać skończony binding przed wykonaniem; wartości w programie są projektowane, nie zmierzone.

## Decyzje architektoniczne

ADR-01: rozszerzyć istniejącego ownera kontekstu zamiast wprowadzać drugi RAG provider. KEEP bez poprawki utrzymuje reprodukowalną niespójność. Nowy adapter lub wymiana całego model plane nie są potrzebne dla A00. Wybrano jeden odczyt i interpretację tych samych bajtów. Koszt: zachowanie przechwyconych źródeł w pamięci do końca wywołania; limit per-source pozostaje dotychczasowy. Kompatybilność poprawnych danych i digestów zachowano.

ADR-02: oddzielić A00 od A01. Pozostawienie wszystkich statycznych deklaracji nie jest rozwiązaniem docelowym; ich globalna zamiana bez zamknięcia konsumentów grozi niespójnością systemowego tekstu, stanu panelu i fixture. A01 kończy się testem całego efektywnego żądania, nie tylko znalezieniem nowego napisu w providerze.

ADR-03: zachować F01–F09 i dyspozycję VERIFY dla peerów. Odczyt manifestu lub dokumentu integracji nie dowodzi realnego call site. KEEP następuje po pozytywnym teście, a EXTEND/REFACTOR dopiero po konkretnym kontrprzykładzie. Nie wykonuje się dekoracyjnych commitów we wszystkich repozytoriach.

ADR-04: opisowy DAG nie jest drugim schedulerem ani LPCL. Dziedziczenie wspólnych pól kart w MISSION_PROGRAM.json służy wyłącznie czytaniu projektu i jego kontroli. Każdy przyszły program wymaga rzeczywistego kompilatora, ingressu, guardów i completion evaluators. Nierozwiązane pola mają wartość null, nie fikcyjną implementację.

ADR-05: publikacja, integracja, wdrożenie i wiedza są osobnymi etapami. Draft PR jest checkpointem źródłowym. Nie tworzy się fałszywego FormalizationClosureRecord, podpisu weryfikatora lub obserwacji przyszłego runtime. Historyczny RAG1.5 i błąd Windows cp1252 pozostają bez nadpisania.

## Śledzenie wymagań i odbiór

R01: B01/C01/D01; R02: A00/B01/D01; R03: A00/A01/B02; R04: A01/B01/B02; R05: A02; R06: A01/A02/B02/C02; R07: C01; R08: C02/E01; R09: D01/D02/C01/E01; R10: D02/C01/E01; R11: D01/D02/C01; R12: C02/E01; R13: A00/D02/E02; R14: A02/E01/E02. To mapa projektu, nie deklaracja spełnienia wszystkich R01–R14.

DAG pozwala prowadzić niezależne domknięcia źródeł bez globalnego restartu. B01 nie wymaga gotowego panelu przed zbudowaniem kompozycji, a D02 nie blokuje pierwszego testu fabryki korzystającej z przekroju strukturalnego. Jednocześnie WIP właściciela repozytorium pozostaje ograniczony do jednego pociągu integracyjnego.

Cztery późniejsze odbiory pozostają NOT_RUN: właściwe wejście panelowe i realny SaaS prowadzą do nowych bajtów i powrotu wyniku; kontrolnie błędny kandydat wraca i powstaje poprawiona generacja; wspólny mechanizm obsługuje dwie różne potrzeby; awarie i odmowy nie powodują podwójnego efektu, złej rozmowy ani fałszywego COMPLETE. Testy strukturalne autora nie zastępują żadnego z nich.

Pierwszy niezamknięty krok: pełny odczyt `cyber_lion/app_coordination/hybrid_gateway_extension.py` i pozostałej ścieżki Gateway wraz z testami, aby A01 naprawił faktycznie wysyłany kontekst. Równoległe odczyty A02 zamykają prawdziwy ingress, operatorów, capability registry i completion evaluators. Kolejną materialną misję uruchamia operator przez istniejący ai_platform.
