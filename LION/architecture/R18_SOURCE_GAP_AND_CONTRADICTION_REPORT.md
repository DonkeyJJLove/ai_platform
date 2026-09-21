# R18 source-gap and contradiction report

At R18 entry, GitHub `master` was `da4dbd7b27b4833c0debddf839e003f2ce170d5c` / `20fa96a86857cecacc5a3c772e2a4dcd7f797dad`.

Observed contradiction: the repository still started Python `tools/lion_local_intelligence_runtime.py` as the 8780 panel and Mission Control started a secure relay whose readiness required browser-driver evidence. The supplied R17.4 live acceptance instead required Node/Express 8780 and `BROWSER_AUTOMATION=DISABLED_BY_POLICY`.

Observed source gap: the supplied R17.4 Git HEAD `745e2672dbf326d4c210efea6bd279f4880efdd0` and branch `lion-node-express-r17-c552dcf0f28b` were not resolvable in GitHub. No exact byte recovery was possible.

R18 disposition: reconstruct behavior on a new Git lineage. Node/Express becomes current 8780 startup owner; legacy browser relay remains code/history but is quarantined behind an explicit non-default flag; durable request/turn/thread binding and reconciliation are materialized in `node_panel/`.

The external implementation of the MCP tools `lion_next_turn`, `lion_get_turn`, and `lion_complete_turn` is not present in the audited repository. R18 therefore does not invent a public `lion_claim_turn` deployment. It implements an internal durable turn-claim lease and records the public MCP claim tool as not materialized.

SOURCE_REF: `tools/lion_control_plane_supervisor_windows.ps1`, `tools/lion_mission_control_v3.py`, `node_panel/src/thread-store.js`.
TEST_REF: `node_panel/test/security.test.js` T30-T33; `node_panel/test/store.test.js` T34; `cyber_lion/tests/test_secure_mcp_broker_relay.py`.
