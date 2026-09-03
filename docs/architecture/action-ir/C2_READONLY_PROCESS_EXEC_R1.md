# C2 Read-only Process Exec R1 — local TEST_ONLY candidate

This candidate is derived from the verified local C1 LCMS commit. It does not
attach to GitHub or production.

The effect path is deliberately narrow:

```text
canonical LCMS ActionSpec
→ exact one-shot C2 gate
→ effect-time workspace/executable/argv currentness
→ private user+network namespace
→ no-new-privileges
→ Landlock ABI-bound filesystem allowlist
→ exact workspace + /usr + /etc read-only
→ one exact isolated /tmp subtree writable
→ seccomp network/process-creation denial
→ exact executable, shell=false
→ independent parent observation
→ exact reconciliation
```

The current global EffectSurfaceScanner labels process launches as
`authority_class=local_write`. C2 preserves that taxonomy rather than silently
rewriting it. The explicit run authorization is narrower: one bounded TEST_ONLY
local process whose command semantics are read-only.

The sandbox target probe must prove that workspace write, network socket creation
and process fork are denied, while `/tmp` remains the only ephemeral writable
filesystem location.
