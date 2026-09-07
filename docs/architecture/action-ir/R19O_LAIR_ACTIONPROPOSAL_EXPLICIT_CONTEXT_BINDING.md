# R19O — LAIR to ActionProposal explicit context binding

The binder consumes an exact `CanonicalActionIR` plus explicit context. Only `payload_digest` is bound directly from LAIR. Every other `ActionProposal` semantic value is context-owned and provenance-bound.

The binder does not infer `requested_authority` from `authority_request`, `action_class` from `kind`, or string `target` from the structured LAIR target. It does not perform PDP/PEP, mint authority, construct runtime admission, invoke an executor, or provide an effect surface.

`CanonicalPolicyDecisionPoint` already exists downstream. The next gap is an explicit handoff of the context-complete proposal into that existing PDP, followed by the separately mediated authority/runtime admission chain.

## Preserved pre-existing schema/runtime divergence

`action_proposal.schema.json` requires `schema_version=1.0.0`, while the exact runtime `cyber_lion.enterprise.control_plane.ActionProposal` dataclass has no `schema_version` field. Both shapes were introduced together in commit `15409591e96aba31ca49017b31c2d4c2a555d0d9`. R19O must preserve this contradiction and bind only the runtime dataclass consumed by the existing PDP. It must not claim wire-schema conformance and must not silently add, drop, or synthesize a wire `schema_version`.
