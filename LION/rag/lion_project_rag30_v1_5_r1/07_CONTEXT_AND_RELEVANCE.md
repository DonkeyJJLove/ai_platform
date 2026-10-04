# LION RAG 1.5 — CONTEXT AND RELEVANCE

Release: `lion-rag30-v1.5-r1`. Klasa: `VERSIONED_PROJECT_KNOWLEDGE`. Zakres dowodu: źródła i badania opisane poniżej; nie live runtime.

## Kontekst wspólny i perspektywy lokalne

RagContextEnvelope odpowiada na pytanie, jakie źródła rzeczywiście weszły do konkretnej pracy. RelevanceGraph reprezentuje relewantne obiekty i relacje; RelevanceProjection wybiera widok dla określonego konsumenta. Wspólny świat nie wymaga identycznej listy tokenów u wszystkich providerów. Wymaga natomiast możliwości ustalenia, co zostało ujawnione, na jakiej podstawie i co pominięto.

W doborze kontekstu podobieństwo słów jest sygnałem pomocniczym. Zależność kontraktowa, ryzyko skutku, negacja, wyjątek, obowiązujący owner i aktualność mogą być ważniejsze niż similarity. Zachowaj warunek i ograniczenie razem z twierdzeniem; odcięcie „nie” lub zakresu wersji tworzy inne twierdzenie.

## Minimalny łańcuch walidacji kompozycji

Sprawdź zgodność envelope–intent, intent–query, query–context, context–scaffold, scaffold–graph, graph–projection i binding–invocation. Nie ograniczaj się do wywołania validate() każdego obiektu osobno. Wcześniejszy test wykazał poprawnie sealed QueryPlan wskazujący niewłaściwy digest rodzica: spójność własnych bajtów nie gwarantuje poprawnej relacji do innego obiektu.

Sprawdź, czy źródło istnieje, czy jego hash odpowiada bajtom, czy obserwacja mieści się przed cutoffem i czy provenance wskazuje commit właściwego repozytorium. Sprawdź, czy projekcja nie ujawnia nieistniejącego węzła, nie zmienia konsumenta i nie poszerza zbioru wymaganych capabilities. Hashy nie traktuj jako poświadczeń autora lub prawdziwości.

## Aktualizacja i budżet

Nowy dowód po cutoffie tworzy nowe wejście lub jawnie związaną rewizję; nie jest dopisywany do starego envelope z zachowaniem starego digestu. Wartości budżetu oznacz jako odczytane, zmierzone lub projektowane. Brak pomiaru kosztu nie jest kosztem równym zero. Cache i kompresja muszą zachować reguły unieważnienia oraz odnośnik do niepominiętego źródła.

Luka kompozycji powinna zostać naprawiona u istniejącego composition root, po prześledzeniu aktualnych konsumentów. Dostarczony instrument badawczy jest kontrprzykładem i pomocą testową, nie uprawnieniem do zastąpienia całej produkcyjnej ścieżki.

## Źródła i dalszy odczyt

- `DonkeyJJLove/ai_platform:cyber_lion/contracts/query_plan.py`
- `DonkeyJJLove/ai_platform:cyber_lion/contracts/rag_context_envelope.py`
- `Prior tools/native_bridge.py and tests/test_semantic_package.py`
