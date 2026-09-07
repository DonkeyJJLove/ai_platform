# R19M LAIR → ActionProposal Static Projection

The live contracts declare exactly one canonical direct mapping between `CanonicalActionIR` and
`ActionProposal`: the raw SHA-256 `payload_digest`. The projection therefore binds that digest and
preserves the relevant LAIR source facts without silently translating them into runtime proposal
semantics.

The following mappings remain explicitly unresolved: proposal identity, mission identity, swarm,
proposer, capability semantics, requested authority, action class, string target, consequentiality,
evidence, observability and verifier identity. In particular the projection forbids implicit
`authority_request → requested_authority`, `kind → action_class`, and structured `target → target`
coercions.

The projection is deterministic, pre-PDP, pre-authority and non-effectful. It does not construct an
`ActionProposal`, select an agent/swarm, validate a grant, create policy evidence, create runtime
identity, request execution or perform transport. The next boundary is an explicit context-bound
ActionProposal binding layer which must supply and prove every unresolved semantic mapping.
