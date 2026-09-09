# LPCL cross-thread generation standard — v1.1 candidate

```text
STATUS=CANDIDATE_NOT_MERGED
PURPOSE=ONE_AUTHORING_INTERPRETATION_ACROSS_LION_THREADS
AUTHORITY_EFFECT=NONE
```

## Required authoring form

When a LION thread is asked to create or continue an executable LPCL process, it should produce the canonical key/value RUN/PHASE surface. JSON remains an internal/machine-oriented LPCL 1.0 compatibility surface and must not be emitted as the default human process language.

Required ordering class:

```text
RUN
IDENTITY_AND_VERSION
PRIMARY_GOAL
SCOPE_AND_CURRENTNESS
MISSION_FLEET
AUTHORITY_STATE
PHASE_0..PHASE_N
VALIDATION_OR_FALSIFICATION
TERMINATION
LINEAGE
NEXT_PROCESS
END
```

Comments, explanatory headings and domain-specific annotation blocks are permitted. They do not carry machine authority and do not override typed controls.

## Required global controls

Every canonical v1.1 process includes at minimum:

```text
RUN
PROCESS_LANGUAGE=LPCL
LPCL_VERSION=1.1
MISSION_CLASS
MISSION_ID
PRIMARY_GOAL
SCOPE_DOMAINS
SCOPE_RESOURCES
WIDENING_ALLOWED=FALSE
```

Every process must also make its material authority posture explicit in the human artifact. Recommended declarations are:

```text
PRODUCTION_AUTHORITY=NONE_UNLESS_EXACTLY_PROVEN
MERGE_AUTHORITY=NONE_UNLESS_EXACTLY_PROVEN
DELETE_AUTHORITY=NONE_UNLESS_EXACTLY_PROVEN
RUNTIME_AUTHORITY=NONE_UNLESS_EXACTLY_PROVEN
```

These declarations are requirements/constraints, never grants.

## Fleet classification

Choose exactly one:

```text
LOGICAL_FLEET_MISSION
LOCAL_FLEET_MISSION
HYBRID_FLEET_MISSION
```

Use LOGICAL only when the process has no `ACTION_REQUIRED` transition and does not cross a material runtime boundary. Use LOCAL when all routed execution roles are material/local. Use HYBRID when logical analysis and material execution are both part of the process.

For HYBRID declare both:

```text
LOGICAL_FLEET_ROLES=
...

LOCAL_FLEET_ROLES=
...
```

Where closure depends on separation, declare it with `ROLE_SEPARATION=ROLE_A!=ROLE_B` and still require independent physical evidence where applicable.

## Canonical phase controls

Every `PHASE_N` declares:

```text
TRANSITION_CLASS=
INTERNAL | ACTION_REQUIRED

OPERATOR=
<existing ProcessIR operator>

ROLE=
<declared mission role>

EVIDENCE_REQUIREMENTS=
...

CURRENTNESS_REQUIREMENTS=
...

AUTHORITY_REQUIREMENTS=
...

EXPECTED_POSTCONDITIONS=
...

REPLAY_POLICY=
DENY | IDEMPOTENT | RECONCILE_FIRST

IDEMPOTENCY_CLASS=
PURE | IDEMPOTENT | NON_IDEMPOTENT

RETRY_MAX_ATTEMPTS=
<n>

RETRY_ON_EXHAUSTED=
BLOCKED | HANDOFF | STOP | UNKNOWN
```

For `ACTION_REQUIRED`, `OPERATOR` is exactly `EMIT_ACTION_INTENT`, evidence/currentness/authority requirements are non-empty, and `ROLE` resolves to a LOCAL execution role.

Optional machine controls are:

```text
DEPENDENCIES
GUARDS
READ_SCOPES
WRITE_SCOPES
AUTHORITY_BUDGETS
CURRENTNESS_SUBJECTS
REPLAY_DOMAIN
RECONCILIATION_GROUP
TRIGGER
PRIORITY
ON_PASS
ON_FAIL
ON_UNKNOWN
ON_DRIFT
ON_BLOCKED
ON_AUTHORITY_BOUNDARY
ON_COMPLETE
```

## Annotation blocks

Domain-specific blocks such as these remain readable authoring annotations:

```text
PURPOSE
ACTIONS
INPUT
OUTPUT
REQUIRE
VERIFY
DENY
FORBIDDEN
FAIL_CLOSED_IF
RECORD
RESEARCH
INSPECT
CREATE
MODIFY
UPDATE
```

Annotations are intentionally not sufficient to create typed transition semantics. If a required ProcessIR meaning matters, the corresponding canonical phase control must be present.

## Continuation rule

Every process generated for a LION autonomous continuation must include or semantically preserve the rule:

```text
ON_FAIL_CLOSED_OR_DEFER=
PRESERVE_EVIDENCE
PRESERVE_EXACT_IDENTITIES
IDENTIFY_LAST_COMPLETED_PHASE
IDENTIFY_BLOCKING_PHASE
IDENTIFY_NEXT_LEGAL_PHASE
GENERATE_COMPLETE_NEXT_LPCL_PROCESS
```

The next process code should be returned together with the terminal/deferred result rather than requiring the operator to reconstruct lineage manually.

## Conformance definition

Cross-thread conformance does not require byte-identical output. It requires the same semantic profile:

```text
SAME_VERSION_MODEL
SAME_FLEET_CLASSIFICATION_RULES
SAME_PHASE_CONTROL_MODEL
SAME_PROCESS_TO_ACTION_BOUNDARY
SAME_AUTHORITY_SEPARATION
SAME_CURRENTNESS_MODEL
SAME_FAIL_CLOSED_MODEL
SAME_TERMINATION_AND_LINEAGE_MODEL
```

A thread that emits YAML, free-form prose or raw JSON as the primary v1.1 human LPCL artifact is non-conformant unless the caller explicitly requests a machine serialization.
