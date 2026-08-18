# CYBER-LION — Capability Map

A capability is defined as a reusable ability to solve a class of problems. It is not identical to a repository, service or memorized workflow.

## Capability graph

```text
OBSERVE
  ├─ telemetry ingest ...................... swarm
  ├─ software-state observation ........... sbom
  ├─ code/delta observation ............... glitchlab
  └─ research/evidence retrieval .......... writeups

STRUCTURE
  ├─ AST / dependency graph ............... glitchlab
  ├─ multi-level graph / λ abstraction .... mosaic_lab_pro.py
  └─ QV9D semantic mapping ................ ai_platform + chunk-chunk

REPRESENT STATE / CONTEXT
  ├─ HMK-9D Δ / 9D relations .............. chunk-chunk
  ├─ PCE / MCV / SNAP / revision .......... HA2D
  └─ identity-over-time .................... sbom/AID

GENERATE / TEST HYPOTHESES
  ├─ explicit falsification research ....... hipotezy_nadawcze_LLM
  ├─ anomaly/model-disagreement analysis ... glitchlab
  └─ evidence corpus ....................... writeups

SIMULATE
  └─ scenarios / MC / Morris / Sobol ....... SymulacjaKaskadySieciowej

AUTHORIZE
  ├─ CI gate evidence ...................... sbom
  ├─ local invariants / Guard .............. glitchlab
  ├─ Kubernetes RBAC ....................... swarm
  └─ TARGET shared mandate contracts ....... ai_platform

EXECUTE
  ├─ distributed service runtime ........... swarm
  ├─ code-analysis/repair pipelines ........ glitchlab
  └─ TARGET sandbox/tool workers ........... swarm adapters

OBSERVE OUTCOME / REPLAY
  ├─ telemetry / traces .................... swarm
  ├─ EGDB / delta history concepts ......... glitchlab
  ├─ event-time analytics .................. sbom
  ├─ revision viewer concept ............... HA2D
  └─ TARGET cross-repo replay .............. ai_platform contract + adapters
```

## Capability ownership model

| Capability | Primary owner | Providers/adapters | Target status |
|---|---|---|---|
| Entity identity | `ai_platform` contract | `sbom` AID adapter | NEW shared contract |
| Provenance envelope | `ai_platform` contract | `sbom`, `glitchlab`, `writeups` | GENERALIZE |
| Typed event envelope | `ai_platform` contract | all repos | NEW shared contract |
| Capability registry | `ai_platform` | provider manifests | NEW |
| QV9D mapping | `ai_platform` | `chunk-chunk`, local manifests | REFINE |
| Context compression | `chunk-chunk` | future API adapter | EXPERIMENTAL→FORMALISE |
| Cognitive state | `HA2D` | memory adapter | SPEC→CONTRACT |
| Structural graph extraction | `glitchlab` | `mosaic_lab_pro.py` | KEEP |
| λ abstraction / supergraph | `mosaic_lab_pro.py` | GlitchLab graph adapter | EXTRACT |
| Delta/anomaly analysis | `glitchlab` | local providers | KEEP |
| Hypothesis evidence records | `ai_platform` schema | `hipotezy`, `writeups` | NEW metadata contract |
| Simulation | `SymulacjaKaskadySieciowej` | scenario adapter | WRAP |
| Policy/gate decision | `ai_platform` contract | local Guard/RBAC/CI gates | NEW common decision model |
| Distributed execution | `swarm` | tool/sandbox adapters | KEEP + REFINE |
| Supply-chain evidence | `sbom` | AID/BOM events | KEEP |
| Research evidence | `writeups` | metadata/index adapter | KEEP + INDEX |
| Cross-repo observability | `ai_platform` contract | swarm/glitchlab/sbom exporters | NEW |
| Replay | `ai_platform` contract | event stores + HA2D viewer | NEW |

## Important non-equivalences

### Identity is not address

```text
pod IP != service name != workload identity != entity identity != authority
```

`swarm` network identity, `sbom` AID, QV9D Latarnia identifiers and HA2D context identities represent different mechanisms. They require correlation, not blind unification.

### Local registry is not global capability registry

GlitchLab's callable registry is useful inside GlitchLab. It must not become the system-wide registry by namespace expansion. Cyber-Lion needs a separate registry of capability descriptors, versions, contracts and required authority.

### Graph representation is not semantic truth

GlitchLab and Mosaic Lab can produce structural representations. QV9D can assign semantic coordinates. A graph transformation or λ abstraction is a representation operation; it cannot silently create evidence or authority.

### Gate existence is not gate application

A policy file, CI rule or RBAC object does not prove that a consequential transition passed through it. Cyber-Lion needs an applied gate event linked to execution identity and receipt.

## Dynamic composition rule

A new workflow should be composed from capabilities only after the control plane can answer:

```text
What capability is required?
Which provider implements it?
Which contract version does it expose?
What identity is executing it?
What inputs and provenance does it consume?
What authority can it request?
Which gate is required?
What events and evidence will it emit?
Can the outcome be replayed?
```

If those questions cannot be answered, the capability is discoverable for analysis at most; it is not eligible for consequential execution.