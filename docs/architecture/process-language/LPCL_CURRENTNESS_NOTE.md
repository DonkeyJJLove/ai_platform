# LPCL — uwaga o currentness kandydata

Historyczny candidate code został zbudowany z default-branch base `67a4f8243aa6805e47035e572bd458f73fd0b358` / tree `4f6fbc481c8df8f7e1fd75f04188207a1c6fbcf5`.

Istniejąca projekcja R20 `LION/architecture/v1_4/current_state.json` sama była związana z wcześniejszym baseline'em, dlatego nie może być używana jako dowód, że ten kandydat LPCL jest zintegrowany lub current na dzisiejszym `master`.

Candidate branch state, PR CI, późniejszy integration readback oraz bieżący live `master` są odrębnymi currentness subjects.

W epoki `LION-DOC-R128-2026-09-10-R1` repozytorium zostało odtworzone przed utworzeniem kandydata dokumentacyjnego jako `master` HEAD `5e40338511fe2a5f0a891c823b03f9855d6ad1e8` / TREE `306b8cf245299517278ab0959a7aca79f66e5343`. Historycznego baseline'u LPCL nie przepisuje się na tę wartość; zachowuje on lineage swojego evidence epoch.


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
