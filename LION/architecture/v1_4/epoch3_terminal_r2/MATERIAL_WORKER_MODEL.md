# Material worker model

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

The current recorded worker fields are pod_name, pod_uid, logical_id, phase, ready, restarts, pod_ip and observed_at, grouped under mission_id. Logical role joins use matching logical_id. Namespace comes from the mission record. These are observations, not claims about independent physical machines.

Normalized fleet exposes counts and copies of logical_workers/material_workers plus assignment_history and receipt_history. Each history is bounded to the newest 100 records and exposes metadata/digests rather than raw input payloads. The explicit history window is not a complete lifecycle archive. Exact UID is preferred for worker detail identity; absent UID requires explicit identity uncertainty. Do not invent node, image, resource usage or environment variables from a pod name. Source does not supply those fields in the scoped worker table.

Protocol events and receipts are mission-scoped unless exact worker identity establishes an association. Time proximity does not justify assigning an event to a worker. Query windows and readiness totals do not replace per-worker currentness evidence.

Worker observations are replaced on collection; the table is not a complete historical lifecycle ledger. Existing material controls retain their own admission boundaries. This R2 projection work adds no worker execution handler or raw environment-variable collection. Runtime deployment acceptance must verify real detail content, timestamps and identity preservation. Sources: material_workers DDL, apply_runtime/apply_runtime_for, runtime_projection.py and v3 worker UI.

Worker receipt ingress additionally requires the claimed material identity and positive lease generation. Under the SQLite writer lock it checks assignment identity, current driver generation and CLAIMED state before the first receipt. A request-supplied identity is a binding check, not authenticated worker provenance. The HTTP endpoint does not expose trusted internal ledger import.
