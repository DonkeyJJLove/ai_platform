# LPCL v1.1 candidate write scope

This candidate intentionally changes only process-language contracts, process-source interpretation, FleetMissionIR, process/fleet tests and corpora, source-derived architecture projection metadata, LPCL architecture documentation and downstream truth/currentness carriers in the carrier-last phase.

Permitted candidate source families are bounded to:

```text
cyber_lion/process_language/**
cyber_lion/architecture_projection/** only where LPCL/process-orchestration projection is represented
cyber_lion/tests/test_lpcl*
docs/architecture/process-language/**
LION/architecture/v1_4/** only for LPCL-related documentation/projections and carrier-last reconciliation
```

The candidate does not change or replace:

- policy-gate/PDP implementation or decision semantics;
- authority sources, grants or revocation;
- `RuntimeAdmissionEngine`;
- `RuntimeExecutionEngine`;
- EffectProvider implementations or raw provider selection;
- Action IR authority semantics;
- host state or local runtime state;
- deployment/release configuration;
- F005 runtime state;
- production authority;
- specialized MissionSpec/SwarmSpec semantics unless separately proven equivalent.

The v1.1 authoring surface may route an `ACTION_REQUIRED` transition to a LOCAL role, but this produces only the existing non-authoritative `ActionIntentCandidate` boundary.

Truth/currentness carriers are not permitted to move until noncarrier implementation and verification are frozen. Merge and branch deletion require separate exact authority and are outside ordinary candidate-write authority.

Any integration beyond this scope requires a new exact-baseline decision.
