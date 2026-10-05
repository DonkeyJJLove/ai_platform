# Cooperative production R6.12 — bounded trusted worker bootstrap

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Authority effect: NONE.

R6.12 adds the source-level bootstrap that can install the R6.10 CooperativeRuntimeCompositionRoot into the R6.11 material-worker process, but only when an explicit trusted external configuration is present.

The default bootstrap mode is UNBOUND. In that mode the worker creates no cooperative runtime databases, installs no runtime root and publishes no cooperative runtime provider marker. Therefore merely deploying the R6.12 source does not make cooperative effect capabilities live.

TRUSTED_EXTERNAL_R1 requires an exact bootstrap version, an absolute repository root, an external dependency module outside that repository, an exact SHA-256 pin for that module, a bounded factory name, the canonical Mission Control SQLite path, and a pre-existing private per-worker root containing artifacts, contexts, verifiers and state directories.

The external factory may return only the exact CooperativeRuntimeBootstrapDependencies type. Those dependencies carry already-existing admission/provisioning/currentness/dispatch/runtime-identity owners plus trust bindings and a zoned clock. The bootstrap itself does not run PDP and cannot mint RuntimeAdmission or LiveAdmittedAuthority.

The built-in bootstrap constructs CooperativeRuntimeCompositionRoot from those dependencies and private paths, installs it exactly once into PROCESS_COOPERATIVE_RUNTIME, then revalidates the root before reporting READY. Invalid mode, version, module path, digest, callable, dependency type or private-storage layout fails closed before process readiness.

worker.py invokes bootstrap_process_runtime before its first status publication. The status surface now includes cooperative_runtime_bootstrap. When the bootstrap is UNBOUND, cooperative_runtime_provider remains null and Mission Control bootstrap_readiness cannot bind cooperative production/verify effects.

This is still source-only wiring. No trusted external dependency module has been deployed into the live fleet, no private per-worker root has been mounted, no Mission Control DB has been mounted read-only into the worker, no container has been restarted and no cooperative live assignment has been executed.
