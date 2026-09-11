# LION — AI-native roadmap v1.4

Ten roadmap rozdziela zintegrowane fundamenty, bounded evidence, sfalsyfikowaną generalność, aktywne frontiery architektoniczne i human-authority boundaries. Jest semantic ownerem planowania, a nie dowodem deploymentu, production state ani authority. Default-branch identity i candidate evidence pozostają jawnie rozdzielone przez warstwę dokumentacji v1.4.

## Currentness tej projekcji

Historyczna część roadmapy poniżej opisuje kolejne stany R22/R23/R24 i zachowuje ich exact evidence. Nie wolno odczytywać tych zapisów jako bieżącego `master` tylko dlatego, że nadal znajdują się w tym pliku.

Dla epoki dokumentacyjnej `LION-DOC-R128-2026-09-10-R1` live `master` został odtworzony przed utworzeniem kandydata jako:

```text
HEAD=5e40338511fe2a5f0a891c823b03f9855d6ad1e8
TREE=306b8cf245299517278ab0959a7aca79f66e5343
```

Późniejsze niż R23/R24 integracje obejmują R2/R3, LPCL lineage oraz VKT-R3. Dlatego dokładny bieżący frontier powinien być ponownie wyprowadzony z live code/test/evidence, a nie z historycznej kolejności sekcji tego dokumentu.

## Stan konsolidacji R23 — historyczne evidence

R23 konsolidował wcześniej równoległe lineage: R21 LPCL/Process, R21/P0 `TEST_ONLY` materialization oraz R22C→R22H→R22I Action→Runtime w jednego kandydata `ai_platform`. Exact pre-documentation candidate wynosił `5f90f1c11e9f997ed9c5e3ac1b02c6d802d15745` / tree `5dd5dc653c24bdd810faeb61f901328ad246e3a7`. Pełny repository test discovery dla tego kandydata był `PASS` dla 2410 testów, przy 268 production sources, 236 effect surfaces, sześciu raw unclassified references i zerze unresolved references po taxonomy reconciliation. Production scan digest wynosił `5f6561edcd368c2acce5f0e216bc9e21324da2913035e92ef175b7aca5b773a2`.

Process layer stał się jawny: LPCL 1.0 parsuje do canonical `Process IR`; transitions `ACTION_REQUIRED` emitują wyłącznie `ActionIntentCandidate`. Process semantics nie mintują authority i nie omijają istniejącego łańcucha Action IR → PDP → RuntimeAdmission → RuntimeExecution → observation → reconciliation.

## DELIVERED / zintegrowane fundamenty

Repozytorium zawiera source-backed architecture projection i code perception, Action IR/proposal, canonical PDP handoff, authority i policy-gate primitives, runtime admission, runtime execution, effect-time currentness, runtime reconciliation, executor provisioning contracts, complete/production mediation surfaces, fleet/swarm governance surfaces, Bean/CapabilityNeed/Composition/Mosaic primitives oraz builder-chain binding. F009 pozostaje bounded live end-to-end evidence dla jednej create-only file effect z niezależną observation/reconciliation.

R22F dostarczył reusable inert Action runtime binder. R22I zamknął następny ówczesny Action-plane frontier: dokładny output `bind_allowed_action_to_runtime_inputs` jest konsumowany przez istniejący governed `RuntimeAdmissionEngine` poprzez `admit_bound_action`, który weryfikuje canonical PDP evidence i przekazuje dokładnie binder-produced effect oraz runtime identity do istniejącej ścieżki `admit`. Nie dodano alternate executora, providera, authority source, generic effect entrypoint ani deployment path.

Falsification R22I wzmocniła również trusted currentness przez `provisioned_executor_digest`. Wiąże to exact `ProvisionedExecutor` i odrzuca coherent alternate provisioning tuples zamiast polegać na przypadkowej niespójności pól. Regression matrix R22I obejmuje exact allow consumption, `DENY`, stale currentness, action/resource/payload/authority/mission/provisioning/runtime-identity/PDP-receipt substitution oraz replay. Binder i jego governed-consumption layer nie mintują authority i same nie wykonują effects.

`cyber_lion/contracts/model_plane_adapter.py` pozostaje provider-independent model-plane contract. ASTRA jest compatibility targetem na poziomie kontraktu; ASTRA/local model runtime w tym evidence epoch pozostawał `NOT_OBSERVED`.

## ACTIVE_FRONTIER — reguła po dalszej ewolucji

Historycznie R21 LPCL/Process i R22I binder consumption przestały być oddzielnymi frontierami po wejściu do wspólnego R23 integration train. Następnie R24 i kolejne epoki przesunęły stan dalej. Po integracjach R2/R3 oraz VKT-R3 nie należy przywracać starego R23 procedural frontier jako bieżącego zadania.

Bieżący frontier musi zostać wyznaczony w następującej kolejności:

```text
LIVE MASTER / EXACT GIT
-> CURRENT CODE + TESTS / CI
-> MACHINE EVIDENCE
-> FRESH PROJECTIONS
-> HISTORICAL ROADMAP
```

Runtime deployment, provider selection, real child activation, production deployment i authority minting pozostają odrębnymi klasami efektów i nie mogą zostać wyprowadzone z dokumentacji.

## PARTIAL / falsified / carried-forward tracks

- **Factory/autonomy:** Bean i composition primitives istnieją. B0 przechodzi dla dwóch unseen families wyłącznie wewnątrz closed grammar. Celowo out-of-grammar family `float-list` jest odrzucana, więc **general Factory generativity jest sfalsyfikowana poza B0**, a nie wyprowadzana z sukcesu B0. Activated child autonomy i Factory-of-Factories pozostają nieudowodnione.
- **Fleet/swarm:** kontrakty oraz governance/runtime trust surfaces istnieją; większa operational federation i niezależne physical failure domains wymagają osobnych dowodów. Historyczny VKT-R3 pokazał 3 × 128 real Kubernetes Pods w ograniczonym `TEST_ONLY` przebiegu, ale ten eksperyment nie jest dowodem 384 niezależnych physical executors ani stale aktywnego runtime.
- **Complete mediation:** contract/implementation surfaces istnieją; `GlobalCompleteMediation` nie powinno być promowane ponad stan wspierany przez exhaustive effect-surface evidence.
- **Model plane:** ASTRA-compatible provider-independent request/candidate semantics są obecne jako non-effectful contract. Wcześniejsze host evidence nie dowodziło ASTRA/local runtime deployment.
- **Preproduction:** wejście pozostaje zależne od evidence dla isolation, rollback/recovery, currentness, mediation, authority separation i physical-domain requirements.
- **Cyber-physical:** schema/design nie jest hardware capability; physical execution pozostaje przyszłą governed surface, dopóki właściwe safety/interlock evidence nie zamknie granic.

## Historyczne R22I source/effect i census evidence

Na exact pre-documentation candidate `b4045878be064586a61efa0f3ec8be5103a5a08c` production source count wynosił 260, a effect surface count 236. Sześć raw unclassified references pozostawało widocznych, a taxonomy reconciliation rozwiązywała wszystkie sześć bez ich ukrywania. Production scan digest: `c643ab174bec81dc86fde535be72230c88cfc557a2ca5596f9362db259d02724`; stabilne counts nie usuwają production-byte drift R22I, który zmienił ten digest.

Exact b404 Full Symbol Census był `PASS`: 502 committed Python files, 502 parsed files, zero parse failures, 8617 symbols, 6784 public symbols i 1052 private-material symbols, census digest `118d23e2508b0dfcab84f2cef95381d7f4cbf68b272323013174bae82d8a1835`. To pre-documentation evidence. Documentation/carrier commits zmieniają Git identity, dlatego final carrier-bound HEAD wymagał nowego exact census run.

## Historyczne R23 source/effect i census evidence

Exact pre-documentation R23 evidence było związane z `5f90f1c11e9f997ed9c5e3ac1b02c6d802d15745` / `5dd5dc653c24bdd810faeb61f901328ad246e3a7`. Względem ówczesnego master kandydat rósł z 256 do 268 production sources bez removals; 12 additions obejmowało parę census R22C, kontrakty Action-runtime/model R22F/R22I oraz source set R21 LPCL/Process. Effect surface count pozostawał 236. Raw inventory digest: `548f7b7db610e793e6ec79c707db423bb82ca61a238c3edce5e638b2696ea79d`, reconciled inventory digest `6435a273d31f21393ac5748ce7c551a36897a8e136240483173b107292be06c4`, taxonomy reconciliation digest `5445e88512ef25352d877550482abd3dd611ea35138c546662f72ba7e29575fe`, production scan digest `5f6561edcd368c2acce5f0e216bc9e21324da2913035e92ef175b7aca5b773a2`.

Deterministic full Python symbol census na tym exact pre-documentation candidate sparsował 535/535 committed Python files bez failures i zidentyfikował 9062 symbols (7154 public; 1079 private-material). Census digest: `e559866f26b14800273e504639895048d8c923466a46609c556e1a7e5351587f`. Ponieważ documentation/carrier commits zmieniały Git identity, final exact-head census pozostawał obowiązkowy po carrier-last closure.

## Federation / documentation homeostasis

Ostatni jawny ten-repository live federation sweep w tej części historycznej lineage pozostaje evidence R22H. Późniejsze dokumenty nie powinny po cichu promować tego sweepu do nowej federation observation. Federation currentness pozostaje historycznym evidence do chwili osobnego reacquisition.

Documentation homeostasis loop regeneruje source/effect truth i census evidence bez zamiany dokumentacji w authority. Dynamiczne `CURRENT` bez reprodukowalnej identity evidence degraduje do `STALE`/`UNKNOWN`.

Bieżąca epoka R128 dodatkowo ustanawia Polish-primary dla human-facing documentation i oddziela translację od semantycznej aktualizacji machine projections.

## Physical i operational boundary

Historyczne host observations pozostają documentation evidence dla swoich epok. Cztery logiczne WSL2 hosts nie oznaczają czterech niezależnych physical failure domains. Dokumentacja nie może przekształcić logic separation w physical independence, utworzyć signer principal ani instancjonować ASTRA/local model runtime.

VKT-R3 rozszerzył później empiryczne evidence o ograniczony K3s `TEST_ONLY` substrate i rzeczywiste Pods, lecz również ten fakt nie zmienia physical-domain claim bez odrębnego dowodu sprzętowego i administracyjnego.

## Dłuższy target

Targetem pozostaje governed Bean Factory, w której capability gaps mogą być materializowane do bounded candidate components, niezależnie weryfikowane, admitted pod explicit authority oraz obserwowane/rekonsyliowane po effects. Recursive child autonomy i Factory-of-Factories wymagają nowego evidence i explicit authority gates; nie wynikają z composition primitives, bounded B0 experiments ani model compatibility contracts.

## R24 → R23 reconciliation checkpoint — historyczne evidence

R24 stał się częścią canonical `master` przy `ab1ab2f2cbdeda1f10b2c73e78acf230f5be21da`. R23 został więc reacquired zamiast scalony ze stale frozen head. Clean post-R24 pre-documentation reconciliation candidate wynosił `93afd90f781d5421ad30dfcad92650347965dd0d` / `e7f56e9de9a014a2371192c191e8f5471a547a37`: 268 production sources, 239 effect surfaces, sześć raw unclassified references, zero unresolved taxonomy references, stable scan digest `861d7e2aed0d5e1dbf32aa6e13ae942682876cec4efcf4985bed4d14815725e2` oraz 2425/2425 passing repository tests z pięcioma controlled skips. Ten checkpoint nie przepisuje wcześniejszego R23 evidence; zapisuje późniejszy reconciliation state, który nadal wymagał carrier-last truth rebinding, exact-head CI/security i osobnego merge authority dla PR #303.

## Etap po R23/R24: R2/R3, LPCL i VKT-R3

Po historycznym checkpoint R23/R24 repozytorium przeszło kolejne merge'e i procesy konwergencji, a następnie zintegrowało VKT-R3. W historycznej misji VKT-R3 zwalidowano 384 real Kubernetes drone Pods, po 128 TIGER/SPECTRA/LION, 384 unikalne UID, zero restartów, pełny zestaw 36 przypadków oraz bounded cleanup. Późniejsze zmiany związały lokalny Mission Control z canonical `master` i udostępniły niesensytywny runtime locator operatorowi.

Te wyniki zmieniają roadmap w dwóch miejscach. Po pierwsze, „large fleet” nie jest już wyłącznie abstrakcyjnym targetem: istnieje ograniczone real-Pod evidence dla konkretnego `TEST_ONLY` eksperymentu. Po drugie, dokumentacja runtime musi konsekwentnie odróżniać `HISTORICAL_TEST_EVIDENCE` od `ACTIVE_RUNTIME_NOW`.

Nie wynika z tego production readiness, general Kubernetes authority, vendor test authority ani physical-domain independence.

## Kolejny krok dokumentacyjny

Po zakończeniu bieżącej translacji i porządkowania prose layer należy ponownie wygenerować albo zweryfikować machine-readable current-state projections, federation vectors, documentation gaps oraz truth/currentness carriers względem exact live baseline.

```text
TRANSLATED_PROSE
!=
CURRENT_MACHINE_PROJECTION
```

Minimalny następny proces:

```text
REACQUIRE EXACT MASTER
-> REGENERATE CURRENT STATE
-> REGENERATE DOCUMENTATION GAPS
-> VERIFY SEMANTIC OWNERS
-> VALIDATE LINKS / SCHEMAS / CURRENTNESS
-> FALSIFY OVERCLAIMS
-> READ BACK CANDIDATE
-> RECONCILE
```

Dopiero potem roadmap może otrzymać nową, evidence-bound klasyfikację bieżącego frontieru.
