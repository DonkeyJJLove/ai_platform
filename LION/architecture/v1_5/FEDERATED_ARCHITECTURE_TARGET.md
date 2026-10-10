# Federated Architecture TARGET — v1.5

Status: `TARGET_CANDIDATE`. Authority effect: `NONE`.

## Target property

A future autonomous worker entering any LION repository should determine within a bounded discovery path: what the repository owns locally; what semantic surfaces it exports/imports; where the global architecture owner lives; what architecture artifacts are current, historical, target-only or generated; what dependencies invalidate architecture knowledge; and what formalization surfaces must close before an architecture-changing candidate can enter governed admission.

## Geometry

```text
GLOBAL OWNER — ai_platform
├── semantic owners
├── FormalizationRegistry
├── code-derived architecture
├── document census + graph
├── code/document reconciliation
├── dependency graph
├── roadmap projection
├── RAG/discoverability
├── federation currentness
└── truth carriers
        ↑
        │ bounded route
LOCAL REPOSITORY
├── AGENTS.md
├── cyber-lion.repository.json
├── semantic exports/imports
├── local architecture artifacts
└── local invalidation triggers
```

The global architecture is never copied into peers. Local repositories remain independently understandable while federation-wide claims route to `ai_platform`.

## Service continuation and knowledge evolution

The versioned [Service Continuation Ledger](SERVICE_CONTINUATION_LEDGER.md) is a formal input to architecture knowledge and operator handoff. The canonical owner is the pure service_continuation_ledger contract; the versioned instance is SERVICE_CONTINUATION_LEDGER_R1.json. Successors append typed events, reconcile task dependencies, reacquire currentness and enter standard formalization/Git gates. The ledger is no new scheduler, runtime authority or automatic mission activator. A future Mission Control read-only projection requires its own implementation and admission.

## Evolution invariant

```text
OBSERVE
→ DERIVE
→ RECONCILE
→ EVOLUTION_DELTA
→ FORMALIZE
→ BUILD/TEST
→ UPDATE KNOWLEDGE
→ UPDATE RAG
→ FEDERATION VECTOR
→ TRUTH CARRIERS LAST
→ INTEGRATE
→ OBSERVE AGAIN
```

Documentation is both an output and a bounded input to evolution, but never authority.
