# R5 — LPCL jako jeden synchroniczny logicznie przebieg tworzenia artefaktu

Status: **SOURCE CANDIDATE / NOT MERGED / NOT DEPLOYED**. Scope: istniejący `tools/lion_mission_control_v3.py` i testy izolowane. Nie wykonano zlecenia materialnego, aktywacji LPCL ani zmiany produkcyjnej bazy.

## Cel operatora i znaczenie „jeden proces”

Operator konstruuje LPCL, waliduje dokładne bajty, wiąże currentness i uruchamia **jedną misję**. Misja odpowiada za postęp od rozpoznania potrzeby, przez kontekst i rekonesans SaaS/LOCAL, po wybór wykonawcy, zapis użytecznych bajtów, niezależną weryfikację, artefakt wynikowy i wynik widoczny w panelu. Nie oznacza to jednego synchronicznego wywołania sieciowego: zewnętrzne modele i wykonawcy odpowiadają asynchronicznie. Synchronizacja oznacza trwałe bariery semantyczne i dowodowe pod jednym `mission_id`, `generation`, bieżącym `binding_epoch` i jednym kursorem `GLOBAL_MISSION_SCHEDULER_V1`.

Wymagany schemat:

```text
OPERATOR LPCL (source bytes, digest, effect boundaries)
  -> canonical compiler and PhaseExecutionContract
  -> validated registration, explicit operator activation
  -> existing Global Mission Scheduler (one durable progress owner)
  -> per-phase capability binding + source/context/authority gates
  -> canonical conversation with independent SaaS and LOCAL legs
  -> joined evidence barrier (actual response and payload digests)
  -> existing Bean/Composition/Mosaic decision and bounded materializer
  -> guarded worker assignment, runtime admission, artifact bytes
  -> independent VERIFY + observed receipt
  -> completion evaluator and terminal reconciliation
  -> same mission/conversation/panel readback
```

Każda strzałka wymaga własnego producenta, konsumenta, przyjętej tożsamości i dowodu. Zgodność dwóch modeli nie daje dwóch niezależnych obserwacji. `ACTIVATED` nie oznacza `EFFECT_ADMITTED`. RAG i LPCL nie wystawiają samodzielnie autoryzacji.

## Potwierdzony problem AS-IS na dokładnym źródle

`bind_lpcl_execution()` wymagał świeżego `_docker_local_model_currentness(32)` **przed** utworzeniem topologii, handlerów i aktywnego drivera dla LPCL z `MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL`. Przy braku kohorty aktywacja misji kończyła się trwałym `LPCL_EXECUTION_BIND:` bez wykonywalnej pierwszej fazy. Istniejące `reconcile_lpcl_execution_bindings()` było wywoływane w `main()` na starcie procesu, nie w cyklu schedulera. Udostępnienie 32 workerów później nie dawało tej samej misji automatycznego, obserwowalnego przejścia do gotowego bindingu.

Ten problem występuje przed fazami `CROSS_MODEL_RECON`, `PREACTIVATE_BUILDER`, `FULL_FLEET_PROVIDER_READINESS`, `BUILD_CROSS_MODEL_ARTIFACT`, `VERIFY_CROSS_MODEL_ARTIFACT` z `application_factory_r1`. Ich source-valid program nie oznacza zatem wykonalnego startu. `control_plane_reconnaissance.ensure_material_leases()` wymaga ponadto materialnych workerów w tabeli `material_workers`, dlatego przeniesienie samego bindera przed flotę **nie** rozwiązałoby problemu przez pominięcie obserwatora/lease.

## R5 — wykonany przyrost funkcjonalny

Wykorzystano istniejący `global_scheduler_once()` do ograniczonego częstotliwością (10 s) ponownego sprawdzenia misji już uruchomionej przez operatora, dotąd mającej `adapter=LPCL_MISSION` lub brak adaptera. Rozwiązanie sprawdza operator-control fence, dokładny LPCL runtime selection, wymaga świeżej 32-worker currentness oraz związanych z misją `source_head/source_tree`. Następnie wywołuje **oryginalny** `bind_lpcl_execution()`; ten w ścieżce R5 dodatkowo odrzuca zmianę digestu kohorty między odczytem a wiązaniem. Sukces musi zostać potwierdzony odczytem adaptera oraz 32/32 workerów. Brak kohorty i source drift pozostają `WAITING` bez Docker/start, nowych authority ani drugiego drivera.

Scenariusz dodatni: zarejestrowana, jawnie aktywowana LPCL z brakiem floty; pojawia się dokładne 32-worker currentness z tej samej epoki źródła; **ten sam scheduler** wiąże ten sam `mission_id` bez restartu. Scenariusze negatywne: misja bez aktywacji, niedostępna flota, inny source tree, zmieniony digest w czasie przejścia, ponowne wykonanie po związaniu. Wszystkie testowane w izolowanej tymczasowej bazie SQLite i na syntetycznym odczycie floty.

Zmiana nie uruchamia floty ani nie dowodzi dostępności workerów na MOON.

## Pozostałe obowiązkowe połączenia — nieukończone

**Bootstrap fazowy bez zakleszczenia:** obecny program wymaga 32 materialnych workerów zanim ruszy `CROSS_MODEL_RECON`, a jednocześnie deklaruje preaktywację przed pełną flotą. Potrzebna jest prawdziwa, osobno dopuszczona droga w istniejącym driverze: `CAPABILITY_NEED` -> zaufany builder/preactivation -> aktualny `DOCKER_FLEET_BOOTSTRAP` admission -> 32 per-worker currentness -> rebind. Jeśli początkowe trajektorie LOCAL wymagają jednego workera, należy jawnie związać tę zależność fazy z minimalnym wykonawcą lub dostępnym natywnym providerem LOCAL; nie wolno deklarować gotowości bez materializacji. Stara kohorta R24 ma drift source/receipt/mount i nie jest zatwierdzonym restart candidate.

**Wspólna synchronizacja poznawcza:** `CanonicalConversationSaaSConsumer` i `conversation_chat.submit_chat` mają przekazywać rzeczywiście wykonane LOCAL/SAAS leg wraz z `conversation_id`, `binding_epoch`, `lane_id`, `request_id`, `context_digest`, `projection_digest` i hashem rzeczywiście wysłanych bajtów. `CROSS_MODEL_INTELLIGENCE_BOUND=PASS` dopiero po trwałej odpowiedzi/receipt i niezależnym readbacku. `SEND_UNKNOWN` wymaga rekonsyliacji, nie replay.

**Produkcja artefaktu:** `cooperative_production.advance_build`, `advance_verify`, `cooperative_process_bootstrap`, `artifact_transfer.py` i `swarm` muszą mieć zainstalowane, źródłowo związane call sites. `WRITE` jest odrębną, dopuszczoną materialną akcją; odrębny worker weryfikuje bajty/hash. Obecność descriptorów i syntetyczny receipt nie zamyka odbioru. Wymagany jest także program zbudowania **dwóch różnych** artefaktów z LPCL opisujących inne potrzeby, bez zaszycia obu workflow.

**Panel i deployment:** dopiero zaktualizowany panel Windows/MC/worker, rzeczywisty operator launch, nowe materiały w prywatnym workspace, niezależny odczyt i spójny status `COMPLETE` domkną produkcyjny odbiór. Canary `8782` i PR437 dotyczą wcześniejszych napraw statusu/validacji i nie są dowodem tego obiegu.

## Następna source-level misja

Wprowadzić rzeczywistą `PREPARE_RUNTIME` ścieżkę w jednym oryginalnym driverze LPCL, reprezentowaną przez obsługiwaną klasę capability i zgodną z aktualnym parserem, uruchamianą tylko po istniejącym admission. Rozdzielić obserwację gotowości etapów (native LOCAL, SaaS, pojedynczy worker, 32-workery) oraz sprawdzić, że `CROSS_MODEL_RECON` nie żąda nieistniejącej floty. Użyć istniejącego issuer/provider dla `DOCKER_FLEET_BOOTSTRAP` i zachować jego dokładne `Resource`, `RuntimeAdmission` i consumed-once guard; bez reanimowania historycznych niezgodnych kontenerów. Nie wymyślać drugiego schedulera ani bocznej ścieżki autoryzacji.

Pierwszy materialny odbiór dopiero po prawdziwym operator-launched LPCL, dokładnym source readback, 32 świeżych heartbeatów, rzeczywistym LOCAL+SaaS, zapisanym artefakcie oraz niezależnym verifier receipt w tym samym `mission_id`. Wynik tej kandydackiej poprawki R5 to tylko wznowienie bindingu po pojawieniu się legalnej kohorty — **nie** obietnica gotowej autonomicznej fabryki.
