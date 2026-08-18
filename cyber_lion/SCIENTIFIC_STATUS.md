# CYBER-LION — Scientific / Implementation Status Register

Cyber-Lion combines executable software, architecture specifications, engineering heuristics and research hypotheses. These categories must not collapse into one another.

## Status vocabulary

```text
FACT / OBSERVED
DERIVED
MODEL
HYPOTHESIS
EXPERIMENTAL
SPECIFICATION
IMPLEMENTED
MODEL_RESULT
NEGATIVE_RESULT
SUPERSEDED
UNKNOWN
```

## Construct register

| Construct | Current status | Evidence / implementation boundary |
|---|---|---|
| INF / SEM / MAND | `SPECIFICATION` | existing QV9D/ai_platform architectural classification |
| QV9D repository mapping | `SPECIFICATION + EXPERIMENTAL` | existing static mosaic and experimental prompt comparisons; not global runtime registry |
| HMK-9D 9D state vector | `MODEL + EXPERIMENTAL` | explicit YAML/specification; bridge weights are authored model parameters, not universal empirical constants |
| `chunk–chunk→` | `MODEL` | explicit transition representation; general runtime router not yet established |
| GlitchLab Δ / AST analysis | `IMPLEMENTED` | executable Python modules exist |
| GlitchLab I1–I4 / αβZ | `MIXED: IMPLEMENTED/SPECIFICATION` | some mechanisms/code plus architectural documentation; individual enforcement paths require test-level verification |
| GlitchLab local registry | `IMPLEMENTED` | callable registry; **not** global capability registry |
| Mosaic AST→graph / λ abstraction | `IMPLEMENTED PROTOTYPE` | executable monolithic application |
| AID identity-over-time | `IMPLEMENTED CONTRACT/LAB` | explicit AID contract and SBOM/scan/delta/gate envelope |
| generalized Cyber-Lion Entity Identity | `TARGET SPECIFICATION` | not yet implemented |
| Swarm distributed execution | `IMPLEMENTED LAB` | UDP/MQTT/APIs/Kubernetes/Istio/RBAC/monitoring artifacts |
| Cyber-Lion typed event bus | `TARGET SPECIFICATION` | adapters/runtime not yet implemented |
| HA2D PCE/MCV/SNAP/MORPH | `SPECIFICATION / EXPERIMENTAL` | predominantly documentary cognitive-state model |
| `_neuro_` / SMA | `EXPERIMENTAL PROCESS MODEL` | must not be represented as clinical/physiological measurement without empirical instrumentation |
| H-LLM text→token thesis | `HYPOTHESIS` | explicit falsification criteria exist; probability value is not itself empirical proof |
| Cascade SD model | `IMPLEMENTED MODEL` | executable package and model interface |
| Monte Carlo/Morris/Sobol outputs | `MODEL_RESULT` | conditional on model, parameterization and seed; not observed geopolitical facts |
| writeups corpus | `OBSERVED ARTIFACT CORPUS` | documents exist; claims inside retain their own epistemic status |
| Security Model Boundary / PDB | `AUTHORED SECURITY MODEL` | research/writeups; should be treated as model/architecture construct unless a specific empirical claim is sourced independently |
| Cyber-Lion Control Plane | `TARGET SPECIFICATION` | current ai_platform is not yet the runtime described by this term |

## Scientific invariants

### S1 — Simulation is conditional

```text
large N
⇒ lower sampling noise inside model
NOT
⇒ empirical truth of model
```

### S2 — Representation is not reality

```text
graph / QV9D / λ / HMK-9D coordinate
= representation
!= direct proof of hidden real-world state
```

### S3 — Semantic coherence is not evidence

A coherent explanation, embedding relationship or generated hypothesis does not self-validate.

### S4 — Research output has zero implicit authority

```text
HYPOTHESIS / MODEL_RESULT / WRITEUP
cannot directly authorize ACTION
```

### S5 — Falsification record is first-class

Negative results and superseded models remain linked in provenance rather than being deleted from the epistemic history.

## Required metadata for future heuristics

Every new Cyber-Lion heuristic should eventually carry:

```yaml
heuristic_id:
status: HYPOTHESIS|EXPERIMENTAL|DERIVED
scope:
assumptions: []
metric:
evidence_for: []
evidence_against: []
known_counterexamples: []
falsification_tests: []
last_reviewed:
```

A heuristic can influence ranking/exploration before formalization, but cannot be the sole gate for irreversible high-authority execution unless the relevant policy explicitly permits that risk.

## Distillation rule

When a repeatedly validated property can be expressed deterministically:

```text
heuristic/model interpretation
→ validator / schema / invariant / test / policy
```

The deterministic mechanism becomes the enforcement source. The historical heuristic remains linked as provenance rather than remaining a repeated LLM guess.