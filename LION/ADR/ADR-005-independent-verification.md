# Niezależna weryfikacja

STATUS: CANDIDATE_REPOSITORY_GUIDANCE

## Context
Builder zna intencję i może powielać własne założenia.

## Decision
BUILD_AND_INDEPENDENT_VERIFICATION_ARE_DISTINCT_ROLES

## Why
Oddzielne pochodzenie oceny daje szansę falsyfikacji.

## Alternatives
Self-review jawnie oznaczony; osobny verifier.

## Rejected alternatives
Zmiana nazwy buildera na verifier bez niezależności.

## Invariants
I14_BUILDER_IS_NOT_INDEPENDENT_VERIFIER

## Evidence required
Tożsamości, zakresy i niezależne artefakty weryfikacji.

## Reversibility
Instrukcję można zastąpić nowym, przejrzanym ADR z jawną relacją supersession; zmiana dokumentu nie cofa wykonanych efektów ani nie zmienia runtime policy.

## Supersession condition
Nowy kontrakt i niezależne dowody zachowujące wskazane granice, wraz z jawną zgodą na zmianę zakresu. Samo wygodniejsze narzędzie lub opinia modelu nie wystarcza.
