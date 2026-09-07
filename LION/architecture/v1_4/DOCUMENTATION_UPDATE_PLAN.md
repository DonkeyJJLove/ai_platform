# LION v1.4 R20 documentation update plan

R20 starts from live implementation and exact Git identities, not from old roadmap labels. It creates an evidence-bound documentation layer, updates stale human semantic owners, and avoids changes to executable projections or schema/runtime contracts whose non-semantic effect cannot be proven.

## Dependency order

1. Exact current-state and federation projections.
2. Semantic-owner and architecture-material catalogs.
3. Capability/contract/event-state catalogs.
4. Documentation gap, contradiction and supersession recording.
5. Reconciliation of `LION/README.md`, repository inventory and roadmap.
6. Repository-local role description only where no adequate owner exists.
7. Remote readback, diff-scope validation, falsification and draft PR creation.
8. Materialize an unpublished RAG32 successor candidate.

## Non-effects

R20 intentionally does not change runtime code, authorization, effect providers, host state, production state, schema required fields, ActionSpec compatibility semantics, executable architecture projection code or legacy status consumers.

## Completeness semantics

`material_object_catalog.json` covers architecture-material objects verified through the live canonical projection, material contracts and runtime/factory surfaces. `ALL_SYMBOL_CENSUS=UNPROVEN` because the connector session does not provide an independently validated complete repository checkout suitable for exhaustive AST enumeration. This limitation prevents a false 100% documentation-coverage claim but does not invalidate the material architecture reconciliation.
