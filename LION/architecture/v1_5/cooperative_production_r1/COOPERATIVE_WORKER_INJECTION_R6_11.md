# Cooperative production R6.11 — material-worker injection seam

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Authority effect: NONE.

R6.11 places the cooperative runtime path into the canonical R24 material-worker source without installing any live runtime root and without changing the fleet topology.

The worker source now contains a CooperativeWorkerRuntime wrapper and exactly-once process registry. The wrapper accepts only the exact CooperativeRuntimeCompositionRoot from R6.10. It routes COOPERATIVE_ARTIFACT_WRITE to the root's admitted writer and canonical artifact root, and COOPERATIVE_ARTIFACT_VERIFY to the distinct private verifier workspace. No root means no cooperative assignment is claimed.

The material-worker source identity now declares COOPERATIVE_ARTIFACT_WRITE and COOPERATIVE_ARTIFACT_VERIFY as source-level direct assignment kinds, plus the corresponding materialization/independent-verification architecture capabilities. These declarations mean only that the canonical worker binary understands the assignment classes. Live readiness still requires the exact cooperative_runtime_provider marker emitted from an installed and revalidated runtime root.

worker.py consults PROCESS_COOPERATIVE_RUNTIME before the generic local-model branch. If the process registry is unbound, the cooperative branch is skipped and the status field cooperative_runtime_provider is null. Therefore a source deployment without trusted root installation cannot satisfy Mission Control bootstrap_readiness and cannot bind effectful cooperative capabilities.

This increment does not mount private runtime state, instantiate CooperativeRuntimeCompositionRoot, deploy a worker image, restart containers, install a process root, publish READY provider markers or execute a cooperative live assignment. The next boundary is a bounded worker bootstrap that constructs and installs the R6.10 root from existing trusted admission/provisioning/currentness owners and private persistent storage.
