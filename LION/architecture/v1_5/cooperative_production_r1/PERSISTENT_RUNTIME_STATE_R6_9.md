# Cooperative production R6.9 — durable runtime state primitives

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Authority effect: NONE.

R6.9 removes the remaining F009-proof-only persistence dependency from the cooperative runtime composition without creating an authority source or a second scheduler/PDP.

The existing cyber_lion.enterprise.runtime_execution owner now provides a durable immutable SQLiteRuntimeAdmissionSource and an exactly-once SQLiteAdmissionConsumptionGuard. The admission source accepts only an already sealed RuntimeAdmission; it cannot construct PDP evidence, live authority or an admission. Publication carries an independent provenance digest and is append-only/replay-denied.

The existing cyber_lion.enterprise.executor_sandbox owner now provides SQLiteSandboxReplayGuard and SQLiteSandboxBudgetLedger. Replay is durable on (mission_id, operation_id). Budget state is monotonic and keyed by the exact ExecutionSandboxPolicy digest; exhaustion does not roll state forward and reconstructing a provider does not reset the budget.

CooperativeRuntimeWriterProvider accepts only the existing in-memory budget owner or the new exact durable budget owner. Its runtime execution path is otherwise unchanged. The cooperative composition tests now use the generic durable admission-consumption owner instead of importing the F009 proof helper.

This increment still does not issue live runtime admission, provision a Docker worker, publish a live worker provider marker, mount private worker storage, deploy Mission Control, restart the fleet or launch a successor LPCL. The next boundary is a trusted composition root that supplies already-issued admission/provisioning/currentness evidence and installs the R6.8 materializers.
