# Workflow Homeostasis — R5

The homeostasis auditor is now schema v2 and classifies workflows by semantic effect family: CRITICAL_EVIDENCE=5, READ_ONLY_CI=4, OBSERVATION=2, LIVE_PROOF=1, SELF_HOSTED_RUNTIME=9, EXTERNAL_WRITE=3. Critical blocking defects are zero.

This run hardened F005 read-only CI, fleet effect-budget evidence, Code Perception observation, group-channel evidence, Core queueing, and F009 live proof. Exact HEAD/TREE binding, credential persistence, bounded execution, non-cancelling concurrency and evidence hash binding were added only where semantics justified them. The remaining 23 control findings occur exclusively on ten SELF_HOSTED_RUNTIME/EXTERNAL_WRITE workflows. They are deliberately not blanket-mutated; each requires effect/idempotency/authority review in the next epoch.

Audit digest: `9887c2e58d655558c77dde516e53c6c0d1fffd21354b114d97990385346ef01c`. Remote exact-head CI for this local lineage remains NOT_PUBLISHED.
