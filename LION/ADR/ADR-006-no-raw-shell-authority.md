# Typowane ograniczone efekty

STATUS: CANDIDATE_REPOSITORY_GUIDANCE

## Context
LocalConsole i autonomous process są granicami wykonania.

## Decision
LOCAL_CONSOLE_AND_AUTONOMOUS_PROCESSES_USE_TYPED_BOUNDED_ACTIONS

## Why
Dowolny shell zaciera scope, target, admission i obserwowalność.

## Alternatives
Typed actions; nieograniczony shell jako runtime interface.

## Rejected alternatives
Raw shell authority i interpreter obchodzący odmowę.

## Invariants
I01_CAPABILITY_GROWTH_DOES_NOT_IMPLY_AUTHORITY_GROWTH, I15_CAPABILITY_IS_NOT_AUTHORITY, I24_RETRY_OF_NON_IDEMPOTENT_EFFECT_REQUIRES_RECONCILIATION

## Evidence required
Action contract, admission i postcondition. Operatorskie polecenia z runbooka nadal wymagają bieżącej zgody i egzekwowanej polityki.

## Reversibility
Instrukcję można zastąpić nowym, przejrzanym ADR z jawną relacją supersession; zmiana dokumentu nie cofa wykonanych efektów ani nie zmienia runtime policy.

## Supersession condition
Nowy kontrakt i niezależne dowody zachowujące wskazane granice, wraz z jawną zgodą na zmianę zakresu. Samo wygodniejsze narzędzie lub opinia modelu nie wystarcza.
