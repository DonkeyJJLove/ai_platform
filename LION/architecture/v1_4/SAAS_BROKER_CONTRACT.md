# Cognitive SaaS broker

The canonical implementation is `tools/lion_saas_broker.py`, schema
`lion.saas-broker/v1`, migration version 6. The former
`lion_saas_session_bridge.py` only re-exports compatibility functions.
This document describes source behavior; it does not attest deployment or CI.

Pure cognition always has `authority_effect=NONE`. CONTROL_PLANE and THREAD
requests require no mission. MISSION adds optional existing mission context;
it does not activate LPCL or grant effects. The legacy request entrypoint keeps
its original LPCL validation and PENDING representation for old consumers.

New requests enter WAITING_SUPERVISOR. Their advisory deadline changes that to
WAITING_OPERATOR_OVERDUE without destroying the question. A mediator claims a
request with a short lease and a rotated token/generation. Expired claims return
to waiting; stale tokens and generations cannot respond. Response acceptance
uses a SQLite write transaction, stores an immutable receipt, sets RESPONDED
and progress RECEIPT_BOUND, and creates a global session binding. Duplicate
responses fail. Operator cancellation is terminal for waiting requests.
CREATED/QUEUED are accepted transitional queue states; FAILED/REJECTED are
reserved terminal states, not automatic deadline outcomes.

Session lease expiry is independent: NOT_ATTESTED, BOUND, EXPIRED. A successful
new mediated roundtrip establishes a new BOUND lease; previous BOUND evidence
becomes SUPERSEDED. Rebinding is represented by distinct immutable binding IDs,
not a fabricated provider login. Stale observation is projected separately as
freshness STALE. Transport is CHATGPT_SENTINELX_SESSION_MEDIATED, attested as
OPERATOR_SESSION_PLUS_CONNECTOR_ROUNDTRIP. This is not cryptographic provider
attestation. AUTO_HOP remains UNAVAILABLE; session BOUND never implies an
automatic provider invocation.

## API and consumers

Under `/api/v3/saas-broker`:

- POST `/requests`: scope_type, question, authority_effect; optional thread_id,
  mission_id and matching scope_id.
- GET `/status`, `/session`, `/pending`, `/requests/{request_id}`: redacted reads.
- POST `/requests/{request_id}/claim`: empty JSON, mediator authentication.
- POST `/requests/{request_id}/respond`: token, claim_generation, answer,
  model_identity, transport and attestation_class; mediator authentication.
- POST `/requests/{request_id}/cancel`: explicit cancellation.
- POST `/session/attest`: confirms a current accepted request/receipt pair;
  cannot invent or renew a lease; mediator authentication.

Mediator authentication uses X-LION-Mediator-Key and the private
`saas-mediator.key` adjacent to the Mission Control database. The key and response
tokens must never be printed or returned to normal UI reads. Keep the service
loopback-only. Provision the key for the local service owner; it is not a
provider credential.

The 8780 LpclControlBridge routes scoped requests and status to the new API.
The SaaS extension supplies thread context from the HTTP handler; explicit
composer LOCAL, SAAS and DUAL routes are supported. Historical mission drivers,
dual joins and old `/api/v3/saas/*` routes use the tested compatibility exports.
Legacy pending reads deliberately exclude new requests and their claim tokens.
Tests import both interfaces. Package admission includes the canonical broker.

`saas_thread_delivery.py` runs independently of browser polling. It discovers
durable request references in the thread database, reads accepted receipts, and
calls append_assistant_once with `saas:{request_id}`. BEGIN IMMEDIATE serializes
the deduplication check and insert. Deleted conversations are never recreated.
The browser reads the persisted message; it does not submit the broker response
or manufacture a receipt. UI_RUNTIME_ERROR diagnostics retain bounded context,
frontend revision and stack digest outside assistant messages.

## Operator mission reset

`tools/lion_mission_state_reset.py` is an offline operator utility, not an agent
tool or HTTP endpoint. Pause dispatch with mission_dispatch_paused=1, then stop
the identified Mission Control process before calling reset_offline. It obtains
a SQLite write lock, takes a WAL-safe backup, discovers mission columns and
foreign-key descendants, exports mission state, and deletes the captured row
identities transactionally. Logical SaaS/dual receipt references from historical
schemas are included. Unsupported implicit/composite foreign keys require
review and fail before deletion. Archive JSON replaces response tokens with
their digests; the private SQLite backup retains exact data.

The reset preserves schema, migrations, configuration, source inventories and
the separate thread database. It clears focus and scheduler counters and keeps
dispatch paused. The durable runtime_mission_reset marker prevents default
mission seeding and history import at restart. Empty views display NO ACTIVE
MISSIONS and the global broker remains usable. No fleet formation, automatic
delegation or executor authority is added.

Acceptance evidence must separately prove exact deployment, zero live missions,
the actual external-session/SentinelX roundtrip, durable one-message delivery,
expiry/rebind, duplicate rejection, browser reload, SQLite integrity and CI.
