# LION Epoch 4 — Communication / Model / Control Architecture

TASK: `LION-E4-T03-FINAL-VERIFICATION-AND-CANDIDATE-IDENTITY-R1`

Status: candidate source architecture. Authority effect: `NONE` for communication and model cognition; control authority remains independently mediated.

## Invariant

```text
COMMUNICATION_PLANE != MODEL_PLANE != AUTHORITY_CONTROL_PLANE
```

## Communication Plane

Normal operator, Supervisor, drone and worker communication uses one durable LION operator-message plane:

```text
LPCL Panel / participant
→ thread_id
→ mission_id + target + binding_revision
→ operator_messages / operator_message_deliveries
→ assignment / consumption
→ process revision application
→ correlated response
```

`correlation_id` binds a conversation trajectory. `causation_id` binds a response or process event to the message that caused it. Persisted or delivered does not imply applied.

Cross-mission thread targets fail closed. Repeated `client_id` with identical payload is idempotent; the same client identity with changed payload is a conflict.

## Model Plane

Model invocation is a typed cognitive operation attached to an existing mission task/assignment. It is not the default operator chat transport.

A model call records mission, phase, task, assignment, logical drone, material worker, requested capability, provider/model/transport, routing reason, context revision, input/result digests and downstream consumer.

Supported transport classes in this candidate:

- `LOCAL`
- `CHATGPT_OPENAI_SECURE_MCP_TUNNEL`
- `CHATGPT_FIREFOX_PROJECT_MEDIATED`

Explicit transport bindings cannot be rewritten by mediator heartbeat.

Firefox-project mediation is optional model capability only. Normal LPCL Panel readiness must not depend on port 8790 or an authenticated browser session.

External browser send durability is:

```text
INTENT_DURABLE
→ SEND_ATTEMPT
→ SEND_UNKNOWN | SEND_CONFIRMED
→ RESPONSE_RECONCILED
```

`SEND_UNKNOWN` is reconcile-first with automatic retry count zero.

## Control Plane

Operator control remains independent of communication/model availability:

- `OPERATOR_PRIMARY`
- `control_epoch`
- `PAUSE_SCOPE`
- `STOP_SCOPE`
- `TAKE_CONTROL`
- `RELEASE_CONTROL`
- explicit resume
- worker lease/fencing and stale-result preservation

UI controls are disabled until pairing is confirmed, and backend submission independently fails closed without a paired operator session.

## Source lineage

- PR359 semantics own the shared operator bus baseline.
- PR356 operator-control/fencing semantics are retained.
- PR357 behavior is represented as explicit equivalence tests over the shared bus rather than a second message store.
- PR358 provider-selector semantics are superseded for normal communication; retained context, pairing, model-route diagnostics and browser opt-in requirements remain.
- PR348 backup and PR353 execution-currentness semantics are integrated.
- local R3 Firefox mediation is retained only as optional Model Plane transport.
