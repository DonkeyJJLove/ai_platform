# E02 Trust State — R5 candidate

APP_SESSION moved from a pure binding contract to a fail-closed external-verifier boundary. The verifier requires exact session/app/subject identity, provider instance and implementation identity, trust-anchor and issuer binding, trusted time, external evidence digest, durable sequence evidence and replay consumption. Provider/issuer/anchor/session/app/subject substitution, stale/future evidence, replay and sequence rollback are rejected.

The in-memory replay and sequence guards are TEST_ONLY reference implementations. No production external verifier, durable replay ledger, durable sequence backend, private signing key, canonical runtime source or runtime activation was installed. Therefore APP_SESSION remains `PARTIAL_EXTERNAL_VERIFIER_BOUNDARY_IMPLEMENTED_NOT_INSTALLED`; authority and runtime effects remain NONE.
