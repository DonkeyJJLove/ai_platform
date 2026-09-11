# TIGER Geometry

Class: PROBABILISTIC_RELATIONAL_REASONING_SCAFFOLD. Authority: NONE. Currentness: NONE. Proof class: HYPOTHESIS_GENERATING_ONLY. HYPOTHESIS_NOT_PROOF; FALSIFICATION_REQUIRED.

Canonical chain: SOURCE → MEANING → INTERPRETATION → AGENT → TOOL → DECISION → ACTION.

Extended chain: OBSERVATION → ENTITIES → RELATIONS → DIRECTION → STATE → TRANSITION → BOUNDARY → AUTHORITY → OBSERVABILITY → HYPOTHESIS → COUNTER_HYPOTHESIS → FALSIFICATION → DETERMINISTIC_PROJECTION → DECISION → BOUNDED_ACTION → OBSERVATION → RECONCILIATION.

Strzałki są pytaniami o wymagane relacje, nie dowodem ich legalności. Węzeł może reprezentować entity, state, evidence, actor, agent, tool, artifact, decision, effect, observer lub carrier. Edge jest relacją; directed edge hipotezą przyczynowości lub kontroli. Gate określa wymagany warunek przejścia; boundary miejsce zmiany semantyki, authority lub klasy efektu. Loop opisuje feedback/retry. UNKNOWN_EDGE zachowuje nieudowodnioną relację. FORBIDDEN_SHORTCUT spłaszcza wymagane granice.

## Operacje analizy

EXPAND_NODE i EXPAND_EDGE rozbijają ukryte założenia. INVERT_RELATION sprawdza alternatywną przyczynowość. TRACE_ANCESTRY/TRACE_DESCENDANTS badają zależności. SEARCH_MISSING_EDGE, SEARCH_DUPLICATE_EDGE i SEARCH_CYCLE ujawniają braki, pozorną niezależność i pętle. SEARCH_HIDDEN_STATE_TRANSITION oraz SEARCH_UNOBSERVED_TRANSITION szukają zmian bez dowodu.

SEARCH_AUTHORITY_JUMP, SEARCH_CURRENTNESS_JUMP, SEARCH_EFFECT_JUMP, SEARCH_OBSERVER_COLLAPSE i SEARCH_BUILDER_VERIFIER_COLLAPSE sprawdzają granice LION. GENERATE_COUNTER_GRAPH i GENERATE_COUNTER_HYPOTHESIS muszą dopuścić wynik przeciwny. SEMANTIC_MUTATION, EDGE_REMOVAL_TEST, EDGE_SUBSTITUTION_TEST, ORDER_REVERSAL_TEST i BOUNDARY_COLLAPSE_TEST są eksperymentami na kopii grafu, nie zmianami oryginalnego wejścia ani runtime.

## Krawędzie wymagające odrzucenia jako nieudowodnione

MODEL_OUTPUT → VERIFIED; PROPOSAL → EFFECT; PDP_ALLOW → EFFECT; COMMIT → DEPLOYED; CI_PASS → PRODUCTION_READY; RECEIPT → RECONCILED; RAG_CURRENT → LIVE_CURRENT; TOOL_AVAILABLE → AUTHORIZED; BUILDER_OUTPUT → INDEPENDENT_VERIFICATION; PROCESS_EXIT_ZERO → PHYSICAL_OR_RUNTIME_POSTCONDITION.

Każdy przypadek zapisz jako: source refs, nodes, candidate edges, gate, unknowns, hypothesis, counter-hypothesis, discriminating test, observed result, bounded conclusion. Przykład: zielone CI dla wcześniejszego HEAD pozwala postawić hipotezę małej regresji, lecz kontrhipoteza nowej awarii wymaga testu bieżącego HEAD. Nie rysuj krawędzi stare CI → bieżący PASS.

Graf może być spójny, elegancki, gęsty semantycznie i matematycznie interesujący, a nadal nieudowodniony. TIGER → hypothesis → falsification plan → deterministic or empirical test → evidence. Wynik testu rozstrzyga wyłącznie jego zakres. Ocena heurystyczna nie jest prawdopodobieństwem skalibrowanym ani zgodą na działanie.
