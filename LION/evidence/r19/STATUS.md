# R19 checkpoint — implementation candidate, live gate unresolved

## THREAD transport diagnosis, 2026-09-21 21:15–21:17 UTC

The screenshot's queued request suffix a44dc3a4ea3b36fd resolves to
`saas-8710f6c7d63d49f2a44dc3a4ea3b36fd`, thread
`8e96590f60024748b2533958bf7c00f4`, scope THREAD, mission_id null, authority NONE.
Its existing ingress turn is `turn_5d86dd8c-939d-49fe-9698-e3395b550676`, hash
`33dc414ff45da385cc0d76c47276caf000e3df171808bcce2b90d6accd85b9b3`.
Independent Mission Control and MCP/ingress reads showed WAITING_SUPERVISOR /
PENDING, response null, and no receipt. The request was created at 21:05:42 UTC
and expires at 21:20:42 UTC; these are timestamped observations, not a claim
that it remains eligible. No historical turn was completed or replayed.

The screenshot's visible answer has LOCAL_MODEL_DIRECT provenance. Its claim
to be GPT-4 is not model identification. The current provider dropdown and that
older answer alone cannot prove an automatic fallback for this queued request.
Focus-mission status reported zero pending while the global pending endpoint
contained THREAD requests; the two observations have different scopes.

The old background driver's recorded bridge is MINIMIZED_EDGE_UIA, with stale
DEGRADED state and SEND_UNKNOWN_RECONCILE_REQUIRED. It does not identify the new
embedded browser. No relay state file for the exact latest request was found.
The previous R19 fix2 producer accepts only configured R19 missions, so it
cannot consume this ordinary THREAD request. That adapter selection was wrong.

The new ThreadConsumer reads existing ingress events after an explicit native
thread/conversation binding. It does not claim requests, create duplicate turns,
or POST answers. The original producer retains the response/receipt path. A
native menu validates local service access and an empty SaaS composer before
resuming; STOP during configuration prevents a late resume. No ChatGPT login
credential is exported. Thirty-seven local tests pass with real SQLite and fake
upstream/browser adapters, including normal THREAD roundtrip, identity mismatch,
claim rollover, STOP, historical-event exclusion and response digest mismatch.

This is source correction, not a deployed repair. Windows producer source and
same-thread delivery remain unverified; the SentinelX MOON host is WSL and its
allowlist does not expose native Windows execution. No policy change or alternate
interpreter was used. The existing service credential, actual project conversation
with MCP tools, exclusive sender ownership and native roundtrip remain live gates.
The earlier fix2 CI (3257 tests, two skips) applies only to its old commit; current
candidate CI must be reacquired. Earlier checkpoints follow unchanged.

## Continuation after native startup, 2026-09-21

The operator's fix1 output reports Electron PID 38800 on Windows. Their screenshot
shows the broker-owned panel and ChatGPT views with the signed-in account and
LION_EVOLUSION project. This is evidence of native rendering and visible login;
it does not demonstrate MCP use, receipt delivery or restart persistence. The
operator reports the requested checks already done. No diagnostic JSON was
available in this workspace or resolved by the targeted Library search, so its
specific contents are not inferred.

Fresh observations at 20:40 UTC still show UNBOUND/EXPIRED, automatic_hop
UNAVAILABLE and no pending request. MOON's ingress service is active at PID 211
with ExecStart `/usr/bin/node /opt/lion/lion-turn-ingress-node-r2/server.mjs`.
Its Windows PowerShell command remains unavailable through the observed SentinelX
allowlist. No policy change or alternate-interpreter workaround was attempted.

The next candidate adds a Node relay using the existing claim/turn/respond
contracts. It accepts a claimed request only with an exact generation and live
lease. SQLite journals claim and turn creation before their effects. Ambiguous
mutations require reconciliation; a lost respond ACK is resolved with GET rather
than a repeated POST. New requests must match an explicitly configured R19
mission, thread and actual conversation, READY_BOUND preflight, and process-start
cutoff. It does not import the historical queue or create authority. No relay is
enabled without configuration and native resume. The existing five-minute claim
lease can block longer inference; renewal is not fabricated.

The same validated project conversation is now persisted and restored. Startup
produces a diagnostic report; the new ISE read-only script prints current status
with real host, entrypoint and SHA256, without credential values. Twenty-seven
local tests pass using SQLite and fake upstream/browser adapters, including
claim rollover, cancellation, STOP, lost acknowledgements and receipt mismatch.
They do not prove a real model response. Broker RECONCILED is explicitly distinct
from same-thread panel DELIVERED. This change is candidate source only; Windows
installation, native MCP feasibility, panel E2E and Docker canary remain open.

The sections below preserve the earlier checkpoint chronology.

The exact uploaded TASK was authorized by an explicit user message. Its original
UTF-8 CRLF bytes and SHA-256 are preserved alongside a separate activation record.
This is developer-session authorization, not a fabricated Mission Control UI event.

The remote master observed on 2026-09-21 is
`da4dbd7b27b4833c0debddf839e003f2ce170d5c`. All 35 non-master branches returned by
the repository branch listing were compared against that commit. The JSON report
contains each head, merge base and file set. Behind-only branches are already
contained in master. Diverged branches remain available; none were deleted or
blindly merged. PR 364's exact-head Core run 35582382692 failed its tests. PR 365's
five returned exact-head workflows succeeded, but its simplified panel is not
proved equivalent to the live R17.4 source. PR 366's Workspace Agent transport is
outside the chosen R19 browser path.

A selective port from PR 363 fixes fresh mission self-lineage and materializes
proposal-only generic phase specs. The two implementation files and regression
test were reviewed and transferred without the old minimized-Edge driver changes.
Its 10 hybrid-execution tests pass locally. No host activation was performed.

The new `browser_broker` component contains a visible Electron WebContentsView,
persistent isolated profile, Express control boundary, durable SQLite queue,
MCP turn readback, no-blind-retry handling and STOP. Sixteen tests using real
SQLite and local HTTP with fake browser/provider adapters pass. These are local
contract tests, not SaaS or native-rendering evidence. Production still uses the
previous deployment; the new component is not wired into the old relay inbox.

Live observations show active Node ingress 0.2.0 on MOON WSL, at
`/opt/lion/lion-turn-ingress-node-r2/server.mjs`, PID 211, source SHA-256
`30a5f727005302729c841d56fa21a63062be13e6ef5512957d1ce2f62542ecea`.
The LAB-DEBIAN tunnel service is active. Mission Control on LION-AUTH-LAB reports
WAITING_MEDIATOR, automatic_hop unavailable, no pending broker request and a fresh
DEGRADED relay heartbeat. Those are independent observations, not an inference
that the browser session is healthy.

The executor has no native display. The SentinelX connection named MOON is WSL,
not a Windows desktop execution channel; its allowlist does not expose PowerShell.
The panel was not reachable from that WSL loopback or the observed Windows gateway.
This does not prove the Windows panel is down. Docker on LION-AUTH-LAB denied
socket access; the permitted sudo command required an interactive password.
No policy change, interpreter substitution or socket-permission change was made.

Next gate: run the pinned candidate on MOON in the operator's desktop session,
prove rendering/login/profile restart and MCP availability. The ISE launcher
creates no autostart task and starts the queue stopped. User login is needed;
a request to reauthorize the already approved R19 scope is not needed.
After feasibility passes, connect the upstream panel/relay adapter, reconcile
receipts into the same thread, then bind the local model and two-worker Docker
canary under the approved task limits. Those dependent phases remain unfinished.
Do not merge/deploy this candidate as a completed fleet or complete R19 mission.

Follow-up observations at 14:38–14:40 UTC: the current broker binding expired at
14:36:47 UTC; status is now UNBOUND/EXPIRED and automatic_hop remains unavailable.
Read-only MCP lion_next_turn returned turn_ed62e0cb-c3e9-4d4c-95d0-e8b4a2f46c16
as PENDING, with request hash
569e943baea50c6775551cfb1dc50a7d53f048b9a4f49b4f71b40b21c6a01c1d.
The same identity/hash exists in the MOON ingress data/turns.jsonl prefix read
(the file read was truncated; it is not a full queue census). The corresponding
Mission Control request saas-a8f909a16d1d487b9423b5dd729ae6f3 is CANCELLED_BY_OPERATOR.
This is a cancellation propagation gap, not an authorized pending user request.
The candidate therefore rechecks the broker request's active state, exact scope
and deadline before dispatch, including after asynchronous ingress readback.
No historical request was completed, deleted or replayed. Matching stored turn
identity supports the ingress association; it does not prove tunnel topology alone.

The first publication is draft PR #367. Its Bandit and Full Symbol Census checks
passed; Core was still running when this follow-up source change began. Those
checks do not apply to a later head. The optional local full-suite run was
interrupted without a terminal result and is not claimed as PASS. The focused
truth/currentness suite ran 50 tests with two live-evidence cases explicitly
skipped; the exact candidate subject was separately recomputed from Git leaves.

The first R19 Core run completed 3,257 tests and found three package-identity
failures: the reviewed Mission Control port changed its bytes, while the restart
package manifest still pinned the previous source. Only the corresponding
mission_control_v3.py manifest entry was regenerated from the actual reviewed
file (SHA-256 7f40ff2b950e9beace598bbfaec064e3edf70c36ca6fe68cd331b97841a0db87).
The manifest validator and all drift/missing-file checks are unchanged. The
12 restart-package tests plus 10 hybrid-execution tests pass after this fix.
The subsequent exact-head CI result must still be read; no prior run is reused.
