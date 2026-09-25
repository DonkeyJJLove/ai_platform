# LION Architecture Formalization Kernel — v1.5 candidate

```text
TASK_ID=LION-V15-ARCHITECTURE-FORMALIZATION-KERNEL-R1
ARCHITECTURE_SOURCE_EPOCH=1.4
ARCHITECTURE_TARGET_EPOCH=1.5
BASELINE_HEAD=1217e1536af5bfbb6ed81d548e9844af48883bff
BASELINE_TREE=e23a043012d5bf865af4f398c0a2cc53c94c36d2
AUTHORITY_EFFECT=NONE
EXECUTION_EFFECT=NONE
```

## Purpose

The kernel closes a missing architectural invariant: an architecture-affecting change is not formally closed merely because candidate code, tests, or independent repository verification exist. It must also prove that every canonical surface through which the next reasoner discovers the architecture has been updated, regenerated, superseded, validated, or explicitly classified `NOT_APPLICABLE`.

This is not a new PDP, broker, executor, or sixteenth top-level layer. It lives inside the existing evolution, governed self-implementation, architecture-projection, currentness, and reconciliation semantics.

## Contracts

`FormalizationRegistry` answers what formalizes architecture, who owns it, what generates and invalidates it, how it is validated, who consumes it, and what currentness model applies. The registry has `authority_effect=NONE`.

`ArchitectureFormalizationManifest` (AFM) is a sidecar to an `EvolutionDelta`. It binds the exact baseline and delta digest, affected concepts, existing-layer bindings, semantic-owner delta, formalization classifications, currentness invalidations, migration/rollback, tests/evals/falsifiers, discoverability probes, and RAG delta. AFM has no execution or authority effect.

`RequiredFormalizationSet` is deterministically derived from `AFM + FormalizationRegistry`. For global concept changes the manifest must classify, at minimum, semantic owners, contract catalog, capability catalog, architecture projection, event/flow semantics, gap/frontier, evolution evals, discoverability, RAG routing, and currentness carriers. Valid classifications are `UPDATE`, `REGENERATE`, `ADD`, `SUPERSEDE`, `VALIDATE_ONLY`, and `NOT_APPLICABLE`; `NOT_APPLICABLE` requires justification.

`FormalizationClosureRecord` (FCR) binds exact candidate digest/HEAD/TREE, independent verification digest, and AFM digest. `PASS` fails closed on any unknown, stale required projection, semantic-owner uniqueness failure, catalog coverage failure, required test/eval failure, required discoverability failure, or required RAG retrieval failure. FCR is not merge or deployment permission.

`FormalizationProposalBinding` is the separate non-effectful record binding `proposal_digest <-> formalization_manifest_digest`. R1 deliberately does not mutate `GovernedChangeProposal/v1`; a v2 is deferred until sidecar shadow evidence exists.

## Integration

```text
EvidenceObservation
→ Hypothesis
→ Experiment / Falsification
→ PromotionDecision
→ RnDMemoryRecord
→ EvolutionDelta
→ ArchitectureFormalizationManifest
→ GovernedChangeProposal/v1
→ FormalizationProposalBinding
→ exact DetachedRepositoryCandidate
→ independent verification
→ regenerate / validate RequiredFormalizationSet
→ FormalizationClosureRecord
→ separately governed repository admission
→ exact repository effect
→ independent observation
→ reconciliation
```

The invariant is:

```text
CANDIDATE_CODE != FORMALIZATION_CLOSED != AUTHORIZED != INTEGRATED != OBSERVED_EFFECT
```

## Shadow A — Process Contract Plane

Historical Process Contract Plane introduction is replayed semantically from its concept/layer/contract properties. Expected file paths are not manually enumerated as the prediction target. The registry derives the required surface set; the historical Git delta is used only as the observed comparison set. Recall is `1.000000` and precision `0.352941`. Recall reaches the preferred threshold 1.0. Precision is intentionally lower because the new kernel conservatively requires surfaces that history did not update; those are reported as historical closure gaps rather than suppressed as false alarms.

## Shadow B — CIP + EBLE + ModelRelease

The prospective shadow binds Cognitive Invocation, EvidenceBoundLearningEpisode, ModelRelease and local coordinator competency into existing layers. The derived set detects all task-required categories: new semantic owners, new contracts, architecture projection delta, behavioral evolution evals, discoverability, RAG delta and currentness invalidation. Detection recall and precision are both 1.0 for the task-level semantic label set; conservative extra formalization surfaces are reported separately.

## Migration boundary

`LION/architecture/v1_4/` remains historical lineage and is not rewritten by this candidate. v1.5 is a candidate formalization space. Existing v1.4 projections may be inputs to drift detection but are not silently refreshed here. Merge, deployment, host mutation, training and model promotion are outside this task.
