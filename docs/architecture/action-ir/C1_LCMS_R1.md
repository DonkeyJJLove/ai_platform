# C1-LCMS R1 — detached local candidate

```text
ROADMAP_STEP=C1-LCMS
BASELINE_KIND=C0 verified
C0_HEAD=d31a6385793909909b62d2d6bf7825713dbe3dab
C0_TREE=e1977c7f1375cfc458c06afa91d469c612a7bc0d
C0_ACTION_SPEC_SCHEMA_SHA256=2da1a37043a19b96e99a5e2270c09dd0d4f3a996906740ec3e72322f2823a7a6
STATUS=LOCAL_DETACHED_CANDIDATE
EXTERNAL_REPOSITORY_EFFECT=NO
RUNTIME_EXECUTION_SUPPORT=NO
TRANSPORT_IMPLEMENTATION=NO
AUTHORITY_MINTING=NO
```

C1 R1 materializes an auditable LCMS `ACTION` surface, parser, normalizer,
canonical Action IR serializer, digest, and canonical LCMS renderer. LCMS is
never executed directly. Compilation produces only a C0 `ActionSpec`-shaped
candidate.

`PLAN`, `NODE`, and `EDGE` remain reserved and fail closed in R1 because the
frozen C0 contract contains no typed CommandPlan IR. This avoids silently
inventing runtime or pipeline semantics.

Canonicalization is semantic, not textual. Object/map order is irrelevant.
The following set-like C0 arrays normalize lexicographically: preconditions,
expected effects, forbidden effects, filesystem read/write scopes, process
children, and required observation events. `arguments` remains order-sensitive.

The parser rejects unknown and duplicate fields, duplicate map keys, aliases,
noncanonical whitespace, non-ASCII/non-NFC values, trailing commas, path
traversal/non-normalized paths, unknown enums, incomplete `process.exec`, and
any attempt to represent `action_id` both in the header and body.

This candidate does not prove support for `process.exec`, network transport,
repository effects, host effects, or any C0 `TARGET_ONLY` field at runtime.
Those remain separate later roadmap steps.
