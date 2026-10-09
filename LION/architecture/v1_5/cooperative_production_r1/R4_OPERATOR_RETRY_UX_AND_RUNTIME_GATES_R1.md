# R4 operator retry: mission deletion, canonical cognition, and cluster truth

Classification: `SOURCE_CANDIDATE_NOT_DEPLOYED`, based on published PR #435
HEAD `ad88220e830c37cc12e12b476f294ab6325d8af2`. This independent UX increment is not
a new broker, mission driver, service manager, or authorization provider.

## Observed failure and verified live operation

The operator's LPCL R2 `LION-R4-FLEET-E2E-8L32M-SANDBOX-ARCHIVE-R2` registered
correctly, but remained REGISTERED/NOT_STARTED, authority NONE, without a driver,
logical drones, material worker allocation, or mission-owned SaaS request.
Backend DELETE preview returned allowed=true. A full consistency-checked
SQLite rollback was created on LION-AUTH-LAB, and the **exact** mission was
deleted by the existing /delete endpoint with matching spec digest. Independent
readback: zero operational missions, 32 untouched historical missions, SQLite
quick_check=ok, no runtime worker effect. The audit receipt and backup are at
`/var/lib/sentinelx/uploads/lion-mission-control-v3/archive-history/exact-mission-delete-r2-20261009/`.

The desktop still runs PR432-era Electron, and the currently running
Mission Control (systemd lion-mission-control.service) uses an older module
without the scoped Docker bootstrap executor. SentinelX presently returns
service_not_allowed for that unit; lion-scale64-control is a *different*
inactive unit. Do not use generic kills or systemctl as a tool policy bypass.

The live canonical SaaS broker returned session_attestation_state=EXPIRED and
pending_count=0, with an Electron consumer STOPPED. SaaS-facing ready/connected
labels are not equivalent to a successful external roundtrip. Refreshing
the LPCL page or registering another mission cannot repair this session.

## UI fixes implemented in this source candidate

The LPCL Panel has a visible **Usuń wybraną misję** action next to mission
title, using the existing GET delete-preview, explicit human confirmation
and POST with the exact spec_digest. It stays disabled for read-only history
or no selected mission. This is not a generic cleanup request and never
stops a container.

A single explicit **Połącz LOCAL + SaaS i synchronizuj** step reads the
registered mission with exact digest, validates the required cognitive
providers, refuses an EXPIRED SaaS session or old broker pending requests,
and creates/reuses a mission-bound canonical conversation with a stable
idempotency key. The original cognitive-sync producer then performs the
separate LOCAL/SaaS projection over this bound conversation. On a canonical
delivery terminal event, the panel refreshes cognitive readiness.
A repeated sync never blindly re-sends to a provider after uncertain
delivery. This button is not LPCL activation and cannot create Docker authority.

Cluster Observatory's default **Follow latest fleet** no longer chooses the
latest historical 12L/64M run when there is no live currentness. Historical
run membership remains available only via explicit dropdown selection;
otherwise it shows **NO CURRENT MATERIAL FLEET**. It does not infer worker
readiness or logical drone existence from stale recorded counts.

## Tests, ownership, and unclosed integration

The tests in `test_r4_operator_retry_ui.py` cover visible deletion,
exact delete-preview API path, source-bound provider requirements,
Node syntax of embedded panel HTML/JS, four simulated UI paths (fresh BOUND
conversation, EXPIRED SaaS, already submitted request, READY readback),
and no auto-activation. The mission-control package manifest and static
SHA pin are updated with exact source bytes. All tests are candidate-local,
not proof of deployed UI.

The **blocking backend edges remain**: the core Mission Control still needs
an admitted exact-source installation and service restart; its active
capability registry does not include DOCKER_FLEET_BOOTSTRAP. Even on the newer
source-only branch, that capability requires a current, trusted PDP and
RuntimeAdmission issuer, a non-destructive MOON runtime source stage, a
one-shot host executor and an observed 32-worker heartbeat receipt.
The historical stopped containers have source/receipt/mount drift and must not
be restarted or relabeled to manufacture readiness. The SaaS native
consumer must be resumed through an authentic operator-owned Electron
interaction and re-attested via a real request, not through a fabricated
session receipt.

**First next independent action**: admit and deploy the exact MC and LPCL
panel successors, using allowlisted service management and rollback.
Read back live current source SHA; confirm visible delete and bind/sync flow;
restore SaaS through the native operator menu and prove exact DUAL delivery.
Only after a real Docker effect path is registered should the operator create
a new LPCL R3 and launch it. Candidate source tests alone do not satisfy that
acceptance.


## SaaS readback during this UI-only successor

The native Electron operator menu was used to restart the existing
CanonicalConversationSaaSConsumer with an empty pending queue. It returned
ENABLED and WAITING_CANONICAL_REQUEST. A single test request over an existing
UNBOUND canonical conversation was created with request ID
saas-04e55617ddc1413a93308e0f918cc24e. Status progressed to CLAIMED,
but no durable reply or receipt arrived at last readback, and the broker
still reported EXPIRED. The consumer reported AWAITING_MCP_RESULT.
Do not replay this request, infer attestation or report end-to-end SaaS PASS.

The source-only panel shows an exact SaaS binding blocker. It must not
fabricate provider lanes, force a claim completion, or turn SAAS_QUEUED into
a material receipt. This UX change does not add a native SaaS session broker.
