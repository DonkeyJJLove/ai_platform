# R17.4 executable provenance gap

```text
DOCUMENT_ID=LION-R17-4-EXECUTABLE-PROVENANCE-GAP
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
PROVEN_LIVE_HEAD=745e2672dbf326d4c210efea6bd279f4880efdd0
PROVEN_LIVE_TREE=9f262a92f3cd74773eeaf5b4202666757df34e7f
GITHUB_RESOLUTION=NOT_MATERIALIZED_AT_R18_START
```

The R17.4 live acceptance proved behavioral facts but the supplied Git commit and branch were not resolvable in GitHub at R18 start. R18 therefore does **not** claim byte identity with the missing source. It reconstructs the accepted behavior as a new Git lineage from audited `master=da4dbd7b27b4833c0debddf839e003f2ce170d5c`.

Recovered invariants: Node/Express owns 8780; 8772 is the local model; 8791 is Turn Ingress; 8792 is MCP transport; durable handoff is not autonomous ChatGPT inference; browser automation is disabled by policy; model/transport/receipt are not authority; same-thread delivery uses immutable request/thread binding.

R18 reconstructed implementation: `node_panel/` provides Node/Express, durable SQLite bindings, provider routing, LOCAL completion, durable CHATGPT handoff, turn reconciliation, exactly-once delivery, relevance/context/latent-proxy evidence and layered readiness. Historical R17.4 source bytes, exact commit ancestry and exact external MCP service implementation remain unavailable.

OBSERVED_GAP: `R17_4_BYTE_LEVEL_SOURCE=UNAVAILABLE`.

SOURCE_REF: `node_panel/src/server.js`, `node_panel/src/thread-store.js`, `node_panel/src/secure-mcp-relay.js`.
TEST_REF: `node_panel/test/integration.test.js`, `node_panel/test/store.test.js`.
