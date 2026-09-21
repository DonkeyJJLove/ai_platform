# R18 ChatGPT SaaS consumer protocol

Activation owner: `ACTIVE_CHATGPT_SAAS_SESSION`.

The current supported server path creates a durable turn but does not remotely trigger inference. A ChatGPT SaaS session consumes the queue through LION-MCP-R2:

```text
lion_next_turn(after=cursor)
-> IDLE or exact turn
-> lion_get_turn(turn_id)
-> claim when a supported claim primitive exists
-> validate authority_effect=NONE
-> infer using turn.input + allowed ContextEnvelope/thread evidence
-> lion_complete_turn(turn_id,response={"text": exact_model_answer},actor="chatgpt-saas-mcp")
-> lion_get_turn(turn_id)
-> verify COMPLETED + response digest
-> advance cursor
```

`CHATGPT_HOST_TRIGGERED_AUTONOMOUS_INFERENCE=NOT_MATERIALIZED`.

R18 adds an internal durable turn-claim lease to prevent competing consumers when an adapter uses it. The audited repository does not contain the external MCP server/tool implementation for `lion_next_turn/lion_get_turn/lion_complete_turn`, so R18 does not claim to have added a public `lion_claim_turn` tool to that external surface.

SOURCE_REF: `node_panel/src/secure-mcp-relay.js`, `node_panel/src/thread-store.js`, `node_panel/src/turn-reconciler.js`.
TEST_REF: `node_panel/test/store.test.js` T34; `node_panel/test/semantics.test.js` T35; `node_panel/test/integration.test.js` T06.
