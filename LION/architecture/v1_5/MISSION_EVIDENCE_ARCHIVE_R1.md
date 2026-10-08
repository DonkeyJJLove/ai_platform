# LION Mission Evidence and Reasoning Archive R1

**Status:** versioned source candidate; authority effect NONE; live mission owner unchanged.

## Executed archive

On 2026-10-08 a bounded archival operation on LION-AUTH-LAB created archive-history/terminal-history-20261008-r1 inside the installed Mission Control area. The source was tools/lion_mission_evidence_archive_r1.py and the entire output was independently validated.

The archive captures a consistent read-only SQLite snapshot of the canonical ledger and a separate terminal-mission reasoning index. It indexes 28 terminal missions (13 COMPLETE, 15 SUPERSEDED). Four remain protected: AUTHORIZED, REGISTERED, STOPPED, and historically RECORDED_RUNNING. The original live database was not modified or pruned.

The physical SQLite snapshot intentionally retains all 32 mission records so relational references and shared tables remain intact. Only 28 terminal identities are classified ARCHIVED_HISTORY in the manifest. The independent readback confirmed 417,009,664 archived bytes, quick_check ok, exact source and trail SHA-256, 28/28 reasoning trails, 56 mission-scoped tables and private 0700/0600 permissions.

## Functional pipeline

SOURCE SQLite mode=ro and query_only=ON → classify terminal/nonterminal → consistent SQLite backup → evidence and event-type counts by mission → source HEAD/TREE plus receipt/phase/artifact indexes → SHA-256 and atomic receipt → independent readback.

An orphan mission reference, altered digest, invalid schema, unknown identity, unexpectedly changed terminal counts, nonterminal reclassification, preexisting incomplete stage or duplicate inconsistent archive ID must fail closed. Re-running the exact archive ID re-verifies its bytes, without writing a duplicate.

Historical hypotheses not represented in the original source are preserved as UNKNOWN_NOT_STRUCTURED_IN_PREVIOUS_RECORD. No model may fill missing historical causal explanations with fabricated narratives.

## Reasoning-lineage journal

The new tools/lion_reasoning_lineage_journal_r1.py implements a local append-only hash-chained journal per case. Every event preserves its previous digest, unique event ID, evidence and counterevidence digest references, timestamp, epistemic classification and optional exact mission/conversation/binding. It separates SOURCE_FACT, RUNTIME_OBSERVATION, TEST_RESULT, HYPOTHESIS, FALSIFICATION, DECISION and UNKNOWN. A hypothesis is not permitted to claim OBSERVED or PASS. A test PASS needs explicit evidence digests, and evidence references themselves are not guarantees of authority. Duplicate identical events are idempotent; conflicting IDs and modified history are rejected.

The journal is a functioning, tested source component. It does not by itself automatically intercept live Mission Control decisions. Connecting it to existing operator events and the canonical Model Chat requires a separately admitted adapter preserving origin and identity. Do not invent past hypotheses from a model response.

## UI semantics

Mission Control should display a compact active process/phase summary and route operator attention to the appropriate detailed surface. Cluster owns worker health, event/log/receipt projections and artifact inventory. System owns machines, environments, physical failure domains, infrastructure functions, repositories and architecture lineage. LPCL/Model Chat owns conversation and provider binding, not worker execution. An archive/history tab is a read-only projection over verified receipts; it is not a second database owner.

## File and function retirement

Source history in Git remains available by exact SHA and supersession metadata. The archive engine does NOT bulk-delete repository branches, old GUI versions or modules. Retire an obsolete file/function only after source ref, production callers, dynamic invocation paths, active processes, tests and rollback references have been verified. Running services, user worktrees, pending SaaS turns and canonical mission state are excluded from title/age-based cleanup.

## Tests and limits

Seven tests for mission evidence archival; eight tests for the reasoning journal, including tamper and symlink denial. Historical snapshot retention is evidence only, not authority or a current worker binding. Before activating a new LPCL mission, require current capability/provider projections, exact IDs, distinct LOCAL/SaaS context digests, and independent post-effect verification.

## Receipt-only SaaS reconciliation owner

The existing Electron canonical consumer now has a separately operator-triggered receipt-only path. It reads exact canonical Mission Control response and receipt digests for each already submitted request, requires the automatic sender to remain paused, checks every outstanding record before one atomic local dispatch-state update, and NEVER invokes a browser send, creates a SaaS thread, accesses ingress, or creates another mission. Any unverified receipt, digest conflict or timeout fails closed, with no partial local update and no automatic retry. This is a source-only successor capability pending reviewed CI and deployment; it does not make the six new overdue handoffs READY or activate a driver.
