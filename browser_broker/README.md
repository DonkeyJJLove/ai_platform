# LION R19 — broker-owned browser candidate

This is a feasibility candidate, not a production replacement for panel R17.4.
The existing 8780 panel is displayed without changing its source or data. A second
WebContentsView belongs to the broker process and hosts the actual ChatGPT site.
The Chromium profile is persistent; Node.js is unavailable to remote renderers.
There is no headless mode, external Edge process, Windows UI Automation, cookie
export, user-agent substitution or execution-policy override.

The implementation follows Electron's [WebContentsView](https://www.electronjs.org/docs/latest/api/web-contents-view)
and [security guidance](https://www.electronjs.org/docs/latest/tutorial/security).
Electron 44.4.3 and Express 5.2.1 are pinned in the lockfile. The UI adapter uses
page selectors in an isolated renderer world. Those selectors are not an OpenAI
compatibility guarantee. Changed markup, rejected embedding, unsupported login
popups or unavailable MCP must stop the feasibility test. No browser view has
been claimed to be authenticated based on process existence.

## Start on Windows, from PowerShell ISE

Open `Start-LION-Browser-ISE.ps1` in this directory and press F5. It installs the
locked dependencies in this checkout if necessary and launches a visible native
window. The launcher explicitly runs the pinned Electron package's official
installer: Electron 44 downloads its executable separately from `npm ci`. It
checks the installer exit code, `dist/electron.exe` and the binary version before
launching. Dependencies already matching the pinned versions are reused. Login and MFA are completed by the operator inside the SaaS view. The
queue starts stopped. No old relay inbox is imported and no SaaS request is sent
merely by starting the program or checking status. Close the window to stop it.
No autostart task or production service is created.

The panel URL defaults to `http://127.0.0.1:8780`. A missing panel is shown as a
load failure; no synthetic success page is substituted. The readback ingress is
`http://127.0.0.1:8791`. `LION_INGRESS_TOKEN_FILE` may point at the operator's
existing ingress credential file. That service credential is not a ChatGPT
session token. It is never printed or exposed to a renderer. Browser login uses
the browser's own profile. `LION_BROWSER_DATA` selects a dedicated local profile.

Use the native LION menu to inspect state, resume after login, or STOP. The status
menu writes `diagnostic-r19.json` in the local profile, without credential values.
Composer visibility is reported separately from MCP and end-to-end verification. The menu
is owned by the main process. Remote web pages receive no IPC bridge. Authentication
flows needing popups may fail because popups are denied in this initial candidate;
this is an explicit feasibility question, not permission to bypass the provider.

## Queue and upstream integration boundary

Express binds only to `127.0.0.1:8793`. Every endpoint requires a locally generated
control key from the broker profile's `control.key` file. Browser-originated
requests are rejected. The credential is an application control key; it does
not replace SaaS inference. Keep the profile under the operator's protected user
directory. Do not share it through a web server, repository or worker volume.

`POST /v1/wakes` accepts exactly:

```
request_id, mission_id, panel_thread_id, turn_id, turn_request_hash,
conversation_url, task_sha256, deadline_at
```

The task digest must match the R19 authorization. IDs refer to an already-created
MCP turn; no raw prompt or arbitrary executable code is accepted by this API.
Conversation URLs must belong to the configured ChatGPT project and match the
currently displayed conversation. Mission/thread/conversation bindings cannot be
changed by resubmitting a request. Only active `LION-R19-*` missions with
`READY_BOUND` preflight pass the main-process admission check. This check constrains
transport. The corresponding broker request must also have a matching mission
and thread, an unexpired deadline and an active unclaimed state. MCP PENDING
alone is insufficient: an old turn may belong to a cancelled broker request.
This is not a replacement for the task's runtime authority lifecycle.

SQLite WAL/FULL stores intent before dispatch. A crashed DISPATCHING request
becomes SEND_UNKNOWN. It cannot be resent automatically. One active external
send holds the queue until readback. Six turns per mission and eighteen total
accepted envelopes bound this candidate's database. Restart or resume does not
reset those counters. Deadlines are capped at twenty minutes.

The browser sends a bounded get-turn/complete-turn prompt. It does not execute
SentinelX mutations or orchestrate the material fleet in this feasibility stage.
Only authenticated ingress readback can produce RESULT_OBSERVED; that is not
RECONCILED or DELIVERED. The existing broker receipt/panel delivery path still
needs an explicit integration adapter and live validation. No incoming queue
adapter is connected automatically to the production relay in this candidate.

STOP prevents future sends, cancels unsent rows, and preserves uncertain external
work for readback. A request already delivered to SaaS cannot be guaranteed to
stop remotely. This limitation is exposed in the API, not hidden by CANCELLED.

## Verification and next gate

`npm ci --ignore-scripts` installs test dependencies without launching Electron.
`npm test` uses a real SQLite database and loopback Express server with fake model
and browser adapters. `npm run check` checks JavaScript syntax. These checks prove
local queue behavior, not Chromium rendering, Windows execution, model inference
or MCP availability in a ChatGPT session.

Before connecting production: prove native login, persistent session after restart,
correct project/conversation, an actual MCP roundtrip, source/runtime identity,
and same-thread receipt delivery. Then integrate the existing R18 semantic/model
modules and Docker workers under the R19 task budgets. Do not replace the live
panel with the simplified R18 candidate without checking feature/data parity.
