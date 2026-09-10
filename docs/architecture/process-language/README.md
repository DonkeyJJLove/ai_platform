# Architektura języka procesu

Zacznij od:

1. `LPCL_V1_CANDIDATE.md` — model semantyczny i architektoniczny.
2. `LPCL_NEGATIVE_RULES.md` — klasy falsyfikacji fail-closed.
3. `LPCL_MIGRATION.md` — addytywna migracja i granica historycznych `RUN`.

Machine-readable candidate decisions znajdują się pod `LION/architecture/v1_4/process_language_*_candidate.json`.

Implementacja znajduje się w:

- `cyber_lion/contracts/process_ir.py`
- `cyber_lion/contracts/process_action.py`
- `cyber_lion/enterprise/process_semantics.py`
- `cyber_lion/process_language/`

Process layer jest non-effectful i nie zastępuje ani nie omija łańcucha Action/PDP/RuntimeAdmission.

## Currentness

Dokumenty tego katalogu mają zachowywać lineage kandydatów LPCL, ale ich historyczne etykiety statusu nie mogą być automatycznie traktowane jako bieżący stan `master`. Bieżącą integrację należy odtwarzać z exact Git/code/test evidence.

Zasady językowe dla human-facing prose określa `LION/architecture/v1_4/DOCUMENTATION_LANGUAGE_POLICY.md`.
