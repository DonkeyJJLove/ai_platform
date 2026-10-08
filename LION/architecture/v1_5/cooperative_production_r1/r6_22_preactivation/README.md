# R6.22 preactivation — formalization preview

Status: `STACKED_SOURCE_CANDIDATE / NOT_DEPLOYED`.

Parent source commit: `245bd4b3fba745142b0358876153ef0ca3cb0846`.

Non-generated source tree: `c7d99780cbcba5398214c27ce7dfa68168765f94`.

Candidate digest: `505ef8f96c378df93544f347145b858f361b05947acfef1518072e1242299dea`.

Compilation digest: `2524ef452c86d70bcaee2da15bf8ac1eb3fb5ab18f489ee3ff936fe78f75c152`.

The existing ArchitectureCompiler derives 33 formalization surfaces and stops before admission.

R6.22 introduces exactly one non-effectful one-worker preactivation capability before the unchanged 32-worker production/verification readiness gate. It persists qualification evidence and an anti-replay journal in the existing mission artifact ledger. It does not claim or execute the qualification assignment.
