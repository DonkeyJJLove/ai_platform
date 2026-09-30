# Federated architecture knowledge migration plan

1. Preserve v1.4 current-state and semantic-owner artifacts as historical compatibility surfaces.
2. Integrate local `AGENTS.md` plus `architecture_knowledge` manifests in peer repositories first.
3. Reacquire exact peer HEAD/TREE after merge.
4. Integrate v1.5 semantic owners, federation registry, generators, flow projection and formalized admission in `ai_platform`.
5. Materialize RAG v1.5 source set and retrieval probes.
6. Close AFM/RFS/FederatedFormalizationBinding/FCR against an exact candidate.
7. Commit ordinary source/documentation first.
8. Regenerate federation vector after peer integration and source stabilization.
9. Regenerate truth carriers last.
10. Merge only exact-head green CI and then reacquire the federation again.

No runtime deployment is part of this migration.
