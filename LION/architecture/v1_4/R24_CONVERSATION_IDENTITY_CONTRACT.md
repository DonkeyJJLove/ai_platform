# LION R24 Conversation Identity Contract

```text
DOCUMENT_ID=LION-R24-CONVERSATION-IDENTITY-CONTRACT
DOCUMENT_VERSION=1.0
TASK_ID=LION-R24-WHOLE-INTEGRATION-CLOSURE-R1
PHASE=1
STATUS=IDENTITY_CONTRACT_CANDIDATE
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
LIVE_DEPLOYMENT=NO
```

## Purpose

This contract freezes the identity semantics that later R24 phases must implement.
It is deliberately earlier than additive schema, routing, delivery, migration, or UI
cutover.  A conversation is a durable LION object.  A mission, provider session,
native SaaS project thread, protocol correlation, participant, executor and model
route are related identities, but none of them may silently become the
conversation identity.

The canonical separation is:

```text
CONVERSATION_ID != MISSION_ID
CONVERSATION_ID != PROVIDER_SESSION_ID
CONVERSATION_ID != NATIVE_SAAS_PROJECT_THREAD_ID
CONVERSATION_ID != PROTOCOL_CORRELATION_ID

MODEL_CHAT != PROTOCOL_CHANNEL
LOGICAL_DRONE != MATERIAL_WORKER
PARTICIPANT_IDENTITY != EXECUTOR_IDENTITY
MISSION_BINDING != CONVERSATION_IDENTITY
MODEL_ROUTE != CONVERSATION_IDENTITY
LOCAL_PROVIDER_SESSION != SAAS_PROVIDER_SESSION
```

No identity conversion is implicit.  A mapping is an explicit record with its own
provenance and lifecycle.

## Conversation lifecycle

A newly created unbound conversation has a new `conversation_id`, no mission
binding and clean context.  A newly created conversation for a mission has a new
`conversation_id`, a new `binding_epoch`, and an exact mission binding.

`BIND` and `DETACH` are successor operations.  They never rewrite the semantic
identity or history of the predecessor conversation.

```text
BIND:
  predecessor conversation -> FROZEN
  successor conversation   -> BOUND(exact mission_id, new binding_epoch)

DETACH:
  predecessor conversation -> FROZEN
  successor conversation   -> UNBOUND(new binding_epoch)
```

Lineage is durable and queryable.  A predecessor transcript is immutable after the
successor is created.

## Model Chat lanes

A Model Chat request carries at minimum:

```text
conversation_id
binding_epoch
lane_id
message_id
causation_id
correlation_id
context_digest
```

LOCAL and SAAS lanes own independent provider sessions.  DUAL freezes one immutable
context snapshot and starts independent LOCAL(K) and SAAS(K) legs.  Hidden state
from one provider leg may not be fed into the other leg as an implicit continuation.

Model route is routing metadata.  It cannot define or replace conversation identity.

## Native SaaS project thread isolation

A native ChatGPT SaaS project thread is external to the LION conversation domain.
It may be related to a LION conversation only by an explicit bridge record.  The
bridge carries at minimum:

```text
bridge_id
conversation_id
external_thread_ref
external_system
created_at
provenance
context_snapshot_digest
authority_effect=NONE
```

Creating a SaaS project thread must not create, bind, or reuse a LION conversation.
Creating a LION conversation must not implicitly reuse a SaaS project thread.

## Protocol separation

Protocol is not Model Chat.  A protocol correlation identifier may be carried for
traceability, but it cannot be used as `conversation_id`, `lane_id`, provider
session identity, or message-thread identity.

Participant identity and executor identity remain distinct.  A logical drone may
be bound to a material worker for execution, but the binding cannot rewrite either
identity.  `drone:<LD*>` and `worker:<MD*>` are disjoint participant namespaces.

## Delivery identity

A response is admissible for delivery only when every required delivery dimension
matches the request that created it:

```text
conversation_id
binding_epoch
lane_id
message_id
causation_id
correlation_id
context_digest
participant_id (when participant-scoped)
```

A mismatch in any required dimension is a delivery denial.  Switching the active
UI conversation cannot redirect an older response.

## Target conceptual data model

The additive schema implemented in Phase 2 must cover, without semantic reduction:

```text
conversations
conversation_lineage
conversation_bindings
conversation_provider_lanes
conversation_threads
conversation_messages
conversation_delivery_events
conversation_delivery_cursors
conversation_external_bridges
conversation_migration_provenance
```

The machine-readable schema specification is
`LION/architecture/v1_4/r24_conversation_identity.schema.json`.

## Phase 1 test boundary

Phase 1 tests are contract tests.  They prove that the specification itself rejects
the six prohibited identity collapses required by the task and that delivery matching
is exact.  They do not claim that the existing runtime already implements the new
domain.  Runtime conformance remains deliberately RED/NOT_IMPLEMENTED until the
additive schema and conversation domain phases implement these objects.

The legacy `threads/thread_bindings/thread_model_routes/messages` model remains
historical implementation evidence and must not be reinterpreted as the new
conversation domain.

## Non-claims

This contract does not create database tables, migrate missions, change routing,
deploy services, bind a SaaS project thread, create provider sessions, or grant any
authority.  It is a Phase 1 semantic contract only.
