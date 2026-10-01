# LION generated-output policy

Status: CURRENT_STANDARD. Authority effect: NONE.

Research and simulation repositories must distinguish source from reproducible output. Generated files are not automatically disposable.

## Classes

- **SOURCE_DATA** — externally supplied or manually curated input required to reproduce work.
- **GOLDEN_FIXTURE** — deliberately versioned test/reference data.
- **CANONICAL_RESULT** — selected result used as a referenced evidence artifact.
- **REPRODUCIBLE_OUTPUT** — deterministic/recomputable output that should normally be regenerated rather than duplicated.
- **PUBLICATION_ARTIFACT** — figure/table/report intentionally retained for publication or review.
- **ARCHIVED_RUN** — frozen historical execution result kept for lineage.

## Rules

1. A generated output must declare or inherit generator/input identity where feasible.
2. Repeated identical outputs should be replaced by one canonical result plus references unless history requires separate run directories.
3. Research corpus cleanup must not delete publication or provenance evidence merely because it is reproducible.
4. New generated output directories should not masquerade as source packages.
5. SymulacjaKaskadySieciowej and writeups require repository-local mappings from their existing output trees into these classes before deletion.
