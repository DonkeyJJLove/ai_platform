# LION version semantics

LION uses several independent version axes. They must not be compared as if they were one sequence.

- **architecture_epoch** — architecture knowledge generation, e.g. `1.5`.
- **product_release** — packaged/distributed product release, if one exists.
- **contract_version** — semantic API/contract compatibility.
- **schema_version** — serialized representation compatibility.
- **formalization_revision** — AFM/RFS/FCR revision of a bounded change.
- **experiment_revision** — Rxx, Exx, Txx and similar experimental lineages.
- **runtime_generation** — deployed/runtime generation or restart lineage.
- **documentation_revision** — source-bound documentation materialization revision.

Rules:

1. `v1_5` does not imply `R24`, and `R24` does not imply architecture epoch 1.5.
2. A historical experiment identifier is not a current product version.
3. Contract/schema compatibility must be explicit and cannot be inferred from directory names.
4. Current documentation must state the axis it is describing.
