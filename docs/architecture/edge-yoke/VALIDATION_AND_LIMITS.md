# Walidacja i ograniczenia R6

## Testy dostarczone w repo

`test_edge_yoke_policy`: deterministyczne progi, rozgrzewka, histereza, EMA, nieświeże dane i zatrzask kwarantanny.

`test_edge_yoke_gate`: podpisy i piny, sekwencje, wygasanie, journal/witness, blokada drugiego obserwatora i zachowanie przy zatrzymaniu.

`test_edge_work_unit`: izolowane bytes/workspace, bindings, zamknięte recipe, negatywne przypadki produktu, proces wykonawczy, timeout i weto w trakcie.

`test_edge_correction`: pełny payload zamiast samego ACK, niezależny routing, ochrona przed błędnym hostem/epoką, stale request i powtórzeniem niejednoznacznego wysłania.

`test_edge_r5_integration`: oryginalny R5 silnik z syntetycznymi źródłami authority, realny zapis, brak zapisu po późnym HOLD, zużycie admission i oryginalna odmowa po revoke.

```sh
python -B -m unittest discover -s cyber_lion/tests -p 'test_edge_*.py' -v
```

Na Linux zestaw R6 obejmuje 81 testów. Na Windows sześć przypadków `test_edge_r5_integration` jest jawnie pomijanych, ponieważ oryginalny R5 writer celowo wymaga descriptor-relative POSIX storage. To nie jest osłabienie bramki produkcyjnej ani akceptacja Windowsowego zapisu bez tego mechanizmu. Domknięcie R5 wymaga wykonania tych testów i regresji na Ubuntu/Docker. Testy Windowsowego obserwatora/Job Object/transportu i natywnego operatorowego pilota są osobne.

Testy narzędzia nakładania patcha są oddzielnie w dystrybucyjnej paczce. Obejmują `check/apply/verify/rollback`, kolizje, zmienione pliki, niezgodną bazę, zmiany po nałożeniu, przerwane potwierdzenie, CRLF oraz zachowanie nietkniętych lokalnych zmian. To nie są testy inferencji lub klastra. Raporty dystrybucyjne określają rzeczywiście wykonane zestawy i błędy wstępnych prób; nie sumuj powtórnych przebiegów jako niezależnego coverage.

## Granice

Przepis generuje i testuje mały produkt ze zaufanego szablonu. Nie wykonuje arbitralnego kodu modelu ani nie udostępnia raw shell. Rozszerzenie rodzin produktów wymaga osobnego kontraktu narzędzi, sieci, toolchainu, zasobów i niezależnego testu.

Osobny proces jarzma nie zapewnia sam rozdziału uprawnień. Docelowo klucz i konfiguracja obserwatora muszą być chronione odrębnymi kontami/ACL; builder nie może ich zapisywać. Job Object ogranicza własne procesy, nie wszystkie efekty hosta. Grupa procesów POSIX nie jest sandboxem wrogiego kodu. Brak obrony przed rootem, administratorem lub wrogim procesem tego samego użytkownika nie jest ukrywany przez hashe.

Kolektor nie przypisuje obciążenia do konkretnej misji, nie zbiera GPU/VRAM ani kolejki modeli. Są to osobne integracje źródeł. Obciążenie hosta nie dowodzi sprawności programu. Weryfikacja source hashes nie atestuje stanu interpretera w pamięci. Lokalne replay state i hash chain wymagają zewnętrznych pinów/checkpointów, aby chronić przed cofnięciem całego środowiska.

R24 pilot sprawdza weto przed krokami, ale nie gwarantuje natychmiastowego zabicia zdalnego `docker exec` po HOLD. Przerwanie klienta modelu nie dowodzi anulowania inferencji na serwerze. Nie powtarzaj automatycznie niejednoznacznych żądań. Nie instalujemy rozproszonego semafora przez lokalny lock; ograniczenie równoległości należy do istniejącego schedulera.

Transfer zachowuje limit oryginalnego artifact_transfer: 64 pliki, 128 KiB na plik, 512 KiB łącznie. Nie jest magazynem checkpointów dużych modeli. Hash określa integralność, nie autora, zgodę lub poprawność semantyczną. Pochodzenie i admission pozostają odrębnymi polami.

Nie wykazano pełnej formalizacji, wszystkich repozytoryjnych testów lub produkcyjnego E2E. Nie wykonano w autorowaniu wdrożenia Windows/R24, nowych inferencji ani live publication. Testy Windows i właściwego klastra są celowo następnym etapem operatora.
