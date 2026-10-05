# LION RAG 1.5 — HISTORY AND SUPERSESSION

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Historyczna prawdziwość i bieżące użycie

Wydania v1.3, v1.4, R7.1, R8-hybrid, R9-auth i source-sety v1.5 opisują różne epoki. R7.1 miało 188 dostępnych rekordów, dostarczony R9 — 211. Wcześniejszy audyt sprawdził zachowanie 188 bloków i 23 późniejsze dodatki. R9 obejmuje historię, nie tylko stan nazwany „current” w tytule rekordu.

Nie przepisuj dawnego braku modelu jako bieżącego braku ani historycznego planu jako ukończonej implementacji. Relacje SUPERSEDES, REFINES, MIGRATES_FROM i CONFLICTS_WITH muszą wskazywać konkretne zakresy, a nie usuwać stare źródło. Wersja opakowania może się zmienić bez materialnej zmiany architektury.

## Jawna retencja przy limicie 30

Nowe wydanie jest skompaktowanym kompendium do orientacji i projektowania, a nie mechanicznym zlepieniem 40 starych plików. `24_SOURCE_RECORD_INDEX.json` zachowuje wszystkie 211 source_id, archive_id, virtual_path, historyczny nośnik i payload hash/rozmiar. Pole payload_location jest jawnie EXTERNAL_ORIGINAL_R9_ARCHIVE. Samego indeksu nie wolno raportować jako roundtrip payloadów.

Oryginalne archiwum R9 ma SHA-256 `e9fa2ff9e04c8841cb23e616ea9a9238b4ed0f56ffded0d3a621f7db90e07d5d`. Pełny wcześniejszy pakiet badawczy ma SHA-256 `f082b5acace4ffd3665a65fdcdb0b053701f44f4639e4554b9fb85c39a2a2348`. Są źródłami reprodukcji, nie wymaganymi dodatkowymi plikami do codziennego kontekstu RAG 1.5. Gdy zadanie wymaga historycznego payloadu, odzyskaj pełne bajty i sprawdź hash; przy ich braku oznacz PARTIAL_READ. Nie próbuj odtwarzać bajtów z hasha.

## Dokumenty rozwojowe wymagające ostrożności

Plan federacji błędnie opisywał dwa dostępne repozytoria jako niedostępne. Podsumowanie mieszało gotowe wyniki i projekt, utożsamiało swarm z Docker Swarm oraz bieżącą sesję SaaS z API. Wymagania tych dokumentów pozostają wartościowe, ale deklaracji wykonanych patchy czy niezależnych testów nie przejęto jako własnych dowodów.

Rekonstrukcja A02, dawne ledgery i karty K00–K13 zachowują swoją tożsamość. Nie odtwarzaj zamkniętych efektów ani nie kasuj lokalnych kandydatów z powodu nowszego merge. Brak dostępu do jednej historycznej kopii nie dowodzi jej globalnego nieistnienia.

## Źródła i dalszy odczyt

- `Prior R9_RECORD_AND_FILE_AUDIT.json`
- `Prior DOKUMENTY_ROZWOJOWE_I_SPRZECZNOSCI.md`
- `Original R9 archive at registered SHA-256`
- `DonkeyJJLove/ai_platform:LION/architecture/v1_4/history_and_supersession.md`
