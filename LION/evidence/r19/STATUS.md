# R19 checkpoint — implementation candidate, live gate unresolved

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
