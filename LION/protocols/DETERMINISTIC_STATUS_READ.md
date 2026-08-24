# Deterministyczny odczyt statusu LION

Używaj tego protokołu dla każdego drona, wątku, dashboardu lub zewnętrznego audytora, który potrzebuje aktualnego stanu operacyjnego LION.

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

`observed_master` identyfikuje ostatni stan kodu bezpośrednio zaobserwowany przez projekcję statusu; nie musi być równy SHA commita zawierającego `status.json`. Pozwala to uniknąć niemożliwej samoreferencji. Późniejszy live `master` pozostaje zgodny ze stanem `CURRENT` tylko wtedy, gdy GitHub dowodzi ograniczonego, ciągłego łańcucha potomnego, a każdy commit pośredni zmienia wyłącznie dokładny allowlist projekcji wskazany powyżej. Każda zmiana kodu lub innego elementu repozytorium powoduje stan `STALE`; brak dowodu pochodzenia oznacza `UNKNOWN`.

`status_digest` identyfikuje kanoniczny logiczny stan floty. `revision_digest` wiąże ten stan z uporządkowanym łańcuchem rewizji. Rozdzielenie jest celowe: równoważny stan logiczny osiągnięty przez różne niezależne kolejności raportów może mieć ten sam digest stanu, zachowując jednocześnie odrębną, audytowalną historię rewizji.
