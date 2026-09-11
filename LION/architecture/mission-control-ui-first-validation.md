# Mission Control UI-first validation

Baseline: master `e3714e2d6d9f32762ae51f668787e478c07a3397`.

The existing generic UI was audited before any changes. It exposed fleet counts
as primary cards, omitted the process-class filter and rendered participant and
evidence detail mostly as raw JSON. The deployed localhost:8766 UI was older than
master; its three historical runs were captured through the existing read API.

This stage changes only presentation and its regression tests. The primary cards
are active/completed/failed/deferred runs, hosts, workloads, events and artifacts.
The registry retains historical runs and adds process-class filtering. Run status,
verification, cleanup, receipt presence, observed effects and reconciliation are
separate. Missing material identity is labeled logical only. VKT metrics and the
existing fleet/channel components are scoped to VKT adapter detail. Historical
metrics fall back to the recorded run when the separate metrics table is empty.

Validation completed before any new cluster implementation:

- Existing required server/security/migration/legacy tests: 23 passed on Linux.
- All Mission Control tests: 29 passed on Linux; Node behavior test skipped there
  because Node is absent. Both new Python UI tests, including Node behavior,
  passed on Windows. JavaScript syntax check passed.
- Browser readback of actual generic HTTP server with captured real API evidence:
  desktop home with zero active runs; run selection; VKT and OSS detail; retained
  cleanup history; artifacts and receipts; empty combined filters; mobile 390 px.
  No page-wide horizontal overflow; tables use their own horizontal scroll.
  Browser error log empty. Before/after screenshots captured outside the repo.
- Isolated unit fixtures test missing vs zero, logical-only participants, escaped
  artifact fields, receipt/postcondition separation, filter behavior, out-of-order
  selection responses and failed detail fetch. Fixtures are not product data.

The local visual server is explicitly marked CAPTURED_API_READBACK and UNKNOWN
runtime currentness. Screenshots prove presentation only. They do not prove host
deployment, live provider freshness, cluster readiness or workload state.
No backend, provider, permission, deployment or test workload was changed during
this UI stage. No new cluster code was implemented before these checks.
