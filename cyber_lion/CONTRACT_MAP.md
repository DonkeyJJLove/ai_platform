# CYBER-LION — mapa kontraktów

Integracja jest prowadzona w modelu **contracts-first**. Istniejący providerzy są najpierw opakowywani adapterami, a dopiero później — jeśli istnieje uzasadnienie — przepisywani.

## Ownership kontraktów

| Kontrakt | Owner | Źródło kompatybilności | Konsumenci |
|---|---|---|---|
| Entity Identity Envelope | `ai_platform` | AID z `sbom` | wszyscy providerzy |
| Repository Manifest | `ai_platform` | mapowanie LAT_GLX/QV9D | control plane |
| Capability Descriptor | `ai_platform` | lokalne rejestry/dokumentacja | control plane, agenci |
| Event Envelope | `ai_platform` | SBOM event envelope, GlitchLab BUS | wszyscy providerzy |
| Communication Envelope | `ai_platform` | operator messages / GroupChannel projection | cognition, fleet, audit |
| Mission Intent | `ai_platform` | CommunicationEnvelope + mission/conversation refs | planning / semantic compiler |
| Query Plan | `ai_platform` | MissionIntent | retrieval/context planning |
| RAG Context Envelope | `ai_platform` | versioned RAG/currentness evidence | semantic compiler |
| Semantic Scaffold IR | `ai_platform` | SIC target + evidence-bound context | relevance organization |
| Semantic Relevance | `ai_platform` | scaffold + specialist semantic providers | cognition / experiments |
| Provenance Envelope | `ai_platform` | AID + metadane evidence | wszyscy providerzy |
| Hypothesis/Evidence Record | `ai_platform` | hipotezy/writeups | cognition, graph |
| Gate Request / Gate Applied | `ai_platform` | SBOM gate, GlitchLab Guard, evidence RBAC | control/execution |
| Execution Contract | `ai_platform` | adaptery swarm/tool | providerzy wykonawczy |
| Execution Receipt | `ai_platform` | nowy wspólny kontrakt | graph/replay/audit |
| Memory Mutation | `ai_platform` + semantyka HA2D | koncepcje PCE/MCV | providerzy pamięci |
| Simulation Request/Result | `ai_platform` | adapter `run_model` | simulator/cognition |
| Structure Graph | `ai_platform` | GlitchLab + Mosaic Lab | konsumenci grafu |
| Replay Query/Record | `ai_platform` | EGDB/event stores/revision viewer | HUD/audit |
| Fleet Aggregate Effect Budget | `ai_platform` | `FleetEffectBudgetStore` + `RepositoryMutationPEP` | consequential repository execution |
| Repository Architecture Knowledge | `ai_platform` schema + local repository manifests | `cyber-lion.repository.json` | fresh agents, federation projection, formalization |
| Federated Formalization Binding | `ai_platform` | `FleetBaseline` + local AFM | formalized governed-change admission |
| Formalized Governed Change Admission | `ai_platform` | existing `GovernedChangeAdmissionEngine` | architecture-changing candidate path |

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

### 2.1 Architecture knowledge extension

Repository Manifest remains the local repository discovery owner. v1.5 adds an optional, backward-compatible `architecture_knowledge` section:

```yaml
architecture_knowledge:
  schema_version: 1.0.0
  global_owner: DonkeyJJLove/ai_platform
  semantic_exports: []
  semantic_imports: []
  repository_dependencies: []
  architecture_artifacts: []
  discoverability:
    entrypoint: AGENTS.md
    global_owner_route: AGENTS.md -> cyber-lion.repository.json -> ai_platform
    max_reads_to_global_owner: 3
  invalidation_triggers: []
```

The extension does not make the manifest a live-truth or authority carrier. It describes repository-local architecture knowledge and the bounded route to the federation owner.

### 2.2 Federated Formalization Binding

`FederatedFormalizationBinding` binds an existing local Architecture Formalization Manifest to an exact `FleetBaseline`, a digest of repository dependency edges, and one disposition per registered repository:

```text
UPDATE
VALIDATE_ONLY
NOT_APPLICABLE
```

It cannot carry authority or execution effect. Architecture-changing admission may use `derive_formalized_request(...)`, which requires proposal binding, AFM, local FCR and the exact federation binding before delegating to the existing admission request derivation.

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

## 3a. Communication Envelope

Canonical owner: `cyber_lion/contracts/communication_envelope.py` (`lion.communication-envelope/v1`).

`CommunicationEnvelope` binds immutable semantic message identity: sender, frozen recipient set, optional conversation/mission scope, correlation/causation/causal-group references and external payload schema/ref/digest. It deliberately does **not** own payload bytes, transport/session readiness, delivery state, model invocation state, authority, runtime admission or effect.

Existing `operator_messages`, `GroupChannelEnvelope`, transport adapters and delivery ledgers remain operational owners. A communication envelope may become the `message_ref` of one or more `CognitiveInvocation` records; DUAL legs still keep separate invocation and attempt identities.

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

## 9. Fleet Aggregate Effect Budget — VERIFIED candidate

Zweryfikowany candidate `FLEET_AGGREGATE_EFFECT_BUDGET_ENFORCEMENT` dodaje restrykcyjną warstwę admission dla sumy lokalnie poprawnych efektów. Evidence dla claimu jest związane z:

```text
PR=249
VERIFIED_HEAD=b352d1c3d472e2b8d247b7194d2d62864611906b
VERIFIED_TREE=ee402be211f1b85ca0018ecccc0c972de56b0cb9
CONTRACT_DIGEST=c361104b330367212b3779f39898cc63b4ab9966219849eca84973a52fa163d2
IMPLEMENTATION_DIGEST=83c359c27e94c0adf288b2e24e78a08860dc3e9ef112cdf4ad88aeda03e27465
DEDICATED_RUN=33615802655
CORE_RUN=33615802648
```

Kontrakt składa się z czterech immutable struktur:

```text
FleetEffectEnvelope
FleetEffectReservationRequest
FleetEffectReservation
FleetEffectBudgetSnapshot
```

Reference implementation `FleetEffectBudgetStore` zapewnia atomową rezerwację, exact scope binding, generation binding, candidate binding, authority-effect-key binding, durable uniqueness, expiry, release/finalization i replay denial dla czterech zweryfikowanych wymiarów:

```text
max_concurrent_writers
max_active_repository_effects
max_active_branch_effects
max_active_path_effects
```

Integracja `RepositoryMutationPEP` wykonuje budget reservation **po** live authority revalidation i exact authority binding, ale **przed** lokalnym `journal.prepare()`. Reservation jest ponownie walidowana przed effect boundary.

Semantyka authority jest zamknięta i restrykcyjna:

```text
CAN_RESTRICT_AUTHORITY=YES
CAN_CREATE_AUTHORITY=NO
CAN_EXPAND_AUTHORITY=NO
CAN_SUBSTITUTE_AUTHORITY=NO

valid authority + no budget => DENY
budget + no authority => DENY
```

Ten claim nie oznacza i nie implikuje:

```text
DISTRIBUTED_CONSENSUS=NO_CLAIM
GLOBAL_MULTI_HOST_REPOSITORY_JOURNAL_LINEARIZABILITY=NO_CLAIM
MONETARY_BUDGET=NO_CLAIM
TOKEN_BUDGET=NO_CLAIM
PRODUCTION_DEPLOYMENT=NO_CLAIM
INTEGRATED=NO
OBSERVED=NO
```

`RepositoryMutationPEP` zachowuje klasyfikację `SINGLE_RUNTIME_ATTACH_ONLY`. Zweryfikowany fleet budget ogranicza admission efektu; nie zmienia lokalnego journala w globalnie linearizowalny multi-host effect store.

## 10. Polityka kompatybilności

```text
CURRENT local contract
→ adapter
→ Cyber-Lion envelope
→ dual emit / compare
→ consumer migration
→ legacy deprecation only after evidence
```

Żaden provider nie musi zastępować swojej wewnętrznej reprezentacji wyłącznie po to, aby uczestniczyć w Cyber-Lion.

## Semantic Cloud boundary

MissionIntent, QueryPlan, RagContextEnvelope, SemanticScaffoldIR and SemanticRelevance are non-effectful representation contracts. Semantic relevance cannot mint authority. RelevanceProjection may request existing capabilities only through explicit Gap/CapabilityNeed binding; material effects continue through the existing Action/PDP/runtime path.
