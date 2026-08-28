# LION environment lifecycle and production-entry sector

This document is a deterministic rendering of the canonical world model and production-entry dossier.
It is not an authority grant and cannot make a deployment permissible.

## Environment lifecycle overview

Experimentation produces observations; observations support bounded claims; claims update assurance dimensions; the assurance vector populates the production-entry dossier. Readiness eligibility remains separate from authority.

## Current laboratory topology

- World: `e006-r9d-9g3a1-three-wsl-lab` / `MULTI_LOGICAL_NODE_LAB`
- Logical nodes: `3`
- Physical domains: `1`
- `MOON` (`host_045dbf1af63f49d4`): role `LAB_CONSUMER_OBSERVER`, runtime `WSL2`, physical domain `WINDOWS-MOON`, trust `NONE`
- `LAB-DEBIAN` (`host_2c67e8a68ffd6360`): role `LAB_BOUNDED_PRODUCER`, runtime `WSL2`, physical domain `WINDOWS-MOON`, trust `TEST_ONLY`
- `LAB-UBUNTU` (`host_df0fa36eb7d44d5b`): role `LAB_INDEPENDENT_VERIFIER`, runtime `WSL2`, physical domain `WINDOWS-MOON`, trust `NONE`

Three distinct SentinelX host IDs prove routing identity, not physical independence.

## Laboratory evidence matrix

| Dimension | State |
| --- | --- |
| PROTOCOL_CORRECTNESS | PASS |
| ROLE_SEPARATION | PASS |
| IDENTITY_SEPARATION | PASS |
| LOGICAL_TOPOLOGY | PASS |
| PHYSICAL_TOPOLOGY | FAIL |
| OBSERVABILITY | PASS |
| EVIDENCE_PROVENANCE | PASS |
| CRYPTOGRAPHIC_VERIFICATION | PASS |
| PRIVATE_KEY_CUSTODY | PASS |
| NON_EXPORTABLE_KEY_STORAGE | BLOCKED |
| FAILURE_DOMAIN_INDEPENDENCE | FAIL |
| OPERATIONAL_RESILIENCE | PASS |
| RECONCILIATION | PASS |
| ROLLBACK_READINESS | PASS |
| CURRENTNESS | PASS |
| GOVERNANCE | PASS |
| AUTHORITY | BLOCKED |
| DEPLOYMENT_READINESS | BLOCKED |

## Production-entry dossier

- Baseline candidate: `23df7e5c95dd540aa057c84ade7409304837a12c`
- Baseline tree: `94cb40f0c0cd61ec03b3b9335e88b7b75ec4d220`
- Lifecycle: `PRODUCTION_ENTRY_BLOCKED`
- Production eligible: `false`
- Authority state: `NONE`
- Blockers: `PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED`
- Missing dimensions: `none`
- Dossier digest: `b0681af09272022380e8ca24909c85bcddcdfd565e54231de7447a3bdc576e67`

## Lab-to-production transition map

`LAB_RESEARCH_TRACK` may continue while `PRODUCTION_ENTRY_TRACK` remains blocked. A laboratory PASS never promotes itself to production.

Required sequence:
1. `AUTONOMOUS_ENVIRONMENT_LIFECYCLE_AND_PRODUCTION_ENTRY_SECTOR`
2. `CURRENT_LAB_EVIDENCE_REGISTRATION_AND_DOSSIER_BASELINE`
3. `LAB_RESILIENCE_AND_AUTONOMOUS_ROLE_RESEARCH`
4. `PREPRODUCTION_EVIDENCE_COMPILATION`
5. `PHYSICAL_EXTERNAL_CONTROL_DOMAIN_ADMISSION`
6. `NON_EXPORTABLE_PRODUCTION_KEY_PROVISIONING`
7. `EXTERNAL_TRUST_ANCHOR_ROTATION`
8. `PRODUCTION_ENTRY_INDEPENDENT_CERTIFICATION`
9. `PRODUCTION_READINESS_CERTIFICATION`
10. `PRODUCTION_AUTHORITY_DECISION`
11. `PRODUCTION_DEPLOYMENT_CANARY`
12. `PRODUCTION_EFFECT_RECONCILIATION`
13. `PRODUCTION_ACTIVE_OR_ROLLBACK`

## Production blocker report

Current three-WSL evidence may support protocol, role, cryptographic, observability, resilience and reconciliation claims. It does **not** prove a second physical control domain or a non-exportable hardware production keystore.

## Production transition runbook

1. Continue rational TEST_ONLY research without erasing production blockers.
2. Re-register evidence against the exact current candidate before using it for readiness.
3. Admit a separately controlled physical host.
4. Observe TPM 2.0 / equivalent non-exportable keystore capability before materializing production key custody.
5. Independently certify production entry and production readiness.
6. Obtain separate, exact, bounded production authority.
7. Execute canary only after currentness, rollback and reconciliation gates pass.

## Production invalidation and rollback runbook

Any loss of currentness, provenance, physical observability, key custody, reconciliation, or rollback capability must regress readiness or invalidate the transition. UNKNOWN is never SUCCESS.

## Future two-physical-domain topology

The target pattern is a consumer/control plane on the existing machine plus one separately controlled physical signer with a hardware-backed non-exportable keystore. Entry eligibility still does not pin v2 or mint authority.

## Non-promotion invariants

- `LOGICAL_HOST_COUNT != PHYSICAL_DOMAIN_COUNT`
- `WSL_INSTANCE != PHYSICAL_CONTROL_DOMAIN`
- `MULTI_NODE_CONSENSUS != PHYSICAL_INDEPENDENCE`
- `LAB_VALIDATION_PASS != PRODUCTION_ADMISSION`
- `TEST_ONLY != PRODUCTION_EXTERNAL`
- `SOFTWARE_RSA_ISOLATION != NON_EXPORTABLE_HARDWARE_KEYSTORE`
- `READINESS != AUTHORITY`
- `OBSERVATION != PERMISSION`
- `UNKNOWN != SUCCESS`
