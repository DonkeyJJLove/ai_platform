# Database schema AS-IS

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

The entry source audit inventories 42 tables across eight scoped modules. It precedes R2 additions; it is not an exhaustive current live inventory. The v3 database is /var/lib/sentinelx/uploads/lion-mission-control-v3/mission-control-v3.db. Generic observation and VKT stores are separate; 8780 ThreadStore uses --thread-db or the material-runtime directory parent/threads/lion-local-model.db.

| Owner | Tables/version role |
|---|---|
| v3 core/process | missions, logical_drones, material_workers, commands, mission_events, mission_meta, mission_process_specs, mission_phases, protocol_messages; original DDL unversioned |
| lifecycle | lineage, gaps, components, designs, audits, rollback points, action receipts; ledger ordinal 2, lifecycle-db/v2 |
| execution driver | drivers, checkpoints, attempts, gates, dual requests/receipts, compilations; ordinal 4, lifecycle-db/v3 |
| SaaS bridge | session bindings and handoff requests; ordinal 5, saas-session-bridge/v2 |
| scheduler | state/specs/assignments/receipts plus R2 mission_scheduler_turns and mission_scheduler_migrations; local migration version 1, lion.scheduler-storage-reconciliation/v1 |
| 8780 | threads/messages; UI diagnostics ui_runtime_events and ui_event_migrations version 1 |

R2 scheduler migration preserves rows, adds last_dispatch_order to historical turns only if absent, and checks SQLite integrity before/after. These are local source/test facts. No new live migration is certified here. Assignment/receipt uniqueness and replay semantics are separately tested; raw SQL schema alone does not prove receipt reconciliation.

The disposable-backup migration probe records 30 original tables preserved, two added scheduler tables, idempotent migration, integrity_check=ok, 25 mission projections and four historical records. Its scope is DISPOSABLE_SQLITE_BACKUP_OF_LIVE_DB and live_database_mutated=false. This is migration/projection evidence on a backup, not a live deployment claim. Evidence: r2-migration-probe.json.

Retention is largely unspecified in scoped source; worker rows are current snapshots, while thread deletion cascades messages. Do not interpret query limits as retention. Review actual table schemas and migration ledgers in read-only mode before deployment. Sources: schema-audit.json, r2-live-db.json, global_scheduler.py, storage modules and ThreadStore.
