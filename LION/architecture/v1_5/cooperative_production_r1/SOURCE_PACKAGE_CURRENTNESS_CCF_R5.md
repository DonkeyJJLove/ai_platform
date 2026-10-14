# LION source-package CCF R5 — exact source successor

**Status:** `SOURCE_ONLY_NOT_DEPLOYMENT`. New source epoch on top of PR #454. No automatic desktop switching, live SaaS response or runtime grant is implied.

The existing `SOURCE_PACKAGE_MANIFEST_CCF_R4.json` describes the prior source epoch and is immutable historical evidence. The new `SOURCE_PACKAGE_MANIFEST_CCF_R5.json` supersedes it **only as the source-validation package** selected by the original `tools/lion_r24_whole_integration_gate.py`. The old `LION/evidence/r24-whole-integration/PACKAGE_MANIFEST.json` remains separately classified historical runtime evidence.

R5 binds Git-index blob bytes, not uncommitted Windows CRLF-transformed working files. Its source path set includes the prior R4 package owners plus the new browser, release-selector, canonical bridge/domain, staging inventory, non-destructive legacy census, documentation and tests. The current release is anchored to its source Git identity; all changed R5-package paths must be hashed again when code changes. The R5 manifest excludes itself and the truth carriers to avoid a self-referential digest.

Update order:

1. Review original owners and dependencies. Stabilize non-carrier source changes and commit them.
2. Materialize a **new** manifest from the exact committed source bytes. Never overwrite R4 or earlier versions.
3. Commit the R5 manifest and validate its exact package digest with the original source gate.
4. Compute truth-plane subject over the Git tree excluding the existing `CARRIER_PATHS` only.
5. Update exactly the declared `baseline.subject_digest` and `registry.generated_from` carriers as a final isolated commit. Run source and full closure tests on the exact final HEAD.
6. GitHub PR, merge, local release installation, native desktop cutover and actual SaaS Model Chat receipt remain separate decisions and readbacks.

A green R5 source package means **source integrity only**. It must not claim that pending historical requests were delivered or that the Windows operator's shortcut was upgraded.
