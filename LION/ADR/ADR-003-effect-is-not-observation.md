# Raport efektu i obserwacja

STATUS: CANDIDATE_REPOSITORY_GUIDANCE

## Context
Executor może zwrócić receipt bez osiągnięcia postcondition.

## Decision
EFFECT_REPORT_AND_INDEPENDENT_OBSERVATION_REMAIN_SEPARATE

## Why
Niezależny odczyt odróżnia deklarację od rzeczywistego skutku.

## Alternatives
Zaufanie exit code; odczyt celu.

## Rejected alternatives
Receipt lub exit 0 jako reconciliation.

## Invariants
I07_EFFECT_RECEIPT_IS_NOT_OBSERVATION, I08_OBSERVATION_IS_NOT_RECONCILIATION, I23_EFFECT_SUCCESS_REQUIRES_POSTCONDITION_EVIDENCE

## Evidence required
Odczyt postcondition, provenance obserwatora i reconciliation.

## Reversibility
Instrukcję można zastąpić nowym, przejrzanym ADR z jawną relacją supersession; zmiana dokumentu nie cofa wykonanych efektów ani nie zmienia runtime policy.

## Supersession condition
Nowy kontrakt i niezależne dowody zachowujące wskazane granice, wraz z jawną zgodą na zmianę zakresu. Samo wygodniejsze narzędzie lub opinia modelu nie wystarcza.
