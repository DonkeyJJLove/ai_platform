# Panel architecture

## Source topology

The source shell is `browser_broker/src/main.cjs`. It creates one Electron `BaseWindow` with isolated `WebContentsView` surfaces for Mission Control, LPCL Panel, ChatGPT SaaS and a local tab strip.

Source-level default endpoints are loopback services:

- Mission Control: `127.0.0.1:8766`.
- LPCL/local panel: `127.0.0.1:8780`.
- local ingress/readback: `127.0.0.1:8791`.
- browser-broker control endpoint: `127.0.0.1:8793`.

These values describe source defaults, not proof that a service is currently running.

## Logical layers

```text
OPERATOR SHELL
  browser_broker
      ↓
MISSION CONTROL OBSERVATION
  cyber_lion/mission_control
      ↓
LOCAL PANEL / APP COORDINATION
  cyber_lion/app_coordination
      ↓
PROCESS / LPCL CONTRACTS
  cyber_lion/process_language + mission-control contracts
      ↓
AUTHORITY / RUNTIME ADMISSION
  cyber_lion/enterprise
      ↓
EFFECT / RECEIPT / OBSERVATION / RECONCILIATION
```

`cyber_lion/vkt_r3/mission_control`, `LION/runtime_compat/*` and older mission-control tools are separate lineage/compatibility surfaces until classified by the global reconciliation census.

## Browser security boundary

Remote SaaS content receives no Node.js authority. The Electron main process constrains navigation, denies new windows, downloads and permission requests, and keeps local service credentials outside renderers. Those controls are source properties; live deployment must be independently observed.
