# CYBER-LION — Event & Data Model

## Core event envelope

Every cross-system event uses a versioned envelope. Domain payloads remain provider-owned.

```json
{
  "schema_version": "1.0.0",
  "event_id": "uuid-or-content-addressed-id",
  "event_type": "ObservationCreated",
  "occurred_at": "RFC3339 timestamp",
  "correlation_id": "end-to-end-trace-id",
  "causation_id": "parent-event-id|null",
  "entity": {},
  "source": {},
  "provenance": {},
  "authority": {},
  "epistemic_state": "UNKNOWN|UNDERSTOOD|FORMALISED",
  "payload": {}
}
```

## Required event families

```text
ObservationCreated
DeltaDetected
StructureExtracted
HypothesisGenerated
HypothesisUpdated
EvidenceAttached
AnomalyDetected
SimulationRequested
SimulationCompleted
DecisionProposed
GateRequested
GateApplied
ActionAuthorized
ActionExecuted
OutcomeObserved
MemoryCandidateCreated
MemoryCommitted
AuthorityDegraded
ArtifactSuperseded
ReplayRequested
ReplayCompleted
```

## Event invariants

### E1 — Identity

```text
cross-system event ⇒ entity.entity_id exists
```

### E2 — Causal trace

```text
DecisionProposed / GateApplied / ActionExecuted
⇒ correlation_id exists
```

### E3 — Provenance

```text
DERIVED event ⇒ provenance.upstream is non-empty
```

### E4 — Authority

```text
ActionExecuted with consequential side effect
⇒ applied GateApplied event is referenced
```

### E5 — Memory

```text
MemoryCommitted
⇒ policy_id + provenance + source candidate exist
```

### E6 — Degraded observability

```text
required observability becomes incomplete
AND action authority > safe fallback
⇒ AuthorityDegraded event before next consequential action
```

## Authority object

```json
{
  "actor_entity": "...",
  "requested": "read|write|execute|admin|custom",
  "effective": "read|write|execute|admin|custom|none",
  "source": "policy|human|platform|workload",
  "policy_ids": [],
  "gate_event_id": null,
  "expires_at": null
}
```

Authority is explicit state. It is not inferred from natural-language intent.

## Typed context

Context transported to a model or agent is a sequence of typed items rather than an undifferentiated text bag:

```json
{
  "context_id": "...",
  "items": [
    {
      "item_id": "...",
      "type": "DATA|INSTRUCTION|CONTEXT|AUTHORITY|MEMORY|EVIDENCE|POLICY",
      "trust": "untrusted|bounded|trusted",
      "provenance": {},
      "content_ref": "..."
    }
  ]
}
```

Rule:

```text
same context window != same trust class
```

An `AUTHORITY` item must originate from a trusted authority source and cannot be minted by a `DATA` or `INSTRUCTION` item.

## Decision proposal

```json
{
  "decision_id": "...",
  "hypothesis_refs": [],
  "evidence_refs": [],
  "proposed_capability": "...",
  "proposed_parameters": {},
  "confidence": null,
  "unknowns": [],
  "expected_effect": {},
  "requested_authority": "..."
}
```

This object is a proposal, not authorization.

## Execution receipt

```json
{
  "execution_id": "...",
  "decision_id": "...",
  "correlation_id": "...",
  "actor_entity": "...",
  "tool_entity": "...",
  "target_entity": "...",
  "capability_id": "...",
  "input_hash": "...",
  "policy_ids": [],
  "gate_event_id": "...",
  "authority": "...",
  "started_at": "...",
  "completed_at": "...",
  "result": "SUCCESS|FAILURE|TIMEOUT|BLOCKED|PARTIAL",
  "result_hash": "...",
  "side_effects": [],
  "observability_complete": true
}
```

Receipts are append-only evidence. Corrections supersede a receipt; they do not silently mutate the historical record.

## Simulation request/result

Request:

```json
{
  "simulation_id": "...",
  "provider_capability": "...",
  "model_entity": "...",
  "model_version": "...",
  "scenario": {},
  "parameters": {},
  "seed": 0,
  "runs": 1,
  "source_graph_ref": null
}
```

Result:

```json
{
  "simulation_id": "...",
  "model_version": "...",
  "seed": 0,
  "runs": 1,
  "metrics": {},
  "uncertainty": {},
  "artifacts": [],
  "epistemic_status": "MODEL_RESULT"
}
```

Invariant:

```text
MODEL_RESULT != OBSERVED_FACT
```

## Graph ingestion

Events update the graph through explicit relations. Example:

```text
ObservationCreated --observed_from--> Source
HypothesisGenerated --derived_from--> Observation
EvidenceAttached --supports|contradicts--> Hypothesis
DecisionProposed --derived_from--> Hypothesis/Evidence
GateApplied --authorized_by--> Policy/Human
ActionExecuted --executed_by--> Agent/Tool
OutcomeObserved --caused_by?--> Execution
```

`caused_by` is only used when causality is established under the local evidence rule; otherwise use `correlated_with` or `derived_from`.

## Provider adapters

Initial mappings:

- SBOM `@timestamp/event_type/aid/payload` → Cyber-Lion envelope while preserving original event under `payload.compat`.
- GlitchLab BUS events → event envelope with delta/invariant metadata.
- Swarm telemetry JSON → `ObservationCreated` with workload/entity/correlation metadata.
- HMK-9D step event → `DeltaDetected` or context-specific analytical event; bridge vectors remain annotations.
- Simulator results → `SimulationCompleted` with model provenance.
- Writeups/hypothesis documents → `EvidenceCandidate`/`Hypothesis` ingestion only after metadata classification.

## Versioning

Breaking contract changes require a major schema version. Adapters should support at least the current and immediately previous major version during migration.