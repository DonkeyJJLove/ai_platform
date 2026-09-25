# Cognitive evolution integration — v1.5 candidate

## Boundary

```text
PROVIDER != ENDPOINT != SESSION != INVOCATION != TRANSPORT != RESULT
COGNITIVE_INVOCATION != AUTHORITY_ACTIVATION
TRANSPORT_READY != COGNITION_DONE
SESSION_BOUND != MODEL_READY
HEARTBEAT != INFERENCE
RECEIPT != CORRECT_RESULT
```

No `COGNITIVE_INVOCATION_PLANE` or `LEARNING_PLANE` is added. Cognitive invocation is an existing-layer domain crossing `EVOLUTIONARY_EPOCH`, `FLEET_AND_SWARM` and `EVIDENCE_AND_EPISTEMIC_PLANE`.

## Invocation

LOCAL and SAAS are separate legs. DUAL is a parent causal group containing two independent invocation and attempt identities. A LOCAL result cannot stand in for a missing SAAS result and cancellation/retry of one leg does not replay the other.

SentinelX is represented as a transport profile in `lion.model-call/v2`; transport readiness alone is not SaaS-session readiness or cognitive completion. Existing `mission_model_calls/v1` storage is not silently widened. The v2 contract provides a projection adapter and explicitly preserves: missing v1 row != proof of no SaaS invocation.

## EBLE

`lion.evidence-bound-learning-episode/v1` is read-only evidence composition. It does not own queues, scheduler assignments, sessions, broker persistence, authority or truth. It binds message/invocation/attempt/assignment/model-call/receipt/result/observation/reconciliation references and projects a validated episode into existing `EvolutionaryRnD` as `EvidenceObservation`.

```text
event_time
observation_time
ingestion_time
available_to_model_at
input_cutoff
decision_time
```

Post-decision evidence may label the outcome but cannot enter reconstructed pre-decision input. Teacher output is proposal/weak label, never automatic ground truth. Confirmed success/failure requires grounded evidence plus reconciliation. Private chain-of-thought is outside the episode contract.

## ModelRelease

`lion.model-release/v1` is immutable identity over base weights, adapter, tokenizer, chat template, prompt profile, tool schema, runtime and knowledge release. Lifecycle state is separate from the release digest. Task2 performs no training, evaluation promotion, shadow promotion or approval effect.

## Coordinator competency

Ten competencies are evaluated independently; there is no aggregate coordinator quality score. Better competency evidence never widens authority.

## HMK-9D

`chunk-chunk` may supply trajectory annotation, transition semantics and diagnostic representation. Matched ablation requires the same corpus, ModelRelease, prompt/tool/runtime configuration, with A=no HMK-9D annotation and B=annotation. HMK-9D is not authority, ground truth, declared training reward or hardware-energy measurement.
