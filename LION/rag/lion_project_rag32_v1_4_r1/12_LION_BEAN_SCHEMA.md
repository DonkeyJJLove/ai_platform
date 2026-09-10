# LION — Schemat BeanSpec i tożsamość kontraktu

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=12_BEAN_SCHEMA
SEARCH_TERMS=Bean schema authority ceiling observability acceptance conditions
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-0bea86b4c00d"></a>
## SRC-V13-0bea86b4c00d — v13/LION_BEAN_SCHEMA_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-0bea86b4c00d
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_BEAN_SCHEMA_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428
SOURCE_BYTES=2942

LION_RECORD_BEGIN: SRC-V13-0bea86b4c00d
LION_RECORD_META: {"anchor":"src-v13-0bea86b4c00d","archive_id":"v13","authority_effect":"NONE","bytes":2942,"carrier":"12_LION_BEAN_SCHEMA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_BEAN_SCHEMA_v1_3_candidate.source.json","sha256":"5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-0bea86b4c00d","virtual_path":"v13/LION_BEAN_SCHEMA_v1_3_candidate.source.json"}
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
  "$id": "lion://schemas/bean/v1.3-candidate",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "properties": {
    "acceptance_tests": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "authority_ceiling": {
      "enum": [
        "none",
        "read",
        "local_write",
        "external_write",
        "financial",
        "deploy",
        "privileged"
      ]
    },
    "bean_id": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "bean_type": {
      "enum": [
        "agent",
        "observer",
        "builder",
        "verifier",
        "adapter",
        "tool",
        "deterministic_service",
        "workflow",
        "reconciler",
        "provider"
      ]
    },
    "defer_conditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "failure_modes": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "falsification_conditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "goal_digest": {
      "pattern": "^[0-9a-f]{64}$",
      "type": "string"
    },
    "implementation_digest": {
      "pattern": "^$|^[0-9a-f]{64}$",
      "type": "string"
    },
    "inputs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "interfaces": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "lineage_parent_digests": {
      "items": {
        "pattern": "^[0-9a-f]{64}$",
        "type": "string"
      },
      "type": "array",
      "uniqueItems": true
    },
    "observability_requirements": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "outputs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "provided_capabilities": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "purpose": {
      "minLength": 1,
      "type": "string"
    },
    "required_capabilities": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "required_grants": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "resource_budget": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "security_invariants": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "stop_conditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "success_conditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "version": {
      "maxLength": 64,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "bean_id",
    "bean_type",
    "version",
    "purpose",
    "goal_digest",
    "success_conditions",
    "stop_conditions",
    "inputs",
    "outputs",
    "required_capabilities",
    "provided_capabilities",
    "authority_ceiling",
    "observability_requirements",
    "failure_modes",
    "security_invariants",
    "acceptance_tests",
    "falsification_conditions"
  ],
  "title": "LION BeanSpec candidate projection",
  "type": "object"
}

````
LION_RECORD_END: SRC-V13-0bea86b4c00d

<a id="src-v14c2-15392019d14c"></a>
## SRC-V14C2-15392019d14c — v14c2/carried_forward/LION_BEAN_SCHEMA_v1_3_candidate.source.json

SOURCE_ID=SRC-V14C2-15392019d14c
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=carried_forward/LION_BEAN_SCHEMA_v1_3_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428
SOURCE_BYTES=2942

LION_RECORD_BEGIN: SRC-V14C2-15392019d14c
LION_RECORD_META: {"anchor":"src-v14c2-15392019d14c","archive_id":"v14c2","authority_effect":"NONE","bytes":2942,"carrier":"12_LION_BEAN_SCHEMA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"carried_forward/LION_BEAN_SCHEMA_v1_3_candidate.source.json","sha256":"5c5ae149e6f8573bf73f055619c45efc9fe8515c86af3d41163f3d4c0dcd8428","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-15392019d14c","virtual_path":"v14c2/carried_forward/LION_BEAN_SCHEMA_v1_3_candidate.source.json"}
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
  "$id": "lion://schemas/bean/v1.3-candidate",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "properties": {
    "acceptance_tests": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "authority_ceiling": {
      "enum": [
        "none",
        "read",
        "local_write",
        "external_write",
        "financial",
        "deploy",
        "privileged"
      ]
    },
    "bean_id": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "bean_type": {
      "enum": [
        "agent",
        "observer",
        "builder",
        "verifier",
        "adapter",
        "tool",
        "deterministic_service",
        "workflow",
        "reconciler",
        "provider"
      ]
    },
    "defer_conditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "failure_modes": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "falsification_conditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "goal_digest": {
      "pattern": "^[0-9a-f]{64}$",
      "type": "string"
    },
    "implementation_digest": {
      "pattern": "^$|^[0-9a-f]{64}$",
      "type": "string"
    },
    "inputs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "interfaces": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "lineage_parent_digests": {
      "items": {
        "pattern": "^[0-9a-f]{64}$",
        "type": "string"
      },
      "type": "array",
      "uniqueItems": true
    },
    "observability_requirements": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "outputs": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "provided_capabilities": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "purpose": {
      "minLength": 1,
      "type": "string"
    },
    "required_capabilities": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "required_grants": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "resource_budget": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "security_invariants": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "stop_conditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "success_conditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "version": {
      "maxLength": 64,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "bean_id",
    "bean_type",
    "version",
    "purpose",
    "goal_digest",
    "success_conditions",
    "stop_conditions",
    "inputs",
    "outputs",
    "required_capabilities",
    "provided_capabilities",
    "authority_ceiling",
    "observability_requirements",
    "failure_modes",
    "security_invariants",
    "acceptance_tests",
    "falsification_conditions"
  ],
  "title": "LION BeanSpec candidate projection",
  "type": "object"
}

````
LION_RECORD_END: SRC-V14C2-15392019d14c
