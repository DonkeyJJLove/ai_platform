# R18 relevance, ContextEnvelope and latent proxy

The R18 relevance engine is deterministic engineering code, not a probability model. It scores Unicode-normalized token overlap, technical identifiers, quoted references, exact entities, explicit references, thread affinity, request lineage, source currentness, recency, contradictions, staleness and declared noise. Evaluation time is an explicit/derived input so identical state yields an identical evidence digest.

`ContextEnvelope` selects exact messages/sources, carries currentness and contradictions, records excluded noise, exposes feature scores and `SEMANTIC_CONTEXT_ENTROPY_METRICS`, and is canonical-digest bound.

`latent-proxy.js` explicitly reports `MODEL_INTERNAL_LATENT_STATE=UNOBSERVABLE` and `LATENT_PROXY_STATE=OBSERVABLE_DERIVED_STATE`. It grants no authority.

SOURCE_REF: `node_panel/src/relevance-engine.js`, `node_panel/src/context-envelope.js`, `node_panel/src/latent-proxy.js`.
TEST_REF: `node_panel/test/semantics.test.js` T23-T28.
