# LION R20-R2 — SentinelX-primary transport closure

TASK_ID=LION-R20-SOL-L64-W8-PANEL-SAAS-REPAIR-R2

R2 proved that the browser dispatch repair from R20 was correct: the SaaS prompt was sent exactly once. The next failure was below the browser layer. The historical OpenAI Secure MCP Tunnel service was inactive and its runtime API-key file was empty, so ChatGPT tool calls returned McpServerError: Session terminated.

The architecture was simplified to one remote tunnel: https://mcp.sentinelx.app/.

The local LION turn ingress on 8791 remains a durable local ledger only. It is no longer exposed through a second OpenAI tunnel. A bounded helper /usr/local/bin/lion-sentinelx-turn exposes only two operations through the existing SentinelX agent on MOON: get <turn_id> and complete <turn_id> chatgpt-saas-sentinelx {text}. The helper does not accept arbitrary URLs, headers, file paths or commands.

The canonical explicit transport is CHATGPT_SENTINELX_MCP. The old CHATGPT_SENTINELX_SESSION_MEDIATED remains legacy/manual compatibility and is not reused for the new automatic path. OpenAI Secure MCP Tunnel remains installed only as an opt-in fallback guarded by LION_ENABLE_OPENAI_SECURE_MCP_TUNNEL=1; its service is disabled/inactive and is not required for R2.

Final live E2E: request saas-d0b73c6fad88495f80c72d14a970251c, turn turn_d90e27d5-a0bb-4f4b-8e08-58bb69c841b5, transport CHATGPT_SENTINELX_MCP, exactly one browser send, turn COMPLETED, broker RESPONDED / RECEIPT_BOUND, answer R20_R2_SENTINELX_OK, receipt 249fa9912d617093f433e27ade24bbb717678433c25ea96c8a8f5030b41ebcda, same-thread delivery confirmed in b868a1fa93de46d9b3d4d0cd3e1c5345.

The local model remained the existing gpt-oss-20b-MXFP4; no additional model server was created. The final Docker fleet result is 64 PASS / 0 BLOCKED / 0 FAIL across 8 material workers.

RESULT=PASS_SENTINELX_PRIMARY_E2E
