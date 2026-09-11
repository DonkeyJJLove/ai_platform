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


## Uzgodnienie LPCL 1.1 — integracja PR #309

Opis LPCL 1.0 powyżej zachowuje zakres historyczny i zgodność wsteczną.
Jawnie wersjonowane `RUN` z `LPCL_VERSION=1.1` mają osobny parser
`cyber_lion/process_language/canonical_run.py` oraz punkt interpretacji
`cyber_lion/process_language/interpretation.py`. Niewersjonowane `RUN` pozostają
danymi historycznymi. Parser wymaga pojedynczego końcowego `END`; znacząca treść
po nim jest błędem, a nie pomijanym fragmentem.

Gramatyka: `cyber_lion/process_language/lpcl_run_1_1.ebnf`.
Model ról: `cyber_lion/process_language/fleet_mission.py`; klasy LOGICAL, LOCAL,
HYBRID opisują reprezentację ról, nie uruchomione drony ani uprawnienia.
Interpretacja zwraca kandydatów ProcessIR/FleetMissionIR bez efektów. Nie zastępuje
Action/PDP/RuntimeAdmission. Projekcja `process_orchestration.py` wiąże istniejące
warstwy i nie dodaje nowej warstwy nadrzędnej.

Konstytucja, model floty i zamrożenie projektu w plikach `LPCL_LANGUAGE_CONSTITUTION.md`,
`LPCL_FLEET_MISSION_MODEL.md`, `LPCL_V1_1_DESIGN_FREEZE.md` dokumentują zakres kandydata
#309; ich stare HEAD/statusy nie są dowodem bieżącego master ani runtime.
Integrację i aktualność potwierdzają dokładne Git/CI, a nie etykieta w dokumencie.
