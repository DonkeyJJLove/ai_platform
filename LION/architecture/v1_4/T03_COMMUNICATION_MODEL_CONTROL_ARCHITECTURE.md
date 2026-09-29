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

## R24 model-chat / protocol-fanout refinement

Task: LION-R24-MODEL-CHAT-PROTOCOL-SWARM-COGNITIVE-FANOUT-R1.

The operator UI now distinguishes two user-visible conversational surfaces:

~~~text
HUMAN MODEL CHAT
→ explicit LOCAL | SAAS | DUAL model route
→ Model Plane
→ response in model-chat thread

OPERATOR / SYSTEM PROTOCOL
→ mission | swarm | group | drone | worker target
→ frozen exact recipient set
→ participant-level cognitive trajectory
→ correlated participant response
→ Protocol Channel
~~~

The canonical separation is:

~~~text
MODEL_CHAT
!=
PROTOCOL_COMMUNICATION
!=
AUTHORITY_CONTROL
~~~

A model is a cognitive backend, not a participant identity. A material worker is
an execution substrate, not a logical drone. The three axes are independent:

~~~text
PARTICIPANT_IDENTITY
!=
EXECUTION_SUBSTRATE
!=
MODEL_PROVIDER
~~~

Protocol broadcast freezes recipient_set_digest and fanout_id when the operator
message is admitted. A participant joining later does not enter the existing
fanout. Each frozen recipient has one delivery and one independent cognitive
trajectory. One worker result can acknowledge only the responding_participant_id
carried by that assignment; it cannot mark both a logical drone and a material
worker as answered.

Canonical protocol identities are drone:<LD...> for logical drones and
worker:<MD...> for material workers. Historical drone:<MD...> input may be
accepted only as a compatibility alias; newly materialized deliveries and
responses use the canonical class-specific identity.

R24 material workers remain deterministic container orchestration. They do not
carry independent model weights. Every cognitively ready worker proves a current
route to the shared local model and a current route to Mission Control. The
worker status carrier exposes local-model capability, model-route currentness,
Mission-Control-route currentness, container identity and worker identity.

Protocol cognition is frozen per recipient at message admission. Material
workers are LOCAL-only cognitive executors. Logical drones accept LOCAL, SAAS or
DUAL cognition routes; when no explicit route policy is supplied, material
workers resolve to LOCAL and logical drones resolve to SAAS. Provider selection
remains independent from participant identity and carries no authority.

Each frozen participant owns one durable cognitive trajectory. LOCAL creates one
participant-bound LOCAL_MODEL_INFERENCE assignment and model-call lineage. SAAS
creates one participant-bound external handoff and reconciles only its returned
receipt. DUAL creates two independent legs: a local assignment and a SaaS
handoff, joined through the durable dual-result ledger. A DUAL participant
delivery is not terminal until both legs exist and the joined result is
reconciled. Ambiguous SaaS sends enter SEND_UNKNOWN-shaped trajectory states and
are not blindly retried.

PAUSE_SCOPE and STOP_SCOPE fence new cognitive admissions before routing.
Participant responses retain the source fanout_id/recipient_set_digest lineage
through the source message, preserve causation_id and correlation_id, and can
satisfy only the exact participant delivery. Authority remains NONE for all
cognition.
