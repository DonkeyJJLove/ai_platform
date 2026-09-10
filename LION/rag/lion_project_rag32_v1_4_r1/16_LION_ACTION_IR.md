# LION — Action Model, ActionSpec i schematy LAIR

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=16_ACTION_IR
SEARCH_TERMS=ActionSpec CanonicalActionIR LAIR ActionProposal PDP payload_digest schema
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-df4281446524"></a>
## SRC-V13-df4281446524 — v13/LION_ACTION_IR_SCHEMA_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-df4281446524
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_ACTION_IR_SCHEMA_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5
SOURCE_BYTES=6967

LION_RECORD_BEGIN: SRC-V13-df4281446524
LION_RECORD_META: {"anchor":"src-v13-df4281446524","archive_id":"v13","authority_effect":"NONE","bytes":6967,"carrier":"16_LION_ACTION_IR.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_ACTION_IR_SCHEMA_v1_3_candidate.source.json","sha256":"8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-df4281446524","virtual_path":"v13/LION_ACTION_IR_SCHEMA_v1_3_candidate.source.json"}
````json
{
  "$defs": {
    "uniqueStrings": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "type": "array",
      "uniqueItems": true
    }
  },
  "$id": "lion://schemas/action-ir/v1.3-candidate",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "allOf": [
    {
      "if": {
        "properties": {
          "kind": {
            "const": "process.exec"
          }
        }
      },
      "then": {
        "required": [
          "executable",
          "arguments",
          "workspace",
          "environment",
          "io"
        ]
      }
    }
  ],
  "properties": {
    "action_id": {
      "pattern": "^[A-Za-z][A-Za-z0-9_.:-]{0,255}$",
      "type": "string"
    },
    "arguments": {
      "items": {
        "maxLength": 4096,
        "type": "string"
      },
      "maxItems": 256,
      "type": "array"
    },
    "authority_request": {
      "additionalProperties": false,
      "properties": {
        "capability": {
          "minLength": 1,
          "type": "string"
        },
        "domain": {
          "minLength": 1,
          "type": "string"
        },
        "grant_ref": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "domain",
        "capability",
        "grant_ref"
      ],
      "type": "object"
    },
    "autonomy_ref": {
      "minLength": 1,
      "type": "string"
    },
    "bean_ref": {
      "minLength": 1,
      "type": "string"
    },
    "boundary": {
      "additionalProperties": false,
      "properties": {
        "filesystem_read": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "filesystem_write": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "max_processes": {
          "maximum": 128,
          "minimum": 1,
          "type": "integer"
        },
        "memory_limit_bytes": {
          "minimum": 1048576,
          "type": "integer"
        },
        "network": {
          "enum": [
            "DENY",
            "READ_ONLY_PINNED",
            "ALLOW_EXACT"
          ]
        },
        "process_children": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "shell": {
          "const": false
        },
        "timeout_ms": {
          "maximum": 3600000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "shell",
        "network",
        "filesystem_read",
        "filesystem_write",
        "process_children",
        "timeout_ms",
        "max_processes",
        "memory_limit_bytes"
      ],
      "type": "object"
    },
    "environment": {
      "additionalProperties": false,
      "properties": {
        "allow": {
          "additionalProperties": {
            "maxLength": 4096,
            "type": "string"
          },
          "type": "object"
        },
        "inherit": {
          "const": false
        }
      },
      "required": [
        "inherit",
        "allow"
      ],
      "type": "object"
    },
    "executable": {
      "additionalProperties": false,
      "properties": {
        "digest": {
          "pattern": "^sha256:[0-9a-f]{64}$",
          "type": "string"
        },
        "path": {
          "pattern": "^/",
          "type": "string"
        }
      },
      "required": [
        "path",
        "digest"
      ],
      "type": "object"
    },
    "expected_effects": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "forbidden_effects": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "intent_ref": {
      "minLength": 1,
      "type": "string"
    },
    "io": {
      "additionalProperties": false,
      "properties": {
        "stderr": {
          "enum": [
            "CAPTURE",
            "DISCARD"
          ]
        },
        "stdin": {
          "const": "NONE"
        },
        "stdout": {
          "enum": [
            "CAPTURE",
            "DISCARD"
          ]
        },
        "tty": {
          "const": false
        }
      },
      "required": [
        "stdin",
        "stdout",
        "stderr",
        "tty"
      ],
      "type": "object"
    },
    "kind": {
      "enum": [
        "process.exec",
        "filesystem.read",
        "filesystem.write",
        "repository.observe",
        "repository.prepare_candidate",
        "repository.attach_exact",
        "test.execute",
        "artifact.generate",
        "robot.task"
      ]
    },
    "mission_ref": {
      "minLength": 1,
      "type": "string"
    },
    "observation": {
      "additionalProperties": false,
      "properties": {
        "observer_class": {
          "enum": [
            "independent",
            "deterministic_independent"
          ]
        },
        "required_events": {
          "$ref": "#/$defs/uniqueStrings"
        }
      },
      "required": [
        "observer_class",
        "required_events"
      ],
      "type": "object"
    },
    "preconditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "reconciliation": {
      "additionalProperties": false,
      "properties": {
        "mode": {
          "enum": [
            "EXACT",
            "PHYSICAL_POSTCONDITION"
          ]
        },
        "receipt": {
          "const": "REQUIRED"
        }
      },
      "required": [
        "mode",
        "receipt"
      ],
      "type": "object"
    },
    "schema_version": {
      "const": "lion.action-ir/v1.3-candidate"
    },
    "target": {
      "additionalProperties": false,
      "properties": {
        "environment": {
          "minLength": 1,
          "type": "string"
        },
        "host": {
          "minLength": 1,
          "type": "string"
        },
        "runtime": {
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "host",
        "environment",
        "runtime"
      ],
      "type": "object"
    },
    "workspace": {
      "additionalProperties": false,
      "properties": {
        "commit": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        },
        "path": {
          "pattern": "^/",
          "type": "string"
        },
        "repository": {
          "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
          "type": "string"
        },
        "tree": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        }
      },
      "required": [
        "repository",
        "commit",
        "tree",
        "path"
      ],
      "type": "object"
    }
  },
  "required": [
    "schema_version",
    "action_id",
    "kind",
    "intent_ref",
    "mission_ref",
    "autonomy_ref",
    "bean_ref",
    "target",
    "authority_request",
    "boundary",
    "preconditions",
    "expected_effects",
    "forbidden_effects",
    "observation",
    "reconciliation"
  ],
  "title": "LION Action Intermediate Representation",
  "type": "object"
}

````
LION_RECORD_END: SRC-V13-df4281446524

<a id="src-v13-fac8410d1f81"></a>
## SRC-V13-fac8410d1f81 — v13/LION_ACTION_MODEL_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-fac8410d1f81
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_ACTION_MODEL_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=1d67d01a40769e3d0854f819061b47028ef7ff6a645ce288aed7c10740db17f3
SOURCE_BYTES=1045

LION_RECORD_BEGIN: SRC-V13-fac8410d1f81
LION_RECORD_META: {"anchor":"src-v13-fac8410d1f81","archive_id":"v13","authority_effect":"NONE","bytes":1045,"carrier":"16_LION_ACTION_IR.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_ACTION_MODEL_v1_3_candidate.source.md","sha256":"1d67d01a40769e3d0854f819061b47028ef7ff6a645ce288aed7c10740db17f3","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-fac8410d1f81","virtual_path":"v13/LION_ACTION_MODEL_v1_3_candidate.source.md"}
````markdown
# LION Action Model v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=CANDIDATE_EXTENSION
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=ActionIntent/ActionSpec/Plan/Permit/Receipts
DEPENDENCIES=existing ActionProposal
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

```text
ActionIntent != ActionSpec
ActionSpec != ExecutionPlan
ExecutionPlan != ActionProposal
ActionProposal != EffectPermit
EffectPermit != Effect
Reported Effect != Observed Effect
Observed Effect != Reconciled Closure
```

Existing ActionProposal remains the mission/capability/authority envelope. Proposed canonical Action IR becomes its digest-bound payload and contains execution semantics, boundaries, preconditions, expected/forbidden effects, observation and reconciliation requirements.

No new execution provider is authorized by this model.

````
LION_RECORD_END: SRC-V13-fac8410d1f81

<a id="src-v13-abd17ba6d3e6"></a>
## SRC-V13-abd17ba6d3e6 — v13/scaffold/action_ir.schema.json

SOURCE_ID=SRC-V13-abd17ba6d3e6
SOURCE_ARCHIVE=v13
SOURCE_PATH=scaffold/action_ir.schema.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5
SOURCE_BYTES=6967

LION_RECORD_BEGIN: SRC-V13-abd17ba6d3e6
LION_RECORD_META: {"anchor":"src-v13-abd17ba6d3e6","archive_id":"v13","authority_effect":"NONE","bytes":6967,"carrier":"16_LION_ACTION_IR.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"scaffold/action_ir.schema.json","sha256":"8a9fbcc80a8f68cf08b0b0a74d98dd1e1f5a13c39f18b19009f91e7bd36b66c5","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-abd17ba6d3e6","virtual_path":"v13/scaffold/action_ir.schema.json"}
````json
{
  "$defs": {
    "uniqueStrings": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "type": "array",
      "uniqueItems": true
    }
  },
  "$id": "lion://schemas/action-ir/v1.3-candidate",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "allOf": [
    {
      "if": {
        "properties": {
          "kind": {
            "const": "process.exec"
          }
        }
      },
      "then": {
        "required": [
          "executable",
          "arguments",
          "workspace",
          "environment",
          "io"
        ]
      }
    }
  ],
  "properties": {
    "action_id": {
      "pattern": "^[A-Za-z][A-Za-z0-9_.:-]{0,255}$",
      "type": "string"
    },
    "arguments": {
      "items": {
        "maxLength": 4096,
        "type": "string"
      },
      "maxItems": 256,
      "type": "array"
    },
    "authority_request": {
      "additionalProperties": false,
      "properties": {
        "capability": {
          "minLength": 1,
          "type": "string"
        },
        "domain": {
          "minLength": 1,
          "type": "string"
        },
        "grant_ref": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "domain",
        "capability",
        "grant_ref"
      ],
      "type": "object"
    },
    "autonomy_ref": {
      "minLength": 1,
      "type": "string"
    },
    "bean_ref": {
      "minLength": 1,
      "type": "string"
    },
    "boundary": {
      "additionalProperties": false,
      "properties": {
        "filesystem_read": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "filesystem_write": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "max_processes": {
          "maximum": 128,
          "minimum": 1,
          "type": "integer"
        },
        "memory_limit_bytes": {
          "minimum": 1048576,
          "type": "integer"
        },
        "network": {
          "enum": [
            "DENY",
            "READ_ONLY_PINNED",
            "ALLOW_EXACT"
          ]
        },
        "process_children": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "shell": {
          "const": false
        },
        "timeout_ms": {
          "maximum": 3600000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "shell",
        "network",
        "filesystem_read",
        "filesystem_write",
        "process_children",
        "timeout_ms",
        "max_processes",
        "memory_limit_bytes"
      ],
      "type": "object"
    },
    "environment": {
      "additionalProperties": false,
      "properties": {
        "allow": {
          "additionalProperties": {
            "maxLength": 4096,
            "type": "string"
          },
          "type": "object"
        },
        "inherit": {
          "const": false
        }
      },
      "required": [
        "inherit",
        "allow"
      ],
      "type": "object"
    },
    "executable": {
      "additionalProperties": false,
      "properties": {
        "digest": {
          "pattern": "^sha256:[0-9a-f]{64}$",
          "type": "string"
        },
        "path": {
          "pattern": "^/",
          "type": "string"
        }
      },
      "required": [
        "path",
        "digest"
      ],
      "type": "object"
    },
    "expected_effects": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "forbidden_effects": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "intent_ref": {
      "minLength": 1,
      "type": "string"
    },
    "io": {
      "additionalProperties": false,
      "properties": {
        "stderr": {
          "enum": [
            "CAPTURE",
            "DISCARD"
          ]
        },
        "stdin": {
          "const": "NONE"
        },
        "stdout": {
          "enum": [
            "CAPTURE",
            "DISCARD"
          ]
        },
        "tty": {
          "const": false
        }
      },
      "required": [
        "stdin",
        "stdout",
        "stderr",
        "tty"
      ],
      "type": "object"
    },
    "kind": {
      "enum": [
        "process.exec",
        "filesystem.read",
        "filesystem.write",
        "repository.observe",
        "repository.prepare_candidate",
        "repository.attach_exact",
        "test.execute",
        "artifact.generate",
        "robot.task"
      ]
    },
    "mission_ref": {
      "minLength": 1,
      "type": "string"
    },
    "observation": {
      "additionalProperties": false,
      "properties": {
        "observer_class": {
          "enum": [
            "independent",
            "deterministic_independent"
          ]
        },
        "required_events": {
          "$ref": "#/$defs/uniqueStrings"
        }
      },
      "required": [
        "observer_class",
        "required_events"
      ],
      "type": "object"
    },
    "preconditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "reconciliation": {
      "additionalProperties": false,
      "properties": {
        "mode": {
          "enum": [
            "EXACT",
            "PHYSICAL_POSTCONDITION"
          ]
        },
        "receipt": {
          "const": "REQUIRED"
        }
      },
      "required": [
        "mode",
        "receipt"
      ],
      "type": "object"
    },
    "schema_version": {
      "const": "lion.action-ir/v1.3-candidate"
    },
    "target": {
      "additionalProperties": false,
      "properties": {
        "environment": {
          "minLength": 1,
          "type": "string"
        },
        "host": {
          "minLength": 1,
          "type": "string"
        },
        "runtime": {
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "host",
        "environment",
        "runtime"
      ],
      "type": "object"
    },
    "workspace": {
      "additionalProperties": false,
      "properties": {
        "commit": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        },
        "path": {
          "pattern": "^/",
          "type": "string"
        },
        "repository": {
          "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
          "type": "string"
        },
        "tree": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        }
      },
      "required": [
        "repository",
        "commit",
        "tree",
        "path"
      ],
      "type": "object"
    }
  },
  "required": [
    "schema_version",
    "action_id",
    "kind",
    "intent_ref",
    "mission_ref",
    "autonomy_ref",
    "bean_ref",
    "target",
    "authority_request",
    "boundary",
    "preconditions",
    "expected_effects",
    "forbidden_effects",
    "observation",
    "reconciliation"
  ],
  "title": "LION Action Intermediate Representation",
  "type": "object"
}

````
LION_RECORD_END: SRC-V13-abd17ba6d3e6

<a id="src-v14c2-d4df68aa51a2"></a>
## SRC-V14C2-d4df68aa51a2 — v14c2/LION_ACTION_IR_SCHEMA_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-d4df68aa51a2
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_ACTION_IR_SCHEMA_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=b652180ea03b75add7e1357f210d6395aee8bae9b16361dca48eb84445c8b4ba
SOURCE_BYTES=7549

LION_RECORD_BEGIN: SRC-V14C2-d4df68aa51a2
LION_RECORD_META: {"anchor":"src-v14c2-d4df68aa51a2","archive_id":"v14c2","authority_effect":"NONE","bytes":7549,"carrier":"16_LION_ACTION_IR.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_ACTION_IR_SCHEMA_v1_4_candidate.source.json","sha256":"b652180ea03b75add7e1357f210d6395aee8bae9b16361dca48eb84445c8b4ba","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-d4df68aa51a2","virtual_path":"v14c2/LION_ACTION_IR_SCHEMA_v1_4_candidate.source.json"}
````json
{
  "$defs": {
    "uniqueStrings": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "type": "array",
      "uniqueItems": true
    }
  },
  "$id": "lion://schemas/action-ir/v1.4-candidate-projection",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "allOf": [
    {
      "if": {
        "properties": {
          "kind": {
            "const": "process.exec"
          }
        }
      },
      "then": {
        "required": [
          "executable",
          "arguments",
          "workspace",
          "environment",
          "io"
        ]
      }
    }
  ],
  "properties": {
    "action_id": {
      "pattern": "^[A-Za-z][A-Za-z0-9_.:-]{0,255}$",
      "type": "string"
    },
    "arguments": {
      "items": {
        "maxLength": 4096,
        "type": "string"
      },
      "maxItems": 256,
      "type": "array"
    },
    "authority_request": {
      "additionalProperties": false,
      "properties": {
        "capability": {
          "minLength": 1,
          "type": "string"
        },
        "domain": {
          "minLength": 1,
          "type": "string"
        },
        "grant_ref": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "domain",
        "capability",
        "grant_ref"
      ],
      "type": "object"
    },
    "autonomy_ref": {
      "minLength": 1,
      "type": "string"
    },
    "bean_ref": {
      "minLength": 1,
      "type": "string"
    },
    "boundary": {
      "additionalProperties": false,
      "properties": {
        "filesystem_read": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "filesystem_write": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "max_processes": {
          "maximum": 128,
          "minimum": 1,
          "type": "integer"
        },
        "memory_limit_bytes": {
          "minimum": 1048576,
          "type": "integer"
        },
        "network": {
          "enum": [
            "DENY",
            "READ_ONLY_PINNED",
            "ALLOW_EXACT"
          ]
        },
        "process_children": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "shell": {
          "const": false
        },
        "timeout_ms": {
          "maximum": 3600000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "shell",
        "network",
        "filesystem_read",
        "filesystem_write",
        "process_children",
        "timeout_ms",
        "max_processes",
        "memory_limit_bytes"
      ],
      "type": "object"
    },
    "environment": {
      "additionalProperties": false,
      "properties": {
        "allow": {
          "additionalProperties": {
            "maxLength": 4096,
            "type": "string"
          },
          "type": "object"
        },
        "inherit": {
          "const": false
        }
      },
      "required": [
        "inherit",
        "allow"
      ],
      "type": "object"
    },
    "executable": {
      "additionalProperties": false,
      "properties": {
        "digest": {
          "pattern": "^sha256:[0-9a-f]{64}$",
          "type": "string"
        },
        "path": {
          "pattern": "^/",
          "type": "string"
        }
      },
      "required": [
        "path",
        "digest"
      ],
      "type": "object"
    },
    "expected_effects": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "forbidden_effects": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "intent_ref": {
      "minLength": 1,
      "type": "string"
    },
    "io": {
      "additionalProperties": false,
      "properties": {
        "stderr": {
          "enum": [
            "CAPTURE",
            "DISCARD"
          ]
        },
        "stdin": {
          "const": "NONE"
        },
        "stdout": {
          "enum": [
            "CAPTURE",
            "DISCARD"
          ]
        },
        "tty": {
          "const": false
        }
      },
      "required": [
        "stdin",
        "stdout",
        "stderr",
        "tty"
      ],
      "type": "object"
    },
    "kind": {
      "enum": [
        "process.exec",
        "filesystem.read",
        "filesystem.write",
        "repository.observe",
        "repository.prepare_candidate",
        "repository.attach_exact",
        "test.execute",
        "artifact.generate",
        "robot.task"
      ]
    },
    "mission_ref": {
      "minLength": 1,
      "type": "string"
    },
    "observation": {
      "additionalProperties": false,
      "properties": {
        "observer_class": {
          "enum": [
            "independent",
            "deterministic_independent"
          ]
        },
        "required_events": {
          "$ref": "#/$defs/uniqueStrings"
        }
      },
      "required": [
        "observer_class",
        "required_events"
      ],
      "type": "object"
    },
    "preconditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "reconciliation": {
      "additionalProperties": false,
      "properties": {
        "mode": {
          "enum": [
            "EXACT",
            "PHYSICAL_POSTCONDITION"
          ]
        },
        "receipt": {
          "const": "REQUIRED"
        }
      },
      "required": [
        "mode",
        "receipt"
      ],
      "type": "object"
    },
    "schema_version": {
      "const": "1.0.0"
    },
    "target": {
      "additionalProperties": false,
      "properties": {
        "environment": {
          "minLength": 1,
          "type": "string"
        },
        "host": {
          "minLength": 1,
          "type": "string"
        },
        "runtime": {
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "host",
        "environment",
        "runtime"
      ],
      "type": "object"
    },
    "workspace": {
      "additionalProperties": false,
      "properties": {
        "commit": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        },
        "path": {
          "pattern": "^/",
          "type": "string"
        },
        "repository": {
          "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
          "type": "string"
        },
        "tree": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        }
      },
      "required": [
        "repository",
        "commit",
        "tree",
        "path"
      ],
      "type": "object"
    }
  },
  "required": [
    "schema_version",
    "action_id",
    "kind",
    "intent_ref",
    "mission_ref",
    "autonomy_ref",
    "bean_ref",
    "target",
    "authority_request",
    "boundary",
    "preconditions",
    "expected_effects",
    "forbidden_effects",
    "observation",
    "reconciliation"
  ],
  "title": "LION ActionSpec / Action IR v1.4 candidate projection of canonical v1 contract",
  "type": "object",
  "x-lion-v1_4-projection": {
    "canonical_schema_id": "cyberlion://schemas/action-spec/v1",
    "canonical_schema_version": "1.0.0",
    "canonical_action_ir": "cyber_lion/contracts/action_ir.py",
    "status": "AS_IS_PARTIALLY_IMPLEMENTED",
    "pdp_handoff": "INTEGRATED",
    "next_minimal_gap": "bind canonical PDP ALLOW result to exact RequestedRuntimeEffect and runtime identity before RuntimeAdmissionEngine",
    "authority_effect": "NONE",
    "note": "Do not confuse this detached package projection with the live canonical schema file."
  }
}

````
LION_RECORD_END: SRC-V14C2-d4df68aa51a2

<a id="src-v14c2-e9e1005a7e01"></a>
## SRC-V14C2-e9e1005a7e01 — v14c2/LION_ACTION_MODEL_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-e9e1005a7e01
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_ACTION_MODEL_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=93a482ec6af3d4f1b1292cd62fe3fd424df48ee882d1e1592a3a35edd7d6dbc1
SOURCE_BYTES=1372

LION_RECORD_BEGIN: SRC-V14C2-e9e1005a7e01
LION_RECORD_META: {"anchor":"src-v14c2-e9e1005a7e01","archive_id":"v14c2","authority_effect":"NONE","bytes":1372,"carrier":"16_LION_ACTION_IR.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_ACTION_MODEL_v1_4_candidate.source.md","sha256":"93a482ec6af3d4f1b1292cd62fe3fd424df48ee882d1e1592a3a35edd7d6dbc1","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-e9e1005a7e01","virtual_path":"v14c2/LION_ACTION_MODEL_v1_4_candidate.source.md"}
````markdown
# LION Action Model v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=AS_IS_PLUS_TARGET_BOUNDARY
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=ActionSpec/LAIR/proposal/PDP/runtime-admission chain
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

```text
ActionIntent != ActionSpec
ActionSpec != CanonicalActionIR
CanonicalActionIR != ActionProposal
ActionProposal != PDPResult
PDPResult != RuntimeAdmission
RuntimeAdmission != Effect
Reported Effect != Observed Effect
Observed Effect != Reconciled Closure
```

Current integrated chain:

```text
ActionSpec → CanonicalActionIR → static projection → explicit ActionProposal context → ActionProposal → canonical PDP → PDPResult
```

Current missing canonical binding:

```text
PDPResult(ALLOW)
→ exact RequestedRuntimeEffect
+ RuntimeIdentityBinding
+ current authority/currentness
→ RuntimeAdmissionEngine
```

No new executor or effect provider is authorized by this model.

````
LION_RECORD_END: SRC-V14C2-e9e1005a7e01

<a id="src-v14c2-abd17ba6d3e6"></a>
## SRC-V14C2-abd17ba6d3e6 — v14c2/scaffold/action_ir.schema.json

SOURCE_ID=SRC-V14C2-abd17ba6d3e6
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=scaffold/action_ir.schema.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=b652180ea03b75add7e1357f210d6395aee8bae9b16361dca48eb84445c8b4ba
SOURCE_BYTES=7549

LION_RECORD_BEGIN: SRC-V14C2-abd17ba6d3e6
LION_RECORD_META: {"anchor":"src-v14c2-abd17ba6d3e6","archive_id":"v14c2","authority_effect":"NONE","bytes":7549,"carrier":"16_LION_ACTION_IR.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"scaffold/action_ir.schema.json","sha256":"b652180ea03b75add7e1357f210d6395aee8bae9b16361dca48eb84445c8b4ba","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-abd17ba6d3e6","virtual_path":"v14c2/scaffold/action_ir.schema.json"}
````json
{
  "$defs": {
    "uniqueStrings": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "type": "array",
      "uniqueItems": true
    }
  },
  "$id": "lion://schemas/action-ir/v1.4-candidate-projection",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "allOf": [
    {
      "if": {
        "properties": {
          "kind": {
            "const": "process.exec"
          }
        }
      },
      "then": {
        "required": [
          "executable",
          "arguments",
          "workspace",
          "environment",
          "io"
        ]
      }
    }
  ],
  "properties": {
    "action_id": {
      "pattern": "^[A-Za-z][A-Za-z0-9_.:-]{0,255}$",
      "type": "string"
    },
    "arguments": {
      "items": {
        "maxLength": 4096,
        "type": "string"
      },
      "maxItems": 256,
      "type": "array"
    },
    "authority_request": {
      "additionalProperties": false,
      "properties": {
        "capability": {
          "minLength": 1,
          "type": "string"
        },
        "domain": {
          "minLength": 1,
          "type": "string"
        },
        "grant_ref": {
          "type": [
            "string",
            "null"
          ]
        }
      },
      "required": [
        "domain",
        "capability",
        "grant_ref"
      ],
      "type": "object"
    },
    "autonomy_ref": {
      "minLength": 1,
      "type": "string"
    },
    "bean_ref": {
      "minLength": 1,
      "type": "string"
    },
    "boundary": {
      "additionalProperties": false,
      "properties": {
        "filesystem_read": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "filesystem_write": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "max_processes": {
          "maximum": 128,
          "minimum": 1,
          "type": "integer"
        },
        "memory_limit_bytes": {
          "minimum": 1048576,
          "type": "integer"
        },
        "network": {
          "enum": [
            "DENY",
            "READ_ONLY_PINNED",
            "ALLOW_EXACT"
          ]
        },
        "process_children": {
          "$ref": "#/$defs/uniqueStrings"
        },
        "shell": {
          "const": false
        },
        "timeout_ms": {
          "maximum": 3600000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "required": [
        "shell",
        "network",
        "filesystem_read",
        "filesystem_write",
        "process_children",
        "timeout_ms",
        "max_processes",
        "memory_limit_bytes"
      ],
      "type": "object"
    },
    "environment": {
      "additionalProperties": false,
      "properties": {
        "allow": {
          "additionalProperties": {
            "maxLength": 4096,
            "type": "string"
          },
          "type": "object"
        },
        "inherit": {
          "const": false
        }
      },
      "required": [
        "inherit",
        "allow"
      ],
      "type": "object"
    },
    "executable": {
      "additionalProperties": false,
      "properties": {
        "digest": {
          "pattern": "^sha256:[0-9a-f]{64}$",
          "type": "string"
        },
        "path": {
          "pattern": "^/",
          "type": "string"
        }
      },
      "required": [
        "path",
        "digest"
      ],
      "type": "object"
    },
    "expected_effects": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "forbidden_effects": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "intent_ref": {
      "minLength": 1,
      "type": "string"
    },
    "io": {
      "additionalProperties": false,
      "properties": {
        "stderr": {
          "enum": [
            "CAPTURE",
            "DISCARD"
          ]
        },
        "stdin": {
          "const": "NONE"
        },
        "stdout": {
          "enum": [
            "CAPTURE",
            "DISCARD"
          ]
        },
        "tty": {
          "const": false
        }
      },
      "required": [
        "stdin",
        "stdout",
        "stderr",
        "tty"
      ],
      "type": "object"
    },
    "kind": {
      "enum": [
        "process.exec",
        "filesystem.read",
        "filesystem.write",
        "repository.observe",
        "repository.prepare_candidate",
        "repository.attach_exact",
        "test.execute",
        "artifact.generate",
        "robot.task"
      ]
    },
    "mission_ref": {
      "minLength": 1,
      "type": "string"
    },
    "observation": {
      "additionalProperties": false,
      "properties": {
        "observer_class": {
          "enum": [
            "independent",
            "deterministic_independent"
          ]
        },
        "required_events": {
          "$ref": "#/$defs/uniqueStrings"
        }
      },
      "required": [
        "observer_class",
        "required_events"
      ],
      "type": "object"
    },
    "preconditions": {
      "$ref": "#/$defs/uniqueStrings"
    },
    "reconciliation": {
      "additionalProperties": false,
      "properties": {
        "mode": {
          "enum": [
            "EXACT",
            "PHYSICAL_POSTCONDITION"
          ]
        },
        "receipt": {
          "const": "REQUIRED"
        }
      },
      "required": [
        "mode",
        "receipt"
      ],
      "type": "object"
    },
    "schema_version": {
      "const": "1.0.0"
    },
    "target": {
      "additionalProperties": false,
      "properties": {
        "environment": {
          "minLength": 1,
          "type": "string"
        },
        "host": {
          "minLength": 1,
          "type": "string"
        },
        "runtime": {
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "host",
        "environment",
        "runtime"
      ],
      "type": "object"
    },
    "workspace": {
      "additionalProperties": false,
      "properties": {
        "commit": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        },
        "path": {
          "pattern": "^/",
          "type": "string"
        },
        "repository": {
          "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
          "type": "string"
        },
        "tree": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        }
      },
      "required": [
        "repository",
        "commit",
        "tree",
        "path"
      ],
      "type": "object"
    }
  },
  "required": [
    "schema_version",
    "action_id",
    "kind",
    "intent_ref",
    "mission_ref",
    "autonomy_ref",
    "bean_ref",
    "target",
    "authority_request",
    "boundary",
    "preconditions",
    "expected_effects",
    "forbidden_effects",
    "observation",
    "reconciliation"
  ],
  "title": "LION ActionSpec / Action IR v1.4 candidate projection of canonical v1 contract",
  "type": "object",
  "x-lion-v1_4-projection": {
    "canonical_schema_id": "cyberlion://schemas/action-spec/v1",
    "canonical_schema_version": "1.0.0",
    "canonical_action_ir": "cyber_lion/contracts/action_ir.py",
    "status": "AS_IS_PARTIALLY_IMPLEMENTED",
    "pdp_handoff": "INTEGRATED",
    "next_minimal_gap": "bind canonical PDP ALLOW result to exact RequestedRuntimeEffect and runtime identity before RuntimeAdmissionEngine",
    "authority_effect": "NONE",
    "note": "Do not confuse this detached package projection with the live canonical schema file."
  }
}

````
LION_RECORD_END: SRC-V14C2-abd17ba6d3e6
