# Failure-domain evidence candidate

Host routing identities and logical drone counts are not physical independence. This generation introduces a bounded observation contract around `host_id`, `boot_id`, virtualization class, evidence digest and observation time. Equal current boot IDs across multiple hosts falsify independence at the kernel/boot-domain layer. Distinct boot IDs merely fail to falsify that layer; they never prove physical or material-executor independence.

The current four-host WSL observation therefore remains `physical_independence=NOT_PROVEN` and `material_executor_independence=NOT_PROVEN`. The contract has no authority or runtime effect.
