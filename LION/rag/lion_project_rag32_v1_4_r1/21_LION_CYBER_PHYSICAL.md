# LION — Cyber-physical, safety invariants i laboratorium robotyki

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=21_CYBER_PHYSICAL
SEARCH_TERMS=cyber physical robotics safety interlocks simulation ISO sensors
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-2d56702909ac"></a>
## SRC-V13-2d56702909ac — v13/LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-2d56702909ac
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=882d682242c59d2e1c982288c855e7496858cdecd5b4b229b07baefa2cec40b0
SOURCE_BYTES=1004

LION_RECORD_BEGIN: SRC-V13-2d56702909ac
LION_RECORD_META: {"anchor":"src-v13-2d56702909ac","archive_id":"v13","authority_effect":"NONE","bytes":1004,"carrier":"21_LION_CYBER_PHYSICAL.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md","sha256":"882d682242c59d2e1c982288c855e7496858cdecd5b4b229b07baefa2cec40b0","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-2d56702909ac","virtual_path":"v13/LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md"}
````markdown
# LION Cyber-Physical Action Model v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=RESEARCH_TARGET
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=typed physical actions
DEPENDENCIES=Action model + safety plane
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

A physical action reuses common intent, mission, authority, expected/forbidden effects and observation semantics, but requires a domain-specific execution plan.

A physical effect binds coordinate frame, units, calibration, object identity, spatial/temporal envelope, speed/force/energy constraints, safety-controller state, emergency stop, independent sensors and physical postconditions.

Model approval cannot replace a hardware safety interlock. Software receipt cannot independently prove a physical postcondition.

````
LION_RECORD_END: SRC-V13-2d56702909ac

<a id="src-v13-f6026e77c166"></a>
## SRC-V13-f6026e77c166 — v13/LION_PHYSICAL_SAFETY_INVARIANTS_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-f6026e77c166
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_PHYSICAL_SAFETY_INVARIANTS_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=9fae4aabfcec3cd358cac3d11b4c39875597bce398aa85e80cf325708a51000e
SOURCE_BYTES=1057

LION_RECORD_BEGIN: SRC-V13-f6026e77c166
LION_RECORD_META: {"anchor":"src-v13-f6026e77c166","archive_id":"v13","authority_effect":"NONE","bytes":1057,"carrier":"21_LION_CYBER_PHYSICAL.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_PHYSICAL_SAFETY_INVARIANTS_v1_3_candidate.source.md","sha256":"9fae4aabfcec3cd358cac3d11b4c39875597bce398aa85e80cf325708a51000e","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-f6026e77c166","virtual_path":"v13/LION_PHYSICAL_SAFETY_INVARIANTS_v1_3_candidate.source.md"}
````markdown
# LION Physical Safety Invariants v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=RESEARCH_TARGET
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=non-negotiable physical safety constraints
DEPENDENCIES=cyber-physical action model
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

- Physical actuation authority is typed and binds exact spatial, temporal and safety scope.
- Loss of sensing, heartbeat, calibration or safety-controller state cannot increase capability.
- Emergency stop is independent from probabilistic inference.
- Unit and coordinate-frame mismatch fails closed.
- Simulation success is not hardware safety proof.
- Partial physical effects enter explicit PARTIAL/UNRECONCILED state.
- Human-presence and protected-zone interlocks dominate model intent.
- Physical observation requires independent sensor evidence.

````
LION_RECORD_END: SRC-V13-f6026e77c166

<a id="src-v13-53f504686263"></a>
## SRC-V13-53f504686263 — v13/LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-53f504686263
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=ee910bfbd5f7957c8463d6720ab4dbd1e857b8418a79024637fbd334f470b45e
SOURCE_BYTES=963

LION_RECORD_BEGIN: SRC-V13-53f504686263
LION_RECORD_META: {"anchor":"src-v13-53f504686263","archive_id":"v13","authority_effect":"NONE","bytes":963,"carrier":"21_LION_CYBER_PHYSICAL.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md","sha256":"ee910bfbd5f7957c8463d6720ab4dbd1e857b8418a79024637fbd334f470b45e","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-53f504686263","virtual_path":"v13/LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md"}
````markdown
# LION Robotics Laboratory Plan v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=FUTURE_TARGET
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=simulation-first robotics path
DEPENDENCIES=Action IR + independent physical domain
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

1. Schema and unit/frame falsification.
2. Simulation-only task provider.
3. Digital-twin divergence tests.
4. Safety-precondition model.
5. Independent observer.
6. Hardware emergency stop and interlocks.
7. One bounded reversible physical task.
8. Physical postcondition reconciliation.

No hardware execution is permitted while canonical Action IR, host authority separation, complete mediation and independent physical failure-domain requirements remain open.

````
LION_RECORD_END: SRC-V13-53f504686263

<a id="src-v13-8367026b2a1c"></a>
## SRC-V13-8367026b2a1c — v13/evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md

SOURCE_ID=SRC-V13-8367026b2a1c
SOURCE_ARCHIVE=v13
SOURCE_PATH=evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=21b284687e9f34d1e98cbf98e3818bc8f9871bc15545fcfa4dbf135a9145b5c1
SOURCE_BYTES=841

LION_RECORD_BEGIN: SRC-V13-8367026b2a1c
LION_RECORD_META: {"anchor":"src-v13-8367026b2a1c","archive_id":"v13","authority_effect":"NONE","bytes":841,"carrier":"21_LION_CYBER_PHYSICAL.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md","sha256":"21b284687e9f34d1e98cbf98e3818bc8f9871bc15545fcfa4dbf135a9145b5c1","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-8367026b2a1c","virtual_path":"v13/evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md"}
````markdown
# Cyber-physical external reference targets

This package does not claim conformity. It identifies current primary-source targets for future design:

- ISO 10218-1:2025 — industrial robot safety requirements.
- ISO 10218-2:2025 — industrial robot applications and cells.
- ISO/TS 15066:2016 remains published for collaborative robots; a successor project is under development.
- Regulation (EU) 2023/1230 on machinery generally applies from 20 January 2027.
- Regulation (EU) 2024/1689 (AI Act) is relevant to AI systems influencing physical environments, human oversight, robustness and cybersecurity.

Sources:
- https://www.iso.org/standard/73933.html
- https://www.iso.org/standard/73934.html
- https://www.iso.org/standard/62996.html
- https://eur-lex.europa.eu/eli/reg/2023/1230/oj
- https://eur-lex.europa.eu/eli/reg/2024/1689/oj

````
LION_RECORD_END: SRC-V13-8367026b2a1c

<a id="src-v14c2-9a6d7ef3f57f"></a>
## SRC-V14C2-9a6d7ef3f57f — v14c2/LION_CYBER_PHYSICAL_ACTION_MODEL_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-9a6d7ef3f57f
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_CYBER_PHYSICAL_ACTION_MODEL_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=e85b5016b73fad63cb2f07e804428b75278c556e4605ebf4af6b90d588a92b8a
SOURCE_BYTES=1150

LION_RECORD_BEGIN: SRC-V14C2-9a6d7ef3f57f
LION_RECORD_META: {"anchor":"src-v14c2-9a6d7ef3f57f","archive_id":"v14c2","authority_effect":"NONE","bytes":1150,"carrier":"21_LION_CYBER_PHYSICAL.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_CYBER_PHYSICAL_ACTION_MODEL_v1_4_candidate.source.md","sha256":"e85b5016b73fad63cb2f07e804428b75278c556e4605ebf4af6b90d588a92b8a","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-9a6d7ef3f57f","virtual_path":"v14c2/LION_CYBER_PHYSICAL_ACTION_MODEL_v1_4_candidate.source.md"}
````markdown
# LION Cyber-Physical Action Model v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=RESEARCH_TARGET
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=typed physical action extension
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

The canonical ActionSpec vocabulary may contain `robot.task`, but no current robotics runtime or physical Effect Provider is proven. `robot.task` in a schema is therefore not physical execution capability.

Target:

```text
PhysicalActionSpec
→ deterministic units/frames validation
→ simulation/digital twin
→ safety admission
→ hardware interlocks
→ bounded actuator provider
→ independent sensors
→ physical reconciliation
```

No compliance claim is made by this package.

````
LION_RECORD_END: SRC-V14C2-9a6d7ef3f57f

<a id="src-v14c2-737adeeab38d"></a>
## SRC-V14C2-737adeeab38d — v14c2/LION_PHYSICAL_SAFETY_INVARIANTS_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-737adeeab38d
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_PHYSICAL_SAFETY_INVARIANTS_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=14ead8fbb6a365325b278a3707214b3bf75c6a3728bb2308195d24affdf7717a
SOURCE_BYTES=1187

LION_RECORD_BEGIN: SRC-V14C2-737adeeab38d
LION_RECORD_META: {"anchor":"src-v14c2-737adeeab38d","archive_id":"v14c2","authority_effect":"NONE","bytes":1187,"carrier":"21_LION_CYBER_PHYSICAL.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_PHYSICAL_SAFETY_INVARIANTS_v1_4_candidate.source.md","sha256":"14ead8fbb6a365325b278a3707214b3bf75c6a3728bb2308195d24affdf7717a","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-737adeeab38d","virtual_path":"v14c2/LION_PHYSICAL_SAFETY_INVARIANTS_v1_4_candidate.source.md"}
````markdown
# LION Physical Safety Invariants v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=TARGET_SAFETY_POLICY
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=simulation-first physical safety
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

Physical execution remains unsupported. No language/model/PDP decision alone may command a physical actuator. A physical action requires typed units/frames, bounded speed/force/energy, deterministic validation, simulation/digital twin, independent safety controller, hardware interlocks, independent sensing and physical postcondition reconciliation.

Logical host redundancy does not satisfy independent physical safety observation. Emergency stop and safety channels must be independent of the model/agent control path.

````
LION_RECORD_END: SRC-V14C2-737adeeab38d

<a id="src-v14c2-789c34671fa9"></a>
## SRC-V14C2-789c34671fa9 — v14c2/LION_ROBOTICS_LAB_PLAN_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-789c34671fa9
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_ROBOTICS_LAB_PLAN_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=a815dc7c6ab9fc322571d79a44ad1b539841b3dc0e21019c0b62028c3bd795a2
SOURCE_BYTES=1013

LION_RECORD_BEGIN: SRC-V14C2-789c34671fa9
LION_RECORD_META: {"anchor":"src-v14c2-789c34671fa9","archive_id":"v14c2","authority_effect":"NONE","bytes":1013,"carrier":"21_LION_CYBER_PHYSICAL.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_ROBOTICS_LAB_PLAN_v1_4_candidate.source.md","sha256":"a815dc7c6ab9fc322571d79a44ad1b539841b3dc0e21019c0b62028c3bd795a2","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-789c34671fa9","virtual_path":"v14c2/LION_ROBOTICS_LAB_PLAN_v1_4_candidate.source.md"}
````markdown
# LION Robotics Lab Plan v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=FUTURE_LAB_TARGET
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=bounded reversible robotics validation
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

Robotics remains downstream of Action/runtime-admission closure, independent physical failure-domain evidence and the physical safety plane. First hardware task, if ever authorized, must be bounded, low-energy, reversible, simulation-prevalidated, interlocked and independently observed. No robot, PLC or actuator effect is performed or authorized here.

````
LION_RECORD_END: SRC-V14C2-789c34671fa9

<a id="src-v14c2-8367026b2a1c"></a>
## SRC-V14C2-8367026b2a1c — v14c2/evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md

SOURCE_ID=SRC-V14C2-8367026b2a1c
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=3ba6fb37c90ce012631a58415af732b1905380e71cde1af7c2e4e891e82880a5
SOURCE_BYTES=409

LION_RECORD_BEGIN: SRC-V14C2-8367026b2a1c
LION_RECORD_META: {"anchor":"src-v14c2-8367026b2a1c","archive_id":"v14c2","authority_effect":"NONE","bytes":409,"carrier":"21_LION_CYBER_PHYSICAL.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md","sha256":"3ba6fb37c90ce012631a58415af732b1905380e71cde1af7c2e4e891e82880a5","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-8367026b2a1c","virtual_path":"v14c2/evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md"}
````markdown
# Cyber-physical external requirements — v1.4 evidence note

This successor preserves the v1.3 external-reference class (industrial robot safety, machine safety and AI robustness/oversight) as **reference context only**. The sources were not revalidated in this package build and no compliance claim is made. Before physical execution, legal/standards versions and applicability must be freshly reacquired.

````
LION_RECORD_END: SRC-V14C2-8367026b2a1c
