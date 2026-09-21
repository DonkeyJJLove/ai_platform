# LION R18 Node.js/Express SaaS Fabric

R18 materializes the current 8780 owner in repository source. The supervised startup is Node 22+ running `node_panel/src/server.js`; the Windows supervisor no longer starts `lion_local_intelligence_runtime.py` on 8780. Mission/operator/model/turn/MCP readiness remain separate.

```text
PANEL :8780
-> ProviderRouter
   -> LOCAL_MODEL -> :8772 -> same thread
   -> CHATGPT_SAAS -> Mission Control :8766 -> Turn Ingress :8791 -> MCP :8792
      -> ACTIVE_CHATGPT_SAAS_SESSION
      -> completed turn
      -> broker receipt
      -> TurnReconciler
      -> immutable request_id -> thread_id
      -> exactly-once assistant append
```

No server-side browser wakeup is part of the current path. Host-triggered ChatGPT inference is not materialized. Panel availability does not depend on MCP or ChatGPT.

SOURCE_REF: `node_panel/src/server.js`, `node_panel/src/thread-store.js`, `node_panel/src/provider-router.js`, `tools/lion_control_plane_supervisor_windows.ps1`.
TEST_REF: `node_panel/test/integration.test.js` T01/T02/T05-T08/T21/T22 and A/B/C harness; `node_panel/test/security.test.js` T30-T33.
