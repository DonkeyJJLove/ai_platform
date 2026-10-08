# LION Desktop R4 — dual-column operator shell source candidate

This successor is based on the exact *source* tree of the PR #431 delivery-reconciliation candidate, not on the older E0 canonical-consumer bytes. It does not update a running Electron application, restore a missing 8780 owner, activate LPCL, or replay any historical SaaS message.

The LEFT tab strip has Mission Control, Cluster and System. The RIGHT strip has LPCL/Model Chat, ChatGPT SaaS and Local GPT. The halves are independently switched without reloading SaaS. Six groups of native Electron menus provide navigation, read-only diagnostics, the 10 declared federation names, and operator-gated control of the external SaaS relay. The existing canonical conversation and Mission Control owners remain unchanged.

The Local GPT viewport is a sandboxed file renderer. Only a sender-identity-checked Electron preload can invoke status and bounded advisory inference through the Electron main process to 127.0.0.1:8772. It offers no tool use, worker action, mission binding, provider-token access, or direct filesystem access. Its displayed request/response digest is not a canonical mission receipt. Only canonical Model Chat may bind LOCAL/SAAS/DUAL requests to conversation_id, mission_id, binding_epoch, lane, correlation/causation and separate shared-context/projection digests.

The Cluster/System viewport uses a distinct allowlisted read-only projection of current Mission Control/panel/model/broker health and mission states. The Cluster reads the existing MOON fleet currentness carrier at the exact fixed path r23-autonomy/fleet-currentness.json, verifies the canonical SHA-256 digest and all 32 worker identities, and labels observations FRESH, STALE, FUTURE or INVALID. A digest-valid recent fleet observation does **not** attest provider readiness, deployment source, authority or execution admission. GitHub repository HEADs and artifact counts remain explicitly stored snapshots and carry their own observation dates. No raw SQLite, filesystem or credentials are exposed to renderers. The read-model only exposes a bounded, redacted launcher-log tail; authenticated current worker logs and artifact bytes remain future work.

On startup the canonical SaaS automatic consumer remains STOPPED. Interactive ChatGPT browser usage is still possible. Menu-driven resumption checks outstanding send states and upstream backlog first. A durable SEND_UNKNOWN or unverified response digest is never retransmitted simply because an HTTP/UI timeout occurred. This candidate retains the single-inflight/receipt protections of PR #431.

Observed Windows-host history: an earlier local E0R4 isolated Electron on port 8795 reported 6 distinct tabs, Mission Control HEALTHY and Local GPT READY, before the reception script hit a PowerShell case-insensitive variable-name collision; raw status was preserved and the isolated process exited. This is **not a native acceptance test of this PR's combined PR431+R4 bytes**. Source testing for the combined tree is required under Node 24 on both supported runners and with exact Git HEAD/TREE.

This branch is intended as a stacked draft PR targeting the validated PR #431 branch. Merge/rebase order must be controlled: first integrate PR #431, then currentness-rebase this PR and recalculate truth subject carriers after all other source changes. Do not erase historical source-package manifests R1/R2; R3 is a separate exact-byte successor and is SOURCE_ONLY_NOT_DEPLOYMENT.

Effect closure: NO new Mission Control, no R24 worker restart, no SaaS backlog changes, no release source deployment. An operator-authorized native handoff of exact source, single-writer 8780 verification, and observed six-tab status remain separate follow-on gates.

## Operator UX / archival successor (source candidate)

The Cluster and System WebContentsView pages no longer reproduce the external tabs as internal duplicates. Cluster exposes overview/workers/logs/artifacts; System exposes machines/repositories/dependencies. The System machine-role inventory distinguishes one WINDOWS-MOON physical control domain from MOON, LION-AUTH-LAB, LAB-UBUNTU and LAB-DEBIAN logical WSL environments; documented roles are not falsely marked live or independent physical hosts. Archive and reasoning-lineage tools are versioned separately, with a first 28-terminal-mission immutable snapshot executed on the current LION-AUTH-LAB DB. No active assignment, bridge or SaaS pending turn was retired by this source change.

## Canonical SaaS broker receipt-only reconciliation (source candidate)

The Intelligence menu offers an operator-triggered exact-receipt-only reconciliation of earlier externally sent requests. No resend occurs, even if Model Chat displays SAAS_QUEUED or a user-facing delivery timeout. The consumer must remain STOPPED and independently check request_id, response_digest, receipt_digest and authority_effect NONE on Mission Control. The batch is bounded to 32 and committed to local broker state as one write only after every receipt verifies; any missing receipt fails closed without local progress. New supervisor handoffs are not covered by this operation.


## R4 compact operator navigation successor (source candidate, not deployed)

The left Mission Control tab is now a compact operator portal. It shows only
status and three native links: Cluster (workers and fleet), System (hosts,
repositories, topology) and LPCL Panel (process/conversation). The historical
full Mission Control page remains accessible under an explicitly collapsed
compatibility inspection element; none of its legacy diagnostics or canonical
Mission Control APIs are removed. The Electron main process routes only exact,
path-free lion-left://cluster, lion-left://system and lion-right://panel
URLs from the Mission Control WebContentsView. It rejects other schemes,
destinations, paths, queries, fragments and credentials without effect. SaaS
remote content cannot use the operator-only navigation branch.

The canonical LPCL panel uses a 56px sidebar rail and an expandable mission
drawer. An explicit view label distinguishes the operational and historical
projections. Selecting a mission closes the drawer. The backend mission
registry, active mission identities, archived SQLite snapshots and mission
completion flags are unchanged. This is a UI navigation change, not a
deletion, backend archive migration or authority transition.

SaaS remains separately governed: a visible composer does not prove an MCP
roundtrip. Current local broker backlog, expired session bindings and any
SEND_UNKNOWN must be reconciled per request before operator-gated relay resume.
This source change does not resend/cancel turns or bypass the backlog gate.

Validation: isolated exact-source UI/HTML checks, native Windows Node 24 test
suite, and an offline headless-Edge visual rendering are separate evidence
classes. A file:// preview has no current Mission Control API and will show
OFFLINE/DEGRADED even when its responsive layout is correct. Production visual
acceptance requires a versioned Windows panel/desktop handoff and authenticated
readback of the actual source bytes.
