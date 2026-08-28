# LION — hosty, środowiska wykonawcze i laboratoria

**Stan obserwacji:** 2026-08-28  
**Baseline repozytorium:** `master@c511a38d67750934bf462730ed046e482e8e6bef`  
**Status dokumentu:** inventory / documentation only — ten dokument nie nadaje authority i nie jest źródłem currentness przy wykonywaniu efektu.

## 1. Reguła interpretacji

LION rozdziela co najmniej pięć różnych pojęć, których nie wolno utożsamiać:

```text
PHYSICAL CONTROL DOMAIN
!= HOST / HOST RECORD
!= ENVIRONMENT / GUEST / WSL / VM / CONTAINER
!= FLEET EXECUTOR / WORKLOAD IDENTITY
!= LAB / REPOSITORY
```

Wpis w rejestrze, identyfikator SentinelX, nazwa WSL albo przejście testu nie dowodzą samodzielnie fizycznej niezależności hosta. Analogicznie publiczne repozytorium laboratoryjne nie jest automatycznie częścią produkcyjnego runtime LION.

Dla stanu dynamicznego obowiązuje precedencja live evidence. Przed consequential effect należy ponownie obserwować exact Git state, runtime identity, currentness, authority i wymagane kanały obserwacyjne.

## 2. Aktualna topologia laboratoryjna

Kanoniczny rendering środowiska produkcyjnego/laboratoryjnego znajduje się w [`docs/architecture/production-entry/README.md`](architecture/production-entry/README.md). Na powyższym baseline opisuje świat:

- world: `e006-r9d-9g3a1-three-wsl-lab`;
- topology class: `MULTI_LOGICAL_NODE_LAB`;
- logical nodes: **3**;
- physical control domains: **1**;
- wspólna domena fizyczna: `WINDOWS-MOON`.

| Logical node | SentinelX / routing ID | Rola | Runtime | Physical domain | Trust / authority status | Znaczenie |
| --- | --- | --- | --- | --- | --- | --- |
| `MOON` | `host_045dbf1af63f49d4` | `LAB_CONSUMER_OBSERVER` | `WSL2` | `WINDOWS-MOON` | `NONE` | konsument/observer; logiczny węzeł laboratoryjny |
| `LAB-DEBIAN` | `host_2c67e8a68ffd6360` | `LAB_BOUNDED_PRODUCER` | `WSL2` | `WINDOWS-MOON` | `TEST_ONLY` | ograniczony producent efektów w laboratorium |
| `LAB-UBUNTU` | `host_df0fa36eb7d44d5b` | `LAB_INDEPENDENT_VERIFIER` | `WSL2` | `WINDOWS-MOON` | `NONE` | niezależna rola logiczna verifiera |

**Najważniejszy wniosek:** trzy różne identyfikatory routingu i trzy instancje WSL dowodzą separacji logicznej, ale **nie** dowodzą trzech niezależnych hostów fizycznych. Aktualny dossier ma `PHYSICAL_TOPOLOGY=FAIL`, `FAILURE_DOMAIN_INDEPENDENCE=FAIL`, `AUTHORITY=BLOCKED` i `DEPLOYMENT_READINESS=BLOCKED`.

Aktualny blocker produkcyjny to brak osobnego, fizycznie kontrolowanego external control domain. Docelowy następny wzorzec topologii to istniejący consumer/control plane oraz osobny fizyczny signer z hardware-backed, non-exportable keystore. Samo pojawienie się drugiego hosta nadal nie mintuje produkcyjnego authority.

## 3. MOON — nazwa występująca w kilku warstwach

`MOON` pojawia się równocześnie jako nazwa logicznego węzła bieżącego laboratorium oraz jako identyfikator używany w testach granicy host/authority. Nie należy scalać tych klas dowodu.

W [`cyber_lion/tests/test_host_authority_separation.py`](../cyber_lion/tests/test_host_authority_separation.py) test regresyjny tworzy obserwację `MOON` do sprawdzenia separacji runtime user / runner / control-plane group. Jest to **fixture/test evidence**, a nie niezależny dowód bieżącej fizycznej topologii. Bieżącą topologię należy brać z current world model / production-entry dossier.

## 4. Kanoniczna taksonomia hostów i środowisk

Kontrakt [`cyber_lion/contracts/host_authority_separation.py`](../cyber_lion/contracts/host_authority_separation.py) rozróżnia:

```text
HostKind:
  PHYSICAL_HOST
  VIRTUAL_GUEST
  CONTAINER
  REMOTE_EXECUTION

RuntimeClass:
  NATIVE
  WSL2
  VM
  CONTAINER
  REMOTE

ConnectivityPosture:
  HOST_LOCAL
  LAN_REACHABLE
  REVERSE_TUNNEL
  BROKERED_API
  OFFLINE
```

`HostRecord` jest inventory/metadata. `EnvironmentRecord` reprezentuje konkretne środowisko wykonawcze związane z hostem. Żaden z tych obiektów nie może przenosić grantów, credentials, tokenów ani effect authority.

Podstawowy invariant:

```text
HOST MEMBERSHIP != AUTHORIZATION
ENVIRONMENT MEMBERSHIP != AUTHORIZATION
ROUTING IDENTITY != AUTHORITY
```

Authority pozostaje osobną ścieżką `PDP -> typed grant -> PEP/reference monitor -> bounded effect -> observation -> reconciliation`.

## 5. Lifecycle środowiska

[`cyber_lion/contracts/environment_lifecycle.py`](../cyber_lion/contracts/environment_lifecycle.py) wprowadza osobny lifecycle środowisk i ich rewizji. Podstawowe stany to:

```text
REGISTERED -> ACTIVE -> RETIRED
```

Aktywacja nie może wynikać wyłącznie z nazwy hosta lub deklaracji operatora. Kontrakt wymaga spójności host binding, runtime, currentness, integrity oraz — zależnie od typu środowiska — dowodów parent/mount/bridge. Rewizje zachowują lineage i supersession zamiast cichej podmiany środowiska pod tym samym identyfikatorem.

Dla WSL szczególnie istotne są jawne parent-host binding oraz bridge/mount metadata. `WSL_INSTANCE != PHYSICAL_CONTROL_DOMAIN` pozostaje inwariantem produkcyjnym.

## 6. Zewnętrzne execution providers nie są hostami LION

GitHub-hosted runners używane przez workflow (np. `ubuntu-24.04` w Bandit CI) są efemerycznym zewnętrznym execution providerem. Nie wolno ich liczyć jako trwałych hostów LION ani jako niezależnych physical control domains tylko dlatego, że workflow został uruchomiony na innym runnerze.

Analogicznie zdalny model, SaaS, MCP albo API są external effect/inference domains, dopóki nie istnieje osobny mechanizm atestacji i bindingu do lokalnego authority model.

## 7. Laboratoria i repozytoria ekosystemu

Machine-readable portfolio znajduje się w [`cyber_lion/registry/repositories.json`](../cyber_lion/registry/repositories.json). Rejestr został wygenerowany z archeologii repozytoriów 2026-08-18, dlatego jego role są użyteczne jako mapa pochodzenia, ale jego pole `maturity` nie może nadpisywać świeższego live state. W szczególności `ai_platform` od tego czasu rozwinęło wykonywalny control/runtime plane.

| Repozytorium / lab | Rola w ekosystemie | Warstwa | Interpretacja bieżąca |
| --- | --- | --- | --- |
| `DonkeyJJLove/ai_platform` | canonical LION control plane, contracts, authority/runtime/evidence | `SEM/MAND/INF` | **CURRENT CANONICAL REPOSITORY**; executable architecture w aktywnym rozwoju |
| `DonkeyJJLove/chunk-chunk` | HMK-9D, context compression/routing | `SEM` | research/specification provider |
| `DonkeyJJLove/glitchlab` | delta/anomaly/structure/invariants | `SEM/MAND` | executable/mixed analysis lab; integracja przez kontrakty/adapters |
| `DonkeyJJLove/HA2D` | cognitive state, memory semantics, Human-AI HUD | `SEM/MAND` | specification/research lab |
| `DonkeyJJLove/hipotezy_nadawcze_LLM` | hypothesis research, communication epistemology | `SEM` | epistemic research lab; output nie jest authority |
| `DonkeyJJLove/mosaic_lab_pro.py` | structure graph, abstraction, visualization | `SEM/INF` | executable prototype/lab |
| `DonkeyJJLove/sbom` | AID identity, SBOM/supply-chain provenance, gate evidence | `MAND/INF` | DevSecOps/provenance lab i compatibility source |
| `DonkeyJJLove/swarm` | telemetry/execution mesh, distributed workloads | `INF/MAND` | executable swarm/Kubernetes lab; nie jest automatycznie production fleet |
| `DonkeyJJLove/SymulacjaKaskadySieciowej` | simulation, Monte Carlo, sensitivity analysis | `SEM/INF` | executable model/simulation lab |
| `DonkeyJJLove/writeups` | research corpus, evidence source, publication | `SEM/MAND` | epistemic/research corpus; free-form text nie jest policy source |

Szczegółowe historyczne capability notes pozostają w [`cyber_lion/REPOSITORY_INVENTORY.md`](../cyber_lion/REPOSITORY_INVENTORY.md). Przy konflikcie z live code lub current CI pierwszeństwo ma nowszy dowód.

## 8. Host/lab status matrix

| Klasa | Stan na baseline | Co jest udowodnione | Czego nie wolno z tego wywnioskować |
| --- | --- | --- | --- |
| Three-WSL lab | `OBSERVED/RENDERED` | 3 logiczne identity, role separation, WSL2 routing, protocol/evidence tests | 3 niezależne maszyny fizyczne |
| Physical topology | `FAIL` | 1 fizyczna domena `WINDOWS-MOON` | production-grade failure-domain independence |
| Lab authority | `TEST_ONLY/NONE` | ograniczone laboratoryjne role | production authority |
| Production entry | `BLOCKED` | jawny blocker i transition map | możliwość deploymentu produkcyjnego |
| Repository labs | `REGISTERED PORTFOLIO` | istnieją źródła/laby i role integracyjne | że ich kod jest zintegrowany z current runtime |
| GitHub runners | `EXTERNAL/EPHEMERAL` | zewnętrzne CI execution | trwały host LION lub physical control domain |

## 9. Reguły dla kolejnych hostów

Nowy host lub environment powinien wejść do dokumentacji dopiero po związaniu co najmniej:

```text
stable host/environment identity
host kind + runtime class
physical control domain
connectivity posture
parent binding (jeżeli dotyczy)
implementation/runtime digest
currentness evidence
integrity evidence
observability requirements
lifecycle state
independent evidence reference
```

Wpis inventory nie zwiększa authority. Jeżeli currentness, wymagane obserwatory albo integralność stają się `UNKNOWN/FAILED`, system musi degradować, zamrażać lub odbierać uprawnienia zgodnie z klasą skutku.

## 10. Powiązane dokumenty

- [`docs/architecture/production-entry/README.md`](architecture/production-entry/README.md) — current three-WSL world, evidence matrix i blocker produkcyjny.
- [`cyber_lion/contracts/host_authority_separation.py`](../cyber_lion/contracts/host_authority_separation.py) — taksonomia i nieprzenoszenie authority przez host/environment.
- [`cyber_lion/contracts/environment_lifecycle.py`](../cyber_lion/contracts/environment_lifecycle.py) — lifecycle i revision lineage.
- [`cyber_lion/REPOSITORY_INVENTORY.md`](../cyber_lion/REPOSITORY_INVENTORY.md) — historyczny/szczegółowy inwentarz capability repozytoriów.
- [`cyber_lion/registry/repositories.json`](../cyber_lion/registry/repositories.json) — machine-readable registry ekosystemu.
- [`../OPEN_SOURCE_LICENSES.md`](../OPEN_SOURCE_LICENSES.md) — status licencji laboratoriów i bezpośrednich komponentów open source.

---

**Invariant końcowy:** liczba logicznych hostów, dronów, WSL, runnerów albo repozytoriów nie może być użyta jako substytut liczby niezależnych fizycznych failure domains ani jako substytut authority.