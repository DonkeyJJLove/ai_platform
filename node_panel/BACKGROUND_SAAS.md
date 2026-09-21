# Background SaaS activation — R18 R2 candidate

Status: implemented repository candidate; live activation NOT VERIFIED.

The previous relay created durable turns but could not start inference. The new
WorkspaceTrigger and WakeDispatcher integrate activation with the existing
TurnReconciler. AUTO is SaaS-first; LOCAL remains an explicit direct-inference
route. The panel polls its current thread so late answers remain visible.

SOURCE_REF: src/workspace-trigger.js, src/wake-dispatcher.js,
src/thread-store.js, src/turn-reconciler.js, src/server.js.
TEST_REF: test/wake.test.js, test/integration.test.js, test/security.test.js.

## Durable activation

New SaaS bindings atomically enroll in saas_wake_outbox. Existing historic
bindings are not enrolled or drained. Mission identity is stored in the request,
forwarded to the broker and ingress, and included in the context digest. Mission
requests include a bounded Mission Control snapshot for the SaaS supervisor.

After exact-turn readback, the dispatcher checks broker status, live thread,
turn hash, command/thread/mission binding and mission state. It leases the
outbox row before sending. The event body and idempotency key remain immutable
across restarts. Retries have backoff and a three-attempt ceiling; permission
rejection is terminal for automatic retries. A crashed lease can be retried
after expiry with the original event key. Cancellation cannot retract an event
already accepted by the remote provider; execution admission remains necessary.

An accepted trigger is not completed inference or fleet execution. Only the
existing MCP completion, broker receipt and same-thread delivery reconciliation
can finish the chat request. No claim of live autonomy is emitted by readiness.

## Deployment dependencies

Configure LION_WORKSPACE_AGENT_CHANNEL with a published agtch_… API channel and
inject LION_WORKSPACE_AGENT_TOKEN using the approved secret-management mechanism.
Do not store credentials in Git, journal files, the panel, or chat. The token
must have Workspace Agents scope; ingress and tunnel credentials are unrelated.
No credential is generated or borrowed by this change. The code uses the
Workspace Agents control API, not the model inference API, and has no browser
or Codex runtime dependency. Availability, workspace permissions, product
compatibility and billing must be verified on the user's account before use.

The published SaaS agent must have LION-MCP-R2 access and the project supervisor
instructions: inspect the exact turn, validate lineage, perform semantic and
heuristic reasoning and complete only that turn. A model name must come from
the real agent configuration; the broker must not invent Sol/Astra identity.

Official contract:
https://learn.chatgpt.com/workspace-agents/trigger-runs
https://learn.chatgpt.com/workspace-agents/authentication

## Fleet boundary and remaining work

The intended loop remains SaaS logical reasoning → local model proposals →
mission contracts/admission → scheduled workers → receipts → reconciliation.
The 128 logical roles (16 cohorts of 8) share 64 material executors; these are
not 128 concurrent model calls. Existing Mission Control remains owner of
phase contracts, authority/currentness, local planning and worker admission.

This patch does not implement a new fleet executor, does not enable the SWARM
chat route, does not submit arbitrary SaaS text as shell actions, and does not
automatically activate a stopped mission. A structured SaaS proposal-to-existing
mission-driver binding and full SaaS/local/worker roundtrip remain unverified
and unfinished. Keeping the existing rejection is deliberate until that binding
is implemented; it is not evidence of fleet integration being complete.

Live R17.4 was not replaced. The actual Mission Control source read remains
blocked by the SentinelX path allowlist. Workspace channel/token availability
is not confirmed. No live SaaS trigger or model billing test was performed.
Local tests use a controlled fake HTTP provider and prove state-machine behavior
only. Full acceptance still requires an observed live trigger, SaaS inference,
local delegation, admitted worker receipt, same-thread delivery and restart.
