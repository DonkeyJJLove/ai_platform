# Failure and counterexample history

Evidence status: source implementation at `72fbb405f5c023baa4605a53c15f1b7b96533a98`, with inventory/package reconciliation in `6724074`. This is a source description at documentation freeze. Final clean validation, exact-head CI, deployment/restart readback and merge are separately evidenced terminal gates; this document does not predict their outcome. Authority effect: NONE.

The R2 failure matrix classifies historical R1 clean-run evidence rather than replaying it as current validation. It records 2,940 run test methods, 2,921 passed, 3 failures, 10 method errors and 6 skipped. Six additional class-setup error outcomes blocked 44 declared methods. Thus 19 nonpass outcomes are not 19 failed test methods. Eighteen outcomes were production-scan pin drift; one was a stale historical expectation. Exact source corroboration and final rerun are separate obligations.

Recorded 8780 HTML called an undeclared evidenceHtml helper. Runtime/source parity therefore needs browser checks, not only HTTP 200. Previous summary/detail divergence and full DOM replacements motivated the normalized shared view and keyed refresh.

Scheduler counterexamples include equal-clock repeated selection, lost fairness after reopen, and competing receipt content/metadata. The R2 storage candidate preserves durable turns and rejects replay/conflicts; historical conflicting receipts remain evidence instead of being deleted. Phase-control counterexamples include stale generation/source/cursor and false success without durable receipt/readback.

Source-family classification preserves old probes, dirty historical variants and obsolete publication machinery. Do not import old truth/scan pins or report all non-ancestor branches as required missing code. Sources: r2-failure-matrix.json; r2-source-family-disposition.md; repository notes; focused tests.


At commit 6724074 the clean full suite ran 2,998 methods: one expected carrier-last truth failure and three class-setup errors remained. Each setup error traced to the diagnostic outside-seven count 297, inherited from 304 total surfaces. Exact inventory now has 313 surfaces; the unchanged seven-surface set leaves 306 outside it. Commit d8c0639 updates these census expectations, preserving the security obligations and UNKNOWN global status. All 19 methods in the three previously blocked classes then passed. Final truth-bound full regression remains a separate gate.

Post-publication live-test preparation found that global focus changes were coupled to registration/activation. The dedicated metadata-only focus endpoint removes that test and operator hazard. Its four tests cover no activation or unrelated table changes, exact HTTP shape, idempotence and rollback on receipt failure. SQLite fixture connections are explicitly closed so these checks also run on Windows. This source correction invalidates the earlier 496ae45 CI identity; final clean tests and CI must run again after carrier-last rebinding.
