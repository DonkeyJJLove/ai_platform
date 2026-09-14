# Control plane AS-IS

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

The source operator path is local-intelligence gateway 8780 through LpclControlBridge to Mission Control 8766. LPCL registration validates and records intent; exact activation remains a separate existing boundary. The proposal model at 8772 and external SaaS session mediation are distinct model paths, not authority sources.

Mission Control reads mission/process records, driver checkpoints, scheduler state, worker snapshots and receipts. runtime_projection.normalize_snapshot is pure and additive. Both process detail and registry summary use its mission_summary. Registry collection calls process_snapshot(read_only=True) to avoid component synchronization writes. Default detail synchronization runs and commits before BEGIN; both modes then read all projected fields within one SQLite read transaction. This does not redesign every older status endpoint as strictly read-only.

New phase-actions are containment only: PAUSE/STOP delegate existing driver controls after a same-connection SQLite fence. Existing mission actions outside this bounded change retain their own contracts. No new execution, phase advancement, retry or material handler is introduced.

Sources: tools/lion_mission_control_v3.py; tools/lion_local_intelligence_runtime.py; cyber_lion/mission_control/runtime_projection.py and phase_control.py. Optional later design: SSE transport. Required current work: runtime acceptance and shared-view evidence.
