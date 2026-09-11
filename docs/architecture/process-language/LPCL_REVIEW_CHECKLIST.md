# LPCL — checklista niezależnego review

Reviewer powinien odrzucić kandydata, jeśli odpowiedź na którekolwiek z poniższych pytań brzmi „tak”:

- Czy LPCL może grantować lub mintować authority?
- Czy LPCL może oceniać lub zastąpić canonical PDP?
- Czy LPCL może konstruować `RuntimeAdmission`?
- Czy LPCL może wybierać lub wykonywać `EffectProvider`?
- Czy historyczny `RUN` może dotrzeć do wykonania bez canonicalization?
- Czy `UNKNOWN` może zostać wymuszone jako `PASS`?
- Czy `PASS` może implikować `CURRENT`, `AUTHORIZED`, `OBSERVED` albo `RECONCILED`?
- Czy `CONTINUE` może pomijać dependencies, ignorować currentness albo rozszerzać scope?
- Czy non-idempotent retry może nastąpić bez reconciliation-first semantics?
- Czy consequential `PASS` może pominąć evidence dla admission/effect/observation/reconciliation/currentness?
- Czy samo istnienie LPCL wymaga 16. warstwy architektury?
- Czy LPCL zastępuje `EvolutionaryEpochEngine`, zamiast współistnieć z nim?

Kandydat nadaje się do integration review dopiero wtedy, gdy wszystkie odpowiedzi brzmią „nie” i exact-head CI jest zakończone sukcesem.

Ta checklista nie stanowi sama w sobie integration authority.


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
