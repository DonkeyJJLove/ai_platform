# AI Platform — integration and orchestration layer

`ai_platform` is the integration layer for the broader DonkeyJJLove research ecosystem. It maps repositories, runtime roles, governance artifacts and semantic coordinates into a common project mosaic.

## Start here

- [`platform.md`](platform.md) — detailed mapping between `/QV9D` and the physical repository structure.
- [`LAT_GLX_PROJECT_MOSAIC.MD`](LAT_GLX_PROJECT_MOSAIC.MD) — project-mosaic mapping across repositories.
- [`PROCESS_GUARD.md`](PROCESS_GUARD.md) — maintenance, observability and authority invariants.
- [`tests/`](tests/) — platform-level verification.

## Role in the ecosystem

```text
writeups      → research / architecture / evidence
chunk-chunk   → semantic process protocol
GlitchLab     → program-analysis / delta / invariant laboratory
swarm         → distributed execution
HA2D          → persistent Human–AI context
sbom          → provenance / DevSecOps
ai_platform   → integration / orchestration / governance map
```

## Core integration rule

A semantic coordinate is not enough. Every important platform object should be traceable in both directions:

```text
semantic role / QV9D coordinate
↔
physical repository / module / artifact
```

This prevents the architecture description from drifting away from the executable system.

## Process boundary

For consequential AI-driven operations:

```text
model proposal
→ context / provenance
→ policy / capability decision
→ deterministic execution gate
→ effect
→ execution receipt
```

The model may propose an action; it should not be the sole authority that authorizes its own critical effect.

## Epistemic status

Repository documents may include architecture, formalization, experiments and hypotheses. Distinguish:

```text
FACT / OBSERVED
DERIVED
CALIBRATED
ASSUMED
HYPOTHESIS
SPECULATION
```

See the cross-repository research corpus: https://github.com/DonkeyJJLove/writeups
