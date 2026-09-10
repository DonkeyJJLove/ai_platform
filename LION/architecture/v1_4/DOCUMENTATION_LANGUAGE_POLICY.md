# Polityka języka dokumentacji LION v1.4

## Cel

Bieżąca dokumentacja przeznaczona dla człowieka ma używać **języka polskiego jako języka podstawowego**, przy zachowaniu literalnych nazw kontraktów, typów, klas, pól schematów, tokenów LPCL/LCMS, identyfikatorów stanów, nazw plików, ścieżek, komend, commitów, hashy i innych elementów technicznych, których tłumaczenie zmieniłoby znaczenie lub możliwość reprodukcji.

Ta polityka dotyczy dokumentacji operatorskiej, architektonicznej, nawigacyjnej i raportowej. Nie zmienia wire formatów, kodu, JSON/YAML keys, API, schematów, nazw symboli ani protokołów wykonawczych.

## Reguła translacji

```text
HUMAN_FACING_PROSE          -> POLISH_PRIMARY
TECHNICAL_IDENTIFIER        -> PRESERVE_LITERAL
CODE / COMMAND / PATH       -> PRESERVE_LITERAL
JSON_YAML_SCHEMA_KEY        -> PRESERVE_LITERAL
LPCL_LCMS_TOKEN             -> PRESERVE_LITERAL
COMMIT_TREE_HASH_DIGEST     -> PRESERVE_LITERAL
HISTORICAL_EXACT_EVIDENCE   -> PRESERVE_IDENTITY_AND_MEANING
```

Dopuszczalne jest tłumaczenie opisów wokół historycznych dowodów, ale nie wolno zmieniać wartości dowodowych, identyfikatorów ani przedstawiać dawnego `CURRENT` jako bieżącego tylko dlatego, że dokument został przetłumaczony.

## Currentness

Tłumaczenie jest zmianą dokumentacji, nie zmianą stanu systemu. Nie może samo promować `STALE`, `CANDIDATE`, `TARGET`, `UNKNOWN` lub historycznego zapisu do `CURRENT`, `INTEGRATED`, `OBSERVED` ani `PRODUCTION`.

Obowiązuje:

```text
NO_VALID_CURRENTNESS_BASIS -> NOT_CURRENT
MATERIAL_BASELINE_DRIFT    -> CURRENT_TO_STALE
HISTORY_CHANGED_BY_REALITY -> SUPERSEDE_DO_NOT_REWRITE
```

Każdy dokument bieżącego stanu, który wiąże exact Git identity, musi wskazywać czy identyfikator odnosi się do: bieżącego `master`, bazowego stanu kandydata, historycznego eksperymentu czy konkretnego runtime evidence epoch.

## Ochrona provenance

Nie tłumaczy się w miejscu materiałów zachowanych jako literalny, bajtowo identyfikowany payload źródłowy. Dla takich materiałów należy dodać polską warstwę objaśniającą albo osobny dokument pochodny, zachowując source identity, hash i lineage.

Nie wolno przepisywać historycznych falsyfikacji tak, aby wyglądały jak dzisiejsze twierdzenia. Późniejsza naprawa powoduje supersession, nie usunięcie historii.

## Styl

Preferowany jest polski opis techniczny z zachowaniem uzasadnionych terminów domenowych, np. `authority`, `currentness`, `runtime admission`, `effect`, `receipt`, `observer`, `reconciler`, `fail-closed`, jeżeli są częścią ustalonego słownika architektury. Przy pierwszym użyciu można dodać polskie objaśnienie, ale nie należy mechanicznie tłumaczyć nazw kontraktów.

## Zakres tej epoki

Epoka `LION-DOC-R128-2026-09-10-R1` koncentruje się na bieżących dokumentach LION v1.4 i VKT-R3. Repozytoryjne źródła maszynowe i historyczne payloady pozostają poza translacją, chyba że późniejszy, jawny etap utworzy bezpieczną polską warstwę prezentacyjną.

## Authority

`DOCUMENTATION_LANGUAGE_POLICY` ma `AUTHORITY_EFFECT=NONE`. Polityka języka nie jest źródłem uprawnień do runtime, hosta, merge, deploy, produkcji ani modyfikacji innych repozytoriów.
