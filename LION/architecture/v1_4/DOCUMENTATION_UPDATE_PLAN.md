# LION v1.4 — plan aktualizacji dokumentacji R128

**UPDATE_EPOCH_ID:** `LION-DOC-R128-2026-09-10-R1`  
**Bazowy `master`:** `5e40338511fe2a5f0a891c823b03f9855d6ad1e8`  
**Bazowy TREE:** `306b8cf245299517278ab0959a7aca79f66e5343`  
**Gałąź kandydata:** `docs/lion-v1.4-r128-polish-homeostasis-r1`  
**Authority effect:** `NONE`  
**Production authority:** `NONE`

Poprzednia treść tego pliku opisywała historyczny plan R22H. Jest zachowana w Git history, ale nie może być używana jako bieżący plan po późniejszych integracjach R23/R24/R2/R3 i VKT-R3. Ta rewizja superseduje wyłącznie bieżącą funkcję planistyczną tego pliku; nie przepisuje historycznych commitów, raportów ani evidence.

## Cel

Celem epoki jest doprowadzenie human-facing documentation do stanu, w którym:

```text
CURRENT_SYSTEM_MODEL
≈
CURRENT_DOCUMENTATION_MODEL
```

w granicach jawnie zapisanej niepewności. Etap koncentruje się na uporządkowaniu dokumentacji, polskim języku podstawowym, currentness, semantic ownership, history/provenance oraz przygotowaniu repozytorium do kolejnego etapu ewolucji. Nie jest to etap rozszerzania runtime authority.

## Flota logiczna

Do audytu używana jest flota 128 logicznych dronów zdefiniowana w `documentation_fleet_r128.json`:

```text
8 sektorów * 16 dronów = 128 logicznych dronów
```

Sektory:

1. `CURRENTNESS_BASELINES`
2. `LANGUAGE_TRANSLATION`
3. `NAVIGATION_STRUCTURE`
4. `ARCHITECTURE_SEMANTICS`
5. `AUTHORITY_SECURITY`
6. `RUNTIME_VKT`
7. `HISTORY_PROVENANCE`
8. `VERIFICATION_RECONCILIATION`

Flota logiczna nie dowodzi 128 jednoczesnych procesów, Podów, modeli ani executorów. Worker count nie zwiększa authority.

## Kolejność zależności

```text
1. REACQUIRE exact master HEAD/TREE
2. classify documentation by owner / artifact class / currentness
3. identify human-facing non-Polish prose
4. translate prose under DOCUMENTATION_LANGUAGE_POLICY
5. repair navigation and stale currentness wording
6. preserve exact historical evidence and supersession lineage
7. reconcile architecture / authority / runtime statements
8. validate Markdown, JSON references and relative links
9. compare candidate against frozen base
10. read back exact candidate HEAD/TREE
11. run or observe applicable repository CI
12. classify machine projections requiring regeneration
13. do not promote candidate to current merely because prose is clean
14. reconcile and produce next documentation/runtime frontier
```

## Polityka translacji

Human-facing prose jest tłumaczony na polski. Następujące elementy pozostają literalne:

```text
contract/class/function names
JSON/YAML/schema keys
LPCL/LCMS tokens
state identifiers
paths
commands
branch names
commit/tree/blob SHA
hashes/digests
runtime object identifiers
exact historical evidence values
```

Nie tłumaczy się w miejscu byte-preserved source payloadów ani materiałów, których hash jest elementem provenance. Dla nich tworzy się polską warstwę objaśniającą.

## Currentness

Każdy dynamiczny dokument musi jawnie rozróżniać:

```text
LIVE_CURRENT
CANDIDATE_BASELINE
HISTORICAL_EVIDENCE
TARGET
UNKNOWN
STALE
```

Obowiązuje:

```text
NO_VALID_CURRENTNESS_BASIS -> NOT_CURRENT
MATERIAL_BASELINE_DRIFT    -> CURRENT_TO_STALE
HISTORY_CHANGED_BY_REALITY -> SUPERSEDE_DO_NOT_REWRITE
```

Poprzedni v1.4 documentation baseline `67a4f8243aa6805e47035e572bd458f73fd0b358` / `4f6fbc481c8df8f7e1fd75f04188207a1c6fbcf5` jest historyczny względem bazowego `master` tej epoki `5e40338511fe2a5f0a891c823b03f9855d6ad1e8` / `306b8cf245299517278ab0959a7aca79f66e5343`.

## Co aktualizujemy w tej fali

Pierwsza fala obejmuje bieżące human-facing entry points i dokumentację VKT-R3:

```text
LION/README.md
LION/architecture/v1_4/README.md
LION/architecture/v1_4/DOCUMENTATION_UPDATE_PLAN.md
LION/architecture/v1_4/DOCUMENTATION_LANGUAGE_POLICY.md
LION/architecture/v1_4/documentation_fleet_r128.json
LION/architecture/v1_4/VKT_R3_FINAL_REPORT.md
LION/architecture/v1_4/VKT_R3_MISSION_CONTROL.md
LION/architecture/v1_4/VKT_R3_RUNTIME_VALIDATION.md
LION/architecture/v1_4/VKT_R3_RUNTIME_IMAGE.md
AI_NATIVE_ROADMAP.md
```

Dokumenty już polskie nie są przepisywane bez potrzeby. Machine-readable projections, truth carriers i schematy nie są modyfikowane wyłącznie po to, aby wyglądały stylistycznie jednolicie.

## Semantyczne bramki jakości

Nowa dokumentacja ma zostać sfalsyfikowana pod kątem:

```text
FEATURE_DOCUMENTED_PRESENT_BUT_ABSENT
FEATURE_PRESENT_BUT_DOCUMENTED_ABSENT
STALE_BASELINE_PRESENTED_AS_CURRENT
CANDIDATE_PRESENTED_AS_INTEGRATED
INTEGRATED_PRESENTED_AS_DEPLOYED
TEST_ONLY_PRESENTED_AS_PRODUCTION
LOGICAL_DRONE_COUNT_PRESENTED_AS_REAL_RUNTIME_COUNT
AUTHORITY_INFLATION_BY_DOCUMENTATION
BROKEN_HISTORY_OR_PROVENANCE
BROKEN_LINK_OR_OWNER_ROUTING
RUNTIME_CLAIM_WITHOUT_RUNTIME_EVIDENCE
```

## VKT-R3

VKT-R3 ma dwa odrębne rodzaje prawdy:

```text
HISTORICAL_TEST_EVIDENCE
!=
CURRENT_ACTIVE_RUNTIME
```

Historyczny test 3 × 128 real Kubernetes Pods pozostaje dowodem określonego przebiegu `TEST_ONLY`. Późniejsze PR #312 i #313 związały lokalny Mission Control i endpoint locator z canonical `master`, ale sama obecność implementacji nie dowodzi, że panel lub swarm jest aktualnie aktywny. Active runtime trzeba obserwować na właściwym hoście.

## Authority

Dokumentacja nie może:

```text
mint authority
expand authority
create runtime admission
select an EffectProvider
execute an effect
turn CI PASS into production readiness
turn translation into semantic integration
```

Gałąź dokumentacyjna jest kandydatem. Merge do `master`, runtime deployment, host mutation oraz production deployment pozostają oddzielnymi efektami.

## Kryterium wyjścia tej epoki

Etap może być nazwany `RECONCILED` dopiero wtedy, gdy:

```text
translated human-facing docs are internally consistent
AND stale currentness claims are removed or explicitly classified
AND exact historical evidence values remain intact
AND navigation resolves to existing owners/files
AND no documentation statement widens authority
AND candidate Git identity is read back exactly
AND applicable validation is terminal
AND remaining machine-projection drift is explicitly listed
```

Sukces pojedynczego commita lub tłumaczenia nie jest closure.
