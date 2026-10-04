# Cooperative production R3: real two-container model/data qualification

Result: PASS_REAL_CONTAINERS_LOCAL_MODEL_DATA_ARTIFACT. This is an operator-scoped qualification, NOT a completed LPCL mission or deployment.

On 2026-10-04 at 22:04 UTC, existing MOON Docker Desktop containers in Compose project `lion-r24-autonomy` were used without recreation or restart. MD001 (container `4d7d3e07e7bb7358459a1fdbfa136c7ffb61d677b1c707bf0d5acb353c61c374`) called the existing local gpt-oss-20b-MXFP4 model through `host.docker.internal:8772`. It produced the exact 1400 UTF-8 bytes committed as `cyber_lion/tests/fixtures/cooperative_readiness_r3.json`, SHA256 `1864a7bada4efcda446f393a4b1afb5ef579888e4d56a5025c45a769b1784ebc`.

MD002 (container `353c9520504c10ccd537a554b9cac610528481824eff6a9777ba91c5bd07c24b`) received those bytes in a separate temporary workspace, checked the checksum and all eight fixed semantic boundary cases, and rejected a deliberately incorrect expected result. MD002 also made a separate local-model review call. The models share the same provider and host; review agreement is not independent evidence. The deterministic verifier was fixed before generation.

Builder request SHA256: `74fcfa792ded2de0e49d66cf55133e8a6b1bd27554d16e319aeb1372cd365675`. Reviewer request SHA256: `fc9d61939794d95d88b1cbf01c4f81b0c663b92a478a37d3aa4d4dcc67958a1d`. Shared task-context SHA256: `76c214c3e44043031aa786719129184bf4fd0a088cc2178fb9e8d6fdd6624d5e`. These identify sent application payloads, not hidden provider transformations.

Both existing containers ran the same 36 source-component tests successfully. A later scoped suite on MOON ran 133 tests successfully, including original runtime/sandbox tests and new synthetic-admission writer tests. Those broader source changes remain in the isolated local candidate; this publication includes ONLY the readiness predicate, its tests and the actual generated corpus. The tests published with the corpus do not claim to reproduce the earlier live model call.

The predicate handles fresh, exact-threshold, stale and future observations, stopped worker, degraded transport, unavailable Mission Control and unavailable model. READY means recent reported reachability, not execution authorization or proof of a completed workload.

Protected state: no live Mission Control assignment was created, no pending turn was drained, no LPCL successor was activated, and no runtime source files were replaced. The R1 pilot remains AUTHORIZED / NOT_STARTED with `lpcl execution adapter cardinality`; it is not completed by this qualification.

The local candidate contains a concrete CanonicalCooperativeWriter plus CooperativeArtifactBackend composed with the original RuntimeExecutionEngine and ExecutorSandbox, and tested fail-closed assignment/storage fixes. Live binding, durable admission ownership, provider installation, model-to-artifact lineage hardening and the full panel return path still require closure. The generic read-only executor must not be used to bypass that boundary. PR407 and the existing cooperative source line remain preserved.

Published subset test command:

```sh
python3 -B -m unittest cyber_lion.tests.test_cooperative_readiness cyber_lion.tests.test_generated_readiness_corpus -v
```
