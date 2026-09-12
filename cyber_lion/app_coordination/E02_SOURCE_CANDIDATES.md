# E02 — nieaktywna konfiguracja i adaptery inspekcji

Ten pakiet przygotowuje lokalny format konfiguracji i odczytu trzech źródeł:
powiązań zadania, indeksu request → admission oraz kanonicznych receiptów.
Operator potwierdził, że konfiguracja rzeczywistych źródeł jeszcze nie istnieje.
Pakiet jest kandydatem do przeglądu, bez integracji produkcyjnej.

## Użycie

Z katalogu checkoutu:

    python -m cyber_lion.app_coordination.source_candidates cyber_lion/app_coordination/e02-sources.inactive.json
    python -m unittest cyber_lion.tests.test_e02_source_candidates -v

Pierwsze polecenie sprawdza konfigurację i wypisuje braki. Kod wyjścia 0
oznacza poprawny nieaktywny dokument; runtime_ready i dispatch_allowed
zawsze pozostają false. Nie czyta wskazanych w nim źródeł. Kod wyjścia 2
oznacza niepoprawną lub niedostępną konfigurację.

Konfiguracja wymaga literalnego enabled: false i trybu INACTIVE_CANDIDATE.
Nie obsługuje trybu produkcyjnego. W szablonie subject i wszystkie trzy
lokalizacje, piny oraz przypisania zaufania są jawnie null: 10 braków.
Nie ma domyślnego producenta, grantów, kluczy ani automatycznej rejestracji.

## Interfejsy i istniejące kontrakty

CandidateSource(config, kind, root, decode_payload=...) ma dwa wejścia:

- inspect(key, trusted_now) zwraca wyłącznie CandidateInspection o statusie
  CONSISTENT_UNAUTHENTICATED_CANDIDATE, po kontroli spójności pliku.
- resolve(...) zawsze podnosi SourceUnavailable. Kandydat nie może zostać
  podłączony jako działające źródło do aktualnego adaptera admission.

| Rodzaj | Kontrola danych |
|---|---|
| task_binding | Jawnie przekazany dekoder istniejącego TaskActionBinding; digest E01 przez istniejący seal; zgodność zadania, kwalifikacji i provisioningu. |
| request_index | Jawnie przekazany dekoder istniejącego BoundTaskAdmission; zgodność zadania i provisioningu z kanonicznym receiptem. |
| admission | Bezpośrednio istniejący RuntimeAdmission.validate; digest wyszukiwania i provisioning muszą odpowiadać receiptowi. |

Dekoder to zależność jawnie przekazana przez kod kompozycji. Konfiguracja nie
wskazuje modułów ani funkcji do zaimportowania. Kształt pending kontraktów
task/index pozostaje w istniejących prototypach E02, nie jest kopiowany do
pakietu jako nowy silnik. Dodatkowy lokalny harness sprawdza kompozycję z nimi.

RuntimeAdmissionSourceTrustBinding jest importowany z istniejącego kontraktu.
Osobne tożsamości źródła indeksu i receiptów są obowiązkowe, ale nie dowodzą
niezależności fizycznej. compare_index_receipt porównuje dwa wyniki inspekcji
i zwraca MATCH_UNAUTHENTICATED_NO_RETRY_OR_DISPATCH. Nie zapisuje do journala.
Brak receiptu pozostaje brakiem wyniku, nigdy pozwoleniem na ponowienie efektu.

## Format i ograniczenia

Plik konfiguracji i pliki rekordów mają limit 256 KiB. Parser odrzuca dodatkowe
pola, duplikaty kluczy JSON, NaN/Infinity, nieprawidłowe kodowanie i przekroczenia
limitu. Snapshot zawiera schema lion.e02.source-snapshot/v1, kind,
source_binding i listę records (maksymalnie 1024). Każdy rekord ma key,
subject, issued_at, expires_at oraz payload. Duplikaty key są odrzucane.

Subject wiąże mission_id, task_id, runtime_instance_id, task_class,
checkpoint_revision, source_head, session_record_digest, qualification_digest,
task_digest i provisioned_executor_digest. Wybrany rekord musi odpowiadać
całemu oczekiwanemu subject. Oba czasy mają strefę czasową; rekord musi być
bieżący, a długość ważności nie może przekraczać limitu konfiguracji (1–300 s).

Lokalizacje snapshotów są względnymi ścieżkami JSON pod jawnym katalogiem
root. Odrzucane są ścieżki absolutne, traversal i rozwiązanie symlinku poza root.
Zmiana pliku unieważnia jego pin. Piny i zgodne identyfikatory wykazują wyłącznie
spójność bajtów: nie uwierzytelniają sesji, kwalifikacji, producenta ani requestu.
Samo mapowanie request → wynik w pliku nie dowodzi pochodzenia.

## Co pozostaje do rzeczywistego E02

1. Wskazanie i wdrożenie niezależnego producenta tożsamości sesji aplikacji.
2. Źródło kwalifikacji wiążące rzeczywisty runtime i klasę zadań.
3. Kanoniczny zapis request → receipt i niezależny odczyt źródła admission.
4. Bootstrap zaufania poza danymi żądania, walidacja autentyczności i odwołań,
   zgodnie z istniejącymi mechanizmami authority/PDP/provisioning.
5. Osobny review aktywacji, testy realnych źródeł i integracji z istniejącym
   RuntimeAdmissionEngine. Usunięcie odmowy resolve wymaga nowej implementacji
   weryfikacji i osobnego przeglądu; nie jest opcją konfiguracyjną tego pakietu.

Nie dodano sieci, serwisu, dispatchu, podpisywania ani drugiego PDP.
Syntetyczne rekordy istnieją tylko w testach. Nie można ich załadować jako
konfiguracji produkcyjnej — loader w ogóle nie obsługuje takiego trybu.

Zmiana dodaje nowy plik Python do inwentarza kandydata. Historyczne CI, piny
skanu i truth carriers nie kwalifikują tego nowego zestawu źródeł. Przed
publikacją potrzebny jest oddzielny przegląd inwentarza i pełna walidacja
integracyjna. Ten etap nie przelicza ani nie promuje starych dowodów.
