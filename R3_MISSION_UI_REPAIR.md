# Conversation cancellation and compact mission records

Deleting a conversation cancels only its saved pending SaaS requests before removing the conversation. Failed cancellation preserves the conversation for retry. The browser stops its polling and ignores an aborted chat response; a backend response arriving after deletion cancels its newly created handoff. Global pending requests are no longer attached to an arbitrary open conversation. A queued request is explicitly described as awaiting an operator, with no automatic delivery claim.

Mission deletion previews the selected record and requires its exact specification digest. A writer transaction rechecks eligibility, removes owned local records, and retains an ID-only import suppression marker. Shared runtime ownership, active drivers, claimed assignments and pending commands prevent deletion. Global session attestations and unrelated missions remain intact. This operation never stops workers or dispatches mission execution. External historical source databases are not purged; the suppression marker excludes their deleted records from the panel.

Phase facts use compact labels with hover/focus descriptions and expandable raw records. Recent events use colored buttons. Mission selectors truncate long labels and keep full names in tooltips. Both panels provide mission deletion controls.

The reported SaaS Bridge R1 mission is blocked by its obsolete PR337 source binding and missing continuation contract. Its recorded authorization is not evidence of execution. The panel now exposes the returned runtime state and stored error; no execution gate is bypassed by this repair.

Validation before deployment: focused cancellation/lifecycle tests; real Edge with isolated HTTP fixtures for conversation polling; actual Mission Control HTTP server with disposable SQLite for deletion and responsive selector layout. These checks do not launch an observer, driver loop, external executor, or live SaaS request. Deployment, live cleanup and merge require separate readback and current CI evidence.

Inventory review: the committed production source scan still covers 338 sources and 313 classified surfaces, with zero unresolved taxonomy entries. The existing gateway control dispatch handles cancellation and record deletion; no new execution adapter or worker operation is introduced. Package manifest hashes and live scan expectations are recomputed from this candidate. Historical fixtures remain historical.
