# LION Operational Knowledge Plane

`/LION/` is the canonical navigation and coordination surface for evolutionary architecture and swarm operations. It is **not** an execution-authority source.

Every thread/drone starts here, then performs live observations before acting.

## Orientation

1. Read `catalog.json` and the protocols.
2. Read target, implementation and evolution maps.
3. Read mission, drone, channel and dependency registries.
4. Re-snapshot live GitHub and the authoritative registries named by the catalog.
5. Mark stale or conflicted projections before using them.
6. Read the work channel for the current mission/drone/swarm.
7. Continue only within separately granted authority.

## Source-of-truth precedence

For dynamic repository state, live GitHub observations override cached `/LION/` projections. Agent identity/lifecycle comes from Agent Registry. Branch-to-mission ownership comes from Branch Ownership Registry. Normative architecture comes from the referenced architecture documents. Chat history is context only and is never canonical state.

## Operational model

`TARGET -> OBSERVE -> GAP -> MISSION -> DRONE/SWARM -> BUILD -> VERIFY -> INTEGRATE -> OBSERVE -> RECONCILE -> UPDATE PROJECTIONS -> NEXT GAP`

Cross-thread communication uses addressable GitHub Issues and comments registered in `ops/channel-registry.json`. A drone posts structured messages to the target work channel; it never assumes access to another chat session.

## Safety

Registry/catalog presence does not grant credentials, runtime access, merge authority, release authority or deployment authority. Unknown, stale or conflicted state must be re-observed or fail closed before consequential use.
