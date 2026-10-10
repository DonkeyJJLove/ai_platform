# R7 — jeden trwały LPCL przed pełną materializacją Docker

Status: **SOURCE CANDIDATE — NOT MERGED / NOT DEPLOYED / NO LIVE LPCL ACTIVATION**.

## Przypadek wykryty w produkcyjnym ownerze

`tools/lion_mission_control_v3.py:bind_lpcl_execution` żąda `READY`
od wszystkich 32 workerów Docker jeszcze zanim istnieje wykonywalny
driver misji. W efekcie operator-aktywowany LPCL/1.2 przechodził w
`LPCL_EXECUTION_BIND` bez trwałego, źródłowo związanego zapotrzebowania
na wykonawców. R5 wprowadził automatyczny rebind po pojawieniu się
kohorty, lecz nie zapisywał tego wcześniejszego `WAIT` w kanonicznym
schedulerze. Historia starej R24 floty zawiera różny `source_head/tree`
między `identity.json` a materialization receipt oraz niezgodne mounty;
nie wolno uruchamiać tych kontenerów jako aktualnych wykonawców.

## Delta implementacyjna

Istniejący `global_scheduler_once` nadal jest **jedynym** schedulerem.
W jego istniejącym, ograniczonym do 10 s `reconcile_activated_unbound_docker_once`
nowy scoped producer `park_activated_docker_lpcl_runtime_need` tworzy
**jeden** trwały checkpoint stanu `WAITING` oraz dokładny, kanoniczny
message `DOCKER_FLEET_BOOTSTRAP_CAPABILITY_NEED`.

Producer sprawdza w **tej samej SQLite misji**:
`mission_id`, `source_head`, `source_tree`, `spec_digest`,
`EXPLICIT_USER_ACTIVATION`, `operator_control.autonomy_allowed`,
`LPCL_DOCKER_LOCAL_MODEL`, brak poprzedniego effect adaptera.
Rekoncyliuje aktualne `Docker READY` wyłącznie przez istniejący
`_docker_local_model_currentness`. Need deklaruje dokładnie
`docker://MOON/lion-r24-autonomy`, 32 materialnych workerów,
`DOCKER_FLEET_BOOTSTRAP` oraz `CANONICAL_RUNTIME_ADMISSION_AND_EXPLICIT_LPCL`.

Stany: `AUTHORIZED LPCL_MISSION` → `WAITING` (bez effect driver lease,
bez rozpoczęcia fazy, bez material worker rows) → gdy prawdziwa
źródłowo zbieżna flota jest obserwowana,
oryginalny `bind_lpcl_execution` wznawia **ten sam driver_id** i
wiąże 32 container IDs oraz dokładne `LD/MD` topo. Nie utworzono
drugiego schedulera, relay, materializera ani ścieżki omijającej admission.
Repeated `WAIT` jest idempotentny, nie emituje kolejnych need events,
nie ponawia nieznanego efektu.

Źródłowo odmienna flota przechodzi do `DOCKER_FLEET_SOURCE_CURRENTNESS_DRIFT`
bez worker assignment. Utrata operator fence lub brak jawnej aktywacji
nie tworzy even `WAIT`.

## Dowód regresji

`cyber_lion/tests/test_r7_activated_docker_runtime_need.py` stosuje
izolowaną tymczasową SQLite i syntetyczne obserwacje kohorty bez Docker.
Testuje: brak aktywacji, operator fence, nieznaną klasę gate, początkową
niedostępność 32 workerów, source drift, idempotencję i transition do
samego drivera po 32 poprawnych material worker IDs.
Wraz z testami R5: 12/12 PASS w source worktree.

## Co pozostaje realnie do zbudowania

Ten zapisany need **nie jest** `RequestedRuntimeEffect`,
`RuntimeAdmission`, PDP `ALLOW`, provisioned executor, Docker `up`
ani odbiór wykonanej misji. Znaczenie `WAITING` jest dokładnie
`WAIT_FOR_ADMITTED_DOCKER_FLEET`, nie `PREPARED` lub `RUNNING`.

Następna source-level delta musi konsumować taki need w **istniejącym**
ownerze `ActionIR→PDP→RuntimeAdmissionEngine→SQLiteRuntimeAdmissionSource`.
Po jawnej aktywacji dokładnego LPCL i obowiązującym source/authority
issuerze, ten proces ma przygotować nową immutable R24 materialization
(poza starymi 32 kontenerami), wydać konsumowalny jednorazowo admission,
wywołać już istniejący `DockerFleetBootstrapExecutor` na MOON i
dowieść 32/32 źródłowo zgodnych heartbeatów, zanim R5 rebind pójdzie dalej.
Nie wolno maskować `DOCKER_FLEET_BOOTSTRAP` jako sandbox `RUN_TEST`.

Następny odrębny rzeczywisty odbiór wymaga: `MAT04`, aktualnej
sesji SaaS z response+receipt, niezależnych LOCAL trajectories,
zainstalowanych trusted cooperative preactivation/production/verify
materializerów, rzeczywistych bajtów artefaktu i readbacku oddzielnego
VERIFIER. Program Application Factory R1 nadal ma fazę
`CROSS_MODEL_RECON` wymagającą już materialnych leases. R7 jej
nie omija i nie zgłasza pełnego E2E success.
