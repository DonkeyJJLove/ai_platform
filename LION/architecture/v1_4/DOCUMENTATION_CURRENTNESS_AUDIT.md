# LION v1.4 — audyt currentness i języka dokumentacji R128

```text
AUDIT_EPOCH=LION-DOC-R128-2026-09-10-R1
BASE_MASTER_HEAD=5e40338511fe2a5f0a891c823b03f9855d6ad1e8
BASE_MASTER_TREE=306b8cf245299517278ab0959a7aca79f66e5343
CANDIDATE_BRANCH=docs/lion-v1.4-r128-polish-homeostasis-r1
AUTHORITY_EFFECT=NONE
PRODUCTION_AUTHORITY=NONE
```

## Werdykt

Repozytorium posiadało jednocześnie trzy klasy problemów dokumentacyjnych: human-facing prose w języku angielskim, dynamiczne projekcje związane z historycznymi baseline'ami oraz dokumenty generowane, których języka nie należy naprawiać wyłącznie w wygenerowanym pliku. Epoka R128 rozdziela te klasy zamiast traktować je jako jedną operację „translate all”.

## Zrealizowana fala Polish-primary

W tej epoce przetłumaczono lub zreorganizowano human-facing prose następujących właścicieli i warstw:

```text
LION/README.md
LION/architecture/v1_4/README.md
LION/architecture/v1_4/DOCUMENTATION_UPDATE_PLAN.md
LION/architecture/v1_4/DOCUMENTATION_LANGUAGE_POLICY.md
LION/architecture/v1_4/history_and_supersession.md
LION/architecture/v1_4/VKT_R3_FINAL_REPORT.md
LION/architecture/v1_4/VKT_R3_MISSION_CONTROL.md
LION/architecture/v1_4/VKT_R3_RUNTIME_VALIDATION.md
LION/architecture/v1_4/VKT_R3_RUNTIME_IMAGE.md
AI_NATIVE_ROADMAP.md
docs/architecture/local-swarm-p0-docker-polygon.md
docs/architecture/process-language/README.md
docs/architecture/process-language/LPCL_STATUS.md
docs/architecture/process-language/LPCL_SCOPE.md
docs/architecture/process-language/LPCL_CURRENTNESS_NOTE.md
docs/architecture/process-language/LPCL_MIGRATION.md
docs/architecture/process-language/LPCL_NEGATIVE_RULES.md
docs/architecture/process-language/LPCL_REVIEW_CHECKLIST.md
docs/architecture/process-language/LPCL_V1_CANDIDATE.md
docs/architecture/process-language/R21_LPCL_BUILD_README.md
docs/architecture/process-language/LPCL_DYNAMIC_CLOSURE_REPAIR.md
```

Translacja zachowuje literalnie nazwy kontraktów, tokeny LPCL/LCMS, klucze machine-readable, paths, commands, status identifiers, commit/tree/hash/digest i exact historical evidence.

## Stale machine projections — nie naprawiać ręcznie

### `LION/architecture/v1_4/current_state.json`

Zaobserwowany plik nadal deklaruje:

```text
process_epoch=R23
baseline_head=ab1ab2f2cbdeda1f10b2c73e78acf230f5be21da
baseline_tree=0dea4254efc0c3da3db5fa994a9b87e9a2f85ba2
```

To nie jest bieżący baseline epoki R128. Plik zawiera również historyczne source/effect counts, census i frontier opisujące R23/R24. Klasyfikacja:

```text
CURRENT_STATE_PROJECTION=STALE_REGENERATION_REQUIRED
MANUAL_FIELD_REWRITE=FORBIDDEN_AS_FALSE_CURRENTNESS_SHORTCUT
```

### `LION/architecture/v1_4/documentation_gap_register.json`

Zaobserwowany plik nadal ma:

```text
baseline_head=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
```

oraz działania nazwane `r20_action`. Jest historycznie użyteczny, ale nie może być bieżącym rejestrem luk po R21/R22/R23/R24/R2/R3/VKT-R3 bez regeneracji. Klasyfikacja:

```text
DOCUMENTATION_GAP_REGISTER=STALE_REGENERATION_REQUIRED
```

### `LION/status.json`

Pozostaje legacy currentness carrier z wcześniejszej epoki. Nie jest promowany ani przepisywany w tej fali bez osobnej analizy consumerów i formalnej migracji/supersession.

## Dokumentacja generowana — lokalizować generator, nie output

`docs/architecture/production-entry/README.md` jawnie deklaruje się jako deterministic rendering canonical world model / production-entry dossier. Jego human-facing output jest po angielsku, a tekst jest emitowany przez `cyber_lion/enterprise/production_entry.py`.

Dlatego:

```text
DIRECT_MARKDOWN_TRANSLATION=DEFER
REASON=WOULD_BE_OVERWRITTEN_BY_REGENERATION
NEXT_CLASS=GENERATOR_LOCALIZATION_REQUIRED
```

Dodatkowo bieżący rendering zachowuje historyczną topologię trzech logicznych WSL nodes i własny dawny dossier baseline. Przed lokalizacją generatora należy najpierw rozstrzygnąć, czy ten renderer ma reprezentować historyczny dossier czy current projection.

## Historyczne dokumenty eksperymentalne

Dokumenty P0, R21/R22/R23 i VKT-R3 zachowują exact historical identity. Translacja prose nie zmienia ich statusu. W szczególności:

```text
HISTORICAL_TEST_PASS != ACTIVE_RUNTIME_NOW
HISTORICAL_CANDIDATE_STATUS != CURRENT_MASTER_STATUS
OLD_HEAD_TREE != CURRENT_HEAD_TREE
```

Późniejszy sukces VKT-R3 nie powoduje przepisania wcześniejszego P0 `IMPLEMENTED_NOT_MATERIALIZED`; jest to zmiana frontier/currentness, nie kasowanie kontrprzykładu.

## Flota dokumentacyjna

`documentation_fleet_r128.json` definiuje 128 logical drone identities w ośmiu rozłącznych sektorach. Jest to materializacja struktury pracy i responsibility partitioning, ale nie dowód 128 procesów runtime.

```text
8 sectors * 16 logical drones = 128 logical drones
REAL_PARALLEL_RUNTIME_PROVEN=false
```

## Następna fala

Kolejny etap nie powinien zaczynać się od dalszego ręcznego przepisywania prose. Najpierw trzeba zamknąć machine-currentness lane:

```text
1. reacquire exact candidate/master identity
2. regenerate current_state from canonical owners
3. regenerate documentation_gap_register
4. reconcile semantic_owners against present files
5. localize generated documentation at generator source where safe
6. regenerate derived Markdown
7. validate internal links and machine references
8. run exact-head repository CI / documentation tests
9. read back generated projections
10. reconcile and only then classify the next evolution frontier
```

## Niezmienniki

```text
TRANSLATION != CURRENTNESS
DOCUMENTATION != AUTHORITY
GENERATED_DOC != GENERATOR_SOURCE
LOGICAL_FLEET != REAL_EXECUTOR_FLEET
HISTORY != CURRENT_STATE
CANDIDATE != MASTER
CLEAN_PROSE != RECONCILED_TRUTH
```
