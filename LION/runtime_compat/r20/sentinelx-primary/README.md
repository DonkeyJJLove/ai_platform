# SentinelX-primary LION transport

R20-R2 uses SentinelX (https://mcp.sentinelx.app/) as the single remote tunnel between ChatGPT and MOON. lion-sentinelx-turn is intentionally narrower than the general SentinelX administration surface. It supports only bounded LION turn read/complete operations against the local 8791 ingress. The heartbeat timer produces a fresh local readiness file consumed by the Node relay. OpenAI Secure MCP Tunnel is not required and remains an opt-in fallback only. Authority is unchanged: model output and transport readiness grant no material authority.
