# LION — Process Contract Plane

PROFILE_ID=LION-RAG32/1
RELEASE_ID=lion-rag32-v1.4-process-contract-r1
PACKAGE_AUTHORITY=NONE

# LION Process Contract Plane

```text
DOCUMENT_ID=LION-PROCESS-CONTRACT-PLANE
DOCUMENT_VERSION=1.0
PROJECT=LION_EVOLUSION
ARCHITECTURE_EPOCH=1.4
ROLE=CANONICAL_PROCESS_SEMANTICS_CONTRACT
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
SCHEMA=lion.phase-execution-contract/v1
COMPILER=lion.phase-contract-compiler/1.0
```

## 1. Purpose and architectural position

The Process Contract Plane is the canonical semantic layer between an LPCL phase intent and a runtime capability binding. It exists because a phase name and objective can be semantically valid while remaining operationally underspecified. The plane does not execute effects, mint authority, select a permanent worker, or replace ProcessIR, FleetMissionIR, Action IR, authority evaluation, runtime admission, observation or reconciliation.

The canonical separation is:

```text
PROCESS_INTENT
!= PHASE_EXECUTION_CONTRACT
!= CAPABILITY_BINDING
!= COGNITIVE_PLAN
!= ACTION_IR
!= AUTHORITY_DECISION
!= RUNTIME_ADMISSION
!= EFFECT
!= COMPLETION_EVIDENCE
!= RECONCILIATION
```

A phase says **what state change or verification is intended**. A `PhaseExecutionContract` says **what class of execution may satisfy that phase, what the maximum effect envelope is, what currentness/evidence are required, and what completion predicates must become true**. A capability binding selects a currently available implementation. Action IR represents one concrete bounded action. None of these objects is authority by itself.

## 2. Normative process invariants

```text
NO_EXECUTABLE_PHASE_WITHOUT_EXECUTION_CONTRACT
PLANNING_IS_NOT_EXECUTION_BINDING
MODEL_OUTPUT_IS_NOT_CAPABILITY
CAPABILITY_BINDING_IS_NOT_AUTHORITY
EFFECT_CEILING_IS_NOT_AUTHORITY_GRANT
RECEIPT_IS_NOT_COMPLETION
COMPLETION_REQUIRES_INDEPENDENT_RECONCILIATION
VERIFY_BEFORE_REPAIR
```

`NO_EXECUTABLE_PHASE_WITHOUT_EXECUTION_CONTRACT` applies to LPCL/1.2 declared phases. LPCL/1.1 remains compatible through a fail-closed `LEGACY_INFERRED_SAFE` contract with `effect_ceiling=NONE`; legacy compatibility must never infer mutation permission from words such as `REPAIR`, `FIX`, `IMPLEMENT` or `MIGRATE`.

## 3. Complete process pipeline

```text
USER / GOAL
  ↓
LPCL SOURCE
  ↓
LEXICAL PARSE
  ↓
MISSION PROCESS IR
  ↓
PHASE EXECUTION CONTRACTS
  ↓
MISSION EXECUTION PREFLIGHT
  ↓
CAPABILITY NEEDS
  ↓
DYNAMIC CAPABILITY BINDING
  ↓
COGNITIVE PLAN / PROPOSAL         [optional]
  ↓
ACTION IR                         [for concrete bounded action]
  ↓
AUTHORITY + CURRENTNESS + ADMISSION
  ↓
BOUNDED EXECUTOR
  ↓
EVIDENCE
  ↓
RECEIPT
  ↓
COMPLETION CONTRACT EVALUATION
  ↓
RECONCILIATION
  ↓
PHASE TRANSITION
  ↓
NEXT PHASE
```

Every arrow is a boundary. Earlier representations constrain later ones but do not prove them. Dynamic capability binding may be changed or rebound without changing the phase's semantic contract.

## 4. PhaseExecutionContract

Canonical schema: `lion.phase-execution-contract/v1`.

Implementation semantic owner: `cyber_lion/contracts/phase_execution_contract.py`.

A contract contains:

```text
mission_id
phase_id
ordinal
contract_version
execution_class
capability_classes[]
effect_ceiling
binding_mode
on_missing_capability
auto_resume
verify_before_mutate
currentness_requirements[]
evidence_requirements[]
completion_predicates[]
contract_source
contract_digest
compiler_version
```

Closed execution-class vocabulary:

```text
OBSERVE
VERIFY
COGNITIVE
VERIFY_THEN_REPAIR
MUTATE
VALIDATE
CONTROL
```

Binding modes:

```text
STATIC
DYNAMIC
```

Missing-capability policies:

```text
FAIL
WAIT
WAIT_AND_DISCOVER
ESCALATE
```

Effect ceilings:

```text
NONE
CONTROL_STATE
BOUNDED_LOCAL
BOUNDED_REPOSITORY
BOUNDED_MATERIAL
```

The ceiling is an upper bound only. It never creates an authority grant or runtime permit. A narrower read-only capability may satisfy a contract with a wider ceiling when the completion predicates can be proven without mutation.

## 5. LPCL/1.2 mapping

The panel-oriented key/value surface declares per-phase contracts with:

```text
PHASE_XX_EXECUTION_CLASS=
PHASE_XX_CAPABILITY_CLASS=
PHASE_XX_EFFECT_CEILING=
PHASE_XX_BINDING_MODE=
PHASE_XX_ON_MISSING_CAPABILITY=
PHASE_XX_AUTO_RESUME=
PHASE_XX_VERIFY_BEFORE_MUTATE=
PHASE_XX_CURRENTNESS=
PHASE_XX_EVIDENCE=
PHASE_XX_COMPLETION_NN=<PREDICATE>=<EXPECTED>
```

Completion predicates containing `=` are written inline. Example:

```text
PHASE_03_COMPLETION_01=FRESH_LPCL_WITHOUT_PARENT=PASS
```

This avoids lexical ambiguity with a new key/value field.

The canonical RUN/PHASE surface uses the complementary phase-scoped fields:

```text
EXECUTION_CLASS
CAPABILITY_CLASS
EFFECT_CEILING
BINDING_MODE
ON_MISSING_CAPABILITY
AUTO_RESUME
VERIFY_BEFORE_MUTATE
CURRENTNESS_CONTRACT
EVIDENCE_CONTRACT
COMPLETION=<PREDICATE>=<EXPECTED>
```

`LPCL_VERSION=1.1` remains legal and is compiled to safe legacy contracts. `LPCL_VERSION=1.2` requires an explicit valid contract for every phase.

## 6. Parser/compiler boundary

LPCL lexical parsing and semantic compilation are separate operations:

```text
TEXT
→ PARSE KEY/VALUE OR RUN/PHASE SURFACE
→ MissionProcessIR / CanonicalRunAST
→ PhaseExecutionContract[]
→ CONTRACT VALIDATION
→ CAPABILITY PREFLIGHT
```

A syntax-valid phase is not necessarily execution-valid. The lexical parser does not infer authority, capability or completion. Mission Control recompiles contracts from the exact `lpcl_text`; client-supplied derived contract objects are not trusted as semantic authority.

## 7. Mission Execution Preflight

Before activation the process contract compiler produces `lion.mission-execution-preflight/v1` containing:

```text
phase_count
contract_count
bound_count
dynamic_count
unbound_count
invalid_count
authority_closure
currentness_closure
evidence_closure
capability_closure
mission_readiness
phase status vector
```

Readiness states:

```text
READY_BOUND
VALID_WITH_DYNAMIC_BINDING
WAITING_FOR_CAPABILITIES
INVALID
```

Phase contract states:

```text
VALID_BOUND
VALID_DYNAMIC
VALID_UNBOUND_WAITING
LEGACY_INFERRED_SAFE
INVALID
```

`VALID_UNBOUND_WAITING` is a valid state when the contract explicitly permits dynamic discovery. It must not be confused with an invalid phase.

## 8. Capability binding state machine

A semantic contract is stable while capability bindings are runtime state:

```text
UNBOUND
→ DISCOVERING
→ BOUND
→ STALE
→ REBOUND
```

The binding resolves `capability_classes` against the current capability registry. It may select a different executor after currentness drift or runtime failure without changing the phase contract. Capability availability is not authority.

Durable Mission Control carriers:

```text
mission_phase_execution_contracts     semantic contract
mission_phase_capability_bindings     current binding
mission_phase_execution_specs         runtime handler/execution spec
```

These tables intentionally have different meanings and must not be collapsed.

## 9. Relation to CapabilityNeed

A phase contract can materialize one or more `CapabilityNeed`-like requirements. `CapabilityNeed` represents a missing or required capability class; `PhaseExecutionContract` provides its process context, effect ceiling, currentness and completion constraints. Capability discovery may satisfy the need, but the resulting binding still does not grant authority.

## 10. Relation to Materializer Registry

When no registered capability satisfies a contract, `WAIT_AND_DISCOVER` may route the need toward the existing Bean/Composition/Abstraction/Materializer mechanisms. A materializer may create a candidate capability only through its own typed inputs, validation, authority and evidence boundaries. The Process Contract Plane does not create a general unrestricted executor.

## 11. Relation to Action IR

```text
PhaseExecutionContract != ActionIR
```

The phase contract specifies an admissible class of execution. `CanonicalActionIR` specifies one concrete bounded action. The required flow is:

```text
PHASE EXECUTION CONTRACT
→ CAPABILITY BINDING
→ COGNITIVE PROPOSAL if needed
→ ACTION IR
→ AUTHORITY / CURRENTNESS / ADMISSION
→ EFFECT
```

Forbidden shortcut:

```text
LPCL TEXT → RAW SHELL / EFFECT
MODEL TEXT → RAW SHELL / EFFECT
```

## 12. Authority and currentness boundary

The contract's `effect_ceiling` is a constraint, never an authority source. Effectful Action IR still requires the canonical authorization lifecycle, currentness and runtime admission. `currentness_requirements` specify what must be reacquired before a capability or completion predicate is trusted. Drift can stale a binding without invalidating the semantic phase intent.

## 13. Evidence and completion contracts

A receipt proves that a bounded action path reported a result. It does not prove that the phase objective is complete. `completion_predicates` are independently evaluated against current evidence. A phase may become `PASS` only after every required predicate is reconciled.

Example:

```text
LOCAL_PLANNING_RECEIPT=PASS
GENERIC_ADAPTER_BOUND=PASS
MATERIAL_READY_64=PASS
RESTART_DURABILITY=PASS
DB_INTEGRITY=PASS
```

A model answer cannot satisfy these predicates by assertion.

## 14. VERIFY_BEFORE_REPAIR

For `VERIFY_THEN_REPAIR` the mandatory path is:

```text
VERIFY CURRENT POSTCONDITION
       ↓
all predicates already satisfied?
  YES → NO MUTATION → evidence → receipt → reconciliation → PASS
  NO  → materialize the narrowest missing repair capability/action
```

This prevents a stale cognitive plan from reimplementing work that subsequent bootstrap repairs already completed. `REPAIR`, `FIX`, `IMPLEMENT` and `MIGRATE` are semantic intentions, not automatic mutation commands.

## 15. LPCL/1.1 compatibility

LPCL/1.1 is not rewritten. A missing explicit execution contract is compiled as:

```text
contract_source=LEGACY_INFERRED_SAFE
execution_class=COGNITIVE
effect_ceiling=NONE
binding_mode=DYNAMIC
on_missing_capability=WAIT_AND_DISCOVER
auto_resume=TRUE
```

This compatibility object preserves readability and proposal-only execution. It cannot infer mutation authority from names, descriptions or model output. A known historical counterexample may be upgraded with a `MIGRATED_EXPLICIT` contract without rewriting its original LPCL bytes or digest.

## 16. Mission Control projection

Mission Control exposes separately:

```text
phase_execution_contracts
execution_preflight
phase_capability_bindings
phase_execution_specs
```

Operators must be able to distinguish:

```text
CONTRACT VALID / BINDING UNRESOLVED / WAIT_AND_DISCOVER
```

from:

```text
CONTRACT INVALID
```

and from a runtime execution failure. UI liveness/progress remain separate: heartbeat activity does not change completion percentage.

## 17. Restart and currentness requirements

Contracts and bindings are durable database state. Restart must not duplicate planning assignments, Action IR, receipts or phase completion. A restart-durability completion predicate requires evidence across a restart/snapshot boundary, not merely a live heartbeat after startup. Reconciliation must be idempotent.

## 18. RAG and onboarding integration

Every project entry point must know the compact invariant:

```text
PHASE_INTENT
!= PHASE_EXECUTION_CONTRACT
!= CAPABILITY_BINDING
!= ACTION_IR
!= EFFECT
!= COMPLETION
```

`AGENTS.md`, Codex integration/runbook/scaffolding, the architecture index and the next versioned RAG candidate route LPCL/mission/phase/capability/preflight/completion work to this document. Historical byte-preserved RAG releases are not rewritten. RAG remains data, never authority or live truth.

## 19. PROCESS_DECISION_LOG

This section is append-only in meaning: later decisions may supersede earlier ones explicitly, but historical counterexamples are not erased.

### PCD-0001 — Phase intent is not an execution contract

```text
PROCESS_DECISION_ID=PCD-0001
COUNTEREXAMPLE=REPAIR_EXECUTION_BINDER reached CAPABILITY_NOT_AVAILABLE despite a semantically valid LPCL phase
DISCOVERY=LPCL represented phase intent but did not carry a canonical PhaseExecutionContract
DECISION=Introduce Process Contract Plane and PhaseExecutionContract
SUPERSEDES=implicit assumption that PHASE intent is sufficient runtime contract
AUTHORITY_EFFECT=NONE
```

The counterexample originated in the Epoch 3 closure mission `LION-GENERIC-LPCL-MISSION-EXECUTION-ADAPTER-REPAIR-R1`. The correction is architectural: a phase may be meaningful before it is executable, and that distinction must be represented before runtime binding.
