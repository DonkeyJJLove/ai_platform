# Deterministic LION Status Read

Use this protocol for any drone, thread, dashboard or external auditor that needs current LION operational state.

```text
READ LION-DETERMINISTIC-STATUS

--repo=DonkeyJJLove/ai_platform
--status=LION/status.json
--mode=STRICT_READ_ONLY
--authority=NONE

--procedure=
    fetch-LION/status.json,
    validate-schema,
    recompute-status-digest,
    recompute-revision-digest,
    validate-previous-digest-bindings-when-prior-revision-is-available,
    resnapshot-live-GitHub-master-tree,
    compare-live-vs-observed,
    read-governor,
    read-missions,
    read-drones,
    read-role-assignments,
    read-formations,
    read-dependencies,
    read-blockers,
    read-current-actions,
    read-history,
    read-pending-messages,
    resolve-source-refs,
    classify-CURRENT-STALE-UNKNOWN-CONFLICTED

--require=
    deterministic-canonicalization,
    no-chat-history-as-source-of-truth,
    no-unknown-to-clean-conversion,
    no-status-to-authority-conversion,
    live-master-resnapshot

--output=
    STATUS_REVISION,
    STATUS_DIGEST,
    REVISION_DIGEST,
    LIVE_MASTER,
    STATUS_MASTER,
    FRESHNESS,
    GOVERNOR,
    ACTIVE_MISSIONS,
    ACTIVE_DRONES,
    ROLE_ASSIGNMENTS,
    FORMATIONS,
    DEPENDENCIES,
    BLOCKERS,
    CURRENT_ACTIONS,
    RECENT_COMPLETIONS,
    PENDING_MESSAGES,
    CONFLICTS,
    NEXT_EXPECTED_ACTION,
    REQUIRED_CONTACTS

--prohibit=
    mutation,
    inference-of-permission,
    fabricated-state,
    synthetic-heartbeat,
    status-update,
    runtime-effect

--fail-closed=true
--continue-until=DETERMINISTIC_STATUS_RECONSTRUCTED_OR_EXACT_BLOCKER
```

`status_digest` identifies the canonical logical fleet state. `revision_digest` binds that state to the ordered revision chain. This separation is intentional: equivalent logical state reached through different independent report orderings can have the same state digest while preserving a distinct, auditable revision history.
