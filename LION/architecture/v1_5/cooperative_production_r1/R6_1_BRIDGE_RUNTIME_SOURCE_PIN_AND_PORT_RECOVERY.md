# R6.1 — source-bound Windows cognitive bridge port recovery

Classification: `SOURCE_CANDIDATE / NOT_MERGED / NOT_DEPLOYED`. Does not create LPCL authority.

## Reproduced failure

PR #439 had deployed a systemd template for the WSL read-only bridge to serve at
`127.0.0.1:8783` while retaining native Windows `127.0.0.1:8780` as upstream.
During the first controlled MOON cutover, `ExecStartPre` SHA checking passed
but `bridge.py --serve --port 8783` returned code 2: the original installed
read-only bridge still enforced `args.port == 8780`. The independently
observed service did not start, and WSL 8783 and 8780 were unavailable.

The exact old service unit was restored with scoped SentinelX stop, edit,
daemon-reload and start, then read back as `active (running)`, SHA
`ExecStartPre=SUCCESS`, and HTTP 200 from WSL `127.0.0.1:8780/health`.
Mission Control `8766/health` remained HTTP 200. No Windows process,
ThreadStore lease, SQLite conversation database, Docker worker or LPCL mission
was changed by the failed port cutover or rollback.

## This source change

The original installed `bridge.py` had SHA-256
`66e9674addc7bc28de75bf6d047b8a1ee30534605d020a1ed0596e049fe51909`.
R6.1 promotes its original exact bytes to a repository-owned source in
`deploy/mission-control/v3/lion-windows-cognitive-readonly-bridge.py` and
changes only its header and the explicit allowed loopback-listener vocabulary:
`8780` (existing rollback) or `8783` (R6 canonical WSL route). All
other ports are denied. The upstream stays strictly Windows canonical
`http://127.0.0.1:8780`, existing scoped health/cognitive-readiness
GET-only routes remain unchanged, and POST/PUT/DELETE/PATCH remain denied.

`lion-windows-cognitive-readonly-bridge.sha256` seals exact installed
bytes for the existing systemd `ExecStartPre`. Distinct raw source, pin,
unit, and single-owner restart are necessary before the new port is accepted.
This change does not grant authorization or create a second canonical provider.

## Required bounded rollout after source merge and CI

1. Re-acquire GitHub `master` exact HEAD/TREE and 4 required PR workflow
   success results; independently verify deployment source blob/pin.
2. Stop exactly `lion-windows-8780-readonly-bridge.service` (SentinelX
   already permits status/stop/start); preserve current source, SHA pin and
   unit before changing them.
3. Atomically stage source under the same existing runtime root, validate
   syntax and SHA. Replace `bridge.py`, `bridge.sha256` and the exact unit
   listener `8780 -> 8783`; do not edit the Windows canonical target.
   Unit pin must verify before systemd launch.
4. Run `daemon-reload`, then the same scoped service start. Read back
   `127.0.0.1:8783/health` HTTP 200 with `authority_effect=NONE` and no
   WSL listener on 8780. Recheck Windows native 8780 owner/ThreadStore.
5. Stage/install exact merged Mission Control via its original bounded
   `MISSION_CONTROL_V3_STAGE_CURRENT_MASTER/INSTALL` deployment owner,
   not manually copied Python. Its already source-tracked systemd drop-in
   binds `LION_COGNITIVE_READINESS_URL=http://127.0.0.1:8783`.
   Read back 8766 HTTP 200 and the actual systemd environment.
6. On any mismatch, revert only this exact bridge source, pin and unit to
   preserved copies, restore the old listener on 8780; independently check
   HTTP and SQLite again before any dependent replay.

Test suite uses a fake HTTP server to prove exact 8780/8783 allowlist,
denial of other ports, unchanged Windows upstream and mutation-method
denial. It does **not** create live SaaS responses, MAT04, Docker runtime
admission, or independently verified material artifact bytes.
