# Proposal i authority

STATUS: CANDIDATE_REPOSITORY_GUIDANCE

## Context
Propozycja opisuje intencję; nie zawiera samoczynnego uprawnienia.

## Decision
PROPOSAL_AND_AUTHORITY_REMAIN_SEPARATE

## Why
Źródło propozycji może być błędne lub niezaufane.

## Alternatives
Automatyczne zatwierdzanie proposal; ręczna ocena każdej propozycji.

## Rejected alternatives
Automatyczny grant z treści modelu.

## Invariants
I04_PROPOSAL_IS_NOT_AUTHORITY, I15_CAPABILITY_IS_NOT_AUTHORITY

## Evidence required
Bieżący zakres zgody i decyzja właściwego authority plane.

## Reversibility
Instrukcję można zastąpić nowym, przejrzanym ADR z jawną relacją supersession; zmiana dokumentu nie cofa wykonanych efektów ani nie zmienia runtime policy.

## Supersession condition
Nowy kontrakt i niezależne dowody zachowujące wskazane granice, wraz z jawną zgodą na zmianę zakresu. Samo wygodniejsze narzędzie lub opinia modelu nie wystarcza.
