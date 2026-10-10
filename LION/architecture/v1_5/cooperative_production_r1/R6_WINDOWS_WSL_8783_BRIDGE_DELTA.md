# R6 — separacja Windows 8780 od mostu WSL

Classification: SOURCE_CANDIDATE, NO_DEPLOYMENT_AUTHORITY.

Operator's current Windows panel is a native Python 3.13 listener at Windows
127.0.0.1:8780 with its own canonical ThreadStore owner/lease. The WSL
read-only bridge previously opened another `127.0.0.1:8780`. Windows
`wslrelay.exe` also advertised a Windows port 8780 listener; this can shadow
native panel routing. Canary instances on 8781 and 8782 have separate SQLite
databases, and are **not** competing owners of the canonical database.

The change only relocates the **WSL** bridge listener to 8783 while leaving
its upstream `WINDOWS_CANONICAL` target at Windows `127.0.0.1:8780`.
The canonical Mission Control deployment drop-in sets
`LION_COGNITIVE_READINESS_URL=http://127.0.0.1:8783`, using the
existing fail-closed consumer; no second consumer or scheduler is created.

The 8780 bridge's legacy systemd unit name remains stable to preserve
SentinelX's existing [status,stop,start] management and historic service
identity. The new unit template remains with the original `Conflicts`
setting as a safety fence. Bridge source bytes are unchanged and verified
by the existing `bridge.sha256` before service launch.

## Deployment and readback order

- Independently verify current GitHub master HEAD/TREE, required CI and
  SHA-pinned source package. Preserve the existing MC database and service
  rollback; do not replace a conversation store or remove Docker workers.
- Install source-bound Mission Control through the existing stage/install
  broker, with the new explicit readiness endpoint. This may briefly cause
  its cognitive-readiness path to fail closed until the bridge is moved.
- After confirming no live operational mission and no pending dependent
  request, back up the exact bridge unit and use the explicitly allowlisted
  scoped systemd edit/daemon-reload/stop-start route. Never modify
  `bridge.py` to silently ignore `--port`.
- Confirm WSL 8780 unbound, WSL 8783 HTTP 200, Mission Control 8766 HTTP
  200 and its active environment points to 8783. Confirm Windows native
  8780 health and owner/ThreadStore lease independently. A new browser
  LPCL session is not presumed ready from these health checks.
- On failure restore the exact previous systemd unit and MC drop-in
  using documented broker rollback; leave old lease/DB untouched.

This solves only the source-bound observation route and port shadowing.
It does **not** authorize Docker `up`, register an LPCL, renew the SaaS
session, verify MAT04, or prove material artifact completion.
