# LION — Model Plane i laboratorium modelu lokalnego

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=20_MODEL_PLANE
SEARCH_TERMS=local model SaaS hybrid routing OpenAI gpt-oss runtime attestation
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-f62d328a846d"></a>
## SRC-V13-f62d328a846d — v13/LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-f62d328a846d
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=84a0c1b6065befa868e66d2038cb59cf989283dfc74abd550e9db067b403029c
SOURCE_BYTES=1138

LION_RECORD_BEGIN: SRC-V13-f62d328a846d
LION_RECORD_META: {"anchor":"src-v13-f62d328a846d","archive_id":"v13","authority_effect":"NONE","bytes":1138,"carrier":"20_LION_MODEL_PLANE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md","sha256":"84a0c1b6065befa868e66d2038cb59cf989283dfc74abd550e9db067b403029c","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-f62d328a846d","virtual_path":"v13/LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md"}
````markdown
# LION Local OpenAI Lab Plan v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=TARGET_PLAN
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=proposal-only open-weight local-model laboratory
DEPENDENCIES=LAB-DEBIAN census + Action IR
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

## Observed baseline

LAB-DEBIAN: Debian 13, 24 logical Ryzen 9 9950X3D CPUs, about 47 GiB RAM, no visible GPU, no container runtime and no local inference runtime.

## Decision

`gpt-oss-20b` CPU/offload feasibility is plausible but unmeasured. `gpt-oss-120b` is outside the observed memory/accelerator envelope.

## Phases

L0 read-only inference; L1 structured proposal-only actions; L2 isolated TEST_ONLY effect; L3 JARZMO/PEP binding; L4 fleet binding; L5 hybrid routing; L6 independent physical domain; L7 shadow; L8 pre-production.

Installation and model download require separate explicit authorization. This plan grants none.

````
LION_RECORD_END: SRC-V13-f62d328a846d

<a id="src-v13-30287154b822"></a>
## SRC-V13-30287154b822 — v13/LION_MODEL_PLANE_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-30287154b822
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_MODEL_PLANE_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=54efb77e01db8a8b417d3091f9ee4b2e20c5014de6dd17c346fe6861547d5101
SOURCE_BYTES=934

LION_RECORD_BEGIN: SRC-V13-30287154b822
LION_RECORD_META: {"anchor":"src-v13-30287154b822","archive_id":"v13","authority_effect":"NONE","bytes":934,"carrier":"20_LION_MODEL_PLANE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_MODEL_PLANE_v1_3_candidate.source.md","sha256":"54efb77e01db8a8b417d3091f9ee4b2e20c5014de6dd17c346fe6861547d5101","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-30287154b822","virtual_path":"v13/LION_MODEL_PLANE_v1_3_candidate.source.md"}
````markdown
# LION Model Plane v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=TARGET_WITH_LIVE_FEASIBILITY
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=provider-independent reasoning plane
DEPENDENCIES=ActionProposal + PEP
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

SaaS, local open-weight models, deterministic engines and humans may produce hypotheses, blueprints, Bean candidates and ActionSpec candidates. Every provider crosses the same policy and authority boundary.

Model selection cannot change authority. Locality does not imply trust. Trust derives from identity, exact model/runtime binding, policy, evidence and execution boundary.

No local model plane is currently deployed on the observed hosts.

````
LION_RECORD_END: SRC-V13-30287154b822

<a id="src-v13-10b0162a9792"></a>
## SRC-V13-10b0162a9792 — v13/evidence/OPENAI_LOCAL_MODEL_RESEARCH.md

SOURCE_ID=SRC-V13-10b0162a9792
SOURCE_ARCHIVE=v13
SOURCE_PATH=evidence/OPENAI_LOCAL_MODEL_RESEARCH.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=38f238580c92caed1e0b339a1e0b45b433ac7f43762f8396466bf70e4c1f4b02
SOURCE_BYTES=790

LION_RECORD_BEGIN: SRC-V13-10b0162a9792
LION_RECORD_META: {"anchor":"src-v13-10b0162a9792","archive_id":"v13","authority_effect":"NONE","bytes":790,"carrier":"20_LION_MODEL_PLANE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"evidence/OPENAI_LOCAL_MODEL_RESEARCH.md","sha256":"38f238580c92caed1e0b339a1e0b45b433ac7f43762f8396466bf70e4c1f4b02","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-10b0162a9792","virtual_path":"v13/evidence/OPENAI_LOCAL_MODEL_RESEARCH.md"}
````markdown
# Official OpenAI local-model evidence

Current official OpenAI material identifies `gpt-oss-20b` and `gpt-oss-120b` open-weight models and safeguard variants. The 20B model is described in an approximately 16 GB memory class; 120B in an approximately 80 GB class. Open-weight models are self-managed and are not the same as models served through the OpenAI API.

Observed LAB-DEBIAN has about 47 GiB RAM, no GPU visible from WSL and no model runtime. Therefore only a CPU/offload 20B laboratory benchmark is plausible; performance remains unknown until measured. 120B is excluded from the current observed envelope.

Sources:
- https://openai.com/open-models/
- https://openai.com/index/introducing-gpt-oss/
- https://help.openai.com/en/articles/11870455-openai-open-weight-models-gpt-oss

````
LION_RECORD_END: SRC-V13-10b0162a9792

<a id="src-v14c2-ae70149d4bd9"></a>
## SRC-V14C2-ae70149d4bd9 — v14c2/LION_LOCAL_OPENAI_LAB_PLAN_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-ae70149d4bd9
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_LOCAL_OPENAI_LAB_PLAN_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=a1a789a44f1a4e96c32ad23b0b47cf162d3f1f11a2eb45425bce857b5d42ca19
SOURCE_BYTES=1203

LION_RECORD_BEGIN: SRC-V14C2-ae70149d4bd9
LION_RECORD_META: {"anchor":"src-v14c2-ae70149d4bd9","archive_id":"v14c2","authority_effect":"NONE","bytes":1203,"carrier":"20_LION_MODEL_PLANE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_LOCAL_OPENAI_LAB_PLAN_v1_4_candidate.source.md","sha256":"a1a789a44f1a4e96c32ad23b0b47cf162d3f1f11a2eb45425bce857b5d42ca19","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-ae70149d4bd9","virtual_path":"v14c2/LION_LOCAL_OPENAI_LAB_PLAN_v1_4_candidate.source.md"}
````markdown
# LION Local OpenAI Lab Plan v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=LAB_TARGET
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=proposal-only local open-weight model experiment
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

No local model runtime was observed during the v1.4 census. Therefore this remains a measurement plan, not deployment documentation.

A future lab experiment must be proposal-only, independently attested, resource-bounded and unable to widen authority. Record exact model digest, runtime/version, tokenizer, host identity, memory/CPU/GPU visibility, latency, failure/restart behavior and deterministic post-run cleanup. Fresh hardware/model feasibility must be measured at execution time rather than copied from the 2026-09-02 estimate.

````
LION_RECORD_END: SRC-V14C2-ae70149d4bd9

<a id="src-v14c2-610c6cbd0862"></a>
## SRC-V14C2-610c6cbd0862 — v14c2/LION_MODEL_PLANE_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-610c6cbd0862
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_MODEL_PLANE_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=8ee61a4071028cc2e2d1fe93b0df86e7ab3ab76803fd33162353c4a60b8e7b50
SOURCE_BYTES=1192

LION_RECORD_BEGIN: SRC-V14C2-610c6cbd0862
LION_RECORD_META: {"anchor":"src-v14c2-610c6cbd0862","archive_id":"v14c2","authority_effect":"NONE","bytes":1192,"carrier":"20_LION_MODEL_PLANE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_MODEL_PLANE_v1_4_candidate.source.md","sha256":"8ee61a4071028cc2e2d1fe93b0df86e7ab3ab76803fd33162353c4a60b8e7b50","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-610c6cbd0862","virtual_path":"v14c2/LION_MODEL_PLANE_v1_4_candidate.source.md"}
````markdown
# LION Model Plane v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=TARGET_WITH_EXTERNAL_SAAS_USAGE
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=local/SaaS model routing and trust boundary
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

Model choice remains orthogonal to authority. SaaS reasoning may produce scaffolding/proposals; local open-weight runtime is not observed on LAB-DEBIAN or LAB-UBUNTU. HybridModelRouter exists only as stale-base candidate lineage.

Target routes may include `LOCAL_ONLY`, `SAAS_ONLY`, `LOCAL_PREFERRED`, `SAAS_PREFERRED`, dual evaluation and deterministic-only modes. Provider substitution must never change capabilities, grants or effect boundaries. Model/runtime identity requires attestation before consequential use.

````
LION_RECORD_END: SRC-V14C2-610c6cbd0862

<a id="src-v14c2-10b0162a9792"></a>
## SRC-V14C2-10b0162a9792 — v14c2/evidence/OPENAI_LOCAL_MODEL_RESEARCH.md

SOURCE_ID=SRC-V14C2-10b0162a9792
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=evidence/OPENAI_LOCAL_MODEL_RESEARCH.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=7f11bf1f026b1e85655d89b865371af65cb7deb284ab252b95b62a0253010b09
SOURCE_BYTES=401

LION_RECORD_BEGIN: SRC-V14C2-10b0162a9792
LION_RECORD_META: {"anchor":"src-v14c2-10b0162a9792","archive_id":"v14c2","authority_effect":"NONE","bytes":401,"carrier":"20_LION_MODEL_PLANE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"evidence/OPENAI_LOCAL_MODEL_RESEARCH.md","sha256":"7f11bf1f026b1e85655d89b865371af65cb7deb284ab252b95b62a0253010b09","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-10b0162a9792","virtual_path":"v14c2/evidence/OPENAI_LOCAL_MODEL_RESEARCH.md"}
````markdown
# Local model research — v1.4 evidence note

The 2026-09-02 package contained OpenAI/open-weight feasibility references. This v1.4 build did not revalidate those external product specifications. Live host census found no local model binary/process on LAB-DEBIAN or LAB-UBUNTU. Therefore `LOCAL_MODEL_PLANE=NOT_DEPLOYED`; any future sizing or model choice must be freshly researched and benchmarked.

````
LION_RECORD_END: SRC-V14C2-10b0162a9792
