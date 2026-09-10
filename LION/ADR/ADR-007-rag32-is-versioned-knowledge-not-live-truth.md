# Wersjonowana wiedza RAG32

STATUS: CANDIDATE_REPOSITORY_GUIDANCE

## Context
RAG zawiera kompletne źródła dawnych epok i kandydatów.

## Decision
RAG32_PRESERVES_KNOWLEDGE_AND_LINEAGE_WITHOUT_REPLACING_LIVE_REACQUISITION

## Why
Spójny hash pakietu nie dowodzi obecnego stanu systemu.

## Alternatives
Live-only bez historii; archiwum plus reacquisition.

## Rejected alternatives
Archiwalny CURRENT lub prompt jako live grant.

## Invariants
I11_HISTORICAL_CURRENT_IS_NOT_LIVE_CURRENT, I15_CAPABILITY_IS_NOT_AUTHORITY

## Evidence required
Profile/release/source hash i oddzielny live evidence.

## Reversibility
Instrukcję można zastąpić nowym, przejrzanym ADR z jawną relacją supersession; zmiana dokumentu nie cofa wykonanych efektów ani nie zmienia runtime policy.

## Supersession condition
Nowy kontrakt i niezależne dowody zachowujące wskazane granice, wraz z jawną zgodą na zmianę zakresu. Samo wygodniejsze narzędzie lub opinia modelu nie wystarcza.
