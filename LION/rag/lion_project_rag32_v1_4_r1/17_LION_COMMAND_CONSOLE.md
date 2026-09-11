# LION — LCMS, adaptery i LocalConsole

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=17_COMMAND_CONSOLE
SEARCH_TERMS=LCMS console adapters shell process.exec parser canonicalization
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-703d2692b309"></a>
## SRC-V13-703d2692b309 — v13/LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-703d2692b309
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=86c4f338f39f08b16fb1d0b8fd8ef33db2b565b50350158c07f9a23dfd4aa0f0
SOURCE_BYTES=1187

LION_RECORD_BEGIN: SRC-V13-703d2692b309
LION_RECORD_META: {"anchor":"src-v13-703d2692b309","archive_id":"v13","authority_effect":"NONE","bytes":1187,"carrier":"17_LION_COMMAND_CONSOLE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json","sha256":"86c4f338f39f08b16fb1d0b8fd8ef33db2b565b50350158c07f9a23dfd4aa0f0","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-703d2692b309","virtual_path":"v13/LION_COMMAND_ADAPTER_REGISTRY_v1_3_candidate.source.json"}
````json
{
  "entries": [
    {
      "constraints": [
        "shell=false",
        "absolute executable",
        "argv array",
        "pinned cwd",
        "environment inheritance=false",
        "network=DENY",
        "stdin=NONE",
        "tty=false",
        "bounded resources",
        "independent observation"
      ],
      "risk_class": "READ_ONLY_LAB",
      "state": "TARGET_FIRST_ADAPTER",
      "type": "process.exec"
    },
    {
      "state": "TARGET_AFTER_PROCESS_EXEC",
      "type": "filesystem.read"
    },
    {
      "state": "TARGET_TEST_ONLY_ISOLATED_ROOT",
      "type": "filesystem.write"
    },
    {
      "state": "PARTIAL_EXISTING",
      "type": "repository.observe"
    },
    {
      "state": "PARTIAL_EXISTING",
      "type": "repository.prepare_candidate"
    },
    {
      "state": "PARTIAL_EXISTING_CAPABILITY_REDUCED",
      "type": "repository.attach_exact"
    },
    {
      "state": "DEFER_HIGH_RISK",
      "type": "service.control"
    },
    {
      "state": "RESEARCH_TARGET_SIMULATION_ONLY",
      "type": "robot.task"
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "schema_version": "lion.command-adapter-registry/v1.3-candidate"
}

````
LION_RECORD_END: SRC-V13-703d2692b309

<a id="src-v13-974119698905"></a>
## SRC-V13-974119698905 — v13/LION_COMMAND_MODELING_SYNTAX_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-974119698905
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_COMMAND_MODELING_SYNTAX_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=a40165ccc280ed789b2249edb5fece4679cd0372be9452cda161cae9d393ac8d
SOURCE_BYTES=924

LION_RECORD_BEGIN: SRC-V13-974119698905
LION_RECORD_META: {"anchor":"src-v13-974119698905","archive_id":"v13","authority_effect":"NONE","bytes":924,"carrier":"17_LION_COMMAND_CONSOLE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_COMMAND_MODELING_SYNTAX_v1_3_candidate.source.md","sha256":"a40165ccc280ed789b2249edb5fece4679cd0372be9452cda161cae9d393ac8d","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-974119698905","virtual_path":"v13/LION_COMMAND_MODELING_SYNTAX_v1_3_candidate.source.md"}
````markdown
# LION Command Modeling Syntax v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=DESIGN_CANDIDATE
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=LCMS surface syntax and compilation
DEPENDENCIES=Action IR schema
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

LCMS is human/model-readable syntax for audit, review and reproduction. It is never executed directly. It parses and normalizes into one canonical Action IR.

Unknown fields, duplicate fields, aliases, implicit effect-changing defaults, noncanonical Unicode, ambiguous units, path traversal and unrecognized enums fail closed.

Pipelines are explicit DAGs of typed process nodes and data edges. They are never encoded as a raw shell string.

````
LION_RECORD_END: SRC-V13-974119698905

<a id="src-v13-4fc7d8c7772b"></a>
## SRC-V13-4fc7d8c7772b — v13/LION_LOCAL_CONSOLE_PROTOCOL_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-4fc7d8c7772b
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_LOCAL_CONSOLE_PROTOCOL_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=f213ac23ce3dfd98bc8df6378a6153093f5590d645c61694a5a76b7b6c10cc3f
SOURCE_BYTES=1058

LION_RECORD_BEGIN: SRC-V13-4fc7d8c7772b
LION_RECORD_META: {"anchor":"src-v13-4fc7d8c7772b","archive_id":"v13","authority_effect":"NONE","bytes":1058,"carrier":"17_LION_COMMAND_CONSOLE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_LOCAL_CONSOLE_PROTOCOL_v1_3_candidate.source.md","sha256":"f213ac23ce3dfd98bc8df6378a6153093f5590d645c61694a5a76b7b6c10cc3f","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-4fc7d8c7772b","virtual_path":"v13/LION_LOCAL_CONSOLE_PROTOCOL_v1_3_candidate.source.md"}
````markdown
# LION Local Console Protocol v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=TARGET_PROTOCOL
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=capability-reduced local console
DEPENDENCIES=LCMS + Action IR + PEP
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

```text
human/model
→ ActionIntent
→ LCMS candidate
→ parser/normalizer
→ canonical Action IR
→ static effect projection
→ ActionProposal
→ PDP/permit/currentness/budget
→ PEP
→ exact adapter
→ independent observation
→ reconciliation
```

The first adapter is read-only `process.exec` on LAB-DEBIAN with `shell=false`, absolute executable, argv array, pinned workspace, non-inherited environment, no stdin/TTY/network, resource bounds and process/filesystem/network post-observation.

This package contains no executor and performs no command effect.

````
LION_RECORD_END: SRC-V13-4fc7d8c7772b

<a id="src-v14c2-fc0e513c9bc0"></a>
## SRC-V14C2-fc0e513c9bc0 — v14c2/LION_COMMAND_ADAPTER_REGISTRY_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-fc0e513c9bc0
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_COMMAND_ADAPTER_REGISTRY_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=327e784deb63f3c83a3cd86649e1925df411b81637c1308c3c39767254d62e23
SOURCE_BYTES=1383

LION_RECORD_BEGIN: SRC-V14C2-fc0e513c9bc0
LION_RECORD_META: {"anchor":"src-v14c2-fc0e513c9bc0","archive_id":"v14c2","authority_effect":"NONE","bytes":1383,"carrier":"17_LION_COMMAND_CONSOLE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_COMMAND_ADAPTER_REGISTRY_v1_4_candidate.source.json","sha256":"327e784deb63f3c83a3cd86649e1925df411b81637c1308c3c39767254d62e23","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-fc0e513c9bc0","virtual_path":"v14c2/LION_COMMAND_ADAPTER_REGISTRY_v1_4_candidate.source.json"}
````json
{
  "schema_version": "lion.command-adapter-registry/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "authority_effect": "NONE",
  "source_recovery": "v1.3 exact bytes omitted from RAG-40; successor reconstructed from v1.3 report/roadmap and current Git state",
  "adapters": [
    {
      "id": "canonical-action-ir",
      "state": "AS_IS",
      "representation": "ActionSpec/CanonicalActionIR",
      "effect": "NONE",
      "ref": "cyber_lion/contracts/action_ir.py"
    },
    {
      "id": "actionproposal-pdp-handoff",
      "state": "AS_IS",
      "representation": "ActionProposal->PDPResult",
      "effect": "NONE",
      "ref": "cyber_lion/contracts/action_proposal_pdp_handoff.py"
    },
    {
      "id": "lcms",
      "state": "STALE_BASE_CANDIDATE",
      "effect": "NONE",
      "ref": "PR#257",
      "requires": "fresh rebase/revalidation"
    },
    {
      "id": "readonly-process-exec",
      "state": "STALE_BASE_CANDIDATE",
      "effect": "READ_ONLY_TEST_ONLY_IF_REBUILT_AND_ADMITTED",
      "ref": "PR#258",
      "requires": "fresh canonical PDP/runtime-admission binding first"
    },
    {
      "id": "raw-shell",
      "state": "FORBIDDEN_AS_TARGET_INTERFACE",
      "effect": "UNBOUNDED",
      "ref": null
    },
    {
      "id": "robot-task-adapter",
      "state": "TARGET",
      "effect": "PHYSICAL",
      "ref": null
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-fc0e513c9bc0

<a id="src-v14c2-9c5b342b0112"></a>
## SRC-V14C2-9c5b342b0112 — v14c2/LION_COMMAND_MODELING_SYNTAX_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-9c5b342b0112
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_COMMAND_MODELING_SYNTAX_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=daa9864b7d1505a38aeee2254f5d132cd5b60ded9de97123f290db14b140682d
SOURCE_BYTES=1320

LION_RECORD_BEGIN: SRC-V14C2-9c5b342b0112
LION_RECORD_META: {"anchor":"src-v14c2-9c5b342b0112","archive_id":"v14c2","authority_effect":"NONE","bytes":1320,"carrier":"17_LION_COMMAND_CONSOLE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_COMMAND_MODELING_SYNTAX_v1_4_candidate.source.md","sha256":"daa9864b7d1505a38aeee2254f5d132cd5b60ded9de97123f290db14b140682d","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-9c5b342b0112","virtual_path":"v14c2/LION_COMMAND_MODELING_SYNTAX_v1_4_candidate.source.md"}
````markdown
# LION Command Modeling Syntax v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=DESIGN_CANDIDATE_STALE_LINEAGE
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=LCMS surface syntax and canonical compilation
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

LCMS remains non-integrated. Historical PR #257 proves a candidate design lineage but is stale-base against current master. A v1.4 LCMS must compile one semantic command into one canonical ActionSpec/CanonicalActionIR and must not duplicate PDP, runtime admission or execution semantics.

Unknown fields, aliases, duplicate fields, ambiguous units, noncanonical Unicode, implicit effect-changing defaults, path traversal and raw shell strings fail closed. Pipelines are explicit typed DAGs, never shell command strings.

Rebuild LCMS only **after** the canonical PDPResult→RequestedRuntimeEffect/runtime identity boundary is closed.

````
LION_RECORD_END: SRC-V14C2-9c5b342b0112

<a id="src-v14c2-d9cb884754c5"></a>
## SRC-V14C2-d9cb884754c5 — v14c2/LION_LOCAL_CONSOLE_PROTOCOL_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-d9cb884754c5
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_LOCAL_CONSOLE_PROTOCOL_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=a2e58784c72790deb0f0d5d7d40bfbf0404a05609f48b2cbbeb481827ce2718d
SOURCE_BYTES=1284

LION_RECORD_BEGIN: SRC-V14C2-d9cb884754c5
LION_RECORD_META: {"anchor":"src-v14c2-d9cb884754c5","archive_id":"v14c2","authority_effect":"NONE","bytes":1284,"carrier":"17_LION_COMMAND_CONSOLE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_LOCAL_CONSOLE_PROTOCOL_v1_4_candidate.source.md","sha256":"a2e58784c72790deb0f0d5d7d40bfbf0404a05609f48b2cbbeb481827ce2718d","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-d9cb884754c5","virtual_path":"v14c2/LION_LOCAL_CONSOLE_PROTOCOL_v1_4_candidate.source.md"}
````markdown
# LION Local Console Protocol v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=TARGET_PROTOCOL
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=capability-reduced local console
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

Target flow:

```text
human/model
→ ActionIntent
→ LCMS
→ Canonical ActionSpec / IR
→ ActionProposal
→ canonical PDP
→ exact runtime-effect/runtime-identity binding
→ RuntimeAdmissionEngine
→ capability-reduced PEP/adapter
→ independent observation
→ reconciliation
```

The historical read-only `process.exec` candidate is stale-base and not a live console. Any successor must use `shell=false`, an exact executable digest, argv array, pinned workspace, non-inherited environment, network deny by default, resource limits, currentness at effect time and post-observation. This package contains no executor.

````
LION_RECORD_END: SRC-V14C2-d9cb884754c5
