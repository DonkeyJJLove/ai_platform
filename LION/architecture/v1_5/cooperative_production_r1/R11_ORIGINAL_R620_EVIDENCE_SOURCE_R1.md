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
