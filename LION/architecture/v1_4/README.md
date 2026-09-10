# Dokumentacja architektury LION — v1.4

Odczyt po integracji #325 i reguły domknięcia #314 opisuje [notatka rekonsyliacji](PR314_PR325_CURRENTNESS.md). Poniższa epoka R128 i jej bazowe identyfikatory są historycznym zakresem tej dokumentacji, nie deklaracją bieżącego HEAD master.

**Epoka dokumentacyjna:** `LION-DOC-R128-2026-09-10-R1`  
**Bazowy stan `master` odtworzony przed utworzeniem kandydata:** HEAD `5e40338511fe2a5f0a891c823b03f9855d6ad1e8` / TREE `306b8cf245299517278ab0959a7aca79f66e5343`  
**Gałąź kandydata dokumentacyjnego:** `docs/lion-v1.4-r128-polish-homeostasis-r1`  
**Authority effect dokumentacji:** `NONE`

Ten katalog jest warstwą homeostazy dokumentacji v1.4. Nie zastępuje kodu źródłowego, kontraktów, runtime evidence ani historycznych rekordów RAG. Każdy koncept powinien posiadać jednego głównego semantic ownera, a fakty o wysokiej kardynalności powinny być materializowane jako exact-baseline machine projections zamiast ręcznie przepisywanej narracji.

## Currentness

Poprzednia wersja tego dokumentu była nadal związana z baseline'em R23 `67a4f8243aa6805e47035e572bd458f73fd0b358` / `4f6fbc481c8df8f7e1fd75f04188207a1c6fbcf5`. W chwili rozpoczęcia tej epoki live `master` został odtworzony jako `5e40338511fe2a5f0a891c823b03f9855d6ad1e8` / `306b8cf245299517278ab0959a7aca79f66e5343`. Stary baseline pozostaje historią, ale nie jest bieżącym currentness basis.

Obowiązuje:

```text
NO_VALID_CURRENTNESS_BASIS -> NOT_CURRENT
MATERIAL_BASELINE_DRIFT    -> CURRENT_TO_STALE
HISTORY_CHANGED_BY_REALITY -> SUPERSEDE_DO_NOT_REWRITE
```

Dokumentacja nie może sama odświeżyć `current_state.json`, truth carriers ani runtime evidence. Ich ponowne związanie wymaga właściwego generatora/walidatora i osobnego readbacku.

## Bieżąca architektura

Model architektury wyprowadzany ze źródeł jest własnością `cyber_lion/architecture_projection/full_architecture.py`. Dokumentacja v1.4 opisuje ten model i jego dowody; nie tworzy drugiej wykonywalnej architektury, drugiego PDP, drugiego `RuntimeAdmissionEngine` ani nowego źródła authority.

W zintegrowanej linii rozwojowej znajdują się między innymi LPCL/Process IR, Action IR/proposal, canonical PDP evaluation/handoff, Action→Runtime binding, runtime admission, runtime execution, effect-time currentness, observation i reconciliation. Dokładna klasyfikacja `AS_IS/CANDIDATE/TARGET` musi być zawsze ponownie odtwarzana z live `master` i nie może być dziedziczona z dawnego raportu.

Ostatnie zintegrowane etapy obejmują także VKT-R3: ograniczony `TEST_ONLY` runtime K3s, 3 × 128 realnych Podów w historycznym teście, Mission Control oraz późniejsze związanie lokalnego obserwatora i endpoint locatora z canonical `master`. Te wyniki są dowodem określonych eksperymentów i implementacji; nie są produkcyjnym authority ani dowodem stale aktywnego runtime.

Bean/Composition/Mosaic primitives oraz ograniczone protokoły B0 pozostają osobną osią dojrzałości. Bounded evidence nie może być rozszerzana semantycznie na nieudowodnioną generalną Factory generativity, child autonomy albo Factory-of-Factories.

## Granice evidence i authority

```text
DOCUMENTATION != AUTHORITY
CODE_PRESENCE != DEPLOYMENT
CI_PASS != PRODUCTION_READY
PDP_ALLOW != RUNTIME_ADMISSION
RUNTIME_ADMISSION != EFFECT
EXECUTION_RECEIPT != INDEPENDENT_OBSERVATION
OBSERVATION != RECONCILED_CLOSURE
```

Liczba logicznych dronów jest również oddzielona od liczby realnych executorów. Manifest `documentation_fleet_r128.json` tworzy 128 logicznych tożsamości pracy dokumentacyjnej, ale nie jest dowodem 128 procesów, Podów, modeli ani niezależnych failure domains.

## Flota dokumentacyjna R128

Epoka wykorzystuje osiem sektorów po 16 logicznych dronów:

```text
DOC-001..016  CURRENTNESS_BASELINES
DOC-017..032  LANGUAGE_TRANSLATION
DOC-033..048  NAVIGATION_STRUCTURE
DOC-049..064  ARCHITECTURE_SEMANTICS
DOC-065..080  AUTHORITY_SECURITY
DOC-081..096  RUNTIME_VKT
DOC-097..112  HISTORY_PROVENANCE
DOC-113..128  VERIFICATION_RECONCILIATION
```

W każdym sektorze role builder/analyzer, verifier, observer i reconciler pozostają logicznie rozdzielone. Zwiększenie liczby workerów nie zwiększa authority.

## Polityka językowa

Bieżąca dokumentacja human-facing używa języka polskiego jako języka podstawowego. Literalnie zachowywane są nazwy kontraktów, klas, funkcji, pól schematów, tokenów LPCL/LCMS, statusów maszynowych, ścieżek, komend, commitów, hashy oraz innych identyfikatorów potrzebnych do reprodukcji. Szczegóły: [`DOCUMENTATION_LANGUAGE_POLICY.md`](DOCUMENTATION_LANGUAGE_POLICY.md).

Historyczne exact evidence nie jest „spolszczane” przez zmianę jego wartości. Można tłumaczyć opis, ale nie commit/tree/hash, wynik eksperymentu, stan historyczny ani znaczenie falsyfikacji.

## Nawigacja

- `current_state.json` — projekcja stanu; wymaga sprawdzenia currentness względem exact baseline'u.
- `federation_current_vector.json` — exact federation identities dla epoki generatora.
- `material_object_catalog.json` — katalog materialnych obiektów architektury; nie jest automatycznie pełnym all-symbol census.
- `capability_catalog.json` — capabilities: integrated/bounded/partial/target/unproven.
- `contract_catalog.json` — materialne kontrakty i znane sprzeczności kompatybilności.
- `event_state_catalog.json` — kanoniczne przepływy i semantyka stanów.
- `semantic_owners.json` — routing semantic ownership.
- `documentation_gap_register.json` — naprawione, otwarte i historyczne luki dokumentacyjne/formalne.
- `documentation_mutation_manifest.json` — historyczny manifest zakresu zmian dokumentacyjnych poprzedniej epoki; nie stanowi bieżącego planu sam przez się.
- `DOCUMENTATION_UPDATE_PLAN.md` — plan bieżącej epoki dokumentacyjnej.
- `DOCUMENTATION_LANGUAGE_POLICY.md` — zasady translacji i zachowania tokenów technicznych.
- `DOCUMENTATION_CURRENTNESS_AUDIT.md` — audyt translacji, stale machine projections i kolejności regeneracji.
- `documentation_fleet_r128.json` — logiczna flota 128 dronów dokumentacyjnych.
- `history_and_supersession.md` — zachowany lineage, falsyfikacja i supersession.
- `VKT_R3_FINAL_REPORT.md` — historyczny raport końcowy ograniczonego testu VKT-R3.
- `VKT_R3_MISSION_CONTROL.md` — model obserwacyjny Mission Control.
- `VKT_R3_RUNTIME_VALIDATION.md` — kontrakt i wynikowe granice walidacji runtime.
- `VKT_R3_RUNTIME_IMAGE.md` — identity obrazu runtime i granice dowodu.

Głównymi human semantic ownerami pozostają m.in. `cyber_lion/CAPABILITY_MAP.md`, `CONTRACT_MAP.md`, `EVENT_DATA_MODEL.md`, `SCIENTIFIC_STATUS.md`, `TARGET_ARCHITECTURE.md`, `cyber_lion/enterprise/README.md` i `AI_NATIVE_ROADMAP.md`. Routing między właścicielami należy odczytywać z bieżącego `semantic_owners.json` tylko w zakresie jego aktualnego baseline'u.

## Następny etap ewolucji dokumentacji

Po translacji i uporządkowaniu prose layer należy ponownie wygenerować lub zweryfikować machine projections, w szczególności `current_state.json`, federation/currentness artefacts i truth carriers. Sam commit dokumentacyjny nie jest closure. Closure wymaga:

```text
CANDIDATE UPDATE
-> STRUCTURAL VALIDATION
-> SEMANTIC FALSIFICATION
-> EXACT GIT READBACK
-> CURRENTNESS CHECK
-> RECONCILIATION
```
