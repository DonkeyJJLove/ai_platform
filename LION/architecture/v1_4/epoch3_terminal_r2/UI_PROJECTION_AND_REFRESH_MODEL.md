# UI projection and refresh model

The recent-mission list serializes its bounded normalized read batches with an independent process-local lock. This prevents concurrent SQLite/deep-copy loops from exhausting the polling latency budget observed on the deployed host. Each request reads current data; there is no summary cache, authority cache, or lifecycle writer lock shared with this read lock.

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

R2 source consumes normalized mission detail and shared summary rather than separate adapter heuristics. Structured phase/worker detail preserves raw observations. Missing historical fields have explicit labels. Registry/detail fields derive from the same normalizer, though separate HTTP reads can still observe different database moments.

Candidate browser changes use keyed/per-field reconciliation for changing lists and panels. Stable mission, phase and worker identity should preserve DOM nodes, open details, focus, text selection and scroll during polling. A content revision is not a reason to replace the entire application root. Existing stale-response and queued-refresh guards remain relevant.

Supervisor cards and capability answers use the canonical supervisor projection. Phase buttons consume supported booleans and their current control token. Diagnostics remain untrusted UI_RUNTIME_ERROR reports with authority NONE; durable diagnostics are not execution receipts.

Acceptance must exercise unchanged polls, changing heartbeat/content, detail expansion, registry selection, route parity, response errors and console errors. Source edits and DOM fixtures do not certify a running browser deployment. Optional later choices include SSE and alternate RAW inspector layouts; preserving interaction and truthful data is required now.

Sources: deploy/mission-control/v3/control-v3.js, app.js, index.html; local_intelligence_gateway.py; ui_runtime_events.py.

The later source correction 68accb2 adds POST /api/v3/missions/{existing-id}/focus with exactly an empty JSON object. It changes only focus metadata and records a FOCUS_CHANGED event plus a CONTROL_DB_METADATA_ONLY receipt with authority_effect=NONE in one transaction. Historical and current targets are allowed; missing targets fail before changes; repeating the same focus is idempotent. Driver, phase, mission authority and all other tables remain unchanged in integration tests. This permits reversible PIN/FOCUS acceptance without mission registration or activation. Package identity was refreshed in 813c2bb.
