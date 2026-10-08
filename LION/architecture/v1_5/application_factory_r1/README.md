# LION Application Factory R1 — cross-model material artifact successor

Status: `SOURCE_CANDIDATE / NOT_REGISTERED / NOT_ACTIVATED / NOT_DEPLOYED`.

## Goal

This package defines the first finite LION application-factory mission whose material artifact is epistemically bound to both LOCAL and SaaS evidence, while execution remains governed by the existing runtime-admission and worker-verification path.

```text
CROSS_MODEL_RECON
→ PREACTIVATE_BUILDER
→ FULL_FLEET_PROVIDER_READINESS
→ BUILD_CROSS_MODEL_ARTIFACT
→ VERIFY_CROSS_MODEL_ARTIFACT
```

The mission deliberately keeps `FULL_FLEET_PROVIDER_READINESS` after one-worker preactivation. The mission can therefore wait while a separately authorized deployment/worker-bootstrap action installs the exact qualified runtime across the fleet. Production and verification do not bypass the existing 32-worker readiness gate.

## Two process-language projections

`PANEL_LPCL_1_2.txt` is the exact Mission Control registration surface (`CONTROL_LANGUAGE=LPCL/1.2`, `PHASE_01_*`).

`CANONICAL_RUN_1_2.txt` is the canonical RUN/PHASE semantic surface. It is not a second mission. Both are emitted from one `PhaseSpec` set in `cyber_lion/mission_control/application_factory_program.py`.

`PROGRAM_VALIDATION.json` proves that both compilers produce the same five `PhaseExecutionContract` digests.

## Cross-model provenance

The reconnaissance phase uses the existing `CONTROL_PLANE_RECONNAISSANCE` owner. Because it is `COGNITIVE`, it runs independent LOCAL trajectories and a separate SaaS advisory. Completion requires `CROSS_MODEL_INTELLIGENCE_BOUND=PASS`, which in R6.23 implies completed LOCAL trajectories plus an actually responded SaaS advisory with response and receipt digests.

R6.23 then binds the resulting `CONTROL_PLANE_INTELLIGENCE_BUNDLE.bundle_digest` into the LOCAL artifact-generation assignment and the later cooperative WRITE assignment. The SaaS result remains epistemic evidence; it does not gain runtime authority.

## Capability staging

`CAPABILITY_PREFLIGHTS.json` contains three deterministic projections:

- no runtime registry: all phases are valid dynamic/unbound;
- preactivation-ready but production-unbound: recon, preactivation and full-fleet bootstrap are bound while BUILD/VERIFY remain waiting;
- full cooperative runtime ready: all five phase contracts are bound.

The second state is intentional and is the deployment boundary. It proves that preactivation does not silently authorize material production.

## Registration currentness rule

`REGISTRATION_PREVIEW.json` is compiled against the exact R6.23 parent used to author this package:

```text
HEAD c530417415c158dfc769b85f9648ec0c65d57b98
TREE c7e9c917fdb70e22354fdf35ec35481e54f2a8f8
```

It is **not** a final live registration payload. Committing, merging or deploying this package changes repository identity. Immediately before live registration, `registration_payload(deployed_head, deployed_tree)` must be regenerated from an exact readback of the deployed/current source. Registration and activation remain separate actions.

## Deployment boundaries

There are two distinct deployment boundaries. First, the R6.18–R6.23 source and pinned process/preactivation providers must already be deployed before this mission can execute at all. Second, after `PREACTIVATE_BUILDER`, a separately admitted fleet activation may install the qualified cooperative runtime on the full worker fleet. Neither deployment is encoded as authority inside LPCL.

## Safety properties

The material BUILD transition in the canonical process is `ACTION_REQUIRED`, `NON_IDEMPOTENT`, `RECONCILE_FIRST`, with zero automatic retries. Unknown material effect is therefore reconciled rather than blindly repeated. BUILDER and VERIFIER are separate local roles.

No file in this package registers, activates, deploys, claims an assignment or writes a live artifact.

## Deployment readiness

`DEPLOYMENT_PACKAGE_MANIFEST.json` freezes the self-contained 8766 package closure. The current candidate package contains 91 exact-hashed files and passes isolated import from the staged package root.

`DEPLOYMENT_READINESS.json` records the remaining publication gate. The concrete `MISSION_CONTROL_V3_INSTALL` effect revalidates its source envelope against current GitHub `master`, while the host deployment contract also requires a real PR/currentness evidence chain. Therefore this local candidate must be published, pass CI and be merged before the existing canonical 8766 installer may be used.

After merge, exact deployed HEAD/TREE is reacquired, the package is restaged from merged bytes, the one-shot deployment is admitted (`retry=0`, reconcile-first), 8766 is read back, and only then is the mission registration payload regenerated. Registration and activation remain later separate actions.
