# LION Local Swarm P0 — Docker Polygon

Status: `EXPERIMENT / TEST_ONLY / IMPLEMENTED_NOT_MATERIALIZED`

This document records the first local-fleet Docker proving-ground implementation boundary for LION 1.4. It grants no authority and is not a runtime-currentness source.

## Objective

P0 is intended to prove the bounded chain:

```text
Mission
-> DockerFleetPlan
-> five logical DroneIdentity bindings
-> bounded Docker containers
-> deterministic D0 work
-> host-side aggregation
-> independent docker-inspect observation
-> reconciliation
-> exact cleanup
```

Container startup alone is not success. `FULL_SUCCESS` requires a live authorized Docker effect, five bound terminal results, mandatory negative tests, independent observation, `MATCHED` reconciliation and cleanup evidence.

## Test-only implementation plane

The P0 implementation intentionally lives under the repository's established `tools/p0_*` experiment plane:

```text
tools/p0_docker_fleet_contract.py
tools/p0_docker_drone_runtime.py
tools/p0_docker_fleet_materializer.py
cyber_lion/tests/test_docker_fleet_polygon.py
deploy/docker/lion-drone-p0/Dockerfile
```

This separation is material. The canonical `_production_path()` inventory treats non-test `cyber_lion/*.py` as production sources. An initial placement under `cyber_lion` changed the frozen production scan digest and correctly failed global Core regressions. The experiment was therefore moved to `tools/p0_*` rather than refreezing historical production evidence around a TEST_ONLY feature.

## Runtime profile

The image definition is pinned to Docker Hardened Images Python 3.11 / Debian 13 for `linux/amd64` by immutable index digest:

```text
sha256:ee6f2172d994d5197755698750a815f842fe7f7df67cadfa0d32f47076a3523e
```

The Dockerfile copies only the P0 contract and one-shot drone runtime. It has no `RUN`, package-install or shell step.

Required runtime posture:

```text
uid:gid                 65532:65532
root filesystem         read-only
Linux capabilities      DROP ALL
no-new-privileges       required
PID limit               64
memory limit            128 MiB
CPU limit               0.20 CPU
tmpfs /tmp              16 MiB, noexec,nosuid,nodev
persistent state        none
host ports              none
Docker socket           forbidden
privileged mode         forbidden
host namespaces         forbidden
runtime shell           absent by image profile
runtime package manager absent by image profile
```

The container is not the drone identity. `DockerDroneBinding` binds logical identity to executor, generation, lease, capsule digest, exact image digest and expected container name.

## Mission capsules and D0 work

Each drone receives one immutable `MissionCapsule` mounted read-only at `/mission/capsule.json`. It binds mission/fleet/drone/role, generation/work unit, issue and expiry time, deterministic operation, bounded input plus digest, policy digest and capsule digest. Mutation, identity substitution, stale/invalid input or unsupported operation is denied.

The five mandatory roles are:

```text
architecture
security
runtime
provenance
falsifier
```

All work is deterministic. No LLM, SaaS model, GitHub API or external service is part of the drone runtime.

For P0 the receipt transport is deliberately narrower than a broker: every one-shot drone emits one canonical terminal result on stdout, and the trusted host-side provider would retrieve it through `docker logs`. `FleetResultAggregator` then enforces mission/drone/generation/input/replay bindings. A mission-owned Docker `--internal` network remains required for observable isolation and later P1 reuse; no host port is published.

## Docker authority boundary

`tools.p0_docker_fleet_materializer` does **not** invoke Docker. It compiles immutable fleet intent into exact Docker CLI argv and interprets independent `docker inspect` evidence. A separate host-side provider must already possess authorized access to the appropriate Docker endpoint.

The compiler never generates:

```text
--privileged
--pid=host
--network=host
--ipc=host
/var/run/docker.sock mounts
/run/docker.sock mounts
```

P0 must not alter Docker socket permissions, group membership, sudoers, SentinelX policy or Docker daemon configuration to make a run succeed.

## Live-state blocker observed during the mission

The reacquired `LION-AUTH-LAB` state showed:

```text
host                      LION-AUTH-LAB
runtime                   WSL2 / linux/amd64
Docker Engine             active
Docker client             26.1.5+dfsg1
system socket             /var/run/docker.sock, root:docker 0660
SentinelX principal       sentinelx (no docker group)
GitHub runner principal   lion-maintenance-runner (no docker group)
rootless principal        lion-container-runtime-lab
rootless runtime          SUPPORTED_ACTIVE
rootless socket           /run/user/1000/docker.sock
trust class               TEST_ONLY
physical domain           WINDOWS-MOON
```

The current SentinelX and self-hosted-runner principals cannot reach either Docker endpoint. No existing authority-preserving Docker effect broker/provider was found. Therefore live image build, five-container fleet execution and Docker-side observation were **not executed**. The correct classification is `IMPLEMENTED_NOT_MATERIALIZED` with blocker `NO_AUTHORIZED_DOCKER_EFFECT_PROVIDER`.

This blocker was not bypassed using group changes, socket ownership/mode changes, sudoers, `su`, Docker-socket mounts or runner hardening changes.

## Validation and falsification

The dedicated suite covers 12 static cases, including hardening degradation, capsule mutation, mission/drone substitution, fleet cardinality/role binding, internal network compilation, privileged/socket/host-namespace exclusion, wrong capsule binding, deterministic execution of all five D0 roles, replay/stale generation, image substitution, independent `docker inspect` parsing and final-image definition checks.

After placement was corrected to the test-only tools plane, an exact WSL2 run on feature head `75660e3c75257e898fed1cd157a27cf233caf480` produced:

```text
P0 targeted tests: 12/12 OK
full repository suite: 2264 tests OK, 5 skipped
compileall: PASS
```

The environment-dependent negative tests — real rootfs write failure, actual egress denial, live shell/package-manager absence, effective capability set, restart/lease behaviour and exact Docker cleanup — remain unproven until the authorized live provider exists.

## Next transition

Live P0 `FULL_SUCCESS` is blocked on a narrow authority-preserving provider for the existing rootless Docker runtime. Only after that live proof may the next experiment add:

```text
D0 deterministic fleet
-> shared LocalInferenceGateway
-> one shared LocalModelRuntime
```

P1 must keep model weights and SaaS credentials out of drone images and separately measure shared-context, cache and batching economics.
