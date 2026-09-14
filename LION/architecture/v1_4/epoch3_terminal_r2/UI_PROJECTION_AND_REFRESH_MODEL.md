# UI projection and refresh model

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

R2 source consumes normalized mission detail and shared summary rather than separate adapter heuristics. Structured phase/worker detail preserves raw observations. Missing historical fields have explicit labels. Registry/detail fields derive from the same normalizer, though separate HTTP reads can still observe different database moments.

Candidate browser changes use keyed/per-field reconciliation for changing lists and panels. Stable mission, phase and worker identity should preserve DOM nodes, open details, focus, text selection and scroll during polling. A content revision is not a reason to replace the entire application root. Existing stale-response and queued-refresh guards remain relevant.

Supervisor cards and capability answers use the canonical supervisor projection. Phase buttons consume supported booleans and their current control token. Diagnostics remain untrusted UI_RUNTIME_ERROR reports with authority NONE; durable diagnostics are not execution receipts.

Acceptance must exercise unchanged polls, changing heartbeat/content, detail expansion, registry selection, route parity, response errors and console errors. Source edits and DOM fixtures do not certify a running browser deployment. Optional later choices include SSE and alternate RAW inspector layouts; preserving interaction and truthful data is required now.

Sources: deploy/mission-control/v3/control-v3.js, app.js, index.html; local_intelligence_gateway.py; ui_runtime_events.py.
