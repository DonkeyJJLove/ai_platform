# LION — Sprzeczności, falsyfikacje i supersession

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=25_CONTRADICTIONS_HISTORY
SEARCH_TERMS=contradiction falsification supersession history unknown evidence conflict
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-f4452e208fd6"></a>
## SRC-V13-f4452e208fd6 — v13/CONTRADICTION_REGISTER.json

SOURCE_ID=SRC-V13-f4452e208fd6
SOURCE_ARCHIVE=v13
SOURCE_PATH=CONTRADICTION_REGISTER.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=36bfaf6a9e9edff0b07738924c48fea2e656391425ad1070b26dd6e7f96b24e5
SOURCE_BYTES=3903

LION_RECORD_BEGIN: SRC-V13-f4452e208fd6
LION_RECORD_META: {"anchor":"src-v13-f4452e208fd6","archive_id":"v13","authority_effect":"NONE","bytes":3903,"carrier":"25_LION_CONTRADICTIONS_HISTORY.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"CONTRADICTION_REGISTER.json","sha256":"36bfaf6a9e9edff0b07738924c48fea2e656391425ad1070b26dd6e7f96b24e5","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-f4452e208fd6","virtual_path":"v13/CONTRADICTION_REGISTER.json"}
````json
{
  "entries": [
    {
      "claim_a": "BeanSpec, BeanCandidate, BeanInstance, CompositionEngine and dynamic Mosaic are TARGET_ONLY.",
      "claim_b": "Those contracts/implementations exist on current master and exact-master Core CI passed.",
      "id": "CONFLICT-001",
      "precedence_result": "LIVE_CODE_AND_CURRENT_CI_WINS",
      "resolution": "Regenerate gap projection and add contradiction/currentness validation.",
      "sources": [
        "cyber_lion/architecture_projection/gap.py",
        "live master code/tests"
      ]
    },
    {
      "claim_a": "ai_platform maturity is SPECIFICATION in central registry.",
      "claim_b": "Current manifest/code expose an engineering control plane, Agent Foundry, authority, fleet and Bean primitives.",
      "id": "CONFLICT-002",
      "precedence_result": "LIVE_MANIFEST_AND_CODE_WINS",
      "resolution": "Keep registry identity stable; derive maturity from current evidence.",
      "sources": [
        "cyber_lion/registry/repositories.json",
        "cyber-lion.repository.json/current master"
      ]
    },
    {
      "claim_a": "Implementation map says CURRENT_AT_BASELINE.",
      "claim_b": "Its embedded baseline is c67ed65... from 2026-08-24; current master is 2be0b3... with material descendants.",
      "id": "CONFLICT-003",
      "precedence_result": "EXACT_GIT_STATE_WINS",
      "resolution": "Automatically degrade CURRENT to STALE on material descendants.",
      "sources": [
        "LION/architecture/implementation-map.json",
        "live master"
      ]
    },
    {
      "claim_a": "Historical Bean Factory research says canonical BeanSpec is missing.",
      "claim_b": "Canonical BeanSpec and related primitives are integrated on current master.",
      "id": "CONFLICT-004",
      "precedence_result": "LIVE_CODE_WINS_HISTORY_PRESERVED",
      "resolution": "Supersede component-absence claim; preserve generativity methodology.",
      "sources": [
        "historical Bean Factory research",
        "current master"
      ]
    },
    {
      "claim_a": "Three logical laboratory nodes can be read as independent physical hosts.",
      "claim_b": "All three WSL environments expose one Windows/CPU/network/mount domain.",
      "id": "CONFLICT-005",
      "precedence_result": "LIVE_PHYSICAL_OBSERVATION_WINS",
      "resolution": "Keep logical roles; record one physical failure domain.",
      "sources": [
        "logical host inventory",
        "live SentinelX census"
      ]
    },
    {
      "claim_a": "Host-authority separation architecture is integrated.",
      "claim_b": "MOON runner is still in lion-control-plane with NoNewPrivileges=0 and Seccomp=0.",
      "id": "CONFLICT-006",
      "precedence_result": "BOTH_TRUE_IN_DIFFERENT_PLANES",
      "resolution": "Code=integrated target transition; live host=not deployed/blocking.",
      "sources": [
        "integrated host-separation contracts",
        "live MOON census"
      ]
    },
    {
      "claim_a": "LAB-UBUNTU tags include Ollama/model-server.",
      "claim_b": "No Ollama binary, service, process or local model runtime was observed.",
      "id": "CONFLICT-007",
      "precedence_result": "LIVE_RUNTIME_OBSERVATION_WINS",
      "resolution": "Mark tags stale; do not infer readiness.",
      "sources": [
        "SentinelX metadata",
        "live LAB-UBUNTU census"
      ]
    },
    {
      "claim_a": "Historical refresh treated PR #224 as current frontier.",
      "claim_b": "PR #224 is closed/unmerged; later controlled ports succeeded selectively.",
      "id": "CONFLICT-008",
      "precedence_result": "CURRENT_GIT_STATE_WINS",
      "resolution": "Classify #224 historical/superseded.",
      "sources": [
        "historical refresh",
        "current PR metadata/PR#242"
      ]
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "schema_version": "lion.contradiction-register/v1.3-candidate"
}

````
LION_RECORD_END: SRC-V13-f4452e208fd6

<a id="src-v13-970ec1649842"></a>
## SRC-V13-970ec1649842 — v13/LION_FALSIFICATION_REGISTER_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-970ec1649842
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_FALSIFICATION_REGISTER_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=2e750ef18c13c234f323e0e5ed33712399a84e14bf0c9591f2e5f97648e333c6
SOURCE_BYTES=2434

LION_RECORD_BEGIN: SRC-V13-970ec1649842
LION_RECORD_META: {"anchor":"src-v13-970ec1649842","archive_id":"v13","authority_effect":"NONE","bytes":2434,"carrier":"25_LION_CONTRADICTIONS_HISTORY.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_FALSIFICATION_REGISTER_v1_3_candidate.source.json","sha256":"2e750ef18c13c234f323e0e5ed33712399a84e14bf0c9591f2e5f97648e333c6","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-970ec1649842","virtual_path":"v13/LION_FALSIFICATION_REGISTER_v1_3_candidate.source.json"}
````json
{
  "entries": [
    {
      "claim": "All historical v1.1 falsifications remain historical facts.",
      "id": "FAL-HISTORY-V11",
      "status": "PRESERVED"
    },
    {
      "claim": "Textual tool prohibition is complete mediation.",
      "id": "FAL-V12-TEXT-ALLOWLIST",
      "repair": "Capability-reduced PEP and split preparation/attachment.",
      "status": "FALSIFIED_PRESERVED"
    },
    {
      "claim": "Canonical BeanSpec, BeanCandidate and CompositionEngine are missing.",
      "id": "FAL-V13-BEAN-ABSENCE",
      "observation": "Integrated current-master contracts, implementations and tests exist.",
      "status": "FALSIFIED"
    },
    {
      "claim": "Three WSL nodes prove three independent physical domains.",
      "id": "FAL-V13-THREE-PHYSICAL-HOSTS",
      "observation": "They share one observed Windows hardware/network/mount domain.",
      "status": "FALSIFIED"
    },
    {
      "claim": "Ollama/model-server tags prove a local model runtime.",
      "id": "FAL-V13-LOCAL-MODEL-READY",
      "observation": "No runtime/service/process/model observed.",
      "status": "FALSIFIED"
    },
    {
      "claim": "Integrated host-separation contracts prove live deployment.",
      "id": "FAL-V13-HOST-SEPARATION-DEPLOYED",
      "observation": "MOON runner/control-plane group overlap remains.",
      "status": "FALSIFIED"
    },
    {
      "claim": "The Bean Factory solves unseen problems by generating missing capability end-to-end.",
      "id": "FAL-V13-FACTORY-GENERATIVITY",
      "status": "NOT_PROVEN"
    },
    {
      "claim": "A generated Factory generates another bounded autonomy.",
      "id": "FAL-V13-FACTORY-OF-FACTORIES",
      "status": "NOT_ATTEMPTED"
    },
    {
      "claim": "Every reachable consequential surface is completely mediated.",
      "id": "FAL-V13-GLOBAL-MEDIATION",
      "status": "UNKNOWN"
    },
    {
      "claim": "100 independent production executors are proven live.",
      "id": "FAL-V13-F100",
      "status": "NOT_ATTEMPTED"
    },
    {
      "claim": "Production-grade OS sandbox enforcement is proven.",
      "id": "FAL-V13-SANDBOX",
      "status": "NOT_PROVEN"
    },
    {
      "claim": "PR #248/#249 properties are current master properties.",
      "id": "FAL-V13-R2E4-INTEGRATED",
      "status": "NOT_INTEGRATED"
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "schema_version": "lion.falsification-register/v1.3-candidate"
}

````
LION_RECORD_END: SRC-V13-970ec1649842

<a id="src-v13-65ec2ca241c1"></a>
## SRC-V13-65ec2ca241c1 — v13/LION_SUPERSESSION_REGISTER_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-65ec2ca241c1
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_SUPERSESSION_REGISTER_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988
SOURCE_BYTES=1198

LION_RECORD_BEGIN: SRC-V13-65ec2ca241c1
LION_RECORD_META: {"anchor":"src-v13-65ec2ca241c1","archive_id":"v13","authority_effect":"NONE","bytes":1198,"carrier":"25_LION_CONTRADICTIONS_HISTORY.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_SUPERSESSION_REGISTER_v1_3_candidate.source.json","sha256":"b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-65ec2ca241c1","virtual_path":"v13/LION_SUPERSESSION_REGISTER_v1_3_candidate.source.json"}
````json
{
  "effective": false,
  "entries": [
    {
      "effective": false,
      "history_preserved": true,
      "id": "SUP-CAND-001",
      "new": "this 1.3.0-intermediate-candidate.1 package",
      "old": "LION v1.2 project source pack",
      "relation": "PROPOSE_SUPERSESSION_AFTER_INTEGRATION_AND_CURRENTNESS_VALIDATION"
    },
    {
      "effective": true,
      "history_preserved": true,
      "id": "SUP-CAND-002",
      "new": "integrated Bean Factory primitives",
      "old": "historical claim: Bean primitives missing",
      "relation": "SUPERSEDE_COMPONENT_ABSENCE_CLAIM"
    },
    {
      "effective": false,
      "history_preserved": true,
      "id": "SUP-CAND-003",
      "new": "AS-IS/CANDIDATE/TARGET",
      "old": "two-state AS-IS/TARGET projection",
      "relation": "PROPOSE_SEMANTIC_EXPANSION"
    },
    {
      "effective": true,
      "history_preserved": true,
      "id": "SUP-CAND-004",
      "new": "#224 historical/superseded; later controlled ports",
      "old": "PR #224 as current frontier",
      "relation": "SUPERSEDE_CURRENTNESS_ONLY"
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "schema_version": "lion.supersession-register/v1.3-candidate"
}

````
LION_RECORD_END: SRC-V13-65ec2ca241c1

<a id="src-v13-2e4156de8bf0"></a>
## SRC-V13-2e4156de8bf0 — v13/SUPERSESSION_REGISTER.json

SOURCE_ID=SRC-V13-2e4156de8bf0
SOURCE_ARCHIVE=v13
SOURCE_PATH=SUPERSESSION_REGISTER.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988
SOURCE_BYTES=1198

LION_RECORD_BEGIN: SRC-V13-2e4156de8bf0
LION_RECORD_META: {"anchor":"src-v13-2e4156de8bf0","archive_id":"v13","authority_effect":"NONE","bytes":1198,"carrier":"25_LION_CONTRADICTIONS_HISTORY.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"SUPERSESSION_REGISTER.json","sha256":"b6f29fc39f996945d0cfd180d6e395219da65ca3061e126565124602724c0988","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-2e4156de8bf0","virtual_path":"v13/SUPERSESSION_REGISTER.json"}
````json
{
  "effective": false,
  "entries": [
    {
      "effective": false,
      "history_preserved": true,
      "id": "SUP-CAND-001",
      "new": "this 1.3.0-intermediate-candidate.1 package",
      "old": "LION v1.2 project source pack",
      "relation": "PROPOSE_SUPERSESSION_AFTER_INTEGRATION_AND_CURRENTNESS_VALIDATION"
    },
    {
      "effective": true,
      "history_preserved": true,
      "id": "SUP-CAND-002",
      "new": "integrated Bean Factory primitives",
      "old": "historical claim: Bean primitives missing",
      "relation": "SUPERSEDE_COMPONENT_ABSENCE_CLAIM"
    },
    {
      "effective": false,
      "history_preserved": true,
      "id": "SUP-CAND-003",
      "new": "AS-IS/CANDIDATE/TARGET",
      "old": "two-state AS-IS/TARGET projection",
      "relation": "PROPOSE_SEMANTIC_EXPANSION"
    },
    {
      "effective": true,
      "history_preserved": true,
      "id": "SUP-CAND-004",
      "new": "#224 historical/superseded; later controlled ports",
      "old": "PR #224 as current frontier",
      "relation": "SUPERSEDE_CURRENTNESS_ONLY"
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "schema_version": "lion.supersession-register/v1.3-candidate"
}

````
LION_RECORD_END: SRC-V13-2e4156de8bf0

<a id="src-v14c2-f4452e208fd6"></a>
## SRC-V14C2-f4452e208fd6 — v14c2/CONTRADICTION_REGISTER.json

SOURCE_ID=SRC-V14C2-f4452e208fd6
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=CONTRADICTION_REGISTER.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=396529ded9026aac33c149a9ad0f905dccef086f92b0c46d2654e84c4c3184ba
SOURCE_BYTES=4274

LION_RECORD_BEGIN: SRC-V14C2-f4452e208fd6
LION_RECORD_META: {"anchor":"src-v14c2-f4452e208fd6","archive_id":"v14c2","authority_effect":"NONE","bytes":4274,"carrier":"25_LION_CONTRADICTIONS_HISTORY.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"CONTRADICTION_REGISTER.json","sha256":"396529ded9026aac33c149a9ad0f905dccef086f92b0c46d2654e84c4c3184ba","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-f4452e208fd6","virtual_path":"v14c2/CONTRADICTION_REGISTER.json"}
````json
{
  "schema_version": "lion.contradiction-register/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "entries": [
    {
      "id": "CONFLICT-001",
      "claim_a": "R2E4 and Fleet Aggregate Effect Budget are non-integrated candidates.",
      "claim_b": "Current master truth/code place both in AS-IS/integrated state.",
      "precedence_result": "LIVE_CODE_AND_CURRENT_GIT_WINS",
      "resolution": "v1.4 promotes them in architecture; historical PR state preserved."
    },
    {
      "id": "CONFLICT-002",
      "claim_a": "ActionSpec/LAIR are target or detached schema only.",
      "claim_b": "ActionSpec and CanonicalActionIR/LAIR are integrated on current master.",
      "precedence_result": "LIVE_CODE_AND_CURRENT_CI_WINS",
      "resolution": "v1.4 AS-IS includes typed Action plane."
    },
    {
      "id": "CONFLICT-003",
      "claim_a": "ActionProposal to PDP is the first unfinished action boundary.",
      "claim_b": "PR #294 is merged; canonical non-effectful PDP handoff is integrated.",
      "precedence_result": "EXACT_GIT_WINS",
      "resolution": "move frontier to PDP ALLOW -> RequestedRuntimeEffect/runtime identity -> RuntimeAdmissionEngine."
    },
    {
      "id": "CONFLICT-004",
      "claim_a": "B0 terminal two-unseen-problem generativity remains not attempted/not proven.",
      "claim_b": "Current master contains an integrated terminal protocol test where two dissimilar unseen families PASS, one counterexample FALSIFIES, no problem-specific workflow switch is present and no effect surface is detected.",
      "precedence_result": "LIVE_CODE_AND_CURRENT_TEST_WINS",
      "resolution": "classify B0 bounded terminal protocol PASS; keep general/domain-independent Factory generativity NOT_PROVEN."
    },
    {
      "id": "CONFLICT-005",
      "claim_a": "MOON hosts the self-hosted runner and runner is in lion-control-plane.",
      "claim_b": "Current read-only census sees no runner on MOON and no supplementary control-plane group; runner is observed on LION-AUTH-LAB.",
      "precedence_result": "LIVE_RUNTIME_OBSERVATION_WINS",
      "resolution": "old BLOCK-AUTH-001 resolved in old form; do not infer production authority."
    },
    {
      "id": "CONFLICT-006",
      "claim_a": "Four logical nodes imply independent host failure domains.",
      "claim_b": "All observed WSL nodes remain under WINDOWS-MOON; MOON and LION-AUTH-LAB expose the same C: via 9p.",
      "precedence_result": "LIVE_PHYSICAL_OBSERVATION_WINS",
      "resolution": "logical separation YES; physical independence FAIL."
    },
    {
      "id": "CONFLICT-007",
      "claim_a": "LION/status.json epistemic_state=CURRENT.",
      "claim_b": "It is generated 2026-08-24 and still reports E003/M128 despite material descendants.",
      "precedence_result": "EXACT_GIT_AND_CURRENTNESS_RULE_WINS",
      "resolution": "classify stale unless regenerated from a valid currentness basis."
    },
    {
      "id": "CONFLICT-008",
      "claim_a": "action_spec.schema.json metadata says CONTRACT_ONLY/TARGET_ONLY for integrated ActionSpec fields.",
      "claim_b": "Canonical ActionSpec/LAIR are integrated and exercised by current code/tests.",
      "precedence_result": "LIVE_CODE_AND_CANONICAL_TRUTH_WINS",
      "resolution": "schema semantic contract remains valid; extension metadata is stale and must be regenerated separately."
    },
    {
      "id": "CONFLICT-009",
      "claim_a": "RAG-40 is the whole v1.3 package.",
      "claim_b": "PACKAGE_MANIFEST lists 58 payloads and SOURCE_DIGESTS references 60; with SOURCE_DIGESTS total topology is 61 while ZIP contains 40.",
      "precedence_result": "PACKAGE_SELF_DESCRIPTION_WINS",
      "resolution": "v1.4 audits all 61 lineage slots; omitted source bytes are marked recovered/reconstructed, not silently ignored."
    },
    {
      "id": "CONFLICT-010",
      "claim_a": "LCMS/read-only process candidate lineage can be treated as current.",
      "claim_b": "Open historical candidates are stale-base relative to current master and canonical gap projects LCMS/LocalConsole as target.",
      "precedence_result": "CURRENT_MASTER_AND_CURRENTNESS_WINS",
      "resolution": "preserve as candidate lineage; require fresh rebase/revalidation before reuse."
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-f4452e208fd6

<a id="src-v14c2-b13117e8c6c2"></a>
## SRC-V14C2-b13117e8c6c2 — v14c2/LION_FALSIFICATION_REGISTER_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-b13117e8c6c2
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_FALSIFICATION_REGISTER_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=b0e241eb7a6cd3d1701148a454e87d3abef7dfff03518bcdc4278083514118cb
SOURCE_BYTES=2370

LION_RECORD_BEGIN: SRC-V14C2-b13117e8c6c2
LION_RECORD_META: {"anchor":"src-v14c2-b13117e8c6c2","archive_id":"v14c2","authority_effect":"NONE","bytes":2370,"carrier":"25_LION_CONTRADICTIONS_HISTORY.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_FALSIFICATION_REGISTER_v1_4_candidate.source.json","sha256":"b0e241eb7a6cd3d1701148a454e87d3abef7dfff03518bcdc4278083514118cb","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-b13117e8c6c2","virtual_path":"v14c2/LION_FALSIFICATION_REGISTER_v1_4_candidate.source.json"}
````json
{
  "schema_version": "lion.falsification-register/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "entries": [
    {
      "id": "FAL-V11-HISTORY",
      "claim": "All historical v1.1 falsifications remain facts.",
      "status": "PRESERVED"
    },
    {
      "id": "FAL-V12-TEXT-ALLOWLIST",
      "claim": "Textual tool prohibition is complete mediation.",
      "status": "FALSIFIED_PRESERVED"
    },
    {
      "id": "FAL-V13-R2E4-INTEGRATED",
      "claim": "R2E4/#248 and aggregate budget/#249 are not current master properties.",
      "status": "FALSIFIED_BY_LATER_INTEGRATION"
    },
    {
      "id": "FAL-V13-ACTIONSPEC-LAIR-ABSENT",
      "claim": "ActionSpec/LAIR are absent/target only.",
      "status": "FALSIFIED_BY_LATER_INTEGRATION"
    },
    {
      "id": "FAL-V13-PDP-HANDOFF-ABSENT",
      "claim": "ActionProposal→canonical PDP is unfinished.",
      "status": "FALSIFIED_BY_PR294_INTEGRATION"
    },
    {
      "id": "FAL-V13-B0-NOT_SHOWN",
      "claim": "Two distinct unseen problem families have not passed the bounded terminal candidate-only protocol.",
      "status": "FALSIFIED_BY_CURRENT_MASTER_TEST"
    },
    {
      "id": "FAL-V14-GENERAL-FACTORY-GENERATIVITY",
      "claim": "The bounded B0 result proves general domain-independent Factory generativity.",
      "status": "NOT_PROVEN"
    },
    {
      "id": "FAL-V13-HOST-SEPARATION-DEPLOYED",
      "claim": "Old MOON runner/control-plane overlap remains live.",
      "status": "FALSIFIED_BY_CURRENT_HOST_OBSERVATION"
    },
    {
      "id": "FAL-V14-PHYSICAL-INDEPENDENCE",
      "claim": "Four logical WSL nodes prove four independent physical domains.",
      "status": "FALSIFIED"
    },
    {
      "id": "FAL-V14-LOCAL-MODEL",
      "claim": "A local model runtime is deployed on observed lab hosts.",
      "status": "FALSIFIED_BY_CURRENT_HOST_CENSUS"
    },
    {
      "id": "FAL-V14-GLOBAL-MEDIATION",
      "claim": "Every reachable consequential surface is completely mediated.",
      "status": "UNKNOWN"
    },
    {
      "id": "FAL-V14-FACTORY-OF-FACTORIES",
      "claim": "A generated Factory generates and activates another bounded autonomy.",
      "status": "NOT_ATTEMPTED"
    },
    {
      "id": "FAL-V14-PRODUCTION",
      "claim": "Production-grade sandbox/authority/recovery are proven.",
      "status": "NOT_PROVEN"
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-b13117e8c6c2

<a id="src-v14c2-df018b5a59b0"></a>
## SRC-V14C2-df018b5a59b0 — v14c2/LION_SUPERSESSION_REGISTER_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-df018b5a59b0
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_SUPERSESSION_REGISTER_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=3e7c6bacaf17465156900f61eed6866d399f09b76fa7f471a4226aaa661423b2
SOURCE_BYTES=2033

LION_RECORD_BEGIN: SRC-V14C2-df018b5a59b0
LION_RECORD_META: {"anchor":"src-v14c2-df018b5a59b0","archive_id":"v14c2","authority_effect":"NONE","bytes":2033,"carrier":"25_LION_CONTRADICTIONS_HISTORY.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_SUPERSESSION_REGISTER_v1_4_candidate.source.json","sha256":"3e7c6bacaf17465156900f61eed6866d399f09b76fa7f471a4226aaa661423b2","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-df018b5a59b0","virtual_path":"v14c2/LION_SUPERSESSION_REGISTER_v1_4_candidate.source.json"}
````json
{
  "schema_version": "lion.supersession-register/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "entries": [
    {
      "id": "SUP-V14-001",
      "old": "v1.3 detached package analysis",
      "new": "v1.4 full detached package analysis",
      "relation": "SUPERSEDE_PACKAGE_ANALYSIS",
      "effective": true,
      "repository_effect": false,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-002",
      "old": "R2E4/effect-budget candidate-only claims",
      "new": "integrated AS-IS claims",
      "relation": "SUPERSEDE_CURRENTNESS",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-003",
      "old": "ActionSpec/LAIR absent/target-only claims",
      "new": "integrated typed action representation",
      "relation": "SUPERSEDE_CURRENTNESS",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-004",
      "old": "ActionProposal→PDP as next gap",
      "new": "PDPResult→RequestedRuntimeEffect/runtime identity as next gap",
      "relation": "SUPERSEDE_FRONTIER",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-005",
      "old": "B0 terminal two-family protocol not shown",
      "new": "bounded B0 terminal protocol PASS; general generativity remains unproven",
      "relation": "NARROW_AND_SUPERSEDE_CLAIM",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-006",
      "old": "MOON runner/control-plane overlap live blocker",
      "new": "old form resolved; runner rehomed; production isolation still not globally proven",
      "relation": "SUPERSEDE_RUNTIME_CURRENTNESS",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-007",
      "old": "RAG-40 treated as full source corpus",
      "new": "61-slot v1.3 source topology with 21 omissions identified",
      "relation": "CORRECT_SOURCE_TOPOLOGY",
      "effective": true,
      "history_preserved": true
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-df018b5a59b0

<a id="src-v14c2-2e4156de8bf0"></a>
## SRC-V14C2-2e4156de8bf0 — v14c2/SUPERSESSION_REGISTER.json

SOURCE_ID=SRC-V14C2-2e4156de8bf0
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=SUPERSESSION_REGISTER.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=1849534fb9c3a5ea5c70317bcee4286e3200443e88893517e65607a0bb2518ce
SOURCE_BYTES=2109

LION_RECORD_BEGIN: SRC-V14C2-2e4156de8bf0
LION_RECORD_META: {"anchor":"src-v14c2-2e4156de8bf0","archive_id":"v14c2","authority_effect":"NONE","bytes":2109,"carrier":"25_LION_CONTRADICTIONS_HISTORY.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"SUPERSESSION_REGISTER.json","sha256":"1849534fb9c3a5ea5c70317bcee4286e3200443e88893517e65607a0bb2518ce","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-2e4156de8bf0","virtual_path":"v14c2/SUPERSESSION_REGISTER.json"}
````json
{
  "schema_version": "lion.supersession-register/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "canonical_ref": "LION_SUPERSESSION_REGISTER_v1_4_candidate.source.json",
  "entries": [
    {
      "id": "SUP-V14-001",
      "old": "v1.3 detached package analysis",
      "new": "v1.4 full detached package analysis",
      "relation": "SUPERSEDE_PACKAGE_ANALYSIS",
      "effective": true,
      "repository_effect": false,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-002",
      "old": "R2E4/effect-budget candidate-only claims",
      "new": "integrated AS-IS claims",
      "relation": "SUPERSEDE_CURRENTNESS",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-003",
      "old": "ActionSpec/LAIR absent/target-only claims",
      "new": "integrated typed action representation",
      "relation": "SUPERSEDE_CURRENTNESS",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-004",
      "old": "ActionProposal→PDP as next gap",
      "new": "PDPResult→RequestedRuntimeEffect/runtime identity as next gap",
      "relation": "SUPERSEDE_FRONTIER",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-005",
      "old": "B0 terminal two-family protocol not shown",
      "new": "bounded B0 terminal protocol PASS; general generativity remains unproven",
      "relation": "NARROW_AND_SUPERSEDE_CLAIM",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-006",
      "old": "MOON runner/control-plane overlap live blocker",
      "new": "old form resolved; runner rehomed; production isolation still not globally proven",
      "relation": "SUPERSEDE_RUNTIME_CURRENTNESS",
      "effective": true,
      "history_preserved": true
    },
    {
      "id": "SUP-V14-007",
      "old": "RAG-40 treated as full source corpus",
      "new": "61-slot v1.3 source topology with 21 omissions identified",
      "relation": "CORRECT_SOURCE_TOPOLOGY",
      "effective": true,
      "history_preserved": true
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-2e4156de8bf0
