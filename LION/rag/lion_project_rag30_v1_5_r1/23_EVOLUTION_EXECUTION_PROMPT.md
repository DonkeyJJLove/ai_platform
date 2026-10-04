# LION — rozwój architektury ewolucyjnej całej federacji przez ai_platform

PROMPT_ID=LION-FEDERATION-EVOLUTION-ARCHITECTURE-AND-MISSION-PROGRAM-R1
PROJECT=LION_EVOLUSION
INPUT_KNOWLEDGE_RELEASE=lion-rag30-v1.5-r1
DERIVED_FROM=LION-RAG15-FEDERATION-EVOLUTION-PROMPT-DESIGN-R1
MODE=SOURCE_RECONCILIATION_THEN_ARCHITECTURE_AND_REPOSITORY_MATERIALIZATION
DEEP_RESEARCH=FORBIDDEN
EXTERNAL_WEB_RESEARCH=FORBIDDEN
FUTURE_MISSION_LAUNCH=OPERATOR_THROUGH_EXISTING_AI_PLATFORM

Uruchomienie tej instrukcji oznacza wykonanie opisanego zadania projektowo-implementacyjnego. Nie jest uruchomieniem wszystkich przyszłych misji ani globalnym dopuszczeniem materialnych efektów. Metadane nie są polami LPCL.

## 1. Rezultat, który masz dostarczyć

Zaprojektuj i zmaterializuj rozwojową architekturę ewolucyjną całej federacji LION. Wykorzystaj już wykonane badania; nie rozpoczynaj od generowania nowego metapromptu ani ponownego opisania sensu RAG. Zapisz rzeczywiste dokumenty, modele, konieczne poprawki i źródła kandydatów, uruchom właściwe testy oraz opublikuj dopuszczony zakres na gałęziach repozytoriów z PR i readbackiem. ZIP może być kopią, nie jedynym rezultatem.

Drugim produktem jest skończony program kolejnych misji realizowanych przez istniejący ai_platform. Operator ma móc stopniowo uruchamiać je i uzyskiwać coraz większą zdolność tworzenia rozwiązań. Program nie może kończyć się na „system potrafi opisać własną architekturę”. Ma obejmować rozpoznanie potrzeby, kontekst i reprezentację, reuse lub generowanie komponentów, kompozycję, kontrolowaną materializację, falsyfikację, poprawioną generację i powrót dowodów do wiedzy.

## 2. Obowiązkowe wejście: RAG, potem źródła

Najpierw odczytaj całe 00_START_HERE, 01_MODEL_INSTRUCTIONS, 03_STATE_AND_CONTINUATION, 02_ROUTING_AND_SOURCE_MAP i 29_PACKAGE_MANIFEST z wybranego wydania. Następnie odczytaj wszystkie pozostałe pliki potrzebne do niniejszego zadania obejmującego całą federację, w szczególności 04–21 oraz mapy 24–28. Ten pakiet ma dokładnie 30 plików; nie wymagaj dodatkowych carrierów dawnego 40-plikowego układu do rozpoczęcia pracy.

Indeks 24 zawiera referencje do 211 historycznych rekordów, a nie ich payloady. Odzyskaj pełne źródło historyczne tylko wtedy, gdy zależy od niego konkretna decyzja; sprawdź jego bytes i hash. Bez źródła nie twierdź, że odtworzono jego treść. Zachowaj wcześniejsze wyniki, nowszy FAIL operatora dla cp1252 i ograniczenia zakresu testów.

Po orientacji odczytaj bieżące ai_platform/AGENTS.md, LION/AGENTS.md i właściwe instrukcje zakresowe, RAG_BOOTSTRAP.json, README.md, LION/README.md, aktualny architecture root, semantic_owners, mapy kontraktów/capabilities, process contract plane, Authorization Lifecycle, registry formalizacji i runbook. Gdy istnieje udokumentowany następca v1.5, użyj go z mapowaniem migracji; nie wymuszaj starej epoki z nazwy tego pakietu.

Pełną dokumentację ai_platform analizuj partiami. Zbuduj aktualny mianownik z exact tree, dokumentów i ich odnośników, a historyczny census traktuj jako wejście do uzgodnienia. Zapisuj status każdego materiału: znaleziony, pobrane bajty, przeczytany, przeanalizowany, przetestowany, niedostępny albo wyłączony z powodem. Nie ukrywaj pominiętych modułów pod procentem sukcesu. Brak blokuje zależną zmianę, nie całe niezależne projektowanie.

Korzystaj wyłącznie z dostępnych plików LION, repozytoriów, dokumentacji, artefaktów i dopuszczonych obserwacji. Użyj GitHub do Git/CI, SentinelX do zakresowanych odczytów hostów. LION-MCP-R2 służy tylko dokładnie powiązanemu turnowi; nie opróżniaj kolejki i nie kończ przypadkowych pending requests. Nie uruchamiaj Deep Research ani ogólnego researchu internetowego.

## 3. Granica obserwacji i ochrona pracy

Ponownie odczytaj default branch, HEAD/TREE oraz potrzebne refs każdego repozytorium. Początkowy zbiór: ai_platform, swarm, chunk-chunk, glitchlab, HA2D, hipotezy_nadawcze_LLM, mosaic_lab_pro.py, sbom, SymulacjaKaskadySieciowej i writeups właściciela DonkeyJJLove. Członkostwo potwierdź manifestami/registry i rzeczywistymi zależnościami; dodatkowe komponenty rozlicz, ale nie nadawaj sobie prawa do ich modyfikacji przez samo discovery.

Zachowaj PR405 i ukończone przyrosty peerów. Odtwórz relację niezbędnych poprzedników, w tym programu dwutorowej ewolucji, schema conformance, execution-binding/schema-closure, historycznej linii A02 oraz rodziny panel–SaaS–swarm. Nie przypisuj staremu digestowi nowych bajtów i nie resetuj checkoutu, by pozbyć się niewyjaśnionej delty. Brak pliku w jednym odczycie nie jest dowodem globalnego usunięcia pracy.

Zapisz początkowy wektor, przedział odczytów i zakres runtime observation. Przed publikacją sprawdź refy ponownie. Drift rozlicz dla dotkniętych zależności; nie wykonuj globalnego restartu audytu. Rozdziel Git source, integrated commit, deployed source, config, session/model identity oraz material executor.

## 4. Rekonstrukcja AS-IS i reprodukcja konkretnych problemów

Niezależnie odtwórz projekcję kodu i dokumentacji oraz dostępną projekcję runtime. Każdy komponent opisz przez ownera, odpowiedzialność, wejścia, wyjścia, consumer call site, stan trwały, kontrakty, efekty, awarie, testy i stopień potwierdzenia. Każda krawędź ma producenta, konsumenta, wersję, źródło, klasę dowodu i warunek unieważnienia. Nie nazwij manifestu dowodem interoperacyjności.

Sprawdź następujące hipotezy na aktualnych źródłach, nie przyjmuj ich jako wiecznych usterek:

A. `lion_context_provider.py` może nadal emitować stałe ARCHITECTURE_EPOCH=1.4, MATERIAL_EPOCH=R10, nazwę modelu i liczniki. Ustal konsumentów, kontrakt kontekstu i sposób source/session bindingu; oddziel źródłowe deklaracje od live poświadczenia.

B. `_compile_and_store_phase_contracts` i `interpret_process_source` mogą odmiennie interpretować panelowy program. Odtwórz te same bajty przez prawdziwy kompilator i izolowany ingress. Nie obniżaj profilu ani nie dopisuj semantyki do nieobsługiwanego źródła.

C. Natywne validate() pojedynczych kontraktów nie musi zapewniać poprawnego powiązania rodzica. Sprawdź actual composition root i istniejące testy. Reprodukuj niewłaściwy parent digest oraz błędy conversation, scope, cutoff i projection. Jeżeli istniejący owner już odrzuca błąd, nie buduj drugiego walidatora.

D. CanonicalConversationSaaSConsumer jest istniejącą implementacją o konkretnym transporcie i durable bridge. Sprawdź źródłowe i rzeczywiste miejsce startowej instrukcji, utworzenia rozmowy, wysłania, SEND_UNKNOWN i zwrotu wyniku. Nie zastępuj session SaaS API innego produktu ani nie zdejmuj CONTROL_PLANE validation.

E. Adapter swarm mapuje admission data, a verifier receiptów może nie wykonywać providerów. Sprawdź pochodzenie PDPResult i rzeczywistą drogę workloadu. Utworzenie obiektu ALLOW lub poprawnego receiptu nie dowodzi dopuszczenia i materializacji.

F. Nowszy wynik operatora wykazał błąd cp1252 w izolowanym procesie CLI. Zachowaj reprodukcję i fix strumienia UTF-8 oraz jawne dekodowanie subprocess. Nie zastępuj porażki string matchingiem ani wycięciem polskich znaków.

Dla każdego problemu zapisz wynik: CONFIRMED_IN_SCOPE, ALREADY_FIXED, HISTORICAL, NOT_REPRODUCED lub UNKNOWN z odpowiednim dowodem i granicą. To etykiety raportu, nie nowe runtime enums.

## 5. Zaprojektuj architekturę ewolucyjną, nie tylko plan napraw

Zdefiniuj docelowe zdolności zgodnie z 20_ARCHITECTURE_REQUIREMENTS. Rozpisz, jak ai_platform ma tworzyć nowe rozwiązania, a nie tylko wykonywać ręcznie przygotowane skrypty. Przeanalizuj przejście Gap → CapabilityNeed → reuse/BeanCandidate → Composition/Mosaic → materializer → artefakt → weryfikacja/falsyfikacja → poprawiona generacja → reconciliacja. Ustal rzeczywisty status każdego elementu i interfejsu.

Architektura semantyczna ma reprezentować lokalne perspektywy, źródła, relacje, hipotezy, niewiedzę, provenance i czas. Zachowaj MissionIntent, QueryPlan, RagContextEnvelope, SemanticScaffoldIR, SemanticAtom/Delta, RelevanceGraph/Projection, CommunicationEnvelope i aktualnych ownerów. HMK-9D i holomozaika muszą mieć źródłowo określony związek z reprezentacją, a nie rolę dekoracyjnych nazw. Nie uznawaj redukcji przestrzeni relewancji za dowód absolutnej kontroli AI.

Architektura poznawcza ma dopuszczać LOCAL, SaaS i deterministic providers zgodnie z rzeczywistą dostępnością. Wspólny kontekst, różne projekcje i payloady oraz osobne session/release identities muszą być rekoncyliowalne. Role builder/verifier/coordinator dobierz do capabilities i niezależności, nie lokalizacji modelu. Teacher output nie jest ground truth; consensus nie jest niezależnością źródeł.

Architektura procesowa ma zachować jeden owner postępu, trwałe conversation–mission bindings i właściwe przejścia intent/contract/capability/action/effect/completion. Architektura materialna ma przenosić prawdziwe bytes albo osiągalne zakresowane referencje między SaaS i federacyjnym workspace; /mnt/data nie jest globalnym filesystemem.

Architektura ewolucji ma objąć EvidenceBoundLearningEpisode, badania, symulacje, retention, koszty inferencji, budżety kontekstu i generacji, backpressure, ograniczenia zasobów oraz aktualizację dokumentacji/RAG. Wartości zmierzone, skonfigurowane, projektowane i nieznane oznacz osobno. Nie ustalaj parametrów z marketingowego opisu lub dawnych tabel harmonogramu.

Dla każdego problemu porównaj KEEP, reuse, rozszerzenie, adapter i refaktoryzację. Wybierz konkretny wariant z uzasadnieniem, kosztami, ryzykiem, kompatybilnością i rollback. Preferuj istniejących ownerów, ale nie utrwalaj błędnego kontraktu dla pozornej zgodności. Nie wprowadzaj nowego brokera, PDP, schedulera, RAG ownera czy bazy rozmów bez wykazanej konieczności oraz jawnej migracji odpowiedzialności.

## 6. Cała federacja ma własne funkcjonalne przyrosty

Dla wszystkich dziesięciu repozytoriów przygotuj lokalny work package albo potwierdzoną dyspozycję KEEP/VERIFY. Oprzyj się na źródłach i 14_FEDERATED_WORK_PACKAGES, nie na automatycznej liście „do napisania od nowa”. Rozpoznaj znaczenie zakończonych integracji F01–F09 i aktualnych konsumentów.

Rozwój chunk-chunk obejmuje semantykę przejść i zachowanie ograniczeń. glitchlab: rzeczywista analiza delty i inwariantów. mosaic: headless projekcja struktury. HA2D: snapshot, replay i izolacja epok. sbom: tożsamość odczytanych artefaktów. hipotezy: eksperyment i falsyfikator. Symulacja: SimulationResult i ModelRiskStatement. writeups: korpus, klasy dowodów, import wyników i retention. swarm: rzeczywisty kontrolowany workload i powrót wyników. ai_platform: integracja tych funkcji w ogólnym mechanizmie tworzenia rozwiązań.

Wskaż publiczne wejście, wyjście, wersję, konsumenta i test każdego użytego peera. Zachowaj strukturalny oraz dowodowy przekrój integracyjny i osobny runtime roundtrip. Nie zastępuj wywołania providerów samą walidacją ich opisów. Nie każdy peer musi uczestniczyć w każdej misji, ale żaden nie może zniknąć z architektury całej federacji.

## 7. Materializuj wszystkie konieczne zmiany w zakresie etapu

Po rekonstrukcji i decyzjach utwórz pełne docelowe dokumenty AS-IS/CANDIDATE/TARGET, typowane modele interfejsów i źródłową macierz traceability. Uaktualnij właściwe entrypointy, contract/capability maps, owner routing, dokumenty peerów oraz plan homeostazy tylko tam, gdzie zmiana jest uzasadniona. Nie kopiuj globalnego opisu do dziesięciu repozytoriów.

Dla potwierdzonych braków nie poprzestawaj na zaleceniu. Przygotuj rzeczywiste, przetestowane patche kodu niezbędne dla projektowanej architektury w izolowanym kandydacie, z zachowaniem poprawnego composition root. Zmiany ingerujące w aktualny runtime pozostają źródłowymi kandydatami do właściwej misji wdrożeniowej. Jeżeli dany moduł musi powstać dopiero w kolejnej misji, dostarcz konkretną specyfikację granicy, fixture, test i kartę jego implementacji; nie udawaj gotowego providera.

Każdy patch wiąże bazowy ref, poprzednie i nowe bytes, ownera, wymaganie, decyzję architektoniczną, test i misję. Zapisz go przez dostępne narzędzia, nie tylko w odpowiedzi tekstowej. W dopuszczonym zakresie opublikuj pliki na osobnej gałęzi i otwórz PR. Odczytaj commit/tree oraz rzeczywiste pliki. Brak uprawnień do publikacji ma być rzeczywistym wynikiem próby narzędzia; nie zakładaj go i nie proś operatora o ręczne kopiowanie, jeżeli zapis jest dostępny.

Nie wykonuj nieodwracalnych operacji, kasowania korpusu/worktrees, rotacji kluczy, aktualizacji agentów, migracji żywych baz ani deploymentu przyszłych misji tylko dlatego, że zlecono projekt całej federacji. Każda taka granica ma konkretny przedmiot, źródło dopuszczenia i warunek stopu.

## 8. Zbuduj program misji wykonywanych przez ai_platform

Zaprojektuj skończone fale według 21_MISSION_PROGRAM_DESIGN i rzeczywistych zależności. Rozdziel fundament kontekstu/procesu, kompozycję poznawczą, generatywność, funkcje peerów, materialne odbiory i knowledge closure. Istniejące naprawy wykorzystaj zamiast powtarzać. Przy starcie potrzeba skończonego bootstrapu, nie gotowości wszystkich przyszłych providerów.

Dla każdej misji zapisz pełną kartę: cel i nowa użyteczna zdolność; exact wejścia i protected effects; owner, peery i zależności; scope odczytu/zapisu; wykonawca i provider; kontrakty; budgets/stop conditions; wymagany LPCL dialect; fazy, guards i completion evaluators; testy; artifact/readback; rollback lub kompensacja; terminalny raport; kolejny dopuszczalny krok.

Wygeneruj rzeczywiste programy LPCL dla misji, dla których dostępny kompilator i interfejsy pozwalają zamknąć autorowanie. Użyj oryginalnego compile_canonical_run i rzeczywistego izolowanego ingressu; zapisz dokładne bytes, source digest, wynikowe IR, kontrakty i logi. Nie wymyślaj nowej składni, pól ani registered capabilities. Niewalidowalny następca otrzymuje jawny brakujący warunek i źródłowy test do zamknięcia, a nie pieczątkę READY.

Zachowaj jeden driver/scheduler i trwały handoff/fence, gdy bootstrap przekazuje mu postęp. Nie twórz zewnętrznego stałego runnera zastępującego ai_platform. Operator uruchamia kolejne dokładne misje; program może wytwarzać propozycję następnej, lecz nie rozszerzać automatycznie własnego scope.

## 9. Walidacja i cztery niezastępowalne odbiory

W autorowaniu wykonaj integralność nośników, referencji, schematów, linków i source bindings, testy jednostkowe nowych zmian, negatywne kontrole, kompilację LPCL oraz izolowane testy konsumentów. Zachowaj rzeczywiste failures. Nie naprawiaj testu przez obniżenie postcondition, usunięcie walidacji albo przepisanie oczekiwania na aktualnie wygenerowany wynik.

Odbiory późniejszych dopuszczonych misji zaprojektuj dokładnie:

1. Wejście przez właściwy panel uruchamia dokładny program; rzeczywista sesja SaaS uczestniczy; worker tworzy nowy użyteczny artefakt; niezależny test/readback sprawdza bytes; wynik i pochodzenie wracają do właściwego panelu i rozmowy.
2. Odrębne jednostki poznawcze, wykonawcze i sprawdzające wymieniają rzeczywiste wyniki; kontrolnie błędny kandydat jest odrzucony; kontrprzykład wraca; poprawiona generacja zachowuje lineage.
3. Ten sam ogólny mechanizm wytwarza kandydatów dla dwóch różnych potrzeb, w tym ai_platform i jednego peera, bez dwóch gotowych workflow skrojonych pod przykłady. Self-change control plane nie wdraża się sam.
4. Restart, utrata SaaS, zgubiony ACK, duplikat, stara generacja, podmiana bytes, wygasły lease, anulowanie i brak admission prowadzą do poprawnego recovery lub jawnego zatrzymania, bez podwójnego efektu i fałszywego COMPLETE.

Nie nazywaj offline fixture realną inferencją. Nie nazywaj samego receiptu wynikiem niezależnej obserwacji. Test literalnych podciągów nie jest ewaluacją semantycznego retrieval. Nowa sesja modelowa wymaga rzeczywiście nowej sesji, nie wyczyszczenia zmiennej w Pythonie. System bez dostępnego modelu może przejść strukturalne testy, lecz nie odbiór żywego roundtripu.

## 10. Formalizacja, publikacja i wiedza po zmianie

Wykorzystaj aktualną ścieżkę EvolutionDelta, ArchitectureFormalizationManifest, RequiredFormalizationSet, FederatedFormalizationBinding, proposal/binding, niezależna weryfikacja i FormalizationClosureRecord. Oddziel closure projektu, kandydata, publikacji oraz runtime. Nie wymagaj gotowego finalnego FCR zanim istnieją jego dowody; nie fabrykuj podpisu weryfikatora.

Źródła i testy stabilizuj przed projekcjami. Dokumentacja opisuje właściwe AS-IS oraz CANDIDATE/TARGET. Dopiero potem zamykaj właściwy source vector i truth/currentness carriers. Nie twórz pętli commitów tylko po to, by plik deklarował własny przyszły SHA.

Zaktualizuj RAG jako nową wersję wiedzy po rzeczywistej delcie, nadal nie przekraczając 30 plików projektu. Zachowaj source IDs, historyczne lokalizatory, zakres dostępności payloadów oraz rozróżnienie faktu, testu i projektu. Nie dopisuj przyszłych deployment observations przed wykonaniem. Instrukcja startowa ma prowadzić do nowych źródeł, nie pozwalać tekstowi RAG przejąć authority.

## 11. Produkty końcowe i kryterium zakończenia

W repozytoriach mają istnieć: pełna architektura i rejestr decyzji; aktualny source/coverage ledger; mapa wymagań i interfejsów; realne patche i source candidates; dyspozycje dziesięciu repozytoriów; skończony DAG i karty misji; dokładne zwalidowane LPCL tam, gdzie zamknięto wymagane wejścia; testy i logi; aktualizacja wiedzy oraz instrukcja pierwszego uruchomienia przez ai_platform. Rzeczywiste ścieżki ustal z ownerów. Przekaż commit/tree/PR oraz wyniki odczytu plików; nie tylko nazwę ZIP-a.

Raport końcowy rozdziela: gotowość materiałów architektonicznych; wykonane zmiany źródeł; ich publikację; zgodność programów misji; wdrożenie; materialne odbiory; ograniczenia pokrycia i unresolved dependencies. Gotowa architektura do realizacji może istnieć przed ukończeniem runtime. Nie oznaczaj przez to całej federacji jako produkcyjnie gotowej.

Przy ograniczeniu sesji zapisz checkpoint z dokładnym stanem, bajtami i pierwszym niezamkniętym zależnym krokiem. Nie uciekaj do kolejnego metapromptu, nie każ odtwarzać historii i nie obiecuj pracy w tle. Zakończ konkretnym programem prowadzącym do kolejnych użytecznych zdolności ai_platform i całej federacji.
