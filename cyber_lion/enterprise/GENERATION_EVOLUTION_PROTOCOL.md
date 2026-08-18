# Generation and Evolution Protocol

## 1. Goal

Cyber-Lion must support continuous generation of agents, code, policies, schemas, experiments and swarm topologies without allowing the ecosystem to drift into an untraceable collection of model-generated artifacts.

The core rule is:

> **Generate freely in proposal space; mutate reality only through typed deltas, deterministic gates and observable execution.**

This protocol applies to:

```text
source code
AgentSpec
SwarmSpec
Mosaic topology
policy
schema
memory contract
repository manifest
research-to-runtime rule
CI configuration
execution provider
```

---

## 2. Change Proposal

Every generated or manually proposed enterprise change is wrapped as:

```text
ChangeProposal = {
  change_id,
  proposer_identity,
  target_entities,
  target_artifacts,
  evidence_refs,
  rationale,
  expected_outcome,
  proposed_delta,
  changed_contracts,
  authority_effect,
  observability_effect,
  security_effect,
  migration_plan,
  tests_required,
  adversarial_tests_required,
  rollback_plan,
  expiry / review window
}
```

A proposal without evidence may still exist as a hypothesis, but it cannot be represented as evidence-backed implementation knowledge.

---

## 3. Universal change pipeline

```text
OBSERVE
↓
STRUCTURE
↓
HYPOTHESISE
↓
PROPOSE CHANGE
↓
NORMALIZE DELTA
↓
GLITCHLAB / STRUCTURAL ANALYSIS
↓
CONTRACT COMPATIBILITY
↓
SECURITY / AUTHORITY ANALYSIS
↓
SIMULATION / FALSIFICATION if required
↓
TEST
↓
GATE
↓
BOUNDED EXECUTION
↓
EXECUTION RECEIPT
↓
OUTCOME OBSERVED
↓
MEMORY / SPEC CANDIDATE
↓
PROMOTE / REJECT / SUPERSEDE
```

No step is skipped simply because an LLM generated high-confidence text.

---

## 4. Delta-first enterprise evolution

GlitchLab's Δ-first principle is generalized beyond source code.

The platform should normalize any change into tokens such as:

```text
ADD_AGENT
REMOVE_AGENT
MODIFY_AGENT_MISSION
MODIFY_AGENT_AUTHORITY
ADD_CAPABILITY
REMOVE_CAPABILITY
MODIFY_CAPABILITY_CONTRACT
ADD_SWARM_EDGE
REMOVE_SWARM_EDGE
CHANGE_SWARM_TOPOLOGY
ADD_POLICY
MODIFY_POLICY
ADD_MEMORY_RULE
MODIFY_SCHEMA
ADD_REPOSITORY_PROVIDER
MODIFY_EXECUTION_DOMAIN
```

Every token is bound to:

```text
entity
location/artifact
before state
after state
provenance
risk class
```

Target integration with GlitchLab:

```text
EnterpriseDelta
→ GlitchLab normalized tokens
→ fingerprint
→ structural projection
→ invariants
→ decision artifact
```

---

## 5. Enterprise invariants

The existing GlitchLab invariants remain useful, but the enterprise introduces a wider invariant family.

### E1 — Identity continuity

A change must not silently change the identity of an entity.

```text
same entity_id
⇒ compatible identity semantics
```

Renaming/migration requires alias/supersession records.

### E2 — Contract compatibility

Public capability/event/schema/agent interfaces may not break silently.

Breaking changes require:

```text
new version
adapter or migration
consumer impact list
rollback
```

### E3 — Authority non-escalation

A generated change may not silently increase effective authority.

```text
Authority_after > Authority_before
⇒ explicit consequential gate
```

### E4 — Provenance completeness

Consequential changes require reconstructable evidence and proposal lineage.

### E5 — Observability preservation

A change must not reduce required causal observability unless authority is degraded accordingly.

```text
Observability_after < required
⇒ Authority_after < Authority_before
```

### E6 — Replayability

The system must be able to reconstruct why a state transition occurred from events/artifacts.

### E7 — Blast-radius boundedness

Changes must declare and test their failure scope.

### E8 — Epistemic correctness

Claims are tagged as:

```text
OBSERVED
DERIVED
CALIBRATED
HYPOTHESIS
EXPERIMENTAL
SPECULATIVE
```

A `HYPOTHESIS` may not silently become a normative production rule.

### E9 — Memory separation

Working context and generated notes do not automatically become committed organizational memory.

### E10 — Polymorphic structural integrity

Dynamic changes to topology must preserve mission capability coverage and authority constraints.

---

## 6. GlitchLab integration model

Long-term, GlitchLab becomes a compiler for enterprise deltas.

Input adapters:

```text
source-code adapter
AgentSpec adapter
SwarmSpec adapter
policy adapter
JSON Schema adapter
repository-manifest adapter
memory-contract adapter
```

Output:

```json
{
  "change_id": "...",
  "delta_tokens": [],
  "fingerprint": "...",
  "contracts": [],
  "violations": [],
  "security_findings": [],
  "observability_delta": {},
  "authority_delta": {},
  "decision": "ACCEPT|REVIEW|BLOCK",
  "evidence": []
}
```

The GlitchLab decision is an input to Cyber-Lion policy. It does not by itself grant production execution rights.

---

## 7. Generation rules for AI agents

An agent generating an artifact MUST receive:

```text
mission
current state
allowed scope
relevant contracts
required invariants
available capabilities
evidence/context refs
output schema
non-goals
authority ceiling
```

It MUST NOT infer missing authority from prose.

Generated output SHOULD contain:

```text
artifact
rationale
delta summary
assumptions
uncertainties
tests
security notes
rollback/migration implications
```

---

## 8. One loop → one bounded artifact

The GlitchLab principle is adopted globally:

```text
one generation loop
→ one primary artifact or one coherent contract change
```

Examples:

```text
one Python module
one AgentSpec
one SwarmSpec
one policy file
one schema
one migration adapter
one research promotion record
```

Large changes are decomposed into a sequence of auditable deltas.

This reduces:

- hidden coupling,
- review complexity,
- rollback uncertainty,
- model-context overload.

---

## 9. Generated code pipeline

```text
SoftwareBuildSpec
→ code proposal
→ static structure extraction
→ dependency/provenance registration
→ tests generated/updated
→ SAST-Bridge
→ GlitchLab invariants
→ bounded local build
→ BuildReceipt
→ optional isolated execution provider
→ gate for external/deploy effects
```

Arbitrary model code is never treated as trusted simply because it compiled.

---

## 10. Agent generation pipeline

```text
MissionSpec
→ required capabilities
→ AgentTemplate selection
→ AgentSpec candidate
→ validate identity/authority/memory/observability
→ simulation or dry-run
→ register AgentSpec version
→ issue AgentInstance identity
→ admit to execution domain
```

An agent template cannot include reusable production credentials.

---

## 11. Swarm generation pipeline

```text
MissionSpec
→ capability gap
→ candidate agents
→ set-cover / topology planning
→ SwarmSpec candidate
→ risk topology rules
→ authority ceiling validation
→ observability quorum validation
→ simulation / adversarial topology test
→ gate if consequential
→ activate swarm
```

Every dynamic spawn/reconfiguration emits a MosaicDelta.

---

## 12. Updating rules and thresholds

Rules themselves evolve. Therefore a distinction is required:

```text
runtime data
rule candidate
calibrated threshold candidate
normative rule
```

Example GlitchLab-style threshold evolution:

```text
observed metric history
→ EWMA/MAD/quantiles
→ threshold candidate
→ drift check
→ shadow evaluation
→ review/gate
→ spec version update
```

Automatic adaptation MUST have bounds. A system must not gradually normalize increasingly dangerous behavior by continuously moving thresholds.

Use:

```text
freeze-on-drift
max-change-per-version
minimum evidence window
manual or independent-agent review for security-critical thresholds
```

---

## 13. Polymorphic repository maintenance

The enterprise is intentionally multi-repository. Cross-repository changes therefore require a `ChangeSet`:

```text
ChangeSet = {
  changeset_id,
  mission_id,
  repository_deltas[],
  dependency_order,
  compatibility_window,
  rollout_order,
  rollback_order,
  expected cross-repo invariants
}
```

Recommended rollout:

```text
1. contract/schema
2. compatibility adapter
3. provider implementation
4. consumer integration
5. dual-read/dual-write period
6. observability validation
7. remove deprecated path
```

Never modify all repositories simultaneously without intermediate compatibility states.

---

## 14. Repository generated artifacts policy

Source repositories SHOULD separate:

```text
SOURCE
SPEC
GENERATED EPHEMERAL
GENERATED REVIEWABLE
RUNTIME STATE
RESEARCH ARTIFACT
```

Rules:

- virtualenv/IDE/runtime state are not source,
- generated source must have provenance,
- large simulation outputs should not silently become canonical input,
- derived artifacts include source/config/seed refs,
- secrets are never stored as generated examples with real values.

---

## 15. Security generation rules

Any generated change involving:

```text
authentication
authorization
credentials
network egress
subprocess/exec
deserialization
file extraction
policy/gate logic
memory write
model/tool delegation
```

MUST trigger security review/adversarial tests.

Minimum negative tests include:

```text
invalid identity
missing provenance
stale capability
unauthorized delegation
path traversal
shell injection
policy bypass
observability loss
replay corruption
authority escalation
malformed provider output
```

---

## 16. Observability rules

Every consequential enterprise mutation must emit enough information to reconstruct:

```text
source evidence
proposer
change proposal
policy decision
capability used
execution identity
actual effect
result/outcome
follow-up state
```

Observability is part of the permission model, not a passive monitoring feature.

---

## 17. Rollback and supersession

Deletion is not the only way to evolve.

Artifacts/agents/policies may be:

```text
ACTIVE
DEPRECATED
SUPERSEDED
REVOKED
ARCHIVED
```

Supersession preserves lineage:

```text
v1 → superseded_by → v2
```

Rollback must specify whether it restores:

- code,
- contract,
- data schema,
- authority state,
- agent topology,
- memory state.

---

## 18. Autonomous update budget

Not every change needs human review. Autonomy is lane-based.

### GREEN

Agent may autonomously update:

- read-only indexes,
- derived documentation,
- local test fixtures,
- non-consequential experiment scaffolds,
- internal analysis artifacts.

### AMBER

Requires deterministic gate and/or independent verifier:

- source code change,
- AgentSpec change,
- memory candidate promotion,
- external communication,
- dependency update,
- swarm reconfiguration.

### RED

Requires high-assurance approval/enforcement:

- production deployment,
- authority expansion,
- secret access changes,
- financial commitments,
- critical infrastructure,
- irreversible data mutation.

---

## 19. Continuous enterprise regression

A successful change creates a regression family.

```text
finding
→ generalized missing invariant
→ deterministic rule where possible
→ regression test
→ adversarial variant set
→ continuous retest
```

The goal is not to teach the model one answer. The goal is to make the unsafe class structurally unreachable or explicitly gated.
