# SaaS supervisor AS-IS

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

The canonical projection is lion.supervisor-projection/v1. It separates channel, session, model, transport, session scope, pending requests, last receipt, lease, automatic-hop capability, freshness and unknown reasons. Card and capability answers consume the projection rather than generic hard-coded availability text.

A global binding has scope GLOBAL_SUPERVISOR_CHANNEL and authority NONE. It is independent of mission focus. Pending handoff deadlines may become overdue without deleting durable requests; the session lease expires separately. EXPIRED/UNKNOWN observations must not be re-labelled BOUND merely because an old attestation exists. Automatic local-to-SaaS transport is reported from supplied evidence and is not inferred from external operator access.

Current source uses CHATGPT_SENTINELX_SESSION_MEDIATED transport and operator-session plus connector-roundtrip attestation. These facts do not constitute cryptographic provider attestation. Projection code does no I/O or session mutation; older bridge status helpers still update expiry/progress and commit.

Sources: tools/lion_saas_session_bridge.py; cyber_lion/mission_control/supervisor_projection.py; gateway and v3 UI consumers. Live session validity and exact request/receipt behavior require post-deployment readback; this candidate document does not renew any binding.

