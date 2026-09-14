# Mission Control Database Lifecycle — Epoch 3 closure

`DOCUMENT_CLASS=LION_ARCHITECTURE_CANDIDATE` · `AUTHORITY_EFFECT=NONE` · `RUNTIME_EFFECT=NONE` until an exact LPCL is explicitly activated and a bounded effect adapter admits an operation.

## Why the database is part of the architecture

Mission Control is no longer only a dashboard over a single current run. At the Epoch 3 boundary it is an evidence and lifecycle plane spanning missions created under different schemas, adapters and evolution stages. A row missing `objective`, `current_phase`, protocol messages or a phase plan is therefore not automatically corrupt. For historical VKT-R3 and OSS Repository Test records those fields did not exist in the source schema. Treating `NULL` as `0.0%`, `no phase`, or an HTTP refresh failure destroys provenance and invents state.

The canonical rule becomes: **absence is typed by source stage**. Every mission is bound to a source schema and stage; every unavailable field carries an explicit reason. Historical records stay historical evidence. Re-running them produces a new revision or successor mission under the current schema; it never rewrites the old record into a modern mission.

## Database planes

Epoch 3 closes with a versioned control database and read-only evidence databases. The control database owns current mission registry state, mission-process state, lifecycle revisions, audits and receipts. Historical source databases remain immutable evidence carriers. Current Mission Control indexes them but does not promote them to authority.

The schema extension `lion.mission-control.lifecycle-db/v2` adds: `schema_migrations`, `mission_lineage`, `mission_data_gaps`, `mission_components`, `mission_design_revisions`, `mission_audits`, `mission_rollback_points`, and `mission_action_receipts`. Migration is additive and idempotent. The migration record is bound to source HEAD/TREE and a digest of the DDL. There is no destructive rewrite of old evidence.

Historical records are classified as `HISTORICAL_PRE_SCHEMA` with a stage such as `PRE_MISSION_PROCESS_SCHEMA:VKT_R3` or `PRE_MISSION_PROCESS_SCHEMA:OSS_REPOSITORY_TEST`. When the exact historical epoch cannot be proven, the system records `UNKNOWN_HISTORICAL_EPOCH`; it does not invent an epoch number. Missing modern fields are recorded as `NOT_RECORDED_AT_SOURCE_STAGE`.

## Lifecycle semantics

Mission Control exposes a common lifecycle vocabulary without pretending that every mission has the same material adapter. `REFRESH` reacquires currentness or reindexes a historical source. `AUDIT` snapshots mission metadata and creates findings. `RESTART` executes only when an exact bounded material adapter is present; otherwise it creates a design revision awaiting an exact LPCL. `START_COMPONENT` exists as an explicit contract but fails closed in Epoch 3 because a per-component material effect adapter is not yet installed. `ADD_COMPONENT` and `REDESIGN` create non-authoritative design revisions. `ROLLBACK` starts from an exact rollback evidence point and produces a rollback plan; it never performs database time-travel.

A rollback point created by audit is intentionally marked non-restorable for material state until runtime identity, material adapter, expected pre-state and rollback effect are independently bound. This keeps the old R7 lesson intact: source identity alone is not rollback authority.

## UI contract

Mission Control must display schema provenance directly. For a historical mission the operator sees the source stage and the exact list of fields that were not recorded. Progress remains `N/A`; no fake `0.0%` is generated. The four imported VKT/OSS records must return HTTP 200 from their process endpoint even though their IDs contain `::`, and their absence of process metadata must be explained as historical schema absence.

Mission actions are displayed according to capability state: `SUPPORTED`, `SUPPORTED_BOUNDED_EFFECT`, `DRAFT_REVISION_SUPPORTED`, `ADAPTER_REQUIRED`, or equivalent fail-closed status. A visible button is not authority; the backend contract and exact adapter determine whether an effect can occur.

## Epoch 3 closure invariant

Epoch 3 is not closed merely because the newest mission works. It closes when current missions and historical evidence can coexist in one Mission Control without false completion, false zeroes, accidental schema erasure or implicit authority. Database migration, schema compatibility, lineage, audit, rollback evidence and design revisions become first-class architecture before Epoch 4 begins.
