# LION — AS-IS, stan implementacji i odziedziczona projekcja kanoniczna

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=09_AS_IS_IMPLEMENTATION
SEARCH_TERMS=AS_IS implementation status canonical state integrated evidence currentness
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

Ostrzeżenie: wcześniejszy plik canonical-state v1.4 ma puste evidence_refs we wszystkich 31 rekordach. Zachowano go jako źródło analityczne, nie samodzielną bramkę dowodową. Patrz 04 i 03.

## Rekordy źródłowe

<a id="src-v13-1ed24f8d0aa4"></a>
## SRC-V13-1ed24f8d0aa4 — v13/LION_ARCHITECTURE_AS_IS_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-1ed24f8d0aa4
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_ARCHITECTURE_AS_IS_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=5497644ceff77d3085d6562b0ff588746a7c05dd1f13e96f75a67655ff956aba
SOURCE_BYTES=1513

LION_RECORD_BEGIN: SRC-V13-1ed24f8d0aa4
LION_RECORD_META: {"anchor":"src-v13-1ed24f8d0aa4","archive_id":"v13","authority_effect":"NONE","bytes":1513,"carrier":"09_LION_AS_IS_IMPLEMENTATION.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_ARCHITECTURE_AS_IS_v1_3_candidate.source.md","sha256":"5497644ceff77d3085d6562b0ff588746a7c05dd1f13e96f75a67655ff956aba","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-1ed24f8d0aa4","virtual_path":"v13/LION_ARCHITECTURE_AS_IS_v1_3_candidate.source.md"}
````markdown
# LION Architecture AS-IS v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=CANDIDATE_PROJECTION
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=integrated and live-observed architecture
DEPENDENCIES=exact master + host census
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

## Integrated software state

Current master contains Agent/Swarm control, `ActionProposal`/Gate/Receipt, authority and runtime evidence mechanisms, exact repository effect patterns, fleet baseline/pin observation, canonical Bean contracts, capability-need derivation, deterministic Bean composition, heterogeneous Mosaic lifecycle and a bridge to detached repository candidate construction.

## Live runtime state

LAB-DEBIAN operates a dedicated Cyber-Lion control-plane service and TEST_ONLY producer. MOON operates a self-hosted GitHub runner and maintenance service. All three logical hosts remain WSL nodes inside one observed Windows failure domain.

## Explicit non-claims

- The Bean Factory is not terminally generative by evidence.
- R2E4 and Fleet Aggregate Effect Budget are not integrated.
- Host authority separation is not deployed on MOON.
- Local model runtime is absent.
- LCMS/LAIR/local console are absent.
- Global complete mediation is unknown.
- Production and robotics readiness are false.

````
LION_RECORD_END: SRC-V13-1ed24f8d0aa4

<a id="src-v13-411b11205c40"></a>
## SRC-V13-411b11205c40 — v13/LION_IMPLEMENTATION_STATUS_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-411b11205c40
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_IMPLEMENTATION_STATUS_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=eac79a9922134665ce9e053949e51ce4b8c8a9fabe3b4638e0dd84877511eeb8
SOURCE_BYTES=5738

LION_RECORD_BEGIN: SRC-V13-411b11205c40
LION_RECORD_META: {"anchor":"src-v13-411b11205c40","archive_id":"v13","authority_effect":"NONE","bytes":5738,"carrier":"09_LION_AS_IS_IMPLEMENTATION.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_IMPLEMENTATION_STATUS_v1_3_candidate.source.json","sha256":"eac79a9922134665ce9e053949e51ce4b8c8a9fabe3b4638e0dd84877511eeb8","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-411b11205c40","virtual_path":"v13/LION_IMPLEMENTATION_STATUS_v1_3_candidate.source.json"}
````json
{
  "baseline": {
    "branch": "master",
    "currentness_rule": "STALE on any material descendant until projection regenerated and exact-head CI passes",
    "head": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
    "repository": "DonkeyJJLove/ai_platform",
    "state": "CURRENT_AT_CAPTURE",
    "tree": "3c9705f85301e73f268228f3c36f6ae82a641633"
  },
  "components": [
    {
      "authority_effect": "NONE",
      "id": "BeanSpec",
      "observed_paths": [
        "cyber_lion/contracts/bean.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "BeanInstance",
      "observed_paths": [
        "cyber_lion/contracts/bean.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "BeanCandidate",
      "observed_paths": [
        "cyber_lion/contracts/bean_candidate.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "CapabilityNeed",
      "observed_paths": [
        "cyber_lion/contracts/capability_need.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "CapabilityNeedResolver",
      "observed_paths": [
        "cyber_lion/enterprise/capability_need.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "CompositionContract",
      "observed_paths": [
        "cyber_lion/contracts/bean_composition.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "CompositionEngine",
      "observed_paths": [
        "cyber_lion/enterprise/bean_composition.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "MosaicCell",
      "observed_paths": [
        "cyber_lion/contracts/mosaic.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "HeterogeneousMosaicPlanner",
      "observed_paths": [
        "cyber_lion/enterprise/mosaic.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "BeanBuilderChainBinding",
      "observed_paths": [
        "cyber_lion/contracts/bean_builder_bridge.py"
      ],
      "state": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "authority_effect": "NONE",
      "id": "AutonomyBlueprint",
      "observed_paths": [],
      "state": "TARGET_NOT_FOUND"
    },
    {
      "authority_effect": "NONE",
      "id": "MaterializerRegistry",
      "observed_paths": [],
      "state": "TARGET_NOT_FOUND"
    },
    {
      "authority_effect": "NONE",
      "id": "ActionSpec",
      "observed_paths": [],
      "state": "TARGET_NOT_FOUND_AS_DISTINCT_CANONICAL_TYPE"
    },
    {
      "authority_effect": "NONE",
      "id": "LCMS",
      "observed_paths": [],
      "state": "TARGET_NOT_FOUND"
    },
    {
      "authority_effect": "NONE",
      "id": "LAIR",
      "observed_paths": [],
      "state": "TARGET_NOT_FOUND"
    },
    {
      "authority_effect": "NONE",
      "id": "LocalConsole",
      "observed_paths": [],
      "state": "TARGET_NOT_FOUND"
    },
    {
      "authority_effect": "NONE",
      "id": "ActionProposal",
      "observed_paths": [
        "cyber_lion/enterprise/control_plane.py"
      ],
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "id": "GateDecision",
      "observed_paths": [
        "cyber_lion/enterprise/control_plane.py"
      ],
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "id": "ExecutionReceipt",
      "observed_paths": [
        "cyber_lion/enterprise/control_plane.py"
      ],
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "id": "FleetRepositoryPins",
      "observed_paths": [
        "R2E1/R2E2/R2E3 lineage"
      ],
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "id": "R2E4EvidenceBinding",
      "observed_paths": [
        "PR#248"
      ],
      "state": "VERIFIED_CANDIDATE"
    },
    {
      "authority_effect": "RESTRICT_ONLY",
      "id": "FleetAggregateEffectBudget",
      "observed_paths": [
        "PR#249"
      ],
      "state": "VERIFIED_CANDIDATE"
    },
    {
      "authority_effect": "NOT_APPLICABLE",
      "id": "GlobalCompleteMediation",
      "observed_paths": [
        "multiple effect-specific closures"
      ],
      "state": "UNKNOWN"
    },
    {
      "authority_effect": "NONE",
      "id": "LocalOpenWeightModelRuntime",
      "observed_paths": [],
      "state": "TARGET"
    },
    {
      "authority_effect": "NONE",
      "id": "HybridModelRouter",
      "observed_paths": [],
      "state": "TARGET"
    },
    {
      "authority_effect": "NONE",
      "id": "CyberPhysicalRuntime",
      "observed_paths": [],
      "state": "TARGET"
    }
  ],
  "critical_conflicts": [
    "CONFLICT-001",
    "CONFLICT-002",
    "CONFLICT-003",
    "CONFLICT-004",
    "CONFLICT-005",
    "CONFLICT-006",
    "CONFLICT-007",
    "CONFLICT-008"
  ],
  "epistemic_states": [
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
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "preproduction_ready": false,
  "schema_version": "lion.implementation-status/v1.3-candidate",
  "version": "1.3.0-intermediate-candidate.1"
}

````
LION_RECORD_END: SRC-V13-411b11205c40

<a id="src-v14c2-51ba9d764204"></a>
## SRC-V14C2-51ba9d764204 — v14c2/LION_ARCHITECTURE_AS_IS_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-51ba9d764204
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_ARCHITECTURE_AS_IS_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=918c46edf4b81af9bd65700fe124d2d2b9228ce03effaf58f3ab4681e9a2a7ab
SOURCE_BYTES=2617

LION_RECORD_BEGIN: SRC-V14C2-51ba9d764204
LION_RECORD_META: {"anchor":"src-v14c2-51ba9d764204","archive_id":"v14c2","authority_effect":"NONE","bytes":2617,"carrier":"09_LION_AS_IS_IMPLEMENTATION.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_ARCHITECTURE_AS_IS_v1_4_candidate.source.md","sha256":"918c46edf4b81af9bd65700fe124d2d2b9228ce03effaf58f3ab4681e9a2a7ab","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-51ba9d764204","virtual_path":"v14c2/LION_ARCHITECTURE_AS_IS_v1_4_candidate.source.md"}
````markdown
# LION Architecture AS-IS v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=CANDIDATE_PROJECTION
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=integrated and live-observed architecture
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

## Exact baseline

`DonkeyJJLove/ai_platform@5d5a02b37fdfff4bcbf62f455d37ce4b86080f59` / tree `9725bebf8d9766c58096cfc34af06ffcb8aa32f1`. Current exact-head Core, Bandit and CodeQL evidence was observed successful during reacquisition.

## Integrated control flow

```text
World/System evidence
→ truth/currentness
→ Gap → CapabilityNeed
→ BeanSpec / Composition / Mosaic
→ candidate construction + verification
→ ActionSpec
→ CanonicalActionIR / LAIR
→ deterministic static projection
→ ExplicitActionProposalContext
→ ActionProposal
→ CanonicalPDPAdmissionContext
→ CanonicalPolicyDecisionPoint
→ PDPResult
```

The action chain above is non-effectful through the PDP handoff. A policy `ALLOW` is not itself an EffectPermit and does not create runtime authority.

## Factory evidence

The integrated B0 terminal protocol now passes two dissimilar unseen problem families using one workflow type, with distinct generated specs and verified candidate digests. A falsified holdout produces `FALSIFIED` rather than a fake pass and the experiment has no detected effect surface.

This proves the **bounded B0 protocol property**. It does not prove unrestricted general Factory generativity, recursive child-autonomy activation or Factory-of-factories.

## Runtime/host state

```text
logical_nodes=4
physical_failure_domains_observed=1
runner=observed on LION-AUTH-LAB
old MOON runner/control-plane overlap=not observed
local model runtime=not observed
```

`LION-AUTH-LAB` improves role isolation and provides WSL/rootless-Docker execution substrate; it is not an independent physical verifier domain.

## Explicit non-claims

- `GlobalCompleteMediation=UNKNOWN`.
- canonical PDP result-to-runtime-effect binding is unfinished.
- LCMS and LocalConsole are not integrated.
- local open-weight model runtime is not deployed.
- production authority/readiness is not proven.
- robotics/cyber-physical execution is not implemented.

````
LION_RECORD_END: SRC-V14C2-51ba9d764204

<a id="src-v14c2-98fc7a51859f"></a>
## SRC-V14C2-98fc7a51859f — v14c2/LION_CANONICAL_STATE_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-98fc7a51859f
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_CANONICAL_STATE_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=59086e3ff9de6b2d81928ff8455c64b97f7d7e4e45f6d38b6cf38e5ed846f072
SOURCE_BYTES=4810

LION_RECORD_BEGIN: SRC-V14C2-98fc7a51859f
LION_RECORD_META: {"anchor":"src-v14c2-98fc7a51859f","archive_id":"v14c2","authority_effect":"NONE","bytes":4810,"carrier":"09_LION_AS_IS_IMPLEMENTATION.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_CANONICAL_STATE_v1_4_candidate.source.json","sha256":"59086e3ff9de6b2d81928ff8455c64b97f7d7e4e45f6d38b6cf38e5ed846f072","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-98fc7a51859f","virtual_path":"v14c2/LION_CANONICAL_STATE_v1_4_candidate.source.json"}
````json
{
  "schema_version": "lion.canonical-state/v1.4-candidate",
  "baseline": {
    "repository": "DonkeyJJLove/ai_platform",
    "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
    "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1",
    "truth_subject_digest": "d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726"
  },
  "records": [
    {
      "id": "GoalContract",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "WorldSnapshot",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "SystemSnapshot",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "Gap",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "BeanSpec",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "BeanCandidate",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "BeanInstance",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "CapabilityNeed",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "CompositionEngine",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "HeterogeneousMosaicPlanner",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "R2E4EvidenceBinding",
      "plane": "AS_IS",
      "status": "INTEGRATED_POST_MERGE_OBSERVED",
      "evidence_refs": []
    },
    {
      "id": "FleetAggregateEffectBudget",
      "plane": "AS_IS",
      "status": "INTEGRATED_POST_MERGE_OBSERVED",
      "evidence_refs": []
    },
    {
      "id": "B0TwoFamilyTerminalGenerativityProtocol",
      "plane": "AS_IS",
      "status": "BOUNDED_PROTOCOL_PASS",
      "evidence_refs": []
    },
    {
      "id": "GeneralFactoryGenerativity",
      "plane": "UNKNOWN",
      "status": "NOT_PROVEN",
      "evidence_refs": []
    },
    {
      "id": "ActionSpec",
      "plane": "AS_IS",
      "status": "PARTIALLY_IMPLEMENTED",
      "evidence_refs": []
    },
    {
      "id": "CanonicalActionIR_LAIR",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE",
      "evidence_refs": []
    },
    {
      "id": "StaticActionProposalProjection",
      "plane": "AS_IS",
      "status": "INTEGRATED_NON_EFFECTFUL",
      "evidence_refs": []
    },
    {
      "id": "ExplicitActionProposalContextBinding",
      "plane": "AS_IS",
      "status": "INTEGRATED_NON_EFFECTFUL",
      "evidence_refs": []
    },
    {
      "id": "ActionProposalCanonicalPDPHandoff",
      "plane": "AS_IS",
      "status": "INTEGRATED_NON_EFFECTFUL",
      "evidence_refs": []
    },
    {
      "id": "PDPResultRuntimeEffectBinding",
      "plane": "TARGET",
      "status": "TARGET_NOT_IMPLEMENTED_CANONICALLY",
      "evidence_refs": []
    },
    {
      "id": "RuntimeAdmissionEngine",
      "plane": "AS_IS",
      "status": "INTEGRATED_EXISTING_ENGINE",
      "evidence_refs": []
    },
    {
      "id": "LCMS",
      "plane": "CANDIDATE",
      "status": "STALE_BASE_CANDIDATE",
      "evidence_refs": []
    },
    {
      "id": "ReadonlyProcessAdapter",
      "plane": "CANDIDATE",
      "status": "STALE_BASE_CANDIDATE",
      "evidence_refs": []
    },
    {
      "id": "LocalConsole",
      "plane": "TARGET",
      "status": "TARGET_NOT_INTEGRATED",
      "evidence_refs": []
    },
    {
      "id": "AutonomyBlueprint",
      "plane": "TARGET",
      "status": "TARGET_NOT_IMPLEMENTED",
      "evidence_refs": []
    },
    {
      "id": "MaterializerRegistry",
      "plane": "TARGET",
      "status": "TARGET_NOT_IMPLEMENTED",
      "evidence_refs": []
    },
    {
      "id": "LocalOpenWeightModelRuntime",
      "plane": "TARGET",
      "status": "TARGET_NOT_DEPLOYED",
      "evidence_refs": []
    },
    {
      "id": "HybridModelRouter",
      "plane": "CANDIDATE",
      "status": "STALE_BASE_CANDIDATE",
      "evidence_refs": []
    },
    {
      "id": "PhysicalActionSpec",
      "plane": "CANDIDATE",
      "status": "STALE_BASE_CANDIDATE",
      "evidence_refs": []
    },
    {
      "id": "CyberPhysicalRuntime",
      "plane": "TARGET",
      "status": "TARGET_NOT_IMPLEMENTED",
      "evidence_refs": []
    },
    {
      "id": "GlobalCompleteMediation",
      "plane": "UNKNOWN",
      "status": "UNKNOWN",
      "evidence_refs": []
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-98fc7a51859f

<a id="src-v14c2-fb490fbc4183"></a>
## SRC-V14C2-fb490fbc4183 — v14c2/LION_IMPLEMENTATION_STATUS_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-fb490fbc4183
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_IMPLEMENTATION_STATUS_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=a07985a1f05985b210389412d3e60176691d8c24d62adc545960a160232e9718
SOURCE_BYTES=4505

LION_RECORD_BEGIN: SRC-V14C2-fb490fbc4183
LION_RECORD_META: {"anchor":"src-v14c2-fb490fbc4183","archive_id":"v14c2","authority_effect":"NONE","bytes":4505,"carrier":"09_LION_AS_IS_IMPLEMENTATION.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_IMPLEMENTATION_STATUS_v1_4_candidate.source.json","sha256":"a07985a1f05985b210389412d3e60176691d8c24d62adc545960a160232e9718","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-fb490fbc4183","virtual_path":"v14c2/LION_IMPLEMENTATION_STATUS_v1_4_candidate.source.json"}
````json
{
  "schema_version": "lion.implementation-status/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "baseline": {
    "repository": "DonkeyJJLove/ai_platform",
    "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
    "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1",
    "truth_subject_digest": "d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726"
  },
  "system_state": "INTEGRATED_ENGINEERING_PLATFORM_SUPERVISED_DOMAIN_AUTONOMY",
  "preproduction_ready": false,
  "records": [
    {
      "component": "GoalContract",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "WorldSnapshot",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "SystemSnapshot",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "Gap",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "BeanSpec",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "BeanCandidate",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "BeanInstance",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "CapabilityNeed",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "CompositionEngine",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "HeterogeneousMosaicPlanner",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "R2E4EvidenceBinding",
      "plane": "AS_IS",
      "status": "INTEGRATED_POST_MERGE_OBSERVED"
    },
    {
      "component": "FleetAggregateEffectBudget",
      "plane": "AS_IS",
      "status": "INTEGRATED_POST_MERGE_OBSERVED"
    },
    {
      "component": "B0TwoFamilyTerminalGenerativityProtocol",
      "plane": "AS_IS",
      "status": "BOUNDED_PROTOCOL_PASS"
    },
    {
      "component": "GeneralFactoryGenerativity",
      "plane": "UNKNOWN",
      "status": "NOT_PROVEN"
    },
    {
      "component": "ActionSpec",
      "plane": "AS_IS",
      "status": "PARTIALLY_IMPLEMENTED"
    },
    {
      "component": "CanonicalActionIR_LAIR",
      "plane": "AS_IS",
      "status": "INTEGRATED_VERIFIED_PRIMITIVE"
    },
    {
      "component": "StaticActionProposalProjection",
      "plane": "AS_IS",
      "status": "INTEGRATED_NON_EFFECTFUL"
    },
    {
      "component": "ExplicitActionProposalContextBinding",
      "plane": "AS_IS",
      "status": "INTEGRATED_NON_EFFECTFUL"
    },
    {
      "component": "ActionProposalCanonicalPDPHandoff",
      "plane": "AS_IS",
      "status": "INTEGRATED_NON_EFFECTFUL"
    },
    {
      "component": "PDPResultRuntimeEffectBinding",
      "plane": "TARGET",
      "status": "TARGET_NOT_IMPLEMENTED_CANONICALLY"
    },
    {
      "component": "RuntimeAdmissionEngine",
      "plane": "AS_IS",
      "status": "INTEGRATED_EXISTING_ENGINE"
    },
    {
      "component": "LCMS",
      "plane": "CANDIDATE",
      "status": "STALE_BASE_CANDIDATE"
    },
    {
      "component": "ReadonlyProcessAdapter",
      "plane": "CANDIDATE",
      "status": "STALE_BASE_CANDIDATE"
    },
    {
      "component": "LocalConsole",
      "plane": "TARGET",
      "status": "TARGET_NOT_INTEGRATED"
    },
    {
      "component": "AutonomyBlueprint",
      "plane": "TARGET",
      "status": "TARGET_NOT_IMPLEMENTED"
    },
    {
      "component": "MaterializerRegistry",
      "plane": "TARGET",
      "status": "TARGET_NOT_IMPLEMENTED"
    },
    {
      "component": "LocalOpenWeightModelRuntime",
      "plane": "TARGET",
      "status": "TARGET_NOT_DEPLOYED"
    },
    {
      "component": "HybridModelRouter",
      "plane": "CANDIDATE",
      "status": "STALE_BASE_CANDIDATE"
    },
    {
      "component": "PhysicalActionSpec",
      "plane": "CANDIDATE",
      "status": "STALE_BASE_CANDIDATE"
    },
    {
      "component": "CyberPhysicalRuntime",
      "plane": "TARGET",
      "status": "TARGET_NOT_IMPLEMENTED"
    },
    {
      "component": "GlobalCompleteMediation",
      "plane": "UNKNOWN",
      "status": "UNKNOWN"
    }
  ],
  "first_genuinely_unfinished_step": "bind canonical PDP ALLOW result to exact RequestedRuntimeEffect and runtime identity before RuntimeAdmissionEngine"
}

````
LION_RECORD_END: SRC-V14C2-fb490fbc4183
