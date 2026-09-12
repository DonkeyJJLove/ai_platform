# Dokumentacja architektury LION — v1.4

> **Generation 8 / R4 local entry (2026-09-12T12:10:33.768699Z)** — validated source `c572a3ec74ac58f20414f81fcb51d0c586f4df01` / `0ec64acce259300c28a031ea9bfcd56d18a4d691`; 307 production sources, 268 effect surfaces, 0 unresolved taxonomy, 2709-test suite green, 23 workflows, E02 trust/source-rebind/Git-generator/failure-domain candidates materialized. Final documentation and truth descendants must be reacquired after this commit. See [`R4_CURRENT_EVOLUTION_STATE.md`](R4_CURRENT_EVOLUTION_STATE.md) and [`GIT_LOGICAL_TREE.json`](GIT_LOGICAL_TREE.json).


> **R3 rebased current entry (2026-09-12T11:34:17.271121Z)** — live remote master `938aa94460a2e0f81c470c1586626290bb74bc2c` / `70d698f937608495c3845b9b7c1f0bc515a3789d`; final validated noncarrier snapshot `03fc2ed8317c5cff775af217b8c9f65b5b1f1c05` / `0898c7b6337acf6963eb11562080d70cd0d4624f`. Exact currentness after this documentation commit must be reacquired. R2 remains incomplete historical evidence (132/136 records) and is superseded for forward evolution, never synthetically completed. Git logical spine: [`GIT_LOGICAL_TREE.json`](GIT_LOGICAL_TREE.json); current R3 state: [`R3_CURRENT_EVOLUTION_STATE.md`](R3_CURRENT_EVOLUTION_STATE.md); R2→R3 gap: [`R2_R3_GAP_AND_SUPERSESSION.json`](R2_R3_GAP_AND_SUPERSESSION.json); workflow audit: [`WORKFLOW_HOMEOSTASIS_R3.md`](WORKFLOW_HOMEOSTASIS_R3.md).


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


## Uzgodnienie LPCL 1.1 — integracja PR #309

Opis LPCL 1.0 powyżej zachowuje zakres historyczny i zgodność wsteczną.
Jawnie wersjonowane `RUN` z `LPCL_VERSION=1.1` mają osobny parser
`cyber_lion/process_language/canonical_run.py` oraz punkt interpretacji
`cyber_lion/process_language/interpretation.py`. Niewersjonowane `RUN` pozostają
danymi historycznymi. Parser wymaga pojedynczego końcowego `END`; znacząca treść
po nim jest błędem, a nie pomijanym fragmentem.

Gramatyka: `cyber_lion/process_language/lpcl_run_1_1.ebnf`.
Model ról: `cyber_lion/process_language/fleet_mission.py`; klasy LOGICAL, LOCAL,
HYBRID opisują reprezentację ról, nie uruchomione drony ani uprawnienia.
Interpretacja zwraca kandydatów ProcessIR/FleetMissionIR bez efektów. Nie zastępuje
Action/PDP/RuntimeAdmission. Projekcja `process_orchestration.py` wiąże istniejące
warstwy i nie dodaje nowej warstwy nadrzędnej.

Konstytucja, model floty i zamrożenie projektu w plikach `LPCL_LANGUAGE_CONSTITUTION.md`,
`LPCL_FLEET_MISSION_MODEL.md`, `LPCL_V1_1_DESIGN_FREEZE.md` dokumentują zakres kandydata
#309; ich stare HEAD/statusy nie są dowodem bieżącego master ani runtime.
Integrację i aktualność potwierdzają dokładne Git/CI, a nie etykieta w dokumencie.
## Generation 10 forward-evolution entry

Current local-candidate truth is described by `current_state.json`; Git lineage by `GIT_LOGICAL_TREE.json`/`.md`; adaptive fleet sizing by `FLEET_EVOLUTION_R4.json`; R3→R4 artifact currentness by `R3_R4_ARTIFACT_CURRENTNESS.json`; the 64-step continuation by `EVOLUTION_PLAN_64_R4.json`; and the next autonomous process by `NEXT_LPCL_R4_TO_R5.txt`. Exact final truth digest is read from the carrier files, not predicted in this noncarrier document.
## R5 multigeneration local state

The current local unpublished lineage is documented by `R5_CURRENT_EVOLUTION_STATE.md`. The informational Git spine is the v3 snapshot in `GIT_LOGICAL_TREE.json`; runtime, RAG and repository nodes remain separate evidence planes. R4 is an exact verified 145-record rebased knowledge candidate, while R5 is built only after final carrier-last truth because code/workflow evolution continued after R4.

E02 now contains an external APP_SESSION verifier boundary but no installed external verifier or durable replay/sequence provider. Mission Control remains on stale runtime source; an effect-free exact-master source-rebind package is prepared but not applied. Workflow homeostasis v2 has zero blocking defects in critical evidence workflows and routes all remaining findings to self-hosted-runtime/external-write family review rather than blanket mutation.
