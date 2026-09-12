# Mission Control Source Rebind — R5 offline candidate

Observed runtime source remains `743cb77bdcc798dcb2d57e7dd389bd763ba81f41` / `5afea703fd887f2609245a48000dbc47b8cd1b0f`; service is active, K3s inactive. Fresh remote master target is `938aa94460a2e0f81c470c1586626290bb74bc2c` / `70d698f937608495c3845b9b7c1f0bc515a3789d`.

The effect-free rebind package binds release fileset digest `3a6fc6527cfc250c3630fa54b23d5b59a7d6f2d24659e2399e4196039a742451`, live configuration digest `d1f1ceb976533b132de34ce1233a9816aedfbf15758b35787804412fdbaef286`, adapter set `197b873aae5db750898014c1116e1cee24f8d9576cb24d224098c151fd9d22d6`, and DB-schema source `49967cc52ded060281bb2a99a7be85ae9fbde8e441dafde4c12d0d7fe83903a7`. Plan digest is `d5e5e60a75aad3c7a45b776739d25ccfc694011b80e541154b0e78312713f15a`; package digest `6041ac732002b44468bdd5ca8c56e28843fa3fcb4f7ac4994fb6dc1ec40f0fa6`.

State is SOURCE_CHANGE_REQUIRED / OFFLINE_CANDIDATE_NOT_ACTIVATED. No restart, deployment, K3s change or production effect occurred. Any future authorized application requires post-effect PID/release/source/API/VKT readback and reconciliation.
