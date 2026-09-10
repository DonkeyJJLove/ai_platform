# LION Local Swarm P0 — Docker Polygon

Status: `EXPERIMENT / TEST_ONLY / IMPLEMENTED_NOT_MATERIALIZED`

Ten dokument zapisuje historyczną granicę implementacyjną pierwszego lokalnego Docker proving-ground dla floty LION 1.4. Nie nadaje authority i nie jest źródłem runtime currentness.

## Cel

P0 miał udowodnić ograniczony łańcuch:

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

Sam start kontenera nie jest sukcesem. `FULL_SUCCESS` wymaga live authorized Docker effect, pięciu związanych terminal results, obowiązkowych negative tests, niezależnej observation, reconciliation `MATCHED` oraz cleanup evidence.

## Test-only implementation plane

Implementacja P0 celowo znajduje się w utrwalonej w repozytorium experiment plane `tools/p0_*`:

```text
tools/p0_docker_fleet_contract.py
tools/p0_docker_drone_runtime.py
tools/p0_docker_fleet_materializer.py
cyber_lion/tests/test_docker_fleet_polygon.py
deploy/docker/lion-drone-p0/Dockerfile
```

To rozdzielenie jest materialne. Canonical inventory `_production_path()` traktuje non-test `cyber_lion/*.py` jako production sources. Pierwotne umieszczenie pod `cyber_lion` zmieniło zamrożony production scan digest i prawidłowo spowodowało failure globalnych Core regressions. Eksperyment został więc przeniesiony do `tools/p0_*`, zamiast ponownie zamrażać historyczne production evidence wokół funkcji `TEST_ONLY`.

## Profil runtime

Definicja obrazu była przypięta immutable index digestem do Docker Hardened Images Python 3.11 / Debian 13 dla `linux/amd64`:

```text
sha256:ee6f2172d994d5197755698750a815f842fe7f7df67cadfa0d32f47076a3523e
```

Dockerfile kopiuje wyłącznie kontrakt P0 i one-shot drone runtime. Nie ma kroku `RUN`, instalacji pakietów ani shell step.

Wymagany runtime posture:

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

Kontener nie jest tożsamością drona. `DockerDroneBinding` wiąże logical identity z executor, generation, lease, capsule digest, exact image digest oraz expected container name.

## Mission capsules i praca D0

Każdy dron otrzymuje jeden immutable `MissionCapsule`, montowany read-only pod `/mission/capsule.json`. Wiąże mission/fleet/drone/role, generation/work unit, issue i expiry time, deterministic operation, bounded input wraz z digestem, policy digest oraz capsule digest. Mutation, identity substitution, stale/invalid input albo unsupported operation są odrzucane.

Pięć obowiązkowych ról:

```text
architecture
security
runtime
provenance
falsifier
```

Cała praca jest deterministyczna. LLM, SaaS model, GitHub API ani zewnętrzny service nie są częścią drone runtime.

Dla P0 receipt transport był celowo węższy niż broker: każdy one-shot drone emituje jeden canonical terminal result na stdout, a zaufany host-side provider miał pobrać go przez `docker logs`. `FleetResultAggregator` następnie egzekwuje mission/drone/generation/input/replay bindings. Mission-owned Docker `--internal` network pozostaje wymagany dla observable isolation i późniejszego reuse P1; żaden host port nie jest publikowany.

## Granica Docker authority

`tools.p0_docker_fleet_materializer` **nie** wywołuje Dockera. Kompiluje immutable fleet intent do exact Docker CLI argv i interpretuje niezależne `docker inspect` evidence. Oddzielny host-side provider musi już posiadać autoryzowany dostęp do właściwego Docker endpoint.

Compiler nigdy nie generuje:

```text
--privileged
--pid=host
--network=host
--ipc=host
/var/run/docker.sock mounts
/run/docker.sock mounts
```

P0 nie może zmieniać permissions socketa Docker, group membership, sudoers, SentinelX policy ani konfiguracji Docker daemon tylko po to, aby run zakończył się sukcesem.

## Live-state blocker zaobserwowany podczas misji

Odtworzony wtedy stan `LION-AUTH-LAB` pokazywał:

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

Ówczesne principals SentinelX i self-hosted runner nie mogły dotrzeć do żadnego Docker endpoint. Nie znaleziono istniejącego authority-preserving Docker effect broker/provider. Dlatego live image build, uruchomienie floty pięciu kontenerów i Docker-side observation **nie zostały wykonane**. Prawidłowa klasyfikacja brzmiała `IMPLEMENTED_NOT_MATERIALIZED`, blocker `NO_AUTHORIZED_DOCKER_EFFECT_PROVIDER`.

Blockera nie obchodzono przez zmiany grup, ownership/mode socketa, sudoers, `su`, mounty Docker socket ani zmiany hardeningu runnera.

## Walidacja i falsyfikacja

Dedykowany suite obejmował 12 static cases, w tym hardening degradation, capsule mutation, mission/drone substitution, fleet cardinality/role binding, internal network compilation, wykluczenie privileged/socket/host-namespace, wrong capsule binding, deterministic execution wszystkich pięciu ról D0, replay/stale generation, image substitution, niezależne parsowanie `docker inspect` oraz final-image definition checks.

Po poprawieniu placement do test-only tools plane exact WSL2 run na feature head `75660e3c75257e898fed1cd157a27cf233caf480` dał:

```text
P0 targeted tests: 12/12 OK
full repository suite: 2264 tests OK, 5 skipped
compileall: PASS
```

Environment-dependent negative tests — real rootfs write failure, rzeczywiste egress denial, live shell/package-manager absence, effective capability set, restart/lease behaviour oraz exact Docker cleanup — pozostały nieudowodnione do czasu istnienia autoryzowanego live provider.

## Historyczna granica a późniejsza ewolucja

Ten dokument opisuje P0 przed późniejszym VKT-R3. Fakt, że VKT-R3 później zmaterializował 3 × 128 rzeczywistych Kubernetes Podów przez inną, ograniczoną ścieżkę authority, nie zmienia historycznego wyniku P0 `IMPLEMENTED_NOT_MATERIALIZED`. Jest to supersession currentness/frontieru, a nie powód do przepisania dawnego eksperymentu.

## Następne transition w tamtym evidence epoch

Live P0 `FULL_SUCCESS` było zablokowane na wąskim authority-preserving provider dla istniejącego rootless Docker runtime. Dopiero po takim live proof następny eksperyment miał dodać:

```text
D0 deterministic fleet
-> shared LocalInferenceGateway
-> one shared LocalModelRuntime
```

P1 miał utrzymać model weights i SaaS credentials poza drone images oraz osobno mierzyć shared-context, cache i batching economics.

Bieżący następny krok należy dziś wyprowadzić ponownie z exact live `master`; nie należy automatycznie kontynuować historycznego P0 frontier.
