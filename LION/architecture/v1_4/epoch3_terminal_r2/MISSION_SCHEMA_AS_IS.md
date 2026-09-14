# Mission schema AS-IS

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

The additive envelope is normalized_schema_version=lion.mission-runtime/v1, projection_version=lion.mission-projection/v1, projection_revision, mission_summary and normalized_runtime. All pre-existing raw fields remain available.

normalized_runtime exposes identity, lineage, authority, source, objective, fleet, runtime, phases, receipts, environment, observability and gaps. Historical adapter records use HISTORICAL_PARTIAL_SCHEMA and HISTORICAL_NOT_RECORDED gaps. Current missing values remain null with NOT_RECORDED; they are not fabricated environment or authority evidence.

A recorded process cursor is retained. When absent, a recorded driver cursor is used only when the driver is ACTIVE/WAITING/BLOCKED/PAUSED and its matching phase is ACTIVE/RUNNING/WAITING/BLOCKED; the reason is RECORDED_DRIVER_CURSOR. Without that evidence, only one ACTIVE/RUNNING phase supports DERIVED_SINGLE_ACTIVE_PHASE; multiple active phases remain ambiguous, while none yields NO_ACTIVE_PHASE_RECORDED. DRIVER_* runtime strings are never displayed as observed material state. Revision hashing uses normalized content, not a newly generated read-clock timestamp.

Phase evidence_count comes from the backend SQL aggregate with evidence_count_scope=PERSISTED_TOTAL. Pure projections supplied only a recent message window instead label the count RECENT_MESSAGE_WINDOW. A displayed window count must not masquerade as a lifetime total.

New LPCL registration invokes validation before writes and persists schema_version plus the creation class in spec_json. Existing required source/LPCL identities and phase-plan validation remain. This is registration conformance for this entry point, not a claim that every legacy importer creates complete modern records.

Sources: runtime_projection.py; register_lpcl_mission, process_snapshot, recent_process_missions in tools/lion_mission_control_v3.py. Tests: test_mission_runtime_projection.py.
