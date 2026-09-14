# Phase containment model

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

The new capability surface contains INSPECT plus PAUSE and STOP only. It does not add START, RESUME, RETRY, SKIP, phase execution or arbitrary verdict edits. PAUSE/STOP contain the existing driver associated with the exact recorded current phase.

Support requires a nonhistorical eligible mission, matching process and driver phase cursors, active phase status, EXPLICIT_USER_ACTIVATION, exact source head/tree, known observed handler and driver identity/generation. The token binds mission, phase/status, source, activation and driver state. Unknown handlers and stale tokens fail closed.

POST /api/v3/missions/{mission_id}/phase-actions accepts exactly phase_id, action and control_token. The 8780 bridge forwards the same bounded fields plus mission_id. mission_action receives an optional phase guard. fence_phase_action obtains BEGIN IMMEDIATE and re-reads/validates on the same connection used by existing PAUSE/STOP driver_transition. Stale rejection happens before transition or receipt writes.

Success then requires expected driver state, unchanged identity/generation/source and raw phase verdict, plus matching persisted PASS action receipt. Guarded driver_transition uses commit=False; the same guarded connection writes the lifecycle action receipt and commits state, checkpoint and receipt together. An exception before that commit rolls back all three; a separate FAIL receipt may then record the failed request. Unmodified callers keep transition's default commit=True behavior. No success may be inferred without readback.

Tests cover cross-connection stale generation rejection, competing writer exclusion, receipt/state mismatch, historical/unknown-handler denial and exact bridge forwarding. Real mission_action integration checks show an independent connection sees the old state/checkpoint until successful receipt commit; injected partial receipt failure leaves state and checkpoints unchanged and no PASS receipt. Sources: phase_control.py; mission_action; test_phase_control.py.
