# LION — Modele awarii i spisy hostów

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=19_HOST_FAILURES
SEARCH_TERMS=host census failure domain WSL MOON LION-AUTH-LAB LAB-DEBIAN LAB-UBUNTU
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-26c7e3df57a8"></a>
## SRC-V13-26c7e3df57a8 — v13/FLEET_FAILURE_MODEL_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-26c7e3df57a8
SOURCE_ARCHIVE=v13
SOURCE_PATH=FLEET_FAILURE_MODEL_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=d62e6c378f971b2100c34c281804c3e46e2fddab858e3e223500690293b5ef68
SOURCE_BYTES=1177

LION_RECORD_BEGIN: SRC-V13-26c7e3df57a8
LION_RECORD_META: {"anchor":"src-v13-26c7e3df57a8","archive_id":"v13","authority_effect":"NONE","bytes":1177,"carrier":"19_LION_HOST_FAILURES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"FLEET_FAILURE_MODEL_v1_3_candidate.source.md","sha256":"d62e6c378f971b2100c34c281804c3e46e2fddab858e3e223500690293b5ef68","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-26c7e3df57a8","virtual_path":"v13/FLEET_FAILURE_MODEL_v1_3_candidate.source.md"}
````markdown
# Fleet Failure Model v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=CANDIDATE_POLICY
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=fleet, model, command and cyber-physical failures
DEPENDENCIES=v1.2 failure model
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

The v1.2 adversarial space remains mandatory. Add model crash/restart/OOM/substitution, tokenizer/runtime substitution, malformed Action IR, command/argument/path/environment injection, TOCTOU, executable/workspace substitution, orphan processes, hidden writes, stale permit, observer death, receipt loss, local/SaaS disagreement and Factory self-promotion.

Future physical failures include stale/spoofed sensors, unit/frame mismatch, calibration drift, unexpected contact, force/speed violations, safety-channel failure, partial physical effect and digital-twin divergence.

Every failure fails closed or enters an explicit PARTIAL, DEGRADED, RESTRICTED, FROZEN or UNRECONCILED state.

````
LION_RECORD_END: SRC-V13-26c7e3df57a8

<a id="src-v13-f9ff031a93d0"></a>
## SRC-V13-f9ff031a93d0 — v13/LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-f9ff031a93d0
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=f2731e226a16fe6e2d887d82a2c610dfb4c202c18e34ca94f106c02ae8b18a86
SOURCE_BYTES=967

LION_RECORD_BEGIN: SRC-V13-f9ff031a93d0
LION_RECORD_META: {"anchor":"src-v13-f9ff031a93d0","archive_id":"v13","authority_effect":"NONE","bytes":967,"carrier":"19_LION_HOST_FAILURES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_3_candidate.source.md","sha256":"f2731e226a16fe6e2d887d82a2c610dfb4c202c18e34ca94f106c02ae8b18a86","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-f9ff031a93d0","virtual_path":"v13/LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_3_candidate.source.md"}
````markdown
# LION Host and Failure-Domain Model v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=LIVE_OBSERVED_PROJECTION
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=logical hosts and physical domains
DEPENDENCIES=SentinelX census
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

## Observed world

```text
MOON       = WSL2 logical node
LAB-DEBIAN = WSL2 logical node
LAB-UBUNTU = WSL2 logical node
PHYSICAL_DOMAIN = WINDOWS-MOON
```

All expose the same CPU family, WSL kernel/network domain and mounted Windows filesystem. Therefore:

```text
LOGICAL_NODE_COUNT=3
PHYSICAL_FAILURE_DOMAIN_COUNT=1
INDEPENDENCE=FAIL
```

MOON additionally retains a runner/control-plane group overlap. This document is an observation, not host-remediation authority.

````
LION_RECORD_END: SRC-V13-f9ff031a93d0

<a id="src-v13-e84d4af24832"></a>
## SRC-V13-e84d4af24832 — v13/evidence/HOST_CENSUS_SUMMARY.json

SOURCE_ID=SRC-V13-e84d4af24832
SOURCE_ARCHIVE=v13
SOURCE_PATH=evidence/HOST_CENSUS_SUMMARY.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=d31111ae8ce05bea387e5cb117b6e98b901be6ecf43ef9e9e150bd5f9096b880
SOURCE_BYTES=2520

LION_RECORD_BEGIN: SRC-V13-e84d4af24832
LION_RECORD_META: {"anchor":"src-v13-e84d4af24832","archive_id":"v13","authority_effect":"NONE","bytes":2520,"carrier":"19_LION_HOST_FAILURES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"evidence/HOST_CENSUS_SUMMARY.json","sha256":"d31111ae8ce05bea387e5cb117b6e98b901be6ecf43ef9e9e150bd5f9096b880","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-e84d4af24832","virtual_path":"v13/evidence/HOST_CENSUS_SUMMARY.json"}
````json
{
  "generated_at": "2026-09-02T12:08:31Z",
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
  "physical_domain_conclusion": "ONE_OBSERVED_WINDOWS_MOON_DOMAIN"
}

````
LION_RECORD_END: SRC-V13-e84d4af24832

<a id="src-v14c2-3bf3e923a533"></a>
## SRC-V14C2-3bf3e923a533 — v14c2/FLEET_FAILURE_MODEL_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-3bf3e923a533
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=FLEET_FAILURE_MODEL_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=e2987f249bdcf2b9fc0b3c3dd0a0208d48a884157570f79ceee46d2702a3ccf3
SOURCE_BYTES=1344

LION_RECORD_BEGIN: SRC-V14C2-3bf3e923a533
LION_RECORD_META: {"anchor":"src-v14c2-3bf3e923a533","archive_id":"v14c2","authority_effect":"NONE","bytes":1344,"carrier":"19_LION_HOST_FAILURES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"FLEET_FAILURE_MODEL_v1_4_candidate.source.md","sha256":"e2987f249bdcf2b9fc0b3c3dd0a0208d48a884157570f79ceee46d2702a3ccf3","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-3bf3e923a533","virtual_path":"v14c2/FLEET_FAILURE_MODEL_v1_4_candidate.source.md"}
````markdown
# Fleet Failure Model v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=CANDIDATE_POLICY
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=fleet, action, runtime, model and cyber-physical failures
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

Preserve all v1.3 failure classes and add explicit post-PDP binding failures: wrong proposal/PDP receipt, stale PDP decision, runtime-identity substitution, RequestedRuntimeEffect widening, authority/currentness race, aggregate-budget bypass and replay between policy decision and runtime admission.

Host-role separation and physical failure-domain independence are separate failure variables. The present architecture has four logical nodes but one observed physical domain.

Every failure fails closed or enters an explicit `PARTIAL`, `DEGRADED`, `RESTRICTED`, `FROZEN`, `UNKNOWN` or `UNRECONCILED` state. Exit code zero never substitutes for postcondition evidence.

````
LION_RECORD_END: SRC-V14C2-3bf3e923a533

<a id="src-v14c2-21599de009c9"></a>
## SRC-V14C2-21599de009c9 — v14c2/LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-21599de009c9
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=554af12bdd65b35658e1296858b9f5c8bc44e133261f3be5ed22b76c52bbd0a9
SOURCE_BYTES=1308

LION_RECORD_BEGIN: SRC-V14C2-21599de009c9
LION_RECORD_META: {"anchor":"src-v14c2-21599de009c9","archive_id":"v14c2","authority_effect":"NONE","bytes":1308,"carrier":"19_LION_HOST_FAILURES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_4_candidate.source.md","sha256":"554af12bdd65b35658e1296858b9f5c8bc44e133261f3be5ed22b76c52bbd0a9","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-21599de009c9","virtual_path":"v14c2/LION_HOST_AND_FAILURE_DOMAIN_MODEL_v1_4_candidate.source.md"}
````markdown
# LION Host and Failure Domain Model v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=OBSERVED_MODEL
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=logical host, runtime placement and physical-domain separation
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

```text
WINDOWS-MOON physical domain
├── MOON            WSL2 Ubuntu       runner not observed
├── LION-AUTH-LAB   WSL2 Debian 13    GitHub runner + rootless Docker observed
├── LAB-DEBIAN      WSL2 Debian 13
└── LAB-UBUNTU      WSL2 Ubuntu 24.04
```

```text
LOGICAL_NODES=4
OBSERVED_PHYSICAL_FAILURE_DOMAINS=1
OLD_MOON_RUNNER_CONTROL_PLANE_OVERLAP=NOT_OBSERVED
PHYSICAL_FAILURE_DOMAIN_INDEPENDENCE=FAIL
```

`LION-AUTH-LAB` is a logical authority/execution substrate, not an independent physical verifier domain. Loss of the Windows parent can still remove all observed WSL roles together.

````
LION_RECORD_END: SRC-V14C2-21599de009c9

<a id="src-v14c2-e84d4af24832"></a>
## SRC-V14C2-e84d4af24832 — v14c2/evidence/HOST_CENSUS_SUMMARY.json

SOURCE_ID=SRC-V14C2-e84d4af24832
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=evidence/HOST_CENSUS_SUMMARY.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=e3ce9bd7778dcb8ac68d239607682f151a33c0967e3cb39bf9c701067a657f3d
SOURCE_BYTES=1319

LION_RECORD_BEGIN: SRC-V14C2-e84d4af24832
LION_RECORD_META: {"anchor":"src-v14c2-e84d4af24832","archive_id":"v14c2","authority_effect":"NONE","bytes":1319,"carrier":"19_LION_HOST_FAILURES.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"evidence/HOST_CENSUS_SUMMARY.json","sha256":"e3ce9bd7778dcb8ac68d239607682f151a33c0967e3cb39bf9c701067a657f3d","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-e84d4af24832","virtual_path":"v14c2/evidence/HOST_CENSUS_SUMMARY.json"}
````json
{
  "schema_version": "lion.host-census/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "logical_node_count": 4,
  "observed_physical_failure_domain_count": 1,
  "physical_failure_domain_independence": "FAIL",
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
  ]
}

````
LION_RECORD_END: SRC-V14C2-e84d4af24832
