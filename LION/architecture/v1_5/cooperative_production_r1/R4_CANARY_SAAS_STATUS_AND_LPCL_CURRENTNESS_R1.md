# R4 canary: SaaS broker projection and MAT04-independent LPCL syntax

Status: **SOURCE-ONLY CANDIDATE — NOT INSTALLED, NOT ACTIVATED**.
Predecessor: exact merged master `9472b1e184b0ee18bad0d8315508b428e4edfe84`.
Ownership: `local_intelligence_gateway.py` renders the panel and proxies the
canonical SaaS status; `lion_local_intelligence_runtime.LpclControlBridge`
compiles LPCL and owns the MAT04 source-currentness dependency.

## Reproduced current runtime evidence

Windows panel canary `8781` launched from exact `panel-master-9472b1e-r1` in an
isolated DB/runtime directory and returned `health=ok`. Its real
`GET /api/saas/broker/status` response contained `session_attestation_state=EXPIRED`,
`pending_count=0`, `channel_state=SENTINELX_MCP_READY`,
`transport=CHATGPT_SENTINELX_MCP`, **but omitted**
`automatic_hop=AVAILABLE`, although the canonical LION Mission Control
producer exposed it. The panel demanded `automatic_hop=AVAILABLE` before
sending the first user-requested, source-bound LOCAL/SaaS synchronization.
This would always fail `SAAS_TRANSPORT_NOT_READY` even if the mediator was
available. The local proxy now forwards exactly the canonical field, without
minting, changing or inferring broker state.

A one-time, read-only `POST /api/lpcl/validate` from the isolated canary
returned HTTP 400 after **30.297 seconds**:
`TimeoutError:material drone timeout:MAT04`. The canary had intentionally
not inherited the live material-drone runtime. The original parser blocked
on a MAT04 `github_branch` request from an unserved inbox; the UI could not
validate LPCL syntax independently.

## Source mechanism and fail-closed distinction

`LpclControlBridge.validate` still compiles the exact LPCL and phase
contracts with the live capability registry. It now inspects the material
broker's current MAT04 heartbeat BEFORE issuing a GitHub request. If MAT04
is absent, not fresh, fails, times out or returns malformed source IDs, LPCL
returns its correct syntax/phase readback together with a DISTINCT
`source_currentness.verification=UNVERIFIED`, `head=null` and `tree=null`.
No local Git, browser-tab source or other nonauthoritative fallback is
substituted. If a verified MAT04 receipt is available, exact 40-character
GitHub HEAD and TREE retain `verification=VERIFIED`. Existing runtime
selection and capability readiness are not altered.

The backend `register_lpcl` **refuses** any unverified source with
`LPCL_SOURCE_CURRENTNESS_REQUIRED:MAT04` before sending a write to
Mission Control. The frontend independently disables "Zarejestruj misję"
when the proof is missing and shows
`VALID SYNTAX · SOURCE CURRENTNESS UNVERIFIED`. LPCL activation remains
unchanged and requires a registered exact digest and two real provider
receipts where cognitive providers are required.

## Tests and acceptance boundary

Tests cover a canary with MAT04 unavailable and **zero** material-drone
dispatches, valid source with exact head/tree, timeout and malformed MAT04
source, no registration effect without a verified source, UI controls under
UNVERIFIED and VERIFIED currentness, and the exact SaaS `automatic_hop`
projection. The old LPCL/1.1 source aliases and Docker runtime declarations
remain tested.

**What this does not do:** It does not install a Docker effect issuer, start
32 workers, attest SaaS without an actual response, rebind a mission, or
complete the target two-sandbox archive mission. Full isolation canary only
proves syntax/currentness gating; final current-source registration must
still run with a live validated MAT04 receipt in the actual operator panel.

First next step: publish and CI-test exact source, install an immutable
new Windows panel release side-by-side with current `8780`, perform the real
isolated canary `/api/saas/broker/status` and `/api/lpcl/validate`
readbacks, backup `threads.db` with integrity check, and only then perform
a controlled source/PID switch and readback. The old release remains the
rollback target.
