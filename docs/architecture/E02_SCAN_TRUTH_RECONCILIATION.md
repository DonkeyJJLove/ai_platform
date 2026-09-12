# E02 local scan and truth reconciliation

This change starts from local snapshot 0191cf29ff2a5cd4a74a2bcf154d62f96daab6a5
(tree bab3a8390735b63823c52dcf0a5dd234c29a0e0b). It confers no runtime,
publication, independent verification or complete-mediation claim.

## Exact production selector and delta

The existing scanner selects tracked cyber_lion Python excluding tests and
GitHub workflow YAML. Sources increase from 297 to 301; surfaces from 259 to
268. Taxonomy still resolves six references, leaving zero unresolved in this
selector. This is classification, not mediation. The current scan is
871ac2bd8ad43dbb1cd95dbe9e4bb70de413b69e16eeebca83a83aef2f122611.

Nine new persistent_state.write entries belong to the offline result recorder:
lines 43/44 set connection PRAGMAs, 58 inserts metadata, 74/75 set per-connection
PRAGMAs, 104 reserves an attempt, and 148/150/152 insert the receipt and index
and update the attempt. The existing scanner classifies those PRAGMAs as writes;
this change does not hide them. Schema creation and opening a database are also
effects to consider manually: this inventory is not an exhaustive proof.
All nine entries remain UNKNOWN, without runtime evidence, binding, chain or
bypass evidence. A regression assertion protects that boundary.

Thirteen F009 entries change only their line-derived identity after addition
of the closing import. Old to new lines are 83 to 85; 144 to 146 (two writes);
145 to 147; 148 to 150 (two unlinks); 206 to 208; 209 to 211; 306 to 308;
309 to 311; 322 to 324; 342 to 344; 403 to 405. The SQLite context change closes
connections explicitly while preserving transaction semantics. Old receipts
are not relabeled as evidence for the new identities.

## Literal classification

CURRENTNESS_CARRIER: EXPECTED_SCAN_DIGEST in surface_closure_campaign,
moon_seven_binding, moon_attested_adjudication, moon_readonly_observer_falsification
and moon_same_connection_denial_carrier (all under tools/p0_*) guards supplied
current inventory. Their corresponding current-inventory test expectations
and runner bridge CURRENT_SCAN are updated to the measured digest.

TOPOLOGY_CONTRACT: the current inventory test now checks 301/268/6. The closure
campaign has 267 items after one historical exclusion: seven PARTIAL and 260
UNKNOWN; 209 persistent-state writes; 38 multi-surface families containing 253
items plus 14 singleton families. Seven-surface historical-evidence projections
retain their existing seven statuses and add nine UNKNOWN (261 total UNKNOWN).
These projections do not attest current execution or physical independence.

The two current readiness materializers and the v2 readiness report validator
also pin topology counts. Their UNKNOWN guard is now 261. Their report fields
previously still declared 250 despite the prior inventory requiring 252;
unknown_outside_seven_count now consistently equals 268 minus 7, with an
explicit report/inventory consistency regression. Existing historical reports
are retained as historical data and are not rewritten or promoted.

HISTORICAL_FIXTURE / SECURITY_CONTRACT: runner bridge historical scan, source
revision/tree, receipts, semantic anchors, seven surface identities and evidence
references remain unchanged. Mission-control fixture numbers such as 297 passed
are unrelated to inventory and remain unchanged. Historical generated reports
are preserved. No global digest replacement or scanner/PDP change is made.

## Truth and outstanding gates

Commit non-carrier changes first. Compute LION/TRUTH-SUBJECT/1 from that exact
Git tree with the canonical two carrier exclusions. Update only baseline
subject_digest and registry generated_from, then commit those two carriers last.
External evidence records the final commit/tree and recomputed subject/census.
The broader Python census has a different selector; its unclassified references
must not be conflated with the production taxonomy result.

Remote CI, publication review, trust provisioning, runtime admission and live
mediation remain separate gates. Passive timing observations are neither
encryption nor grants; this change implements no timing channel or live probe.

## Correction of prior exported-byte measurement

The earlier candidate d18835d scan (and baseline 68c940ef scan) hashed CRLF
export bytes produced by git archive under local Git configuration. They are
not canonical Git-blob source scans. Direct Git blobs agree with read_text
inputs used by current inventory tests; their candidate scan is 871ac2bd
above. Preserve the previous artifacts as historical erroneous measurements,
not current pins. Final census uses cat-file blob bytes, avoiding export filters.

The structural PEP blob check also requires exact bytes: the isolated checkout's
mediation_falsification.py was materialized directly from its unchanged Git blob
to remove checkout-only CRLF conversion. Its Git diff remains empty; neither the
historical PEP pin nor its byte identity was changed to accommodate the host.
