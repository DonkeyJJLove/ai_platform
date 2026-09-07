# LION — project documentation entry point

LION is an evidence-bound, authority-separated architecture for governing AI-assisted evolution from observation and proposals through authorization, runtime admission, bounded effects, independent observation and reconciliation. Documentation, code presence and CI success do not themselves confer authority or prove deployment.

## Current v1.4 documentation

For the current architecture documentation candidate, start at [`architecture/v1_4/README.md`](architecture/v1_4/README.md). Its current-state projection is bound to exact Git identities and becomes stale on baseline drift. The source-derived architecture model remains owned by `cyber_lion/architecture_projection/full_architecture.py`; the v1.4 catalogs are projections and indexes, not a second executable truth source.

`status.json` is retained as an E003-era historical projection. Its self-declared `CURRENT` label is not valid evidence for the R20/R19P live repository state; do not use it as the v1.4 currentness source.

## Architecture boundaries

The live Action plane includes Action IR/proposal, canonical PDP handoff, runtime admission, runtime execution, effect-time currentness and runtime reconciliation. F009 demonstrates a bounded end-to-end live evidence path. The remaining general frontier is a reusable canonical materializer/binder from PDP ALLOW + exact proposal/current authority/provisioning to the runtime effect, identity and PDP-evidence objects consumed by the existing admission engine.

Bean, capability-need, composition, Mosaic and builder-chain primitives are implemented, with bounded B0 candidate evidence. This is not proof of general Factory generativity, activated recursive child autonomy or Factory-of-Factories.

## Navigation and lineage

- `architecture/v1_4/current_state.json` — exact-baseline current-state projection.
- `architecture/v1_4/federation_current_vector.json` — exact live federation identities.
- `architecture/v1_4/material_object_catalog.json` — architecture-material object census; exhaustive all-symbol census is explicitly unproven.
- `architecture/v1_4/capability_catalog.json` and `contract_catalog.json` — capability/contract state.
- `architecture/v1_4/event_state_catalog.json` — canonical flows/state semantics.
- `architecture/v1_4/semantic_owners.json` — semantic-owner routing.
- `architecture/v1_4/documentation_gap_register.json` — stale, contradictory and intentionally unresolved formal gaps.
- `architecture/v1_4/history_and_supersession.md` — v1.3/v14c2/R20 lineage and falsification boundaries.

Historical documentation remains historical evidence and must not be rewritten to resemble current state.
