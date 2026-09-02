# C0 Action IR Schema Freeze

```text
ROADMAP_STEP=C0-ACTION-IR
STATUS=CANDIDATE_SCHEMA_FREEZE
BASELINE_SHA=22ae615c3ec6eedf2a500d0d70d8ecc97ba1cabd
BASELINE_TREE=ac8474a13d46e568787b2fc5bd77955e8b0febda
AUTHORITY_EFFECT=NONE
RUNTIME_EXECUTION=NONE
TRANSPORT_IMPLEMENTATION=NONE
SUPERSEDES=NONE_UNTIL_INTEGRATED
```

C0 freezes an `ActionSpec` candidate as a digest-bindable payload for the existing live
`ActionProposal` contract. It does not add an executor, transport provider, shell, authority
issuer, or effect provider. `ActionProposal.payload_digest` is the only AS_IS binding used by
this step.

## AS_IS

The live contract remains `cyber_lion/contracts/v1/action_proposal.schema.json`. Its authority
vocabulary is `none`, `read`, `local_write`, `external_write`, `financial`, `deploy`,
`privileged`; its `target` remains a nonempty string. Those facts are not rewritten by C0.

## TARGET_ONLY

The structured ActionSpec fields `kind`, structured `target`, `authority_request`, `boundary`,
preconditions, expected/forbidden effects, observation, reconciliation, and process-shaped
fields are schema-only. Their presence in the candidate schema is not evidence of runtime
support.

## Preserved contradictions

`C0-FINANCIAL-AUTHORITY-VOCABULARY`: live `ActionProposal.requested_authority` contains
`financial`, while candidate `authority_request` has `domain/capability/grant_ref` and no
canonical financial mapping. Resolution: `NO_SILENT_MAPPING`.

`C0-V1_2-ACTIONSPEC-ABSENT`: the frozen baseline contains ActionProposal and execution/PEP/
receipt contracts but no canonical ActionSpec/Action IR schema. C0 therefore introduces a new
candidate; it does not claim silent v1.2 supersession.

`C0-TARGET-SHAPE`: live ActionProposal target is a string while candidate ActionSpec target is
structured. Resolution: `NO_IMPLICIT_RUNTIME_COERCION`.

The machine-readable support matrix is
`cyber_lion/contracts/v1/action_spec_support_matrix.json`.
