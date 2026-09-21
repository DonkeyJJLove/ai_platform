# R18 provider contract

`ProviderRegistry` defines two cognitive providers with `authority_effect=NONE`.

`LOCAL_MODEL`: MODEL / DIRECT_MODEL_ENDPOINT / LOCAL_HTTP / 8772 / completion owner Node/Express / autonomous-capable locally.

`CHATGPT_SAAS`: EXTERNAL_MODEL_SESSION / DURABLE_EXTERNAL_COMPLETION / MCP / completion owner active ChatGPT SaaS consumer / autonomous-capable false.

`ProviderRouter` maps LOCAL to LOCAL_MODEL, CHATGPT to CHATGPT_SAAS, AUTO by readiness/relevance, and SWARM only to an explicit mission-scoped path. CHATGPT never calls SWARM and never silently falls back to LOCAL.

SOURCE_REF: `node_panel/src/provider-registry.js`, `node_panel/src/provider-router.js`, `node_panel/src/local-model.js`.
TEST_REF: `node_panel/test/semantics.test.js` T04/T29; `node_panel/test/integration.test.js` T05/T07/T08/T22.
