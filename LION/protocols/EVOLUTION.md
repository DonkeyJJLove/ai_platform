# LION — protokół ewolucji

LION rozwija architekturę przez jawne delty, a nie przez gromadzenie niepowiązanego kodu.

```text
TARGET
→ OBSERVE IMPLEMENTATION
→ COMPUTE GAP
→ CREATE MISSION
→ ASSIGN DRONE/SWARM
→ BUILD
→ VERIFY
→ INTEGRATE
→ OBSERVE EFFECT
→ RECONCILE
→ UPDATE IMPLEMENTATION/DEPENDENCY PROJECTIONS
→ SELECT NEXT GAP
```

## Rozdzielenie stanów

Lifecycle architektoniczny: `TARGET_ONLY | PLANNED | BUILDING | VERIFIED | INTEGRATED | OBSERVED | BLOCKED | QUARANTINED | SUPERSEDED`.

Świeżość epistemiczna: `CURRENT | STALE | UNKNOWN | CONFLICTED`.

Wymiary te są niezależne. Przykładowo komponent może pozostawać w stanie `INTEGRATED + STALE`, dopóki bieżący stan nie zostanie ponownie zaobserwowany.

## Wybór misji

Preferuj najmniejszy fragment ścieżki krytycznej, który domyka rzeczywistą lukę target-vs-implementation. Utrzymuj WIP równy jeden na ścieżce krytycznej, chyba że niezależność partycji została jawnie udowodniona. Zachowuj specjalizację providerów i unikaj przedwczesnej migracji do `ai_platform`.

## Aktualizacja projekcji

Pliki katalogowe są przeglądanymi projekcjami. Fakty dynamiczne muszą zawierać provenance i binding świeżości. Nigdy nie przepisuj normatywnych dokumentów targetu tylko po to, aby implementacja wyglądała na ukończoną.

## Authority

Rekordy ewolucji opisują, co powinno istnieć lub co istnieje. Nie mintują authority do execution, merge, credentials, release ani deploymentu.
