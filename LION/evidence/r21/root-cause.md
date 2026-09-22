# LION R21 — persistent Chat-only SentinelX runtime

## Confirmed defects

R21 found three independent lifecycle defects after the SentinelX-primary transport itself had already passed E2E.

1. Browser authorization was not persistent. Normal Electron shutdown called store.stop(), and recover() unconditionally restored stopped=true. Every restart therefore revoked a previously authorized automatic dispatch.
2. ThreadConsumer cursor existed only in memory. A restart could prime to the newest ingress sequence and skip a turn created while the browser broker was restarting.
3. Node secure-MCP relay cached a claim past claim_expires_at. When the broker returned a request to WAITING_SUPERVISOR, the relay could reuse the stale response token and receive HTTP 409 instead of reacquiring a fresh claim.

The OpenAI-side LION conversation is required to remain a normal Chat inside project LION_EVOLUSION, not Work.

## Repairs

Browser Store now persists auto_dispatch_authorized separately from stopped. Normal shutdown records SHUTDOWN/PRESERVE_AUTHORIZED instead of becoming OPERATOR_STOP. recover() restores automatic dispatch only when no unresolved external-effect state exists. DISPATCHING, SEND_UNKNOWN and OPERATOR_REQUIRED remain fail-closed.

ThreadConsumer now persists a scope-specific ingress cursor under thread_cursor:<thread_id>. Authorized restart resumes from that exact cursor and does not replay historical events or skip turns created during restart.

The Node relay now validates cached claims with claimUsable(): broker state must still be CLAIMED, generation must match and the lease must not be expired. A released or expired claim is discarded. Reacquisition occurs only when broker state proves the request is again waiting, so no blind retry of an unknown respond effect is introduced.

The bound SaaS scope carries experience=CHAT. Browser readiness rejects Work markers with WORK_MODE_FORBIDDEN. Startup of a bound ThreadConsumer always loads relay.scope.conversation_url rather than the project landing page. The verified live route is the existing LION_EVOLUSION /c/... conversation, preserving history without Work.

## Live proof

Two normal broker restarts produced SHUTDOWN/PRESERVE_AUTHORIZED followed by PROCESS_START_AUTHORIZATION_RESTORED. stopped remained false and the durable cursor survived and advanced.

For request saas-25ece29cb91b4879b27b69e776751cc9, the original claim expired. After relay restart the fixed runtime reacquired claim_generation 2 and bound the already completed turn to receipt 37cb21e9940c483d92e035ffd0cc321fcac7e149fc67dc24c8553d8723ad98a9 without another browser send.

The subsequent project question and TEST request also reached RESPONDED / RECEIPT_BOUND. Final pending count is zero.

Final browser observation:
- project LION_EVOLUSION
- route PROJECT_CONVERSATION
- experience CHAT
- work_selected=false
- stopped=false
- relay WAITING_NEW_PANEL_TURN
- composer ready

RESULT=PASS_PERSISTENT_CHAT_ONLY_SENTINELX
