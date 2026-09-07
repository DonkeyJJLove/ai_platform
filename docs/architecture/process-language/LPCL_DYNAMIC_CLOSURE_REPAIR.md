# LPCL dynamic closure repair — R21 successor

```text
STATUS=CANDIDATE_REPAIR_PENDING_EXACT_HEAD_CI
PARENT_HEAD=410802aea8c19ff4c49b87d2ab768345b3366d0b
PARENT_TREE=491b4ec434d2e79878ba5ed9ebf29721f50f0f1f
AUTHORITY_EFFECT=NONE
RUNTIME_EFFECT=NONE
```

This successor preserves the independent falsification of the original LPCL candidate rather than rewriting it. Against the parent head, F8, F11 and F20 were confirmed: currentness could be represented by an unverified label, retry state was not dynamically consumed, and caller-constructed `ProcessTransitionOutcome` could advance process state without proving the preceding legal selection.

## Historical counterexamples

- CEX-01: `UNKNOWN` could be replaced by caller-asserted `PASS`.
- CEX-02: an `ACTION_REQUIRED` transition could be closed with caller-supplied `consequential=false`.
- CEX-03: `attempt_counts` were not advanced by accepted outcomes.
- CEX-04: currentness satisfaction was string membership, not evidence-bound state.
- CEX-05: control directives could be paired with arbitrary valid `next_state` values.
- CEX-06: ProcessIR and ProcessTransitionOutcome used different outcome vocabularies.
- CEX-07: a syntactically valid but self-fabricated transition-decision record could be supplied unless the closure re-derived canonical selector evidence.

These remain historical evidence for the parent head and are not deleted when repaired.

## Dynamic closure repair

The repaired path is:

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

`apply_transition_outcome` re-runs selection against the exact context, reconstructs the canonical decision record, and requires its digest to match the supplied record. Therefore `UNKNOWN`, `BLOCKED`, `HANDOFF_REQUIRED`, stale context, an unselected transition, or a fabricated decision record cannot be promoted through the feedback boundary.

## Currentness

`CurrentnessBasis` is now a digest-bound process evaluation type. It binds requirement id, subject, observed identity, evidence reference, observation time, currentness state and drift rule. Bare compatibility labels remain parseable in `ProcessContextSnapshot` only for migration, but `TransitionSelector` does not use them as currentness proof.

Supported basis states are `CURRENT`, `STALE`, `NOT_REVALIDATED` and `UNKNOWN`. A required basis must be sealed, evidence-bound and `CURRENT`; otherwise the transition remains `UNKNOWN`.

## Retry and replay

`max_attempts` means the number of additional attempts after the initial attempt. Every accepted outcome creates an immutable `AttemptRecord` and advances `attempt_counts`. A transition with `max_attempts=0` is therefore ineligible immediately after its first accepted failed attempt.

For `NON_IDEMPOTENT + RECONCILE_FIRST`, a retry is legal only when the exact immediately preceding attempt record carries reconciliation evidence. An unrelated process-level reconciliation reference does not satisfy this check.

## Action-required consequentiality

Consequentiality is no longer caller-controlled. `ProcessTransitionOutcome` does not carry a `consequential` boolean. The canonical `TransitionSpec.transition_class` determines whether downstream evidence is required. For `ACTION_REQUIRED + PASS`, the process closure requires action, proposal, runtime-admission, effect, independent-observation, reconciliation and currentness-basis references.

This does not make LPCL an Action, PDP, RuntimeAdmission or effect plane. These fields are evidence references consumed at the Process boundary; LPCL still cannot mint authority or execute the referenced effects.

## Directive semantics

`CONTINUE`, `DEFER`, `HANDOFF`, `STOP` and `COMPLETE` are control directives, not aliases for arbitrary process states. A directive outcome must preserve the current process state and updates the separate process-control dimension:

```text
CONTINUE → ACTIVE
DEFER    → DEFERRED
HANDOFF  → HANDOFF_REQUIRED
STOP     → TERMINATED
COMPLETE → COMPLETE
```

The selector refuses future transition selection when the process-control state makes continuation illegal.

## Outcome vocabulary

The canonical ProcessIR and ProcessTransitionOutcome vocabularies now both include:

```text
PASS
FAIL
UNKNOWN
DRIFT
BLOCKED
AUTHORITY_BOUNDARY
COMPLETE
```

The executable regression suite asserts equality.

## Executable falsification

`cyber_lion/tests/test_lpcl_dynamic_closure.py` preserves and re-tests the closure counterexamples, including decision/context/digest substitution and retry-attempt lineage.

`cyber_lion/process_language/negative_corpus.json` maps N01-N25 to concrete test names in `cyber_lion/tests/test_lpcl_negative_corpus.py`. The negative corpus is therefore an executable invariant set rather than documentation-only policy.

`cyber_lion/tests/test_process_reference_corpus.py` now exercises dynamic selection and closure for all 12 reference scenarios rather than only parser round-trips.

## Invariants preserved

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
```

LPCL remains in the existing `EVOLUTIONARY_EPOCH` architecture layer with `GOVERNED_SELF_IMPLEMENTATION` as a cross-concern. No sixteenth top-level architecture layer is introduced and `EvolutionaryEpochEngine` remains a specialized canonical state machine.

## Closure gate

This document does not claim integration. Candidate repair is complete only after focused tests, production/effect-surface currentness reacquisition, full exact-head CI, readback and an independent semantic verifier bound to the resulting exact head/tree.
