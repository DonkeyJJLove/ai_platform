# LION — Authority attenuation i polityka floty

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=18_AUTHORITY_FLEET
SEARCH_TERMS=authority fleet R2E4 aggregate effect budget lease heartbeat restrict only
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-6f743f802c22"></a>
## SRC-V13-6f743f802c22 — v13/FLEET_AUTHORITY_MODEL_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-6f743f802c22
SOURCE_ARCHIVE=v13
SOURCE_PATH=FLEET_AUTHORITY_MODEL_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=721f60b5158df879e31d5707234a00ca146fafc63ca5957f00e43ee528d7cbc7
SOURCE_BYTES=884

LION_RECORD_BEGIN: SRC-V13-6f743f802c22
LION_RECORD_META: {"anchor":"src-v13-6f743f802c22","archive_id":"v13","authority_effect":"NONE","bytes":884,"carrier":"18_LION_AUTHORITY_FLEET.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"FLEET_AUTHORITY_MODEL_v1_3_candidate.source.md","sha256":"721f60b5158df879e31d5707234a00ca146fafc63ca5957f00e43ee528d7cbc7","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-6f743f802c22","virtual_path":"v13/FLEET_AUTHORITY_MODEL_v1_3_candidate.source.md"}
````markdown
# Fleet Authority Model v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=CANDIDATE_POLICY
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=authority attenuation and typed future domains
DEPENDENCIES=v1.2 authority model
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

```text
child ≤ explicit external grant
executor ≤ mission
mission ≤ fleet envelope
budget ≤ granted effect envelope
```

Executor count cannot increase per-executor authority. Model choice cannot alter authority. Factory lineage cannot transmit credentials.

Physical authority may require a typed partially ordered envelope rather than a single rank; this remains a research target.

````
LION_RECORD_END: SRC-V13-6f743f802c22

<a id="src-v13-9e41c0a72022"></a>
## SRC-V13-9e41c0a72022 — v13/LION_FLEET_POLICY_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-9e41c0a72022
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_FLEET_POLICY_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=d9990df3c1caffc6aad725876940b369df3d4f2c109ef64b1b981278ed19e48f
SOURCE_BYTES=985

LION_RECORD_BEGIN: SRC-V13-9e41c0a72022
LION_RECORD_META: {"anchor":"src-v13-9e41c0a72022","archive_id":"v13","authority_effect":"NONE","bytes":985,"carrier":"18_LION_AUTHORITY_FLEET.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_FLEET_POLICY_v1_3_candidate.source.md","sha256":"d9990df3c1caffc6aad725876940b369df3d4f2c109ef64b1b981278ed19e48f","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-9e41c0a72022","virtual_path":"v13/LION_FLEET_POLICY_v1_3_candidate.source.md"}
````markdown
# LION Fleet Policy v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=CANDIDATE_POLICY
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=fleet identity, model binding and effect budgets
DEPENDENCIES=v1.2 fleet policy + R2E1-R2E4
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

Fleet is a governed subsystem. Each executor binds immutable identity, mission, repository baseline, leases, authority context, sandbox, model/runtime attestation, heartbeat and receipt chain.

Builder, verifier, observer and reconciler remain distinct roles. Model binding is a runtime property, not agent identity or authority. Aggregate budgets can only restrict already valid grants.

A batch closes only after unknown missions, results, branches, leases and effects are reconciled.

````
LION_RECORD_END: SRC-V13-9e41c0a72022

<a id="src-v14c2-d09d10cb7263"></a>
## SRC-V14C2-d09d10cb7263 — v14c2/FLEET_AUTHORITY_MODEL_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-d09d10cb7263
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=FLEET_AUTHORITY_MODEL_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=23ad65db115ae577146962a7608e583999925f5f317e572c2a2f32b2c2c18c3f
SOURCE_BYTES=1226

LION_RECORD_BEGIN: SRC-V14C2-d09d10cb7263
LION_RECORD_META: {"anchor":"src-v14c2-d09d10cb7263","archive_id":"v14c2","authority_effect":"NONE","bytes":1226,"carrier":"18_LION_AUTHORITY_FLEET.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"FLEET_AUTHORITY_MODEL_v1_4_candidate.source.md","sha256":"23ad65db115ae577146962a7608e583999925f5f317e572c2a2f32b2c2c18c3f","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-d09d10cb7263","virtual_path":"v14c2/FLEET_AUTHORITY_MODEL_v1_4_candidate.source.md"}
````markdown
# Fleet Authority Model v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=CANDIDATE_POLICY
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=authority attenuation across fleet, action and runtime admission
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

```text
child ≤ explicit external grant
executor ≤ mission
mission ≤ fleet envelope
budget ≤ granted effect envelope
runtime admission ≤ PDP ALLOW ∩ current authority ∩ exact runtime identity ∩ budget
```

A model, Bean, Factory lineage, ActionSpec, ActionProposal or PDP adapter cannot mint credentials or grants. Aggregate effect budget is restrict-only. Rehoming the runner changes placement, not authority semantics. Physical authority remains a typed research target and must never be inferred from logical-host identity.

````
LION_RECORD_END: SRC-V14C2-d09d10cb7263

<a id="src-v14c2-7853c4b080b9"></a>
## SRC-V14C2-7853c4b080b9 — v14c2/LION_FLEET_POLICY_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-7853c4b080b9
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_FLEET_POLICY_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=c7f3011b8ce7c4c1cdb781758b85887377bd9db2aeda8eed4e4f6f0cfb3c70b8
SOURCE_BYTES=1103

LION_RECORD_BEGIN: SRC-V14C2-7853c4b080b9
LION_RECORD_META: {"anchor":"src-v14c2-7853c4b080b9","archive_id":"v14c2","authority_effect":"NONE","bytes":1103,"carrier":"18_LION_AUTHORITY_FLEET.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_FLEET_POLICY_v1_4_candidate.source.md","sha256":"c7f3011b8ce7c4c1cdb781758b85887377bd9db2aeda8eed4e4f6f0cfb3c70b8","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-7853c4b080b9","virtual_path":"v14c2/LION_FLEET_POLICY_v1_4_candidate.source.md"}
````markdown
# LION Fleet Policy v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=CANDIDATE_POLICY
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=federated fleet behavior and evidence
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

Fleet identity is exact repository/mission/runtime evidence, not worker count. R2E4 exact semantic/evidence binding and aggregate effect budget are integrated AS-IS. Budgets restrict effects but never create authority.

A fleet operation must bind exact source, exact target, capability, mission, authority/currentness, runtime identity, observation and reconciliation. `100 logical workers` is not evidence of `100 independent production executors`.

````
LION_RECORD_END: SRC-V14C2-7853c4b080b9
