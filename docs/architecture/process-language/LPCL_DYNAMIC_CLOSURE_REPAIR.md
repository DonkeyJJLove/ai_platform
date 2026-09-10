# LPCL — naprawa dynamic closure, następca R21

```text
STATUS=CANDIDATE_REPAIR_PENDING_EXACT_HEAD_CI
PARENT_HEAD=410802aea8c19ff4c49b87d2ab768345b3366d0b
PARENT_TREE=491b4ec434d2e79878ba5ed9ebf29721f50f0f1f
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
```

Ten historyczny successor zachowuje niezależną falsyfikację pierwotnego kandydata LPCL zamiast ją przepisywać. Względem parent head potwierdzono F8, F11 i F20: currentness mogło być reprezentowane przez niezweryfikowaną etykietę, retry state nie było konsumowane dynamicznie, a skonstruowany przez caller `ProcessTransitionOutcome` mógł przesuwać process state bez udowodnienia poprzedzającego legal selection.

## Historyczne kontrprzykłady

- CEX-01: `UNKNOWN` mogło zostać zastąpione caller-asserted `PASS`.
- CEX-02: transition `ACTION_REQUIRED` mogła zostać zamknięta caller-supplied `consequential=false`.
- CEX-03: `attempt_counts` nie były zwiększane przez accepted outcomes.
- CEX-04: currentness satisfaction było string membership, a nie evidence-bound state.
- CEX-05: control directives można było połączyć z dowolnymi poprawnymi wartościami `next_state`.
- CEX-06: `ProcessIR` i `ProcessTransitionOutcome` używały różnych outcome vocabularies.
- CEX-07: syntaktycznie poprawny, lecz self-fabricated transition-decision record mógł zostać podany, jeśli closure nie odtwarzało ponownie canonical selector evidence.

Te kontrprzykłady pozostają historical evidence dla parent head i nie są usuwane po naprawie.

## Naprawa dynamic closure

Naprawiona ścieżka:

```text
CanonicalProcessIR
+
ProcessContextSnapshot
→ TransitionSelector
→ canonical TransitionDecisionRecord
→ ProcessTransitionOutcome bound to decision digest
→ dynamic semantic verification
→ ProcessState / process-control state
```

`apply_transition_outcome` ponownie uruchamia selection względem exact context, odtwarza canonical decision record i wymaga, aby jego digest odpowiadał supplied record. Dzięki temu `UNKNOWN`, `BLOCKED`, `HANDOFF_REQUIRED`, stale context, unselected transition albo fabricated decision record nie mogą zostać promowane przez feedback boundary.

## Currentness

`CurrentnessBasis` jest digest-bound process evaluation type. Wiąże requirement id, subject, observed identity, evidence reference, observation time, currentness state oraz drift rule. Bare compatibility labels pozostają parsowalne w `ProcessContextSnapshot` wyłącznie dla migracji, ale `TransitionSelector` nie używa ich jako dowodu currentness.

Obsługiwane basis states to `CURRENT`, `STALE`, `NOT_REVALIDATED` oraz `UNKNOWN`. Wymagany basis musi być sealed, evidence-bound i `CURRENT`; w przeciwnym razie transition pozostaje `UNKNOWN`.

## Retry i replay

`max_attempts` oznacza liczbę dodatkowych prób po próbie początkowej. Każdy accepted outcome tworzy immutable `AttemptRecord` i zwiększa `attempt_counts`. Transition z `max_attempts=0` staje się więc ineligible natychmiast po pierwszej accepted failed attempt.

Dla `NON_IDEMPOTENT + RECONCILE_FIRST` retry jest legalne tylko wtedy, gdy dokładnie poprzedzający `AttemptRecord` zawiera reconciliation evidence. Niezwiązany process-level reconciliation reference nie spełnia tego warunku.

## ACTION_REQUIRED, consequentiality i downstream evidence

Consequentiality nie jest już kontrolowane przez caller. `ProcessTransitionOutcome` nie posiada boolean `consequential`. To canonical `TransitionSpec.transition_class` określa, czy downstream evidence jest wymagane.

Dla `ACTION_REQUIRED + PASS` **niepuste stringi nie są evidence**. Outcome carrier musi być uzupełniony przez niezależnie zmaterializowane `CanonicalDownstreamEvidence`, którego elementami są istniejące canonical contracts, a cross-bindings są ponownie weryfikowane przed przesunięciem `ProcessState`:

```text
ActionIntentCandidate
→ CanonicalActionIR
→ ExplicitActionProposalContext
→ ActionProposal
→ CanonicalPDPDecisionEvidence
→ RuntimeIdentityBinding
→ RequestedRuntimeEffect
→ RuntimeAdmission
→ EffectTimeCurrentnessEvidence
→ RuntimeExecutionReceipt
→ RuntimeEffectObservation
→ RuntimeReconciliationReceipt(MATCHED)
→ ProcessTransitionOutcome
```

Verifier wymaga, aby Action IR wiązał wybrany `ActionIntentCandidate`, proposal był reprodukowany przez istniejący binder LAIR→ActionProposal, PDP evidence wiązało exact admission, requested effect i runtime identity wiązały to admission, runtime receipt raportował zaobserwowany successful effect, independent observation odpowiadała receipt, a reconciliation receipt była anomaly-free `MATCHED`. Referencje action/proposal/admission/effect/observation/reconciliation w outcome muszą odpowiadać canonical digests. Self-consistent zestaw arbitralnych references bez tego oddzielnego typed chain jest odrzucany.

Nie czyni to LPCL warstwą Action, PDP, RuntimeAdmission ani effect. `CanonicalDownstreamEvidence` nie wykonuje admission, execution, observation, reconciliation ani authority decision; jedynie weryfikuje już zmaterializowane canonical objects na Process feedback boundary.

## Semantyka directive

`CONTINUE`, `DEFER`, `HANDOFF`, `STOP` i `COMPLETE` są control directives, a nie aliasami dla arbitralnych process states. Directive outcome musi zachować bieżący process state i aktualizować oddzielny process-control dimension:

```text
CONTINUE → ACTIVE
DEFER    → DEFERRED
HANDOFF  → HANDOFF_REQUIRED
STOP     → TERMINATED
COMPLETE → COMPLETE
```

Selector odmawia future transition selection, gdy process-control state uniemożliwia legalną kontynuację.

## Outcome vocabulary

Canonical `ProcessIR` oraz `ProcessTransitionOutcome` mają ten sam vocabulary:

```text
PASS
FAIL
UNKNOWN
DRIFT
BLOCKED
AUTHORITY_BOUNDARY
COMPLETE
```

Executable regression suite sprawdza ich equality.

## Wykonywalna falsyfikacja

`cyber_lion/tests/test_lpcl_dynamic_closure.py` zachowuje i ponownie testuje closure counterexamples, w tym decision/context/digest substitution oraz retry-attempt lineage.

`cyber_lion/tests/test_process_semantics.py` zawiera obie strony granicy B8: kompletnie wyglądający self-attested reference set jest odrzucany, natomiast exact cross-bound istniejący łańcuch Action/PDP/runtime/currentness/execution/observation/reconciliation może zamknąć `ACTION_REQUIRED + PASS`. Podmiana observation reference jest odrzucana.

`cyber_lion/process_language/negative_corpus.json` mapuje N01–N25 na konkretne test names w `cyber_lion/tests/test_lpcl_negative_corpus.py`. Negative corpus jest więc executable invariant set, a nie documentation-only policy.

`cyber_lion/tests/test_process_reference_corpus.py` wykonuje wszystkie 12 reference scenarios. Internal transitions mogą zamknąć się lokalnie, gdy ich evidence jest spełnione. Generic `ACTION_REQUIRED` reference scenarios zatrzymują się na jawnej granicy `AUTHORITY_BOUNDARY → HANDOFF_REQUIRED` zamiast fabrykować downstream runtime success; pełny downstream `PASS` jest dowodzony wyłącznie przez dedykowany canonical-chain test.

## Zachowane inwarianty

```text
PROCESS_TEXT != AUTHORITY
TRANSITION_SELECTION != ACTION_EXECUTION
ActionIntentCandidate != ActionSpec
ActionSpec != ActionProposal
ActionProposal != PDP_ALLOW
PDP_ALLOW != RuntimeAdmission
RuntimeAdmission != Effect
Effect != Observation
Observation != Reconciliation
CALLER_ASSERTED_OUTCOME != VERIFIED_PROCESS_OUTCOME
SELF_ATTESTED_DOWNSTREAM_REFS != CANONICAL_DOWNSTREAM_EVIDENCE
```

LPCL pozostaje w istniejącej architecture layer `EVOLUTIONARY_EPOCH`, z `GOVERNED_SELF_IMPLEMENTATION` jako cross-concern. Nie wprowadza się szesnastej top-level architecture layer, a `EvolutionaryEpochEngine` pozostaje specialized canonical state machine.

## Closure gate

Ten dokument nie deklaruje integracji. Status i parent identity powyżej dotyczą historycznego repair candidate. Każda bieżąca klasyfikacja wymaga reacquisition względem aktualnego exact head/tree.

Candidate repair w swojej epoce był kompletny dopiero po focused tests, production/effect-surface currentness reacquisition, full exact-head CI, readback i independent semantic verifier związanym z wynikowym exact head/tree.
