# LION — wersjonowana wiedza projektu

## RAG 1.5: gotowy zestaw 30 plików

[**Wejście do RAG 1.5**](lion_project_rag30_v1_5_r1/00_START_HERE.md) prowadzi do jednego wydania `lion-rag30-v1.5-r1`. Katalog zawiera dokładnie 30 plików: 24 pliki Markdown i 6 JSON. Jest gotowy jako wiedza do umieszczenia w projekcie i projektowania rozwoju, nie jako deklaracja zakończonego deploymentu całego LION. Limit 30 pochodzi od operatora.

[Instrukcja dla modelu](lion_project_rag30_v1_5_r1/01_MODEL_INSTRUCTIONS.md), [metaprompt](lion_project_rag30_v1_5_r1/22_METAPROMPT.md) i [gotowy prompt rozwoju federacji](lion_project_rag30_v1_5_r1/23_EVOLUTION_EXECUTION_PROMPT.md) są częścią tych 30 plików. Nie trzeba generować kolejnego promptu: plik 23 jest gotową instancją reguł metapromptu 22. Uruchomienie pliku 23 ma wytworzyć architekturę, konkretne zmiany źródeł i skończony program misji do realizacji przez istniejący ai_platform. Przyszłe misje uruchamia operator.

## Użycie

Rozpakuj wyeksportowany ZIP i dodaj jego 30 plików do projektu jako wybrane wydanie wiedzy. Nie dodawaj równocześnie starego układu 34+6 jako drugiego aktywnego wydania. Zachowaj stare archiwa do audytu historii. Treść pliku 01 dołącz jako instrukcję startową modelu lub nowego wątku; następnie uruchom pełną treść 23. Sam odczyt promptów w retrieval nie jest ich aktywacją.

RAG kieruje do pełnej dokumentacji ai_platform, aktualnych ownerów i źródeł peerów. Nie zastępuje ich streszczeniem ani nie przyznaje authority. Historyczny indeks 24 zachowuje 211 referencji źródłowych, ale nie pełne payloady R9. Oryginalne bajty pozostają w archiwach o hashach podanych w 18 i 27; brak odzyskanych bajtów nie staje się pełnym odczytem.

## Sprawdzenie i eksport

Narzędzie wymaga Python 3.9+ i tylko standardowej biblioteki. Testowano je na wersji wskazanej w raporcie. Z katalogu głównego repozytorium:

```bash
python -B tools/lion_rag15.py verify
python -B -m unittest discover -s tests -p test_lion_rag15.py -v
python -B tools/lion_rag15.py query "Wyjaśnij współpracę SaaS i modelu lokalnego przy zadaniu swarm"
python -B tools/lion_rag15.py pack LION_RAG_1_5_30_FILES.zip
```

ZIP jest płaski: dokładnie 30 zwykłych plików, bez podkatalogów, narzędzi, logów i dodatkowych sidecarów. `--root` przed podkomendą pozwala wskazać rozpakowany katalog. To narzędzie integralności i jawnego routingu tematycznego, nie nowy silnik inferencji ani alternatywny runtime LION.

[Raport walidacji](validation/RAG15_RELEASE_VALIDATION.json) obejmuje 30 testów unittest, w tym 18 przypadków routingu, wszystkie 211 odnośników, deterministyczny ZIP oraz świeży proces i wymuszony strumień cp1252. Nie jest to natywny test Windows ani test modelu. [Raport poprawki poprzedniego instrumentu](validation/RAG15_UTF8_FIX_RESULT.json) zachowuje reprodukcję błędu i wyniki rewalidacji 63 testów oraz 23 probes. [Patch UTF-8](validation/RAG15_LEGACY_UTF8.patch) dotyczy dokładnej kopii poprzedniego pakietu badawczego, nie automatycznej modyfikacji produkcyjnych modułów tego repozytorium.

## Integracja wydania a stan systemu

Canonical owner pozostaje w `RAG_BOOTSTRAP.json`. Publikacja tego katalogu na gałęzi/PR nie zmienia samoczynnie `preferred_release` master ani kontekstu działającego modelu. Wybór RAG 1.5 przez operatora umożliwia jego użycie w nowym wątku; promocja bootstrapu i wiring kontekstu wymagają oddzielnego źródłowo uzasadnionego przyrostu. Nie zmieniono historycznych kontraktów ani testów oczekujących R9 wyłącznie po to, by nazwać pakiet 1.5.

Istotna wskazówka do pierwszych misji: `lion_context_provider.py` może nadal emitować stałe v1.4/R10 i tożsamości modelu. Pełny konsument i jego zależne testy mają być sprawdzone przed poprawką. Plik 23 obejmuje tę kwestię, kompozycję Semantic Cloud, The Bean Factory, rzeczywistych providerów, funkcje wszystkich peerów i cztery późniejsze materialne odbiory.
