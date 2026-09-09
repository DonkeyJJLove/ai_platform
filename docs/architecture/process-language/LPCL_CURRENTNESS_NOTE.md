# LPCL v1.1 candidate currentness note

The current v1.1 language-interpretation candidate was branched from default-branch base `70929bb895726c0b4a552295e595e373191b0d2b` / tree `0c463f98122145a1a39287240136d1a824a8038c`.

Candidate HEAD/TREE are intentionally not embedded here because every noncarrier write would immediately stale that value. Exact candidate identity must be reacquired from `architecture/lpcl-canonical-interpretation-r1` at each verification or action boundary.

Currentness subjects remain distinct:

```text
MASTER_IDENTITY
CANDIDATE_IDENTITY
PROCESS_SOURCE_SET
LPCL_CONFORMANCE_PROFILE
ARCHITECTURE_PROJECTION
TEST_EXECUTION_IDENTITY
TRUTH_SUBJECT
TRUTH_CARRIERS
POST_MERGE_MASTER_IDENTITY
```

Documentation or source presence does not prove integration. The existing `LION/architecture/v1_4/current_state.json`, capability catalog and repository truth carriers remain historical/currentness projections until carrier-last rebind after noncarrier verification. They must not be manually promoted early.

A new source file under the production source set can change source-set currentness digests even when it adds no consequential effect surface. Any resulting scan-digest drift must be observed and reconciled from exact candidate execution evidence rather than guessed from chat state.

PR CI, if later used as a validation carrier, must bind the exact candidate head and its checkout/synthetic merge identity. Pre-PR source review is not a substitute for executed tests.
