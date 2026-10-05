# Integracja R6 — wykonanie, artefakty i osobne jarzmo

## Źródło i zakres

R6 jest source candidate nad R5, nie wykonaniem pełnego programu autonomii. Zachowuje dotychczasowy `CooperativeRuntimeWriterProvider`, `PinnedCooperativeContextResolver`, `RuntimeExecutionEngine`, `ExecutorSandbox` i źródła authority/currentness. Nie dodaje drugiego schedulera, brokera ani źródła ALLOW. Pozostają właściwi globalni ownerzy z `LION/architecture/v1_5/semantic_owners.json`.

SaaS może określać cel produktu, interfejsy, kolejność pakietów i propozycję poprawionej generacji. Istniejący driver posiada kursor procesu. Worker otrzymuje mały, związany assignment; verifier odczytuje dokładne bajty produktu, nie udostępniony przez buildera zapisywalny katalog. Model, proces workera, kontener i host są odrębnymi tożsamościami. Wiele workerów korzystających z tego samego modelu nie tworzy wielu niezależnych dowodów.

## Weto przy rzeczywistym admission

```python
from cyber_lion.enterprise.edge_yoke.gate import YokeGate, attach_yoke

gate = YokeGate(
    snapshot=trusted_snapshot_path,
    host_id=expected_host_id,
    public_key=pinned_observer_public_key,
    policy_sha256=pinned_policy_sha256,
)
# Obiekty pochodzą z istniejącego zaufanego composition root, nie z modelu.
admitted_writer = attach_yoke(dependencies=existing_r5_dependencies, gate=gate)
```

`attach_yoke` korzysta bezpośrednio z rodzimego konstruktora R5 w tym repozytorium. Opakowuje `context_source`, zachowując wszystkie pozostałe zależności: admission_source/trust, authority_admission, currentness_source/trust, dispatch_source, admission_guard, sandbox_guard oraz budget_source. Wywołanie resolvera ma gate przed i po odczycie. R5 wywołuje context_source jeszcze raz tuż przed zapisem, więc późne HOLD zatrzymuje również tę granicę. Testy `test_edge_r5_integration` przechodzą przez oryginalny silnik i kontrolowany filesystem; źródła authority są jawnie syntetyczne.

**NO_VETO != ALLOW.** Świeży podpisany snapshot nie wystawia dopuszczenia, nie przywraca cofniętej zgody i nie zeruje guardów ponownego wykonania. Po późnym zatrzymaniu zużyte dopuszczenie nie jest automatycznie zwracane do ponownego użycia.

## Telemetria i korekta

Jarzmo jest osobnym procesem. Mierzy CPU, pamięć i wolne miejsce; sprawdza piny źródeł; utrzymuje EMA i histerezę. Pojedynczy skok jest ostrzeżeniem do przeglądu, nie diagnozą włamania. Brak świeżej próbki to UNKNOWN. Niezgodność źródła zatrzaskuje QUARANTINE także po restarcie. Progi są projektowanymi wartościami początkowymi, nie pomiarem dopuszczalnego obciążenia MOON.

Podpisy Ed25519 i łańcuch hashy wiążą lokalne obserwacje z kluczem. Nie dowodzą poprawności programu lub uczciwości kernela. Obcięcie poprawnego końca wymaga niezależnie zachowanego checkpointu. `export-audit` eksportuje spójny podpisany segment zamiast kopiować aktywną bazę SQLite bez WAL. Klucz prywatny należy do obserwatora i nie trafia do workerów.

`edge_correction.deliver_once` projektuje podpisaną obserwację na istniejący pięciopolowy interfejs `post_protocol_message(mid, x)`: protocol/from_id/to_id/phase/payload. Protokół EVIDENCE, nie CONTROL. Zaufany owner dostarcza aktualny binding misja–rozmowa oraz funkcje publikacji i odczytu zachowanego payloadu. Durable SEND_ATTEMPT powstaje przed I/O; utrata wyniku daje SEND_UNKNOWN i odmowę automatycznego retry. DELIVERY_OBSERVED nie oznacza, że model wykonał korektę. Nie ma tu nowego endpointu lub skopiowanych credentials brokera.

## Most artefaktów i przyszłe repozytoria

`edge_work_unit` wiąże operatorową kwalifikację z hostem, workerem, generacją, źródłowym wykonawcą i oryginalnym bindingiem `artifact_transfer`. Zachowuje dodatkowe współrzędne lane, sesji, message/correlation/causation i source_tree. Fizyczny transfer wykonuje istniejący kanał; katalog `/mnt/data` sesji SaaS nie jest ścieżką na MOON. Każdy odbiorca weryfikuje otrzymane bytes i niezależnie przekazany expected digest.

Przyszłe repozytorium wymaga jawnego ownera, bazy, kontraktów, profilu toolchainu i dopuszczonych ścieżek. Odkrycie hosta nie nadaje mu globalnego exec. Autorytatywnych hostów nie obciążamy dowolnymi buildami. Kod recipe może zostać użyty na innym hoście, ale transport, enrollment kluczy i rozdział domen awarii wymagają rzeczywistego odbioru.

## Nierozwiązane zależności produkcyjne

R5 nadal potrzebuje rzeczywistego powiązania producenta admission/provisioning z kontekstem i prywatnym workspace workera. Pierwotny pilot R1 nie miał MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL; jego zarejestrowany digest nie jest edytowany przez ten patch. Poprawne nowe wejście i aktywacja muszą przejść istniejącą ścieżką LPCL. Kwalifikacja operatorowa nie wypełnia automatycznie completion predicates żywej misji.

Historyczny PACKAGE_IDENTITY_MISMATCH opisany przy R5 pozostaje jawną granicą: historyczny pakiet uruchomieniowy nie został przehashowany, aby udawać wdrożenie nowego bridge'a. R6 aktualizuje tylko dokładne bieżące carriers źródłowego subject digest według istniejącego generatora. Pełne formalization closure, exact-head CI i deployment wymagają osobnego odbioru; nie wytworzono fikcyjnego FCR lub podpisu niezależnego weryfikatora.
