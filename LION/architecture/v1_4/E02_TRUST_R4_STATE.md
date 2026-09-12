# E02 Trust State — Generation 10

E02 retains deterministic producer/collector provenance, trusted-time, durable-sequence and local-runtime trust candidates. Generation 10 adds an **effect-free APP_SESSION attestation binding candidate**. It accepts only externally supplied attestation evidence with explicit provider/trust-anchor digests, bounded freshness and exact session/app/subject binding; substitution, stale evidence, wrong access class and trust promotion fail closed.

This is not an attestation provider. `APP_SESSION` state is `PARTIAL_CANDIDATE_EXTERNAL_ATTESTER_REQUIRED`; canonical runtime source remains `NOT_ACTIVATABLE`, runtime activation remains `NOT_AUTHORIZED_NOT_INSTALLED`, and no key/credential/provider was installed. Mission Control runtime source remains stale relative to master and K3s remains inactive.
