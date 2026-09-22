# LION Turn Ingress Node R2

Own Node.js transport replacing Slack as the turn bus.

## Scope

- no OpenAI API key
- no Slack
- loopback-only by default
- append-only JSONL ledger
- exactly-once `command_id`
- mission/session/thread/cursor preserved
- pending → claimed → completed lifecycle
- REST + SSE
- minimal MCP JSON-RPC surface for later ChatGPT app integration
- does not change LION authority or call runtime `8780`

## Canonical REST flow

`POST /v1/turns` → `GET /v1/queue/next` → `POST /v1/turns/:id/claim` → `POST /v1/turns/:id/complete`

Health: `GET /health`
State: `GET /v1/state`
Events: `GET /v1/events?after=N`
SSE: `GET /v1/events/stream`

## Boundary

This server is transport and durable state only. It does not itself wake a ChatGPT web conversation. For ChatGPT SaaS, use a supported remote MCP/app connection or another approved event ingress. Until that is connected, SentinelX/ChatGPT can read the queue explicitly.

## R20 lineage extension

R20 materializes the exact observed 8791 source into the repository and adds one non-authoritative causal field: `parent_event_id=saas_request:<request_id>`. The field participates in the immutable request hash, is returned by public turn reads, and therefore cannot be substituted without the existing command-id conflict check failing. No credential, grant, execution authority or new effect provider is introduced.
