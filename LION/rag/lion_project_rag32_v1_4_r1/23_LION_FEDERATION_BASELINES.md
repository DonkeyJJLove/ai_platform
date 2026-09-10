# LION — Federacja repozytoriów i historyczne baseline’y Git

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=23_FEDERATION_BASELINES
SEARCH_TERMS=repository federation baseline head tree manifest semantic ownership
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-914025f33917"></a>
## SRC-V13-914025f33917 — v13/LION_REPOSITORY_FEDERATION_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-914025f33917
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_REPOSITORY_FEDERATION_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=d9af756f9d2ce1789ac281026f05a2e42d61c92f8fc7fb89abeae668e8e61b8d
SOURCE_BYTES=6573

LION_RECORD_BEGIN: SRC-V13-914025f33917
LION_RECORD_META: {"anchor":"src-v13-914025f33917","archive_id":"v13","authority_effect":"NONE","bytes":6573,"carrier":"23_LION_FEDERATION_BASELINES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_REPOSITORY_FEDERATION_v1_3_candidate.source.json","sha256":"d9af756f9d2ce1789ac281026f05a2e42d61c92f8fc7fb89abeae668e8e61b8d","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-914025f33917","virtual_path":"v13/LION_REPOSITORY_FEDERATION_v1_3_candidate.source.json"}
````json
{
  "canonical_control_repository": "DonkeyJJLove/ai_platform",
  "federation_mode": "CONTRACT_FEDERATION_NOT_MONOREPO",
  "generated_at": "2026-09-02T12:08:31Z",
  "invariants": [
    "repository != subsystem",
    "manifest != runtime admission",
    "public repository != open-source grant",
    "registered capability != authority",
    "data flow != credential inheritance"
  ],
  "repositories": [
    {
      "default_branch": "master",
      "head": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "license": "NOASSERTION_ROOT_LICENSE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "ENGINEERING_CANDIDATE",
      "observed_commit_at": "2026-08-31T12:21:56Z",
      "release": "NONE",
      "repository": "DonkeyJJLove/ai_platform",
      "role": [
        "EnterpriseControlPlane",
        "AgentFoundry",
        "SwarmPlanner",
        "FederationRegistry",
        "AuthorityPolicyEngine"
      ],
      "state": "INTEGRATED_ENGINEERING_PLATFORM",
      "tree": "3c9705f85301e73f268228f3c36f6ae82a641633"
    },
    {
      "default_branch": "master",
      "head": "b8657036cbfbc77b14de6ffc0e7bececacef9b67",
      "license": "MIT_FILE_WITH_UNRESOLVED_PLACEHOLDERS",
      "manifest": "PRESENT",
      "manifest_epistemic": "FORMALISED",
      "observed_commit_at": "2026-08-19T09:30:26Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/chunk-chunk",
      "role": [
        "ProcessSemanticsEngine",
        "TransitionMicrocode",
        "TrajectoryDiagnostics"
      ],
      "state": "FORMALISED_COMPONENT_REPOSITORY",
      "tree": "3fdfc759879ad2f9909478d981a9710961f7c951"
    },
    {
      "default_branch": "master",
      "head": "1506876c51166f08a9f88478d95063772f4528ab",
      "license": "MIT",
      "manifest": "PRESENT",
      "manifest_epistemic": "ENGINEERING_CANDIDATE",
      "observed_commit_at": "2026-08-19T09:15:33Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/glitchlab",
      "role": [
        "EvolutionCompiler",
        "DeltaNormalizer",
        "InvariantEvaluator",
        "StructuralChangeAnalyzer"
      ],
      "state": "ENGINEERING_CANDIDATE_COMPONENT",
      "tree": "50d25834c396bf07dfe26270d0158f052d621642"
    },
    {
      "default_branch": "master",
      "head": "e2aabacf6854f36de43e9b5bf13ff6bd0780f15b",
      "license": "NOASSERTION_ROOT_LICENSE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "EXPERIMENTAL",
      "observed_commit_at": "2026-08-19T09:24:45Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/HA2D",
      "role": [
        "ContextMemoryLab",
        "MemoryCandidateProvider",
        "ReplayContextProvider",
        "ProcessStateDiagnostics"
      ],
      "state": "EXPERIMENTAL_COMPONENT",
      "tree": "ea9c9d18ec0b7dae8460212746612079280eec2c"
    },
    {
      "default_branch": "main",
      "head": "2fbb568875aad2026dcc4d6c70023a6fc33f49c8",
      "license": "NOASSERTION_ROOT_LICENSE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "EXPERIMENTAL",
      "observed_commit_at": "2026-08-19T09:36:14Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/hipotezy_nadawcze_LLM",
      "role": [
        "HypothesisLab",
        "ExperimentDesignProvider",
        "FalsificationEvidenceProvider"
      ],
      "state": "EXPERIMENTAL_RESEARCH_COMPONENT",
      "tree": "cf0adfae3d3a1ace3436b95e8eeae80c0e0a53a3"
    },
    {
      "default_branch": "main",
      "head": "3036e5cb075617b2799735f56572f788ac5fbf2c",
      "license": "Apache-2.0",
      "manifest": "PRESENT",
      "manifest_epistemic": "ENGINEERING_CANDIDATE",
      "observed_commit_at": "2026-08-19T09:28:12Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/mosaic_lab_pro.py",
      "role": [
        "StructuralIntelligenceEngine",
        "GraphProjectionProvider",
        "TopologyRiskAnalyzer"
      ],
      "state": "ENGINEERING_CANDIDATE_COMPONENT",
      "tree": "c36c273117ee6e657127862f14357757bdd22b11"
    },
    {
      "default_branch": "main",
      "head": "ed5c95a081980186352309c425473dd8eefb35fb",
      "license": "NOASSERTION_ROOT_LICENSE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "OBSERVED",
      "observed_commit_at": "2026-08-19T09:41:09Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/sbom",
      "role": [
        "SupplyChainEvidenceProvider",
        "ArtifactIdentityProvider",
        "CompositionIntelligence"
      ],
      "state": "OBSERVED_EVIDENCE_COMPONENT",
      "tree": "14bb3858445510228526f9e2568a8052cff3d36a"
    },
    {
      "default_branch": "master",
      "head": "f152e410300333f781290fc7cbc158e284a3676e",
      "license": "MIT_DECLARED_IN_README_ROOT_FILE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "ENGINEERING_CANDIDATE",
      "observed_commit_at": "2026-08-19T09:20:31Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/swarm",
      "role": [
        "ExecutionMesh",
        "WorkloadRuntime",
        "TelemetryPlane",
        "CapabilityLeaseRuntime"
      ],
      "state": "ENGINEERING_CANDIDATE_LAB_RUNTIME",
      "tree": "97fb122330b830a22ce7af2aa50fbfbd7ab77cdb"
    },
    {
      "default_branch": "main",
      "head": "4ac1697b390c905129006465fde9ab1b2bba2c56",
      "license": "Apache-2.0",
      "manifest": "PRESENT",
      "manifest_epistemic": "FORMALISED",
      "observed_commit_at": "2026-08-19T09:33:45Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/SymulacjaKaskadySieciowej",
      "role": [
        "SimulationProvider",
        "FalsificationEngine",
        "StressScenarioProvider",
        "SensitivityAnalyzer"
      ],
      "state": "FORMALISED_SIMULATION_COMPONENT",
      "tree": "1dd51900aef89a902906d4820af3a64a2f2e4cf9"
    },
    {
      "default_branch": "master",
      "head": "65f1bf06d0cc4971dc86a2f0923b42c5b3819efd",
      "license": "UNKNOWN_NOT_REPRODUCED_IN_THIS_RUN",
      "manifest": "ABSENT",
      "manifest_epistemic": "UNKNOWN",
      "observed_commit_at": "2026-04-27T05:15:23Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/writeups",
      "role": [
        "ResearchMemory",
        "EvidenceCorpus",
        "Publication"
      ],
      "state": "RESEARCH_CORPUS_WITHOUT_FEDERATION_MANIFEST",
      "tree": "a91028035765220dce90e4a93c3062b06f082bf3"
    }
  ],
  "runtime_federation_state": "PARTIAL_NOT_PROVEN_END_TO_END",
  "schema_version": "lion.repository-federation/v1.3-candidate"
}

````
LION_RECORD_END: SRC-V13-914025f33917

<a id="src-v13-099a3e88dd92"></a>
## SRC-V13-099a3e88dd92 — v13/evidence/GITHUB_BASELINES.json

SOURCE_ID=SRC-V13-099a3e88dd92
SOURCE_ARCHIVE=v13
SOURCE_PATH=evidence/GITHUB_BASELINES.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=848f564b94f31933b1c0550ec511e4108447e12254c0f8c8a732926e0f28265e
SOURCE_BYTES=7337

LION_RECORD_BEGIN: SRC-V13-099a3e88dd92
LION_RECORD_META: {"anchor":"src-v13-099a3e88dd92","archive_id":"v13","authority_effect":"NONE","bytes":7337,"carrier":"23_LION_FEDERATION_BASELINES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"evidence/GITHUB_BASELINES.json","sha256":"848f564b94f31933b1c0550ec511e4108447e12254c0f8c8a732926e0f28265e","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-099a3e88dd92","virtual_path":"v13/evidence/GITHUB_BASELINES.json"}
````json
{
  "candidates": [
    {
      "authority_effect": "NONE",
      "base_branch": "master",
      "base_head": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "draft": false,
      "evidence": "12 successful exact-head workflow runs observed",
      "head": "8bf8934a0cf2809b58b460c01976cf82ae0692e7",
      "head_branch": "mission/r2e4-fleet-manifest-exact-head-semantic-binding",
      "integrated": false,
      "name": "R2E4 exact-head semantic and evidence binding",
      "pr": 248,
      "state": "VERIFIED_CANDIDATE",
      "tree": "eee3ea5f4f0a116e0f5409b6885a4fb0a5f691d1"
    },
    {
      "authority_effect": "RESTRICT_ONLY",
      "base_branch": "mission/r2e4-fleet-manifest-exact-head-semantic-binding",
      "base_head": "8bf8934a0cf2809b58b460c01976cf82ae0692e7",
      "draft": true,
      "evidence": "7 successful exact-head workflow runs; budget/concurrency/replay/PEP tests passed",
      "head": "46174de77634ce2b6d62bd6709f8ff3470d51951",
      "head_branch": "mission/fleet-aggregate-effect-budget-r1",
      "integrated": false,
      "name": "Fleet aggregate effect budget",
      "pr": 249,
      "state": "VERIFIED_CANDIDATE_STACKED",
      "tree": "a2c2ca9594dd30174e0892f48464678da27e1bf2"
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "repositories": [
    {
      "default_branch": "master",
      "head": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "license": "NOASSERTION_ROOT_LICENSE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "ENGINEERING_CANDIDATE",
      "observed_commit_at": "2026-08-31T12:21:56Z",
      "release": "NONE",
      "repository": "DonkeyJJLove/ai_platform",
      "role": [
        "EnterpriseControlPlane",
        "AgentFoundry",
        "SwarmPlanner",
        "FederationRegistry",
        "AuthorityPolicyEngine"
      ],
      "state": "INTEGRATED_ENGINEERING_PLATFORM",
      "tree": "3c9705f85301e73f268228f3c36f6ae82a641633"
    },
    {
      "default_branch": "master",
      "head": "b8657036cbfbc77b14de6ffc0e7bececacef9b67",
      "license": "MIT_FILE_WITH_UNRESOLVED_PLACEHOLDERS",
      "manifest": "PRESENT",
      "manifest_epistemic": "FORMALISED",
      "observed_commit_at": "2026-08-19T09:30:26Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/chunk-chunk",
      "role": [
        "ProcessSemanticsEngine",
        "TransitionMicrocode",
        "TrajectoryDiagnostics"
      ],
      "state": "FORMALISED_COMPONENT_REPOSITORY",
      "tree": "3fdfc759879ad2f9909478d981a9710961f7c951"
    },
    {
      "default_branch": "master",
      "head": "1506876c51166f08a9f88478d95063772f4528ab",
      "license": "MIT",
      "manifest": "PRESENT",
      "manifest_epistemic": "ENGINEERING_CANDIDATE",
      "observed_commit_at": "2026-08-19T09:15:33Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/glitchlab",
      "role": [
        "EvolutionCompiler",
        "DeltaNormalizer",
        "InvariantEvaluator",
        "StructuralChangeAnalyzer"
      ],
      "state": "ENGINEERING_CANDIDATE_COMPONENT",
      "tree": "50d25834c396bf07dfe26270d0158f052d621642"
    },
    {
      "default_branch": "master",
      "head": "e2aabacf6854f36de43e9b5bf13ff6bd0780f15b",
      "license": "NOASSERTION_ROOT_LICENSE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "EXPERIMENTAL",
      "observed_commit_at": "2026-08-19T09:24:45Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/HA2D",
      "role": [
        "ContextMemoryLab",
        "MemoryCandidateProvider",
        "ReplayContextProvider",
        "ProcessStateDiagnostics"
      ],
      "state": "EXPERIMENTAL_COMPONENT",
      "tree": "ea9c9d18ec0b7dae8460212746612079280eec2c"
    },
    {
      "default_branch": "main",
      "head": "2fbb568875aad2026dcc4d6c70023a6fc33f49c8",
      "license": "NOASSERTION_ROOT_LICENSE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "EXPERIMENTAL",
      "observed_commit_at": "2026-08-19T09:36:14Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/hipotezy_nadawcze_LLM",
      "role": [
        "HypothesisLab",
        "ExperimentDesignProvider",
        "FalsificationEvidenceProvider"
      ],
      "state": "EXPERIMENTAL_RESEARCH_COMPONENT",
      "tree": "cf0adfae3d3a1ace3436b95e8eeae80c0e0a53a3"
    },
    {
      "default_branch": "main",
      "head": "3036e5cb075617b2799735f56572f788ac5fbf2c",
      "license": "Apache-2.0",
      "manifest": "PRESENT",
      "manifest_epistemic": "ENGINEERING_CANDIDATE",
      "observed_commit_at": "2026-08-19T09:28:12Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/mosaic_lab_pro.py",
      "role": [
        "StructuralIntelligenceEngine",
        "GraphProjectionProvider",
        "TopologyRiskAnalyzer"
      ],
      "state": "ENGINEERING_CANDIDATE_COMPONENT",
      "tree": "c36c273117ee6e657127862f14357757bdd22b11"
    },
    {
      "default_branch": "main",
      "head": "ed5c95a081980186352309c425473dd8eefb35fb",
      "license": "NOASSERTION_ROOT_LICENSE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "OBSERVED",
      "observed_commit_at": "2026-08-19T09:41:09Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/sbom",
      "role": [
        "SupplyChainEvidenceProvider",
        "ArtifactIdentityProvider",
        "CompositionIntelligence"
      ],
      "state": "OBSERVED_EVIDENCE_COMPONENT",
      "tree": "14bb3858445510228526f9e2568a8052cff3d36a"
    },
    {
      "default_branch": "master",
      "head": "f152e410300333f781290fc7cbc158e284a3676e",
      "license": "MIT_DECLARED_IN_README_ROOT_FILE_ABSENT",
      "manifest": "PRESENT",
      "manifest_epistemic": "ENGINEERING_CANDIDATE",
      "observed_commit_at": "2026-08-19T09:20:31Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/swarm",
      "role": [
        "ExecutionMesh",
        "WorkloadRuntime",
        "TelemetryPlane",
        "CapabilityLeaseRuntime"
      ],
      "state": "ENGINEERING_CANDIDATE_LAB_RUNTIME",
      "tree": "97fb122330b830a22ce7af2aa50fbfbd7ab77cdb"
    },
    {
      "default_branch": "main",
      "head": "4ac1697b390c905129006465fde9ab1b2bba2c56",
      "license": "Apache-2.0",
      "manifest": "PRESENT",
      "manifest_epistemic": "FORMALISED",
      "observed_commit_at": "2026-08-19T09:33:45Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/SymulacjaKaskadySieciowej",
      "role": [
        "SimulationProvider",
        "FalsificationEngine",
        "StressScenarioProvider",
        "SensitivityAnalyzer"
      ],
      "state": "FORMALISED_SIMULATION_COMPONENT",
      "tree": "1dd51900aef89a902906d4820af3a64a2f2e4cf9"
    },
    {
      "default_branch": "master",
      "head": "65f1bf06d0cc4971dc86a2f0923b42c5b3819efd",
      "license": "UNKNOWN_NOT_REPRODUCED_IN_THIS_RUN",
      "manifest": "ABSENT",
      "manifest_epistemic": "UNKNOWN",
      "observed_commit_at": "2026-04-27T05:15:23Z",
      "release": "NONE_OBSERVED",
      "repository": "DonkeyJJLove/writeups",
      "role": [
        "ResearchMemory",
        "EvidenceCorpus",
        "Publication"
      ],
      "state": "RESEARCH_CORPUS_WITHOUT_FEDERATION_MANIFEST",
      "tree": "a91028035765220dce90e4a93c3062b06f082bf3"
    }
  ]
}

````
LION_RECORD_END: SRC-V13-099a3e88dd92

<a id="src-v14c2-821318a414a7"></a>
## SRC-V14C2-821318a414a7 — v14c2/LION_REPOSITORY_FEDERATION_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-821318a414a7
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_REPOSITORY_FEDERATION_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=dece51cb822c993a278bf07a4fc2c4df03b69fad4ee08618c03ecfeb74ebe655
SOURCE_BYTES=4817

LION_RECORD_BEGIN: SRC-V14C2-821318a414a7
LION_RECORD_META: {"anchor":"src-v14c2-821318a414a7","archive_id":"v14c2","authority_effect":"NONE","bytes":4817,"carrier":"23_LION_FEDERATION_BASELINES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_REPOSITORY_FEDERATION_v1_4_candidate.source.json","sha256":"dece51cb822c993a278bf07a4fc2c4df03b69fad4ee08618c03ecfeb74ebe655","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-821318a414a7","virtual_path":"v14c2/LION_REPOSITORY_FEDERATION_v1_4_candidate.source.json"}
````json
{
  "schema_version": "lion.repository-federation/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "state": "EXACT_VECTOR_AT_PACKAGE_BUILD",
  "repositories": [
    {
      "repository": "DonkeyJJLove/ai_platform",
      "default_branch": "master",
      "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
      "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1",
      "roles": [
        "EnterpriseControlPlane",
        "AgentFoundry",
        "SwarmPlanner",
        "FederationRegistry",
        "AuthorityPolicyEngine",
        "BeanFactoryOwner"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    },
    {
      "repository": "DonkeyJJLove/chunk-chunk",
      "default_branch": "master",
      "head": "b8657037e94787a103c99f1fbb3058341821ffd7",
      "tree": "3fdfc7ad46c2b742585aeb33a09c10a8e3b3d4f9",
      "roles": [
        "ProcessSemanticsEngine",
        "TransitionMicrocode",
        "TrajectoryDiagnostics"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    },
    {
      "repository": "DonkeyJJLove/glitchlab",
      "default_branch": "master",
      "head": "329d670e53f3e4606f60eeb2f446eb34df3bb05d",
      "tree": "653f7593e4c6f0478c2f85b48d3091d0faed7892",
      "roles": [
        "EvolutionCompiler",
        "DeltaNormalizer",
        "InvariantEvaluator",
        "StructuralChangeAnalyzer"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    },
    {
      "repository": "DonkeyJJLove/HA2D",
      "default_branch": "master",
      "head": "13ac2c760aa0c4f528addaacc782239c00e3890e",
      "tree": "bc6c8a067074fead00b57d6c9f8f852f1fa74977",
      "roles": [
        "ContextMemoryLab",
        "MemoryCandidateProvider",
        "ReplayContextProvider",
        "ProcessStateDiagnostics"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    },
    {
      "repository": "DonkeyJJLove/mosaic_lab_pro.py",
      "default_branch": "main",
      "head": "0ad23c8a9fb9f942e41ade83ecafa8f393e5d481",
      "tree": "ca88c45e92bd7bd4f5d269bc87c93ccaaf3716f1",
      "roles": [
        "StructuralIntelligenceEngine",
        "GraphProjectionProvider",
        "TopologyRiskAnalyzer"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    },
    {
      "repository": "DonkeyJJLove/hipotezy_nadawcze_LLM",
      "default_branch": "main",
      "head": "569acad16f0ca8eb0c4e4522586914b57f5bf475",
      "tree": "0c1f6d690a2bdae34f0ecd6c9afbb04933af220c",
      "roles": [
        "HypothesisLab",
        "ExperimentDesignProvider",
        "FalsificationEvidenceProvider"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    },
    {
      "repository": "DonkeyJJLove/swarm",
      "default_branch": "master",
      "head": "6aee0442d4b8a861989503ca55aac0c45f065afb",
      "tree": "86830750c688e9e65d3eafc7232e89f20267c705",
      "roles": [
        "ExecutionMesh",
        "WorkloadRuntime",
        "TelemetryPlane",
        "CapabilityLeaseRuntime"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    },
    {
      "repository": "DonkeyJJLove/sbom",
      "default_branch": "main",
      "head": "86b92e9f7c3361d69e2322193441f4626f8205e7",
      "tree": "8d7cc0e5b5025899d0889c4a5c17ac230681c4fb",
      "roles": [
        "SupplyChainEvidenceProvider",
        "ArtifactIdentityProvider",
        "CompositionIntelligence"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    },
    {
      "repository": "DonkeyJJLove/SymulacjaKaskadySieciowej",
      "default_branch": "main",
      "head": "2fa3b9f8285387d8f14e116901a671c4fcb75174",
      "tree": "9c3fc13abab6ac22631615ac4ac72085bd84ded9",
      "roles": [
        "SimulationProvider",
        "FalsificationEngine",
        "StressScenarioProvider",
        "SensitivityAnalyzer"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    },
    {
      "repository": "DonkeyJJLove/writeups",
      "default_branch": "master",
      "head": "63b1cded7eafddc8c6a7d585c99aa7d97b6ab92c",
      "tree": "2b82b8875f976b836af04db412483ce278e1ef95",
      "roles": [
        "ResearchMemory",
        "EvidenceCorpus",
        "Publication"
      ],
      "state": "CURRENT_EXACT_GIT_OBSERVATION",
      "currentness": "CURRENT_AT_PACKAGE_BUILD"
    }
  ],
  "invariants": [
    "repository != subsystem",
    "manifest != runtime admission",
    "semantic registry != exact baseline vector",
    "public != licensed"
  ]
}

````
LION_RECORD_END: SRC-V14C2-821318a414a7

<a id="src-v14c2-099a3e88dd92"></a>
## SRC-V14C2-099a3e88dd92 — v14c2/evidence/GITHUB_BASELINES.json

SOURCE_ID=SRC-V14C2-099a3e88dd92
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=evidence/GITHUB_BASELINES.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=806e6e15d660ed965646bf03deabb13acee04ba001186321d3088736cb988eb3
SOURCE_BYTES=2146

LION_RECORD_BEGIN: SRC-V14C2-099a3e88dd92
LION_RECORD_META: {"anchor":"src-v14c2-099a3e88dd92","archive_id":"v14c2","authority_effect":"NONE","bytes":2146,"carrier":"23_LION_FEDERATION_BASELINES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"evidence/GITHUB_BASELINES.json","sha256":"806e6e15d660ed965646bf03deabb13acee04ba001186321d3088736cb988eb3","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-099a3e88dd92","virtual_path":"v14c2/evidence/GITHUB_BASELINES.json"}
````json
{
  "schema_version": "lion.github-baselines/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "repositories": [
    {
      "repository": "DonkeyJJLove/ai_platform",
      "branch": "master",
      "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
      "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1"
    },
    {
      "repository": "DonkeyJJLove/chunk-chunk",
      "branch": "master",
      "head": "b8657037e94787a103c99f1fbb3058341821ffd7",
      "tree": "3fdfc7ad46c2b742585aeb33a09c10a8e3b3d4f9"
    },
    {
      "repository": "DonkeyJJLove/glitchlab",
      "branch": "master",
      "head": "329d670e53f3e4606f60eeb2f446eb34df3bb05d",
      "tree": "653f7593e4c6f0478c2f85b48d3091d0faed7892"
    },
    {
      "repository": "DonkeyJJLove/HA2D",
      "branch": "master",
      "head": "13ac2c760aa0c4f528addaacc782239c00e3890e",
      "tree": "bc6c8a067074fead00b57d6c9f8f852f1fa74977"
    },
    {
      "repository": "DonkeyJJLove/mosaic_lab_pro.py",
      "branch": "main",
      "head": "0ad23c8a9fb9f942e41ade83ecafa8f393e5d481",
      "tree": "ca88c45e92bd7bd4f5d269bc87c93ccaaf3716f1"
    },
    {
      "repository": "DonkeyJJLove/hipotezy_nadawcze_LLM",
      "branch": "main",
      "head": "569acad16f0ca8eb0c4e4522586914b57f5bf475",
      "tree": "0c1f6d690a2bdae34f0ecd6c9afbb04933af220c"
    },
    {
      "repository": "DonkeyJJLove/swarm",
      "branch": "master",
      "head": "6aee0442d4b8a861989503ca55aac0c45f065afb",
      "tree": "86830750c688e9e65d3eafc7232e89f20267c705"
    },
    {
      "repository": "DonkeyJJLove/sbom",
      "branch": "main",
      "head": "86b92e9f7c3361d69e2322193441f4626f8205e7",
      "tree": "8d7cc0e5b5025899d0889c4a5c17ac230681c4fb"
    },
    {
      "repository": "DonkeyJJLove/SymulacjaKaskadySieciowej",
      "branch": "main",
      "head": "2fa3b9f8285387d8f14e116901a671c4fcb75174",
      "tree": "9c3fc13abab6ac22631615ac4ac72085bd84ded9"
    },
    {
      "repository": "DonkeyJJLove/writeups",
      "branch": "master",
      "head": "63b1cded7eafddc8c6a7d585c99aa7d97b6ab92c",
      "tree": "2b82b8875f976b836af04db412483ce278e1ef95"
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-099a3e88dd92
