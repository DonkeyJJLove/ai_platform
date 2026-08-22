# LION Swarm Communication Protocol

Independent threads cannot assume direct access to each other's chat state. Cross-thread coordination uses GitHub Issues/comments registered in `LION/ops/channel-registry.json`.

## Addresses

- `mission:<mission_id>` — mission work channel.
- `drone:<drone_id>` — resolves to the drone's registered work channel.
- `swarm:<swarm_id>` — shared temporary swarm channel.
- `group:<name>` — stable functional channel such as architecture/security/runtime.

Unresolved address => fail closed and report routing failure.

## Message envelope

Every inter-drone message records: `message_id`, `from`, `to`, `mission_id`, `type`, `correlation_id`, `evidence_refs`, `requested_action`, `created_at`, and optional `expires_at`.

Allowed message types: `DEPENDENCY`, `HANDOFF`, `BLOCKER`, `EVIDENCE`, `REQUEST`, `STATUS`, `RECONCILIATION`.

## Delivery

1. Resolve target address through channel registry.
2. Re-observe the Issue/channel state.
3. Post one structured envelope as a comment.
4. Sender records the evidence reference/correlation id in its own mission state when required.
5. Recipient reads channel during bootstrap/checkpoint and validates referenced evidence before acting.

## Swarm rules

- Group messages do not silently mutate every drone's state.
- Handoff requires explicit recipient acknowledgement/evidence when consequential.
- A blocker is routed to the smallest responsible channel first; escalate only when dependency ownership cannot resolve it.
- Do not duplicate canonical artifacts into comments; link immutable SHA/PR/run/evidence references.
- Communication never expands authority.
