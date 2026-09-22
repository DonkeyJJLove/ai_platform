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

Use the native LION menu to inspect state, resume after login, or STOP. Startup and
the status menu write `diagnostic-r19.json` in the local profile, without credential
values. `Test-LION-Browser-ISE.ps1` reads current broker status and displays it in
ISE; it never resumes the queue. Reports include the real host, entrypoint path
and entrypoint SHA256, plus separate local and upstream observations. A health
response alone does not prove a service credential is valid.
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
conversation_url, task_sha256, deadline_at, claim_generation (optional)
```

The task digest must match the R19 authorization. IDs refer to an already-created
MCP turn; no raw prompt or arbitrary executable code is accepted by this API.
Conversation URLs must match the currently displayed conversation. Project
routes compare the stable project ID; a different display slug does not create
a different project. Direct `/c/<id>` routes do not encode project membership
and require native operator confirmation bound to that exact URL and configured
project before a consumer can start. Mission/thread/conversation bindings cannot be
changed by resubmitting a request. For normal chat, `mission_id` is explicitly
null and admission requires the locally bound THREAD scope with authority NONE.
For mission mode, only active `LION-R19-*` missions with
`READY_BOUND` preflight pass the main-process admission check. This check constrains
transport. The corresponding broker request must also have a matching mission
and thread, an unexpired deadline and an active unclaimed state. A claimed envelope
additionally requires the exact positive claim generation and a live upstream
claim lease. Omitting the generation cannot authorize a claimed request. MCP PENDING
alone is insufficient: an old turn may belong to a cancelled broker request.
This is not a replacement for the task's runtime authority lifecycle.

SQLite WAL/FULL stores intent before dispatch. A crashed DISPATCHING request
becomes SEND_UNKNOWN. It cannot be resent automatically. One active external
send holds the queue until readback. Six turns per mission or bound thread and eighteen total
accepted envelopes bound this candidate's database. Restart or resume does not
reset those counters. Deadlines are capped at twenty minutes.

The browser sends a bounded get-turn/complete-turn prompt. It does not execute
SentinelX mutations or orchestrate the material fleet in this feasibility stage.
Only authenticated ingress readback can produce RESULT_OBSERVED. In mission
producer mode, the Node relay then submits that exact answer to the existing Mission Control respond endpoint
and independently checks the response digest and receipt in a fresh GET before
RECONCILED. This is broker receipt reconciliation, not proof of panel delivery.
No relay is activated by installing or opening this candidate.

## Connect normal panel chat (THREAD consumer)

Normal panel chat creates a THREAD request with `mission_id: null`. The existing
panel path already creates the ingress turn. `src/thread-consumer.cjs` consumes
that existing turn; it neither claims the broker request nor creates a second
turn nor writes an upstream response. The mission producer described below is
not the adapter for these ordinary chat requests.

1. Close the previous candidate window and run this checkout's ISE launcher.
2. In the right view, open a concrete conversation inside the LION project where
   LION-MCP-R2 is available. Leave its message composer empty. A project landing
   page is not a conversation.
3. Use **LION > Połącz rozmowę SaaS z wątkiem panelu** and select the matching
   panel thread. For a direct `/c/` address, the same dialog asks you to confirm
   that the visible conversation belongs to LION_EVOLUSION; the URL alone cannot
   establish that. If it has no queued question yet, send one panel question first
   so the thread can be selected; that initial question is not replayed.
4. If prompted, select the existing **local ingress service credential file**
   (`secure-mcp-ingress.token`). This is not a ChatGPT session token or OpenAI API
   key. The app validates access to authenticated `/v1/state` before saving only
   the file path. It does not extract login data or generate a replacement key.
5. After the connection confirmation, send **one new question** from the left
   panel with CHATGPT selected. Only new ingress events after this binding are
   eligible. Observe the actual question/answer on SaaS, MCP completion and the
   answer's delivery back to the same panel thread.

Binding persists the exact thread and conversation. Restart keeps the queue
stopped and requires native resume; it does not replay events from downtime.
The consumer only reads local service endpoints. It checks the exact request,
turn hash, thread, cognitive authority, deadline and any observed claim lease
before dispatch. The existing producer remains responsible for delivering the
MCP result to Mission Control and the panel. RECONCILED means an independently
matching upstream response digest and receipt, not verified panel rendering.
An expired producer claim blocks dispatch; this adapter does not silently renew
it. Missing service access, unavailable MCP tools or competing legacy senders
remain deployment prerequisites, not successful handshakes.

Do not enable two senders for the same scope. Historical unknown sends stay
unresolved until independently reconciled; this candidate does not retry them.
The bounded fixture tests prove the consumer contract, not a native SaaS roundtrip.

## Scoped Node relay candidate

`src/relay.cjs` runs inside the browser owner's Node main process. It uses the
existing `/api/v3/saas-broker` and ingress REST contracts. It does not launch the
old Python/Firefox/hidden-browser driver or a model API client. To configure a
controlled test, the operator supplies existing local service credential file
paths in `LION_INGRESS_TOKEN_FILE` and `LION_MEDIATOR_KEY_FILE`, and sets
`LION_R19_RELAY_SCOPE_FILE` to a JSON file with `mission_id`, `thread_id`,
`conversation_url`, and `task_sha256` matching the authorized R19 task. IDs must
come from the real mission and panel thread; the URL must be the actual project
conversation. These service credentials are unrelated to ChatGPT login cookies.

The queue must be resumed through the native menu. The relay only selects new
requests created after its process started, in that exact mission/thread, with
READY_BOUND mission preflight. It does not import old inboxes. A maximum of six
requests per mission and eighteen recorded handoffs bounds the durable journal.
Claim and turn creation intent is persisted before their respective POST. An
ambiguous claim/creation needs operator reconciliation; it is never replayed.
A lost respond acknowledgement is reconciled using the response digest and
receipt GET, with no repeated POST. Expired or replaced claims block dispatch and
delivery; this candidate does not silently renew the existing five-minute claim.
The queue may therefore require reconciliation for a longer inference.

Claim response tokens are kept only in the broker's private SQLite journal and
removed after receipt reconciliation. They never enter the page, prompt, HTTP
status or diagnostic report. Protect the complete profile, including WAL files.
STOP prevents further mutations; readback can still reconcile a response already
accepted upstream. A validated conversation is saved on navigation and restored
on startup, without restoring send permission or navigating to an auth URL.

Before enabling this adapter in production, complete native MCP/login/restart
feasibility and replace the legacy relay under a controlled deployment. Do not
run both consumers for the same scope. Windows configuration, panel receipt
consumption and actual SaaS inference still require live verification.

STOP prevents future sends, cancels unsent rows, and preserves uncertain external
work for readback. A request already delivered to SaaS cannot be guaranteed to
stop remotely. This limitation is exposed in the API, not hidden by CANCELLED.

## Conversation address diagnostics (fix4)

The previous validator required one exact project URL prefix, including its
human-readable slug. It rejected direct conversation routes and a matching
project ID with a different or absent slug. The current parser separates URL
identity from project membership. It retains exact conversation binding and
rejects a different project ID, other origins, credentials in the URL and
unreviewed query/fragment routes. It does not turn a generic ChatGPT conversation
into a verified project conversation automatically.

**LION > Adres rozmowy SaaS** shows the current route and expected project.
Binding failures display a specific reason and the actual address without query
values, fragments or authentication data, and save `binding-error-r19.json` in
the same profile. The general diagnostic report includes the same observation.
The screenshot did not expose its actual URL; it establishes a binding-stage
failure, not which route variant caused that failure. Native behavior remains
to be observed after installing this correction.

To update an existing installation, close its window, copy the archive's
`browser_broker` contents over the existing application directory, then start
its ISE launcher. Preserve the existing `node_modules` and user profile. This
reuses the already installed pinned dependencies and browser login profile.

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
