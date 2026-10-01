# LION panel / operator shell

Status: CURRENT_SOURCE_DERIVED. Deployment state: UNKNOWN until live runtime readback. Authority effect of this documentation: NONE.

The current source topology is owned by the Electron shell in `browser_broker/src/main.cjs`:

```text
Electron BaseWindow
├── LEFT: Mission Control
└── RIGHT:
    ├── LPCL Panel
    └── ChatGPT SaaS
```

Additional canonical UI surfaces include Canonical Model Chat and a separate Protocol plane. The panel is an observation/control product surface; it is not itself a source of authority.

Read:

1. `PANEL_ARCHITECTURE.md`
2. `PANEL_INFORMATION_MODEL.md`
3. `PANEL_STATE_MODEL.json`
4. `PANEL_CONTROL_CONTRACTS.md`
5. `PANEL_USER_FLOWS.md`
6. `PANEL_AUTHORITY_BOUNDARIES.md`
7. `PANEL_OBSERVABILITY.md`
8. `PANEL_COMPONENT_CATALOG.json`
