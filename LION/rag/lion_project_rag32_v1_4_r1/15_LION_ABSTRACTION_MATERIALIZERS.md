# LION — Abstraction Compiler i rejestry materializerów

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=15_ABSTRACTION_MATERIALIZERS
SEARCH_TERMS=Abstraction Compiler MaterializerRegistry representations validator verifier
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-55c461758407"></a>
## SRC-V13-55c461758407 — v13/LION_ABSTRACTION_COMPILER_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-55c461758407
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_ABSTRACTION_COMPILER_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=c0366be0a9e0c95cd08f69cef9751db3650a0c9f444bec65dafff30f5ec2400d
SOURCE_BYTES=1082

LION_RECORD_BEGIN: SRC-V13-55c461758407
LION_RECORD_META: {"anchor":"src-v13-55c461758407","archive_id":"v13","authority_effect":"NONE","bytes":1082,"carrier":"15_LION_ABSTRACTION_MATERIALIZERS.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_ABSTRACTION_COMPILER_v1_3_candidate.source.md","sha256":"c0366be0a9e0c95cd08f69cef9751db3650a0c9f444bec65dafff30f5ec2400d","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-55c461758407","virtual_path":"v13/LION_ABSTRACTION_COMPILER_v1_3_candidate.source.md"}
````markdown
# LION Abstraction Compiler v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=PARTIAL_RESEARCH_TARGET
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=representation selection and materialization
DEPENDENCIES=GlitchLab + Bean Factory + Action model
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

The compiler chooses a representation from the required effect and target medium. Current or partial representations include source-code candidates, policy/test/evidence artifacts and simulations. Canonical Action IR is introduced only as a detached schema. Machine-control, robot-task, PLC and CAD/CAM outputs remain unsupported targets.

Every supported representation requires a typed input schema, Materializer, Validator, independent Verifier, authority contract for activation, Effect Provider, Observer and Reconciler. A model alone is not a Materializer.

````
LION_RECORD_END: SRC-V13-55c461758407

<a id="src-v13-5426439e1308"></a>
## SRC-V13-5426439e1308 — v13/LION_MATERIALIZER_REGISTRY_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-5426439e1308
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_MATERIALIZER_REGISTRY_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=fbaf330fd571dcc294288feaea624125d0bbf1af1ba1f8b8b4fcbc8b7a5c6642
SOURCE_BYTES=1616

LION_RECORD_BEGIN: SRC-V13-5426439e1308
LION_RECORD_META: {"anchor":"src-v13-5426439e1308","archive_id":"v13","authority_effect":"NONE","bytes":1616,"carrier":"15_LION_ABSTRACTION_MATERIALIZERS.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_MATERIALIZER_REGISTRY_v1_3_candidate.source.json","sha256":"fbaf330fd571dcc294288feaea624125d0bbf1af1ba1f8b8b4fcbc8b7a5c6642","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-5426439e1308","virtual_path":"v13/LION_MATERIALIZER_REGISTRY_v1_3_candidate.source.json"}
````json
{
  "entries": [
    {
      "authority": "externally issued BuilderInvocationPermit",
      "domains": [
        "software"
      ],
      "effect": "candidate preparation only",
      "implementation": "existing E004 builder chain + BeanBuilderChainBinding",
      "input": "BeanSpec / repository change intent",
      "materializer_id": "python-source-materializer",
      "output": "DetachedRepositoryCandidate / BeanCandidate",
      "state": "PARTIAL_EXISTING_BUILDER_CHAIN",
      "verification": "independent candidate verifier"
    },
    {
      "authority": "NONE for generation",
      "domains": [
        "governance"
      ],
      "effect": "NONE",
      "input": "PolicyIntent",
      "materializer_id": "policy-materializer",
      "output": "PolicyCandidate",
      "state": "TARGET"
    },
    {
      "authority": "EffectPermit for execution",
      "domains": [
        "local-compute"
      ],
      "effect": "process execution only after PEP",
      "input": "ActionIntent",
      "materializer_id": "console-command-materializer",
      "output": "canonical Action IR",
      "state": "TARGET"
    },
    {
      "authority": "NONE in simulation; typed physical permit for hardware",
      "domains": [
        "cyber-physical"
      ],
      "effect": "SIMULATION_ONLY until safety plane",
      "input": "PhysicalActionIntent",
      "materializer_id": "robot-task-materializer",
      "output": "PhysicalActionSpec + simulation plan",
      "state": "RESEARCH_TARGET"
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "schema_version": "lion.materializer-registry/v1.3-candidate"
}

````
LION_RECORD_END: SRC-V13-5426439e1308

<a id="src-v14c2-b06fd8ebb802"></a>
## SRC-V14C2-b06fd8ebb802 — v14c2/LION_ABSTRACTION_COMPILER_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-b06fd8ebb802
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_ABSTRACTION_COMPILER_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=b7e753d414a62d7bddb472d99b3878ee453073a2ec6c44c13c180278248fa119
SOURCE_BYTES=1478

LION_RECORD_BEGIN: SRC-V14C2-b06fd8ebb802
LION_RECORD_META: {"anchor":"src-v14c2-b06fd8ebb802","archive_id":"v14c2","authority_effect":"NONE","bytes":1478,"carrier":"15_LION_ABSTRACTION_MATERIALIZERS.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_ABSTRACTION_COMPILER_v1_4_candidate.source.md","sha256":"b7e753d414a62d7bddb472d99b3878ee453073a2ec6c44c13c180278248fa119","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-b06fd8ebb802","virtual_path":"v14c2/LION_ABSTRACTION_COMPILER_v1_4_candidate.source.md"}
````markdown
# LION Abstraction Compiler v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=PARTIAL_RESEARCH_TARGET
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=representation selection and governed materialization
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

The compiler is still not a single canonical subsystem. Its implemented substrate now includes Gap/CapabilityNeed, Bean/Composition/Mosaic, deterministic ActionSpec/CanonicalActionIR and candidate/evidence construction. This materially advances the `ACTION_IR` representation class from detached design to AS-IS.

Current/partial representations: source-code candidates, policy/test/evidence artifacts, simulations, canonical typed Action IR. Target/unsupported effect representations remain machine-control, robot task execution, PLC and CAD/CAM.

Every materializable representation requires typed input, deterministic materialization boundary, validation, independent verification, explicit activation authority, effect provider, observer and reconciler. A model alone is not a Materializer.

````
LION_RECORD_END: SRC-V14C2-b06fd8ebb802

<a id="src-v14c2-c8c3626bb145"></a>
## SRC-V14C2-c8c3626bb145 — v14c2/LION_MATERIALIZER_REGISTRY_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-c8c3626bb145
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_MATERIALIZER_REGISTRY_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=d88c11b73f1377bb267e48a7be59888102eaab4e180375c19eedcf9d5f53529e
SOURCE_BYTES=1247

LION_RECORD_BEGIN: SRC-V14C2-c8c3626bb145
LION_RECORD_META: {"anchor":"src-v14c2-c8c3626bb145","archive_id":"v14c2","authority_effect":"NONE","bytes":1247,"carrier":"15_LION_ABSTRACTION_MATERIALIZERS.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_MATERIALIZER_REGISTRY_v1_4_candidate.source.json","sha256":"d88c11b73f1377bb267e48a7be59888102eaab4e180375c19eedcf9d5f53529e","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-c8c3626bb145","virtual_path":"v14c2/LION_MATERIALIZER_REGISTRY_v1_4_candidate.source.json"}
````json
{
  "schema_version": "lion.materializer-registry/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "status": "TARGET_NOT_IMPLEMENTED",
  "authority_effect": "NONE",
  "source_recovery": "v1.3 registry present in RAG-40; semantics updated against current state",
  "representations": [
    {
      "representation": "SOURCE_CODE_CANDIDATE",
      "state": "PARTIAL",
      "canonical_registry_entry": false
    },
    {
      "representation": "POLICY_CANDIDATE",
      "state": "PARTIAL",
      "canonical_registry_entry": false
    },
    {
      "representation": "TEST_OR_EVIDENCE_ARTIFACT",
      "state": "PARTIAL",
      "canonical_registry_entry": false
    },
    {
      "representation": "EXPERIMENT_PROTOCOL",
      "state": "PARTIAL",
      "canonical_registry_entry": false
    },
    {
      "representation": "ACTION_SPEC_IR",
      "state": "AS_IS_REPRESENTATION",
      "canonical_registry_entry": false,
      "ref": "cyber_lion/contracts/action_ir.py"
    },
    {
      "representation": "ROBOT_TASK_OR_MACHINE_CONTROL",
      "state": "TARGET",
      "canonical_registry_entry": false
    }
  ],
  "note": "Existing mechanisms are not silently promoted into a domain-independent canonical MaterializerRegistry."
}

````
LION_RECORD_END: SRC-V14C2-c8c3626bb145
