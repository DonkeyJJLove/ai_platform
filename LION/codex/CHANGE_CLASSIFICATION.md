# Klasyfikacja zmian

Klasyfikuj region semantyczny, nie samą nazwę pliku. Jeden plik może zawierać live pin i historyczny fixture.

| Klasa | Znaczenie | Currentness | Walidacja | Kolejność | Zależne klasy | Zakaz skrótu |
|---|---|---|---|---|---|---|
| PRODUCTION_NON_CARRIER | źródło produkcyjne | truth i możliwy scan | testy zachowania i inwentarz | przed scan/truth | TEST, SCAN_PIN_CARRIER, TRUTH_CARRIER | pin bez obserwacji |
| SECURITY_SOURCE | przyczyna zabezpieczenia | truth i możliwy scan | regresja i skaner | przed refreeze | TEST, WORKFLOW, SCAN_PIN_CARRIER | wyciszenie zapytania |
| TEST | test lub fixture | truth; nie produkcyjny selector | przypadki dodatnie i ujemne | po ustaleniu kontraktu, przed truth | TRUTH_CARRIER | zmiana assertion dla pozornego PASS |
| WORKFLOW | procedura CI | truth i scan | poprawność workflow, exact-head run | przed scan/truth | SCAN_PIN_CARRIER, TRUTH_CARRIER | wyłączenie wymaganej kontroli |
| TRUTH_CARRIER | proven live subject binding | zgodność z domeną subject | recompute i dwa carriers | ostatni zapis epoki | CURRENTNESS_CARRIER | własny przyszły SHA |
| CURRENTNESS_CARRIER | bieżące powiązanie obserwacji | zależne od konkretnej tożsamości | sprawdź domenę i źródło | po wszystkich zależnościach | GENERATED_EVIDENCE | dziedziczenie starego PASS |
| SCAN_PIN_CARRIER | bieżący pin inwentarza | zależny od produkcyjnego source set | recompute, taxonomy i testy kaskady | po źródłach, przed truth | TRUTH_CARRIER | ślepa zamiana wszystkich hashy |
| RAG_CONTEXT | wersjonowany kontener wiedzy | materialny dla truth; archiwalny | manifest, bytes, routing | tylko jawna nowa epoka, przed truth | DOCUMENTATION, TRUTH_CARRIER | edycja historycznego payloadu |
| DOCUMENTATION | opis lub instrukcje | może zmieniać truth | linki, zakres twierdzeń, review | przed truth | TRUTH_CARRIER | uznanie dokumentacji za runtime proof |
| GENERATED_EVIDENCE | wynik właściwego generatora | związany z input identity | generator i readback | po inputach | CURRENTNESS_CARRIER | ręczne malowanie statusu CURRENT |
| HISTORICAL_EVIDENCE | dowód dawnej epoki | historyczny, nie live pin | zachowanie pochodzenia | supersede, nie rewrite | DOCUMENTATION | refreeze fixture |
| SCHEMA | kontrakt danych | truth; możliwa zmiana semantyki | meta-schema i negatywne instancje | przed konsumentami/carriers | TEST, GENERATED_EVIDENCE | dowolne object jako pozorna walidacja |
| RUNTIME_CONFIGURATION | konfiguracja wykonania | runtime identity i możliwy truth | zakres zgody, test i obserwacja | po admission, przed readback | GENERATED_EVIDENCE | wdrożenie z samego merge |
| AUTHORITY_POLICY | reguła uprawnień | scope i approval evidence | osobna zgoda i review | przed dozwolonym efektem | RUNTIME_CONFIGURATION | grant z opisu możliwości |
| UNKNOWN | nieustalone znaczenie | nieznany | dalsza analiza | bez automatycznej edycji | UNKNOWN | zgadywanie klasy |
