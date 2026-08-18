# CYBER-LION — Architecture Analysis Root

Status: **ANALYTICAL BASELINE / pre-implementation**  
Branch: `cyber-lion/00-architecture-analysis`

Cyber-Lion is defined here as a **federated system-of-systems**, not a monolith and not a rewrite of the existing repositories. The architecture is organized by capabilities, state transitions, information flow and authority rather than repository names.

## Governing invariants

```text
OPEN INTELLIGENCE != OPEN AUTHORITY

NO ACTION WITHOUT IDENTITY
NO AUTHORITY WITHOUT PROVENANCE
NO ESCALATION WITHOUT APPLIED GATE
NO MEMORY WRITE WITHOUT POLICY
NO DECISION WITHOUT TRACE
NO CROSS-SYSTEM CALL WITHOUT CONTRACT
NO GLOBAL CLAIM FROM LOCAL OBSERVATION
NO LOST OBSERVABILITY WITHOUT AUTHORITY DEGRADATION
NO PROBABILISTIC OUTPUT DIRECTLY AS EXECUTION
NO FORMALISED RULE LEFT AS REPEATED LLM GUESS
```

## Analytical outputs

1. [`REPOSITORY_INVENTORY.md`](REPOSITORY_INVENTORY.md) — actual roles, assets, maturity and debt.
2. [`CAPABILITY_MAP.md`](CAPABILITY_MAP.md) — capabilities independent of repository boundaries.
3. [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md) — target federated architecture and ownership.
4. [`CONTRACT_MAP.md`](CONTRACT_MAP.md) — contracts required before cross-repository integration.
5. [`EVENT_DATA_MODEL.md`](EVENT_DATA_MODEL.md) — shared identity/event/gate/execution model.
6. [`MIGRATION_MAP.md`](MIGRATION_MAP.md) — ordered CURRENT → COMPATIBILITY → MIGRATION → TARGET plan.
7. [`SCIENTIFIC_STATUS.md`](SCIENTIFIC_STATUS.md) — epistemic status of constructs and evidence.

## Architecture rule

A Git repository is an organizational boundary, **not automatically a subsystem boundary**. A repository may provide several capabilities; one capability may depend on several repositories.

## Current high-level reconstruction

```text
                         CYBER-LION
                              |
                     ai_platform contracts
                     registry / control plane
                              |
        +---------------------+---------------------+
        |                     |                     |
   COGNITION / SEM       AUTHORITY / MAND      EXECUTION / INF
        |                     |                     |
 chunk-chunk               sbom/AID               swarm
 HA2D                      local gates             tool workers
 hipotezy                  policy contracts        sandbox boundary
        |                     |                     |
        +----------+----------+----------+----------+
                   |                     |
             STRUCTURE / DELTA      SIMULATION / RISK
                   |                     |
          glitchlab + mosaic      SymulacjaKaskadySieciowej
                   |
              EVIDENCE CORPUS
                   |
                writeups
```

This diagram is a migration hypothesis. `REPOSITORY_INVENTORY.md` and `CAPABILITY_MAP.md` identify which parts already exist as executable mechanisms and which remain specifications or research constructs.

## Mandatory migration discipline

```text
archaeology
→ architecture specification
→ identity contract
→ event contract
→ capability registry
→ adapters
→ local enforcement integration
→ observability/replay
→ adversarial validation
→ deprecate legacy only after compatibility proof
```

No later Cyber-Lion PR should bypass this dependency order without documenting why.