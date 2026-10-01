# LION repository layout standard

Status: CURRENT_STANDARD. This is a target geometry for current content, not an instruction to rewrite historical evidence.

Canonical content roles:

- `contracts/` — semantic contracts.
- `schemas/` — serialization schemas where not colocated with a contract.
- `architecture/` — current architecture knowledge and versioned history.
- `runtime/` — executable runtime implementation.
- `mission_control/` — mission/control-plane domain.
- `app_coordination/` — application/session/conversation coordination.
- `process_language/` — LPCL/process semantics.
- `registry/` — registries and membership/role state.
- `rag/` — versioned retrieval knowledge.
- `evals/` — evaluations.
- `tests/` — current tests, with historical/compatibility class carried as metadata.
- `tools/` — operator/generator/validator/migration tooling.
- `docs/` — human reference/operations documentation.
- `compat/` — compatibility surfaces when they are not already frozen in a versioned historical tree.
- `archive/` — intentionally frozen history.
- `generated/` — deterministic projections whose generator/input binding is explicit.

Existing packages are not mass-moved solely to satisfy this target. Each move requires a migration map and consumer evidence.
