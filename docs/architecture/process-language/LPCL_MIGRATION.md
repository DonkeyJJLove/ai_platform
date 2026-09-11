# LPCL — kandydat migracji

LPCL v1 został wprowadzony jako addytywny candidate. Istniejące `MissionSpec`, `EvolutionaryEpoch`, `ActionSpec`, `ActionProposal`, PDP, `RuntimeAdmission` oraz kontrakty effect/reconciliation pozostają kanoniczne w swoich domenach.

## Historyczny RUN

```text
historical RUN text
→ LegacyRunAdapter
→ classification
→ semantic candidate only when non-ambiguous
→ canonical ProcessIR validation
```

Klasyfikacje:

- `LOSSLESS_TRANSLATION`
- `LOSSY_BUT_SAFE`
- `AMBIGUOUS`
- `UNREPRESENTABLE`

Bieżący adapter tej lineage celowo klasyfikuje proceduralne `MODE=...THEN...`, numerowane semantyki PHASE oraz niejednoznaczne pola authority jako `AMBIGUOUS`. Nigdy nie wykonuje historycznego tekstu.

## Federacja

Centralny repository registry jest truth-subject-derived. Kandydat zapisuje split ownership jawnie, ale nie przepisuje ręcznie generowanego currentness carrier. Regeneracja/reconciliation tego carrier jest krokiem późniejszym względem poprawnego LPCL contract CI.

## Istniejące state machines

Nie ma zgody na bulk migration. `EvolutionaryEpochEngine` oraz inne domenowe state machines pozostają bez zmian, dopóki equivalence z generic `TransitionSpec` semantics nie zostanie indywidualnie udowodniona.

## Granica translacji

`LOSSLESS_TRANSLATION` jest klasyfikacją semantycznej migracji formatu procesu, a nie instrukcją językowej translacji nazw tokenów LPCL. Tokeny, identyfikatory i wire semantics pozostają literalne niezależnie od tego, że prose dokumentacji jest po polsku.


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
