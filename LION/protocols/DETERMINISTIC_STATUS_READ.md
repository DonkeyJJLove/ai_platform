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
    read-observed-master-commit-and-tree,
    fetch-observed-master-commit-and-verify-its-tree,
    resnapshot-live-GitHub-master-tree,
    if-live-master-equals-observed-master-compare-exact-tree,
    else-verify-observed-master-is-ancestor-of-live-master,
    enumerate-every-intervening-commit-in-order,
    require-contiguous-parent-binding,
    require-no-more-than-16-intervening-commits,
    require-every-intervening-path-is-projection-only,
    classify-CURRENT-STALE-UNKNOWN-CONFLICTED,
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
    resolve-source-refs

--projection-only-paths=
    LION/status.json,
    LION/architecture/implementation-map.json,
    LION/ops/mission-registry.json,
    LION/ops/drone-registry.json,
    LION/ops/future-mission-pool.json

--freshness-rules=
    exact-observed-commit-and-tree => preserve-status-epistemic-state,
    verified-descendant-with-only-allowlisted-projection-commits => preserve-status-epistemic-state,
    verified-descendant-containing-any-other-path => STALE,
    missing-or-broken-ancestry-proof => UNKNOWN,
    more-than-16-intervening-commits => UNKNOWN,
    arbitrary-descendant-without-path-proof => UNKNOWN

--require=
    deterministic-canonicalization,
    exact-observed-commit-tree-binding,
    exact-ancestor-binding,
    bounded-complete-intervening-commit-chain,
    closed-projection-path-allowlist,
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
    runtime-effect,
    treating-arbitrary-descendant-master-as-current,
    broad-LION-directory-freshness-bypass

--fail-closed=true
--continue-until=DETERMINISTIC_STATUS_RECONSTRUCTED_OR_EXACT_BLOCKER
```

`observed_master` identifies the last code state directly observed by the status projection; it is not required to equal the SHA of the commit that contains `status.json`. This avoids impossible self-reference. A later live master remains CURRENT-compatible only when GitHub proves a bounded, contiguous descendant chain and every intervening commit changes only the exact projection allowlist above. Any code or other repository change makes the status STALE; missing ancestry evidence is UNKNOWN.

`status_digest` identifies the canonical logical fleet state. `revision_digest` binds that state to the ordered revision chain. This separation is intentional: equivalent logical state reached through different independent report orderings can have the same state digest while preserving a distinct, auditable revision history.
