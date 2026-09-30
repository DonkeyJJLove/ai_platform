# Federated architecture knowledge rollback plan

- Never reset or delete a user dirty worktree.
- Peer rollback: revert only task-created peer commits/PRs; preserve pre-existing repository evidence.
- `ai_platform` rollback before merge: drop/revert only candidate commits. After merge use an explicit revert candidate; never force-push master.
- Machine projections and their source bindings roll back together.
- Do not manually restore old `CURRENT` labels; recompute currentness from the reverted exact source/federation.
- RAG rollback selects the previous verified versioned release; historical RAG never becomes live truth.
- Truth carriers are recomputed after rollback and remain the last currentness write.
