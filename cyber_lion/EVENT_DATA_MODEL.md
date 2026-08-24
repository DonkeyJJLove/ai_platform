# CYBER-LION — model zdarzeń i danych

## Podstawowa koperta zdarzenia

Każde zdarzenie cross-system korzysta z wersjonowanej koperty. Payloady domenowe pozostają własnością providerów.

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

## Wymagane rodziny zdarzeń

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

## Inwarianty zdarzeń

### E1 — Tożsamość

```text
cross-system event ⇒ entity.entity_id exists
```

### E2 — Ślad przyczynowy

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

### E5 — Pamięć

```text
MemoryCommitted
⇒ policy_id + provenance + source candidate exist
```

### E6 — Zdegradowana obserwowalność

```text
required observability becomes incomplete
AND action authority > safe fallback
⇒ AuthorityDegraded event before next consequential action
```

## Obiekt authority

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

Authority jest jawnym stanem. Nie jest wywodzone z intencji wyrażonej językiem naturalnym.

## Typowany kontekst

Kontekst przekazywany do modelu lub agenta jest sekwencją typowanych elementów, a nie nieodróżnialnym workiem tekstu:

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

Reguła:

```text
same context window != same trust class
```

Element `AUTHORITY` musi pochodzić z zaufanego authority source i nie może zostać zmintowany przez element `DATA` lub `INSTRUCTION`.

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

Obiekt ten jest propozycją, a nie autoryzacją.

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

Receipts są append-only evidence. Korekty supersedują receipt; nie modyfikują po cichu rekordu historycznego.

## Simulation request/result

Żądanie:

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

Wynik:

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

Inwariant:

```text
MODEL_RESULT != OBSERVED_FACT
```

## Ingest grafu

Zdarzenia aktualizują graf przez jawne relacje. Przykład:

```text
ObservationCreated --observed_from--> Source
HypothesisGenerated --derived_from--> Observation
EvidenceAttached --supports|contradicts--> Hypothesis
DecisionProposed --derived_from--> Hypothesis/Evidence
GateApplied --authorized_by--> Policy/Human
ActionExecuted --executed_by--> Agent/Tool
OutcomeObserved --caused_by?--> Execution
```

`caused_by` jest używane wyłącznie wtedy, gdy przyczynowość została ustalona zgodnie z lokalną regułą evidence; w przeciwnym razie należy użyć `correlated_with` lub `derived_from`.

## Adaptery providerów

Początkowe mapowania:

- SBOM `@timestamp/event_type/aid/payload` → koperta Cyber-Lion z zachowaniem oryginalnego zdarzenia w `payload.compat`.
- Zdarzenia BUS GlitchLab → event envelope z metadanymi delty/inwariantów.
- Telemetria JSON `swarm` → `ObservationCreated` z metadanymi workload/entity/correlation.
- Zdarzenie kroku HMK-9D → `DeltaDetected` albo analityczne zdarzenie zależne od kontekstu; wektory mostów pozostają adnotacjami.
- Wyniki symulatora → `SimulationCompleted` z provenance modelu.
- Dokumenty writeups/hipotez → ingest `EvidenceCandidate`/`Hypothesis` dopiero po klasyfikacji metadanych.

## Wersjonowanie

Zmiany łamiące kompatybilność kontraktów wymagają głównej wersji schematu. W okresie migracji adaptery powinny obsługiwać co najmniej bieżącą i bezpośrednio poprzednią wersję główną.
