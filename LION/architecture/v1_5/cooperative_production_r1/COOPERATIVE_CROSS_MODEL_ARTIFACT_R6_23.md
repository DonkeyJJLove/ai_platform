# Cooperative production R6.23 — cross-model evidence bound artifact source

Status: `TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED`. Authority effect: `NONE`.

R6.23 turns the first cooperative artifact from a merely local-model canary into a source-bound Human/AI federation artifact path when a cross-model intelligence bundle is present.

## Recon completion

`CONTROL_PLANE_RECONNAISSANCE` now exposes three additional completion facts:

```text
LOCAL_RECON_TRAJECTORIES_COMPLETE
SAAS_ADVISORY_RESPONSE_OBSERVED
CROSS_MODEL_INTELLIGENCE_BOUND
```

The first requires actual completed local trajectory outputs. The second requires `state=RESPONDED` plus SaaS response and receipt digests. The third requires a persisted `CONTROL_PLANE_INTELLIGENCE_BUNDLE` containing both local trajectory evidence and a responded SaaS advisory.

Therefore a cognitive phase may explicitly wait until both model legs exist instead of treating unavailable/session-mediated SaaS as equivalent evidence.

## Artifact source binding

`advance_build()` now checks for the existing `CONTROL_PLANE_INTELLIGENCE_BUNDLE` mission artifact.

If no such artifact exists, the legacy cooperative canary path is unchanged.

If it exists, the bundle must be complete and valid. A partial bundle never silently falls back to legacy local-only behavior.

The model assignment records:

```text
source_intelligence_bundle_digest=<exact bundle digest>
```

and receives a bounded cross-model view containing findings, ranked root-cause candidates, LOCAL/SaaS agreements, disagreements and explicit unknowns.

Before a WRITE assignment is created, cooperative production re-reads the current intelligence bundle and requires its digest to match the digest bound to the model assignment. Drift stops before material write.

The WRITE assignment carries the same `source_intelligence_bundle_digest`, and the completed build result returns it as provenance.

## Evidence topology

```text
LOCAL independent trajectories
        +
SaaS independent advisory + receipt
        ↓
CONTROL_PLANE_INTELLIGENCE_BUNDLE
        ↓ exact bundle digest
LOCAL artifact-generation model
        ↓ response digest + bundle digest
HELD cooperative WRITE
        ↓
R6.21/R6.16 runtime preparation
        ↓
material artifact
```

The SaaS result does not gain execution authority. It contributes epistemic evidence to the source bundle. The material effect still requires the existing runtime-admission path.

## Validation

Focused validation proves legacy fallback, exact digest propagation into model and WRITE assignments, successful artifact provenance readback, and bundle drift denial before WRITE creation.

`test_cooperative_production`: 6/6 PASS.
`test_control_plane_reconnaissance`: 21/21 PASS.

Live deployment and mission activation remain separate effects.
