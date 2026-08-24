# CYBER-LION — mapa kontraktów

Integracja jest prowadzona w modelu **contracts-first**. Istniejący providerzy są najpierw opakowywani adapterami, a dopiero później — jeśli istnieje uzasadnienie — przepisywani.

## Ownership kontraktów

| Kontrakt | Owner | Źródło kompatybilności | Konsumenci |
|---|---|---|---|
| Entity Identity Envelope | `ai_platform` | AID z `sbom` | wszyscy providerzy |
| Repository Manifest | `ai_platform` | mapowanie LAT_GLX/QV9D | control plane |
| Capability Descriptor | `ai_platform` | lokalne rejestry/dokumentacja | control plane, agenci |
| Event Envelope | `ai_platform` | SBOM event envelope, GlitchLab BUS | wszyscy providerzy |
| Provenance Envelope | `ai_platform` | AID + metadane evidence | wszyscy providerzy |
| Hypothesis/Evidence Record | `ai_platform` | hipotezy/writeups | cognition, graph |
| Gate Request / Gate Applied | `ai_platform` | SBOM gate, GlitchLab Guard, evidence RBAC | control/execution |
| Execution Contract | `ai_platform` | adaptery swarm/tool | providerzy wykonawczy |
| Execution Receipt | `ai_platform` | nowy wspólny kontrakt | graph/replay/audit |
| Memory Mutation | `ai_platform` + semantyka HA2D | koncepcje PCE/MCV | providerzy pamięci |
| Simulation Request/Result | `ai_platform` | adapter `run_model` | simulator/cognition |
| Structure Graph | `ai_platform` | GlitchLab + Mosaic Lab | konsumenci grafu |
| Replay Query/Record | `ai_platform` | EGDB/event stores/revision viewer | HUD/audit |

## 1. Entity Identity Envelope

Generalizacja musi zachować istniejącą semantykę AID.

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

Reguły:

- `entity_id` identyfikuje logiczną encję, a nie jej adres sieciowy.
- `vcs_ref` identyfikuje obserwację źródła, a nie trwałą tożsamość.
- AID pozostaje poprawny wewnątrz `compat.aid` w okresie migracji.
- Nieznany owner/tożsamość może obniżyć authority; LLM nie może ich zgadywać.

## 2. Repository Manifest

Każde repozytorium publikuje machine-readable manifest deklarujący to, co **rzeczywiście** udostępnia.

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

Manifest ma charakter deklaratywny. Discovery powinno — tam, gdzie to możliwe — walidować go względem wykonywalnych endpointów/testów.

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

Capabilities powodujące skutki w świecie rzeczywistym muszą je deklarować. Ukryte side effects dyskwalifikują providera z autonomicznej kompozycji.

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

Kompresja musi zachować odwołanie do upstream evidence nawet wtedy, gdy payload zostaje podsumowany.

## 5. Kontrakt Hypothesis / Evidence

Hipoteza:

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

Rekord hipotezy jest jawnie nieautorytatywny w odniesieniu do execution.

## 6. Kontrakt gate

Żądanie:

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

Zastosowany wynik:

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

Deklaracja polityki nie jest zastosowanym zdarzeniem gate.

## 7. Execution Contract

Providerzy wykonawczy konsumują deterministyczny, wcześniej zwalidowany kontrakt:

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

Model probabilistyczny może zaproponować wartości; kod deterministyczny przed wykonaniem waliduje schema, authority, gate i constraints.

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

Niezaufane wejście może utworzyć candidate; nie może samo autoryzować trwałego memory commit.

## 9. Polityka kompatybilności

```text
CURRENT local contract
→ adapter
→ Cyber-Lion envelope
→ dual emit / compare
→ consumer migration
→ legacy deprecation only after evidence
```

Żaden provider nie musi zastępować swojej wewnętrznej reprezentacji wyłącznie po to, aby uczestniczyć w Cyber-Lion.
