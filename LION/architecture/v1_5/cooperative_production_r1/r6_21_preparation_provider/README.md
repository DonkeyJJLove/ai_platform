# R6.21 durable preparation provider — formalization preview

Status: `STACKED_SOURCE_CANDIDATE / NOT_DEPLOYED`.

Parent source commit:
```text
b20e0c385bb9d0f1bbbffe3fa94e3ef04dc0d415
```

Non-generated source tree:
```text
3ff8a579f1ee3c0ae2c34bf4d9e0baf20f294932
```

Candidate digest:
```text
096902f1a3c85573d1636835ce8ac51286af298005ca7cf362957b9f992085ee
```

Compilation digest:
```text
bda820b4275ff076c49af99a80af1d5360409335bdebfbb1365e264e1b3e929e
```

The existing ArchitectureCompiler derives 33 formalization surfaces and stops before admission.

R6.21 composes the existing R6.20 preparer, R6.9 durable admission source and R6.16 materializer. It journals preparation, supports restart reconstruction from an already-issued durable admission, and leaves ambiguous post-replay/pre-journal failure as `ADMISSION_ISSUANCE_UNKNOWN` with no automatic retry.

The vertical acceptance uses current Mission Control storage/migrations and proves durable RuntimeAdmission publication plus independent R6.16 readback and canonical HELD-to-READY transition without writing artifact bytes.
