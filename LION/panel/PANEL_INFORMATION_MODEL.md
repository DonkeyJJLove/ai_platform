# Panel information model

Every operator-visible state must identify its evidence plane.

```text
UI CONTROL
→ INTENT
→ API
→ CONTRACT
→ AUTHORITY
→ RUNTIME ADMISSION
→ EFFECT
→ RECEIPT
→ OBSERVATION
→ RECONCILIATION
→ UI STATE
```

The arrows are gates, not guarantees.

## Required provenance per visible state

A panel field SHOULD expose or be traceable to:

- semantic owner;
- source endpoint or projection;
- observation timestamp/currentness;
- identity (mission/conversation/phase/assignment where applicable);
- authority state when the control can request a consequential action;
- reconciliation state for reported effects.

## Separate information planes

- **Mission state**: Mission Control projection/database.
- **Process/phase state**: process-contract and phase execution projections.
- **Conversation state**: canonical conversation store.
- **Model-call state**: model-call plane; model output does not imply authority.
- **SaaS transport state**: browser/bridge durable transport state.
- **Authority state**: explicit authority source/grant/admission path.
- **Effect state**: effect provider and independent observation/reconciliation.
- **UI diagnostic state**: renderer/main-process diagnostics; never effect proof.
