# Panel control contracts

## Read-only surfaces

Observation endpoints may display source/projected state without granting authority. Read access is not action admission.

## Consequential controls

Any control that can lead to mutation must preserve:

```text
operator intent
→ exact contract/input identity
→ authority lookup/decision
→ runtime admission
→ bounded effect
→ receipt
→ independent observation
→ reconciliation
```

A button click is not authority. A successful HTTP response is not effect proof. A receipt is not independent observation.

## Canonical source families

- Mission Control APIs: `cyber_lion/mission_control/server.py`.
- Operator controls: `cyber_lion/mission_control/operator_control.py` and governed enterprise paths.
- Canonical Model Chat/UI: `cyber_lion/app_coordination/r24_model_chat_ui.py` and conversation modules.
- Browser/SaaS mediation: `browser_broker/src/*.cjs`.
- LPCL semantics: `cyber_lion/process_language/*`.

Compatibility/legacy sources must not silently become new authority owners.
