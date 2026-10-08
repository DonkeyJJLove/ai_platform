# LION — autonomiczne wykonanie a granica dostarczenia wiadomości (R1)

Status: **SOURCE_CANDIDATE / NOT_DEPLOYED / AUTHORITY_EFFECT=NONE**. Dotyczy konsumenta `CanonicalConversationSaaSConsumer`, przekazywania wyników do natywnego wątku ChatGPT SaaS oraz sposobu prowadzenia dłuższych operacji LION. Nie zmienia timeoutów ani infrastruktury platformy ChatGPT.

## Rozpoznanie incydentu

Operator zaobserwował komunikat: **„Przekroczono limit czasu dostarczenia wiadomości. Spróbuj ponownie.”**. Bez bezpośredniego identyfikatora żądania, logu dostawcy i potwierdzenia przyczyny nie wolno klasyfikować go jako błędu kodu LION, ani utożsamiać go z porażką lub nieukończeniem operacji na MOON. Możliwe klasy zjawiska to problem dostarczenia odpowiedzi w UI ChatGPT, transport request/response, timeout lokalnego narzędzia i timeout wysłania zewnętrznego SaaS. Są to różne granice dowodu.

**Zaobserwowano w źródłach:** `browser_broker/src/main.cjs` stosuje timeout pięciu sekund dla lokalnych żądań HTTP. `canonical-conversation-consumer.cjs` pobierał do 128 oczekujących kandydatów i przechodził po wszystkich w jednym `tick`. Natywny adapter przeglądarki może czekać oddzielnie na URL, composer i powstanie wątku; brak natychmiastowego ACK nie rozstrzyga, czy kliknięcie Send nastąpiło. W starszym przebiegu wyjątek podczas `createProjectConversationWithPrompt()` pozostawiał trwały stan `PROVISIONING` bez jednoznacznej klasyfikacji jako niepewne wysłanie, co stwarzało ryzyko powtórnego wejścia w ten sam efekt.

## Zmiana implementacyjna

Od tej wersji konsument dopuszcza **maksymalnie jednego nowego kandydata w jednym cyklu**. Pozycja round-robin jest zapisywana w stanie lokalnym *przed* rozpoczęciem efektu, co redukuje skumulowaną pracę jednego wywołania i zapobiega głodzeniu kolejnych wątków.

Stany `PROVISIONING` i `DISPATCHING` po przerwanym wykonaniu są traktowane jako `SEND_UNKNOWN`, nigdy jako zgoda na resend. Błąd powstały w trakcie tworzenia i wysyłania wiadomości do nowego wątku jest od razu materializowany jako `SEND_UNKNOWN` z zachowaniem `broker_request_id` i oryginalnych digestów. Proces zgłasza `OPERATOR_REQUIRED`.

**Zasada pojedynczego nierozstrzygniętego wysłania:** gdy istnieje `PROVISIONING`, `DISPATCHING`, `SEND_COMMITTED`, `BOUND_SENT`, `SEND_UNKNOWN` lub `RESULT_OBSERVED`, nie można wysłać kolejnej wiadomości. Konsument odczytuje stan tej samej wiadomości. Nawet gdy jej nie ma już na liście oczekujących, zwalnia bramkę tylko po świeżym `RESPONDED` dla dokładnego `request_id`, z pełnymi, poprawnie sformatowanymi `response_digest` i `receipt_digest`, i `authority_effect=NONE`. Wielokrotny stan niepewny wymaga rekonsyliacji przez operatora. Brak potwierdzenia **nie oznacza** możliwości automatycznej ponownej próby.

Zmiana nie modyfikuje etapu API `lion_get_turn / lion_complete_turn`, nie przepisuje rozmów ani kolejek, nie uruchamia alternatywnego transportu i nie wyłącza walidacji tożsamości `conversation_id`, `binding_epoch`, `lane_id`, `request_message_id`, `correlation_id`, `causation_id`, `shared_context_digest` i `projection_digest`.

## Korekta strategii autonomicznej LION

Długą pracę należy dzielić na **skończone, niezależnie odczytywane efekty**, a nie oczekiwać, że jedna odpowiedź SaaS będzie trwałym nośnikiem całej misji. Przed efektem zachowuje się dokładny kontrakt, identyfikatory, expected source HEAD/TREE, generation, zakres zmian i warunek stop. Po efekcie odczytuje się stan rzeczywisty, zapisuje receipt/checkpoint i dopiero potem rozpoczyna kolejną fazę. Samo `TIMEOUT` albo błąd dostarczenia nie uprawnia do powtórzenia efektu.

**Budżety operacyjne — strategia, nie gwarancje czasu platformy:** w zadaniach prowadzonych z ChatGPT należy przekazywać niezależne informacje o osiągniętych etapach w krótkich odpowiedziach zamiast kumulować całą pracę w jeden wielominutowy message. Szybkie wywołania narzędzi powinny obejmować pojedynczą, ograniczoną akcję; długie host-side wykonania wymagają rzeczywistego identyfikatora zadania, zdarzenia zakończenia i osobnego odczytu. Przeniesienie do tła nie jest samo w sobie terminalnym receipt. Kontroler nie może wysyłać kolejnego turnu na podstawie braku natychmiastowej odpowiedzi.

Autonomiczny system powinien emitować stany semantyczne `RUNNING`, `AWAITING_RECEIPT`, `SEND_UNKNOWN`, `RECONCILE_REQUIRED`, `TERMINAL_OBSERVED`. Nie należy sprowadzać wszystkich timeoutów do `FAILED`; równie niepoprawne jest traktowanie `timeout` jako `SUCCESS`.

## Odbiór i ograniczenia

Testy jednostkowe: round-robin i zapis kursora, brak ponownego wysłania po `PROVISIONING`/`DISPATCHING`, timeout istniejącego i nowego wątku, pojedyncze nierozstrzygnięte wysłanie, weryfikacja digestów i brak zwolnienia blokady bez receipt. Testy te są źródłowe — nie dowodzą aktualizacji uruchomionej aplikacji Electron ani usunięcia komunikatu platformy ChatGPT.

Pakiet źródłowy został objęty **nowym** manifestem `LION/architecture/v1_5/cooperative_production_r1/SOURCE_PACKAGE_MANIFEST_CCF_R2.json`, który weryfikuje dokładne bajty konsumenta SaaS i nowy wybór manifestu przez bramkę integracji. Historyczny `SOURCE_PACKAGE_MANIFEST_CCF_R1.json` i runtime R24 `LION/evidence/r24-whole-integration/PACKAGE_MANIFEST.json` pozostają niezmienione. Zgodność nowego manifestu oznacza jedynie zgodność źródła, nie deployment.

Wdrożenie wymaga oddzielnego procesu: dokładny deployed source/renderer/browser broker, wydanie aplikacji, rebind service owner i pozytywny test end-to-end na **nowym** turnie, bez ponawiania istniejących `SEND_UNKNOWN`. Nie wolno usuwać historycznych pending turns, resetować kursora lub łamać single-sender authority dla poprawienia wskaźników sukcesu.

Oryginalny, już działający provider Windows `8780` i Mission Control `8766` pozostają poza zakresem tej źródłowej poprawki. Zmiany w osobnym PR dla floty `#430` także pozostają niezależne.
