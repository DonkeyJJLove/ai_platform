# R11 candidate — canonical R6.17 qualification consumption at R6.22

Status: TESTED_SOURCE_CANDIDATE_NOT_PUBLISHED_NOT_DEPLOYED.
Authority effect: NONE. Execution effect: NONE.
Source baseline: 222d52e57ebf17b950322e2a097f9ed94271cf9c
(tree 68dd5043e6ede09eb5c2c2f348c40205cf2f44b6).

## Reproduced producer–consumer defect

Canonical global_scheduler.release_held_assignment persists
mission_assignment_release_evidence.evidence_digest = digest(full release evidence).
CooperativeRuntimeCompositionRoot.qualify_released_write_assignment (R6.17)
uses this OUTER ledger digest as release_evidence_digest, while its separate
control_plane_evidence_digest is the INNER materializer evidence digest.
Before this candidate, the R6.22 consumer compared the outer field against
the inner digest. The original synthetic test qualifier mirrored that wrong
assumption. Thus a correctly qualified R6.17 result was incorrectly rejected.

## Concrete source delta

R6.22 now reads the complete persisted release record and independently checks
its canonical hash and assignment/mission identity. It checks the R6.17 outer
and inner digests against their respective sources and recomputes the canonical
qualification digest with domain LION/COOPERATIVE-WORKER-QUALIFICATION/1.
The consumer rejects missing, unexpected and substituted qualification fields.
It accepts both optional bootstrap metadata fields only when mode UNBOUND
and version 1.0.0 match the canonical worker qualification entrypoint.

A real R6.17 producer is exercised with disposable SQLite in a producer/consumer
contract test. Additional negative tests reject substituted release/control
digests and an invented qualification digest. Mission Control v3's exact
93-file deployment manifest and its broker pinned hash were updated to
the new candidate source bytes.

## Tests and limitations

Isolated current-master MOON checkout: 288/288 cooperative tests PASS, 114/114
focused mission-control/package tests PASS, 8/8 P0 pinned-history tests PASS
after fetching prior Git objects, and git diff --check PASS.

Tests exercise fixture authority and runtime evidence. They do not demonstrate
production RuntimeAdmission, installed worker provider, material effects, full
LPCL or independently responded SaaS. No live mission or fleet was activated.

## Remaining full-R11 boundary

Existing bootstrap still requires a SHA-pinned external trusted dependency
factory and remains UNBOUND. The full R11 mission must bind current, real
CooperativeRuntimePreparationEvidence to RuntimeAdmissionEngine and canonical
SQLiteRuntimeAdmissionSource, R6.16 materialization, and authenticated R6.17
worker qualification transport for the SAME exact assignment/worker.
Synthetic factories or checksums cannot stand in for runtime authority.

Only after a separately admitted source deployment may a readback verify the
provider's current binding, durable admission, qualification journal, and
worker-private materialization. Full BUILD/VERIFY must retain the separate
32-worker readiness gates and operator activation.
