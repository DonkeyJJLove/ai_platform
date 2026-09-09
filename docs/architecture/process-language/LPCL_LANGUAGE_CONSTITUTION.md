# LPCL Language Constitution — v1.1 candidate

```text
STATUS=CANDIDATE_NOT_MERGED
ARCHITECTURE_EPOCH=1.4
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
PRODUCTION_EFFECT=NONE
```

## 1. Purpose

LPCL is the canonical non-effectful process-orchestration language of LION. Its human/model authoring surface is intentionally distinct from the machine semantic representation. The canonical chain is:

```text
LPCL canonical RUN/PHASE surface
→ CanonicalRunAST
→ CanonicalProcessIR
→ FleetMissionIR
→ bounded role routing
→ ActionIntent only when transition_class=ACTION_REQUIRED
→ existing Action / PDP / RuntimeAdmission / effect chain
→ independent observation
→ reconciliation
```

The language does not mint authority, evaluate policy, construct RuntimeAdmission, choose an EffectProvider or execute an effect.

## 2. Canonical layers

```text
LPCL_SURFACE
!=
LPCL_AST
!=
CANONICAL_PROCESS_IR
!=
FLEET_MISSION_IR
!=
ACTION_INTENT
!=
AUTHORITY_DECISION
!=
RUNTIME_ADMISSION
!=
EFFECT
!=
OBSERVED_EFFECT
!=
RECONCILED_CLOSURE
```

`CanonicalProcessIR` remains the normative deterministic process-state contract. `FleetMissionIR` is a complementary non-authoritative execution-topology contract. The RUN/PHASE surface is the canonical authoring form for v1.1 candidates.

## 3. Surface language

The v1.1 authoring surface uses the historical LION key/value shape rather than JSON as the primary human language:

```text
RUN=
...

PROCESS_LANGUAGE=
LPCL

LPCL_VERSION=
1.1

MISSION_CLASS=
HYBRID_FLEET_MISSION

PHASE_0=
...
```

Comments and descriptive blocks may be present. Descriptive blocks are annotations only. They never override the typed controls compiled into ProcessIR or FleetMissionIR.

The strict RFC8259 JSON LPCL 1.0 surface remains a compatibility surface and a machine-oriented serialization path. It is not silently reinterpreted as v1.1.

## 4. Version and legacy rule

The former statement "historical RUN is never executable" is refined rather than removed:

```text
UNVERSIONED_HISTORICAL_RUN=DATA_ONLY
UNPARSED_RUN=DATA_ONLY
INVALID_CANONICAL_RUN=DATA_ONLY
VALID_LPCL_1_1_RUN=PROCESS_CANDIDATE
PROCESS_CANDIDATE!=AUTHORITY
PROCESS_CANDIDATE!=RUNTIME_ADMISSION
PROCESS_CANDIDATE!=EFFECT
```

`LegacyRunAdapter` remains a read-only historical adapter. It cannot grant execution semantics to ambiguous historical material.

## 5. Fleet mission rule

Every executable LPCL v1.1 process declares exactly one mission class:

```text
LOGICAL_FLEET_MISSION
LOCAL_FLEET_MISSION
HYBRID_FLEET_MISSION
```

A fleet mission defines execution topology, bounded role identity, routing and evidence lineage. It is not an authority source.

`LOGICAL` is used when no material effect is crossed. Logical roles may be virtual or sequentially materialized by one model runtime, but role identity and evidence lineage remain distinct.

`LOCAL` is used for a process whose execution roles cross a material local boundary. `ACTION_REQUIRED` transitions must route to a LOCAL role and may only emit `ActionIntent`.

`HYBRID` is used when one process combines logical reasoning with material execution. A HYBRID mission must contain and actually route work through both LOGICAL and LOCAL domains.

## 6. Role separation

Role separation is a process property, not proof of independent physical infrastructure. The surface can declare symmetric logical separation through `ROLE_SEPARATION`.

Minimum architecture invariants are:

```text
ANALYST!=MATERIALIZER
MATERIALIZER!=INDEPENDENT_OBSERVER
AUTHORITY_OBSERVER!=AUTHORITY_SOURCE
EFFECTFUL_ROLE!=CLOSURE_RECONCILER
```

Where physical independence matters, separate runtime evidence remains required. Logical role separation alone is insufficient.

## 7. Phase semantics

`PHASE_N` is the canonical human authoring unit. Compilation gives each phase one deterministic source state and one deterministic transition. Numbering is contiguous from `PHASE_0`.

Each canonical phase explicitly declares:

```text
TRANSITION_CLASS
OPERATOR
ROLE
EVIDENCE_REQUIREMENTS
CURRENTNESS_REQUIREMENTS
AUTHORITY_REQUIREMENTS
EXPECTED_POSTCONDITIONS
REPLAY_POLICY
IDEMPOTENCY_CLASS
RETRY_MAX_ATTEMPTS
RETRY_ON_EXHAUSTED
```

Default outcome semantics are fail-closed:

```text
PASS → next PHASE or DONE
FAIL → STOP
UNKNOWN → HANDOFF
DRIFT → HANDOFF
BLOCKED → DEFER
AUTHORITY_BOUNDARY → HANDOFF
```

Explicit `ON_*` controls may override only with valid ProcessIR targets.

## 8. Action boundary

```text
TRANSITION_CLASS=ACTION_REQUIRED
→ OPERATOR=EMIT_ACTION_INTENT
→ LOCAL role
→ existing downstream authority evaluation
```

A mission declaration, role, fleet, green test, receipt, repository permission or model decision is never sufficient downstream authority.

## 9. Currentness and replay

Currentness is an independent process dimension. Evidence PASS does not imply CURRENT. Non-idempotent retries remain reconciliation-first under the existing ProcessIR contract. The v1.1 compiler does not weaken ProcessIR validation.

## 10. Cross-thread conformance

All new LION threads that are asked to create an executable LPCL process should emit the canonical RUN/PHASE authoring surface. Exact prose and comments need not be identical, but semantic controls, fleet classification, phase numbering, authority separation, termination and lineage requirements must conform.

The canonical machine truth is the compiled IR, not textual similarity.

## 11. Architecture placement

LPCL becomes an explicit process-orchestration plane in architecture documentation:

```text
Intent / Goal
→ LPCL surface
→ CanonicalRunAST
→ CanonicalProcessIR
→ FleetMissionIR
→ bounded execution-role routing
→ ActionIntent if required
→ existing canonical authority decision
→ existing RuntimeAdmission
→ effect
→ independent observation
→ reconciliation
```

This placement does not create a second PDP, runtime-admission engine or effect provider.

## 12. Bootstrap rule

The v1.1 constitution cannot authorize its own creation. Until merged and independently reconciled, this document and the associated implementation are candidate material only.
