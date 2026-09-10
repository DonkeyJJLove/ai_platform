# LION — AutonomyBlueprint: model oraz oryginalny i odtworzony schemat

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=13_BLUEPRINT_SCHEMA
SEARCH_TERMS=AutonomyBlueprint schema bean_spec_refs bean_specs gap_refs gap_ref action_schema_refs action_schemas
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

Ostrzeżenie: oryginalny schemat v1.3 ma bean_spec_refs, gap_refs i action_schema_refs. Odtworzenie v1.4 zmienia pola oraz typy. Nie jest to literalny carry-forward ani potwierdzona migracja. Obie wersje zachowano bez zmian.

## Rekordy źródłowe

<a id="src-v13-4a418cbb0aa9"></a>
## SRC-V13-4a418cbb0aa9 — v13/LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-4a418cbb0aa9
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=b6dc2786355a1d4294e6ed828219bcadacbeec2515bbb091c43eb1b8da7b4f4e
SOURCE_BYTES=3683

LION_RECORD_BEGIN: SRC-V13-4a418cbb0aa9
LION_RECORD_META: {"anchor":"src-v13-4a418cbb0aa9","archive_id":"v13","authority_effect":"NONE","bytes":3683,"carrier":"13_LION_BLUEPRINT_SCHEMA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json","sha256":"b6dc2786355a1d4294e6ed828219bcadacbeec2515bbb091c43eb1b8da7b4f4e","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-4a418cbb0aa9","virtual_path":"v13/LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_3_candidate.source.json"}
````json
{
  "$defs": {
    "uniqueStrings": {
      "items": {
        "minLength": 1,
        "type": "string"
      },
      "type": "array",
      "uniqueItems": true
    }
  },
  "$id": "lion://schemas/autonomy-blueprint/v1.3-candidate",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "properties": {
    "action_schema_refs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "authority_ceiling": {
      "minLength": 1,
      "type": "string"
    },
    "authority_requirements": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "bean_spec_refs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "blueprint_digest": {
      "pattern": "^[0-9a-f]{64}$",
      "type": "string"
    },
    "blueprint_id": {
      "minLength": 1,
      "type": "string"
    },
    "build_plan": {
      "type": "string"
    },
    "command_vocabulary": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "composition_contract": {
      "minLength": 1,
      "type": "string"
    },
    "constitution_ref": {
      "minLength": 1,
      "type": "string"
    },
    "counter_hypothesis_refs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "deployment_candidate_plan": {
      "type": "string"
    },
    "failure_model": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "falsifier_refs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "gap_refs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "hypothesis_refs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "lineage": {
      "additionalProperties": false,
      "properties": {
        "generation": {
          "minimum": 0,
          "type": "integer"
        },
        "maximum_children": {
          "minimum": 0,
          "type": "integer"
        },
        "maximum_generation_depth": {
          "minimum": 0,
          "type": "integer"
        },
        "parent_refs": {
          "$ref": "#/$defs/uniqueStrings"
        }
      },
      "required": [
        "parent_refs",
        "generation"
      ],
      "type": "object"
    },
    "memory_contract": {
      "type": "string"
    },
    "mission_specs": {
      "items": {
        "type": "object"
      },
      "minItems": 1,
      "type": "array"
    },
    "model_requirements": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "model_routing_policy": {
      "minLength": 1,
      "type": "string"
    },
    "mosaic_constraints": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "observability_requirements": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "required_capabilities": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "rollback_or_compensation_plan": {
      "type": "string"
    },
    "root_goal_ref": {
      "minLength": 1,
      "type": "string"
    },
    "schema_version": {
      "const": "lion.autonomy-blueprint/v1.3-candidate"
    },
    "supersession_policy": {
      "type": "string"
    },
    "system_model_contract": {
      "minLength": 1,
      "type": "string"
    },
    "verification_plan": {
      "minLength": 1,
      "type": "string"
    },
    "world_model_contract": {
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "blueprint_id",
    "schema_version",
    "root_goal_ref",
    "constitution_ref",
    "world_model_contract",
    "system_model_contract",
    "mission_specs",
    "required_capabilities",
    "bean_spec_refs",
    "composition_contract",
    "model_routing_policy",
    "action_schema_refs",
    "authority_ceiling",
    "observability_requirements",
    "failure_model",
    "verification_plan",
    "lineage",
    "blueprint_digest"
  ],
  "title": "LION AutonomyBlueprint candidate",
  "type": "object"
}

````
LION_RECORD_END: SRC-V13-4a418cbb0aa9

<a id="src-v13-9c9a21a96d8f"></a>
## SRC-V13-9c9a21a96d8f — v13/LION_AUTONOMY_BLUEPRINT_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-9c9a21a96d8f
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_AUTONOMY_BLUEPRINT_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=85666d2148cbdb2b06ae8315728791c35a265dfb22c770ad1273250fe9667106
SOURCE_BYTES=982

LION_RECORD_BEGIN: SRC-V13-9c9a21a96d8f
LION_RECORD_META: {"anchor":"src-v13-9c9a21a96d8f","archive_id":"v13","authority_effect":"NONE","bytes":982,"carrier":"13_LION_BLUEPRINT_SCHEMA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_AUTONOMY_BLUEPRINT_v1_3_candidate.source.md","sha256":"85666d2148cbdb2b06ae8315728791c35a265dfb22c770ad1273250fe9667106","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-9c9a21a96d8f","virtual_path":"v13/LION_AUTONOMY_BLUEPRINT_v1_3_candidate.source.md"}
````markdown
# LION Autonomy Blueprint v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=TARGET_CONTRACT
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=canonical blueprint semantics
DEPENDENCIES=Bean/Composition/Action models
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

`AutonomyBlueprint` binds goal, constitution, world/system models, gaps, hypotheses, missions, capabilities, Beans, Mosaic constraints, model routing, Action schemas, authority, observability, failure/recovery, memory, build, verification, deployment-candidate and lineage policies.

It carries no credentials, implicit grant, raw shell authority or self-declared verification. Its canonical serialized payload must be digest-bound. The JSON Schema in this package is a detached design candidate.

````
LION_RECORD_END: SRC-V13-9c9a21a96d8f

<a id="src-v14c2-09f015ba4e6e"></a>
## SRC-V14C2-09f015ba4e6e — v14c2/LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-09f015ba4e6e
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=5d4d61043054b8fc3a97ccad54bd4920527a923075511f057dbe92b4c572c486
SOURCE_BYTES=5099

LION_RECORD_BEGIN: SRC-V14C2-09f015ba4e6e
LION_RECORD_META: {"anchor":"src-v14c2-09f015ba4e6e","archive_id":"v14c2","authority_effect":"NONE","bytes":5099,"carrier":"13_LION_BLUEPRINT_SCHEMA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_4_candidate.source.json","sha256":"5d4d61043054b8fc3a97ccad54bd4920527a923075511f057dbe92b4c572c486","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-09f015ba4e6e","virtual_path":"v14c2/LION_AUTONOMY_BLUEPRINT_SCHEMA_v1_4_candidate.source.json"}
````json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "lion://schemas/autonomy-blueprint/v1.4-candidate",
  "title": "LION AutonomyBlueprint v1.4 detached target schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "blueprint_id",
    "schema_version",
    "root_goal_ref",
    "constitution_ref",
    "world_model_contract",
    "system_model_contract",
    "gap_ref",
    "hypothesis_refs",
    "counter_hypothesis_refs",
    "falsifier_refs",
    "mission_specs",
    "required_capabilities",
    "bean_specs",
    "composition_contract",
    "mosaic_constraints",
    "model_requirements",
    "model_routing_policy",
    "command_vocabulary",
    "action_schemas",
    "authority_ceiling",
    "authority_requirements",
    "observability_requirements",
    "failure_model",
    "memory_contract",
    "build_plan",
    "verification_plan",
    "deployment_candidate_plan",
    "rollback_or_compensation_plan",
    "lineage",
    "supersession_policy",
    "blueprint_digest"
  ],
  "properties": {
    "blueprint_id": {
      "type": "string"
    },
    "schema_version": {
      "const": "lion.autonomy-blueprint/v1.4-candidate"
    },
    "root_goal_ref": {
      "type": "string"
    },
    "constitution_ref": {
      "type": "string"
    },
    "world_model_contract": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "system_model_contract": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "gap_ref": {
      "type": "string"
    },
    "hypothesis_refs": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "uniqueItems": true
    },
    "counter_hypothesis_refs": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "uniqueItems": true
    },
    "falsifier_refs": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "uniqueItems": true
    },
    "mission_specs": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "uniqueItems": true
    },
    "required_capabilities": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "uniqueItems": true
    },
    "bean_specs": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "uniqueItems": true
    },
    "composition_contract": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "mosaic_constraints": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "model_requirements": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "model_routing_policy": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "command_vocabulary": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "action_schemas": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "uniqueItems": true
    },
    "authority_ceiling": {
      "type": "string"
    },
    "authority_requirements": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "uniqueItems": true
    },
    "observability_requirements": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "uniqueItems": true
    },
    "failure_model": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "memory_contract": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "build_plan": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "verification_plan": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "deployment_candidate_plan": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "rollback_or_compensation_plan": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "lineage": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "supersession_policy": {
      "type": [
        "string",
        "object",
        "array"
      ]
    },
    "blueprint_digest": {
      "type": "string",
      "pattern": "^[0-9a-f]{64}$"
    }
  },
  "x-lion": {
    "status": "TARGET_NOT_IMPLEMENTED",
    "authority_effect": "NONE",
    "forbidden_content": [
      "private_credentials",
      "implicit_grants",
      "production_secrets",
      "raw_unrestricted_shell",
      "self_declared_verification",
      "self_declared_integration",
      "self_declared_production_status"
    ],
    "source_recovery": "v1.3 exact schema bytes omitted from RAG-40; field semantics recovered from supplied master research prompt and v1.3 Blueprint model"
  }
}

````
LION_RECORD_END: SRC-V14C2-09f015ba4e6e

<a id="src-v14c2-f46748ef95a4"></a>
## SRC-V14C2-f46748ef95a4 — v14c2/LION_AUTONOMY_BLUEPRINT_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-f46748ef95a4
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_AUTONOMY_BLUEPRINT_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=c6f2f6bd8686814890eeb23ed77f8b1be4ad85aab3e7eb754bf44a583d4f530d
SOURCE_BYTES=1334

LION_RECORD_BEGIN: SRC-V14C2-f46748ef95a4
LION_RECORD_META: {"anchor":"src-v14c2-f46748ef95a4","archive_id":"v14c2","authority_effect":"NONE","bytes":1334,"carrier":"13_LION_BLUEPRINT_SCHEMA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_AUTONOMY_BLUEPRINT_v1_4_candidate.source.md","sha256":"c6f2f6bd8686814890eeb23ed77f8b1be4ad85aab3e7eb754bf44a583d4f530d","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-f46748ef95a4","virtual_path":"v14c2/LION_AUTONOMY_BLUEPRINT_v1_4_candidate.source.md"}
````markdown
# LION Autonomy Blueprint v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=TARGET_CONTRACT
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=canonical autonomy blueprint semantics
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

`AutonomyBlueprint` remains a target contract. It binds goal/constitution, world/system models, gaps/hypotheses/falsifiers, missions, required capabilities, Beans and composition, model routing, command/action schemas, authority ceilings, observability, failure/recovery, memory, build/verification/deployment candidate plans and lineage.

Its payload is digest-bound. It carries no credentials, implicit grants, raw shell authority, self-declared verification/integration or production status. The JSON Schema in this package is a detached reconstruction/successor because the exact v1.3 schema bytes were referenced by the original manifest/digests but omitted from RAG-40.

````
LION_RECORD_END: SRC-V14C2-f46748ef95a4
