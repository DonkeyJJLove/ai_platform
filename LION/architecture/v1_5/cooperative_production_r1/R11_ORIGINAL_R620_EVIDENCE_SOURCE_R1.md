# R11 original R6.20 preparation evidence from independent sources

Status: SOURCE_ONLY / NOT_INSTALLED / NO_PRODUCTION_AUTHORITY.

The existing R6.21 CooperativeRuntimePreparationProvider needs an
independently issued, exact CooperativeRuntimePreparationEvidence to call
its ORIGINAL RuntimeAdmissionEngine. Before this source increment there
was no first-party adapter joining the twelve original typed input
contracts to a live canonical MD001 HELD assignment. That absence is
not repaired by guessing grants from Mission Control receipts.

The new ReadOnlyOriginalR620EvidenceSource consumes a PREEXISTING
independent original input source with resolve_exact(assignment,
mission, generation, input_digest, trusted_now). That source must
return OriginalR620PreparationParts, with all twelve original typed
objects already supplied by their legitimate upstream producers.
The parts input owner, the R6.20 output source, and the canonical PDP
reader use separate exact source/trust bindings.

The adapter reads one exact canonical Mission Control assignment via the
existing _ReadOnlySQLite helper (mode=ro, query_only=ON), requires
HELD, exact mission, MD001, generation and input digest, obtains the
independent upstream typed parts, calls the original R6.20 pure
validate_cooperative_runtime_preparation_inputs() and
bind_allowed_action_to_runtime_inputs(), then compares the bound
canonical PDP evidence to an EXISTING read-only original
SQLiteR11CanonicalPDPEvidenceReader and separately current original
policy binding. It rereads the assignment after assembly to reject drift.
It neither calls the original CanonicalPolicyDecisionPoint.evaluate()
nor issues LiveAuthorityAdmission or RuntimeAdmission, provisions a
worker, writes SQLite or starts Docker.

Clock closure: R6.21 captures one trusted_now BEFORE resolving upstream
preparation evidence. The existing R6.21 provider accepts an optional
resolve_at(assignment_id,trusted_now) method and the original R11 service
adapter forwards exactly that bound clock to this R6.20 source. Its
input owner must return the same sealed currentness trusted_now.
A normally advancing clock is accepted within five seconds, but
rollback, stale clock, missing currentness, stale PDP, changed
assignment or duplicate/mismatched source binding are rejected.

The original one-argument evidence_source(assignment_id) remains
compatible for historical bounded fixtures and legacy callers.
Time-source compatibility is not evidence of production readiness.
The isolated full original chain R6.20 -> R6.21 -> R6.16 -> R6.17
now exercises one HELD MD001 with the source's joined twelve contracts;
it reaches source-bound preactivation PASS while producing zero material
artifact execution receipts and no artifact output bytes. These observations
prove only the exact isolated integration, not actual deployment.

All acceptance fixtures here are disposable and synthetic, including
the upstream original input owner and PDP record. The actual
independently authenticated original owner inputs and protected
zero-argument service module remain UNINSTALLED on LION-AUTH-LAB.

SOURCE_NOT_AUTHORITY; POLICY_ALLOW_NOT_ADMISSION;
NO_MERGE; NO_DEPLOY; NO_MD001_START; NO_LPCL_START.

First missing live producer: independently attested original R6.20
twelve-part source and current PDP decision/policy/authority issued
under the exact original governance for Application Factory/MD001.


## Original operator/driver fence before RuntimeAdmission

A canonical HELD assignment is necessary but NOT proof that its
original operator authority, driver generation or capability remains
current. The original scheduler historically verifies these before
HELD->READY release, but the R6.21 preparation provider can consume
its admission replay key and journal a RuntimeAdmission earlier.

The R11 read-only source now reacquires the original
mission_operator_control, operator_capability_revocations and
mission_execution_drivers tables, refusing absent control/schema
rather than treating absence as no revocations. Before requesting any
independently issued twelve-part preparation inputs, it calls the
existing operator_control.assignment_allowed and
operator_control.is_capability_revoked on canonical SQLite and checks
the same assignment control_epoch, context_revision, plan_revision,
driver generation and original allowed driver states (ACTIVE, WAITING,
BLOCKED). It does not create an alternative authorization policy or
change the original scheduler's release check.

The entire fence is checked again after the original PDP, input source
and current-policy readback; a PAUSE or operator epoch transition
during R6.20 collection denies rather than continuing to admission.
Original R6.21 still validates all of its own guards. This preflight
reduces stale source acceptance but cannot eliminate every concurrent
post-preflight operator change; effect-time and HELD->READY fences stay
mandatory separate boundaries.

Disposable negative tests cover PAUSE, STOP, owner/epoch changes,
context/plan revision changes, revoked capability, missing revocation
schema/control row, driver generation or terminal state, and a PAUSE
arriving during original input-source collection. The original R6.21
consumer regression observes zero newly consumed admission replay
rows, no durable RuntimeAdmission and no PREPARING journal after
operator PAUSE. Tests are synthetic isolation, not production
operator/issuer attestation.


## Actual signed R6.20 input source consumer

SQLiteSignedOriginalR620PartsSource supplies the missing concrete,
read-only source of the twelve original R6.20 parts in a cryptographically
authenticated format. See R11_SIGNED_ORIGINAL_R620_PARTS_R1.md.
Its true production issuer, signing key's authorization provenance and
already-issued signed records MUST be established independently.
The test-only Ed25519 signer is NOT a canonical production source.
