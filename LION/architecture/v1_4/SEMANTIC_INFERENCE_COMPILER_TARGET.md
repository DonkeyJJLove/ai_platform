# LION Semantic Inference Compiler — target track F

`DOCUMENT_CLASS=LION_FUTURE_ARCHITECTURE_EXTENSION` · `STATUS=TARGET_ARCHITECTURE_CANDIDATE` · `AUTHORITY_EFFECT=NONE` · `RUNTIME_EFFECT=NONE`.

Semantic Inference Compiler (SIC) is the future semantic front-end for LION. Its purpose is not to add another agent, but to stop repeatedly spending probabilistic compute on relationships the system has already discovered, tested and bound to evidence. Its canonical trajectory is `deterministic anchor → probabilistic discovery → semantic compression → probabilistic refinement inside a reduced space → deterministic materialization → reuse → delta`.

The central artifact is `SemanticScaffold` / `SemanticScaffoldIR`, carrying entities, relations, gaps, dependencies, constraints, hypotheses, counter-hypotheses, falsifiers, unknowns, capability needs, representation candidates, evidence bindings, currentness basis and next frontier. A scaffold is never a source of authority. If its evidence or truth subject drifts, currentness degrades and the scaffold becomes stale.

SIC sits upstream of The Bean Factory and acts as a front-end to the future Abstraction Compiler: raw evidence becomes a structured problem space; `Gap` and `CapabilityNeed` become explicit; Bean reuse/generation and CompositionContract build organization; the abstraction/materialization back-end selects representation, schema, validator and verifier. SIC ends before authority. It may produce an ActionSpec candidate but never an effect.

Mission Control is the natural operational view of this compiler. A mission revision can expose current exact state, semantic model, gap, hypothesis, phase, last deterministic commit, last observation, unknown set and next frontier. `ADD_COMPONENT` and `REDESIGN` in Epoch 3 remain non-authoritative revision operations; Epoch 4 may route their structured payloads through SIC before a successor LPCL is generated.

The future development track is `F_SEMANTIC_COMPILATION_AND_INFERENCE_ECONOMY`, progressing from semantic scaffold contract and IR through evidence/currentness binding, semantic delta detection, deterministic reuse decision, inference lineage/falsification, semantic RAG memory, Bean Factory binding, Abstraction Compiler binding, Mission Control semantic process view, local/SaaS equivalence testing, inference-amortization benchmarking and homeostatic semantic compilation.

The invariant added to LION is: `INTELLIGENCE IS NOT AUTHORITY`, `INFERENCE IS NOT MEMORY`, and stable evidence-bound understanding should become reusable structure when falsification and currentness allow it. This track is deliberately target-only at the Epoch 3 boundary and must not be used to bypass unresolved runtime, database or authority frontiers.
