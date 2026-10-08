# R6.20 runtime preparer — formalization preview

Status: `STACKED_SOURCE_CANDIDATE / NOT_DEPLOYED`.

Parent source commit:

```text
1eacd0fab0cfa5f6672fc37a7a46c3258769fca8
```

Non-generated source tree:

```text
3fb9fe64f1424397b6eed833036a2f08219799d9
```

Candidate digest:

```text
942fde6343c87ac434d8f5ba0a31ae3b61973ec8526f77d1597583785c6885bf
```

Compilation digest:

```text
40246f2c706ff76a25aa4a82136541bc5fcd3b15bd56df4b8642778fdd8720a2
```

The existing ArchitectureCompiler classifies this as a bounded CAPABILITY increment and derives 33 formalization surfaces. It stops before admission.

The implementation composes one exact HELD cooperative WRITE assignment with existing Action/PDP/currentness/live-authority/provisioning/sandbox evidence, delegates admission to the existing `RuntimeAdmissionEngine.admit_bound_action(...)`, and returns `CooperativeRuntimeContext`.

The prepared context is then reusable by existing R6.16 without re-running admission. The vertical integration test proves:

```text
current Mission Control storage/migrations
→ HELD WRITE
→ R6.20 prepare once
→ immutable prepared context source
→ R6.16 provider evidence export
→ canonical HELD→READY transition
→ no artifact bytes written
```

No live Mission Control database, worker container, Git ref, mission activation or artifact path is mutated by this candidate.
