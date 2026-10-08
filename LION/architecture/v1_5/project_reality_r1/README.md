# Project Reality / Evolution R1 — formalization candidate

Status: `STACKED_SOURCE_CANDIDATE / FORMALIZATION_PREVIEW`. Authority effect: `NONE`. Execution effect: `NONE`.

This package reconciles the supplied Mental Matrix, evolutionary-architecture, conversation, RAG and cooperative-production materials with the current LION source and with the Dynamic Evolution Fitness R1 parent candidate.

## Exact source binding

```text
stacked parent HEAD = 7e943f24958fbedc0933c4a145b3cadc55b2153a
non-generated tree = 4c58045909a9e1d4fe46d80f61f35d843ed5c65f

candidate digest    = b671f67875a38d982c8a60a647ca60e87e5962631846d89c97a8e261392bedaf
compilation digest  = edbc7001f30777999a68333b138b47f4d8e417d9dd071474bd7714f22a482980
```

Generated sidecars are deliberately excluded from the source tree to avoid self-referential hashing.

## Architectural result

The implementation introduces no new truth database, graph authority, scheduler, broker, PDP, Mission Control instance or runtime owner.

It adds:

- `ProjectRealitySnapshot`: exact digest-bound projection over existing world/system/federation/currentness/architecture/enterprise-graph evidence;
- `ProjectClaimProjection`: bounded read-only projection over existing `SemanticAtom` and `EnterpriseGraph.DATA_PROVENANCE`;
- `CandidateRealityBinding`: one exact observation of every Dynamic Evolution Fitness hard gate;
- `PressureObservation`: evidence-bound dynamic pressure;
- `EvolutionRealityContext`: fail-closed bridge from project reality to fitness;
- `system_snapshot_from_control_plane_observations(...)`: pure normalizer for the already-existing `lion.control-plane-reconnaissance/v1` evidence producer.

Mental Matrix and Architecture Studio remain downstream consumers of this common substrate.

## Existing producer reuse

Current source already contains a read-oriented producer:

```text
tools/lion_local_intelligence_runtime.py
  control_plane_recon_observer_once(...)
          ↓
CONTROL_PLANE_WINDOWS_OBSERVATION

cyber_lion/mission_control/control_plane_reconnaissance.py
  collect_observations(...)
          ↓
lion.control-plane-reconnaissance/v1
```

Project Reality does **not** duplicate those probes. It normalizes the existing observation into the canonical evolutionary state plane.

## Formalization preview

The existing `ArchitectureCompiler` generated:

- `EVOLUTION_DELTA.json`
- `ARCHITECTURE_FORMALIZATION_MANIFEST.json`
- `REQUIRED_FORMALIZATION_SET.json`
- `COMPILATION_RESULT.json`

The required formalization set contains **36** surfaces. No `FormalizationClosureRecord=PASS` is asserted. Admission remains outside this package.

## Live boundary observed during authoring

The current Mission Control read model is healthy enough for readback, but the focused cooperative mission remains:

```text
LION-COOPERATIVE-PRODUCTION-PILOT-R3
REGISTERED
NOT_STARTED
authority = NONE
source = c4e3c889... / 3badc880...
```

while current remote `master` is `b6cc132...`. The current summary also reports worker-observation readiness `UNKNOWN`. Therefore the current artifact-production path is **not** promoted to a CURRENT executable successor by this candidate.

## Next source step

Bind a fresh, current control-plane reconnaissance evidence generation into one `ProjectRealitySnapshot`, derive candidate-specific gates/pressure, and author the exact current-source successor for the first closed application-factory artifact.

Activation remains a separate operator action.
