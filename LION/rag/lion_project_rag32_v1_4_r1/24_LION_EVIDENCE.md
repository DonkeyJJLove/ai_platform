# LION — Indeksy dowodów i ich ograniczenia

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=24_EVIDENCE
SEARCH_TERMS=evidence index CI workflow hosts provenance observations source limitations
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-a3fd7931a2e1"></a>
## SRC-V13-a3fd7931a2e1 — v13/EVIDENCE_INDEX.json

SOURCE_ID=SRC-V13-a3fd7931a2e1
SOURCE_ARCHIVE=v13
SOURCE_PATH=EVIDENCE_INDEX.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=5bcd55fa15d70b3aeff9d3301953dbffe1b6bde936700f0a40482a45a07c1216
SOURCE_BYTES=13515

LION_RECORD_BEGIN: SRC-V13-a3fd7931a2e1
LION_RECORD_META: {"anchor":"src-v13-a3fd7931a2e1","archive_id":"v13","authority_effect":"NONE","bytes":13515,"carrier":"24_LION_EVIDENCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"EVIDENCE_INDEX.json","sha256":"5bcd55fa15d70b3aeff9d3301953dbffe1b6bde936700f0a40482a45a07c1216","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-a3fd7931a2e1","virtual_path":"v13/EVIDENCE_INDEX.json"}
````json
{
  "external_references": [
    {
      "authority": "OpenAI official",
      "finding": "Current open-model family includes gpt-oss and safeguard variants; self-managed deployment.",
      "id": "EXT-OPENAI-001",
      "title": "Open models / gpt-oss",
      "url": "https://openai.com/open-models/"
    },
    {
      "authority": "OpenAI official",
      "finding": "20B approximately 16 GB class; 120B approximately 80 GB class; local ecosystem documented.",
      "id": "EXT-OPENAI-002",
      "title": "Introducing gpt-oss",
      "url": "https://openai.com/index/introducing-gpt-oss/"
    },
    {
      "authority": "OpenAI official Help Center",
      "finding": "Self-managed open weights differ from OpenAI API-hosted models.",
      "id": "EXT-OPENAI-003",
      "title": "Open-weight models",
      "url": "https://help.openai.com/en/articles/11870455-openai-open-weight-models-gpt-oss"
    },
    {
      "authority": "ISO official",
      "finding": "Industrial robot safety requirements.",
      "id": "EXT-ISO-001",
      "title": "ISO 10218-1:2025",
      "url": "https://www.iso.org/standard/73933.html"
    },
    {
      "authority": "ISO official",
      "finding": "Robot application/cell integration safety requirements.",
      "id": "EXT-ISO-002",
      "title": "ISO 10218-2:2025",
      "url": "https://www.iso.org/standard/73934.html"
    },
    {
      "authority": "EUR-Lex",
      "finding": "General application from 20 January 2027; future machine/robot target.",
      "id": "EXT-EU-001",
      "title": "Regulation (EU) 2023/1230",
      "url": "https://eur-lex.europa.eu/eli/reg/2023/1230/oj"
    },
    {
      "authority": "EUR-Lex",
      "finding": "AI Act requirements relevant to physical environments, oversight, robustness and cybersecurity.",
      "id": "EXT-EU-002",
      "title": "Regulation (EU) 2024/1689",
      "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj"
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "github": {
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
    "exact_master_ci": {
      "head": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "runs": [
        {
          "conclusion": "success",
          "id": 33391391678,
          "name": "Cyber-Lion Core"
        },
        {
          "conclusion": "success",
          "id": 33391391679,
          "name": "Bandit"
        },
        {
          "conclusion": "success",
          "id": 33391390994,
          "name": "CodeQL push"
        },
        {
          "conclusion": "success",
          "id": 33597811837,
          "name": "Scheduled CodeQL"
        }
      ]
    },
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
  },
  "hosts": [
    {
      "container_runtime": "ABSENT",
      "cpu": "AMD Ryzen 9 9950X3D",
      "environment": "WSL2 / Debian 13",
      "gpu_visible": false,
      "kernel": "6.6.87.2-microsoft-standard-WSL2",
      "local_model_runtime": "ABSENT",
      "logical_cpus": 24,
      "logical_host": "LAB-DEBIAN",
      "memory_kib": 49328252,
      "python": "3.13.5",
      "security": {
        "cgroup_v2": true,
        "cyber_lion_control_plane": "ACTIVE; dedicated user; NoNewPrivileges=yes; ProtectSystem=strict; process Seccomp=0",
        "lion_lab_producer": "ACTIVE; dedicated signer; NoNewPrivileges=yes; process Seccomp=2",
        "tpm_visible": false
      },
      "sentinel_host_id": "host_2c67e8a68ffd6360",
      "state": "ONLINE_LOGICAL_NODE_SINGLE_PHYSICAL_DOMAIN",
      "swap_gib": 16
    },
    {
      "container_runtime": "ABSENT",
      "cpu": "AMD Ryzen 9 9950X3D",
      "environment": "WSL2 / Ubuntu 24.04.4",
      "gpu_visible": false,
      "kernel": "6.6.87.2-microsoft-standard-WSL2",
      "local_model_runtime": "ABSENT",
      "logical_cpus": 24,
      "logical_host": "MOON",
      "memory_kib": 49328252,
      "python": "3.12.3",
      "security": {
        "authority_group_overlap": "lion-maintenance-runner remains member of lion-control-plane",
        "cgroup_v2": true,
        "control_plane_store": "/var/lib/lion/control-plane owned by lion-control-plane, mode 2770",
        "github_runner": "ACTIVE as lion-maintenance-runner; NoNewPrivileges=0; Seccomp=0",
        "tpm_visible": false
      },
      "sentinel_host_id": "host_045dbf1af63f49d4",
      "state": "ONLINE_LOGICAL_NODE_WITH_LIVE_AUTHORITY_SEPARATION_BLOCKER",
      "swap_gib": 16
    },
    {
      "container_runtime": "ABSENT",
      "cpu": "AMD Ryzen 9 9950X3D",
      "environment": "WSL2 / Ubuntu 24.04.4",
      "gpu_visible": false,
      "kernel": "6.6.87.2-microsoft-standard-WSL2",
      "local_model_runtime": "ABSENT",
      "logical_cpus": 24,
      "logical_host": "LAB-UBUNTU",
      "memory_kib": 49328252,
      "python": "3.12.3",
      "security": {
        "cgroup_v2": true,
        "sentinel_tag_drift": "Ollama/model-server tag present, but no binary/service/process/runtime observed",
        "tpm_visible": false
      },
      "sentinel_host_id": "host_df0fa36eb7d44d5b",
      "state": "ONLINE_LOGICAL_NODE_WITH_STALE_MODEL_TAG",
      "swap_gib": 16
    }
  ],
  "limitations": [
    "No repository or host was mutated.",
    "No package/model was installed.",
    "Host observations prove visible WSL state, not hidden physical devices.",
    "Full tests were not rerun locally; exact-head CI is separately classified.",
    "No cyber-physical compliance claim is made."
  ],
  "method": "READ_ONLY live GitHub + exact Git objects + workflow metadata + SentinelX host census + supplied sources + official external sources",
  "package_id": "the-bean-factory-lion-evolution-v1.3-candidate-2026-09-02",
  "project_sources": [
    "LION v1.2 source pack",
    "master research prompt",
    "JARZMO/reference-monitor research",
    "Geometria Tygrysa/probabilistic sources",
    "historical refresh/Bean Factory analyses"
  ],
  "schema_version": "lion.evidence-index/v1.3-candidate"
}

````
LION_RECORD_END: SRC-V13-a3fd7931a2e1

<a id="src-v14c2-a3fd7931a2e1"></a>
## SRC-V14C2-a3fd7931a2e1 — v14c2/EVIDENCE_INDEX.json

SOURCE_ID=SRC-V14C2-a3fd7931a2e1
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=EVIDENCE_INDEX.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=06fdfc1db6880230eeec95ee9be9376dcd0f67d99efcee7926312373a28fe024
SOURCE_BYTES=8013

LION_RECORD_BEGIN: SRC-V14C2-a3fd7931a2e1
LION_RECORD_META: {"anchor":"src-v14c2-a3fd7931a2e1","archive_id":"v14c2","authority_effect":"NONE","bytes":8013,"carrier":"24_LION_EVIDENCE.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"EVIDENCE_INDEX.json","sha256":"06fdfc1db6880230eeec95ee9be9376dcd0f67d99efcee7926312373a28fe024","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-a3fd7931a2e1","virtual_path":"v14c2/EVIDENCE_INDEX.json"}
````json
{
  "schema_version": "lion.evidence-index/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "package_version": "1.4.0-candidate.2",
  "method": "Supplied v1.3 RAG-40 + manifest/digest topology audit + live GitHub exact master/federation + live SentinelX read-only census",
  "baseline": {
    "repository": "DonkeyJJLove/ai_platform",
    "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
    "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1",
    "truth_subject_digest": "d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726"
  },
  "exact_master_ci": [
    {
      "name": "Cyber-Lion Core",
      "conclusion": "success"
    },
    {
      "name": "Bandit Security Scan",
      "conclusion": "success"
    },
    {
      "name": "CodeQL push",
      "conclusion": "success"
    }
  ],
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
  "hosts": [
    {
      "logical_host": "MOON",
      "environment": "WSL2 / Ubuntu",
      "physical_domain": "WINDOWS-MOON",
      "runner": "NOT_OBSERVED",
      "lion_maintenance_runner_groups": [
        "lion-maintenance-runner"
      ],
      "control_plane_overlap": "NOT_OBSERVED",
      "mount_c": "9p",
      "local_model_runtime": "NOT_OBSERVED"
    },
    {
      "logical_host": "LION-AUTH-LAB",
      "environment": "WSL2 / Debian 13",
      "physical_domain": "WINDOWS-MOON",
      "runner": "OBSERVED /opt/lion/github-runner",
      "container_runtime": "ROOTLESS_DOCKER_OBSERVED",
      "mount_c": "9p",
      "local_model_runtime": "NOT_OBSERVED"
    },
    {
      "logical_host": "LAB-DEBIAN",
      "environment": "WSL2 / Debian 13",
      "physical_domain": "WINDOWS-MOON",
      "runner": "NOT_OBSERVED",
      "local_model_runtime": "NOT_OBSERVED"
    },
    {
      "logical_host": "LAB-UBUNTU",
      "environment": "WSL2 / Ubuntu 24.04",
      "physical_domain": "WINDOWS-MOON",
      "runner": "NOT_OBSERVED",
      "local_model_runtime": "NOT_OBSERVED"
    }
  ],
  "current_code_evidence": [
    {
      "id": "E-ACTION-PDP",
      "state": "INTEGRATED",
      "ref": "cyber_lion/contracts/action_proposal_pdp_handoff.py",
      "finding": "context-complete ActionProposal handoff to existing CanonicalPolicyDecisionPoint returns PDPResult without effect"
    },
    {
      "id": "E-ACTION-GAP",
      "state": "PARTIAL",
      "ref": "cyber_lion/architecture_projection/gap.py",
      "finding": "next minimal gap is PDP ALLOW to exact RequestedRuntimeEffect/runtime identity before RuntimeAdmissionEngine"
    },
    {
      "id": "E-LAIR",
      "state": "INTEGRATED",
      "ref": "cyber_lion/contracts/action_ir.py",
      "finding": "CanonicalActionIR deterministic, canonical, digest-bound, non-effectful"
    },
    {
      "id": "E-B0",
      "state": "BOUNDED_PROTOCOL_PASS",
      "ref": "cyber_lion/tests/test_bean_generativity_protocol.py",
      "finding": "two dissimilar unseen problem families PASS same workflow; negative holdout falsifies; no detected effect surface"
    },
    {
      "id": "E-TRUTH",
      "state": "INTEGRATED_WITH_PROJECTION_DRIFT",
      "ref": "LION/architecture/canonical-state-v1-3-candidate.json",
      "finding": "truth projection uses v1.4-a0 protocol but contains stale candidate metadata for some historical frontiers"
    }
  ],
  "limitations": [
    "No repository mutation",
    "No host mutation",
    "No local model installed",
    "No production effect executed",
    "Physical independence not established",
    "External standards/model-research not revalidated in this build unless separately noted"
  ]
}

````
LION_RECORD_END: SRC-V14C2-a3fd7931a2e1
