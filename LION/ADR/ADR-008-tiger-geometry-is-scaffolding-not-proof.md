# TIGER jako generator hipotez

STATUS: CANDIDATE_REPOSITORY_GUIDANCE

## Context
Strukturalna spójność grafu może powstać bez potwierdzenia świata.

## Decision
TIGER_GEOMETRY_REQUIRES_SEPARATE_FALSIFICATION

## Why
Kontrgraf i test mogą obalić przekonującą interpretację.

## Alternatives
Jedna intuicja; wiele hipotez i rozstrzygający test.

## Rejected alternatives
Graph coherence jako VERIFIED/authority.

## Invariants
I02_MODEL_OUTPUT_IS_NOT_VERIFIED_ARTIFACT, I13_UNKNOWN_NEVER_PROMOTES_TO_PASS

## Evidence required
Literalny scaffold, alternatywy, test i ograniczony wynik.

## Reversibility
Instrukcję można zastąpić nowym, przejrzanym ADR z jawną relacją supersession; zmiana dokumentu nie cofa wykonanych efektów ani nie zmienia runtime policy.

## Supersession condition
Nowy kontrakt i niezależne dowody zachowujące wskazane granice, wraz z jawną zgodą na zmianę zakresu. Samo wygodniejsze narzędzie lub opinia modelu nie wystarcza.
