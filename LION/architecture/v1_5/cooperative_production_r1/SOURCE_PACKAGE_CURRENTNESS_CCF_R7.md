# LION source-package CCF R7 — exact CI effect-relocation reconciliation

Status: SOURCE_ONLY_NOT_DEPLOYMENT.

Predecessor CCF R6 is immutable (Git blob SHA-256
b5110764379b5b70d061ac053c30a234ccd5726f2b019be8aecf65724049ea79).
R7 adds the exact P0 bridge INSERT location-relocation regression to the
source package after an observed CI failure in PR #456, run
38535489639 / job 115757247033.

The P0 historic origin (b6cc132095deb268b2754d2afc0634aeac5a7ac4)
and 567 historical source surfaces are NOT rewritten. A canonical
conversation binding/epoch/context fence inserted before the existing
bridge INSERT relocates its scanner line identity from 553 to 561.
The historical and candidate SQL-write AST, class and effects remain
identical. Only that exact one-to-one relocation is recognized.

The original source validation requires exact Git-index source hashes,
an R7 package digest and two carrier-last truth paths. Source/currentness
PASS is not permission to merge, deploy, mutate operator profiles,
rebind historical conversations, retry queued SaaS requests or start LPCL.
