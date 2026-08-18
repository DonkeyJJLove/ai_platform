# CYBER-LION — Migration Map

The migration is incremental and compatibility-first.

```text
CURRENT
→ COMPATIBILITY
→ MIGRATION
→ TARGET
```

No phase may delete a working legacy path before its replacement has contract tests, observability and rollback evidence.

## Phase 0 — Repository archaeology — COMPLETE FOR BASELINE

Deliverables in this branch:

- repository inventory;
- capability map;
- target architecture;
- contract map;
- event/data model;
- scientific status;
- migration order.

Existing process-upgrade PRs are treated as pending dependencies rather than silently duplicated.

## Phase 1 — Repository hygiene / compatibility baseline

Before federation, merge or supersede current hardening PRs where valid:

- `ai_platform` process-upgrade PR: canonical README, source purity;
- `chunk-chunk` PRs: remove tracked virtualenv; sanitize/redact run IDs;
- `glitchlab` process-upgrade PR: generated/local state cleanup and CI ratchet;
- `HA2D` process-upgrade PR: persistent-context guard;
- `hipotezy_nadawcze_LLM` process-upgrade PR: falsification contract.

For other providers, create equivalent source-purity and regression checks only where repository archaeology confirms the need.

**Exit criteria**

```text
source tree != local runtime state
canonical repository entrypoint documented
CI/test status known
no new Cyber-Lion integration built on hidden local artifacts
```

## Phase 2 — Shared Entity Identity

Owner: `ai_platform`  
Compatibility anchor: `sbom/AID`

Add versioned Entity Identity schema and adapter from AID.

Do **not** replace AID fields. Prove round-trip compatibility:

```text
AID event
→ Entity Envelope adapter
→ Cyber-Lion event
→ extract original AID
== original AID
```

**Tests**

- schema validation;
- stable identity vs version/ref distinction;
- invalid/unknown owner handling;
- AID round trip;
- no network address treated as identity.

## Phase 3 — Shared Event Schema

Owner: `ai_platform`.

Implement versioned event envelope and typed event names. Create adapters first for:

1. SBOM events;
2. GlitchLab delta/BUS events;
3. Swarm telemetry;
4. simulator result events.

**Exit criteria**

- shared correlation ID traverses at least two repositories;
- upstream provenance is preserved;
- consumer rejects incompatible major schema version.

## Phase 4 — Capability Registry

Owner: `ai_platform`.

Build manifest discovery. A provider registers:

- capability id/version;
- input/output schemas;
- side effects;
- authority requirements;
- event production;
- provider entity/version.

Do not reuse GlitchLab's local filter registry as global state. Add an adapter only if useful.

**First provider manifests**

- GlitchLab AST/delta/graph analysis;
- Mosaic Lab structure abstraction;
- Cascade simulation;
- SBOM observation/gate evidence;
- Swarm telemetry/execution.

## Phase 5 — QV9D / Mosaic Registry Refresh

Replace the stale static repository list with generated manifests while preserving QV9D annotations.

```text
GitHub/repository manifest
→ deterministic physical inventory
→ semantic QV9D annotation
→ validation against actual repository/ref
```

QV9D is metadata/coordinate space. It must not create authority.

## Phase 6 — Provenance + LBOM / Decision BOM

Generalize provenance from supply-chain evidence to decision inputs.

Initial Decision BOM records:

- model/provider version;
- context item refs;
- evidence refs;
- prompt/instruction refs where available;
- memory refs;
- policies;
- capability/tool versions;
- gate event;
- transformation chain.

Start with metadata references/hashes, not wholesale payload duplication.

## Phase 7 — Global Graph State

Owner: `ai_platform` contract/service.

Start as an append-derived projection from typed events. Do not make the graph the system of record for provider-local state.

Graph must distinguish:

```text
supports / contradicts
from
caused / authorized
```

## Phase 8 — Policy / Gate / Authority Engine

Owner: `ai_platform` shared decision interface. Enforcement remains federated.

Adapters:

- SBOM gate evidence;
- GlitchLab Guard/invariants;
- Kubernetes RBAC/workload authorization;
- human approval.

Required invariant:

```text
consequential ActionExecuted
⇒ GateApplied reference
```

## Phase 9 — Agent Execution Mesh

Owner: `swarm` as execution provider.

Migration path:

```text
current domain JSON/API
→ event-envelope adapter
→ workload/entity identity
→ deterministic ExecutionContract consumer
→ receipt emitter
→ sandbox/tool-worker extraction
```

Review existing RBAC against actual service behavior. Remove authority that has no documented consumer.

## Phase 10 — Cognitive State / Memory

Owner semantics: `HA2D`; common contract: `ai_platform`.

First implement types and policy, then storage.

```text
WORKING
EPISODIC
SEMANTIC
PROCEDURAL
POLICY
EVIDENCE
QUARANTINE
```

Untrusted input may become `MemoryCandidateCreated`; persistent commit requires policy/gate.

## Phase 11 — Hypothesis Engine

Use machine-readable hypothesis/evidence records. `hipotezy_nadawcze_LLM` becomes one provider of records; it does not become a privileged inference engine.

## Phase 12 — Glitch / Novelty Engine

Expose GlitchLab analysis through stable capability contracts. Prefer adapters around current graph/delta/invariant modules.

`glitch` means incompatibility with the preferred model, not automatically vulnerability/error.

## Phase 13 — Propagation / Risk Simulator

Wrap existing `run_model` first. Then introduce a generalized simulation provider protocol.

Do not rewrite the current Iran SD model into a universal propagation model. New propagation models become separate provider implementations behind the same simulation contract.

## Phase 14 — Human–AI HUD

Use HA2D HUD/revision concepts to visualize:

- current graph/world model;
- alternative hypotheses;
- evidence and unknowns;
- delta;
- proposed action;
- requested/effective authority;
- blast radius/scenarios;
- abstraction λ.

HUD display is a projection of state, not the authority source.

## Phase 15 — Cross-repository observability

Minimum end-to-end trace:

```text
Observation
→ Reasoning result
→ DecisionProposal
→ GateApplied
→ ActionExecuted
→ OutcomeObserved
```

Each transition must share correlation/causation identifiers.

## Phase 16 — Replay

A replay record reconstructs:

- observed inputs;
- known unknowns;
- hypotheses;
- evidence;
- model/provider versions;
- policies/gates;
- authority;
- execution receipt;
- outcome.

Replay must tolerate missing data explicitly; it must not fabricate absent state.

## Phase 17 — Distillation

For repeatedly validated behavior:

```text
UNDERSTOOD
→ deterministic function/schema/test/policy
→ FORMALISED
```

Record supersession between heuristic and formalized mechanism.

## Phase 18 — Deterministic enforcement

All consequential providers consume validated execution contracts rather than free-form model outputs.

## Phase 19 — Adversarial validation

Architecture-level tests include:

```text
Can DATA become AUTHORITY?
Can MEMORY bypass a GATE?
Can a child agent inherit parent mandate implicitly?
Can compression lose provenance?
Can λ abstraction hide a critical dependency?
Can observability disappear without authority degradation?
Can a probabilistic output reach execution without a deterministic contract?
```

## Stacked PR strategy

Recommended PR sequence:

```text
PR-00 architecture analysis
PR-01 shared identity contract
PR-02 event envelope
PR-03 capability/repository manifests
PR-04 provider adapters: sbom + glitchlab
PR-05 provider adapter: swarm
PR-06 provider adapter: simulator
PR-07 graph projection
PR-08 gate/authority contract
...
```

Each PR body must contain:

```text
WHY
CURRENT
TARGET
ARCHITECTURAL INVARIANTS
CHANGED CONTRACTS
MIGRATION
TESTS
ROLLBACK
```

## Rollback principle

Until a legacy path is explicitly deprecated, disabling a Cyber-Lion adapter must return the provider to its previous standalone behavior. Cross-repo federation must therefore begin as an additive layer.