# Cooperative production R6.6 — source package currentness

Status: SOURCE_ONLY_NOT_DEPLOYMENT. Authority effect: NONE. Runtime effect: NONE.

R6.6 separates two evidence classes that were previously collapsed by the R24 whole-integration gate:

    HISTORICAL_RUNTIME_PACKAGE != CURRENT_SOURCE_PACKAGE != DEPLOYED_RUNTIME

LION/evidence/r24-whole-integration/PACKAGE_MANIFEST.json remains immutable evidence for the historical R24 runtime package. A later source change is expected to differ from that historical package. Rewriting the historical manifest to match new source would erase deployment lineage and is forbidden.

SOURCE_PACKAGE_MANIFEST_R6_6.json is the exact current source-package carrier for the cooperative Mission Control candidate. Its file hashes and package digest are verified by tools/lion_r24_whole_integration_gate.py. A mismatch in this current manifest remains a hard PACKAGE_IDENTITY_MISMATCH.

The gate retains historical runtime mismatch as explicit evidence under package.historical_runtime_mismatch, but does not reinterpret it as current source-package failure. This is not a relaxation of deployment currentness: --deployment-state-path still performs independent exact deployed HEAD/tree and panel readback, and absence of that argument remains explicitly PRE_H5_NOT_DEPLOYED.

The source package therefore proves only that the candidate source closure is internally exact. It does not prove installation, service restart, worker rematerialization, runtime authority, LPCL activation, effect execution or mission completion. Those transitions remain separate and require their existing authority/currentness/readback boundaries.
