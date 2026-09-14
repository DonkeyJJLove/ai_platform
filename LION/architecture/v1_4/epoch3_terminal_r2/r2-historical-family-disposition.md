# Finite historical F/C/R2e4 disposition

Baseline: committed candidate `5234e57ace18d107f8a8b48ba06766345d253f11`. Exactly 25 unique historical heads were selected from the previously unresolved F006–F009, C0–C2 and R2e4 aliases. All 25 now have explicit dispositions; none remains unclassified. All original refs and files remain preserved.

`r2-historical-family-proof.json` records each exact head, all aliases, merge base, changed path, historical blob, candidate blob, and membership in candidate history. Comparisons read Git objects using alternate object stores; no historical code or workflow was executed.

## F006 / F007 / F008 / F009: integrated source history

For all 12 selected F-family heads, **every changed nondeleted blob exists in candidate Git history**. This is stronger than a title-based assumption and does not depend on those old refs being ancestors. The three F009 heads absent from the main lab object store were read from their observed Ubuntu-24.04 checkout and satisfy the same test.

Classification: INTEGRATED source content, historical aliases preserved. No concrete unique required Epoch-3 work was found in this family. Current runtime equivalence is not asserted merely from historical blob equality; runtime acceptance remains a separate final gate.

## C0 R2–R8: superseded by canonical contract-only schema

All seven selected schema variants were structurally compared with the candidate. Constraint differences are **zero** after excluding schema identity (`$id`, title and schema_version) and explicit x-lion-c0 metadata. Candidate identity is `cyberlion://schemas/action-spec/v1`, schema_version `1.0.0`; old variants use the candidate identity.

Candidate equivalents are:

- `cyber_lion/contracts/v1/action_spec.schema.json`
- `cyber_lion/contracts/v1/action_spec_support_matrix.json`
- `cyber_lion/tests/test_action_spec_schema.py`
- `docs/architecture/action-ir/C0_ACTION_IR_SCHEMA_FREEZE.md`

Support metadata explicitly promotes only the schema contract, preserves ActionProposal runtime semantics and contradictions, and adds a schema/runtime version distinction. Old truth pins and baseline identities are historical and must not replace final computed values.

Classification: SUPERSEDED candidate freezes. No missing contract constraint requires integration. Evidence: `r2-c0-contract-comparison.json`, `r2-c0-all-version-proof.json`.

## C1 / C2: explicit separate experiments, optional Epoch-4 adoption

C1 document declares `STATUS=CANDIDATE_ONLY`, `RUNTIME_EXECUTION=NONE`, and `MERGE=FORBIDDEN_IN_THIS_PHASE`. Its additions are LCMS grammar/compiler, compiler tests and documentation, layered on the old candidate ActionSpec identity.

C2 document declares `STATUS=LOCAL_UNPUBLISHED_CANDIDATE`, `AUTHORITY=READ_ONLY/TEST_ONLY`, and `MERGE=FORBIDDEN`. Its additions are a narrowly pinned LAB-DEBIAN process adapter, observer/reconciler, tests and documentation. It binds an old workspace and executable identities. These are separate research/tooling proposals, not missing code in the Mission Control runtime or the required current mission normalization.

Classification: EXPERIMENTAL, preserve and record optional adoption in EPOCH4_HANDOFF. Rationale: adopting an alternate compiler syntax or old pinned process experiment adds a separate scope that the current terminal mission does not require. No current UI/schema/phase/worker requirement is deferred by this classification. No experiment was executed or developed here.

## R2e4 R6/R7/R10/R13: archival test evidence, not live merge authority

The four heads add a standalone terminal-evidence helper/workflow and historical test/cardinality changes. The helper calls non-consuming admission through a static test authority source; its PR number is 248, verifier accepts a fixed test signature, and synthetic grant dates are August 2026. Its own module docstring says candidate-only evidence machinery.

Candidate equivalents for the underlying behavior are `cyber_lion/enterprise/merge_admission.py` and `cyber_lion/tests/test_merge_admission.py`, including exact-match immutable evidence, missing/ambiguous source rejection, head mismatch, invalid signature, epoch change and wrong action/method cases. Current workflow runs those tests. Historical source-count pins/test wrappers must not substitute for final recomputation.

Classification: HISTORICAL test fixture/publication evidence. Importing that helper would not produce a real current merge grant and is not required to satisfy Epoch-3 protected publication.

One current limitation must be explicit in AS_IS documentation: `.github/workflows/cyber-lion-contracts.yml` emits literal `MERGE_ADMISSION_TERMINAL=OK` after unit tests. That marker means the test job reached its success step; it does **not** prove a live admission decision for the current PR. Actual publication still needs exact-head CI, current PR readback and match-head protection. Do not cite the marker as independent live authority.

## Finite-scope result

For these 25 selected heads: `UNCLASSIFIED=0`, `REQUIRED_UNIQUE_EPOCH3_WORK=0`. This finite conclusion excludes other already tracked terminal obligations, including final committed scheduler/UI/schema work, live carrier observation, full regression, production pins, documentation and protected publication. It does not declare global repository convergence or Epoch-3 closure.
