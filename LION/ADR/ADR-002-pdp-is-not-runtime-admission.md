# PDP i runtime admission

STATUS: CANDIDATE_REPOSITORY_GUIDANCE

## Context
Polityka może dopuścić działanie przed zmianą warunków runtime.

## Decision
POLICY_DECISION_AND_RUNTIME_ADMISSION_REMAIN_SEPARATE

## Why
Freshness, tożsamość celu i ograniczenia wykonania wymagają sprawdzenia przy efekcie.

## Alternatives
Jeden wspólny etap; oddzielny admission.

## Rejected alternatives
PDP_ALLOW jako dowód wykonania.

## Invariants
I05_PDP_ALLOW_IS_NOT_RUNTIME_ADMISSION, I06_RUNTIME_ADMISSION_IS_NOT_EFFECT

## Evidence required
Typed decision, runtime binding i aktualne admission.

## Reversibility
Instrukcję można zastąpić nowym, przejrzanym ADR z jawną relacją supersession; zmiana dokumentu nie cofa wykonanych efektów ani nie zmienia runtime policy.

## Supersession condition
Nowy kontrakt i niezależne dowody zachowujące wskazane granice, wraz z jawną zgodą na zmianę zakresu. Samo wygodniejsze narzędzie lub opinia modelu nie wystarcza.
