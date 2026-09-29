# LION architecture 1.5 — cognitive evolution candidate

Status: `CANDIDATE_ONLY`. Authority effect: `NONE`. Training/model-promotion effect: `NONE`.

This directory hosts the Architecture Formalization Kernel successor work and the cognitive-evolution candidate. It does not create a new top-level architecture layer, scheduler, broker, authority engine, learning engine or runtime owner.

Canonical candidate concepts:

- `CognitiveInvocation` → `cyber_lion/contracts/cognitive_invocation.py`
- `EvidenceBoundLearningEpisode` → `cyber_lion/contracts/evidence_bound_learning_episode.py`
- `ModelRelease` → `cyber_lion/contracts/model_release.py`
- `ModelCallV2` → `cyber_lion/contracts/model_call_v2.py`
- `CoordinatorCompetencyProfile` → `cyber_lion/contracts/coordinator_competency.py`

Layer binding remains within the existing 15-layer vocabulary: `EVOLUTIONARY_EPOCH`, `FLEET_AND_SWARM`, `EVIDENCE_AND_EPISTEMIC_PLANE`, `TRUSTED_RUNTIME`, and `OBSERVABILITY_AND_RECONCILIATION`.

Start with [COGNITIVE_EVOLUTION_INTEGRATION.md](COGNITIVE_EVOLUTION_INTEGRATION.md), then [semantic_owners.json](semantic_owners.json). Formalization is governed by `ARCHITECTURE_FORMALIZATION_MANIFEST_TASK2.json` and closes only through an exact-tree `FormalizationClosureRecord`.

Task3 input artifacts are generated only after source stabilization and closure; their presence does not make a RAG release or live truth.
