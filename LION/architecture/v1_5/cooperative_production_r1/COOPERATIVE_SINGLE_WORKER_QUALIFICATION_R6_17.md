# Cooperative production R6.17 — single-worker private qualification

Status: TESTED_SOURCE_CANDIDATE_NOT_DEPLOYED. Authority effect: NONE. Live effect: NONE.

R6.17 closes the source-side boundary immediately after R6.16 without activating the cooperative fleet. It adds a bounded qualification path for exactly one already-existing material worker and exactly one cooperative WRITE assignment that has already passed the canonical HELD→READY fence.

The execution resolver is not weakened. PinnedCooperativeContextResolver.__call__ still requires the canonical assignment state CLAIMED. R6.17 adds a separate resolve_for_qualification read path that requires READY; it cannot be used by the writer effect path. The qualification path therefore proves provider reconstruction before claim rather than manufacturing an executable claim.

Qualification accepts READY only when the canonical lion.assignment-release-evidence/v1 row exists and matches the assignment, mission, worker, generation, control/context/plan revisions, capability, materialization kind and provider. state=READY by itself is insufficient.

The worker-side composition root re-opens the R6.16 provider projection through the existing read-only SQLite evidence sources and pinned context carrier. It revalidates admission, dispatch, runtime identity, provisioning, authority, policy currentness, observability and transfer binding. It then copies the already-issued RuntimeAdmission into the worker-private durable state and materializes the context into that worker's private context root.

The result is lion.cooperative-worker-qualification/v1. It records the canonical release digest, R6.16 control-plane evidence digest, private context pin, private transfer digest, private materialization descriptor, RuntimeAdmission digest and exact provider marker. writer_factory_built=true means the existing writer provider could be reconstructed; it does not mean the writer was called.

The bounded entrypoint tools/lion_cooperative_worker_qualification.py is intentionally pre-activation only. It requires LION_COOPERATIVE_BOOTSTRAP_MODE=UNBOUND, an exact bootstrap version and a --worker-id equal to LION_MATERIAL_WORKER_ID. It does not install a root into PROCESS_COOPERATIVE_RUNTIME, claim an assignment, advance Mission Control or call the runtime writer.

Negative acceptance is fail-closed. Qualification rejects a manually forced READY assignment without release evidence, wrong worker identity, replaced provider SQLite database, tampered context-carrier bytes, stale RuntimeAdmission evidence and a repeated qualification. Replay is rejected before creating a second worker-private workspace.

Source validation on MOON at the R6.16 parent plus the R6.17 working delta: all test_*cooperative*.py suites pass, 223/223. The focused R6.17 qualification suite passes 7/7. py_compile and git diff --check pass.

This remains source-only. No container was restarted or rematerialized, no live provider state was imported into the running fleet, no worker bootstrap mode was changed from UNBOUND, no assignment was claimed and no cooperative material artifact effect was executed. Live single-worker qualification requires a later, separately admitted operator action against exact deployed R6.17 source and current provider evidence.
