# LION R20 status

TASK_ID=LION-R20-SOL-L64-W8-PANEL-SAAS-REPAIR-R1
RESULT=PARTIAL_REPAIRED_NO_FINAL_SAAS_E2E_BY_ATTEMPT_BUDGET

The repair is deployed on MOON. The existing local model remains gpt-oss-20b-MXFP4 on Windows port 8772; no additional model runtime exists. The active Node panel is PID 52728 on 8780, browser_broker is PID 9688 on 8793 and intentionally STOPPED, WSL turn ingress is active on 8791 with PID 16971, and the Node secure-MCP relay reports READY.

The 64-role / 8-worker fleet reconciles to 62 PASS, 2 BLOCKED, 0 FAIL. The two blocked predicates are successful SaaS completion/receipt/same-thread delivery and the dependent terminal E2E audit. TASK allowed at most two fresh live attempts. Attempt 1 was rejected before browser send because the active Node producer lacked parent_event_id. Attempt 2 had correct lineage but exposed a multiline contenteditable equality defect; DOM readback proved the exact transport prompt remained an unsent draft. Both broker requests were cancelled and no third attempt was made.

Known implementation defects found during R20 are repaired: Windows ingress credential provisioning, causal turn lineage, cursor advancement on rejected lineage, and multiline composer comparison. Native regression tests pass 24/24 for browser_broker and 2/2 for the active Node relay; Python focused suites pass 33/33. Panel restart durability and local-model inference both pass.

NEXT_ALLOWED_OBSERVATION: a future separately authorized fresh SaaS E2E request may validate the repaired send gate. R20 itself must not create a third attempt.
