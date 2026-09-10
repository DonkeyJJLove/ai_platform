# LION — punkt wejścia do dokumentacji projektu

LION jest architekturą związaną z dowodami i rozdzielającą authority, która zarządza ewolucją wspomaganą przez AI: od obserwacji i propozycji, przez autoryzację, runtime admission i ograniczone efekty, po niezależną obserwację i rekonsyliację. Dokumentacja, sama obecność kodu oraz sukces CI nie nadają authority i nie dowodzą wdrożenia.

## Bieżąca dokumentacja v1.4

Punktem wejścia do bieżącej warstwy dokumentacyjnej architektury jest [`architecture/v1_4/README.md`](architecture/v1_4/README.md). Projekcje stanu muszą być związane z exact Git identity i stają się `STALE` po materialnym driftcie baseline'u. Model architektury wyprowadzany ze źródeł pozostaje własnością `cyber_lion/architecture_projection/full_architecture.py`; katalogi v1.4 są projekcjami i indeksami, a nie drugim wykonywalnym źródłem prawdy.

`status.json` jest zachowany jako historyczna projekcja epoki E003. Jego samodeklarowany stan `CURRENT` nie jest dowodem bieżącego stanu repozytorium i nie może być używany jako źródło currentness dla v1.4.

Bieżąca epoka upgrade'u dokumentacji używa manifestu [`architecture/v1_4/documentation_fleet_r128.json`](architecture/v1_4/documentation_fleet_r128.json) oraz polityki językowej [`architecture/v1_4/DOCUMENTATION_LANGUAGE_POLICY.md`](architecture/v1_4/DOCUMENTATION_LANGUAGE_POLICY.md). Flota 128 dronów jest flotą **logiczną**; sam manifest nie dowodzi 128 równoległych procesów, Podów, modeli ani executorów runtime.

## Granice architektury

Bieżący Action plane obejmuje Action IR/proposal, canonical PDP handoff, runtime admission, runtime execution, effect-time currentness oraz runtime reconciliation. F009 pozostaje ograniczonym dowodem end-to-end dla konkretnego toru wykonawczego, a nie automatycznym dowodem kompletnej kontroli wszystkich powierzchni skutku.

Bean, CapabilityNeed, Composition, Mosaic i builder-chain primitives są zaimplementowane. Ograniczone dowody B0 nie są dowodem generalnej Factory generativity, aktywowanej rekursywnej child autonomy ani Factory-of-Factories.

Po integracjach R21/R22/R23 i kolejnych etapach R2/R3 nie wolno traktować dawnych frontierów jako bieżących wyłącznie dlatego, że pozostają opisane w historycznych dokumentach. Bieżący frontier musi być wyprowadzany z live `master`, exact Git state, aktualnych testów oraz właściwej klasy evidence.

## Nawigacja i lineage

- `architecture/v1_4/current_state.json` — projekcja bieżącego stanu; jej currentness należy oceniać względem dokładnego baseline'u, do którego jest związana.
- `architecture/v1_4/federation_current_vector.json` — exact Git identities federacji dla epoki, w której został wygenerowany.
- `architecture/v1_4/material_object_catalog.json` — katalog materialnych obiektów architektury; nie jest automatycznie pełnym spisem wszystkich symboli.
- `architecture/v1_4/capability_catalog.json` i `contract_catalog.json` — stan capabilities i kontraktów.
- `architecture/v1_4/event_state_catalog.json` — kanoniczne przepływy i semantyka stanów.
- `architecture/v1_4/semantic_owners.json` — routing własności semantycznej.
- `architecture/v1_4/documentation_gap_register.json` — naprawione, otwarte i historyczne luki dokumentacyjne/formalne.
- `architecture/v1_4/history_and_supersession.md` — lineage v1.3/v1.4 oraz granice falsyfikacji i supersession.
- `architecture/v1_4/documentation_fleet_r128.json` — logiczna flota do audytu dokumentacji.
- `architecture/v1_4/DOCUMENTATION_LANGUAGE_POLICY.md` — reguły polskiego języka podstawowego i ochrony literalnych elementów technicznych.

Dokumentacja historyczna pozostaje historycznym evidence i nie może być przepisywana tak, aby udawała bieżący stan.

## Polityka językowa

Dokumentacja przeznaczona dla człowieka używa języka polskiego jako podstawowego. Nazwy kontraktów, typów, klas, symboli, pól JSON/YAML, LPCL/LCMS, stanów maszynowych, ścieżek, komend, commitów, hashy i innych reprodukowalnych identyfikatorów pozostają literalne.

Tłumaczenie dokumentu nie zmienia jego statusu epistemicznego. `STALE`, `TARGET`, `CANDIDATE`, `UNKNOWN` albo historyczny zapis nie może stać się `CURRENT` lub `INTEGRATED` przez samą redakcję tekstu.

## Niezmienniki

```text
DOCUMENTATION != AUTHORITY
DOCUMENTATION != LIVE EVIDENCE
PROPOSAL != AUTHORIZATION
PDP ALLOW != RUNTIME ADMISSION
RUNTIME ADMISSION != EFFECT
RECEIPT != INDEPENDENT OBSERVATION
OBSERVATION != RECONCILED CLOSURE
CANDIDATE != INTEGRATED
IMPLEMENTED != DEPLOYED
LOGICAL DRONE COUNT != REAL RUNTIME PROCESS COUNT
```

Każda istotna aktualizacja dokumentacji powinna przechodzić cykl:

```text
LIVE / EXACT EVIDENCE
→ DOCUMENTATION GAP
→ CANDIDATE UPDATE
→ VALIDATION / FALSIFICATION
→ READBACK
→ RECONCILIATION
```
