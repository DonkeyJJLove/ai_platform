# LION R20 — final root cause and repair

TASK_ID=LION-R20-SOL-L64-W8-PANEL-SAAS-REPAIR-R1

## 1. Ingress credential discovery

Rev2 searched for --ingress-token-file on the 8780 panel process. That premise was false for the live topology. The credential is owned by lion-turn-ingress-node-r2.service on 8791 through LION_INGRESS_TOKEN_FILE=/etc/lion/mcp-local-token. The existing credential was verified against authenticated /v1/state with HTTP 200; the same endpoint without a credential returns 401. Windows browser_broker initially had neither services.json nor thread-scope.json, so ingress_credential_present=false and relay=NOT_CONFIGURED were correct observations rather than an expired ChatGPT session.

The Windows installer was repaired for two Windows PowerShell 5.1-specific defects discovered during live execution: wsl.exe -l -q returned embedded NUL characters, and $PID is a case-insensitive read-only automatic variable. The final installer completed, created a rollback backup, verified ingress auth, ran native Node tests and started Electron with ingress_credential_present=true.

## 2. Turn causal lineage

The live turn producer was not the historical Python relay. Runtime currentness identified Windows node_panel/src/secure-mcp-relay.js as the process creating POST /v1/turns. R20 added parent_event_id=saas_request:<request_id> to that live Node producer and to the ingress request hash/public turn view. The browser consumer now requires the same causal identity and advances its cursor even when a malformed historical event is rejected, preventing a poison-pill event from pinning the queue.

Attempt 1 proved this gap: the old producer created a fresh turn with parent_event_id=null. The consumer rejected it before any browser send and the broker request was cancelled. The Node producer was then patched and its native tests passed 2/2.

## 3. Browser SEND_UNKNOWN root cause

Attempt 2 proved correct causal lineage but reached SEND_UNKNOWN after one browser send attempt. No retry was performed. Read-only DOM reconciliation found the exact turn_id and request_id still in the ChatGPT composer. After selective draft cleanup and restart, no user-message or assistant-message contained either identity and the ingress turn remained PENDING with response=null. The request and local wake were therefore reconciled as UNSENT and cancelled.

A bounded draft-only UI experiment isolated the adapter bug. For a single-line insertText, textContent exactly equals the inserted input and the send button is enabled. For the real six-line transport prompt, execCommand(insertText) stores line boundaries as DOM blocks. The expected prompt length was 444 with five newline characters; contenteditable textContent was 439 with zero newline characters. The old click gate required literal p.textContent equality, so it rejected the already-correct draft before clicking.

R20 replaces that gate with composerEquivalent(observed, expected), which accepts only:
1. exact byte-equivalent visible text, or
2. the exact expected text with CR/LF removed.

Any altered space, character, request id or turn id remains a rejection. Native browser tests pass 24/24. No third SaaS live attempt was performed because TASK capped fresh attempts at two.

## 4. Local model and Docker fleet

No additional model runtime exists. The existing LION gpt-oss-20b-MXFP4 on Windows 127.0.0.1:8772 remained the cognitive plane. The active panel returned LOCAL_MODEL_DIRECT with R20_LOCAL_MODEL_OK before the panel restart and R20_POST_RESTART_LOCAL_OK after it. The 8 Docker workers remained bounded material/evidence executors; no worker hosted a model server.

The final worker result is 62 PASS / 2 BLOCKED / 0 FAIL. Remaining BLOCKED predicates are successful SaaS completion/receipt/same-thread delivery and the dependent final E2E audit. They are blocked by the exhausted two-attempt limit, not by an unresolved known implementation defect.

## 5. Restart and durability

browser_broker was restarted repeatedly with its durable SQLite queue and scope. Historical requests were not replayed. The active Node panel was restarted from PID 42856 to PID 52728 against the same thread database. The prior local-model canary remained in the thread, and local inference succeeded after restart. The secure MCP Node relay was restarted from patched source and reported READY with turn_ingress_ready=true and mcp_transport_ready=true.

RESULT=PARTIAL_REPAIRED_NO_FINAL_SAAS_E2E_BY_ATTEMPT_BUDGET
