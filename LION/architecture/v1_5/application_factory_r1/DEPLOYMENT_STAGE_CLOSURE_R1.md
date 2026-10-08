# Application Factory R1 — canonical Mission Control V3 package staging closure

Status: `SOURCE_CANDIDATE / NOT_DEPLOYED`. Runtime authority effect: `NONE`.

## The blocked operational edge

The existing privileged effect broker already contained a current-master
`mission_control_v3_stage_current_master(...)` producer and a transactional
`MISSION_CONTROL_V3_INSTALL` consumer. The staging producer was not reachable
through the broker's allowlisted dispatch, so even a merged and CI-clean
Application Factory source could not stage the exact 91-file package through
the canonical effect path.

This increment connects the existing operation:

```text
MISSION_CONTROL_V3_STAGE_CURRENT_MASTER
  → exact request field set
  → existing current GitHub master HEAD/TREE check
  → one shallow detached checkout of that exact master
  → existing 91-source-file SHA256 package identity
  → atomic staging directory swap + backup of prior stage
  → exact stage identity and bounded staging receipt
```

It then leaves the already-existing `MISSION_CONTROL_V3_INSTALL` unchanged:

```text
validated stage + exact current master
  → previous live package backup
  → 91 exact-file installation
  → systemd drop-in / service restart
  → health/locator/SQLite integrity readback
  → rollback on failure
```

Only the first operation is newly reachable. Its result explicitly carries
`runtime_effect=NONE`; package staging itself is a privileged bounded host
effect and requires separate host authorization. Merely merging this source
does not perform staging or installation.

## Fail-closed cases

The staging operation rejects unexpected request fields, source/current-master
drift, missing or substituted package files, and duplicate request IDs for
which a staging receipt already exists. Repeated publication of an identical
request must not create another backup/replacement.

The pre-existing atomic stage materializer is tested against an incomplete
candidate: it fails before switching the stage root and leaves the previous
valid package bytes and identity unchanged. No production service is touched
during this test.

## Test evidence

```text
new stage-dispatch/receipt/rollback tests: 7/7 PASS
existing package/deployment/host-authority tests: 30/30 PASS
isolated materialized staging: 91 exact source files
```

These tests use temporary filesystems and mock host identity; they are not
an observation of successful live privileged staging on LION-AUTH-LAB.

## Real deployment order

1. Separately approve and reconcile GitHub PR merge to current `master`.
2. Reacquire the merged source HEAD/TREE and source-of-truth package SHA map.
3. Use the existing broker-update provider for exact candidate broker
   validation, backup, update and readback under separate host admission.
4. Submit `MISSION_CONTROL_V3_STAGE_CURRENT_MASTER` once using the exact
   current master envelope; verify stage receipt and package identity.
5. Separately admit `MISSION_CONTROL_V3_INSTALL`; observe health, source
   identity, database integrity, active service and rollback receipt.
6. Regenerate the LPCL registration payload from the **deployed** HEAD/TREE,
   then separately register and activate the finite application-factory mission.
7. Execute one-worker qualification before the unchanged 32-worker production
   readiness gate; complete distinct builder/verifier artifact acceptance.

No GitHub workflow reruns, direct host copying, fleet rematerialization,
database reset, LPCL registration or mission activation is part of this
source candidate. Historical R24 and P0 evidence remains unchanged.
