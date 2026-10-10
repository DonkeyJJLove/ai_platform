# R9 — fazowe zapotrzebowanie materialne LPCL w Mission Control

Classification: **SOURCE CANDIDATE / NOT MERGED / NOT DEPLOYED**. Release owner:
`DonkeyJJLove/ai_platform`. Authority and runtime effect: `NONE`.

## Pochodzenie implementacji i brak drugiego schedulera

Ten przyrost uzgadnia bieżący `master` po PR #442 z wcześniejszym,
nadal otwartym szkicem PR #430, który zbudował source-only
`material_fleet_lifecycle.py` oraz izolowane, odczytowe testy.
Oryginalny semantyczny kod projekcji i CLI zostały przeniesione bez
nadpisywania dokumentów historycznych i bez scalania przestarzałego
ref `e0e979d...`. Testy dostosowano jawnie do **nowego** call site
aktualnego Mission Control.

`tools/lion_mission_control_v3.py::process_snapshot` jest istniejącym
źródłem szczegółów jednej misji. R9 podpina tam
`mission_material_fleet_lifecycle_snapshot()` i aktualizuje
`deploy/mission-control/v3/control-v3.js`, żeby przejść z widoku
`ACTIVE ECOSYSTEM` do dowodów w zakładce `Cluster`. Bez nowego
schedulera, ingressu Docker ani nowej tabeli uprawnień.

## Pojemność zależna od aktualnej fazy

```text
CONTROL_PLANE_RECONNAISSANCE       -> 0 material workers
COOPERATIVE_WORKER_PREACTIVATION  -> 1 material worker
COOPERATIVE_ARTIFACT_BOOTSTRAP    -> 32 material workers
COOPERATIVE_ARTIFACT_PRODUCTION   -> 32 material workers
COOPERATIVE_ARTIFACT_VERIFY       -> 32 material workers
TERMINAL (reconciled)             -> 0 material workers
```

Liczba pochodzi wyłącznie z aktualnego w misji, trwałego
`PhaseExecutionContract` po odtworzeniu i weryfikacji **całego**
`contract_digest`. Nie jest parsowana z nazwy etapu, odczytu
`data-workers` w JS ani z pożądanej liczby 32 w LPCL.

Kod `material_fleet_lifecycle.project_lifecycle` weryfikuje też
source/LPCL digest, operator control, lease/generację drivera,
aktualność schedulera, zajęte assignments i leases także innych misji,
oraz pełną tożsamość 32 identyfikatorów w przekazanym carrierze.
Fałszywy/stary digest carrier, niewłaściwe źródło, nieznana faza
albo terminal bez reconciliation oznaczają `BLOCKED`.

## Ścisłe znaczenie produkcyjnej projekcji

Ten pierwszy konsument Mission Control **celowo** wywołuje
`project_lifecycle` z `current_source=None` i
`fleet_carrier=None`, bo serwer nie posiada niezależnego, aktualnego
źródła dowodu swojego wdrożenia i 32 materialnych heartbeatów pod
tożsamością tej samej misji.

Zatem wyznacza `desired_workers` i `phase_contract_digest`, ale
nie promuje currentness, `READY`, admission lub efektu. W UI można
zobaczyć `0/1/32` obok `UNKNOWN/UNVERIFIED`, jawnych blockerów
i `effect_admitted=false`. Jest to reprezentacja potrzeby, nie
bramka uruchomienia.

Stan R7 `WAIT_FOR_ADMITTED_DOCKER_FLEET` może nadal oczekiwać na
32 materialnych workerów nawet dla pierwszej fazy o wymaganiu
semantycznym `desired_workers=0`. Taką różnicę panel musi
ujawniać jako **legacy bootstrap dependency**, nie udawać, że
faza startuje. R8 source consumer działa tylko z osobnym kanonicznym
`RuntimeAdmission`; ten przyrost nie zmienia R8 ani nie uruchamia
historycznej R24 kohorty.

## Artefakty, testy i niezależne powiązania

Wprowadzone i odbierane osobno:

- moduł `cyber_lion/mission_control/material_fleet_lifecycle.py`,
  CLI `tools/lion_material_fleet_lifecycle_probe.py`,
  oryginalny zestaw regresji (PR #430);
- jedyny odczyt `mission_material_fleet_lifecycle_snapshot()`
  w `process_snapshot` + prezentacja potrzeb w
  `Active Ecosystem` i szczegółowe blockers/contract w `Cluster`;
- osobne testy UI 0/1/32, brak live admission i odrzucenie
  fałszywych twierdzeń o wykonaniu;
- rozszerzona, jawnie SHA-przypięta lista plików instalatora
  Mission Control **91 → 92**, aktualizowane manifesty i carriers.
  Historyczne 91 plików nie są przepisywane w starszej epoce.

Kandydat wymaga pełnych testów Source Validation, Host Authority
Surface Census, Mission Control packaging/staging, testów fazowych
oraz niezależnego GitHub CI przed scaleniem. Live instalator musi
odczytać kod i JS pod dokładnym `master` oraz zachować
kanoniczną SQLite i rollback.

## Nierozwiązany zależny efekt

Pierwszy kolejny krok po instalacji R9: nadać fazie 0 zaufanego
providera cognitive, fazie 1 osobny, poprawnie admitowany
one-worker preactivation; dla faz 3–5 przygotować nową immutable
kohortę 32 z aktualnym image/worker/source/receipt/mount identity,
a następnie po oddzielnej zgodzie `ActionIR→PDP→RuntimeAdmission`
wykonać `DockerFleetBootstrapExecutor`.

Dopiero prawdziwe odpowiedzi LOCAL i SaaS, materialne bajty
artefaktu, niezależny VERIFY receipt i reconciled completion pod
jednym `mission_id` będą stanowić pełny odbiór LPCL. Nadal nie
ma dowodu pełnego E2E.
