# Panel observability

The panel should expose state from independently owned evidence planes instead of maintaining parallel truth.

Minimum observable dimensions:

- source/runtime identity;
- mission and phase identity;
- currentness/freshness;
- model provider/transport/call state;
- operator command identity;
- authority decision and expiry where relevant;
- runtime admission;
- effect receipt;
- independent effect observation;
- reconciliation result;
- transport errors and renderer diagnostics.

UI diagnostics are useful evidence about the UI itself but are not authority or external-effect evidence.

Live deployment claims require runtime reacquisition. Source documentation alone can only establish source-bound behavior.

## Archive and functional boundaries (successor candidate)

Mission Control provides a compact summary of active process state and current phase predicates. Cluster owns material worker/currentness projection, logs, receipts and artifact metadata, while System owns logical/physical host domains, repositories and architecture dependency roles. Repeating the externally selected tab as an internal subtab is an information-architecture error. The archive-history projection must route only to the Mission Control owner's verified immutable snapshot and reasoning trails. Health and broker QUEUED status do not prove connected SaaS→logical drone→worker→LOCAL execution. See LION/architecture/v1_5/MISSION_EVIDENCE_ARCHIVE_R1.md for provenance and retention semantics.

**Manual receipt-only reconciliation:** Electron Intelligence menu uses canonical Mission Control GET response/receipt IDs to close earlier LOCAL statuses while the SaaS automatic consumer remains STOPPED. A response proof is not a mission phase execution receipt. New pending handoffs require their own current session binding.
