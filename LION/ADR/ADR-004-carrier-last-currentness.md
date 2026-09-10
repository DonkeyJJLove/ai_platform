# Carrier-last currentness

STATUS: CANDIDATE_REPOSITORY_GUIDANCE

## Context
Source i dokumentacja zmieniają subject wiązany przez carriers.

## Decision
CURRENTNESS_CARRIERS_REBIND_ONLY_AFTER_RELEVANT_NON_CARRIER_SOURCE_STABILIZES

## Why
Wcześniejszy hash przestaje opisywać końcowe drzewo.

## Alternatives
Rebind po każdym kroku; final rebind po stabilizacji.

## Rejected alternatives
Final carrier przed oczekującym source.

## Invariants
I16_NON_CARRIER_SOURCE_STABILIZES_BEFORE_CARRIER_REBIND, I17_SECURITY_SOURCE_STABILIZES_BEFORE_SCAN_REFREEZE, I18_CARRIER_REBIND_IS_LAST_SEMANTIC_WRITE_OF_CURRENTNESS_EPOCH, I19_NO_SELF_REFERENTIAL_CURRENTNESS

## Evidence required
Dokładny DAG, źródła, domena digest i ostatni carrier-only commit.

## Reversibility
Instrukcję można zastąpić nowym, przejrzanym ADR z jawną relacją supersession; zmiana dokumentu nie cofa wykonanych efektów ani nie zmienia runtime policy.

## Supersession condition
Nowy kontrakt i niezależne dowody zachowujące wskazane granice, wraz z jawną zgodą na zmianę zakresu. Samo wygodniejsze narzędzie lub opinia modelu nie wystarcza.
