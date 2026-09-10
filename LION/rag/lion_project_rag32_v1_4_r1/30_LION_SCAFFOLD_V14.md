# LION — Odtworzony scaffold v1.4 — materiał porównawczy

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=30_SCAFFOLD_V14
SEARCH_TERMS=reconstructed scaffold validator tests EBNF semantic regression candidate
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

Ostrzeżenie: ten wcześniejszy scaffold v1.4 jest rekonstrukcją o innym interfejsie i słabszym zestawie kontroli niż oryginał v1.3. Nie używaj go jako zatwierdzonego upgrade walidatora. Patrz 04 i źródła 29.

## Rekordy źródłowe

<a id="src-v14c2-4026f9a9f090"></a>
## SRC-V14C2-4026f9a9f090 — v14c2/scaffold/README.md

SOURCE_ID=SRC-V14C2-4026f9a9f090
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=scaffold/README.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=650443b5ec247b2ff428f901288e31efe040a9f320b708f930443ca2c650a6e6
SOURCE_BYTES=270

LION_RECORD_BEGIN: SRC-V14C2-4026f9a9f090
LION_RECORD_META: {"anchor":"src-v14c2-4026f9a9f090","archive_id":"v14c2","authority_effect":"NONE","bytes":270,"carrier":"30_LION_SCAFFOLD_V14.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"scaffold/README.md","sha256":"650443b5ec247b2ff428f901288e31efe040a9f320b708f930443ca2c650a6e6","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-4026f9a9f090","virtual_path":"v14c2/scaffold/README.md"}
````markdown
# v1.4 detached validation scaffold

Dependency-free validation helpers. They do not access network, execute system effects, mutate repositories, grant authority or claim canonical integration. `.pyc` cache from the v1.3 package topology is deliberately not propagated.

````
LION_RECORD_END: SRC-V14C2-4026f9a9f090

<a id="src-v14c2-0e1879d3bef4"></a>
## SRC-V14C2-0e1879d3bef4 — v14c2/scaffold/canonical_state.schema.json

SOURCE_ID=SRC-V14C2-0e1879d3bef4
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=scaffold/canonical_state.schema.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=36838127548d5f9802a286deb2c76bb161e7a9af0b55bc1974210b04ef21437e
SOURCE_BYTES=1685

LION_RECORD_BEGIN: SRC-V14C2-0e1879d3bef4
LION_RECORD_META: {"anchor":"src-v14c2-0e1879d3bef4","archive_id":"v14c2","authority_effect":"NONE","bytes":1685,"carrier":"30_LION_SCAFFOLD_V14.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"scaffold/canonical_state.schema.json","sha256":"36838127548d5f9802a286deb2c76bb161e7a9af0b55bc1974210b04ef21437e","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-0e1879d3bef4","virtual_path":"v14c2/scaffold/canonical_state.schema.json"}
````json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "lion://schemas/canonical-state/v1.4-candidate",
  "title": "LION canonical state v1.4 detached schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "baseline",
    "records"
  ],
  "properties": {
    "schema_version": {
      "const": "lion.canonical-state/v1.4-candidate"
    },
    "baseline": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "repository",
        "head",
        "tree"
      ],
      "properties": {
        "repository": {
          "type": "string"
        },
        "head": {
          "type": "string",
          "pattern": "^[0-9a-f]{40}$"
        },
        "tree": {
          "type": "string",
          "pattern": "^[0-9a-f]{40}$"
        },
        "truth_subject_digest": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      }
    },
    "records": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "id",
          "plane",
          "status"
        ],
        "properties": {
          "id": {
            "type": "string"
          },
          "plane": {
            "enum": [
              "AS_IS",
              "CANDIDATE",
              "TARGET",
              "UNKNOWN",
              "HISTORICAL"
            ]
          },
          "status": {
            "type": "string"
          },
          "evidence_refs": {
            "type": "array",
            "items": {
              "type": "string"
            }
          }
        },
        "additionalProperties": true
      }
    }
  }
}

````
LION_RECORD_END: SRC-V14C2-0e1879d3bef4

<a id="src-v14c2-33eecdb5d9ab"></a>
## SRC-V14C2-33eecdb5d9ab — v14c2/scaffold/lcms.ebnf

SOURCE_ID=SRC-V14C2-33eecdb5d9ab
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=scaffold/lcms.ebnf
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=23c51c14742ec5f48e1335f711b2891f1f66f19118338f12bf1b09ffb4be9b2f
SOURCE_BYTES=899

LION_RECORD_BEGIN: SRC-V14C2-33eecdb5d9ab
LION_RECORD_META: {"anchor":"src-v14c2-33eecdb5d9ab","archive_id":"v14c2","authority_effect":"NONE","bytes":899,"carrier":"30_LION_SCAFFOLD_V14.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"ebnf","original_path":"scaffold/lcms.ebnf","sha256":"23c51c14742ec5f48e1335f711b2891f1f66f19118338f12bf1b09ffb4be9b2f","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-33eecdb5d9ab","virtual_path":"v14c2/scaffold/lcms.ebnf"}
````ebnf
(* Detached v1.4 design grammar. Never execute directly. *)
command = action_id, ws, kind, ws, target, ws, authority, ws, boundary ;
action_id = identifier ;
kind = "process.exec" | "filesystem.read" | "repository.observe" | "test.execute" | "artifact.generate" ;
target = "target", "(", identifier, ")" ;
authority = "authority", "(", identifier, ")" ;
boundary = "boundary", "(", "shell=false", ",", "network=DENY", ")" ;
identifier = letter, { letter | digit | "_" | "-" | "." | ":" } ;
ws = " ", { " " } ;
letter = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "I" | "J" | "K" | "L" | "M" | "N" | "O" | "P" | "Q" | "R" | "S" | "T" | "U" | "V" | "W" | "X" | "Y" | "Z" | "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j" | "k" | "l" | "m" | "n" | "o" | "p" | "q" | "r" | "s" | "t" | "u" | "v" | "w" | "x" | "y" | "z" ;
digit = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;

````
LION_RECORD_END: SRC-V14C2-33eecdb5d9ab

<a id="src-v14c2-d165e1c30e47"></a>
## SRC-V14C2-d165e1c30e47 — v14c2/scaffold/test_validate_canonical_state.py

SOURCE_ID=SRC-V14C2-d165e1c30e47
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=scaffold/test_validate_canonical_state.py
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=0c65a5729d39e908f01a42d6ba6cce7c68136818b3332ed968f4489c08d50017
SOURCE_BYTES=663

LION_RECORD_BEGIN: SRC-V14C2-d165e1c30e47
LION_RECORD_META: {"anchor":"src-v14c2-d165e1c30e47","archive_id":"v14c2","authority_effect":"NONE","bytes":663,"carrier":"30_LION_SCAFFOLD_V14.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"python","original_path":"scaffold/test_validate_canonical_state.py","sha256":"0c65a5729d39e908f01a42d6ba6cce7c68136818b3332ed968f4489c08d50017","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-d165e1c30e47","virtual_path":"v14c2/scaffold/test_validate_canonical_state.py"}
````python
import unittest
from validate_canonical_state import validate
B={"schema_version":"lion.canonical-state/v1.4-candidate","baseline":{"repository":"x/y","head":"0"*40,"tree":"1"*40},"records":[]}
class T(unittest.TestCase):
 def test_base(self): self.assertTrue(validate(B))
 def test_target_live_fails(self):
  s={**B,"records":[{"id":"x","plane":"TARGET","status":"TARGET","evidence_classes":["LIVE_CODE"]}]}
  with self.assertRaises(ValueError): validate(s)
 def test_current_without_basis_fails(self):
  s={**B,"records":[{"id":"x","plane":"AS_IS","status":"CURRENT"}]}
  with self.assertRaises(ValueError): validate(s)
if __name__=="__main__": unittest.main()

````
LION_RECORD_END: SRC-V14C2-d165e1c30e47

<a id="src-v14c2-2b6dff33b7f2"></a>
## SRC-V14C2-2b6dff33b7f2 — v14c2/scaffold/validate_canonical_state.py

SOURCE_ID=SRC-V14C2-2b6dff33b7f2
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=scaffold/validate_canonical_state.py
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=6fde7eb98978587810ee1964ade4c8d1e6e24b71a0159f7e000ef17054329307
SOURCE_BYTES=1230

LION_RECORD_BEGIN: SRC-V14C2-2b6dff33b7f2
LION_RECORD_META: {"anchor":"src-v14c2-2b6dff33b7f2","archive_id":"v14c2","authority_effect":"NONE","bytes":1230,"carrier":"30_LION_SCAFFOLD_V14.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"python","original_path":"scaffold/validate_canonical_state.py","sha256":"6fde7eb98978587810ee1964ade4c8d1e6e24b71a0159f7e000ef17054329307","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-2b6dff33b7f2","virtual_path":"v14c2/scaffold/validate_canonical_state.py"}
````python
#!/usr/bin/env python3
"""Dependency-free structural validator for detached v1.4 canonical-state projections.
No network, execution or mutation authority.
"""
import json,re,sys
SHA40=re.compile(r"^[0-9a-f]{40}$")
LIVE={"LIVE_CODE","CURRENT_TEST","EXACT_GIT_STATE","MACHINE_EVIDENCE"}

def validate(state):
    if state.get("schema_version")!="lion.canonical-state/v1.4-candidate": raise ValueError("schema_version")
    b=state.get("baseline") or {}
    if not SHA40.fullmatch(b.get("head", "")) or not SHA40.fullmatch(b.get("tree", "")): raise ValueError("exact baseline")
    seen=set()
    for r in state.get("records",[]):
        i=r.get("id"); plane=r.get("plane"); status=r.get("status","")
        if not i or i in seen: raise ValueError("duplicate/empty id")
        seen.add(i)
        ev=set(r.get("evidence_classes",[]))
        if plane=="TARGET" and ev & LIVE: raise ValueError("TARGET cannot carry live implementation evidence")
        if status=="CURRENT" and not r.get("currentness_basis"): raise ValueError("CURRENT requires currentness_basis")
    return True

def main(path):
    with open(path,encoding="utf-8") as f: s=json.load(f)
    validate(s); print("PASS")
if __name__=="__main__": main(sys.argv[1])

````
LION_RECORD_END: SRC-V14C2-2b6dff33b7f2
