# CYBER-LION — Contract Map

Integration is contracts-first. Existing providers are wrapped before they are rewritten.

## Contract ownership

| Contract | Owner | Compatibility source | Consumers |
|---|---|---|---|
| Entity Identity Envelope | `ai_platform` | `sbom` AID | all providers |
| Repository Manifest | `ai_platform` | LAT_GLX/QV9D mapping | control plane |
| Capability Descriptor | `ai_platform` | local registries/docs | control plane, agents |
| Event Envelope | `ai_platform` | SBOM event envelope, GlitchLab BUS | all providers |
| Provenance Envelope | `ai_platform` | AID + evidence metadata | all providers |
| Hypothesis/Evidence Record | `ai_platform` | hipotezy/writeups | cognition, graph |
| Gate Request / Gate Applied | `ai_platform` | SBOM gate, GlitchLab Guard, RBAC evidence | control/execution |
| Execution Contract | `ai_platform` | swarm/tool adapters | execution providers |
| Execution Receipt | `ai_platform` | new common contract | graph/replay/audit |
| Memory Mutation | `ai_platform` + HA2D semantics | PCE/MCV concepts | memory providers |
| Simulation Request/Result | `ai_platform` | `run_model` adapter | simulator/cognition |
| Structure Graph | `ai_platform` | GlitchLab + Mosaic Lab | graph consumers |
| Replay Query/Record | `ai_platform` | EGDB/event stores/revision viewer | HUD/audit |

## 1. Entity Identity Envelope

Generalization must preserve existing AID semantics.

```json
{
  "entity_id": "stable-id",
  "entity_type": "application|repo|service|agent|model|tool|artifact|experiment|execution|dataset",
  "owner": "owner-id",
  "repo": "owner/name",
  "version": "version-or-build",
  "vcs_ref": "commit-or-tag",
  "environment": "lab|dev|test|prod|unknown",
  "parent_entity": "optional-id",
  "compat": {
    "aid": {}
  }
}
```

Rules:

- `entity_id` identifies the logical entity, not its network address.
- `vcs_ref` identifies a source observation, not permanent identity.
- AID remains valid inside `compat.aid` during migration.
- an unknown owner/identity can reduce authority; it must not be guessed by an LLM.

## 2. Repository Manifest

Each repository publishes a machine-readable manifest declaring what it **actually** provides.

```yaml
repo:
  id: DonkeyJJLove/swarm
  vcs_ref: <commit>
cyber_lion:
  tile_id: swarm
  roles: [execution_mesh]
  layers: [INF, MAND]
capabilities: []
contracts:
  consumes: []
  produces: []
authority:
  maximum_level: bounded
  required_gates: []
observability:
  logs: []
  metrics: []
  traces: []
security:
  trust_boundaries: []
epistemic:
  status: FACT|DERIVED|HYPOTHESIS|EXPERIMENTAL
```

The manifest is declarative. Discovery must validate it against executable endpoints/tests where possible.

## 3. Capability Descriptor

```yaml
capability_id: structure.ast_graph.v1
provider_entity: <entity-id>
version: 1.0.0
inputs:
  schema: cyberlion://schemas/source-artifact/v1
outputs:
  schema: cyberlion://schemas/structure-graph/v1
side_effects: none
required_authority: read
required_gates: []
observability:
  emits: [ObservationCreated, OutcomeObserved]
epistemic_status: FORMALISED
```

Capabilities with real-world side effects must declare them. Hidden side effects make the provider ineligible for autonomous composition.

## 4. Provenance Envelope

Minimum:

```json
{
  "source_entity": "...",
  "source_event": "...",
  "source_artifact": "...",
  "content_hash": "...",
  "transformation_chain": [],
  "confidence": null,
  "epistemic_status": "FACT|DERIVED|HYPOTHESIS|SPECULATION|RESULT|NEGATIVE_RESULT|SUPERSEDED",
  "upstream": []
}
```

Compression must preserve the reference to upstream evidence even if payload is summarized.

## 5. Hypothesis / Evidence contract

Hypothesis:

```json
{
  "hypothesis_id": "...",
  "statement": "...",
  "prior": null,
  "posterior": null,
  "supporting_evidence": [],
  "contradicting_evidence": [],
  "unknowns": [],
  "dependencies": [],
  "falsification_tests": [],
  "status": "UNKNOWN|UNDERSTOOD|FORMALISED"
}
```

A hypothesis record is explicitly non-authoritative for execution.

## 6. Gate contract

Request:

```json
{
  "gate_request_id": "...",
  "decision_id": "...",
  "execution_id": "...",
  "actor": "...",
  "requested_capability": "...",
  "requested_authority": "...",
  "impact": "...",
  "policy_ids": [],
  "evidence": [],
  "observability_state": "..."
}
```

Applied result:

```json
{
  "gate_event_id": "...",
  "gate_request_id": "...",
  "result": "ALLOW|ALLOW_REDUCED|REQUIRE_APPROVAL|QUARANTINE|PAUSE|DENY",
  "effective_authority": "...",
  "policy_ids": [],
  "applied_at": "...",
  "evidence_hash": "..."
}
```

A policy declaration is not an applied gate event.

## 7. Execution Contract

Execution providers consume a deterministic, already validated contract:

```json
{
  "execution_id": "...",
  "actor_entity": "...",
  "tool_entity": "...",
  "capability_id": "...",
  "input": {},
  "input_schema": "...",
  "authority": "...",
  "gate_event_id": "...",
  "constraints": {},
  "timeout": null,
  "correlation_id": "..."
}
```

A probabilistic model may propose the values; deterministic code validates schema, authority, gate and constraints before execution.

## 8. Memory Mutation Contract

```json
{
  "memory_event_id": "...",
  "memory_class": "WORKING|EPISODIC|SEMANTIC|PROCEDURAL|POLICY|EVIDENCE|QUARANTINE",
  "operation": "CANDIDATE|COMMIT|SUPERSEDE|DELETE",
  "source": "...",
  "policy_id": "...",
  "gate_event_id": "...",
  "provenance": {},
  "payload_ref": "..."
}
```

Untrusted input may create a candidate; it cannot self-authorize a persistent memory commit.

## 9. Compatibility policy

```text
CURRENT local contract
→ adapter
→ Cyber-Lion envelope
→ dual emit / compare
→ consumer migration
→ legacy deprecation only after evidence
```

No provider is required to replace its internal representation merely to participate in Cyber-Lion.