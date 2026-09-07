# R19P — ActionProposal to canonical PDP admission handoff

R19P adds one reusable non-effectful handoff between a context-complete runtime `ActionProposal` and the already-live `CanonicalPolicyDecisionPoint`. It does not create a second policy decision point, mint or expand authority, create runtime admission, construct a requested runtime effect, invoke PEP, execute a tool, or transport an effect.

The handoff accepts the exact live `ActionProposal`, an exact existing `CanonicalPolicyDecisionPoint`, and explicit context containing request/gate identity, `MissionSpec`, `SwarmSpec`, the agent mapping, `PolicyRevision`, `AuthorityLookupKey`, `EnterpriseGraphProjection`, canonical LION status, observability state, observed events, evidence references, and an explicit timezone-aware trusted time. It validates only context shape and identity coherence required to prevent substitution at the handoff boundary, then delegates the policy decision to `CanonicalPolicyDecisionPoint.evaluate()` exactly once and returns its exact `PDPResult` unchanged.

The handoff preserves PDP replay semantics and does not create a parallel receipt. `GateRequested`, `GateApplied`, and `PDPDecisionReceipt` remain the canonical PDP artifacts. A PDP `DENY` remains a `DENY`; PDP exceptions remain fail-closed exceptions and are not converted into authorization.

The next unfinished boundary is downstream of the PDP. Current runtime code constructs `RequestedRuntimeEffect`, runtime identity and canonical PDP evidence before `RuntimeAdmissionEngine.admit(...)`. R19P intentionally stops before those objects because they bind an allowed policy decision to runtime/effect admission semantics.

The pre-existing ActionProposal JSON-schema/runtime-dataclass `schema_version` divergence remains preserved. R19P makes no wire-schema conformance claim and does not change ActionSpec target/authority coercion rules.
