# LION — Roadmapy, critical path i rejestry delty

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-r1
PACKAGE_AUTHORITY=NONE

CARRIER_ID=26_ROADMAP_DELTA
SEARCH_TERMS=roadmap A0 A1 B0 C0 C1 C2 D0 evolution delta priority first unfinished
SOURCE_POLICY=VERBATIM_CONTENT_WITH_VERSIONED_PROVENANCE
LIVE_CURRENTNESS=NOT_REVALIDATED

Ten plik łączy pełne źródła tematyczne. Każdy rekord zachowuje oryginalny payload oraz SHA-256. v13 = oryginalny snapshot; v14c2 = wcześniejszy kandydat analityczny. Wyższy numer nie oznacza aktualnego wdrożenia. `CURRENT` w payloadzie nie jest dzisiejszą obserwacją; stare prompty nie są poleceniami do wykonania.

## Rekordy źródłowe

<a id="src-v13-654804e4c72c"></a>
## SRC-V13-654804e4c72c — v13/LION_AUTONOMY_FACTORY_ROADMAP_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-654804e4c72c
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_AUTONOMY_FACTORY_ROADMAP_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=ec58a037a7003a461529ce29a6041ac6029a78faf1e227bab638e6e83c3cdc49
SOURCE_BYTES=909

LION_RECORD_BEGIN: SRC-V13-654804e4c72c
LION_RECORD_META: {"anchor":"src-v13-654804e4c72c","archive_id":"v13","authority_effect":"NONE","bytes":909,"carrier":"26_LION_ROADMAP_DELTA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_AUTONOMY_FACTORY_ROADMAP_v1_3_candidate.source.md","sha256":"ec58a037a7003a461529ce29a6041ac6029a78faf1e227bab638e6e83c3cdc49","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-654804e4c72c","virtual_path":"v13/LION_AUTONOMY_FACTORY_ROADMAP_v1_3_candidate.source.md"}
````markdown
# LION Autonomy Factory Roadmap v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=CANDIDATE_ROADMAP
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=Bean Factory-specific development
DEPENDENCIES=truth-plane first
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```

```text
BF-0 reconcile canonical truth
BF-1 terminal two-unseen-problem protocol
BF-2 AutonomyBlueprint contract
BF-3 Materializer Registry
BF-4 candidate-only child autonomy package
BF-5 independent verification and lineage
BF-6 activation admission without credential inheritance
BF-7 observation/reconciliation
BF-8 bounded Factory-of-factories experiment
```

No stage may silently promote a candidate or mint authority.

````
LION_RECORD_END: SRC-V13-654804e4c72c

<a id="src-v13-5d808a855ff5"></a>
## SRC-V13-5d808a855ff5 — v13/LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md

SOURCE_ID=SRC-V13-5d808a855ff5
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=0f94b207eb817ae21a174b5966660da4760f7f7f97eb89831f59e30912fa50e6
SOURCE_BYTES=5650

LION_RECORD_BEGIN: SRC-V13-5d808a855ff5
LION_RECORD_META: {"anchor":"src-v13-5d808a855ff5","archive_id":"v13","authority_effect":"NONE","bytes":5650,"carrier":"26_LION_ROADMAP_DELTA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"markdown","original_path":"LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md","sha256":"0f94b207eb817ae21a174b5966660da4760f7f7f97eb89831f59e30912fa50e6","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-5d808a855ff5","virtual_path":"v13/LION_EVOLUTION_ROADMAP_v1_3_candidate.source.md"}
````markdown
# LION Evolution Roadmap v1.3 Candidate

```text
PACKAGE_VERSION=1.3.0-intermediate-candidate.1
PACKAGE_STATUS=CANDIDATE_ROADMAP
GENERATED_AT=2026-09-02T12:08:31Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c
BASELINE_TREE=3c9705f85301e73f268228f3c36f6ae82a641633
SCOPE=critical and parallel work
DEPENDENCIES=live blockers
SUPERSEDES=NONE_UNTIL_INTEGRATED
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
```
## A0-TRUTH-RECONCILIATION

**Objective:** Make canonical projections describe current master exactly.

**Baseline:** `2be0b312407920ac25d812f1c0bb6ecfcb31aa4c/3c9705f85301e73f268228f3c36f6ae82a641633`

**Delta:** Repair gap/registry/implementation projections; AS-IS/CANDIDATE/TARGET; currentness validator.

**Authority:** NONE; candidate-only

**Exit gate:** Truth-plane tests reject drift and contradictions.

## A1-R2E4-STACK-CLOSURE

**Objective:** Resolve PR #248/#249 state without silent promotion.

**Baseline:** `master=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c;r2e4=8bf8934a0cf2809b58b460c01976cf82ae0692e7;budget=46174de77634ce2b6d62bd6709f8ff3470d51951`

**Delta:** Exact lineage/evidence reconciliation, then authorized attach or supersession.

**Authority:** External repository effect only at exact attach

**Exit gate:** Master/post-merge CI observed.

## A1B-LAB-WSL-DOCKER-SUBSTRATE

**Objective:** Create a fourth LAB WSL2 authority node and the first reusable WSL→Docker execution-substrate pattern for later drone migration.

**Baseline:** `MOON`, `LAB-DEBIAN` and `LAB-UBUNTU` are WSL2 logical nodes under `WINDOWS-MOON`; observed `container_runtime=ABSENT`.

**Delta:** Add `LION-AUTH-LAB` as Debian 13 WSL2 with `physical_domain=WINDOWS-MOON`, systemd, SentinelX and a dedicated LAB authority-signer principal. Install and validate a native Docker Engine with an isolated daemon and rootless mode where supported. Do not use a shared Docker Desktop engine. Do not generate signing keys in this step.

**Authority:** LAB host administration; TEST_ONLY; no production authority or physical-independence claim.

**Exit gate:** `LION-AUTH-LAB` is online with exact Sentinel host identity; WSL2/systemd/cgroup-v2/native-Docker checks pass; `trust_class=TEST_ONLY`, `production_externality=NO`, `physical_independence=NO`; `LAB_AUTHORITY_KEY_GENERATED=NO`.

## A2-HOST-AUTHORITY-DEPLOYMENT

**Objective:** Remove MOON runner/control-plane principal overlap.

**Baseline:** `Live MOON census 2026-09-02`

**Delta:** Fixed-operation principal/ACL/systemd transition.

**Authority:** Privileged host mutation; human authorization

**Exit gate:** Independent post-state proves separation.

## B0-GENERATIVITY-PROTOCOL

**Objective:** Prove/falsify The Bean Factory on unseen problem classes.

**Baseline:** `2be0b312407920ac25d812f1c0bb6ecfcb31aa4c`

**Delta:** Two dissimilar evidence-bound problems; CapabilityNeed, Bean, Mosaic, candidate, verifier, no attach.

**Authority:** NONE

**Exit gate:** Terminal evidence for both or explicit falsification.

## C0-ACTION-IR

**Objective:** Define ActionSpec/LAIR beneath ActionProposal.

**Baseline:** `2be0b312407920ac25d812f1c0bb6ecfcb31aa4c`

**Delta:** Schema, canonical serialization, effect projection, negative corpus; no executor.

**Authority:** NONE

**Exit gate:** Ambiguous/injected/noncanonical input fails closed.

## C1-LCMS

**Objective:** Auditable surface syntax compiling exactly to Action IR.

**Baseline:** `C0 verified`

**Delta:** EBNF, parser, normalizer, round-trip canonicalization.

**Authority:** NONE

**Exit gate:** One semantic action has one canonical IR.

## C2-READONLY-PROCESS-EXEC

**Objective:** First capability-reduced local-console action.

**Baseline:** `C0/C1 verified; LAB-DEBIAN refreshed`

**Delta:** shell=false exact process adapter, no network, independent observer/reconciliation.

**Authority:** READ_ONLY/TEST_ONLY

**Exit gate:** Allowed command passes; write/network/injection/substitution deny.

## D0-LOCAL-MODEL-FEASIBILITY

**Objective:** Measure gpt-oss-20b proposal-only inference on observed hardware.

**Baseline:** `LAB-DEBIAN ~47 GiB RAM, no visible GPU/runtime`

**Delta:** After separate authorization, one pinned runtime/model and read-only benchmark.

**Authority:** Install/download separately authorized; inference no tools

**Exit gate:** Attestation and repeatable metrics.

## D1-HYBRID-ROUTER

**Objective:** Route local/SaaS/deterministic providers without changing authority.

**Baseline:** `C0/D0 verified`

**Delta:** Provider-independent mission route policy/comparison.

**Authority:** NONE for routing

**Exit gate:** Route substitution cannot alter capability/authority.

## A3-PHYSICAL-DOMAIN

**Objective:** Add independent physical verifier/observer domain.

**Baseline:** `One Windows domain`

**Delta:** Separate hardware/identity/power/admin and failure test.

**Authority:** Infrastructure administration

**Exit gate:** MOON loss preserves independent verification/evidence.

## E0-PHYSICAL-ACTION-SIMULATION

**Objective:** Typed physical actions without hardware effects.

**Baseline:** `C0 verified; no robotics runtime`

**Delta:** PhysicalActionSpec, typed authority, safety preconditions, digital-twin-only provider.

**Authority:** NONE/SIMULATION_ONLY

**Exit gate:** Unit/frame/calibration/safety substitutions fail closed.

## P0-SHADOW-PREPRODUCTION

**Objective:** Real workloads without consequential attachment.

**Baseline:** `Critical blockers closed`

**Delta:** Shadow missions, recovery drills, release candidate.

**Authority:** No production attach

**Exit gate:** Independent-domain entry criteria satisfied.

````
LION_RECORD_END: SRC-V13-5d808a855ff5

<a id="src-v13-ac46bae0ab49"></a>
## SRC-V13-ac46bae0ab49 — v13/LION_POST_V1_2_DELTA_REGISTER_v1_3_candidate.source.json

SOURCE_ID=SRC-V13-ac46bae0ab49
SOURCE_ARCHIVE=v13
SOURCE_PATH=LION_POST_V1_2_DELTA_REGISTER_v1_3_candidate.source.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=db5022d74dbdc79e0630e77e967d5801c9f2286fa14627ace779dd596651bcd3
SOURCE_BYTES=7068

LION_RECORD_BEGIN: SRC-V13-ac46bae0ab49
LION_RECORD_META: {"anchor":"src-v13-ac46bae0ab49","archive_id":"v13","authority_effect":"NONE","bytes":7068,"carrier":"26_LION_ROADMAP_DELTA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"LION_POST_V1_2_DELTA_REGISTER_v1_3_candidate.source.json","sha256":"db5022d74dbdc79e0630e77e967d5801c9f2286fa14627ace779dd596651bcd3","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-ac46bae0ab49","virtual_path":"v13/LION_POST_V1_2_DELTA_REGISTER_v1_3_candidate.source.json"}
````json
{
  "entries": [
    {
      "authority_effect": "NONE",
      "consequence": "The Bean Factory now has a typed capability-unit and runtime-instance substrate.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "cyber_lion/contracts/bean.py",
        "Cyber-Lion Core@master"
      ],
      "first_observed_commit": "cc1092f2565059294963aa89595ebe4d0ea37c44",
      "id": "DELTA-V13-001",
      "name": "Canonical BeanSpec and BeanInstance",
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "Generated implementations are separated from specs, grants and activation.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "cyber_lion/contracts/bean_candidate.py",
        "cyber_lion/tests/test_bean_candidate.py"
      ],
      "first_observed_commit": "post-v1.2 integrated lineage",
      "id": "DELTA-V13-002",
      "name": "BeanCandidate exact non-authoritative binding",
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "Minimal admissible heterogeneous compositions can be selected under hard constraints.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "cyber_lion/contracts/bean_composition.py",
        "cyber_lion/enterprise/bean_composition.py"
      ],
      "first_observed_commit": "706bd702ea89f9031ca8d92deb275a3ef408db80",
      "id": "DELTA-V13-003",
      "name": "Deterministic CompositionContract and CompositionEngine",
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "A declared gap can lead to reuse or a candidate BeanSpec without build authority.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "cyber_lion/contracts/capability_need.py",
        "cyber_lion/enterprise/capability_need.py"
      ],
      "first_observed_commit": "f292983e25bb9c07bd3adfaed48368ad65a3e4ec",
      "id": "DELTA-V13-004",
      "name": "Gap-derived CapabilityNeed and BeanSpec generation",
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "Non-agent Beans remain first-class organizational members with staged evidence.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "cyber_lion/contracts/mosaic.py",
        "cyber_lion/enterprise/mosaic.py",
        "cyber_lion/tests/test_dynamic_mosaic.py"
      ],
      "first_observed_commit": "post-v1.2 integrated lineage",
      "id": "DELTA-V13-005",
      "name": "Heterogeneous Mosaic lifecycle",
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "BeanSpec can bind to an externally issued detached builder permit.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "cyber_lion/contracts/bean_builder_bridge.py"
      ],
      "first_observed_commit": "5ad65276f70cd25335d0e20042afa1358b73ac28",
      "id": "DELTA-V13-006",
      "name": "Bean-to-existing-builder-chain bridge",
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE_BY_CANDIDATE_CONSTRUCTION",
      "consequence": "Production entry is a separate sector; live MOON still violates intended principal separation.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "PR#233",
        "PR#234",
        "docs/architecture/production-entry/README.md",
        "live MOON census"
      ],
      "first_observed_commit": "e091cf86cc297df92c8c82a2e877ddbf4c81ff6d",
      "id": "DELTA-V13-007",
      "name": "Authority provisioning, host-separation target and production-entry lifecycle",
      "state": "INTEGRATED_CODE_NOT_FULLY_DEPLOYED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "Exact multi-repository head/tree observations exist without UNKNOWN-to-PASS promotion.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "PR#245"
      ],
      "first_observed_commit": "dcf2c7589219220d3f4e5ab570fdaa5f785d9afd",
      "id": "DELTA-V13-008",
      "name": "R2E1 fleet repository baseline contract",
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "Registry pins can be materialized without health or authority promotion.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "PR#246"
      ],
      "first_observed_commit": "7689aec0dcf4d8cee41dedefe5bd58cafa43e210",
      "id": "DELTA-V13-009",
      "name": "R2E2 fleet registry pin materializer",
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "Exact live GitHub reads and a second drift sweep bind repository observations.",
      "current_commit": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "evidence": [
        "PR#247",
        "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c"
      ],
      "first_observed_commit": "ca7d36e8c1f3af8547839969b90ccf544c3efcf9",
      "id": "DELTA-V13-010",
      "name": "R2E3 live GitHub fleet pin source binding",
      "state": "INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "Candidate and synthetic execution carrier identity are explicitly bound; outside master.",
      "current_commit": "8bf8934a0cf2809b58b460c01976cf82ae0692e7",
      "current_tree": "eee3ea5f4f0a116e0f5409b6885a4fb0a5f691d1",
      "evidence": [
        "PR#248",
        "12 exact-head successful workflow runs"
      ],
      "first_observed_commit": "8bf8934a0cf2809b58b460c01976cf82ae0692e7",
      "id": "DELTA-V13-011",
      "name": "R2E4 exact-head semantic evidence binding",
      "state": "VERIFIED_CANDIDATE_NOT_INTEGRATED"
    },
    {
      "authority_effect": "RESTRICT_ONLY",
      "consequence": "Cross-runtime reservations can restrict aggregate effects before local preparation.",
      "current_commit": "46174de77634ce2b6d62bd6709f8ff3470d51951",
      "current_tree": "a2c2ca9594dd30174e0892f48464678da27e1bf2",
      "evidence": [
        "PR#249",
        "7 exact-head successful workflow runs"
      ],
      "first_observed_commit": "46174de77634ce2b6d62bd6709f8ff3470d51951",
      "id": "DELTA-V13-012",
      "name": "Fleet Aggregate Effect Budget",
      "state": "VERIFIED_STACKED_CANDIDATE_NOT_INTEGRATED"
    },
    {
      "authority_effect": "NONE",
      "consequence": "Provider-independent route from reasoning to typed, deterministically mediated effects.",
      "current_commit": "NOT_APPLICABLE",
      "evidence": [
        "THE BEAN FACTORY / LION EVOLUTION master prompt"
      ],
      "first_observed_commit": "NOT_APPLICABLE",
      "id": "DELTA-V13-013",
      "name": "Typed Action/Command and local-model architecture proposal",
      "state": "PROJECT_RESEARCH_TARGET"
    }
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "schema_version": "lion.post-v1.2-delta-register/v1.3-candidate"
}

````
LION_RECORD_END: SRC-V13-ac46bae0ab49

<a id="src-v13-72b2535ba5d7"></a>
## SRC-V13-72b2535ba5d7 — v13/ROADMAP.json

SOURCE_ID=SRC-V13-72b2535ba5d7
SOURCE_ARCHIVE=v13
SOURCE_PATH=ROADMAP.json
SOURCE_CLASS=ORIGINAL_SOURCE_SNAPSHOT
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=cc5a6bcc67d2158d7ca5007c9ede8d91e20332e740dc3a47f53d7ff60d69166d
SOURCE_BYTES=6901

LION_RECORD_BEGIN: SRC-V13-72b2535ba5d7
LION_RECORD_META: {"anchor":"src-v13-72b2535ba5d7","archive_id":"v13","authority_effect":"NONE","bytes":6901,"carrier":"26_LION_ROADMAP_DELTA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-02T12:08:31Z","declared_package_version":"1.3.0-intermediate-candidate.1","language":"json","original_path":"ROADMAP.json","sha256":"cc5a6bcc67d2158d7ca5007c9ede8d91e20332e740dc3a47f53d7ff60d69166d","source_class":"ORIGINAL_SOURCE_SNAPSHOT","source_id":"SRC-V13-72b2535ba5d7","virtual_path":"v13/ROADMAP.json"}
````json
{
  "critical_path": [
    "A0-TRUTH-RECONCILIATION",
    "A1-R2E4-STACK-CLOSURE",
    "A1B-LAB-WSL-DOCKER-SUBSTRATE",
    "A2-HOST-AUTHORITY-DEPLOYMENT",
    "B0-GENERATIVITY-PROTOCOL",
    "C0-ACTION-IR",
    "C1-LCMS",
    "C2-READONLY-PROCESS-EXEC",
    "D0-LOCAL-MODEL-FEASIBILITY",
    "D1-HYBRID-ROUTER",
    "A3-PHYSICAL-DOMAIN",
    "E0-PHYSICAL-ACTION-SIMULATION",
    "P0-SHADOW-PREPRODUCTION"
  ],
  "generated_at": "2026-09-02T12:08:31Z",
  "schema_version": "lion.evolution-roadmap/v1.3-candidate",
  "steps": [
    {
      "authority": "NONE; candidate-only",
      "baseline": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c/3c9705f85301e73f268228f3c36f6ae82a641633",
      "delta": "Repair gap/registry/implementation projections; AS-IS/CANDIDATE/TARGET; currentness validator.",
      "exit": "Truth-plane tests reject drift and contradictions.",
      "objective": "Make canonical projections describe current master exactly.",
      "priority": 1,
      "step": "A0-TRUTH-RECONCILIATION",
      "track": "A"
    },
    {
      "authority": "External repository effect only at exact attach",
      "baseline": "master=2be0b312407920ac25d812f1c0bb6ecfcb31aa4c;r2e4=8bf8934a0cf2809b58b460c01976cf82ae0692e7;budget=46174de77634ce2b6d62bd6709f8ff3470d51951",
      "delta": "Exact lineage/evidence reconciliation, then authorized attach or supersession.",
      "exit": "Master/post-merge CI observed.",
      "objective": "Resolve PR #248/#249 state without silent promotion.",
      "priority": 2,
      "step": "A1-R2E4-STACK-CLOSURE",
      "track": "A/Fleet"
    },
    {
      "authority": "LAB host administration; TEST_ONLY; no production authority or physical-independence claim",
      "baseline": "Current LAB: MOON/LAB-DEBIAN/LAB-UBUNTU are WSL2 under WINDOWS-MOON; container_runtime=ABSENT",
      "delta": "Add LION-AUTH-LAB as Debian 13 WSL2 logical node in physical_domain=WINDOWS-MOON; enable systemd and SentinelX; establish dedicated LAB authority-signer principal; install/validate native Docker Engine with isolated daemon and rootless mode where supported; Docker Desktop shared engine forbidden; no signing key generation in this step.",
      "exit": "LION-AUTH-LAB online with exact Sentinel host identity; WSL2/systemd/cgroup-v2/native-Docker checks pass; trust_class=TEST_ONLY, production_externality=NO and physical_independence=NO remain explicit; LAB authority key generated=NO.",
      "objective": "Create a fourth LAB WSL2 authority node and the first reusable WSL→Docker execution-substrate pattern for later drone migration.",
      "priority": 3,
      "step": "A1B-LAB-WSL-DOCKER-SUBSTRATE",
      "track": "A/Infra-Lab"
    },
    {
      "authority": "Privileged host mutation; human authorization",
      "baseline": "Live MOON census 2026-09-02",
      "delta": "Fixed-operation principal/ACL/systemd transition.",
      "exit": "Independent post-state proves separation.",
      "objective": "Remove MOON runner/control-plane principal overlap.",
      "priority": 4,
      "step": "A2-HOST-AUTHORITY-DEPLOYMENT",
      "track": "A"
    },
    {
      "authority": "NONE",
      "baseline": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "delta": "Two dissimilar evidence-bound problems; CapabilityNeed, Bean, Mosaic, candidate, verifier, no attach.",
      "exit": "Terminal evidence for both or explicit falsification.",
      "objective": "Prove/falsify The Bean Factory on unseen problem classes.",
      "priority": 5,
      "step": "B0-GENERATIVITY-PROTOCOL",
      "track": "B"
    },
    {
      "authority": "NONE",
      "baseline": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
      "delta": "Schema, canonical serialization, effect projection, negative corpus; no executor.",
      "exit": "Ambiguous/injected/noncanonical input fails closed.",
      "objective": "Define ActionSpec/LAIR beneath ActionProposal.",
      "priority": 6,
      "step": "C0-ACTION-IR",
      "track": "C"
    },
    {
      "authority": "NONE",
      "baseline": "C0 verified",
      "delta": "EBNF, parser, normalizer, round-trip canonicalization.",
      "exit": "One semantic action has one canonical IR.",
      "objective": "Auditable surface syntax compiling exactly to Action IR.",
      "priority": 7,
      "step": "C1-LCMS",
      "track": "C"
    },
    {
      "authority": "READ_ONLY/TEST_ONLY",
      "baseline": "C0/C1 verified; LAB-DEBIAN refreshed",
      "delta": "shell=false exact process adapter, no network, independent observer/reconciliation.",
      "exit": "Allowed command passes; write/network/injection/substitution deny.",
      "objective": "First capability-reduced local-console action.",
      "priority": 8,
      "step": "C2-READONLY-PROCESS-EXEC",
      "track": "C"
    },
    {
      "authority": "Install/download separately authorized; inference no tools",
      "baseline": "LAB-DEBIAN ~47 GiB RAM, no visible GPU/runtime",
      "delta": "After separate authorization, one pinned runtime/model and read-only benchmark.",
      "exit": "Attestation and repeatable metrics.",
      "objective": "Measure gpt-oss-20b proposal-only inference on observed hardware.",
      "priority": 9,
      "step": "D0-LOCAL-MODEL-FEASIBILITY",
      "track": "D"
    },
    {
      "authority": "NONE for routing",
      "baseline": "C0/D0 verified",
      "delta": "Provider-independent mission route policy/comparison.",
      "exit": "Route substitution cannot alter capability/authority.",
      "objective": "Route local/SaaS/deterministic providers without changing authority.",
      "priority": 10,
      "step": "D1-HYBRID-ROUTER",
      "track": "D"
    },
    {
      "authority": "Infrastructure administration",
      "baseline": "One Windows domain",
      "delta": "Separate hardware/identity/power/admin and failure test.",
      "exit": "MOON loss preserves independent verification/evidence.",
      "objective": "Add independent physical verifier/observer domain.",
      "priority": 11,
      "step": "A3-PHYSICAL-DOMAIN",
      "track": "A/Infra"
    },
    {
      "authority": "NONE/SIMULATION_ONLY",
      "baseline": "C0 verified; no robotics runtime",
      "delta": "PhysicalActionSpec, typed authority, safety preconditions, digital-twin-only provider.",
      "exit": "Unit/frame/calibration/safety substitutions fail closed.",
      "objective": "Typed physical actions without hardware effects.",
      "priority": 12,
      "step": "E0-PHYSICAL-ACTION-SIMULATION",
      "track": "E"
    },
    {
      "authority": "No production attach",
      "baseline": "Critical blockers closed",
      "delta": "Shadow missions, recovery drills, release candidate.",
      "exit": "Independent-domain entry criteria satisfied.",
      "objective": "Real workloads without consequential attachment.",
      "priority": 13,
      "step": "P0-SHADOW-PREPRODUCTION",
      "track": "Pre-production"
    }
  ]
}

````
LION_RECORD_END: SRC-V13-72b2535ba5d7

<a id="src-v14c2-2918893eeac8"></a>
## SRC-V14C2-2918893eeac8 — v14c2/LION_AUTONOMY_FACTORY_ROADMAP_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-2918893eeac8
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_AUTONOMY_FACTORY_ROADMAP_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=fd65ce727311569f636a5f34d74cb26632a92f8e282279890975fe88c3c93010
SOURCE_BYTES=1422

LION_RECORD_BEGIN: SRC-V14C2-2918893eeac8
LION_RECORD_META: {"anchor":"src-v14c2-2918893eeac8","archive_id":"v14c2","authority_effect":"NONE","bytes":1422,"carrier":"26_LION_ROADMAP_DELTA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_AUTONOMY_FACTORY_ROADMAP_v1_4_candidate.source.md","sha256":"fd65ce727311569f636a5f34d74cb26632a92f8e282279890975fe88c3c93010","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-2918893eeac8","virtual_path":"v14c2/LION_AUTONOMY_FACTORY_ROADMAP_v1_4_candidate.source.md"}
````markdown
# LION Autonomy Factory Roadmap v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=CANDIDATE_ROADMAP
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=Bean Factory development after B0
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

```text
BF-0 canonical truth reconciliation                 = SUBSTANTIALLY INTEGRATED
BF-1 bounded two-unseen-family terminal protocol    = PASS
BF-1G general/domain-independent generativity       = NOT_PROVEN
BF-2 canonical AutonomyBlueprint                    = TARGET
BF-3 domain-independent Materializer Registry        = TARGET
BF-4 candidate-only child autonomy package          = TARGET
BF-5 independent verification + lineage             = TARGET
BF-6 activation admission without credential inheritance = TARGET
BF-7 observation/reconciliation                     = TARGET
BF-8 bounded Factory-of-factories experiment         = NOT_ATTEMPTED
```

No later BF stage may bypass the canonical PDP/runtime-admission boundary or widen inherited authority.

````
LION_RECORD_END: SRC-V14C2-2918893eeac8

<a id="src-v14c2-178aeb549332"></a>
## SRC-V14C2-178aeb549332 — v14c2/LION_EVOLUTION_ROADMAP_v1_4_candidate.source.md

SOURCE_ID=SRC-V14C2-178aeb549332
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_EVOLUTION_ROADMAP_v1_4_candidate.source.md
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=38db7b9d40af2ddb8a0d4ff9923deebf3e04e66de1e4ef9228886fd5acc53e21
SOURCE_BYTES=1575

LION_RECORD_BEGIN: SRC-V14C2-178aeb549332
LION_RECORD_META: {"anchor":"src-v14c2-178aeb549332","archive_id":"v14c2","authority_effect":"NONE","bytes":1575,"carrier":"26_LION_ROADMAP_DELTA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"markdown","original_path":"LION_EVOLUTION_ROADMAP_v1_4_candidate.source.md","sha256":"38db7b9d40af2ddb8a0d4ff9923deebf3e04e66de1e4ef9228886fd5acc53e21","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-178aeb549332","virtual_path":"v14c2/LION_EVOLUTION_ROADMAP_v1_4_candidate.source.md"}
````markdown
# LION Evolution Roadmap v1.4 Candidate

```text
PACKAGE_VERSION=1.4.0-candidate.2
PACKAGE_STATUS=CANDIDATE_ROADMAP
GENERATED_AT=2026-09-07T15:25:55Z
BASELINE_REPOSITORY=DonkeyJJLove/ai_platform
BASELINE_HEAD=5d5a02b37fdfff4bcbf62f455d37ce4b86080f59
BASELINE_TREE=9725bebf8d9766c58096cfc34af06ffcb8aa32f1
TRUTH_SUBJECT_DIGEST=d0efd373568ce9608303d4d2a743dfb7099d18d57e32003b4c92c56fd5b0b726
SCOPE=post-R19P evolution sequence
DEPENDENCIES=current master + supplied v1.3 corpus
SUPERSEDES_PACKAGE_ANALYSIS=1.3.0-intermediate-candidate.1
REPOSITORY_SUPERSESSION_EFFECT=NONE
CURRENTNESS_RULE=STALE_ON_MATERIAL_BASELINE_DRIFT
AUTHORITY_EFFECT=NONE
```

## Completed/superseded v1.3 frontier

A0 truth reconciliation is materially integrated; R2E4 and aggregate budget are integrated; `LION-AUTH-LAB` exists as logical WSL/Docker substrate; the old MOON runner group-overlap is no longer observed; the bounded B0 terminal protocol passes; ActionSpec, LAIR, static projection, explicit ActionProposal context and canonical PDP handoff are integrated.

## Current critical path

```text
R20 PDPResult→RequestedRuntimeEffect/runtime identity admission binding
→ C1 LCMS current-master reconstruction
→ C2 read-only process adapter reconstruction
→ BF-1G general generativity research
→ BF-2 AutonomyBlueprint
→ BF-3 Materializer Registry
→ D0 local model feasibility/attestation
→ A3 independent physical domain
→ M0 global complete-mediation proof
→ E0 physical simulation
→ P0 shadow pre-production
```

The detailed machine-readable state is `ROADMAP.json`.

````
LION_RECORD_END: SRC-V14C2-178aeb549332

<a id="src-v14c2-49ce04ba9d8d"></a>
## SRC-V14C2-49ce04ba9d8d — v14c2/LION_POST_V1_3_DELTA_REGISTER_v1_4_candidate.source.json

SOURCE_ID=SRC-V14C2-49ce04ba9d8d
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=LION_POST_V1_3_DELTA_REGISTER_v1_4_candidate.source.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=4f1239cf494447b3efb6302202e82645e9b486fc7a1e8796eed58561d0f09695
SOURCE_BYTES=3612

LION_RECORD_BEGIN: SRC-V14C2-49ce04ba9d8d
LION_RECORD_META: {"anchor":"src-v14c2-49ce04ba9d8d","archive_id":"v14c2","authority_effect":"NONE","bytes":3612,"carrier":"26_LION_ROADMAP_DELTA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"LION_POST_V1_3_DELTA_REGISTER_v1_4_candidate.source.json","sha256":"4f1239cf494447b3efb6302202e82645e9b486fc7a1e8796eed58561d0f09695","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-49ce04ba9d8d","virtual_path":"v14c2/LION_POST_V1_3_DELTA_REGISTER_v1_4_candidate.source.json"}
````json
{
  "schema_version": "lion.post-v1.3-delta-register/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "baseline_v1_3": {
    "head": "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c",
    "repository": "DonkeyJJLove/ai_platform",
    "tree": "3c9705f85301e73f268228f3c36f6ae82a641633"
  },
  "baseline_v1_4": {
    "repository": "DonkeyJJLove/ai_platform",
    "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
    "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1"
  },
  "entries": [
    {
      "id": "DELTA-V14-001",
      "delta": "R2E4 exact semantic/evidence binding integrated",
      "old_state": "VERIFIED_CANDIDATE",
      "new_state": "AS_IS_INTEGRATED",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-002",
      "delta": "Fleet Aggregate Effect Budget integrated",
      "old_state": "VERIFIED_STACKED_CANDIDATE",
      "new_state": "AS_IS_INTEGRATED",
      "authority_effect": "RESTRICT_ONLY"
    },
    {
      "id": "DELTA-V14-003",
      "delta": "truth-subject derived currentness protocol integrated",
      "old_state": "truth drift blocker",
      "new_state": "AS_IS_WITH_REMAINING_PROJECTION_DRIFT",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-004",
      "delta": "B0 bounded terminal two-family generativity protocol integrated/passing",
      "old_state": "NOT_PROVEN_NOT_ATTEMPTED",
      "new_state": "BOUNDED_PROTOCOL_PASS",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-005",
      "delta": "ActionSpec canonical contract integrated",
      "old_state": "TARGET/CANDIDATE",
      "new_state": "AS_IS",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-006",
      "delta": "CanonicalActionIR/LAIR integrated",
      "old_state": "TARGET",
      "new_state": "AS_IS",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-007",
      "delta": "Static ActionProposal projection integrated",
      "old_state": "TARGET",
      "new_state": "AS_IS_NON_EFFECTFUL",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-008",
      "delta": "Explicit ActionProposal context binder integrated",
      "old_state": "TARGET",
      "new_state": "AS_IS_NON_EFFECTFUL",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-009",
      "delta": "Canonical ActionProposal→PDP handoff integrated",
      "old_state": "NEXT_GAP",
      "new_state": "AS_IS_NON_EFFECTFUL",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-010",
      "delta": "Action frontier moved downstream",
      "old_state": "ActionProposal→PDP",
      "new_state": "PDPResult(ALLOW)→RequestedRuntimeEffect/runtime identity→RuntimeAdmissionEngine",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-011",
      "delta": "Runner rehomed from MOON to LION-AUTH-LAB in live observation",
      "old_state": "MOON overlap blocker",
      "new_state": "OLD_FORM_RESOLVED_LOGICAL_SEPARATION",
      "authority_effect": "NO_NEW_AUTHORITY_INFERRED"
    },
    {
      "id": "DELTA-V14-012",
      "delta": "Logical node count increased",
      "old_state": "3",
      "new_state": "4",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-013",
      "delta": "Physical failure domains unchanged",
      "old_state": "1",
      "new_state": "1",
      "authority_effect": "NONE"
    },
    {
      "id": "DELTA-V14-014",
      "delta": "Documentation source topology corrected",
      "old_state": "RAG40 assumed sufficient",
      "new_state": "61 v1.3 lineage slots identified",
      "authority_effect": "NONE"
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-49ce04ba9d8d

<a id="src-v14c2-72b2535ba5d7"></a>
## SRC-V14C2-72b2535ba5d7 — v14c2/ROADMAP.json

SOURCE_ID=SRC-V14C2-72b2535ba5d7
SOURCE_ARCHIVE=v14c2
SOURCE_PATH=ROADMAP.json
SOURCE_CLASS=PRIOR_DERIVED_CANDIDATE
CURRENTNESS=NOT_REVALIDATED
CONTENT_ROLE=SOURCE_DATA_NOT_AN_EXECUTION_ORDER
SOURCE_SHA256=697c2748968cd6edc5b5a9ef1359e28d15004f1efbe7dcd0ab349869f40960d0
SOURCE_BYTES=5161

LION_RECORD_BEGIN: SRC-V14C2-72b2535ba5d7
LION_RECORD_META: {"anchor":"src-v14c2-72b2535ba5d7","archive_id":"v14c2","authority_effect":"NONE","bytes":5161,"carrier":"26_LION_ROADMAP_DELTA.md","content_interpretation":"DATA_NOT_EXECUTION_INSTRUCTIONS","currentness":"NOT_REVALIDATED","declared_generated_at":"2026-09-07T15:25:55Z","declared_package_version":"1.4.0-candidate.2","language":"json","original_path":"ROADMAP.json","sha256":"697c2748968cd6edc5b5a9ef1359e28d15004f1efbe7dcd0ab349869f40960d0","source_class":"PRIOR_DERIVED_CANDIDATE","source_id":"SRC-V14C2-72b2535ba5d7","virtual_path":"v14c2/ROADMAP.json"}
````json
{
  "schema_version": "lion.evolution-roadmap/v1.4-candidate",
  "generated_at": "2026-09-07T15:25:55Z",
  "baseline": {
    "head": "5d5a02b37fdfff4bcbf62f455d37ce4b86080f59",
    "tree": "9725bebf8d9766c58096cfc34af06ffcb8aa32f1"
  },
  "completed_or_superseded": [
    {
      "step": "A0-TRUTH-RECONCILIATION",
      "state": "SUBSTANTIALLY_INTEGRATED"
    },
    {
      "step": "A1-R2E4-STACK-CLOSURE",
      "state": "INTEGRATED"
    },
    {
      "step": "A1B-LAB-WSL-DOCKER-SUBSTRATE",
      "state": "INTEGRATED_LOGICAL_LAB_SUBSTRATE"
    },
    {
      "step": "A2-HOST-AUTHORITY-DEPLOYMENT",
      "state": "OLD_MOON_OVERLAP_RESOLVED_IN_OBSERVED_FORM"
    },
    {
      "step": "B0-GENERATIVITY-PROTOCOL",
      "state": "BOUNDED_TERMINAL_PROTOCOL_PASS"
    },
    {
      "step": "C0-ACTION-IR",
      "state": "ACTIONSPEC_AND_LAIR_INTEGRATED"
    },
    {
      "step": "R19M-STATIC-PROJECTION",
      "state": "INTEGRATED"
    },
    {
      "step": "R19O-EXPLICIT-ACTIONPROPOSAL-CONTEXT",
      "state": "INTEGRATED"
    },
    {
      "step": "R19P-ACTIONPROPOSAL-PDP-HANDOFF",
      "state": "INTEGRATED"
    }
  ],
  "critical_path": [
    "R20-RUNTIME-ADMISSION-BINDING",
    "C1-LCMS-RECONSTRUCTION",
    "C2-READONLY-PROCESS-EXEC-RECONSTRUCTION",
    "BF-1G-GENERAL-GENERATIVITY",
    "BF-2-AUTONOMY-BLUEPRINT",
    "BF-3-MATERIALIZER-REGISTRY",
    "D0-LOCAL-MODEL-FEASIBILITY",
    "A3-PHYSICAL-DOMAIN",
    "M0-GLOBAL-COMPLETE-MEDIATION",
    "E0-PHYSICAL-ACTION-SIMULATION",
    "P0-SHADOW-PREPRODUCTION"
  ],
  "steps": [
    {
      "priority": 1,
      "step": "R20-RUNTIME-ADMISSION-BINDING",
      "track": "C/A",
      "state": "NEXT",
      "objective": "Bind canonical PDP ALLOW result to exact RequestedRuntimeEffect and runtime identity before RuntimeAdmissionEngine.",
      "authority": "NONE; contract/candidate only",
      "exit": "identity/currentness/replay/widening tests fail closed; no effect provider added"
    },
    {
      "priority": 2,
      "step": "C1-LCMS-RECONSTRUCTION",
      "track": "C",
      "state": "STALE_CANDIDATE_REBUILD",
      "objective": "Rebuild LCMS on current canonical ActionSpec/LAIR and post-PDP boundary.",
      "authority": "NONE",
      "exit": "one semantic command -> one canonical IR; no execution"
    },
    {
      "priority": 3,
      "step": "C2-READONLY-PROCESS-EXEC-RECONSTRUCTION",
      "track": "C",
      "state": "STALE_CANDIDATE_REBUILD",
      "objective": "Rebuild bounded read-only process adapter only after current runtime admission.",
      "authority": "READ_ONLY_TEST_ONLY if separately granted",
      "exit": "write/network/shell/substitution/currentness deny"
    },
    {
      "priority": 4,
      "step": "BF-1G-GENERAL-GENERATIVITY",
      "track": "B",
      "state": "RESEARCH",
      "objective": "Extend beyond bounded B0 protocol without problem-specific workflow growth.",
      "authority": "NONE",
      "exit": "predeclared cross-domain generalization criterion"
    },
    {
      "priority": 5,
      "step": "BF-2-AUTONOMY-BLUEPRINT",
      "track": "B",
      "state": "TARGET",
      "objective": "Integrate digest-bound non-authoritative AutonomyBlueprint.",
      "authority": "NONE",
      "exit": "canonical contract + falsification"
    },
    {
      "priority": 6,
      "step": "BF-3-MATERIALIZER-REGISTRY",
      "track": "B",
      "state": "TARGET",
      "objective": "Define domain-independent materializer registry.",
      "authority": "NONE",
      "exit": "typed representation/materializer/validator/verifier/observer contracts"
    },
    {
      "priority": 7,
      "step": "D0-LOCAL-MODEL-FEASIBILITY",
      "track": "D",
      "state": "TARGET",
      "objective": "Fresh proposal-only local model feasibility and attestation.",
      "authority": "LAB install/execution only if explicitly granted",
      "exit": "repeatable resource/failure evidence"
    },
    {
      "priority": 8,
      "step": "A3-PHYSICAL-DOMAIN",
      "track": "A/Infra",
      "state": "BLOCKED",
      "objective": "Add independent physical verifier/observer domain.",
      "authority": "external physical infrastructure",
      "exit": "loss of WINDOWS-MOON preserves independent verification/evidence"
    },
    {
      "priority": 9,
      "step": "M0-GLOBAL-COMPLETE-MEDIATION",
      "track": "A/Security",
      "state": "UNKNOWN",
      "objective": "Classify all reachable consequential surfaces.",
      "authority": "READ_ONLY_FIRST",
      "exit": "no unclassified consequential surface and bypass requirements satisfied"
    },
    {
      "priority": 10,
      "step": "E0-PHYSICAL-ACTION-SIMULATION",
      "track": "E",
      "state": "TARGET",
      "objective": "Simulation-only typed physical actions.",
      "authority": "NONE physical",
      "exit": "unit/frame/calibration/safety substitutions fail closed"
    },
    {
      "priority": 11,
      "step": "P0-SHADOW-PREPRODUCTION",
      "track": "P",
      "state": "BLOCKED",
      "objective": "Shadow real workloads without consequential attachment.",
      "authority": "separate",
      "exit": "all preproduction entry criteria pass"
    }
  ]
}

````
LION_RECORD_END: SRC-V14C2-72b2535ba5d7
