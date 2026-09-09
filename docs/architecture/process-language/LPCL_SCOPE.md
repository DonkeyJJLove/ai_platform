# LPCL candidate write scope

This candidate intentionally changes only process-language contracts, tests, architecture projection metadata and documentation.

It does not change:

- policy-gate/PDP implementation,
- authority source/grant/revocation,
- RuntimeAdmissionEngine,
- RuntimeExecutionEngine,
- EffectProvider,
- host state,
- deployment/release configuration,
- F005 runtime state.

Any later integration beyond this scope requires a new exact-baseline decision.
