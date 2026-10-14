# LION R4/R11 desktop release and canonical conversation continuity

Status: ISOLATED_SOURCE_CANDIDATE. Parent PR #454 at head 00be49a1f72c696b756435396e1915c4a85c53ba. This document is source knowledge, not runtime or merge authorization.

## Observation and ownership

On 2026-10-14 the operator Desktop shortcut LION - panel i SaaS.lnk pointed to wscript.exe, Start-LION-Current-R24.vbs and hardcoded Start-LION-Desktop-PR432-9FB-R4.ps1, although the new PR #454 Electron source was installed and running. This is not a stable release switch.

The operator staging root had 59 top-level entries: 30 directories and 29 files. The source-only inventory listed seven explicitly referenced active items and 52 other entries requiring review. Its count is not an exhaustive recursive census of all nested material and grants NO deletion right.

The canonical SQLite showed 82 conversations, 22 mission-bound, 52 unbound and 8 frozen, with 15 external bridge records. Canonical BOUND or UNBOUND is distinct from an external ChatGPT SaaS bridge, provider session, and a verified request/response receipt. No inference of external binding follows from the selected visual tab.

The existing original owners remain the browser_broker Electron shell, cyber_lion canonical conversation domain, existing Mission Control broker and original Windows desktop operator. This source candidate creates no replacement broker, authority owner or scheduler.

## Target directory contract

~~~
%LOCALAPPDATA%\LION\
  operator\
    Start-LION.vbs
    Start-LION-Current.ps1
    current-release.json
    shortcut-backups\
  desktop\
    release-<exact-id>\browser_broker\
  r24-c2-staging-browser\  # protected user browser profile, unchanged
  control-panel\threads.db # original single-writer canonical data
  staging\                 # transitional/historical, not release selector
~~~

The stable Desktop shortcut points at one operator-owned VBS. VBS invokes one stable selector, which checks an explicit source-bound current-release.json selector with HEAD, TREE and file SHA-256 identities, then invokes the pinned release-specific launcher. A release is not selected just because its directory sorts newest. Missing/invalid current selection blocks; no default old version fallback.

The existing historic PR #432 shortcut and PR #454 active Electron remain unchanged until the original operator separately approves a specific installation. The initial Install-LION-Stable-Shortcut.ps1 requires explicit owner approval, preserves backup of old shortcut and does not copy, clear, migrate or replace existing broker data and browser profile. Future versions require independently admitted exact-ref pointer changes, not a series of rewritten Desktop .lnk files.

## Conversation and external bridge lifecycle

A new canonical conversation via + UNBOUND or + dla wybranej misji does not itself create any ChatGPT conversation. Mission BIND / DETACH creates a successor binding epoch; it cannot import or rebind an external SaaS session as a side effect.

Existing automatic provisioning runs only when a fresh SaaS consumer sends the first bounded prompt, so it is unable to complete while broker pending claims are unresolved and the consumer remains STOPPED. Replaying a broker request, clearing a ledger or assigning old claims to a new thread is not a valid repair.

The source candidate adds an independent, explicitly operator-confirmed adoption of an ALREADY EXISTING ChatGPT project conversation. The native SaaS view must show a concrete matching project-scoped thread URL. The original canonical consumer captures its exact thread ID, rechecks the canonical conversation state/epoch/context and browser URL after confirmation, prohibits any previous SaaS lane or bridge, performs at most one create-bridge write, and requires independent readback. It sends zero prompts. Duplicate external thread IDs across canonical conversations remain rejected by the existing conversation domain.

A recorded bridge is labelled BRIDGE RECORD / SaaS E2E NOT PROVEN, not a current validated session. A no-bridge conversation clears the previous UI external ref and disables stale Open / Rotate buttons. A frozen conversation cannot acquire a new external bridge. For legacy or outstanding requests, the original identity, claims, digests, status and lineage are preserved. A new safe conversation must have no earlier SaaS lane; historical work requires separate exact reconciliation.

## Staging hygiene without destruction

tools/lion_desktop_staging_inventory.py is the sole new bounded inventory utility: top-level filesystem read-only, explicit active names, SHA-256 of modest-sized files, no recursion, no rename/move/delete, and no output inside the monitored staging tree. UNKNOWN and symlink entries are held, not automatically cleaned. Other historical staging files may be archived only after confirming all live consumers, exact backup and original operator permission.

## Exact successor source-package identity

The R11/desktop continuity sources are included in the successor R5 exact Git-index source package (cooperative_production_r1/SOURCE_PACKAGE_CURRENTNESS_CCF_R5.md). R4 remains immutable historical source evidence; only R5 is the current source-validation owner after this candidate integration. R5 validation is neither desktop deployment nor verified SaaS E2E.

## Release and runtime gates

Source candidate and exact-head tests are not integration. Before runtime release: check original owners, reconcile source/truth carriers, review exact source and CI, obtain bounded operator activation, install beside the prior release, read back shortcut and selector, test one fresh manual bind without prior SaaS history, reconcile historical pending claims without blind retry, and verify a new complete SaaS response, broker response/receipt hashes and canonical delivered event.

No PR merge, LPCL start, broker replay, worker launch, credential extraction, historical deletion or SaaS deliverability claim is authorized by this documentation.

## Legacy conversation disposition without destructive migration

The companion `tools/lion_legacy_conversation_inventory.py` works against the
original canonical SQLite using URI `mode=ro`, `PRAGMA query_only=ON` and a
single consistent read transaction. It reports no user text, browser secrets
or complete external-thread URLs, and it cannot create a bridge.

An exact scoped historical readback on 2026-10-14 (not a self-refreshing live
assertion) classified **82** source conversations:
- **34** `NEW_EXPLICIT_OPERATOR_LINK_CANDIDATE`: no previous SAAS lane or
  stored external bridge; still requires operator choice, exact project-thread
  proof and admission
- **29** `LEGACY_SAAS_CLAIM_RECONCILIATION_REQUIRED`: at least one previous
  SaaS lane/event; no retrospective automatic adoption
- **11** `BRIDGE_RECORD_REVALIDATION_REQUIRED`: stored bridge records whose
  live ChatGPT delivery/session has not been proven
- **8** `FROZEN_HISTORICAL_PRESERVE`: never mutate frozen predecessor

The readback report is stored outside staging at
`C:\ProgramData\SentinelX\workspace\LION_R11_R4_OPERATOR_STAGING_AUDIT_20261014\CANONICAL_CONVERSATION_LEGACY_READONLY_CENSUS.json`,
SHA-256 `7ef7f26ed53be6543c2315ae74844928fd8f7cf693ba829744c51488d2bda65f`.
These numbers belong to that observation, not to a new architectural invariant.
All categories hold `authorized_to_bind=false`, `ready_to_send=false`
and `authorized_to_delete=false` until the original owner revalidates.

## PR #449 complementary list-scope integration (source candidate)

The operator-reported failure to refresh visible Model Chat conversations has an
existing primary UI owner in PR #449, exact historical source commit
7b563730a0a13b11c30be7bdb6357b2e33d952d1. This R11 successor integrates
only PR #449's source-only filter UI behavior and original scoped test,
without replaying its unrelated master source-package or truth carriers.
The existing cmcListStatus now distinguishes ALL vs exact MISSION scope, missing
mission selection, and an open conversation outside its current filter.
It prevents stale asynchronous list responses from replacing later user choice.
This does not automatically bind an external ChatGPT project conversation.

Existing parallel PR #450 concerns a separate, older four-view source and is not
substituted for the active six-view R4/R11 desktop or original operator shortcut.
The exact PR #449 and #450 lineages must be explicitly reconciled at integration
time to avoid overwriting an independently merged UI fix.

The source package for this extended increment is
cooperative_production_r1/SOURCE_PACKAGE_MANIFEST_CCF_R6.json. R5 remains immutable
historical input; both source-only package currentness and truth carriers are
recomputed after the final non-carrier delta. Runtime adoption is separate.

## P0 historical effect-surface relocation ledger

The exact PR #456 CI core failure (GitHub Actions run 38535489639, job
115757247033) is from the historical effect scanner's source-line-encoded
identity, not an additional database mutation. The original existing
conn.execute INSERT INTO conversation_external_bridges call in
cyber_lion/app_coordination/conversation_domain.py shifted from line 553
(P0 historic b6cc132095deb268b2754d2afc0634aeac5a7ac4) to line 561
(PR #456 head 5ba4d9165c6eb1ce0eeaca1484407139f7c40979).
The intervening source change is an 8-line fail-closed current
canonical binding/epoch/context fence before the original INSERT.

A target-specific regression in
cyber_lion/tests/test_p0_current_candidate_inventory_delta.py verifies
the historical and current complete AST of that exact INSERT are identical,
that its owner and write/taxonomy/authority class match, and that the
exact before/after surface digests remain pinned. The semantic P0 census
still requires 562 retained (561 literally identical + 1 AST-proven
relocated), 11 truly added, 5 truly removed, and 573 current observed
surface identifiers. Unclassified/taxonomy-unknown results still fail.
No scanner, historical receipt or inventory baseline is rewritten.

A successor source-package CCF R7 includes this new regression test
and references immutable R6 (and its predecessors). Carrier digest must
be recomputed last; no runtime or GitHub publication is implied.
