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
