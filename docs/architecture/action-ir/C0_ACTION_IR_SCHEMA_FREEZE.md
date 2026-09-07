# C0 Action IR Schema Freeze

```text
ROADMAP_STEP=C0-ACTION-IR
STATUS=CONTRACT_ONLY
BASELINE_SHA=db51d0eb8784cb3b9a45a180aa421b35bc86d9c3
BASELINE_TREE=3a9d5821fcf02839923247e56ceb5b0369e7fd1b
AUTHORITY_EFFECT=NONE
RUNTIME_EXECUTION=NONE
TRANSPORT_IMPLEMENTATION=NONE
SUPERSEDES=NONE
```

C0 integrates `ActionSpec` as the canonical digest-bindable schema contract beneath the existing live
`ActionProposal` runtime envelope. It does not add an executor, transport provider, shell, authority
issuer, or effect provider. `ActionProposal.payload_digest` is the only AS_IS binding used by
this step.

## AS_IS

The live contract remains `cyber_lion/contracts/v1/action_proposal.schema.json`. Its authority
vocabulary is `none`, `read`, `local_write`, `external_write`, `financial`, `deploy`,
`privileged`; its `target` remains a nonempty string. Those facts are not rewritten by C0.

## TARGET_ONLY

The structured ActionSpec fields `kind`, structured `target`, `authority_request`, `boundary`,
preconditions, expected/forbidden effects, observation, reconciliation, and process-shaped
fields remain contract-only. Their presence in the canonical schema is not evidence of runtime
support.

## Preserved contradictions

`C0-FINANCIAL-AUTHORITY-VOCABULARY`: live `ActionProposal.requested_authority` contains
`financial`, while candidate `authority_request` has `domain/capability/grant_ref` and no
canonical financial mapping. Resolution: `NO_SILENT_MAPPING`.

`C0-V1_2-ACTIONSPEC-ABSENT`: the frozen baseline contains ActionProposal and execution/PEP/
receipt contracts but no canonical ActionSpec/Action IR schema. C0 therefore integrates a new canonical schema contract without claiming runtime supersession of `ActionProposal`.

`C0-TARGET-SHAPE`: live ActionProposal target is a string while candidate ActionSpec target is
structured. Resolution: `NO_IMPLICIT_RUNTIME_COERCION`.

The machine-readable support matrix is
`cyber_lion/contracts/v1/action_spec_support_matrix.json`.
