# LION RAG 1.5 — VALIDATION AND WINDOWS UTF8

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Nowszy wynik operatora

W dostarczonym result.json 63 testy unittest oraz 23 routing probes przechodzą. Przechodzi także offline provider substitution i 37 zapisanych probes R9. Jednak clean_process_orientation kończy się FAIL: child uruchomiony z `-I` próbuje wydrukować polski JSON przez cp1252 i zgłasza UnicodeEncodeError. Cały artifact_tests_result jest więc FAIL, nie PASS.

To błąd granicy procesu/strumienia, a nie dowód wadliwej semantyki wszystkich kontraktów. Interaktywny terminal może mieć inne kodowanie niż stdout przechwyconego child process. `PYTHONIOENCODING` nie jest wystarczającą poprawką dla interpretera uruchomionego w trybie izolowanym `-I`.

## Poprawka

Nowe narzędzie repozytoryjne `tools/lion_rag15.py` ustawia UTF-8 na stdout/stderr przez reconfigure przed emisją polskiego tekstu. Wyniki JSON mają określone kodowanie, a pliki zapisywane są w UTF-8. Test subprocess wymusza wcześniej cp1252 i strict, aby rzeczywiście sprawdzić naprawianą granicę; osobny test uruchamia świeży interpreter `-I`.

Do wcześniejszego instrumentu przygotowano odtwarzalny patch: reconfigure strumieni w CLI, `-X utf8` w wywołaniu potomnym oraz jawne `encoding='utf-8'` przy dekodowaniu jego wyjścia. Poprawka nie osłabia żadnej asercji testów semantycznych. Log operatora pozostaje niezmienionym dowodem wcześniejszego błędu.

## Co nowa walidacja może potwierdzić

Weryfikacja wydania sprawdza dokładny zestaw 30 plików, sumy, wersję, manifest bez samohashowania, unikalność 211 referencji historycznych, 47 ownerów i dziesięciu repozytoriów, lokalne linki Markdown oraz zgodność z wybranym wydaniem. Próby routingu są jawnie deterministyczne. Przypadki negatywne obejmują uszkodzone bytes, dodatkowy plik, błędne źródło, pusty query i nieistniejący source_id.

Wyniki nowego przebiegu są w repozytoryjnym raporcie walidacji wydania. Nie są testem rzeczywistego Windows, jeśli uruchomiono jedynie symulację strumienia cp1252 na Linux; nie są też testem modelu SaaS lub workloadu Docker. Takie testy pozostają własnymi misjami odbiorczymi.

## Źródła i dalszy odczyt

- `User result.json@sha256:9cb69219e518637487342d23cf4431019d519a7f31e6f829552afab470bb6bc8`
- `User Wklejony Markdown(1).md`
- `Prior tools/query_rag.py`
- `Prior tools/run_validation.py`
