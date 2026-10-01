# Panel authority boundaries

The panel is not an authority root.

## Invariants

```text
UI_CONTROL != AUTHORITY
MODEL_OUTPUT != AUTHORITY
CAPABILITY != AUTHORITY
PDP_ALLOW != RUNTIME_ADMISSION
HTTP_2XX != EFFECT_OBSERVED
RECEIPT != OBSERVATION != RECONCILIATION
SAAS_SESSION != EXECUTION_AUTHORITY
```

Local and SaaS model surfaces may propose or return cognition. Consequential effects require the existing authority/admission path.

Electron/browser isolation constrains transport and renderer capabilities; it does not create execution authority.

When authority/currentness cannot be proven, controls must fail closed or degrade to proposal/read-only behavior.
