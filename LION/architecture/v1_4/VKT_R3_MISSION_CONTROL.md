# VKT-R3 Mission Control

## Scope

Mission Control is a read-only observability plane for the VKT-R3 local swarm. It consumes only the bounded `READ_POD_EVIDENCE` contract exposed through the VKT effect-admission client. It does not receive kubeconfig, Docker/containerd sockets, `kubectl`, `exec`, Pod mutation, K3s lifecycle, or vendor-network authority.

## Runtime model

The panel is a local systemd service running as `sentinelx`. It binds only to `127.0.0.1` and selects the first free port from the bounded set `8765` through `8775`, without terminating or replacing pre-existing listeners. The selected endpoint is written to the operator-readable runtime locator `/run/lion-vkt-mission-control/listen.json` (`0644` inside a `0755` runtime directory). Its source HEAD/TREE is derived from `/opt/lion/k3s-vkt-r3/source-identity.json`, so UI state is bound to the same installed source identity as the bounded provider. The evidence snapshot combines real Kubernetes Pod state with the structured Router `/state` snapshot. A heartbeat alone is not treated as proof of a live drone; Kubernetes readiness, Pod UID and the Router's freshness window remain distinct evidence carriers.

Mission Control stores normalized snapshots, structured events and structured messages in SQLite under `/var/lib/sentinelx/uploads/vkt-r3-mission-control/mission-control.db`. The database is an observability cache only. It is not an authority source and does not modify proof state.

## UI and transport

The repo-native implementation uses the Python standard library to avoid adding a new dependency stack. It provides HTTP endpoints for state/export/health and a WebSocket stream for live browser updates. The browser renders Pod/UID/restart counts, fresh drone counts, per-fleet state, cases, proof state, messages, ACK rate, orphans, duplicates, vendor requests, recent events and recent structured messages.

## Security boundary

The systemd unit runs as `sentinelx`, not root. `NoNewPrivileges` is enabled. `/opt/lion/k3s-vkt-r3` is read-only. The SQLite state directory remains private to `sentinelx`; only the non-sensitive endpoint locator in `/run/lion-vkt-mission-control` is operator-readable. The data source invokes only the `evidence` operation of `lion-vkt-effect-admission-client.py`.

## Currentness

Repository implementation is current only when its HEAD/TREE is the installed source identity. Active-runtime status must be reacquired from `LION-AUTH-LAB`; repository code or historical receipts alone are not evidence that the live panel or swarm is currently running.


## Operator / LPCL separation

Local environment preparation and local observation are allowed outside the test run. Mission Control is observation-only and cannot start, materialize, mutate, stop, or validate the swarm. The supervised test lifecycle is driven by LPCL. The canonical process contract is `LION/architecture/v1_4/VKT_R3_SUPERVISED_LOCAL_TEST.lpcl`. Manual test start is denied by architecture, not merely by convention.
