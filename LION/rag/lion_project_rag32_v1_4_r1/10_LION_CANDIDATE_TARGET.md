# LION — Kandydaci, granice dowodu i architektura docelowa

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=10_CANDIDATE_TARGET
SEARCH_TERMS=CANDIDATE TARGET frontier stale candidate not integrated
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-f8090ab11d59"></a>
## SRC-V13-f8090ab11d59 — v13/LION_ARCHITECTURE_CANDIDATE_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-f8090ab11d59
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_ARCHITECTURE_CANDIDATE_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=fd426ef9b6d8fb6f1348bd8703e5404d7cbb8f36b4277c0348381b9a4ef0462a
SOURCE_BYTES=1206

LION_RECORD_BEGIN: SRC-V13-f8090ab11d59
LION_RECORD_META: {"anchor":"src-v13-f8090ab11d59","archive_id":"v13","authority_effect":"NONE","bytes":1206,"carrier":"10_LION_CANDIDATE_TARGET.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_ARCHITECTURE_CANDIDATE_v1_3_candidate.source.md","sha256":"fd426ef9b6d8fb6f1348bd8703e5404d7cbb8f36b4277c0348381b9a4ef0462a","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-f8090ab11d59","virtual_path":"v13/LION_ARCHITECTURE_CANDIDATE_v1_3_candidate.source.md"}
````markdown
# LION Architecture CANDIDATE v1.3

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=VERIFIED_AND_RESEARCH_CANDIDATES
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=non-integrated and detached candidate planes
DEPENDENCIES=AS-IS baseline
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

## Git candidates

- PR #248: R2E4 exact-head semantic/evidence binding at `8bf8934a0cf2809b58b460c01976cf82ae0692e7` / `eee3ea5f4f0a116e0f5409b6885a4fb0a5f691d1`.
- PR #249: aggregate effect budget at `46174de77634ce2b6d62bd6709f8ff3470d51951` / `a2c2ca9594dd30174e0892f48464678da27e1bf2`, stacked on #248.

Both are verified candidates and do not change master or production authority.

## Detached research candidates

- AS-IS/CANDIDATE/TARGET truth model;
- AutonomyBlueprint schema;
- Action IR schema beneath ActionProposal;
- LCMS EBNF;
- Materializer Registry;
- local model and hybrid routing plan;
- simulation-first cyber-physical action model.

None becomes integrated by inclusion in this package.

````
LION_RECORD_END: SRC-V13-f8090ab11d59

<a id="src-v13-9cc4cfb26ffd"></a>
## SRC-V13-9cc4cfb26ffd — v13/LION_ARCHITECTURE_TARGET_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-9cc4cfb26ffd
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_ARCHITECTURE_TARGET_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=dcd22324c4b88a52bd525cf2bcd6553ad9db35b9ecbedd4ccf8c13141bdae3bf
SOURCE_BYTES=1331

LION_RECORD_BEGIN: SRC-V13-9cc4cfb26ffd
LION_RECORD_META: {"anchor":"src-v13-9cc4cfb26ffd","archive_id":"v13","authority_effect":"NONE","bytes":1331,"carrier":"10_LION_CANDIDATE_TARGET.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_ARCHITECTURE_TARGET_v1_3_candidate.source.md","sha256":"dcd22324c4b88a52bd525cf2bcd6553ad9db35b9ecbedd4ccf8c13141bdae3bf","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-9cc4cfb26ffd","virtual_path":"v13/LION_ARCHITECTURE_TARGET_v1_3_candidate.source.md"}
````markdown
# LION Architecture TARGET v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=TARGET
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=desired pre-production architecture
DEPENDENCIES=AS-IS + CANDIDATE
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

## Target flow

```text
evidence-bound world/system state
→ Gap
→ CapabilityNeed
→ Bean reuse/spec candidate
→ deterministic CompositionContract
→ Mosaic
→ AutonomyBlueprint candidate
→ Materializer
→ Bean/Autonomy candidate
→ independent verification
→ ActionSpec/IR
→ ActionProposal
→ PDP/authority/budget/currentness
→ capability-reduced PEP
→ effect
→ independent observation
→ reconciliation
→ next epoch
```

## Target properties

Automatically self-degrading truth projections; live host authority separation; global complete mediation; an independent physical verifier domain; terminal Bean Factory generativity; provider-independent local/SaaS routing; typed local console without raw shell authority; model/runtime attestation; simulation-first physical actions; hardware safety interlocks before physical execution.

````
LION_RECORD_END: SRC-V13-9cc4cfb26ffd

<a id="src-v14c2-b0dc76e256c7"></a>
## SRC-V14C2-b0dc76e256c7 — v14c2/LION_ARCHITECTURE_CANDIDATE_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-b0dc76e256c7
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_ARCHITECTURE_CANDIDATE_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=fd0dcb14c9575825240b0dab03d706e0771d3655f11e26759ca782dfc2a4ee7d
SOURCE_BYTES=1544

LION_RECORD_BEGIN: SRC-V14C2-b0dc76e256c7
LION_RECORD_META: {"anchor":"src-v14c2-b0dc76e256c7","archive_id":"v14c2","authority_effect":"NONE","bytes":1544,"carrier":"10_LION_CANDIDATE_TARGET.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_ARCHITECTURE_CANDIDATE_v1_4_candidate.source.md","sha256":"fd0dcb14c9575825240b0dab03d706e0771d3655f11e26759ca782dfc2a4ee7d","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-b0dc76e256c7","virtual_path":"v14c2/LION_ARCHITECTURE_CANDIDATE_v1_4_candidate.source.md"}
````markdown
# LION Architecture CANDIDATE v1.4

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=CANDIDATE_AND_STALE_FRONTIER
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=non-integrated candidate and research planes
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

## Current candidate taxonomy

Historical candidate branches are evidence lineage, not current AS-IS. LCMS, read-only `process.exec`, hybrid model routing and PhysicalActionSpec exist as stale-base candidate families and require reconstruction/revalidation on current master before any reuse.

`AutonomyBlueprint` and `MaterializerRegistry` remain target contracts rather than integrated candidates.

The package itself introduces detached v1.4 documentation/schema candidates only. Inclusion here grants no repository, runtime, host or production authority.

## Candidate admission rule

```text
candidate present
!= candidate current
!= candidate verified on current base
!= integrated
!= deployed
```

Any v1.3 candidate reused in v1.4 must bind the exact current baseline, exact semantic delta and current tests before it may be called `CURRENT_MASTER_BASE_CANDIDATE`.

````
LION_RECORD_END: SRC-V14C2-b0dc76e256c7

<a id="src-v14c2-9ed0f641dd74"></a>
## SRC-V14C2-9ed0f641dd74 — v14c2/LION_ARCHITECTURE_TARGET_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-9ed0f641dd74
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_ARCHITECTURE_TARGET_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=e996cbe7c165e82dbbafd112909ba496ba381a753d77a6be4a7986154187e524
SOURCE_BYTES=2008

LION_RECORD_BEGIN: SRC-V14C2-9ed0f641dd74
LION_RECORD_META: {"anchor":"src-v14c2-9ed0f641dd74","archive_id":"v14c2","authority_effect":"NONE","bytes":2008,"carrier":"10_LION_CANDIDATE_TARGET.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_ARCHITECTURE_TARGET_v1_4_candidate.source.md","sha256":"e996cbe7c165e82dbbafd112909ba496ba381a753d77a6be4a7986154187e524","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-9ed0f641dd74","virtual_path":"v14c2/LION_ARCHITECTURE_TARGET_v1_4_candidate.source.md"}
````markdown
# LION Architecture TARGET v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=TARGET
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=desired pre-production architecture
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

## Target evolutionary loop

```text
evidence-bound world/system state
→ Gap
→ CapabilityNeed
→ Bean reuse/spec
→ CompositionContract
→ Mosaic
→ AutonomyBlueprint candidate
→ Materializer
→ candidate artifact/autonomy
→ independent verification
→ ActionSpec / CanonicalActionIR
→ ActionProposal
→ canonical PDP
→ exact runtime-effect + runtime-identity binding
→ RuntimeAdmissionEngine
→ capability-reduced PEP
→ effect
→ independent observation
→ reconciliation
→ next epoch
```

## Target properties

- documentation/truth projections self-degrade on material drift;
- general Factory generativity is separately proven beyond the bounded B0 protocol;
- child autonomy lineage exists without credential inheritance;
- canonical domain-independent Materializer Registry exists;
- PDP result binds exactly one runtime effect and runtime identity;
- LCMS compiles deterministically to canonical ActionSpec/IR and never executes directly;
- Local Console exposes capability-reduced adapters, not raw shell authority;
- provider-independent local/SaaS routing cannot alter authority;
- independent physical verifier/observer domain exists;
- complete mediation moves from `UNKNOWN` only after reachable-surface proof;
- cyber-physical actions remain simulation-first and require hardware safety interlocks before real effects.

````
LION_RECORD_END: SRC-V14C2-9ed0f641dd74
