# LION Mission Control

LION Mission Control is the generic, read-only observation plane for LION test, tool, fleet, and LPCL runs. It replaces the VKT-R3-specific dashboard as the primary observer. VKT-R3 remains supported through the `VKT_R3` adapter; bounded OSS repository tests use the `OSS_REPOSITORY_TEST` adapter; future LPCL processes can enter the common run registry through the `lion.observation-event/v1` event contract.

The core schema is intentionally runtime-neutral. A run carries identity, process class, adapter, status, phase, source, target, workload, authority, participants, metrics, artifacts, receipts, cleanup and verification. VKT-specific properties such as 384 pod cardinality, cases, messages and ACK are adapter metrics, not global requirements. Completed runs persist in SQLite after their runtime namespace or job has been deleted.

The primary service is `lion-mission-control.service`, running as `sentinelx` on loopback only and selecting the first free port in 8765–8775. The endpoint is published in `/run/lion-mission-control/listen.json`; `/run/lion-vkt-mission-control/listen.json` is written by the same process as a compatibility locator. The old `lion-vkt-mission-control.service` is disabled and must not run independently.

Runtime authority is separated from observation. Mission Control cannot use the mutating VKT admission socket directly. Its systemd namespace masks mutating/control sockets and adapters use `/run/lion-mission-control-read.sock`, served by a fixed read-only proxy whose allowlist contains only `PING`, `READ_POD_EVIDENCE`, and `READ_OSS_REPO_TEST_EVIDENCE`. HTTP exposes only GET and WebSocket observation surfaces; POST, PUT, PATCH and DELETE return 405.

The generic local event ingress is `/run/lion-mission-control/events.sock`. It accepts `lion.observation-event/v1` records only from root or `sentinelx`, stores events append-only, and projects run/phase/metric/participant/artifact/receipt state without executing commands. Events are declarations or observations, not independent proof; `VERIFIED` state requires corroborating runtime, receipt, or artifact evidence.

Known historical VKT-R3 and `pallets/itsdangerous` evidence is imported from fixed allowlisted evidence roots. The artifact index stores bounded metadata and hashes only; path traversal, evidence-root escape and secret-like filenames are rejected. No arbitrary filesystem browser is exposed by the HTTP API.
