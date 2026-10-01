# LION typed status model

Status words are not one flat enum. Every status belongs to a semantic plane.

## Lifecycle

`EXPERIMENT → CANDIDATE → FORMALIZED → INTEGRATED → SUPERSEDED → ARCHIVED`

## Currentness

`CURRENT | SOURCE_BOUND | STALE | UNKNOWN | HISTORICAL`

## Authority

`UNAUTHORIZED | AUTHORIZED | REVOKED | EXPIRED | UNKNOWN`

## Execution

`REQUESTED | ADMITTED | EXECUTING | EFFECT_OBSERVED | RECONCILED | FAILED | UNKNOWN`

## Verification

`PASS | FAIL | SKIPPED | UNKNOWN`

## Deployment

`NOT_DEPLOYED | DEPLOYED | DEGRADED | UNKNOWN`

A component may simultaneously be `INTEGRATED` in lifecycle, `SOURCE_BOUND` in currentness, `UNAUTHORIZED` in authority and `NOT_DEPLOYED` in deployment. Flattening those claims into a single word such as "ACTIVE" is prohibited in new machine-readable artifacts.
