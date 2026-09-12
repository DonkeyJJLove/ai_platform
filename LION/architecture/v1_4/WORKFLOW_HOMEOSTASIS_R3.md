# Workflow Homeostasis — R3 rebased candidate

Snapshot source: `cee7861fb548e01db7678a83dfe43fae477c3ab2` / `17abcb6921fa46577c59ee3d2014aef4863b756b`. Inventory contains **21** workflow files. This stage changes no GitHub permission scope and no secret scope.

## Materialized local fixes

- `bandit-security.yml`: exact candidate checkout, explicit HEAD/TREE readback, `persist-credentials: false`, JSON evidence, artifact SHA-256 and retained artifact.
- `cyber-lion-contracts.yml`: bounded job timeouts and non-persisted checkout credentials for core/admission/observation jobs.
- `lion-repository-maintenance-sandbox.yml`: `actions/checkout@v6` and `actions/setup-python@v6`; authority semantics and permissions unchanged.

Dedicated workflow contract tests: **25 PASS / 0 FAIL** before the workflow commit. A new remote exact-head CI result does not exist until publication; local green tests are not remote CI.

## Remaining review classes

Several workflows intentionally lack a generic HEAD/TREE evidence block because their trigger or evidence model differs. They are not automatically marked defective. Future generations should prioritize exact-head evidence where a workflow makes a security/currentness claim, artifact digest output where evidence is consumed later, and bounded concurrency only when cancellation cannot destroy required evidence. Pinned action SHAs are not downgraded merely because they are not written as `@v6`.
