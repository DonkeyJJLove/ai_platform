# LION — Oryginalne manifesty, raporty kontroli, indeksy i prompty

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=31_SOURCE_PROVENANCE
SEARCH_TERMS=source manifest SHA256 verification inventory upgrade decisions NEXT_EXECUTION_PROMPT README
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

Wszystkie prompty i instrukcje w tym kontenerze są archiwalnymi materiałami. Aktywny protokół kontynuacji znajduje się w 03. Dawne deklaracje „brak pliku” należy czytać jako stan ówczesnego, niepełnego wejścia; literalne oryginały są teraz zachowane.

## Rekordy źródłowe

<a id="src-v13-d251ab018fff"></a>
## SRC-V13-d251ab018fff — v13/LION_OPENAI_PROJECT_SOURCE_INDEX_v1_3_candidate.md

SOURCE_ID=SRC-V13-d251ab018fff
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_OPENAI_PROJECT_SOURCE_INDEX_v1_3_candidate.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=10ec000c31fccf63f9d93996181433070f2c499757001c4772ee148bb28ba240
SOURCE_BYTES=1116

LION_RECORD_BEGIN: SRC-V13-d251ab018fff
LION_RECORD_META: {"anchor":"src-v13-d251ab018fff","archive_id":"v13","authority_effect":"NONE","bytes":1116,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_OPENAI_PROJECT_SOURCE_INDEX_v1_3_candidate.md","sha256":"10ec000c31fccf63f9d93996181433070f2c499757001c4772ee148bb28ba240","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-d251ab018fff","virtual_path":"v13/LION_OPENAI_PROJECT_SOURCE_INDEX_v1_3_candidate.md"}
````markdown
# LION OpenAI Project Source Index v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=CURRENT_CANDIDATE_PACKAGE_INDEX
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=package navigation and precedence
DEPENDENCIES=all package files
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

This package is a detached project-context candidate. It is not an execution authority and does not become a second canonical owner.

Read first:

1. `LION_EVOLUTION_FULL_REPORT_2026-09-02.md`
2. `EVIDENCE_INDEX.json`
3. `CONTRADICTION_REGISTER.json`
4. `LION_ARCHITECTURE_AS_IS_v1_3_candidate.source.md`
5. `LION_ARCHITECTURE_CANDIDATE_v1_3_candidate.source.md`
6. `LION_ARCHITECTURE_TARGET_v1_3_candidate.source.md`
7. `THE_BEAN_FACTORY_CANONICAL_MODEL_v1_3_candidate.source.md`
8. `NEXT_EXECUTION_PROMPT.md`

When live Git evidence conflicts with this package, live evidence wins and this package becomes STALE.

````
LION_RECORD_END: SRC-V13-d251ab018fff

<a id="src-v13-57ef89f7ff3e"></a>
## SRC-V13-57ef89f7ff3e — v13/NEXT_EXECUTION_PROMPT.md

SOURCE_ID=SRC-V13-57ef89f7ff3e
SOURCE_ARCHIVE=v13
SOURCE_PATH=NEXT_EXECUTION_PROMPT.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=459ccd27b16504ee374753034d153d397cf6abf5f3e63fbb4a41875b3523839a
SOURCE_BYTES=3922

LION_RECORD_BEGIN: SRC-V13-57ef89f7ff3e
LION_RECORD_META: {"anchor":"src-v13-57ef89f7ff3e","archive_id":"v13","authority_effect":"NONE","bytes":3922,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"NEXT_EXECUTION_PROMPT.md","sha256":"459ccd27b16504ee374753034d153d397cf6abf5f3e63fbb4a41875b3523839a","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-57ef89f7ff3e","virtual_path":"v13/NEXT_EXECUTION_PROMPT.md"}
````markdown
# NEXT EXECUTION PROMPT

```text
RUN=
LION-EVOLUTION-A0-TRUTH-PLANE-EXACT-BASELINE-RECONCILIATION-R1

--repository=
DonkeyJJLove/ai_platform

--baseline-branch=
master

--expected-head=
2be0b312407920ac25d812f1c0bb6ecfcb31aa4c

--expected-tree=
3c9705f85301e73f268228f3c36f6ae82a641633

--mode=
READ_ONLY_FIRST
CANDIDATE_ONLY
FAIL_CLOSED
FALSIFICATION_FIRST
NO_AUTHORITY
NO_HOST_MUTATION
NO_REPOSITORY_EFFECT
NO_PR_CREATION
NO_BRANCH_CREATION
NO_MERGE
NO_RELEASE
NO_DEPLOY
```

## Objective

Reconstruct and prepare a detached candidate repair for the internal truth-plane contradiction in which current master implements BeanSpec, BeanInstance, BeanCandidate, CapabilityNeed, CompositionContract, CompositionEngine and heterogeneous Mosaic, while `cyber_lion/architecture_projection/gap.py` and stale architecture/registry projections still classify material elements as TARGET_ONLY or CURRENT at an older baseline.

## Required read-only observations

1. Resolve live `master` and require `2be0b312407920ac25d812f1c0bb6ecfcb31aa4c` / `3c9705f85301e73f268228f3c36f6ae82a641633`.
2. Re-fetch exact blobs for:
   - `cyber_lion/contracts/bean.py`
   - `cyber_lion/contracts/bean_candidate.py`
   - `cyber_lion/contracts/bean_composition.py`
   - `cyber_lion/contracts/capability_need.py`
   - `cyber_lion/contracts/mosaic.py`
   - `cyber_lion/contracts/bean_builder_bridge.py`
   - `cyber_lion/enterprise/bean_composition.py`
   - `cyber_lion/enterprise/capability_need.py`
   - `cyber_lion/enterprise/mosaic.py`
   - corresponding tests
   - `cyber_lion/architecture_projection/gap.py`
   - `cyber_lion/registry/repositories.json`
   - `LION/architecture/implementation-map.json`
   - `LION/architecture/target-map.json`
3. Bind exact file blob digests.
4. Retrieve exact-master Cyber-Lion Core, Bandit and CodeQL conclusions.
5. Reconfirm PR #248 and #249 heads and preserve them as CANDIDATE.

## Candidate-only output

```text
candidate/
  canonical_state.json
  contradiction_register.json
  implementation_projection.json
  gap_projection.json
  repository_maturity_projection.json
  canonical_state.schema.json
  validate_canonical_state.py
  test_validate_canonical_state.py
  README.md
```

Do not attach, branch, open a PR or mutate master.

## Required semantic changes

- Convert live integrated Bean primitives from TARGET_ONLY to evidence-bound integrated states.
- Preserve genuinely missing AutonomyBlueprint, MaterializerRegistry, ActionSpec/LAIR/LCMS/local console as TARGET.
- Mark old implementation-map baseline STALE.
- Separate AS_IS, CANDIDATE and TARGET.
- Do not rewrite historical falsifications.
- Do not infer runtime deployment from code.
- Do not classify PR #248/#249 as integrated.
- Add automatic `CURRENT -> STALE` on material baseline drift.

## Falsifiers

```text
F1 exact master HEAD/TREE differs
F2 a claimed integrated component path is absent
F3 exact-master CI is missing or failed
F4 generated projection still contains TARGET for a live integrated path
F5 generated projection promotes candidate PR content to master
F6 currentness validator accepts HEAD/TREE drift
F7 unknown state or extra field is silently accepted
F8 history is deleted rather than superseded
```

## PASS

```text
exact baseline reproduced
AND current Bean/Composition/Mosaic paths classified consistently
AND candidate plane separated
AND validator negative tests pass
AND no repository/host effect occurred
```

## FAIL

Any falsifier occurs or a material contradictory projection remains.

## UNKNOWN

Required live evidence cannot be retrieved literally.

## Terminal output

```text
RUN=
...

BASELINE_HEAD=
...

BASELINE_TREE=
...

READ_ONLY_OBSERVATION=
PASS | FAIL | UNKNOWN

INTEGRATED_BEAN_PRIMITIVES=
...

STALE_PROJECTIONS=
...

CANDIDATE_FRONTIER=
...

CURRENTNESS_NEGATIVE_TESTS=
PASS | FAIL | UNKNOWN

REPOSITORY_MUTATED=
NO

HOST_MUTATED=
NO

CANDIDATE_PACKAGE_PATH=
...

NEXT_STEP=
...
```

````
LION_RECORD_END: SRC-V13-57ef89f7ff3e

<a id="src-v13-3ea0eeada919"></a>
## SRC-V13-3ea0eeada919 — v13/PACKAGE_MANIFEST.json

SOURCE_ID=SRC-V13-3ea0eeada919
SOURCE_ARCHIVE=v13
SOURCE_PATH=PACKAGE_MANIFEST.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=410da9da1265de7365a181e23472cc73a997429007ee9b5c73d9238ae98bae94
SOURCE_BYTES=10967

LION_RECORD_BEGIN: SRC-V13-3ea0eeada919
LION_RECORD_META: {"anchor":"src-v13-3ea0eeada919","archive_id":"v13","authority_effect":"NONE","bytes":10967,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"PACKAGE_MANIFEST.json","sha256":"410da9da1265de7365a181e23472cc73a997429007ee9b5c73d9238ae98bae94","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-3ea0eeada919","virtual_path":"v13/PACKAGE_MANIFEST.json"}
````json
{
  "authority_effect": "NONE",
  "baseline": {
    "head": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
    "repository": "DonkeyJJLove/ai_platform",
    "tree": "3c9705f85301e73f268228f3c36f6ae82a641633"
  },
  "can_supersede_v1_2_now": false,
  "files": [
    {
      "bytes": 3903,
      "path": "CONTRADICTION_REGISTER.json",
      "sha256": "36bfaf6a9e9edff0b07738924c48fea2e656391425ad1070b26dd6e7f96b24e5"
    },
    {
      "bytes": 13515,
      "path": "EVIDENCE_INDEX.json",
      "sha256": "5bcd55fa15d70b3aeff9d3301953dbffe1b6bde936700f0a40482a45a07c1216"
    },
    {
      "bytes": 884,
      "path": "FLEET_AUTHORITY_MODEL_v1_3_candidate.source.md",
      "sha256": "721f60b5158df879e31d5707234a00ca146fafc63ca5957f00e43ee528d7cbc7"
    },
    {
      "bytes": 1177,
      "path": "FLEET_FAILURE_MODEL_v1_3_candidate.source.md",
      "sha256": "d62e6c378f971b2100c34c281804c3e46e2fddab858e3e223500690293b5ef68"
    },
    {
      "bytes": 1082,
      "path": "LION_ABSTRACTION_COMPILER_v1_3_candidate.source.md",
      "sha256": "c0366be0a9e0c95cd08f69cef9751db3650a0c9f444bec65dafff30f5ec2400d"
    },
    {
      "bytes": 6967,
      "path": "LION_ACTION_IR_SCHEMA_v1_3_candidate.source.json",
      "sha256": "8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5"
    },
    {
      "bytes": 1045,
      "path": "LION_ACTION_MODEL_v1_3_candidate.source.md",
      "sha256": "1d67d01a40769e3d0854f819061b47028ef7ff6a645ce288aed7c10740db17f3"
    },
    {
      "bytes": 1513,
      "path": "LION_ARCHITECTURE_AS_IS_v1_3_candidate.source.md",
      "sha256": "5497644ceff77d3085d6562b0ff588746a7c05dd1f13e96f75a67655ff956aba"
    },
    {
      "bytes": 1206,
      "path": "LION_ARCHITECTURE_CANDIDATE_v1_3_candidate.source.md",
      "sha256": "fd426ef9b6d8fb6f1348bd8703e5404d7cbb8f36b4277c0348381b9a4ef0462a"
    },
    {
      "bytes": 1331,
      "path": "LION_ARCHITECTURE_TARGET_v1_3_candidate.source.md",
      "sha256": "dcd22324c4b88a52bd525cf2bcd6553ad9db35b9ecbedd4ccf8c13141bdae3bf"
    },
    {
      "bytes": 3683,
      "path": "LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json",
      "sha256": "b6dc2786355a1d4294e6ed828219bcadacbeec2515bbb091c43eb1b8da7b4f4e"
    },
    {
      "bytes": 982,
      "path": "LION_AUTONOMY_BLUEPRINT_v1_3_candidate.source.md",
      "sha256": "85666d2148cbdb2b06ae8315728791c35a265dfb22c770ad1273250fe9667106"
    },
    {
      "bytes": 909,
      "path": "LION_AUTONOMY_FACTORY_ROADMAP_v1_3_candidate.source.md",
      "sha256": "ec58a037a7003a461529ce29a6041ac6029a78faf1e227bab638e6e83c3cdc49"
    },
    {
      "bytes": 985,
      "path": "LION_AUTONOMY_MODEL_v1_3_candidate.source.md",
      "sha256": "812bed9b998b2edaf836003369039ba15b11e19898e6e7cacde55983399baaa8"
    },
    {
      "bytes": 1281,
      "path": "LION_BEAN_MODEL_v1_3_candidate.source.md",
      "sha256": "239892f742a9d972e0ea99620fbfa5814a912fe3f083efe78f968fbbf993e21d"
    },
    {
      "bytes": 2942,
      "path": "LION_BEAN_SCHEMA_v1_3_candidate.source.json",
      "sha256": "5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428"
    },
    {
      "bytes": 1187,
      "path": "LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json",
      "sha256": "86c4f338f39f08b16fb1d0b8fd8ef33db2b565b50350158c07f9a23dfd4aa0f0"
    },
    {
      "bytes": 924,
      "path": "LION_COMMAND_MODELING_SYNTAX_v1_3_candidate.source.md",
      "sha256": "a40165ccc280ed789b2249edb5fece4679cd0372be9452cda161cae9d393ac8d"
    },
    {
      "bytes": 1004,
      "path": "LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md",
      "sha256": "882d682242c59d2e1c982288c855e7496858cdecd5b4b229b07baefa2cec40b0"
    },
    {
      "bytes": 38459,
      "path": "LION_EVOLUTION_FULL_REPORT_2026-09-02.md",
      "sha256": "595fe690dab18f0aed938d1a3e3e839288092d8b3007d40b30d673f9450bd7c2"
    },
    {
      "bytes": 5650,
      "path": "LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md",
      "sha256": "0f94b207eb817ae21a174b5966660da4760f7f7f97eb89831f59e30912fa50e6"
    },
    {
      "bytes": 244,
      "path": "LION_FACTORY_LINEAGE_REGISTER_v1_3_candidate.source.json",
      "sha256": "3c977116ea14fba0f16715977944de7661413820cc4985595798e51dfd3baf6f"
    },
    {
      "bytes": 1040,
      "path": "LION_FACTORY_RECURSION_POLICY_v1_3_candidate.source.md",
      "sha256": "cb1fb6d155a9b4526e93d47d9f693aa39dfcd23b20176e437de5cce90c6212bc"
    },
    {
      "bytes": 2434,
      "path": "LION_FALSIFICATION_REGISTER_v1_3_candidate.source.json",
      "sha256": "2e750ef18c13c234f323e0e5ed33712399a84e14bf0c9591f2e5f97648e333c6"
    },
    {
      "bytes": 985,
      "path": "LION_FLEET_POLICY_v1_3_candidate.source.md",
      "sha256": "d9990df3c1caffc6aad725876940b369df3d4f2c109ef64b1b981278ed19e48f"
    },
    {
      "bytes": 967,
      "path": "LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_3_candidate.source.md",
      "sha256": "f2731e226a16fe6e2d887d82a2c610dfb4c202c18e34ca94f106c02ae8b18a86"
    },
    {
      "bytes": 5738,
      "path": "LION_IMPLEMENTATION_STATUS_v1_3_candidate.source.json",
      "sha256": "eac79a9922134665ce9e053949e51ce4b8c8a9fabe3b4638e0dd84877511eeb8"
    },
    {
      "bytes": 1058,
      "path": "LION_LOCAL_CONSOLE_PROTOCOL_v1_3_candidate.source.md",
      "sha256": "f213ac23ce3dfd98bc8df6378a6153093f5590d645c61694a5a76b7b6c10cc3f"
    },
    {
      "bytes": 1138,
      "path": "LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md",
      "sha256": "84a0c1b6065befa868e66d2038cb59cf989283dfc74abd550e9db067b403029c"
    },
    {
      "bytes": 1616,
      "path": "LION_MATERIALIZER_REGISTRY_v1_3_candidate.source.json",
      "sha256": "fbaf330fd571dcc294288feaea624125d0bbf1af1ba1f8b8b4fcbc8b7a5c6642"
    },
    {
      "bytes": 934,
      "path": "LION_MODEL_PLANE_v1_3_candidate.source.md",
      "sha256": "54efb77e01db8a8b417d3091f9ee4b2e20c5014de6dd17c346fe6861547d5101"
    },
    {
      "bytes": 1116,
      "path": "LION_OPENAI_PROJECT_SOURCE_INDEX_v1_3_candidate.md",
      "sha256": "10ec000c31fccf63f9d93996181433070f2c499757001c4772ee148bb28ba240"
    },
    {
      "bytes": 1057,
      "path": "LION_PHYSICAL_SAFETY_INVARIANTS_v1_3_candidate.source.md",
      "sha256": "9fae4aabfcec3cd358cac3d11b4c39875597bce398aa85e80cf325708a51000e"
    },
    {
      "bytes": 7068,
      "path": "LION_POST_V1_2_DELTA_REGISTER_v1_3_candidate.source.json",
      "sha256": "db5022d74dbdc79e0630e77e967d5801c9f2286fa14627ace779dd596651bcd3"
    },
    {
      "bytes": 1156,
      "path": "LION_PREPRODUCTION_ENTRY_CRITERIA_v1_3_candidate.source.md",
      "sha256": "d266bae4a2b27e6bd9900e24eff9a935fd1a91c67d1118e5742a759964870989"
    },
    {
      "bytes": 1633,
      "path": "LION_PROJECT_CANONICAL_CONTEXT_v1_3_candidate.source.md",
      "sha256": "ff3d3c39f33c228da2375cbe184bd7261fac7cf3364ab44bdb99b5ff19842123"
    },
    {
      "bytes": 1025,
      "path": "LION_RECONCILIATION_POLICY_v1_3_candidate.source.md",
      "sha256": "6755583487a128e55808bd89fb1e57a6108116e83179630cfe4ed2e82be38713"
    },
    {
      "bytes": 6573,
      "path": "LION_REPOSITORY_FEDERATION_v1_3_candidate.source.json",
      "sha256": "d9af756f9d2ce1789ac281026f05a2e42d61c92f8fc7fb89abeae668e8e61b8d"
    },
    {
      "bytes": 963,
      "path": "LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md",
      "sha256": "ee910bfbd5f7957c8463d6720ab4dbd1e857b8418a79024637fbd334f470b45e"
    },
    {
      "bytes": 1198,
      "path": "LION_SUPERSESSION_REGISTER_v1_3_candidate.source.json",
      "sha256": "b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988"
    },
    {
      "bytes": 3922,
      "path": "NEXT_EXECUTION_PROMPT.md",
      "sha256": "459ccd27b16504ee374753034d153d397cf6abf5f3e63fbb4a41875b3523839a"
    },
    {
      "bytes": 4781,
      "path": "PREPRODUCTION_BLOCKERS.json",
      "sha256": "c775e4ad6db6edfc4c3c283b68dea61d087073e11ed24a484c68ad1dd2924689"
    },
    {
      "bytes": 1139,
      "path": "README.md",
      "sha256": "7f06df0486ae55882e1eaf8357900112f34c34348f4cb6118efa8ed4b7673750"
    },
    {
      "bytes": 6901,
      "path": "ROADMAP.json",
      "sha256": "cc5a6bcc67d2158d7ca5007c9ede8d91e20332e740dc3a47f53d7ff60d69166d"
    },
    {
      "bytes": 1198,
      "path": "SUPERSESSION_REGISTER.json",
      "sha256": "b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988"
    },
    {
      "bytes": 1251,
      "path": "THE_BEAN_FACTORY_CANONICAL_MODEL_v1_3_candidate.source.md",
      "sha256": "5131c8a6f40ce1cbf145e76d17f29ef6fce796565981c9b43e5855b621a7ecc5"
    },
    {
      "bytes": 841,
      "path": "evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md",
      "sha256": "21b284687e9f34d1e98cbf98e3818bc8f9871bc15545fcfa4dbf135a9145b5c1"
    },
    {
      "bytes": 7337,
      "path": "evidence/GITHUB_BASELINES.json",
      "sha256": "848f564b94f31933b1c0550ec511e4108447e12254c0f8c8a732926e0f28265e"
    },
    {
      "bytes": 2520,
      "path": "evidence/HOST_CENSUS_SUMMARY.json",
      "sha256": "d31111ae8ce05bea387e5cb117b6e98b901be6ecf43ef9e9e150bd5f9096b880"
    },
    {
      "bytes": 790,
      "path": "evidence/OPENAI_LOCAL_MODEL_RESEARCH.md",
      "sha256": "38f238580c92caed1e0b339a1e0b45b433ac7f43762f8396466bf70e4c1f4b02"
    },
    {
      "bytes": 806,
      "path": "scaffold/README.md",
      "sha256": "d87e2c4b5ea9622a40ce307273742b533e78e0d191b9b72b1e47fa2313583c99"
    },
    {
      "bytes": 5260,
      "path": "scaffold/__pycache__/test_validate_canonical_state.cpython-313.pyc",
      "sha256": "8a67d01ee897d4b0b6b4a2188985a26b0854b55d5827bf5b15d689d0c8848e97"
    },
    {
      "bytes": 7083,
      "path": "scaffold/__pycache__/validate_canonical_state.cpython-313.pyc",
      "sha256": "ea58beefeefc87f48b79e2a25b34877cf5af0dbef8eaa96ebfe13d5d7697a4f6"
    },
    {
      "bytes": 6967,
      "path": "scaffold/action_ir.schema.json",
      "sha256": "8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5"
    },
    {
      "bytes": 2286,
      "path": "scaffold/canonical_state.schema.json",
      "sha256": "a561d224e2e9c7ce23c06aee330660c95aeb3d44c0e7bc6321d1b1400d5f2af1"
    },
    {
      "bytes": 2399,
      "path": "scaffold/lcms.ebnf",
      "sha256": "b2ebe55113efd8d033c396156e2653346bf0293109b6e9c8d24562caf5c5e745"
    },
    {
      "bytes": 2416,
      "path": "scaffold/test_validate_canonical_state.py",
      "sha256": "99869dcc33e59249dcec719ea8c7750f5ba52c8fbb04359aa047fcc2ef3293ef"
    },
    {
      "bytes": 5110,
      "path": "scaffold/validate_canonical_state.py",
      "sha256": "9a20e63551b75768c0adc38cd0fe20d1cd6d1e41585306540fd2feda709adacc"
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "host_effect": "NONE",
  "package_id": "the-bean-factory-lion-evolution-v1.3-candidate-2026-09-02",
  "repository_effect": "NONE",
  "schema_version": "lion.package-manifest/v1.3-candidate",
  "status": "DETACHED_CANDIDATE",
  "version": "1.3.0-intermediate-candidate.1"
}

````
LION_RECORD_END: SRC-V13-3ea0eeada919

<a id="src-v13-b33563055168"></a>
## SRC-V13-b33563055168 — v13/README.md

SOURCE_ID=SRC-V13-b33563055168
SOURCE_ARCHIVE=v13
SOURCE_PATH=README.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=7f06df0486ae55882e1eaf8357900112f34c34348f4cb6118efa8ed4b7673750
SOURCE_BYTES=1139

LION_RECORD_BEGIN: SRC-V13-b33563055168
LION_RECORD_META: {"anchor":"src-v13-b33563055168","archive_id":"v13","authority_effect":"NONE","bytes":1139,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"README.md","sha256":"7f06df0486ae55882e1eaf8357900112f34c34348f4cb6118efa8ed4b7673750","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-b33563055168","virtual_path":"v13/README.md"}
````markdown
# THE BEAN FACTORY / LION EVOLUTION — detached candidate package

**Version:** `1.3.0-intermediate-candidate.1`  
**Generated:** `2026-09-02T12:08:31Z`  
**Baseline:** `DonkeyJJLove/ai_platform@2be0b312407920ac25d812f1c0bb6ecfcb31aa4c`  
**Tree:** `3c9705f85301e73f268228f3c36f6ae82a641633`  
**Authority:** none  
**Repository or host mutation:** none

## Main result

LION has integrated governed-autonomy and Bean Factory primitives, but the master truth-plane is internally stale, live MOON authority separation is incomplete, physical failure-domain independence fails, terminal Factory generativity is unproven, and no typed local console or local model runtime exists.

Start with:

- `LION_EVOLUTION_FULL_REPORT_2026-09-02.md`
- `EVIDENCE_INDEX.json`
- `CONTRADICTION_REGISTER.json`
- `PREPRODUCTION_BLOCKERS.json`
- `NEXT_EXECUTION_PROMPT.md`

This package is a **candidate**, not a canonical source owner or execution authority. It proposes `1.3.0-intermediate-candidate.1` and sets `CAN_SUPERSEDE_V1_2_NOW=NO`.

Verification parses every JSON file, executes dependency-free truth-plane unit tests and records SHA-256 digests.

````
LION_RECORD_END: SRC-V13-b33563055168

<a id="src-v13-9f327044bc6a"></a>
## SRC-V13-9f327044bc6a — v13/SOURCE_DIGESTS.sha256

SOURCE_ID=SRC-V13-9f327044bc6a
SOURCE_ARCHIVE=v13
SOURCE_PATH=SOURCE_DIGESTS.sha256
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=82b05603dee3e9ab736b53b2dce60a208b2e5f4fe800e75558d8b4c6a95b0224
SOURCE_BYTES=6634

LION_RECORD_BEGIN: SRC-V13-9f327044bc6a
LION_RECORD_META: {"anchor":"src-v13-9f327044bc6a","archive_id":"v13","authority_effect":"NONE","bytes":6634,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"text","original_path":"SOURCE_DIGESTS.sha256","sha256":"82b05603dee3e9ab736b53b2dce60a208b2e5f4fe800e75558d8b4c6a95b0224","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-9f327044bc6a","virtual_path":"v13/SOURCE_DIGESTS.sha256"}
````text
36bfaf6a9e9edff0b07738924c48fea2e656391425ad1070b26dd6e7f96b24e5  CONTRADICTION_REGISTER.json
5bcd55fa15d70b3aeff9d3301953dbffe1b6bde936700f0a40482a45a07c1216  EVIDENCE_INDEX.json
721f60b5158df879e31d5707234a00ca146fafc63ca5957f00e43ee528d7cbc7  FLEET_AUTHORITY_MODEL_v1_3_candidate.source.md
d62e6c378f971b2100c34c281804c3e46e2fddab858e3e223500690293b5ef68  FLEET_FAILURE_MODEL_v1_3_candidate.source.md
c0366be0a9e0c95cd08f69cef9751db3650a0c9f444bec65dafff30f5ec2400d  LION_ABSTRACTION_COMPILER_v1_3_candidate.source.md
8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5  LION_ACTION_IR_SCHEMA_v1_3_candidate.source.json
1d67d01a40769e3d0854f819061b47028ef7ff6a645ce288aed7c10740db17f3  LION_ACTION_MODEL_v1_3_candidate.source.md
5497644ceff77d3085d6562b0ff588746a7c05dd1f13e96f75a67655ff956aba  LION_ARCHITECTURE_AS_IS_v1_3_candidate.source.md
fd426ef9b6d8fb6f1348bd8703e5404d7cbb8f36b4277c0348381b9a4ef0462a  LION_ARCHITECTURE_CANDIDATE_v1_3_candidate.source.md
dcd22324c4b88a52bd525cf2bcd6553ad9db35b9ecbedd4ccf8c13141bdae3bf  LION_ARCHITECTURE_TARGET_v1_3_candidate.source.md
b6dc2786355a1d4294e6ed828219bcadacbeec2515bbb091c43eb1b8da7b4f4e  LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json
85666d2148cbdb2b06ae8315728791c35a265dfb22c770ad1273250fe9667106  LION_AUTONOMY_BLUEPRINT_v1_3_candidate.source.md
ec58a037a7003a461529ce29a6041ac6029a78faf1e227bab638e6e83c3cdc49  LION_AUTONOMY_FACTORY_ROADMAP_v1_3_candidate.source.md
812bed9b998b2edaf836003369039ba15b11e19898e6e7cacde55983399baaa8  LION_AUTONOMY_MODEL_v1_3_candidate.source.md
239892f742a9d972e0ea99620fbfa5814a912fe3f083efe78f968fbbf993e21d  LION_BEAN_MODEL_v1_3_candidate.source.md
5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428  LION_BEAN_SCHEMA_v1_3_candidate.source.json
86c4f338f39f08b16fb1d0b8fd8ef33db2b565b50350158c07f9a23dfd4aa0f0  LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json
a40165ccc280ed789b2249edb5fece4679cd0372be9452cda161cae9d393ac8d  LION_COMMAND_MODELING_SYNTAX_v1_3_candidate.source.md
882d682242c59d2e1c982288c855e7496858cdecd5b4b229b07baefa2cec40b0  LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md
595fe690dab18f0aed938d1a3e3e839288092d8b3007d40b30d673f9450bd7c2  LION_EVOLUTION_FULL_REPORT_2026-09-02.md
0f94b207eb817ae21a174b5966660da4760f7f7f97eb89831f59e30912fa50e6  LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md
3c977116ea14fba0f16715977944de7661413820cc4985595798e51dfd3baf6f  LION_FACTORY_LINEAGE_REGISTER_v1_3_candidate.source.json
cb1fb6d155a9b4526e93d47d9f693aa39dfcd23b20176e437de5cce90c6212bc  LION_FACTORY_RECURSION_POLICY_v1_3_candidate.source.md
2e750ef18c13c234f323e0e5ed33712399a84e14bf0c9591f2e5f97648e333c6  LION_FALSIFICATION_REGISTER_v1_3_candidate.source.json
d9990df3c1caffc6aad725876940b369df3d4f2c109ef64b1b981278ed19e48f  LION_FLEET_POLICY_v1_3_candidate.source.md
f2731e226a16fe6e2d887d82a2c610dfb4c202c18e34ca94f106c02ae8b18a86  LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_3_candidate.source.md
eac79a9922134665ce9e053949e51ce4b8c8a9fabe3b4638e0dd84877511eeb8  LION_IMPLEMENTATION_STATUS_v1_3_candidate.source.json
f213ac23ce3dfd98bc8df6378a6153093f5590d645c61694a5a76b7b6c10cc3f  LION_LOCAL_CONSOLE_PROTOCOL_v1_3_candidate.source.md
84a0c1b6065befa868e66d2038cb59cf989283dfc74abd550e9db067b403029c  LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md
fbaf330fd571dcc294288feaea624125d0bbf1af1ba1f8b8b4fcbc8b7a5c6642  LION_MATERIALIZER_REGISTRY_v1_3_candidate.source.json
54efb77e01db8a8b417d3091f9ee4b2e20c5014de6dd17c346fe6861547d5101  LION_MODEL_PLANE_v1_3_candidate.source.md
10ec000c31fccf63f9d93996181433070f2c499757001c4772ee148bb28ba240  LION_OPENAI_PROJECT_SOURCE_INDEX_v1_3_candidate.md
9fae4aabfcec3cd358cac3d11b4c39875597bce398aa85e80cf325708a51000e  LION_PHYSICAL_SAFETY_INVARIANTS_v1_3_candidate.source.md
db5022d74dbdc79e0630e77e967d5801c9f2286fa14627ace779dd596651bcd3  LION_POST_V1_2_DELTA_REGISTER_v1_3_candidate.source.json
d266bae4a2b27e6bd9900e24eff9a935fd1a91c67d1118e5742a759964870989  LION_PREPRODUCTION_ENTRY_CRITERIA_v1_3_candidate.source.md
ff3d3c39f33c228da2375cbe184bd7261fac7cf3364ab44bdb99b5ff19842123  LION_PROJECT_CANONICAL_CONTEXT_v1_3_candidate.source.md
6755583487a128e55808bd89fb1e57a6108116e83179630cfe4ed2e82be38713  LION_RECONCILIATION_POLICY_v1_3_candidate.source.md
d9af756f9d2ce1789ac281026f05a2e42d61c92f8fc7fb89abeae668e8e61b8d  LION_REPOSITORY_FEDERATION_v1_3_candidate.source.json
ee910bfbd5f7957c8463d6720ab4dbd1e857b8418a79024637fbd334f470b45e  LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md
b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988  LION_SUPERSESSION_REGISTER_v1_3_candidate.source.json
459ccd27b16504ee374753034d153d397cf6abf5f3e63fbb4a41875b3523839a  NEXT_EXECUTION_PROMPT.md
410da9da1265de7365a181e23472cc73a997429007ee9b5c73d9238ae98bae94  PACKAGE_MANIFEST.json
c775e4ad6db6edfc4c3c283b68dea61d087073e11ed24a484c68ad1dd2924689  PREPRODUCTION_BLOCKERS.json
7f06df0486ae55882e1eaf8357900112f34c34348f4cb6118efa8ed4b7673750  README.md
cc5a6bcc67d2158d7ca5007c9ede8d91e20332e740dc3a47f53d7ff60d69166d  ROADMAP.json
b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988  SUPERSESSION_REGISTER.json
5131c8a6f40ce1cbf145e76d17f29ef6fce796565981c9b43e5855b621a7ecc5  THE_BEAN_FACTORY_CANONICAL_MODEL_v1_3_candidate.source.md
1e82c81988a9b559382a78b2e46ce33c8572be2e476b1d8343126d7d9e838d70  VERIFICATION_REPORT.json
21b284687e9f34d1e98cbf98e3818bc8f9871bc15545fcfa4dbf135a9145b5c1  evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md
848f564b94f31933b1c0550ec511e4108447e12254c0f8c8a732926e0f28265e  evidence/GITHUB_BASELINES.json
d31111ae8ce05bea387e5cb117b6e98b901be6ecf43ef9e9e150bd5f9096b880  evidence/HOST_CENSUS_SUMMARY.json
38f238580c92caed1e0b339a1e0b45b433ac7f43762f8396466bf70e4c1f4b02  evidence/OPENAI_LOCAL_MODEL_RESEARCH.md
d87e2c4b5ea9622a40ce307273742b533e78e0d191b9b72b1e47fa2313583c99  scaffold/README.md
8a67d01ee897d4b0b6b4a2188985a26b0854b55d5827bf5b15d689d0c8848e97  scaffold/__pycache__/test_validate_canonical_state.cpython-313.pyc
ea58beefeefc87f48b79e2a25b34877cf5af0dbef8eaa96ebfe13d5d7697a4f6  scaffold/__pycache__/validate_canonical_state.cpython-313.pyc
8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5  scaffold/action_ir.schema.json
a561d224e2e9c7ce23c06aee330660c95aeb3d44c0e7bc6321d1b1400d5f2af1  scaffold/canonical_state.schema.json
b2ebe55113efd8d033c396156e2653346bf0293109b6e9c8d24562caf5c5e745  scaffold/lcms.ebnf
99869dcc33e59249dcec719ea8c7750f5ba52c8fbb04359aa047fcc2ef3293ef  scaffold/test_validate_canonical_state.py
9a20e63551b75768c0adc38cd0fe20d1cd6d1e41585306540fd2feda709adacc  scaffold/validate_canonical_state.py

````
LION_RECORD_END: SRC-V13-9f327044bc6a

<a id="src-v13-26766deabbb3"></a>
## SRC-V13-26766deabbb3 — v13/VERIFICATION_REPORT.json

SOURCE_ID=SRC-V13-26766deabbb3
SOURCE_ARCHIVE=v13
SOURCE_PATH=VERIFICATION_REPORT.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=1e82c81988a9b559382a78b2e46ce33c8572be2e476b1d8343126d7d9e838d70
SOURCE_BYTES=3517

LION_RECORD_BEGIN: SRC-V13-26766deabbb3
LION_RECORD_META: {"anchor":"src-v13-26766deabbb3","archive_id":"v13","authority_effect":"NONE","bytes":3517,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"VERIFICATION_REPORT.json","sha256":"1e82c81988a9b559382a78b2e46ce33c8572be2e476b1d8343126d7d9e838d70","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-26766deabbb3","virtual_path":"v13/VERIFICATION_REPORT.json"}
````json
{
  "generated_at": "2026-09-02T12:08:31Z",
  "host_mutated": false,
  "json_files": [
    {
      "path": "CONTRADICTION_REGISTER.json",
      "status": "PASS"
    },
    {
      "path": "EVIDENCE_INDEX.json",
      "status": "PASS"
    },
    {
      "path": "LION_ACTION_IR_SCHEMA_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_BEAN_SCHEMA_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_FACTORY_LINEAGE_REGISTER_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_FALSIFICATION_REGISTER_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_IMPLEMENTATION_STATUS_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_MATERIALIZER_REGISTRY_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_POST_V1_2_DELTA_REGISTER_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_REPOSITORY_FEDERATION_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_SUPERSESSION_REGISTER_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "PACKAGE_MANIFEST.json",
      "status": "PASS"
    },
    {
      "path": "PREPRODUCTION_BLOCKERS.json",
      "status": "PASS"
    },
    {
      "path": "ROADMAP.json",
      "status": "PASS"
    },
    {
      "path": "SUPERSESSION_REGISTER.json",
      "status": "PASS"
    },
    {
      "path": "evidence/GITHUB_BASELINES.json",
      "status": "PASS"
    },
    {
      "path": "evidence/HOST_CENSUS_SUMMARY.json",
      "status": "PASS"
    },
    {
      "path": "scaffold/action_ir.schema.json",
      "status": "PASS"
    },
    {
      "path": "scaffold/canonical_state.schema.json",
      "status": "PASS"
    }
  ],
  "json_validation": "PASS",
  "repository_mutated": false,
  "required_files": {
    "count": 51,
    "missing": [],
    "status": "PASS"
  },
  "schema_version": "lion.package-verification/v1.3-candidate",
  "unit_test_command": "python -S -m unittest discover -s scaffold -p test_*.py -v",
  "unit_test_count": 7,
  "unit_test_exit_code": 0,
  "unit_test_status": "PASS",
  "unit_test_stderr": "test_duplicate_component_fails_closed (test_validate_canonical_state.CanonicalStateTests.test_duplicate_component_fails_closed) ... ok\ntest_extra_field_fails_closed (test_validate_canonical_state.CanonicalStateTests.test_extra_field_fails_closed) ... ok\ntest_head_drift_fails_closed (test_validate_canonical_state.CanonicalStateTests.test_head_drift_fails_closed) ... ok\ntest_integrated_without_evidence_path_fails_closed (test_validate_canonical_state.CanonicalStateTests.test_integrated_without_evidence_path_fails_closed) ... ok\ntest_target_with_observed_path_fails_closed (test_validate_canonical_state.CanonicalStateTests.test_target_with_observed_path_fails_closed) ... ok\ntest_unknown_state_fails_closed (test_validate_canonical_state.CanonicalStateTests.test_unknown_state_fails_closed) ... ok\ntest_valid_current_state (test_validate_canonical_state.CanonicalStateTests.test_valid_current_state) ... ok\n\n----------------------------------------------------------------------\nRan 7 tests in 0.001s\n\nOK\n",
  "unit_test_stdout": ""
}

````
LION_RECORD_END: SRC-V13-26766deabbb3

<a id="src-v14c2-53170c5c0239"></a>
## SRC-V14C2-53170c5c0239 — v14c2/LION_OPENAI_PROJECT_SOURCE_INDEX_v1_4_candidate.md

SOURCE_ID=SRC-V14C2-53170c5c0239
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_OPENAI_PROJECT_SOURCE_INDEX_v1_4_candidate.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=f9cfc0d76141019e3f73583ee6c7bcf5dbd27c0c26e2f7336d4578c5046d8bdc
SOURCE_BYTES=1332

LION_RECORD_BEGIN: SRC-V14C2-53170c5c0239
LION_RECORD_META: {"anchor":"src-v14c2-53170c5c0239","archive_id":"v14c2","authority_effect":"NONE","bytes":1332,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_OPENAI_PROJECT_SOURCE_INDEX_v1_4_candidate.md","sha256":"f9cfc0d76141019e3f73583ee6c7bcf5dbd27c0c26e2f7336d4578c5046d8bdc","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-53170c5c0239","virtual_path":"v14c2/LION_OPENAI_PROJECT_SOURCE_INDEX_v1_4_candidate.md"}
````markdown
# LION — OpenAI Project Source Index v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=DOCUMENTATION_CANDIDATE
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=project source/index and evidence precedence
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

## Precedence

`REPRODUCED EXECUTION > LIVE CODE + CURRENT CI > EXACT GIT > MACHINE EVIDENCE > VERIFIED CANDIDATE > CURRENT REFERENCE PACKAGE > ARCHITECTURE > HISTORY > SYNTHESIS`.

## v1.4 additions

- complete v1.3 source-topology inventory (61 lineage slots);
- corrected AS-IS/CANDIDATE/TARGET architecture;
- B0 bounded terminal-protocol PASS vs general-generativity distinction;
- canonical ActionSpec/LAIR/PDP-handoff AS-IS;
- current runtime-admission frontier;
- four-logical-node/one-physical-domain host model;
- documentation currentness/homeostasis model.

This index is not authority and does not make itself canonical by inclusion.

````
LION_RECORD_END: SRC-V14C2-53170c5c0239

<a id="src-v14c2-57ef89f7ff3e"></a>
## SRC-V14C2-57ef89f7ff3e — v14c2/NEXT_EXECUTION_PROMPT.md

SOURCE_ID=SRC-V14C2-57ef89f7ff3e
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=NEXT_EXECUTION_PROMPT.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=5ca467c156df04910bcd631c53dcdbcc90d05ef963b99b66dbd5a2e9d28b5b5e
SOURCE_BYTES=1711

LION_RECORD_BEGIN: SRC-V14C2-57ef89f7ff3e
LION_RECORD_META: {"anchor":"src-v14c2-57ef89f7ff3e","archive_id":"v14c2","authority_effect":"NONE","bytes":1711,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"NEXT_EXECUTION_PROMPT.md","sha256":"5ca467c156df04910bcd631c53dcdbcc90d05ef963b99b66dbd5a2e9d28b5b5e","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-57ef89f7ff3e","virtual_path":"v14c2/NEXT_EXECUTION_PROMPT.md"}
````markdown
# RUN LION-R20-PDP-RUNTIME-ADMISSION-BINDING-v1.4-R1

```text
PROJECT=LION_EVOLUSION
MODE=CANONICAL_RAG_FIRST / LIVE_STATE_REACQUISITION / FALSIFICATION_FIRST / CANDIDATE_ONLY / FAIL_CLOSED
EXPECTED_MASTER_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
EXPECTED_MASTER_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
PRODUCTION_EFFECT=NONE
```

## Objective

Close exactly the first unfinished architecture boundary:

```text
existing PDPResult(ALLOW)
+ exact ActionProposal identity
+ exact policy/authority/currentness evidence
→ one exact RequestedRuntimeEffect
+ one exact RuntimeIdentityBinding
→ existing RuntimeAdmissionEngine.admit(...)
```

Do not create a second PDP. Do not add PEP/provider execution. Do not mint authority. Do not widen target/capability/operation. Do not treat `ALLOW` as a permit.

## Baseline gate

Reacquire live `master` HEAD/TREE and canonical truth subject before any mutation. If material drift exists, rebuild the candidate from the new master; do not transplant a stale patch.

## Required falsification

Deny at minimum: proposal substitution, PDP receipt/result substitution, stale policy/currentness, runtime identity substitution, target/operation/capability widening, RequestedRuntimeEffect payload substitution, replay, aggregate-budget bypass and any attempt to enter RuntimeAdmissionEngine without exact live authority/currentness evidence.

## Evidence/exit

Candidate passes only if targeted tests + full current Core + exact-head CI are green and effect surface inventory does not gain an unintended provider. Green CI is evidence, not merge authority. Stop at candidate/PR or any genuine external authority boundary.

````
LION_RECORD_END: SRC-V14C2-57ef89f7ff3e

<a id="src-v14c2-3ea0eeada919"></a>
## SRC-V14C2-3ea0eeada919 — v14c2/PACKAGE_MANIFEST.json

SOURCE_ID=SRC-V14C2-3ea0eeada919
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=PACKAGE_MANIFEST.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=967871c0c36584d0881915c65ed83a236117420912f69b5e2bfb7cdbb57bc323
SOURCE_BYTES=12066

LION_RECORD_BEGIN: SRC-V14C2-3ea0eeada919
LION_RECORD_META: {"anchor":"src-v14c2-3ea0eeada919","archive_id":"v14c2","authority_effect":"NONE","bytes":12066,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"PACKAGE_MANIFEST.json","sha256":"967871c0c36584d0881915c65ed83a236117420912f69b5e2bfb7cdbb57bc323","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-3ea0eeada919","virtual_path":"v14c2/PACKAGE_MANIFEST.json"}
````json
{
  "schema_version": "lion.package-manifest/v1.4-candidate",
  "package_id": "the-bean-factory-lion-evolution-v1.4-full-candidate-2026-09-07",
  "version": "1.4.0-candidate.2",
  "status": "DETACHED_CANDIDATE",
  "generated_at": "2026-09-07T15:25:55Z",
  "baseline": {
    "repository": "DonkeyJJLove/ai_platform",
    "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
    "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1",
    "truth_subject_digest": "d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726"
  },
  "source_corpus": {
    "rag40_files": 40,
    "v1_3_manifest_payloads": 58,
    "v1_3_digest_references": 60,
    "v1_3_total_topology": 61,
    "omitted_from_rag40": 21,
    "dropped_noncanonical_pyc": 2
  },
  "authority_effect": "NONE",
  "repository_effect": "NONE",
  "host_effect": "NONE",
  "can_claim_repository_canonical_supersession": false,
  "files": [
    {
      "path": "CONTRADICTION_REGISTER.json",
      "bytes": 4274,
      "sha256": "396529ded9026aac33c149a9ad0f905dccef086f92b0c46d2654e84c4c3184ba"
    },
    {
      "path": "EVIDENCE_INDEX.json",
      "bytes": 8013,
      "sha256": "06fdfc1db6880230eeec95ee9be9376dcd0f67d99efcee7926312373a28fe024"
    },
    {
      "path": "FLEET_AUTHORITY_MODEL_v1_4_candidate.source.md",
      "bytes": 1226,
      "sha256": "23ad65db115ae577146962a7608e583999925f5f317e572c2a2f32b2c2c18c3f"
    },
    {
      "path": "FLEET_FAILURE_MODEL_v1_4_candidate.source.md",
      "bytes": 1344,
      "sha256": "e2987f249bdcf2b9fc0b3c3dd0a0208d48a884157570f79ceee46d2702a3ccf3"
    },
    {
      "path": "LION_ABSTRACTION_COMPILER_v1_4_candidate.source.md",
      "bytes": 1478,
      "sha256": "b7e753d414a62d7bddb472d99b3878ee453073a2ec6c44c13c180278248fa119"
    },
    {
      "path": "LION_ACTION_IR_SCHEMA_v1_4_candidate.source.json",
      "bytes": 7549,
      "sha256": "b652180ea03b75add7e1357f210d6395aee8bae9b16361dca48eb84445c8b4ba"
    },
    {
      "path": "LION_ACTION_MODEL_v1_4_candidate.source.md",
      "bytes": 1372,
      "sha256": "93a482ec6af3d4f1b1292cd62fe3fd424df48ee882d1e1592a3a35edd7d6dbc1"
    },
    {
      "path": "LION_ARCHITECTURE_AS_IS_v1_4_candidate.source.md",
      "bytes": 2617,
      "sha256": "918c46edf4b81af9bd65700fe124d2d2b9228ce03effaf58f3ab4681e9a2a7ab"
    },
    {
      "path": "LION_ARCHITECTURE_CANDIDATE_v1_4_candidate.source.md",
      "bytes": 1544,
      "sha256": "fd0dcb14c9575825240b0dab03d706e0771d3655f11e26759ca782dfc2a4ee7d"
    },
    {
      "path": "LION_ARCHITECTURE_TARGET_v1_4_candidate.source.md",
      "bytes": 2008,
      "sha256": "e996cbe7c165e82dbbafd112909ba496ba381a753d77a6be4a7986154187e524"
    },
    {
      "path": "LION_ARCHITECTURE_v1_4_candidate.md",
      "bytes": 4281,
      "sha256": "94876dc13db525dc533fb6c0c804f19aeb2c563afee656bf607cf2b5d755780d"
    },
    {
      "path": "LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_4_candidate.source.json",
      "bytes": 5099,
      "sha256": "5d4d61043054b8fc3a97ccad54bd4920527a923075511f057dbe92b4c572c486"
    },
    {
      "path": "LION_AUTONOMY_BLUEPRINT_v1_4_candidate.source.md",
      "bytes": 1334,
      "sha256": "c6f2f6bd8686814890eeb23ed77f8b1be4ad85aab3e7eb754bf44a583d4f530d"
    },
    {
      "path": "LION_AUTONOMY_FACTORY_ROADMAP_v1_4_candidate.source.md",
      "bytes": 1422,
      "sha256": "fd65ce727311569f636a5f34d74cb26632a92f8e282279890975fe88c3c93010"
    },
    {
      "path": "LION_AUTONOMY_MODEL_v1_4_candidate.source.md",
      "bytes": 1211,
      "sha256": "8aaf1811e2252ceb7660a1a63630a14198b40ae51c195d6ba4427dee3336d272"
    },
    {
      "path": "LION_BEAN_MODEL_v1_4_candidate.source.md",
      "bytes": 1492,
      "sha256": "5385bfeaca3e4f89cb02bff8ef7945e3dd129c127c3bec2d6227f5372f2aaa8a"
    },
    {
      "path": "LION_CANONICAL_STATE_v1_4_candidate.source.json",
      "bytes": 4810,
      "sha256": "59086e3ff9de6b2d81928ff8455c64b97f7d7e4e45f6d38b6cf38e5ed846f072"
    },
    {
      "path": "LION_COMMAND_ADAPTER_REGISTRY_v1_4_candidate.source.json",
      "bytes": 1383,
      "sha256": "327e784deb63f3c83a3cd86649e1925df411b81637c1308c3c39767254d62e23"
    },
    {
      "path": "LION_COMMAND_MODELING_SYNTAX_v1_4_candidate.source.md",
      "bytes": 1320,
      "sha256": "daa9864b7d1505a38aeee2254f5d132cd5b60ded9de97123f290db14b140682d"
    },
    {
      "path": "LION_CYBER_PHYSICAL_ACTION_MODEL_v1_4_candidate.source.md",
      "bytes": 1150,
      "sha256": "e85b5016b73fad63cb2f07e804428b75278c556e4605ebf4af6b90d588a92b8a"
    },
    {
      "path": "LION_DOCUMENTATION_HOMEOSTASIS_MODEL_v1_4_candidate.source.md",
      "bytes": 1265,
      "sha256": "1bb577c753ca1fdfb1547edfe2777c4f18c32953348c1cce38351f5928211af1"
    },
    {
      "path": "LION_EVOLUTION_FULL_REPORT_2026-09-07_v1_4_candidate.md",
      "bytes": 3688,
      "sha256": "45273a1b41d77bf12de87b57b19622b3fb0e4a547d6eb520845051850b018d90"
    },
    {
      "path": "LION_EVOLUTION_ROADMAP_v1_4_candidate.source.md",
      "bytes": 1575,
      "sha256": "38db7b9d40af2ddb8a0d4ff9923deebf3e04e66de1e4ef9228886fd5acc53e21"
    },
    {
      "path": "LION_FACTORY_LINEAGE_REGISTER_v1_4_candidate.source.json",
      "bytes": 476,
      "sha256": "be79b29cbffc927a9bc86b04b8d3e72c6f31877d058e4f9f7251d4225258a588"
    },
    {
      "path": "LION_FACTORY_RECURSION_POLICY_v1_4_candidate.source.md",
      "bytes": 1124,
      "sha256": "1bfe79ab2eb3df59b4203ec95cf7d6d82cf3c301053f21ad5de3b30278f591b9"
    },
    {
      "path": "LION_FALSIFICATION_REGISTER_v1_4_candidate.source.json",
      "bytes": 2370,
      "sha256": "b0e241eb7a6cd3d1701148a454e87d3abef7dfff03518bcdc4278083514118cb"
    },
    {
      "path": "LION_FLEET_POLICY_v1_4_candidate.source.md",
      "bytes": 1103,
      "sha256": "c7f3011b8ce7c4c1cdb781758b85887377bd9db2aeda8eed4e4f6f0cfb3c70b8"
    },
    {
      "path": "LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_4_candidate.source.md",
      "bytes": 1308,
      "sha256": "554af12bdd65b35658e1296858b9f5c8bc44e133261f3be5ed22b76c52bbd0a9"
    },
    {
      "path": "LION_IMPLEMENTATION_STATUS_v1_4_candidate.source.json",
      "bytes": 4505,
      "sha256": "a07985a1f05985b210389412d3e60176691d8c24d62adc545960a160232e9718"
    },
    {
      "path": "LION_LOCAL_CONSOLE_PROTOCOL_v1_4_candidate.source.md",
      "bytes": 1284,
      "sha256": "a2e58784c72790deb0f0d5d7d40bfbf0404a05609f48b2cbbeb481827ce2718d"
    },
    {
      "path": "LION_LOCAL_OPENAI_LAB_PLAN_v1_4_candidate.source.md",
      "bytes": 1203,
      "sha256": "a1a789a44f1a4e96c32ad23b0b47cf162d3f1f11a2eb45425bce857b5d42ca19"
    },
    {
      "path": "LION_MATERIALIZER_REGISTRY_v1_4_candidate.source.json",
      "bytes": 1247,
      "sha256": "d88c11b73f1377bb267e48a7be59888102eaab4e180375c19eedcf9d5f53529e"
    },
    {
      "path": "LION_MODEL_PLANE_v1_4_candidate.source.md",
      "bytes": 1192,
      "sha256": "8ee61a4071028cc2e2d1fe93b0df86e7ab3ab76803fd33162353c4a60b8e7b50"
    },
    {
      "path": "LION_OPENAI_PROJECT_SOURCE_INDEX_v1_4_candidate.md",
      "bytes": 1332,
      "sha256": "f9cfc0d76141019e3f73583ee6c7bcf5dbd27c0c26e2f7336d4578c5046d8bdc"
    },
    {
      "path": "LION_PHYSICAL_SAFETY_INVARIANTS_v1_4_candidate.source.md",
      "bytes": 1187,
      "sha256": "14ead8fbb6a365325b278a3707214b3bf75c6a3728bb2308195d24affdf7717a"
    },
    {
      "path": "LION_POST_V1_3_DELTA_REGISTER_v1_4_candidate.source.json",
      "bytes": 3612,
      "sha256": "4f1239cf494447b3efb6302202e82645e9b486fc7a1e8796eed58561d0f09695"
    },
    {
      "path": "LION_PREPRODUCTION_ENTRY_CRITERIA_v1_4_candidate.source.md",
      "bytes": 1389,
      "sha256": "20fbbe241fa7f3f0138997aa90d602fc9799f1e8f66e4141e111161a6fc5119d"
    },
    {
      "path": "LION_PROJECT_CANONICAL_CONTEXT_v1_4_candidate.source.md",
      "bytes": 1563,
      "sha256": "f81fea99eb023ddfd7c4be450ae997806da7791a529b3cad95745d5061253f56"
    },
    {
      "path": "LION_RECONCILIATION_POLICY_v1_4_candidate.source.md",
      "bytes": 1145,
      "sha256": "92548eea3d91fc893ceecab4deb45c44c81b53ee6f53f7c923820ed5d24fdbc8"
    },
    {
      "path": "LION_REPOSITORY_FEDERATION_v1_4_candidate.source.json",
      "bytes": 4817,
      "sha256": "dece51cb822c993a278bf07a4fc2c4df03b69fad4ee08618c03ecfeb74ebe655"
    },
    {
      "path": "LION_ROBOTICS_LAB_PLAN_v1_4_candidate.source.md",
      "bytes": 1013,
      "sha256": "a815dc7c6ab9fc322571d79a44ad1b539841b3dc0e21019c0b62028c3bd795a2"
    },
    {
      "path": "LION_SUPERSESSION_REGISTER_v1_4_candidate.source.json",
      "bytes": 2033,
      "sha256": "3e7c6bacaf17465156900f61eed6866d399f09b76fa7f471a4226aaa661423b2"
    },
    {
      "path": "NEXT_EXECUTION_PROMPT.md",
      "bytes": 1711,
      "sha256": "5ca467c156df04910bcd631c53dcdbcc90d05ef963b99b66dbd5a2e9d28b5b5e"
    },
    {
      "path": "PREPRODUCTION_BLOCKERS.json",
      "bytes": 4181,
      "sha256": "5695bf482c9a130447f85bf8d273aededa78c2664848975353a270774918cbfd"
    },
    {
      "path": "README.md",
      "bytes": 1463,
      "sha256": "19421b0239252ed59116be107c196a9ca356a86528878a855ba61b5344834617"
    },
    {
      "path": "ROADMAP.json",
      "bytes": 5161,
      "sha256": "697c2748968cd6edc5b5a9ef1359e28d15004f1efbe7dcd0ab349869f40960d0"
    },
    {
      "path": "SUPERSESSION_REGISTER.json",
      "bytes": 2109,
      "sha256": "1849534fb9c3a5ea5c70317bcee4286e3200443e88893517e65607a0bb2518ce"
    },
    {
      "path": "THE_BEAN_FACTORY_CANONICAL_MODEL_v1_4_candidate.source.md",
      "bytes": 1404,
      "sha256": "14cb62a7841a934322f98053b93145f9d67774a2397f12153db74eeb18deb627"
    },
    {
      "path": "UPGRADE_DECISION_REGISTER.json",
      "bytes": 24534,
      "sha256": "1911f1ae7b7096610b9b33def7a8d80383bf6cea45069cc6a727ea49c45ffd0e"
    },
    {
      "path": "V1_3_SOURCE_INVENTORY.json",
      "bytes": 16972,
      "sha256": "0a19534fa36ab90c08e921e611a0aa89669ec9a40098c4a095dc51002ccd6259"
    },
    {
      "path": "carried_forward/LION_BEAN_SCHEMA_v1_3_candidate.source.json",
      "bytes": 2942,
      "sha256": "5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428"
    },
    {
      "path": "evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md",
      "bytes": 409,
      "sha256": "3ba6fb37c90ce012631a58415af732b1905380e71cde1af7c2e4e891e82880a5"
    },
    {
      "path": "evidence/GITHUB_BASELINES.json",
      "bytes": 2146,
      "sha256": "806e6e15d660ed965646bf03deabb13acee04ba001186321d3088736cb988eb3"
    },
    {
      "path": "evidence/HOST_CENSUS_SUMMARY.json",
      "bytes": 1319,
      "sha256": "e3ce9bd7778dcb8ac68d239607682f151a33c0967e3cb39bf9c701067a657f3d"
    },
    {
      "path": "evidence/OPENAI_LOCAL_MODEL_RESEARCH.md",
      "bytes": 401,
      "sha256": "7f11bf1f026b1e85655d89b865371af65cb7deb284ab252b95b62a0253010b09"
    },
    {
      "path": "scaffold/README.md",
      "bytes": 270,
      "sha256": "650443b5ec247b2ff428f901288e31efe040a9f320b708f930443ca2c650a6e6"
    },
    {
      "path": "scaffold/action_ir.schema.json",
      "bytes": 7549,
      "sha256": "b652180ea03b75add7e1357f210d6395aee8bae9b16361dca48eb84445c8b4ba"
    },
    {
      "path": "scaffold/canonical_state.schema.json",
      "bytes": 1685,
      "sha256": "36838127548d5f9802a286deb2c76bb161e7a9af0b55bc1974210b04ef21437e"
    },
    {
      "path": "scaffold/lcms.ebnf",
      "bytes": 899,
      "sha256": "23c51c14742ec5f48e1335f711b2891f1f66f19118338f12bf1b09ffb4be9b2f"
    },
    {
      "path": "scaffold/test_validate_canonical_state.py",
      "bytes": 663,
      "sha256": "0c65a5729d39e908f01a42d6ba6cce7c68136818b3332ed968f4489c08d50017"
    },
    {
      "path": "scaffold/validate_canonical_state.py",
      "bytes": 1230,
      "sha256": "6fde7eb98978587810ee1964ade4c8d1e6e24b71a0159f7e000ef17054329307"
    }
  ],
  "verification_report_sha256": "670dbe68a6006fbf69d92ea99b53c283dcd7fd3042959e5b618b57ecba60fd6c",
  "source_digests_sha256": "0efb096c0cdcd8289762d445c4e1d130ab12e59cd69195ca9c91f001f964561d",
  "package_file_count_including_manifest_verification_digests": 64
}

````
LION_RECORD_END: SRC-V14C2-3ea0eeada919

<a id="src-v14c2-b33563055168"></a>
## SRC-V14C2-b33563055168 — v14c2/README.md

SOURCE_ID=SRC-V14C2-b33563055168
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=README.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=19421b0239252ed59116be107c196a9ca356a86528878a855ba61b5344834617
SOURCE_BYTES=1463

LION_RECORD_BEGIN: SRC-V14C2-b33563055168
LION_RECORD_META: {"anchor":"src-v14c2-b33563055168","archive_id":"v14c2","authority_effect":"NONE","bytes":1463,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"README.md","sha256":"19421b0239252ed59116be107c196a9ca356a86528878a855ba61b5344834617","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-b33563055168","virtual_path":"v14c2/README.md"}
````markdown
# THE BEAN FACTORY / LION EVOLUTION — v1.4 FULL detached candidate package

**Version:** `1.4.0-candidate.2`  
**Generated:** `2026-09-07T15:25:55Z`  
**Baseline:** `DonkeyJJLove/ai_platform@5d5a02b37fdfff4bcbf62f455d37ce4b86080f59`  
**Tree:** `9725bebf8d9766c58096cfc34af06ffcb8aa32f1`  
**Authority effect:** none  
**Repository/host mutation:** none

## Why this package is `FULL`

The uploaded `LION_PROJECT_RAG_40_v1_3.zip` contains 40 files, but its own manifest/digest topology describes 61 total v1.3 package artifacts. This package audits all 61 lineage slots. The 21 omitted slots are recorded explicitly; two `.pyc` cache files are dropped, not treated as documentation.

## Main architectural result

LION is now integrated through canonical `ActionProposal → PDPResult`. The current first unfinished boundary is `PDPResult(ALLOW) → exact RequestedRuntimeEffect + runtime identity → RuntimeAdmissionEngine`. The bounded B0 two-family terminal generativity protocol is `PASS`; general Factory generativity is still `NOT_PROVEN`.

Start with:

- `LION_ARCHITECTURE_v1_4_candidate.md`
- `LION_EVOLUTION_FULL_REPORT_2026-09-07_v1_4_candidate.md`
- `V1_3_SOURCE_INVENTORY.json`
- `UPGRADE_DECISION_REGISTER.json`
- `EVIDENCE_INDEX.json`
- `CONTRADICTION_REGISTER.json`
- `ROADMAP.json`
- `NEXT_EXECUTION_PROMPT.md`

This package supersedes the earlier incomplete v1.4 **analysis artifact**, not repository canonical state or production authority.

````
LION_RECORD_END: SRC-V14C2-b33563055168

<a id="src-v14c2-9f327044bc6a"></a>
## SRC-V14C2-9f327044bc6a — v14c2/SOURCE_DIGESTS.sha256

SOURCE_ID=SRC-V14C2-9f327044bc6a
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=SOURCE_DIGESTS.sha256
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=f6c3df4ef32e97e1518990d5dbf5647ffc9b8822e3af4695f8452e1728493575
SOURCE_BYTES=6938

LION_RECORD_BEGIN: SRC-V14C2-9f327044bc6a
LION_RECORD_META: {"anchor":"src-v14c2-9f327044bc6a","archive_id":"v14c2","authority_effect":"NONE","bytes":6938,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"text","original_path":"SOURCE_DIGESTS.sha256","sha256":"f6c3df4ef32e97e1518990d5dbf5647ffc9b8822e3af4695f8452e1728493575","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-9f327044bc6a","virtual_path":"v14c2/SOURCE_DIGESTS.sha256"}
````text
396529ded9026aac33c149a9ad0f905dccef086f92b0c46d2654e84c4c3184ba  CONTRADICTION_REGISTER.json
06fdfc1db6880230eeec95ee9be9376dcd0f67d99efcee7926312373a28fe024  EVIDENCE_INDEX.json
23ad65db115ae577146962a7608e583999925f5f317e572c2a2f32b2c2c18c3f  FLEET_AUTHORITY_MODEL_v1_4_candidate.source.md
e2987f249bdcf2b9fc0b3c3dd0a0208d48a884157570f79ceee46d2702a3ccf3  FLEET_FAILURE_MODEL_v1_4_candidate.source.md
b7e753d414a62d7bddb472d99b3878ee453073a2ec6c44c13c180278248fa119  LION_ABSTRACTION_COMPILER_v1_4_candidate.source.md
b652180ea03b75add7e1357f210d6395aee8bae9b16361dca48eb84445c8b4ba  LION_ACTION_IR_SCHEMA_v1_4_candidate.source.json
93a482ec6af3d4f1b1292cd62fe3fd424df48ee882d1e1592a3a35edd7d6dbc1  LION_ACTION_MODEL_v1_4_candidate.source.md
918c46edf4b81af9bd65700fe124d2d2b9228ce03effaf58f3ab4681e9a2a7ab  LION_ARCHITECTURE_AS_IS_v1_4_candidate.source.md
fd0dcb14c9575825240b0dab03d706e0771d3655f11e26759ca782dfc2a4ee7d  LION_ARCHITECTURE_CANDIDATE_v1_4_candidate.source.md
e996cbe7c165e82dbbafd112909ba496ba381a753d77a6be4a7986154187e524  LION_ARCHITECTURE_TARGET_v1_4_candidate.source.md
94876dc13db525dc533fb6c0c804f19aeb2c563afee656bf607cf2b5d755780d  LION_ARCHITECTURE_v1_4_candidate.md
5d4d61043054b8fc3a97ccad54bd4920527a923075511f057dbe92b4c572c486  LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_4_candidate.source.json
c6f2f6bd8686814890eeb23ed77f8b1be4ad85aab3e7eb754bf44a583d4f530d  LION_AUTONOMY_BLUEPRINT_v1_4_candidate.source.md
fd65ce727311569f636a5f34d74cb26632a92f8e282279890975fe88c3c93010  LION_AUTONOMY_FACTORY_ROADMAP_v1_4_candidate.source.md
8aaf1811e2252ceb7660a1a63630a14198b40ae51c195d6ba4427dee3336d272  LION_AUTONOMY_MODEL_v1_4_candidate.source.md
5385bfeaca3e4f89cb02bff8ef7945e3dd129c127c3bec2d6227f5372f2aaa8a  LION_BEAN_MODEL_v1_4_candidate.source.md
59086e3ff9de6b2d81928ff8455c64b97f7d7e4e45f6d38b6cf38e5ed846f072  LION_CANONICAL_STATE_v1_4_candidate.source.json
327e784deb63f3c83a3cd86649e1925df411b81637c1308c3c39767254d62e23  LION_COMMAND_ADAPTER_REGISTRY_v1_4_candidate.source.json
daa9864b7d1505a38aeee2254f5d132cd5b60ded9de97123f290db14b140682d  LION_COMMAND_MODELING_SYNTAX_v1_4_candidate.source.md
e85b5016b73fad63cb2f07e804428b75278c556e4605ebf4af6b90d588a92b8a  LION_CYBER_PHYSICAL_ACTION_MODEL_v1_4_candidate.source.md
1bb577c753ca1fdfb1547edfe2777c4f18c32953348c1cce38351f5928211af1  LION_DOCUMENTATION_HOMEOSTASIS_MODEL_v1_4_candidate.source.md
45273a1b41d77bf12de87b57b19622b3fb0e4a547d6eb520845051850b018d90  LION_EVOLUTION_FULL_REPORT_2026-09-07_v1_4_candidate.md
38db7b9d40af2ddb8a0d4ff9923deebf3e04e66de1e4ef9228886fd5acc53e21  LION_EVOLUTION_ROADMAP_v1_4_candidate.source.md
be79b29cbffc927a9bc86b04b8d3e72c6f31877d058e4f9f7251d4225258a588  LION_FACTORY_LINEAGE_REGISTER_v1_4_candidate.source.json
1bfe79ab2eb3df59b4203ec95cf7d6d82cf3c301053f21ad5de3b30278f591b9  LION_FACTORY_RECURSION_POLICY_v1_4_candidate.source.md
b0e241eb7a6cd3d1701148a454e87d3abef7dfff03518bcdc4278083514118cb  LION_FALSIFICATION_REGISTER_v1_4_candidate.source.json
c7f3011b8ce7c4c1cdb781758b85887377bd9db2aeda8eed4e4f6f0cfb3c70b8  LION_FLEET_POLICY_v1_4_candidate.source.md
554af12bdd65b35658e1296858b9f5c8bc44e133261f3be5ed22b76c52bbd0a9  LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_4_candidate.source.md
a07985a1f05985b210389412d3e60176691d8c24d62adc545960a160232e9718  LION_IMPLEMENTATION_STATUS_v1_4_candidate.source.json
a2e58784c72790deb0f0d5d7d40bfbf0404a05609f48b2cbbeb481827ce2718d  LION_LOCAL_CONSOLE_PROTOCOL_v1_4_candidate.source.md
a1a789a44f1a4e96c32ad23b0b47cf162d3f1f11a2eb45425bce857b5d42ca19  LION_LOCAL_OPENAI_LAB_PLAN_v1_4_candidate.source.md
d88c11b73f1377bb267e48a7be59888102eaab4e180375c19eedcf9d5f53529e  LION_MATERIALIZER_REGISTRY_v1_4_candidate.source.json
8ee61a4071028cc2e2d1fe93b0df86e7ab3ab76803fd33162353c4a60b8e7b50  LION_MODEL_PLANE_v1_4_candidate.source.md
f9cfc0d76141019e3f73583ee6c7bcf5dbd27c0c26e2f7336d4578c5046d8bdc  LION_OPENAI_PROJECT_SOURCE_INDEX_v1_4_candidate.md
14ead8fbb6a365325b278a3707214b3bf75c6a3728bb2308195d24affdf7717a  LION_PHYSICAL_SAFETY_INVARIANTS_v1_4_candidate.source.md
4f1239cf494447b3efb6302202e82645e9b486fc7a1e8796eed58561d0f09695  LION_POST_V1_3_DELTA_REGISTER_v1_4_candidate.source.json
20fbbe241fa7f3f0138997aa90d602fc9799f1e8f66e4141e111161a6fc5119d  LION_PREPRODUCTION_ENTRY_CRITERIA_v1_4_candidate.source.md
f81fea99eb023ddfd7c4be450ae997806da7791a529b3cad95745d5061253f56  LION_PROJECT_CANONICAL_CONTEXT_v1_4_candidate.source.md
92548eea3d91fc893ceecab4deb45c44c81b53ee6f53f7c923820ed5d24fdbc8  LION_RECONCILIATION_POLICY_v1_4_candidate.source.md
dece51cb822c993a278bf07a4fc2c4df03b69fad4ee08618c03ecfeb74ebe655  LION_REPOSITORY_FEDERATION_v1_4_candidate.source.json
a815dc7c6ab9fc322571d79a44ad1b539841b3dc0e21019c0b62028c3bd795a2  LION_ROBOTICS_LAB_PLAN_v1_4_candidate.source.md
3e7c6bacaf17465156900f61eed6866d399f09b76fa7f471a4226aaa661423b2  LION_SUPERSESSION_REGISTER_v1_4_candidate.source.json
5ca467c156df04910bcd631c53dcdbcc90d05ef963b99b66dbd5a2e9d28b5b5e  NEXT_EXECUTION_PROMPT.md
967871c0c36584d0881915c65ed83a236117420912f69b5e2bfb7cdbb57bc323  PACKAGE_MANIFEST.json
5695bf482c9a130447f85bf8d273aededa78c2664848975353a270774918cbfd  PREPRODUCTION_BLOCKERS.json
19421b0239252ed59116be107c196a9ca356a86528878a855ba61b5344834617  README.md
697c2748968cd6edc5b5a9ef1359e28d15004f1efbe7dcd0ab349869f40960d0  ROADMAP.json
1849534fb9c3a5ea5c70317bcee4286e3200443e88893517e65607a0bb2518ce  SUPERSESSION_REGISTER.json
14cb62a7841a934322f98053b93145f9d67774a2397f12153db74eeb18deb627  THE_BEAN_FACTORY_CANONICAL_MODEL_v1_4_candidate.source.md
1911f1ae7b7096610b9b33def7a8d80383bf6cea45069cc6a727ea49c45ffd0e  UPGRADE_DECISION_REGISTER.json
0a19534fa36ab90c08e921e611a0aa89669ec9a40098c4a095dc51002ccd6259  V1_3_SOURCE_INVENTORY.json
670dbe68a6006fbf69d92ea99b53c283dcd7fd3042959e5b618b57ecba60fd6c  VERIFICATION_REPORT.json
5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428  carried_forward/LION_BEAN_SCHEMA_v1_3_candidate.source.json
3ba6fb37c90ce012631a58415af732b1905380e71cde1af7c2e4e891e82880a5  evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md
806e6e15d660ed965646bf03deabb13acee04ba001186321d3088736cb988eb3  evidence/GITHUB_BASELINES.json
e3ce9bd7778dcb8ac68d239607682f151a33c0967e3cb39bf9c701067a657f3d  evidence/HOST_CENSUS_SUMMARY.json
7f11bf1f026b1e85655d89b865371af65cb7deb284ab252b95b62a0253010b09  evidence/OPENAI_LOCAL_MODEL_RESEARCH.md
650443b5ec247b2ff428f901288e31efe040a9f320b708f930443ca2c650a6e6  scaffold/README.md
b652180ea03b75add7e1357f210d6395aee8bae9b16361dca48eb84445c8b4ba  scaffold/action_ir.schema.json
36838127548d5f9802a286deb2c76bb161e7a9af0b55bc1974210b04ef21437e  scaffold/canonical_state.schema.json
23c51c14742ec5f48e1335f711b2891f1f66f19118338f12bf1b09ffb4be9b2f  scaffold/lcms.ebnf
0c65a5729d39e908f01a42d6ba6cce7c68136818b3332ed968f4489c08d50017  scaffold/test_validate_canonical_state.py
6fde7eb98978587810ee1964ade4c8d1e6e24b71a0159f7e000ef17054329307  scaffold/validate_canonical_state.py

````
LION_RECORD_END: SRC-V14C2-9f327044bc6a

<a id="src-v14c2-96107301464b"></a>
## SRC-V14C2-96107301464b — v14c2/UPGRADE_DECISION_REGISTER.json

SOURCE_ID=SRC-V14C2-96107301464b
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=UPGRADE_DECISION_REGISTER.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=1911f1ae7b7096610b9b33def7a8d80383bf6cea45069cc6a727ea49c45ffd0e
SOURCE_BYTES=24534

LION_RECORD_BEGIN: SRC-V14C2-96107301464b
LION_RECORD_META: {"anchor":"src-v14c2-96107301464b","archive_id":"v14c2","authority_effect":"NONE","bytes":24534,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"UPGRADE_DECISION_REGISTER.json","sha256":"1911f1ae7b7096610b9b33def7a8d80383bf6cea45069cc6a727ea49c45ffd0e","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-96107301464b","virtual_path":"v14c2/UPGRADE_DECISION_REGISTER.json"}
````json
{
  "schema_version": "lion.upgrade-decision-register/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "source_topology_count": 61,
  "decisions": [
    {
      "path": "CONTRADICTION_REGISTER.json",
      "present_in_rag40": true,
      "sha256_v1_3": "36bfaf6a9e9edff0b07738924c48fea2e656391425ad1070b26dd6e7f96b24e5",
      "bytes_v1_3": 3903,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "CONTRADICTION_REGISTER.json"
    },
    {
      "path": "EVIDENCE_INDEX.json",
      "present_in_rag40": true,
      "sha256_v1_3": "5bcd55fa15d70b3aeff9d3301953dbffe1b6bde936700f0a40482a45a07c1216",
      "bytes_v1_3": 13515,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "EVIDENCE_INDEX.json"
    },
    {
      "path": "FLEET_AUTHORITY_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "721f60b5158df879e31d5707234a00ca146fafc63ca5957f00e43ee528d7cbc7",
      "bytes_v1_3": 884,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "FLEET_AUTHORITY_MODEL_v1_4_candidate.source.md"
    },
    {
      "path": "FLEET_FAILURE_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "d62e6c378f971b2100c34c281804c3e46e2fddab858e3e223500690293b5ef68",
      "bytes_v1_3": 1177,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "FLEET_FAILURE_MODEL_v1_4_candidate.source.md"
    },
    {
      "path": "LION_ABSTRACTION_COMPILER_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "c0366be0a9e0c95cd08f69cef9751db3650a0c9f444bec65dafff30f5ec2400d",
      "bytes_v1_3": 1082,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_ABSTRACTION_COMPILER_v1_4_candidate.source.md"
    },
    {
      "path": "LION_ACTION_IR_SCHEMA_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5",
      "bytes_v1_3": 6967,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_ACTION_IR_SCHEMA_v1_4_candidate.source.json"
    },
    {
      "path": "LION_ACTION_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "1d67d01a40769e3d0854f819061b47028ef7ff6a645ce288aed7c10740db17f3",
      "bytes_v1_3": 1045,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_ACTION_MODEL_v1_4_candidate.source.md"
    },
    {
      "path": "LION_ARCHITECTURE_AS_IS_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "5497644ceff77d3085d6562b0ff588746a7c05dd1f13e96f75a67655ff956aba",
      "bytes_v1_3": 1513,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_ARCHITECTURE_AS_IS_v1_4_candidate.source.md"
    },
    {
      "path": "LION_ARCHITECTURE_CANDIDATE_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "fd426ef9b6d8fb6f1348bd8703e5404d7cbb8f36b4277c0348381b9a4ef0462a",
      "bytes_v1_3": 1206,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_ARCHITECTURE_CANDIDATE_v1_4_candidate.source.md"
    },
    {
      "path": "LION_ARCHITECTURE_TARGET_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "dcd22324c4b88a52bd525cf2bcd6553ad9db35b9ecbedd4ccf8c13141bdae3bf",
      "bytes_v1_3": 1331,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_ARCHITECTURE_TARGET_v1_4_candidate.source.md"
    },
    {
      "path": "LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json",
      "present_in_rag40": false,
      "sha256_v1_3": "b6dc2786355a1d4294e6ed828219bcadacbeec2515bbb091c43eb1b8da7b4f4e",
      "bytes_v1_3": 3683,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_4_candidate.source.json"
    },
    {
      "path": "LION_AUTONOMY_BLUEPRINT_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "85666d2148cbdb2b06ae8315728791c35a265dfb22c770ad1273250fe9667106",
      "bytes_v1_3": 982,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_AUTONOMY_BLUEPRINT_v1_4_candidate.source.md"
    },
    {
      "path": "LION_AUTONOMY_FACTORY_ROADMAP_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "ec58a037a7003a461529ce29a6041ac6029a78faf1e227bab638e6e83c3cdc49",
      "bytes_v1_3": 909,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_AUTONOMY_FACTORY_ROADMAP_v1_4_candidate.source.md"
    },
    {
      "path": "LION_AUTONOMY_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "812bed9b998b2edaf836003369039ba15b11e19898e6e7cacde55983399baaa8",
      "bytes_v1_3": 985,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_AUTONOMY_MODEL_v1_4_candidate.source.md"
    },
    {
      "path": "LION_BEAN_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "239892f742a9d972e0ea99620fbfa5814a912fe3f083efe78f968fbbf993e21d",
      "bytes_v1_3": 1281,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_BEAN_MODEL_v1_4_candidate.source.md"
    },
    {
      "path": "LION_BEAN_SCHEMA_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428",
      "bytes_v1_3": 2942,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "CARRY_FORWARD_EXACT_CONTRACT",
      "successor": "carried_forward/LION_BEAN_SCHEMA_v1_3_candidate.source.json"
    },
    {
      "path": "LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json",
      "present_in_rag40": false,
      "sha256_v1_3": "86c4f338f39f08b16fb1d0b8fd8ef33db2b565b50350158c07f9a23dfd4aa0f0",
      "bytes_v1_3": 1187,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "LION_COMMAND_ADAPTER_REGISTRY_v1_4_candidate.source.json"
    },
    {
      "path": "LION_COMMAND_MODELING_SYNTAX_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "a40165ccc280ed789b2249edb5fece4679cd0372be9452cda161cae9d393ac8d",
      "bytes_v1_3": 924,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_COMMAND_MODELING_SYNTAX_v1_4_candidate.source.md"
    },
    {
      "path": "LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "882d682242c59d2e1c982288c855e7496858cdecd5b4b229b07baefa2cec40b0",
      "bytes_v1_3": 1004,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "LION_CYBER_PHYSICAL_ACTION_MODEL_v1_4_candidate.source.md"
    },
    {
      "path": "LION_EVOLUTION_FULL_REPORT_2026-09-02.md",
      "present_in_rag40": true,
      "sha256_v1_3": "595fe690dab18f0aed938d1a3e3e839288092d8b3007d40b30d673f9450bd7c2",
      "bytes_v1_3": 38459,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_EVOLUTION_FULL_REPORT_2026-09-07_v1_4_candidate.md"
    },
    {
      "path": "LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "0f94b207eb817ae21a174b5966660da4760f7f7f97eb89831f59e30912fa50e6",
      "bytes_v1_3": 5650,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "LION_EVOLUTION_ROADMAP_v1_4_candidate.source.md"
    },
    {
      "path": "LION_FACTORY_LINEAGE_REGISTER_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "3c977116ea14fba0f16715977944de7661413820cc4985595798e51dfd3baf6f",
      "bytes_v1_3": 244,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_FACTORY_LINEAGE_REGISTER_v1_4_candidate.source.json"
    },
    {
      "path": "LION_FACTORY_RECURSION_POLICY_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "cb1fb6d155a9b4526e93d47d9f693aa39dfcd23b20176e437de5cce90c6212bc",
      "bytes_v1_3": 1040,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_FACTORY_RECURSION_POLICY_v1_4_candidate.source.md"
    },
    {
      "path": "LION_FALSIFICATION_REGISTER_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "2e750ef18c13c234f323e0e5ed33712399a84e14bf0c9591f2e5f97648e333c6",
      "bytes_v1_3": 2434,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_FALSIFICATION_REGISTER_v1_4_candidate.source.json"
    },
    {
      "path": "LION_FLEET_POLICY_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "d9990df3c1caffc6aad725876940b369df3d4f2c109ef64b1b981278ed19e48f",
      "bytes_v1_3": 985,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_FLEET_POLICY_v1_4_candidate.source.md"
    },
    {
      "path": "LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "f2731e226a16fe6e2d887d82a2c610dfb4c202c18e34ca94f106c02ae8b18a86",
      "bytes_v1_3": 967,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_4_candidate.source.md"
    },
    {
      "path": "LION_IMPLEMENTATION_STATUS_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "eac79a9922134665ce9e053949e51ce4b8c8a9fabe3b4638e0dd84877511eeb8",
      "bytes_v1_3": 5738,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_IMPLEMENTATION_STATUS_v1_4_candidate.source.json"
    },
    {
      "path": "LION_LOCAL_CONSOLE_PROTOCOL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "f213ac23ce3dfd98bc8df6378a6153093f5590d645c61694a5a76b7b6c10cc3f",
      "bytes_v1_3": 1058,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_LOCAL_CONSOLE_PROTOCOL_v1_4_candidate.source.md"
    },
    {
      "path": "LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "84a0c1b6065befa868e66d2038cb59cf989283dfc74abd550e9db067b403029c",
      "bytes_v1_3": 1138,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "LION_LOCAL_OPENAI_LAB_PLAN_v1_4_candidate.source.md"
    },
    {
      "path": "LION_MATERIALIZER_REGISTRY_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "fbaf330fd571dcc294288feaea624125d0bbf1af1ba1f8b8b4fcbc8b7a5c6642",
      "bytes_v1_3": 1616,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_MATERIALIZER_REGISTRY_v1_4_candidate.source.json"
    },
    {
      "path": "LION_MODEL_PLANE_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "54efb77e01db8a8b417d3091f9ee4b2e20c5014de6dd17c346fe6861547d5101",
      "bytes_v1_3": 934,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "LION_MODEL_PLANE_v1_4_candidate.source.md"
    },
    {
      "path": "LION_OPENAI_PROJECT_SOURCE_INDEX_v1_3_candidate.md",
      "present_in_rag40": true,
      "sha256_v1_3": "10ec000c31fccf63f9d93996181433070f2c499757001c4772ee148bb28ba240",
      "bytes_v1_3": 1116,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_OPENAI_PROJECT_SOURCE_INDEX_v1_4_candidate.md"
    },
    {
      "path": "LION_PHYSICAL_SAFETY_INVARIANTS_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "9fae4aabfcec3cd358cac3d11b4c39875597bce398aa85e80cf325708a51000e",
      "bytes_v1_3": 1057,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_PHYSICAL_SAFETY_INVARIANTS_v1_4_candidate.source.md"
    },
    {
      "path": "LION_POST_V1_2_DELTA_REGISTER_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "db5022d74dbdc79e0630e77e967d5801c9f2286fa14627ace779dd596651bcd3",
      "bytes_v1_3": 7068,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_POST_V1_3_DELTA_REGISTER_v1_4_candidate.source.json"
    },
    {
      "path": "LION_PREPRODUCTION_ENTRY_CRITERIA_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "d266bae4a2b27e6bd9900e24eff9a935fd1a91c67d1118e5742a759964870989",
      "bytes_v1_3": 1156,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_PREPRODUCTION_ENTRY_CRITERIA_v1_4_candidate.source.md"
    },
    {
      "path": "LION_PROJECT_CANONICAL_CONTEXT_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "ff3d3c39f33c228da2375cbe184bd7261fac7cf3364ab44bdb99b5ff19842123",
      "bytes_v1_3": 1633,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_PROJECT_CANONICAL_CONTEXT_v1_4_candidate.source.md"
    },
    {
      "path": "LION_RECONCILIATION_POLICY_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "6755583487a128e55808bd89fb1e57a6108116e83179630cfe4ed2e82be38713",
      "bytes_v1_3": 1025,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_RECONCILIATION_POLICY_v1_4_candidate.source.md"
    },
    {
      "path": "LION_REPOSITORY_FEDERATION_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "d9af756f9d2ce1789ac281026f05a2e42d61c92f8fc7fb89abeae668e8e61b8d",
      "bytes_v1_3": 6573,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_REPOSITORY_FEDERATION_v1_4_candidate.source.json"
    },
    {
      "path": "LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "ee910bfbd5f7957c8463d6720ab4dbd1e857b8418a79024637fbd334f470b45e",
      "bytes_v1_3": 963,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "LION_ROBOTICS_LAB_PLAN_v1_4_candidate.source.md"
    },
    {
      "path": "LION_SUPERSESSION_REGISTER_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988",
      "bytes_v1_3": 1198,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "LION_SUPERSESSION_REGISTER_v1_4_candidate.source.json"
    },
    {
      "path": "NEXT_EXECUTION_PROMPT.md",
      "present_in_rag40": false,
      "sha256_v1_3": "459ccd27b16504ee374753034d153d397cf6abf5f3e63fbb4a41875b3523839a",
      "bytes_v1_3": 3922,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "NEXT_EXECUTION_PROMPT.md"
    },
    {
      "path": "PACKAGE_MANIFEST.json",
      "present_in_rag40": true,
      "sha256_v1_3": "410da9da1265de7365a181e23472cc73a997429007ee9b5c73d9238ae98bae94",
      "bytes_v1_3": null,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "PACKAGE_MANIFEST.json"
    },
    {
      "path": "PREPRODUCTION_BLOCKERS.json",
      "present_in_rag40": true,
      "sha256_v1_3": "c775e4ad6db6edfc4c3c283b68dea61d087073e11ed24a484c68ad1dd2924689",
      "bytes_v1_3": 4781,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "PREPRODUCTION_BLOCKERS.json"
    },
    {
      "path": "README.md",
      "present_in_rag40": true,
      "sha256_v1_3": "7f06df0486ae55882e1eaf8357900112f34c34348f4cb6118efa8ed4b7673750",
      "bytes_v1_3": 1139,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "README.md"
    },
    {
      "path": "ROADMAP.json",
      "present_in_rag40": true,
      "sha256_v1_3": "cc5a6bcc67d2158d7ca5007c9ede8d91e20332e740dc3a47f53d7ff60d69166d",
      "bytes_v1_3": 6901,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "ROADMAP.json"
    },
    {
      "path": "SOURCE_DIGESTS.sha256",
      "present_in_rag40": true,
      "sha256_v1_3": null,
      "bytes_v1_3": null,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "SOURCE_DIGESTS.sha256"
    },
    {
      "path": "SUPERSESSION_REGISTER.json",
      "present_in_rag40": false,
      "sha256_v1_3": "b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988",
      "bytes_v1_3": 1198,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "SUPERSESSION_REGISTER.json"
    },
    {
      "path": "THE_BEAN_FACTORY_CANONICAL_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "5131c8a6f40ce1cbf145e76d17f29ef6fce796565981c9b43e5855b621a7ecc5",
      "bytes_v1_3": 1251,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "THE_BEAN_FACTORY_CANONICAL_MODEL_v1_4_candidate.source.md"
    },
    {
      "path": "VERIFICATION_REPORT.json",
      "present_in_rag40": true,
      "sha256_v1_3": "1e82c81988a9b559382a78b2e46ce33c8572be2e476b1d8343126d7d9e838d70",
      "bytes_v1_3": null,
      "treatment": "SOURCE_PRESENT_REVIEWED",
      "decision": "UPGRADE_OR_RECONCILE",
      "successor": "VERIFICATION_REPORT.json"
    },
    {
      "path": "evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md",
      "present_in_rag40": false,
      "sha256_v1_3": "21b284687e9f34d1e98cbf98e3818bc8f9871bc15545fcfa4dbf135a9145b5c1",
      "bytes_v1_3": 841,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md"
    },
    {
      "path": "evidence/GITHUB_BASELINES.json",
      "present_in_rag40": false,
      "sha256_v1_3": "848f564b94f31933b1c0550ec511e4108447e12254c0f8c8a732926e0f28265e",
      "bytes_v1_3": 7337,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "evidence/GITHUB_BASELINES.json"
    },
    {
      "path": "evidence/HOST_CENSUS_SUMMARY.json",
      "present_in_rag40": false,
      "sha256_v1_3": "d31111ae8ce05bea387e5cb117b6e98b901be6ecf43ef9e9e150bd5f9096b880",
      "bytes_v1_3": 2520,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "evidence/HOST_CENSUS_SUMMARY.json"
    },
    {
      "path": "evidence/OPENAI_LOCAL_MODEL_RESEARCH.md",
      "present_in_rag40": false,
      "sha256_v1_3": "38f238580c92caed1e0b339a1e0b45b433ac7f43762f8396466bf70e4c1f4b02",
      "bytes_v1_3": 790,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "evidence/OPENAI_LOCAL_MODEL_RESEARCH.md"
    },
    {
      "path": "scaffold/README.md",
      "present_in_rag40": false,
      "sha256_v1_3": "d87e2c4b5ea9622a40ce307273742b533e78e0d191b9b72b1e47fa2313583c99",
      "bytes_v1_3": 806,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "scaffold/README.md"
    },
    {
      "path": "scaffold/__pycache__/test_validate_canonical_state.cpython-313.pyc",
      "present_in_rag40": false,
      "sha256_v1_3": "8a67d01ee897d4b0b6b4a2188985a26b0854b55d5827bf5b15d689d0c8848e97",
      "bytes_v1_3": 5260,
      "treatment": "DROP_NONCANONICAL_CACHE",
      "decision": "DROP_NONCANONICAL_CACHE",
      "successor": null
    },
    {
      "path": "scaffold/__pycache__/validate_canonical_state.cpython-313.pyc",
      "present_in_rag40": false,
      "sha256_v1_3": "ea58beefeefc87f48b79e2a25b34877cf5af0dbef8eaa96ebfe13d5d7697a4f6",
      "bytes_v1_3": 7083,
      "treatment": "DROP_NONCANONICAL_CACHE",
      "decision": "DROP_NONCANONICAL_CACHE",
      "successor": null
    },
    {
      "path": "scaffold/action_ir.schema.json",
      "present_in_rag40": false,
      "sha256_v1_3": "8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5",
      "bytes_v1_3": 6967,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "scaffold/action_ir.schema.json"
    },
    {
      "path": "scaffold/canonical_state.schema.json",
      "present_in_rag40": false,
      "sha256_v1_3": "a561d224e2e9c7ce23c06aee330660c95aeb3d44c0e7bc6321d1b1400d5f2af1",
      "bytes_v1_3": 2286,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "scaffold/canonical_state.schema.json"
    },
    {
      "path": "scaffold/lcms.ebnf",
      "present_in_rag40": false,
      "sha256_v1_3": "b2ebe55113efd8d033c396156e2653346bf0293109b6e9c8d24562caf5c5e745",
      "bytes_v1_3": 2399,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "scaffold/lcms.ebnf"
    },
    {
      "path": "scaffold/test_validate_canonical_state.py",
      "present_in_rag40": false,
      "sha256_v1_3": "99869dcc33e59249dcec719ea8c7750f5ba52c8fbb04359aa047fcc2ef3293ef",
      "bytes_v1_3": 2416,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "scaffold/test_validate_canonical_state.py"
    },
    {
      "path": "scaffold/validate_canonical_state.py",
      "present_in_rag40": false,
      "sha256_v1_3": "9a20e63551b75768c0adc38cd0fe20d1cd6d1e41585306540fd2feda709adacc",
      "bytes_v1_3": 5110,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS",
      "decision": "RECONSTRUCT_V1_4_SUCCESSOR_FROM_MANIFEST_DIGEST_AND_AVAILABLE_SEMANTICS",
      "successor": "scaffold/validate_canonical_state.py"
    }
  ],
  "new_v1_4_artifacts": [
    "LION_ARCHITECTURE_v1_4_candidate.md",
    "LION_CANONICAL_STATE_v1_4_candidate.source.json",
    "LION_DOCUMENTATION_HOMEOSTASIS_MODEL_v1_4_candidate.source.md",
    "V1_3_SOURCE_INVENTORY.json",
    "UPGRADE_DECISION_REGISTER.json"
  ],
  "policy": "Only semantic changes force a new source version; exact historical evidence and unchanged contracts may be carried forward. Cache/build outputs are not source."
}

````
LION_RECORD_END: SRC-V14C2-96107301464b

<a id="src-v14c2-741e3ea1c2c6"></a>
## SRC-V14C2-741e3ea1c2c6 — v14c2/V1_3_SOURCE_INVENTORY.json

SOURCE_ID=SRC-V14C2-741e3ea1c2c6
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=V1_3_SOURCE_INVENTORY.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=0a19534fa36ab90c08e921e611a0aa89669ec9a40098c4a095dc51002ccd6259
SOURCE_BYTES=16972

LION_RECORD_BEGIN: SRC-V14C2-741e3ea1c2c6
LION_RECORD_META: {"anchor":"src-v14c2-741e3ea1c2c6","archive_id":"v14c2","authority_effect":"NONE","bytes":16972,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"V1_3_SOURCE_INVENTORY.json","sha256":"0a19534fa36ab90c08e921e611a0aa89669ec9a40098c4a095dc51002ccd6259","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-741e3ea1c2c6","virtual_path":"v14c2/V1_3_SOURCE_INVENTORY.json"}
````json
{
  "schema_version": "lion.source-inventory/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "source_zip": "LION_PROJECT_RAG_40_v1_3.zip",
  "rag40_file_count": 40,
  "v1_3_manifest_payload_count": 58,
  "v1_3_digest_reference_count": 60,
  "reconstructed_total_package_topology_count": 61,
  "missing_from_rag40_count": 21,
  "note": "The v1.3 package topology is 61 files: 60 digest-referenced artifacts plus SOURCE_DIGESTS.sha256 itself. Two omitted .pyc files are cache and are not canonical source.",
  "entries": [
    {
      "path": "CONTRADICTION_REGISTER.json",
      "present_in_rag40": true,
      "sha256_v1_3": "36bfaf6a9e9edff0b07738924c48fea2e656391425ad1070b26dd6e7f96b24e5",
      "bytes_v1_3": 3903,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "EVIDENCE_INDEX.json",
      "present_in_rag40": true,
      "sha256_v1_3": "5bcd55fa15d70b3aeff9d3301953dbffe1b6bde936700f0a40482a45a07c1216",
      "bytes_v1_3": 13515,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "FLEET_AUTHORITY_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "721f60b5158df879e31d5707234a00ca146fafc63ca5957f00e43ee528d7cbc7",
      "bytes_v1_3": 884,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "FLEET_FAILURE_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "d62e6c378f971b2100c34c281804c3e46e2fddab858e3e223500690293b5ef68",
      "bytes_v1_3": 1177,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_ABSTRACTION_COMPILER_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "c0366be0a9e0c95cd08f69cef9751db3650a0c9f444bec65dafff30f5ec2400d",
      "bytes_v1_3": 1082,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_ACTION_IR_SCHEMA_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5",
      "bytes_v1_3": 6967,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_ACTION_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "1d67d01a40769e3d0854f819061b47028ef7ff6a645ce288aed7c10740db17f3",
      "bytes_v1_3": 1045,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_ARCHITECTURE_AS_IS_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "5497644ceff77d3085d6562b0ff588746a7c05dd1f13e96f75a67655ff956aba",
      "bytes_v1_3": 1513,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_ARCHITECTURE_CANDIDATE_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "fd426ef9b6d8fb6f1348bd8703e5404d7cbb8f36b4277c0348381b9a4ef0462a",
      "bytes_v1_3": 1206,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_ARCHITECTURE_TARGET_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "dcd22324c4b88a52bd525cf2bcd6553ad9db35b9ecbedd4ccf8c13141bdae3bf",
      "bytes_v1_3": 1331,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json",
      "present_in_rag40": false,
      "sha256_v1_3": "b6dc2786355a1d4294e6ed828219bcadacbeec2515bbb091c43eb1b8da7b4f4e",
      "bytes_v1_3": 3683,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "LION_AUTONOMY_BLUEPRINT_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "85666d2148cbdb2b06ae8315728791c35a265dfb22c770ad1273250fe9667106",
      "bytes_v1_3": 982,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_AUTONOMY_FACTORY_ROADMAP_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "ec58a037a7003a461529ce29a6041ac6029a78faf1e227bab638e6e83c3cdc49",
      "bytes_v1_3": 909,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_AUTONOMY_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "812bed9b998b2edaf836003369039ba15b11e19898e6e7cacde55983399baaa8",
      "bytes_v1_3": 985,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_BEAN_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "239892f742a9d972e0ea99620fbfa5814a912fe3f083efe78f968fbbf993e21d",
      "bytes_v1_3": 1281,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_BEAN_SCHEMA_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428",
      "bytes_v1_3": 2942,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json",
      "present_in_rag40": false,
      "sha256_v1_3": "86c4f338f39f08b16fb1d0b8fd8ef33db2b565b50350158c07f9a23dfd4aa0f0",
      "bytes_v1_3": 1187,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "LION_COMMAND_MODELING_SYNTAX_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "a40165ccc280ed789b2249edb5fece4679cd0372be9452cda161cae9d393ac8d",
      "bytes_v1_3": 924,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_CYBER_PHYSICAL_ACTION_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "882d682242c59d2e1c982288c855e7496858cdecd5b4b229b07baefa2cec40b0",
      "bytes_v1_3": 1004,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "LION_EVOLUTION_FULL_REPORT_2026-09-02.md",
      "present_in_rag40": true,
      "sha256_v1_3": "595fe690dab18f0aed938d1a3e3e839288092d8b3007d40b30d673f9450bd7c2",
      "bytes_v1_3": 38459,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "0f94b207eb817ae21a174b5966660da4760f7f7f97eb89831f59e30912fa50e6",
      "bytes_v1_3": 5650,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "LION_FACTORY_LINEAGE_REGISTER_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "3c977116ea14fba0f16715977944de7661413820cc4985595798e51dfd3baf6f",
      "bytes_v1_3": 244,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_FACTORY_RECURSION_POLICY_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "cb1fb6d155a9b4526e93d47d9f693aa39dfcd23b20176e437de5cce90c6212bc",
      "bytes_v1_3": 1040,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_FALSIFICATION_REGISTER_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "2e750ef18c13c234f323e0e5ed33712399a84e14bf0c9591f2e5f97648e333c6",
      "bytes_v1_3": 2434,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_FLEET_POLICY_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "d9990df3c1caffc6aad725876940b369df3d4f2c109ef64b1b981278ed19e48f",
      "bytes_v1_3": 985,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "f2731e226a16fe6e2d887d82a2c610dfb4c202c18e34ca94f106c02ae8b18a86",
      "bytes_v1_3": 967,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_IMPLEMENTATION_STATUS_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "eac79a9922134665ce9e053949e51ce4b8c8a9fabe3b4638e0dd84877511eeb8",
      "bytes_v1_3": 5738,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_LOCAL_CONSOLE_PROTOCOL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "f213ac23ce3dfd98bc8df6378a6153093f5590d645c61694a5a76b7b6c10cc3f",
      "bytes_v1_3": 1058,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_LOCAL_OPENAI_LAB_PLAN_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "84a0c1b6065befa868e66d2038cb59cf989283dfc74abd550e9db067b403029c",
      "bytes_v1_3": 1138,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "LION_MATERIALIZER_REGISTRY_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "fbaf330fd571dcc294288feaea624125d0bbf1af1ba1f8b8b4fcbc8b7a5c6642",
      "bytes_v1_3": 1616,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_MODEL_PLANE_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "54efb77e01db8a8b417d3091f9ee4b2e20c5014de6dd17c346fe6861547d5101",
      "bytes_v1_3": 934,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "LION_OPENAI_PROJECT_SOURCE_INDEX_v1_3_candidate.md",
      "present_in_rag40": true,
      "sha256_v1_3": "10ec000c31fccf63f9d93996181433070f2c499757001c4772ee148bb28ba240",
      "bytes_v1_3": 1116,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_PHYSICAL_SAFETY_INVARIANTS_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "9fae4aabfcec3cd358cac3d11b4c39875597bce398aa85e80cf325708a51000e",
      "bytes_v1_3": 1057,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_POST_V1_2_DELTA_REGISTER_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "db5022d74dbdc79e0630e77e967d5801c9f2286fa14627ace779dd596651bcd3",
      "bytes_v1_3": 7068,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_PREPRODUCTION_ENTRY_CRITERIA_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "d266bae4a2b27e6bd9900e24eff9a935fd1a91c67d1118e5742a759964870989",
      "bytes_v1_3": 1156,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_PROJECT_CANONICAL_CONTEXT_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "ff3d3c39f33c228da2375cbe184bd7261fac7cf3364ab44bdb99b5ff19842123",
      "bytes_v1_3": 1633,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_RECONCILIATION_POLICY_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "6755583487a128e55808bd89fb1e57a6108116e83179630cfe4ed2e82be38713",
      "bytes_v1_3": 1025,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_REPOSITORY_FEDERATION_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "d9af756f9d2ce1789ac281026f05a2e42d61c92f8fc7fb89abeae668e8e61b8d",
      "bytes_v1_3": 6573,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "LION_ROBOTICS_LAB_PLAN_v1_3_candidate.source.md",
      "present_in_rag40": false,
      "sha256_v1_3": "ee910bfbd5f7957c8463d6720ab4dbd1e857b8418a79024637fbd334f470b45e",
      "bytes_v1_3": 963,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "LION_SUPERSESSION_REGISTER_v1_3_candidate.source.json",
      "present_in_rag40": true,
      "sha256_v1_3": "b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988",
      "bytes_v1_3": 1198,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "NEXT_EXECUTION_PROMPT.md",
      "present_in_rag40": false,
      "sha256_v1_3": "459ccd27b16504ee374753034d153d397cf6abf5f3e63fbb4a41875b3523839a",
      "bytes_v1_3": 3922,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "PACKAGE_MANIFEST.json",
      "present_in_rag40": true,
      "sha256_v1_3": "410da9da1265de7365a181e23472cc73a997429007ee9b5c73d9238ae98bae94",
      "bytes_v1_3": null,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "PREPRODUCTION_BLOCKERS.json",
      "present_in_rag40": true,
      "sha256_v1_3": "c775e4ad6db6edfc4c3c283b68dea61d087073e11ed24a484c68ad1dd2924689",
      "bytes_v1_3": 4781,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "README.md",
      "present_in_rag40": true,
      "sha256_v1_3": "7f06df0486ae55882e1eaf8357900112f34c34348f4cb6118efa8ed4b7673750",
      "bytes_v1_3": 1139,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "ROADMAP.json",
      "present_in_rag40": true,
      "sha256_v1_3": "cc5a6bcc67d2158d7ca5007c9ede8d91e20332e740dc3a47f53d7ff60d69166d",
      "bytes_v1_3": 6901,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "SOURCE_DIGESTS.sha256",
      "present_in_rag40": true,
      "sha256_v1_3": null,
      "bytes_v1_3": null,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "SUPERSESSION_REGISTER.json",
      "present_in_rag40": false,
      "sha256_v1_3": "b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988",
      "bytes_v1_3": 1198,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "THE_BEAN_FACTORY_CANONICAL_MODEL_v1_3_candidate.source.md",
      "present_in_rag40": true,
      "sha256_v1_3": "5131c8a6f40ce1cbf145e76d17f29ef6fce796565981c9b43e5855b621a7ecc5",
      "bytes_v1_3": 1251,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "VERIFICATION_REPORT.json",
      "present_in_rag40": true,
      "sha256_v1_3": "1e82c81988a9b559382a78b2e46ce33c8572be2e476b1d8343126d7d9e838d70",
      "bytes_v1_3": null,
      "treatment": "SOURCE_PRESENT_REVIEWED"
    },
    {
      "path": "evidence/CYBER_PHYSICAL_EXTERNAL_REQUIREMENTS.md",
      "present_in_rag40": false,
      "sha256_v1_3": "21b284687e9f34d1e98cbf98e3818bc8f9871bc15545fcfa4dbf135a9145b5c1",
      "bytes_v1_3": 841,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "evidence/GITHUB_BASELINES.json",
      "present_in_rag40": false,
      "sha256_v1_3": "848f564b94f31933b1c0550ec511e4108447e12254c0f8c8a732926e0f28265e",
      "bytes_v1_3": 7337,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "evidence/HOST_CENSUS_SUMMARY.json",
      "present_in_rag40": false,
      "sha256_v1_3": "d31111ae8ce05bea387e5cb117b6e98b901be6ecf43ef9e9e150bd5f9096b880",
      "bytes_v1_3": 2520,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "evidence/OPENAI_LOCAL_MODEL_RESEARCH.md",
      "present_in_rag40": false,
      "sha256_v1_3": "38f238580c92caed1e0b339a1e0b45b433ac7f43762f8396466bf70e4c1f4b02",
      "bytes_v1_3": 790,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "scaffold/README.md",
      "present_in_rag40": false,
      "sha256_v1_3": "d87e2c4b5ea9622a40ce307273742b533e78e0d191b9b72b1e47fa2313583c99",
      "bytes_v1_3": 806,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "scaffold/__pycache__/test_validate_canonical_state.cpython-313.pyc",
      "present_in_rag40": false,
      "sha256_v1_3": "8a67d01ee897d4b0b6b4a2188985a26b0854b55d5827bf5b15d689d0c8848e97",
      "bytes_v1_3": 5260,
      "treatment": "DROP_NONCANONICAL_CACHE"
    },
    {
      "path": "scaffold/__pycache__/validate_canonical_state.cpython-313.pyc",
      "present_in_rag40": false,
      "sha256_v1_3": "ea58beefeefc87f48b79e2a25b34877cf5af0dbef8eaa96ebfe13d5d7697a4f6",
      "bytes_v1_3": 7083,
      "treatment": "DROP_NONCANONICAL_CACHE"
    },
    {
      "path": "scaffold/action_ir.schema.json",
      "present_in_rag40": false,
      "sha256_v1_3": "8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5",
      "bytes_v1_3": 6967,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "scaffold/canonical_state.schema.json",
      "present_in_rag40": false,
      "sha256_v1_3": "a561d224e2e9c7ce23c06aee330660c95aeb3d44c0e7bc6321d1b1400d5f2af1",
      "bytes_v1_3": 2286,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "scaffold/lcms.ebnf",
      "present_in_rag40": false,
      "sha256_v1_3": "b2ebe55113efd8d033c396156e2653346bf0293109b6e9c8d24562caf5c5e745",
      "bytes_v1_3": 2399,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "scaffold/test_validate_canonical_state.py",
      "present_in_rag40": false,
      "sha256_v1_3": "99869dcc33e59249dcec719ea8c7750f5ba52c8fbb04359aa047fcc2ef3293ef",
      "bytes_v1_3": 2416,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    },
    {
      "path": "scaffold/validate_canonical_state.py",
      "present_in_rag40": false,
      "sha256_v1_3": "9a20e63551b75768c0adc38cd0fe20d1cd6d1e41585306540fd2feda709adacc",
      "bytes_v1_3": 5110,
      "treatment": "OMITTED_FROM_RAG40_RECOVER_SEMANTICS"
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-741e3ea1c2c6

<a id="src-v14c2-26766deabbb3"></a>
## SRC-V14C2-26766deabbb3 — v14c2/VERIFICATION_REPORT.json

SOURCE_ID=SRC-V14C2-26766deabbb3
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=VERIFICATION_REPORT.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=670dbe68a6006fbf69d92ea99b53c283dcd7fd3042959e5b618b57ecba60fd6c
SOURCE_BYTES=3551

LION_RECORD_BEGIN: SRC-V14C2-26766deabbb3
LION_RECORD_META: {"anchor":"src-v14c2-26766deabbb3","archive_id":"v14c2","authority_effect":"NONE","bytes":3551,"carrier":"31_LION_SOURCE_PROVENANCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"VERIFICATION_REPORT.json","sha256":"670dbe68a6006fbf69d92ea99b53c283dcd7fd3042959e5b618b57ecba60fd6c","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-26766deabbb3","virtual_path":"v14c2/VERIFICATION_REPORT.json"}
````json
{
  "schema_version": "lion.verification-report/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "baseline": {
    "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
    "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1"
  },
  "json_files": [
    {
      "path": "CONTRADICTION_REGISTER.json",
      "status": "PASS"
    },
    {
      "path": "EVIDENCE_INDEX.json",
      "status": "PASS"
    },
    {
      "path": "LION_ACTION_IR_SCHEMA_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_CANONICAL_STATE_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_COMMAND_ADAPTER_REGISTRY_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_FACTORY_LINEAGE_REGISTER_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_FALSIFICATION_REGISTER_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_IMPLEMENTATION_STATUS_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_MATERIALIZER_REGISTRY_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_POST_V1_3_DELTA_REGISTER_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_REPOSITORY_FEDERATION_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "LION_SUPERSESSION_REGISTER_v1_4_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "PREPRODUCTION_BLOCKERS.json",
      "status": "PASS"
    },
    {
      "path": "ROADMAP.json",
      "status": "PASS"
    },
    {
      "path": "SUPERSESSION_REGISTER.json",
      "status": "PASS"
    },
    {
      "path": "UPGRADE_DECISION_REGISTER.json",
      "status": "PASS"
    },
    {
      "path": "V1_3_SOURCE_INVENTORY.json",
      "status": "PASS"
    },
    {
      "path": "carried_forward/LION_BEAN_SCHEMA_v1_3_candidate.source.json",
      "status": "PASS"
    },
    {
      "path": "evidence/GITHUB_BASELINES.json",
      "status": "PASS"
    },
    {
      "path": "evidence/HOST_CENSUS_SUMMARY.json",
      "status": "PASS"
    },
    {
      "path": "scaffold/action_ir.schema.json",
      "status": "PASS"
    },
    {
      "path": "scaffold/canonical_state.schema.json",
      "status": "PASS"
    },
    {
      "path": "PACKAGE_MANIFEST.json",
      "status": "PASS"
    }
  ],
  "python_compile": [
    {
      "path": "scaffold/validate_canonical_state.py",
      "compile": "PASS"
    },
    {
      "path": "scaffold/test_validate_canonical_state.py",
      "compile": "PASS"
    }
  ],
  "scaffold_unittest": {
    "status": "PASS",
    "returncode": 0,
    "stdout": "",
    "stderr": "test_base (test_validate_canonical_state.T.test_base) ... ok\ntest_current_without_basis_fails (test_validate_canonical_state.T.test_current_without_basis_fails) ... ok\ntest_target_live_fails (test_validate_canonical_state.T.test_target_live_fails) ... ok\n\n----------------------------------------------------------------------\nRan 3 tests in 0.000s\n\nOK\n"
  },
  "canonical_state_validator": {
    "status": "PASS",
    "returncode": 0,
    "stdout": "PASS",
    "stderr": ""
  },
  "source_topology": {
    "rag40_file_count": 40,
    "reconstructed_v1_3_total": 61,
    "missing_from_rag40": 21,
    "pyc_dropped": 2
  },
  "repository_mutated": false,
  "host_mutated": false,
  "production_effect": false
}

````
LION_RECORD_END: SRC-V14C2-26766deabbb3
