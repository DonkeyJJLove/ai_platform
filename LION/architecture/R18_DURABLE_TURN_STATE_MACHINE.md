# R18 durable turn state machine

The durable state is request-bound, not FIFO-bound.

```text
CREATED
-> PENDING
-> WAITING_FOR_SAAS_CONSUMER
-> CLAIMED
-> COMPLETED
-> RECEIPT_OBSERVED
-> DELIVERED
-> RECONCILED
```

Degraded states are `SEND_UNKNOWN`, `COMPLETION_UNKNOWN`, `ORPHANED_THREAD`, `CANCELLED`, and `FAILED_CLOSED`. `SEND_UNKNOWN` is fail-closed and is not automatically redispatched. `ORPHANED_THREAD` is nondeliverable but remains observable so a late completed turn/receipt can be retained without recreating the deleted thread.

Request, turn, receipt, delivery and reconciliation are separate tables. A request has exactly one immutable thread. Delivery dedupe keys are `saas-user:<request_id>` and `saas:<request_id>`.

An internal turn-claim lease table implements one-unexpired-consumer semantics for adapters that can bind it. The external MCP public `lion_claim_turn` tool is not present in the audited GitHub source and is not falsely claimed as deployed.

SOURCE_REF: `node_panel/src/thread-store.js`, `node_panel/src/secure-mcp-relay.js`, `node_panel/src/turn-reconciler.js`, `node_panel/src/saas-delivery.js`.
TEST_REF: `node_panel/test/store.test.js` T09-T19/T34; `node_panel/test/integration.test.js` A/B/C; `node_panel/test/semantics.test.js` T35.
