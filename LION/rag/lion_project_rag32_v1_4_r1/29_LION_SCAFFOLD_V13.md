# LION — Oryginalny scaffold, walidator, testy i gramatyka v1.3

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=29_SCAFFOLD_V13
SEARCH_TERMS=original scaffold canonical state validator tests LCMS EBNF 57 lines
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

To jest oryginalny scaffold v1.3 odzyskany z pełnego archiwum, nie wcześniejsza rekonstrukcja. Nie oznacza to jego zgodności z aktualnym runtime. Odtworzenie pliku nie uprawnia do wykonania.

## Rekordy źródłowe

<a id="src-v13-4026f9a9f090"></a>
## SRC-V13-4026f9a9f090 — v13/scaffold/README.md

SOURCE_ID=SRC-V13-4026f9a9f090
SOURCE_ARCHIVE=v13
SOURCE_PATH=scaffold/README.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=d87e2c4b5ea9622a40ce307273742b533e78e0d191b9b72b1e47fa2313583c99
SOURCE_BYTES=806

LION_RECORD_BEGIN: SRC-V13-4026f9a9f090
LION_RECORD_META: {"anchor":"src-v13-4026f9a9f090","archive_id":"v13","authority_effect":"NONE","bytes":806,"carrier":"29_LION_SCAFFOLD_V13.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"scaffold/README.md","sha256":"d87e2c4b5ea9622a40ce307273742b533e78e0d191b9b72b1e47fa2313583c99","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-4026f9a9f090","virtual_path":"v13/scaffold/README.md"}
````markdown
# Truth-plane and Action-plane candidate scaffold

This scaffold is detached, read-only and authority-free.

## Validate canonical state

```bash
python scaffold/validate_canonical_state.py   --state example-canonical-state.json   --repository DonkeyJJLove/ai_platform   --head 2be0b312407920ac25d812f1c0bb6ecfcb31aa4c   --tree 3c9705f85301e73f268228f3c36f6ae82a641633
```

The validator rejects baseline drift, duplicate components, unknown states,
`TARGET` components that carry observed implementation paths, and integrated
components without evidence paths.

## Tests

```bash
python -m unittest discover -s scaffold -p "test_*.py" -v
```

`action_ir.schema.json` and `lcms.ebnf` are design candidates only. No executor,
network client, repository mutator, package installer or credential path exists.

````
LION_RECORD_END: SRC-V13-4026f9a9f090

<a id="src-v13-0e1879d3bef4"></a>
## SRC-V13-0e1879d3bef4 — v13/scaffold/canonical_state.schema.json

SOURCE_ID=SRC-V13-0e1879d3bef4
SOURCE_ARCHIVE=v13
SOURCE_PATH=scaffold/canonical_state.schema.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=a561d224e2e9c7ce23c06aee330660c95aeb3d44c0e7bc6321d1b1400d5f2af1
SOURCE_BYTES=2286

LION_RECORD_BEGIN: SRC-V13-0e1879d3bef4
LION_RECORD_META: {"anchor":"src-v13-0e1879d3bef4","archive_id":"v13","authority_effect":"NONE","bytes":2286,"carrier":"29_LION_SCAFFOLD_V13.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"scaffold/canonical_state.schema.json","sha256":"a561d224e2e9c7ce23c06aee330660c95aeb3d44c0e7bc6321d1b1400d5f2af1","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-0e1879d3bef4","virtual_path":"v13/scaffold/canonical_state.schema.json"}
````json
{
  "$id": "lion://schemas/canonical-state/v1.3-candidate",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "properties": {
    "baseline": {
      "additionalProperties": false,
      "properties": {
        "branch": {
          "minLength": 1,
          "type": "string"
        },
        "head": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        },
        "repository": {
          "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
          "type": "string"
        },
        "state": {
          "enum": [
            "CURRENT",
            "STALE",
            "UNKNOWN"
          ]
        },
        "tree": {
          "pattern": "^[0-9a-f]{40}$",
          "type": "string"
        }
      },
      "required": [
        "repository",
        "branch",
        "head",
        "tree",
        "state"
      ],
      "type": "object"
    },
    "components": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "id": {
            "minLength": 1,
            "type": "string"
          },
          "observed_paths": {
            "items": {
              "minLength": 1,
              "type": "string"
            },
            "type": "array",
            "uniqueItems": true
          },
          "state": {
            "enum": [
              "INTEGRATED",
              "OBSERVED",
              "REPRODUCED",
              "VERIFIED",
              "VERIFIED_CANDIDATE",
              "IMPLEMENTED_NOT_LIVE",
              "EXPERIMENTAL",
              "TARGET",
              "QUARANTINED",
              "DEGRADED",
              "RESTRICTED",
              "FROZEN",
              "FALSIFIED",
              "SUPERSEDED",
              "HISTORICAL",
              "STALE",
              "CONFLICTED",
              "UNKNOWN"
            ]
          }
        },
        "required": [
          "id",
          "state",
          "observed_paths"
        ],
        "type": "object"
      },
      "type": "array"
    },
    "schema_version": {
      "const": "lion.canonical-state/v1.3-candidate"
    }
  },
  "required": [
    "schema_version",
    "baseline",
    "components"
  ],
  "title": "LION canonical state candidate",
  "type": "object"
}

````
LION_RECORD_END: SRC-V13-0e1879d3bef4

<a id="src-v13-33eecdb5d9ab"></a>
## SRC-V13-33eecdb5d9ab — v13/scaffold/lcms.ebnf

SOURCE_ID=SRC-V13-33eecdb5d9ab
SOURCE_ARCHIVE=v13
SOURCE_PATH=scaffold/lcms.ebnf
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=b2ebe55113efd8d033c396156e2653346bf0293109b6e9c8d24562caf5c5e745
SOURCE_BYTES=2399

LION_RECORD_BEGIN: SRC-V13-33eecdb5d9ab
LION_RECORD_META: {"anchor":"src-v13-33eecdb5d9ab","archive_id":"v13","authority_effect":"NONE","bytes":2399,"carrier":"29_LION_SCAFFOLD_V13.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"ebnf","original_path":"scaffold/lcms.ebnf","sha256":"b2ebe55113efd8d033c396156e2653346bf0293109b6e9c8d24562caf5c5e745","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-33eecdb5d9ab","virtual_path":"v13/scaffold/lcms.ebnf"}
````ebnf
document          = action | plan ;

action            = "ACTION", identifier, "{", action-field*, "}" ;
plan              = "PLAN", identifier, "{", plan-field*, "}" ;

action-field      = scalar-field
                  | target-block
                  | executable-block
                  | arguments-field
                  | workspace-block
                  | environment-block
                  | io-block
                  | authority-block
                  | boundary-block
                  | string-list-field
                  | observation-block
                  | reconciliation-block ;

plan-field        = scalar-field | node-block | edge-block | string-list-field ;
scalar-field      = identifier, "=", scalar, ";" ;
string-list-field = identifier, "=", "[", [ string, { ",", string } ], "]", ";" ;

target-block      = "target", object-block ;
executable-block  = "executable", object-block ;
workspace-block   = "workspace", object-block ;
environment-block = "environment", object-block ;
io-block          = "io", object-block ;
authority-block   = "authority_request", object-block ;
boundary-block    = "boundary", object-block ;
observation-block = "observation", object-block ;
reconciliation-block = "reconciliation", object-block ;
node-block        = "NODE", identifier, object-block ;
edge-block        = "EDGE", identifier, object-block ;

object-block      = "{", object-field*, "}" ;
object-field      = identifier, "=", ( scalar | list | map ), ";" ;
map               = "{", [ map-entry, { ",", map-entry } ], "}" ;
map-entry         = string, ":", string ;
list              = "[", [ scalar, { ",", scalar } ], "]" ;

scalar            = string | integer | boolean | null ;
identifier        = qualified-name ;
qualified-name    = segment, { ":", segment } ;
segment           = letter, { letter | digit | "-" | "_" | "." } ;
string            = '"', character*, '"' ;
integer           = [ "-" ], digit, { digit } ;
boolean           = "true" | "false" ;
null              = "null" ;
letter            = "A"…"Z" | "a"…"z" ;
digit             = "0"…"9" ;

(* Normative rules:
   UTF-8 NFC only. Unknown/duplicate fields are errors. No aliases.
   No implicit effect-changing defaults. Map keys sort canonically.
   Paths are absolute and normalized. Raw shell strings, substitutions,
   redirections and background operators are not execution semantics.
*)

````
LION_RECORD_END: SRC-V13-33eecdb5d9ab

<a id="src-v13-d165e1c30e47"></a>
## SRC-V13-d165e1c30e47 — v13/scaffold/test_validate_canonical_state.py

SOURCE_ID=SRC-V13-d165e1c30e47
SOURCE_ARCHIVE=v13
SOURCE_PATH=scaffold/test_validate_canonical_state.py
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=99869dcc33e59249dcec719ea8c7750f5ba52c8fbb04359aa047fcc2ef3293ef
SOURCE_BYTES=2416

LION_RECORD_BEGIN: SRC-V13-d165e1c30e47
LION_RECORD_META: {"anchor":"src-v13-d165e1c30e47","archive_id":"v13","authority_effect":"NONE","bytes":2416,"carrier":"29_LION_SCAFFOLD_V13.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"python","original_path":"scaffold/test_validate_canonical_state.py","sha256":"99869dcc33e59249dcec719ea8c7750f5ba52c8fbb04359aa047fcc2ef3293ef","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-d165e1c30e47","virtual_path":"v13/scaffold/test_validate_canonical_state.py"}
````python
from __future__ import annotations
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_canonical_state import CanonicalStateError, validate_state

HEAD = "a" * 40
TREE = "b" * 40
REPO = "owner/repo"

def valid():
    return {
        "schema_version":"lion.canonical-state/v1.3-candidate",
        "baseline":{"repository":REPO,"branch":"master","head":HEAD,"tree":TREE,"state":"CURRENT"},
        "components":[
            {"id":"BeanSpec","state":"INTEGRATED","observed_paths":["cyber_lion/contracts/bean.py"]},
            {"id":"ActionSpec","state":"TARGET","observed_paths":[]},
        ],
    }

class CanonicalStateTests(unittest.TestCase):
    def call(self, payload):
        return validate_state(payload, observed_repository=REPO,
                              observed_head=HEAD, observed_tree=TREE)
    def test_valid_current_state(self):
        self.assertEqual(self.call(valid())["validation"], "PASS")
    def test_head_drift_fails_closed(self):
        payload=valid(); payload["baseline"]["head"]="c"*40
        with self.assertRaisesRegex(CanonicalStateError, "CURRENT baseline drift"): self.call(payload)
    def test_duplicate_component_fails_closed(self):
        payload=valid(); payload["components"].append(copy.deepcopy(payload["components"][0]))
        with self.assertRaisesRegex(CanonicalStateError, "duplicate component"): self.call(payload)
    def test_unknown_state_fails_closed(self):
        payload=valid(); payload["components"][0]["state"]="PROBABLY_FINE"
        with self.assertRaisesRegex(CanonicalStateError, "unknown epistemic state"): self.call(payload)
    def test_target_with_observed_path_fails_closed(self):
        payload=valid(); payload["components"][1]["observed_paths"]=["exists.py"]
        with self.assertRaisesRegex(CanonicalStateError, "TARGET component"): self.call(payload)
    def test_integrated_without_evidence_path_fails_closed(self):
        payload=valid(); payload["components"][0]["observed_paths"]=[]
        with self.assertRaisesRegex(CanonicalStateError, "requires observed paths"): self.call(payload)
    def test_extra_field_fails_closed(self):
        payload=valid(); payload["authority"]="none"
        with self.assertRaisesRegex(CanonicalStateError, "root fields must be exact"): self.call(payload)

if __name__ == "__main__":
    unittest.main()

````
LION_RECORD_END: SRC-V13-d165e1c30e47

<a id="src-v13-2b6dff33b7f2"></a>
## SRC-V13-2b6dff33b7f2 — v13/scaffold/validate_canonical_state.py

SOURCE_ID=SRC-V13-2b6dff33b7f2
SOURCE_ARCHIVE=v13
SOURCE_PATH=scaffold/validate_canonical_state.py
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=9a20e63551b75768c0adc38cd0fe20d1cd6d1e41585306540fd2feda709adacc
SOURCE_BYTES=5110

LION_RECORD_BEGIN: SRC-V13-2b6dff33b7f2
LION_RECORD_META: {"anchor":"src-v13-2b6dff33b7f2","archive_id":"v13","authority_effect":"NONE","bytes":5110,"carrier":"29_LION_SCAFFOLD_V13.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"python","original_path":"scaffold/validate_canonical_state.py","sha256":"9a20e63551b75768c0adc38cd0fe20d1cd6d1e41585306540fd2feda709adacc","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-2b6dff33b7f2","virtual_path":"v13/scaffold/validate_canonical_state.py"}
````python
"""Fail-closed, dependency-free LION canonical-state validator.

No network calls. No repository or host mutation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
STATES = frozenset({
    "INTEGRATED", "OBSERVED", "REPRODUCED", "VERIFIED",
    "VERIFIED_CANDIDATE", "IMPLEMENTED_NOT_LIVE", "EXPERIMENTAL",
    "TARGET", "QUARANTINED", "DEGRADED", "RESTRICTED", "FROZEN",
    "FALSIFIED", "SUPERSEDED", "HISTORICAL", "STALE", "CONFLICTED",
    "UNKNOWN",
})

class CanonicalStateError(ValueError):
    pass

def _exact_dict(value: Any, name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise CanonicalStateError(f"{name} must be an exact object")
    return value

def validate_state(payload: Any, *, observed_repository: str,
                   observed_head: str, observed_tree: str) -> dict[str, Any]:
    root = _exact_dict(payload, "root")
    if set(root) != {"schema_version", "baseline", "components"}:
        raise CanonicalStateError("root fields must be exact")
    if root["schema_version"] != "lion.canonical-state/v1.3-candidate":
        raise CanonicalStateError("schema_version mismatch")

    baseline = _exact_dict(root["baseline"], "baseline")
    if set(baseline) != {"repository", "branch", "head", "tree", "state"}:
        raise CanonicalStateError("baseline fields must be exact")
    if not REPOSITORY.fullmatch(str(baseline["repository"])):
        raise CanonicalStateError("baseline repository invalid")
    for key in ("head", "tree"):
        if not SHA40.fullmatch(str(baseline[key])):
            raise CanonicalStateError(f"baseline {key} invalid")
    if baseline["state"] not in {"CURRENT", "STALE", "UNKNOWN"}:
        raise CanonicalStateError("baseline state invalid")

    observed = (observed_repository, observed_head, observed_tree)
    declared = (baseline["repository"], baseline["head"], baseline["tree"])
    if baseline["state"] == "CURRENT" and declared != observed:
        raise CanonicalStateError(
            "CURRENT baseline drift: declared identity differs from observed identity"
        )

    components = root["components"]
    if type(components) is not list:
        raise CanonicalStateError("components must be a list")
    seen: set[str] = set()
    normalized = []
    for index, raw in enumerate(components):
        component = _exact_dict(raw, f"components[{index}]")
        if set(component) != {"id", "state", "observed_paths"}:
            raise CanonicalStateError("component fields must be exact")
        component_id = component["id"]
        if not isinstance(component_id, str) or not component_id.strip():
            raise CanonicalStateError("component id invalid")
        if component_id in seen:
            raise CanonicalStateError(f"duplicate component id: {component_id}")
        seen.add(component_id)
        state = component["state"]
        if state not in STATES:
            raise CanonicalStateError(f"unknown epistemic state: {state}")
        paths = component["observed_paths"]
        if type(paths) is not list or any(
            not isinstance(path, str) or not path.strip() for path in paths
        ):
            raise CanonicalStateError("observed_paths invalid")
        if len(paths) != len(set(paths)):
            raise CanonicalStateError("observed_paths must be unique")
        if state == "TARGET" and paths:
            raise CanonicalStateError(
                f"TARGET component {component_id} cannot carry observed paths"
            )
        if state in {"INTEGRATED", "OBSERVED", "REPRODUCED", "VERIFIED"} and not paths:
            raise CanonicalStateError(
                f"{state} component {component_id} requires observed paths"
            )
        normalized.append({
            "id": component_id,
            "state": state,
            "observed_paths": sorted(paths),
        })
    return {
        "schema_version": root["schema_version"],
        "baseline": dict(baseline),
        "components": sorted(normalized, key=lambda item: item["id"]),
        "validation": "PASS",
    }

def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--tree", required=True)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.state.read_text(encoding="utf-8"))
        result = validate_state(payload, observed_repository=args.repository,
                                observed_head=args.head, observed_tree=args.tree)
    except (OSError, json.JSONDecodeError, CanonicalStateError) as exc:
        print(json.dumps({"validation":"FAIL","reason":str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",",":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

````
LION_RECORD_END: SRC-V13-2b6dff33b7f2
