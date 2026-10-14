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

## Release and runtime gates

Source candidate and exact-head tests are not integration. Before runtime release: check original owners, reconcile source/truth carriers, review exact source and CI, obtain bounded operator activation, install beside the prior release, read back shortcut and selector, test one fresh manual bind without prior SaaS history, reconcile historical pending claims without blind retry, and verify a new complete SaaS response, broker response/receipt hashes and canonical delivered event.

No PR merge, LPCL start, broker replay, worker launch, credential extraction, historical deletion or SaaS deliverability claim is authorized by this documentation.
