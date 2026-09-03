# C1 LCMS Canonicalization

```text
ROADMAP_STEP=C1-LCMS
STATUS=CANDIDATE_ONLY
PARENT_PR=256
PARENT_HEAD=f8d8e44191d5c84ecca9feec1a8602f574948619
PARENT_TREE=b303b628e18dd1b31bb19c923cd0f18e2f050ae9
GRAMMAR_VERSION=lion.lcms/v1.0-candidate
TARGET_ACTIONSPEC=lion.action-spec/v1.3-candidate
AUTHORITY_EFFECT=NONE
RUNTIME_EXECUTION=NONE
TRANSPORT_IMPLEMENTATION=NONE
EXTERNAL_EFFECT=NONE
ATTACH=FORBIDDEN
MERGE=FORBIDDEN_IN_THIS_PHASE
```

C1 introduces only a versioned human/model-readable surface syntax and a deterministic,
non-effectful compiler into the frozen C0 `ActionSpec` candidate. LCMS is not a shell,
executor, transport, `EffectPermit`, or `ActionProposal`. Compilation ends after canonical
ActionSpec bytes and their SHA-256 digest are produced.

## Semantic law

The C1 chain is:

```text
LCMS source
  -> strict parser
  -> deterministic normalized ActionSpec object
  -> sorted canonical JSON bytes
  -> SHA-256 digest
```

No execution follows this chain. No provider is selected or loaded. No credential is read.
No network or filesystem effect is performed by the compiler. No authority is minted,
attenuated, consumed, inferred, or transformed.

The source header is `LCMS/1.0`; the grammar identity is
`lion.lcms/v1.0-candidate`. Assignment names are exact. Aliases are not accepted.
Values use RFC 8259 JSON native types so booleans and integers cannot be silently coerced.
Every base ActionSpec field is explicit: omission is not a request for an effect-bearing
default.

C1 source is intentionally ASCII-only, NFC, and LF-only. This is a fail-closed restriction
against Unicode confusables in the command-modeling surface; it is not a claim that the C0
ActionSpec schema itself forbids Unicode.

## Canonicalization

Field order and insignificant JSON whitespace are accepted as semantically irrelevant.
Duplicate LCMS fields and duplicate JSON-object keys are rejected. Accepted equivalent
sources must therefore produce byte-identical ActionSpec serialization.

Canonical bytes are UTF-8-compatible ASCII JSON with:

- recursively sorted object keys through `json.dumps(sort_keys=True)`;
- separators exactly `,` and `:`;
- `ensure_ascii=True`;
- NaN and Infinity forbidden;
- exactly one terminal LF.

The digest is `sha256:<64 lowercase hex>` over those exact bytes.

## Fail-closed surface

C1 exposes stable rejection classes for:

`UNKNOWN_FIELD`, `DUPLICATE_FIELD`, `UNKNOWN_ENUM`, `UNKNOWN_ACTION_KIND`,
`ALIAS_NOT_CANONICAL`, `NONCANONICAL_UNICODE`, `AMBIGUOUS_UNIT`,
`AMBIGUOUS_BOOLEAN`, `PATH_TRAVERSAL`, `RELATIVE_EXECUTABLE_PATH`,
`IMPLICIT_DEFAULT_WITH_EFFECT`, `RAW_SHELL_STRING`, `SHELL_TRUE`,
`ENVIRONMENT_INHERITANCE`, `UNBOUND_WORKSPACE`, `MALFORMED_DIGEST`,
`DUPLICATE_SET_MEMBER`, `UNKNOWN_PIPELINE_EDGE`, `CYCLIC_PIPELINE`, and
`UNDECLARED_PIPELINE_NODE`.

These classifications are diagnostics only. They grant no authority.

## Process-shaped ActionSpec

`process.exec` remains schema-only in C1. The compiler requires its complete execution-shaped
data because C1 refuses implicit defaults: pinned executable path and digest, exact workspace
repository/commit/tree/path, explicit arguments, `environment.inherit=false`, explicit
environment allow-map, and exact IO policy.

Compiling a valid `process.exec` ActionSpec does **not** prove that an executor exists.
It does not create one and it does not make the ActionSpec executable.

## Pipelines deferred

C1 deliberately defines no executable pipeline syntax. Raw shell pipelines such as
`command1 | command2` are unrepresentable. Reserved `pipeline.*` forms fail closed with
explicit pipeline rejection classes. A later step may introduce typed nodes and a dependency
DAG only after deterministic DAG semantics and authority non-transfer are separately proven.

## Preserved C0 contradictions

C1 does not resolve any C0 contradiction.

`C0-FINANCIAL-AUTHORITY-VOCABULARY` remains `PRESERVED /
NO_SILENT_MAPPING`. C1 contains no mapping from live
`ActionProposal.requested_authority=financial` to candidate
`ActionSpec.authority_request`.

`C0-V1_2-ACTIONSPEC-ABSENT` remains `PRESERVED /
NEW_CANDIDATE_NOT_SUPERSESSION`. LCMS compiles only to the C0 candidate; it does not
rewrite history or claim a canonical v1.2 ActionSpec.

`C0-TARGET-SHAPE` remains `PRESERVED /
NO_IMPLICIT_RUNTIME_COERCION`. C1 outputs the structured candidate ActionSpec target and
does not map it into the live string-valued ActionProposal target.

## Evidence boundary

The C1 test corpus validates compiled results against the exact parent C0
`cyber_lion/contracts/v1/action_spec.schema.json`, exercises deterministic canonical bytes,
and falsifies the required negative cases. Green tests are evidence about this candidate only;
they are never merge authority.

```text
C0_INTEGRATED=NO
C1_INTEGRATED=NO
MERGE_AUTHORIZATION_INFERRED=NO
```

## Candidate tool-plane placement

The compiler implementation is intentionally materialized as `tools/lcms.py`, alongside the repository's existing deterministic tooling, rather than under `cyber_lion/enterprise/`. This placement is part of the C1 non-promotion boundary: LCMS is a candidate contract compiler and is not a production runtime source, executor, transport, provider, or authority component. The exact production effect inventory therefore remains unchanged by C1.
