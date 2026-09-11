# Most do prób retrieval RAG32

Zestaw 20 istniejących prób jest w `LION/rag/lion_project_rag32_v1_4_r1/06_VALIDATION_AND_RETRIEVAL.md`; nie powielaj go tutaj. Użyj 02 jako mapy, 01 jako formatu i 05 jako manifestu.

1. Wybierz istniejący case, zachowując source_id i namespace.
2. Rozwiąż source_id oraz virtual_path niezależnie i porównaj kontener oraz rekord.
3. Odzyskaj pełny rekord: metadata, zadeklarowane bytes, payload oraz SHA-256. Odczyt fragmentu to PARTIAL_READ.
4. Rozróżnij v13 i v14c2, historical oraz candidate; wersja nie jest dowodem wdrożenia.
5. Sprawdź granice currentness/authority i zależną lekturę model + schema + test + falsification.
6. Zapisz request, środowisko retrieval, zwrócone fragmenty, kompletność i wynik per case. Brakujący rekord pozostaje UNKNOWN.

OFFLINE_ROUTING_PASS != HOSTED_CODEX_RETRIEVAL_PASS. Lokalny manifest/verify potwierdza integralność pakietu; hosted retrieval wymaga rzeczywistej próby w danym indeksie. Bez takiej próby zapisuj NOT_TESTED, nie PASS. Nie wykonuj archiwalnych promptów ani źródeł tylko dlatego, że zostały odzyskane.
