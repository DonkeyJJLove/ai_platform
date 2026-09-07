# LION Local Swarm P0 — Docker Polygon

Status: `EXPERIMENT / TEST_ONLY`

This document records the first material local-fleet implementation boundary for LION 1.4. It does not grant authority and must not be used as a source of runtime currentness.

## Objective

P0 proves a narrow chain:

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

## Runtime profile

The P0 image is defined by `deploy/docker/lion-drone-p0/Dockerfile` and is pinned to Docker Hardened Images Python 3.11 / Debian 13 for `linux/amd64` by immutable index digest. The final image contains only the Python runtime and the minimum Cyber-Lion modules required by the one-shot drone process.

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

The container is not the drone identity. `DockerDroneBinding` binds the logical identity to an executor, generation, lease, capsule digest, exact image digest and expected container name.

## Mission capsules

A drone receives exactly one immutable `MissionCapsule` mounted read-only at `/mission/capsule.json`. The capsule binds:

- mission and fleet;
- drone and role;
- generation and work unit;
- issue/expiry timestamps;
- deterministic operation;
- bounded input payload and digest;
- policy digest;
- self-verifying capsule digest.

The P0 runtime validates the capsule before work. Mutation, wrong mission/drone, unsupported operation or expiry produces `DENIED` and a non-zero exit.

## D0 workload

Five roles are mandatory:

```text
architecture
security
runtime
provenance
falsifier
```

All work is deterministic. No LLM, model API, GitHub API or external service is available to the drone.

The transport chosen for this first polygon is intentionally narrower than a broker: every one-shot drone emits exactly one canonical terminal result on stdout. The trusted host-side provider retrieves the result via `docker logs`; `FleetResultAggregator` applies mission/drone/generation/input/replay binding and creates one fleet result. This is an equivalent local receipt transport for P0 and removes an unnecessary network service from the first falsification surface.

A mission-owned Docker `--internal` network is still required so that network isolation is independently observable and later broker/gateway work can reuse the same materialization boundary. No host port is published.

## Docker authority boundary

`cyber_lion.enterprise.docker_fleet_polygon` does **not** call Docker. It compiles immutable fleet intent into exact CLI argv and interprets independent `docker inspect` evidence. An effect-capable provider must be separate and already authorized by the host/runtime authority model.

The adapter never generates:

```text
--privileged
--pid=host
--network=host
--ipc=host
/var/run/docker.sock mounts
/run/docker.sock mounts
```

No P0 code may alter Docker socket permissions, group membership, sudoers, SentinelX policy or daemon configuration to make a run succeed.

## Live-state blocker observed at mission start

On the reacquired `LION-AUTH-LAB` state for this experiment:

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

The current SentinelX and self-hosted runner principals cannot reach either authorized Docker endpoint. Therefore repository implementation and static CI may complete, but live materialization must remain `IMPLEMENTED_NOT_MATERIALIZED` until an existing authority-preserving provider exposes the rootless runtime or another approved Docker effect path is established.

This blocker must not be solved by adding either principal to the `docker` group, changing socket ownership/mode, adding sudoers rules, using `su`, mounting the Docker socket into a workload or weakening runner hardening.

## Observation and reconciliation

`observation_from_docker_inspect()` reconstructs an `ObservedContainer` from host-side evidence and validates the security boundary independently of drone output. `reconcile()` then compares the requested plan, five observed containers and the canonical aggregate result.

Possible terminal classifications:

```text
MATCHED
MISMATCHED
UNKNOWN
```

Only `MATCHED` is success. `UNKNOWN` is never upgraded to success.

## Falsification set

Repository tests currently cover the static equivalents of:

- runtime hardening degradation;
- capsule mutation;
- mission/drone substitution;
- incomplete/duplicate fleet identity;
- internal network compilation;
- Docker socket/privileged/host namespace exclusion;
- wrong capsule-to-drone binding;
- deterministic execution for all five D0 roles;
- replayed terminal result;
- wrong mission and stale generation;
- image substitution during reconciliation;
- independent Docker-inspect parsing;
- final-image definition without runtime install or shell steps.

The remaining environment-dependent negative tests — real rootfs write failure, actual egress denial, runtime shell/package-manager absence, live capability set, exact restart/lease behaviour and cleanup — require the authorized live Docker provider and cannot be claimed from static tests.

## Next transition

After and only after live P0 reaches `FULL_SUCCESS`, the next target is `LION-LOCAL-SWARM-P1-INFERENCE-GATEWAY`:

```text
D0 deterministic fleet
-> shared LocalInferenceGateway
-> one shared LocalModelRuntime
```

P1 must keep model weights and SaaS credentials out of drone images and introduce shared-context/cache/batching accounting as a separate experiment.
